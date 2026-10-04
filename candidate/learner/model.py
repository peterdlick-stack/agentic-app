"""Frozen-contract v1 ranking and genuine scenario learning. Scores are uncalibrated."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import time
import numpy as np

VERSION = "scenario-logistic-v1"
SEED = 20261004
FIELDS = ("bpm", "rms_dbfs", "dynamic_db")
ACTIVITIES = ("unknown", "stationary", "walking", "running", "cycling", "reading", "workout", "relax")
TARGETS = dict(walking=104, running=136, cycling=124, reading=70, workout=136, relax=68)
PARAMS = dict(l2=1., learning_rate=.05, steps=400)


def canonical(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(obj):
    return hashlib.sha256(canonical(obj).encode()).hexdigest()


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def song_split(content_id):
    bucket = int(hashlib.sha256((content_id + "|20261004").encode()).hexdigest(), 16) % 10
    return "sealed" if bucket < 2 else "validation" if bucket == 2 else "development"


def effective_context(context, now=None, strict=False):
    now = time.time() if now is None else now
    c = context or {}
    observed, until = c.get("observed_at"), c.get("valid_until")
    valid = (number(now) and number(observed) and number(until) and observed <= now <= until
             and c.get("allowed_for_current") is True and c.get("historical") is False
             and c.get("activity") in ACTIVITIES and c.get("source_kind") not in (None, "historical_replay"))
    if c.get("activity") in ("reading", "relax") and c.get("source_kind") != "manual":
        valid = False
    if strict and not valid:
        raise ValueError("expired_future_or_inadmissible_context")
    return c.get("activity", "unknown") if valid else "unknown"


def validate_features(rows):
    out = {}
    for row in rows:
        cid = row["content_id"]
        if cid in out:
            raise ValueError("duplicate_feature_identity")
        for field in (*FIELDS, "vocal"):
            f = row.get("features", {}).get(field)
            required = {"value", "unit", "method_version", "source", "kind", "quality", "reason"}
            if not isinstance(f, dict) or not required.issubset(f):
                raise ValueError("missing_required_feature_field:" + field)
            v = f["value"]
            if v is not None and (type(v) is not bool if field == "vocal" else not number(v)):
                raise ValueError("invalid_feature_value:" + field)
            if f["quality"].get("calibrated") is not False:
                raise ValueError("unsupported_feature_quality_calibration")
        out[cid] = row
    return out


def raw_features(cid, rows):
    return [rows.get(cid, {}).get("features", {}).get(f, {}).get("value") for f in FIELDS]


def design(raw, activities, transform=None):
    a = np.array([[np.nan if v is None else v for v in row] for row in raw], dtype=float)
    missing = np.isnan(a)
    if transform is None:
        median = np.array([np.median(a[~missing[:, j], j]) if (~missing[:, j]).any() else 0.
                           for j in range(len(FIELDS))])
        filled = np.where(missing, median, a)
        mean, std = filled.mean(axis=0), filled.std(axis=0)
        std = np.where(std < 1e-8, 1., std)
        transform = dict(median=median.tolist(), mean=mean.tolist(), std=std.tolist())
    filled = np.where(missing, np.array(transform["median"]), a)
    z = (filled - np.array(transform["mean"])) / np.array(transform["std"])
    z = np.clip(z, -10, 10)
    base = np.concatenate([z, missing.astype(float)], axis=1)
    context = np.array([[float(activity == name) for name in ACTIVITIES] for activity in activities])
    interaction = (base[:, :, None] * context[:, None, :]).reshape(len(a), -1)
    return np.concatenate([np.ones((len(a), 1)), base, context, interaction], axis=1), transform


def rank(tracks, feature_rows, context, preferences, policy="P0", model=None, now=None):
    if policy not in ("P0", "P1", "P2"):
        raise ValueError("unknown_policy")
    now = time.time() if now is None else now
    rows = validate_features(feature_rows)
    activity = effective_context(context, now)
    effective, status = policy, "OK"
    if policy == "P2" and (not model or model.get("status") != "TRAINED"):
        effective, status = "P0", "UNTRAINED"
    elif policy == "P2":
        if model.get("version") != VERSION or model.get("synthetic") is not False:
            raise ValueError("invalid_model_provenance_or_version")
        if model["trained_until"] >= now:
            raise ValueError("future_label_leakage")
        if model["feature_hash"] != digest(feature_rows):
            raise ValueError("model_feature_version_mismatch")
    if activity in ("unknown", "stationary"):
        effective = "P0"
        if status == "OK" and policy != "P0":
            status = "CONTEXT_FALLBACK"
    learned = (preferences or {}).get("tracks", {})
    result = []
    for track in tracks:
        cid = track["content_id"]
        pref = learned.get(cid, 0)
        if not number(pref):
            raise ValueError("invalid_preference_value")
        score = .35 * pref / (abs(pref) + 2)
        reason, evidence = "ordinary explicit song preference", False
        bpm = raw_features(cid, rows)[0]
        if effective == "P1" and activity in TARGETS and bpm is not None:
            score += 1 - min(abs(bpm - TARGETS[activity]) / 100, 1)
            reason, evidence = "soft estimated BPM rule; no hard tempo constraint", True
        if effective == "P2":
            x, _ = design([raw_features(cid, rows)], [activity], model["transform"])
            score = float(x[0] @ np.array(model["weights"]))
            reason = "uncalibrated scenario logit"
        result.append(dict(track, score=round(score, 8), context_evidence=evidence, reason=reason,
                           score_semantics="uncalibrated_ranking_score",
                           seen_in_training=cid in (model or {}).get("seen_content_ids", [])))
    result.sort(key=lambda t: (-t["score"], t["content_id"]))
    return dict(requested_policy=policy, effective_policy=effective, status=status, tracks=result,
                effective_activity=activity, algorithm_version=VERSION, predicted_at=now)


def _validate_bundle(bundle, cutoff):
    from .store import validate_bundle
    return validate_bundle(bundle, cutoff)


def train(events, feature_rows, output_path=None, now=None):
    """events is the immutable store export bundle, not an unverified list of labels."""
    now = time.time() if now is None else now
    rows = validate_features(feature_rows)
    all_events = _validate_bundle(events, now)
    # Sealed labels never enter eligibility, preprocessing, fit or parameter selection.
    eligible = [e for e in all_events if song_split(e["content_id"]) != "sealed"
                and e["target"] == "scenario_acceptance" and e["provenance"] == "real_user"
                and type(e["value"]) is int and e["value"] in (0, 1)]
    development = [e for e in eligible if song_split(e["content_id"]) == "development"]
    def counts(group):
        return dict(n=len(group), positive=sum(e["value"] == 1 for e in group),
                    negative=sum(e["value"] == 0 for e in group),
                    complete_sessions=len({e["session_id"] for e in group if e["session_complete"]}))
    total, dev = counts(eligible), counts(development)
    ready = (total["n"] >= 40 and min(total["positive"], total["negative"]) >= 10
             and total["complete_sessions"] >= 5 and dev["n"] >= 30
             and min(dev["positive"], dev["negative"]) >= 8 and dev["complete_sessions"] >= 4)
    model = dict(version=VERSION, status="TRAINED" if ready else "UNTRAINED", synthetic=False,
                 params=PARAMS, seed=SEED, eligibility_counts=total, development_counts=dev,
                 training_data_hash=digest(development), evidence_bundle_hash=digest(events),
                 feature_hash=digest(feature_rows), score_semantics="uncalibrated_ranking_score",
                 sealed_used_for_training=False, user_benefit="NO_USER_BENEFIT_EVIDENCE")
    if eligible and any(e["snapshot"].get("feature_hash") != digest(feature_rows) for e in eligible):
        raise ValueError("training_snapshot_feature_hash_mismatch")
    if ready:
        if len({e["feature_version"] for e in eligible}) != 1:
            raise ValueError("mixed_feature_versions")
        raw = [raw_features(e["content_id"], rows) for e in development]
        acts = [effective_context(e["context"], e["exposed_at"], strict=True) for e in development]
        x, transform = design(raw, acts)
        y = np.array([e["value"] for e in development])
        weights = np.zeros(x.shape[1])
        for _ in range(PARAMS["steps"]):
            p = 1 / (1 + np.exp(-np.clip(x @ weights, -40, 40)))
            penalty = weights.copy()
            penalty[0] = 0
            weights -= PARAMS["learning_rate"] * (x.T @ (p-y) / len(y) + PARAMS["l2"] * penalty / len(y))
        model.update(weights=weights.tolist(), transform=transform,
                     trained_until=max(e["recorded_at"] for e in development),
                     seen_content_ids=sorted({e["content_id"] for e in development}))
    if output_path:
        Path(output_path).write_text(json.dumps(model, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    return model


def predict_before_update(tracks, feature_rows, context, preferences, bundle, at):
    """Prefix-only prequential prediction; future events are removed before fitting."""
    kept_events = [e for e in bundle["events"] if e["recorded_at"] < at]
    exposure_ids = {e["exposure_id"] for e in kept_events}
    exposures = [e for e in bundle["exposures"] if e["exposure_id"] in exposure_ids and e["exposed_at"] < at]
    snapshot_ids = {e["snapshot_id"] for e in exposures}
    prefix = dict(events=kept_events, exposures=exposures,
                  snapshots=[s for s in bundle["snapshots"] if s["snapshot_id"] in snapshot_ids and s["created_at"] < at],
                  sessions=[s for s in bundle["sessions"] if s["completed_at"] < at])
    model = train(prefix, feature_rows, now=at)
    return rank(tracks, feature_rows, context, preferences, "P2", model, at)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--events", required=True, help="store export JSON bundle")
    p.add_argument("--features", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    model = train(json.loads(Path(args.events).read_text()), json.loads(Path(args.features).read_text()), args.output)
    print(json.dumps({k:model[k] for k in ("status", "eligibility_counts", "training_data_hash")}))


if __name__ == "__main__":
    main()
