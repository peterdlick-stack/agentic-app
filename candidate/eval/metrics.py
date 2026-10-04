"""Frozen numerical gates and source-bound paired-study protocol validation.

Synthetic fixtures validate mechanisms only. Source hashes prove consistency, not
that a human or trusted device actually produced a self-consistent forged bundle.
"""
import hashlib
import itertools
import json
import math
import re
import sys
from pathlib import Path
import numpy as np

SEED = 20261004
POLICIES = ("P0", "P1", "P2")
VERSION_KEYS = ("request_hash", "library_hash", "feature_hash", "initial_preferences_hash")
PARAMS = dict(l2=1., learning_rate=.05, steps=400)


def number(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def without(value, *keys):
    return {k: v for k, v in value.items() if k not in keys}


def bpm_metrics(rows):
    labeled = [r for r in rows if r.get("split") == "sealed" and r.get("truth_source")
               and number(r.get("truth_bpm")) and r["truth_bpm"] > 0]
    valid = [r for r in labeled if number(r.get("bpm")) and r["bpm"] > 0]
    hit = sum(abs(r["bpm"] / r["truth_bpm"] - 1) <= .05 for r in valid)
    n = len(labeled)
    coverage = len(valid) / n if n else None
    return dict(truth_count=n, valid_count=len(valid), hit_rate=hit/n if n else None,
                coverage=coverage, conditional_hit_rate=hit/len(valid) if valid else None,
                mae=sum(abs(r["bpm"]-r["truth_bpm"]) for r in valid)/len(valid) if valid else None,
                octave_errors=sum(min(abs(r["bpm"]/r["truth_bpm"]-2)/2,
                                      abs(r["bpm"]/r["truth_bpm"]-.5)/.5) <= .05 for r in valid),
                status="BPM_GATE_SUPPORTED" if n >= 30 and hit/n >= .8 and coverage >= .8
                else "FEATURES_ESTIMATED")


def freeze_sample_size(dev_session_differences):
    if (not isinstance(dev_session_differences, (list, tuple))
            or len(dev_session_differences) < 6
            or not all(number(x) and -1 <= x <= 1 for x in dev_session_differences)):
        return dict(status="SAMPLE_SIZE_BLOCKED", reason="need >=6 finite real development paired-session differences")
    variance = float(np.var(dev_session_differences, ddof=1))
    if not math.isfinite(variance) or variance <= 0:
        return dict(status="SAMPLE_SIZE_BLOCKED", reason="variance not estimable")
    return dict(status="FROZEN",
                sessions=math.ceil(max(12, (1.96+.841621)**2*variance/.10**2)/.8),
                effect=.10, alpha=.05, power=.80, paired_session_variance=variance,
                method="paired-session normal planning approximation; 20% reserve; must freeze before test")


def schedule(sessions):
    if type(sessions) is not int or not 0 <= sessions <= 100000:
        raise ValueError("invalid_session_count")
    orders = list(itertools.permutations(POLICIES))
    rng = np.random.default_rng(SEED)
    rng.shuffle(orders)
    return [dict(session_index=i, policy_order=list(orders[i % 6]), exposures_each=6,
                 no_repeat_content_within_session=True) for i in range(sessions)]


def interval(values):
    if not isinstance(values, (list, tuple)) or len(values) < 2 or not all(number(x) for x in values):
        return None
    a = np.asarray(values, float)
    rng = np.random.default_rng(SEED)
    means = np.mean(a[rng.integers(0, len(a), size=(10000, len(a)))], axis=1)
    return [float(x) for x in np.quantile(means, [.025, .975])]


def numerical_gates(stats, planned_n):
    """Each predicate is independently observable; no short-circuit hides a gate."""
    def ci(value):
        return (isinstance(value, (list, tuple)) and len(value) == 2
                and all(number(x) and -1 <= x <= 1 for x in value) and value[0] <= value[1])
    n = stats.get("complete_sessions")
    missing = stats.get("missing_rates")
    diff = stats.get("p2_p0_difference")
    gain, worst, interruption = (stats.get(k) for k in
                                ("p2_p0_ci", "worst_missing_difference_ci", "interruption_difference_ci"))
    return {
        "fixed_sample_size": type(planned_n) is int and planned_n > 0 and type(n) is int and n >= planned_n,
        "missing_at_most_20pct": isinstance(missing, dict) and set(missing) == set(POLICIES)
            and all(number(x) and 0 <= x <= .20 for x in missing.values()),
        "gain_at_least_10pp": number(diff) and .10 <= diff <= 1,
        "gain_lower_positive": ci(gain) and gain[0] > 0,
        "worst_missing_lower_positive": ci(worst) and worst[0] > 0,
        "interruption_upper_nonpositive": ci(interruption) and interruption[1] <= 0,
    }


def descriptive_metrics(rows):
    good = [r for r in rows if isinstance(r, dict) and r.get("policy") in POLICIES]
    conditions = {}
    groups = {}
    for r in good:
        if type(r.get("session_id")) is str:
            groups.setdefault(r["session_id"], {}).setdefault(r["policy"], []).append(r)
    for p in POLICIES:
        a = [r for r in good if r["policy"] == p]
        obs = [r["accept"] for r in a if type(r.get("accept")) is int and r["accept"] in (0, 1)]
        conditions[p] = dict(exposures=len(a), observed=len(obs),
                             missing_rate=(len(a)-len(obs))/len(a) if a else None,
                             acceptance=sum(obs)/len(obs) if obs else None,
                             skips=sum(r.get("skipped") is True for r in a))
    diffs, other, interruptions, worst = [], [], [], []
    for sid in sorted(groups):
        g = groups[sid]
        if set(g) != set(POLICIES) or any(len(g[p]) != 6 for p in POLICIES):
            continue
        if any(r.get("accept") is not None and not (type(r.get("accept")) is int and r["accept"] in (0, 1))
               for a in g.values() for r in a):
            continue
        observed = {p: [r["accept"] for r in g[p] if r.get("accept") is not None] for p in POLICIES}
        if not all(observed.values()):
            continue
        rates = {p: sum(a)/len(a) for p, a in observed.items()}
        diffs.append(rates["P2"]-rates["P0"])
        other.append(rates["P2"]-rates["P1"])
        worst.append(sum(r.get("accept") or 0 for r in g["P2"])/6
                     - sum(1 if r.get("accept") is None else r["accept"] for r in g["P0"])/6)
        interruptions.append(sum(1 if r.get("interruption") is None else r["interruption"] for r in g["P2"])/6
                             - sum(r.get("interruption") or 0 for r in g["P0"])/6)
    return dict(conditions=conditions, complete_sessions=len(diffs),
                p2_p0_difference=float(np.mean(diffs)) if diffs else None,
                p2_p0_ci=interval(diffs), p2_p1_ci=interval(other),
                interruption_difference_ci=interval(interruptions),
                worst_missing_difference_ci=interval(worst),
                missing_rates={p: conditions[p]["missing_rate"] for p in POLICIES})


def registration_core(plan):
    return {k: plan.get(k) for k in ("status", "evidence_kind", "sessions", "session_ids", "seed",
                                    "frozen_at", "development_data_hash", "paired_session_variance",
                                    "schedule", "versions", "model_hash")}


def song_split(content_id):
    bucket = int(hashlib.sha256((content_id+"|20261004").encode()).hexdigest(), 16) % 10
    return "sealed" if bucket < 2 else "validation" if bucket == 2 else "development"


def validate_protocol(rows, plan):
    reasons = []
    def check(ok, reason):
        if not ok and reason not in reasons:
            reasons.append(reason)
        return ok
    def index(items, key, name):
        result = {}
        if not isinstance(items, list):
            check(False, name+"_missing_or_invalid")
            return result
        for item in items:
            if not isinstance(item, dict) or type(item.get(key)) is not str or not item[key]:
                check(False, name+"_invalid_record")
                continue
            check(item[key] not in result, name+"_duplicate_id")
            result[item[key]] = item
        return result
    evidence = plan.get("evidence")
    if not isinstance(evidence, dict):
        return ["evidence_bundle_missing"]
    kind = plan.get("evidence_kind")
    check(kind in ("synthetic", "real_user"), "evidence_kind_invalid")
    sources = index(evidence.get("sources"), "source_id", "source")
    for src in sources.values():
        payload = src.get("payload")
        check(isinstance(payload, dict) and src.get("sha256") == digest(payload), "source_digest_mismatch")
        if isinstance(payload, dict):
            check(payload.get("evidence_kind") == kind, "source_kind_mismatch")
            check(type(payload.get("collector")) is str and bool(payload["collector"]), "source_collector_missing")
            check(number(payload.get("captured_at")), "source_capture_time_invalid")
    used_sources = set()
    def backed(record, expected_kind, time_key):
        source_id = record.get("source_id")
        src = sources.get(source_id, {})
        payload = src.get("payload", {})
        used_sources.add(source_id) if type(source_id) is str else None
        return check(isinstance(payload, dict) and payload.get("kind") == expected_kind
                     and payload.get("data") == without(record, "source_id")
                     and payload.get("captured_at") == record.get(time_key),
                     expected_kind+"_source_mismatch")
    frozen, cutoff = plan.get("frozen_at"), plan.get("collected_until")
    valid_clock = check(number(frozen) and number(cutoff) and frozen < cutoff, "plan_time_invalid")
    freeze = frozen if number(frozen) else -math.inf
    until = cutoff if number(cutoff) else -math.inf
    check(plan.get("status") == "FROZEN", "plan_not_frozen")
    n = plan.get("sessions")
    valid_n = check(type(n) is int and 1 <= n <= 100000, "planned_n_invalid")
    session_ids = plan.get("session_ids")
    valid_ids = check(isinstance(session_ids, list) and all(type(s) is str and s for s in session_ids)
                      and len(session_ids) == len(set(session_ids)) and valid_n and len(session_ids) == n,
                      "planned_session_ids_invalid")
    trial_ids = set(session_ids) if valid_ids else set()
    check(plan.get("seed") == SEED and type(plan.get("seed")) is int, "schedule_seed_mismatch")
    if valid_n:
        check(plan.get("schedule") == schedule(n), "schedule_not_frozen_balanced_order")
    versions = plan.get("versions", {})
    if not isinstance(versions, dict):
        check(False, "version_hashes_invalid")
        versions = {}
    valid_versions = check(isinstance(versions, dict) and set(versions) == set(VERSION_KEYS)
                           and all(type(x) is str and len(x) == 64 and all(c in "0123456789abcdef" for c in x)
                                   for x in versions.values()), "version_hashes_invalid")

    development = evidence.get("development", {})
    if not isinstance(development, dict):
        development = {}
    dev_sessions = index(development.get("sessions"), "session_id", "development_session")
    dev_rows = index(development.get("rows"), "exposure_id", "development_exposure")
    check(plan.get("development_data_hash") == digest(development), "development_data_hash_mismatch")
    check(not (set(dev_sessions) & trial_ids), "development_trial_overlap")
    independence = []
    for session in dev_sessions.values():
        backed(session, "development_session", "completed_at")
        independence.append(session.get("independent_unit"))
        check(number(session.get("started_at")) and number(session.get("completed_at"))
              and session["started_at"] < session["completed_at"] < freeze, "development_session_time_invalid")
    check(all(type(s) is str and s for s in independence) and len(set(independence)) == len(independence),
          "development_sessions_not_independent")
    dev_groups = {}
    seen_dev_content = set()
    for record in dev_rows.values():
        backed(record, "development_observation", "recorded_at")
        sid, p = record.get("session_id"), record.get("policy")
        check(sid in dev_sessions and p in ("P0", "P2"), "development_row_orphan_or_policy")
        check(record.get("effective_policy") == p, "development_policy_not_delivered")
        check(type(record.get("accept")) is int and record["accept"] in (0, 1),
              "development_observation_missing_or_invalid")
        pair = (sid, record.get("content_id"))
        check(type(record.get("content_id")) is str and bool(re.fullmatch(r"sha256:[0-9a-f]{64}", record["content_id"]))
              and pair not in seen_dev_content, "development_content_repeat_or_invalid_hash")
        seen_dev_content.add(pair)
        s = dev_sessions.get(sid, {})
        check(number(record.get("exposed_at")) and number(record.get("recorded_at"))
              and number(s.get("started_at")) and number(s.get("completed_at"))
              and s["started_at"] <= record["exposed_at"] <= record["recorded_at"] <= s["completed_at"] < freeze,
              "development_time_invalid")
        if type(sid) is str and p in ("P0", "P2") and type(record.get("accept")) is int:
            dev_groups.setdefault(sid, {}).setdefault(p, []).append(record["accept"])
    differences = []
    for sid in dev_sessions:
        g = dev_groups.get(sid, {})
        if check(set(g) == {"P0", "P2"} and all(len(a) == 6 for a in g.values()),
                 "development_equal_exposure_count"):
            differences.append(sum(g["P2"])/6-sum(g["P0"])/6)
    size = freeze_sample_size(differences)
    check(size.get("status") == "FROZEN", "development_sample_size_unavailable")
    check(valid_n and n == size.get("sessions"), "sample_size_not_recomputed")
    check(number(plan.get("paired_session_variance"))
          and plan["paired_session_variance"] == size.get("paired_session_variance"), "development_variance_mismatch")

    training = evidence.get("training", {})
    if not isinstance(training, dict):
        training = {}
    train_sessions = index(training.get("sessions"), "session_id", "training_session")
    labels = index(training.get("labels"), "event_id", "training_label")
    check(not (set(train_sessions) & trial_ids), "training_trial_overlap")
    for session in train_sessions.values():
        backed(session, "training_session", "completed_at")
        check(number(session.get("started_at")) and number(session.get("completed_at"))
              and session["started_at"] < session["completed_at"] < freeze, "training_session_time_invalid")
    units = [s.get("independent_unit") for s in train_sessions.values()]
    check(all(type(s) is str and s for s in units) and len(set(units)) == len(units),
          "training_sessions_not_independent")
    bundle = training.get("bundle", {})
    validated_labels = []
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from learner.store import validate_bundle
        validated_labels = validate_bundle(bundle, freeze)
    except (TypeError, ValueError, KeyError, AttributeError) as exc:
        check(False, "training_bundle_invalid:"+str(exc))
    expected_labels = {x["event_id"]: x for x in validated_labels}
    check(set(labels) == set(expected_labels), "training_bundle_label_set_mismatch")
    for session in train_sessions.values():
        matches = [x for x in bundle.get("sessions", []) if isinstance(x, dict) and x.get("session_id") == session["session_id"]] if isinstance(bundle, dict) else []
        check(len(matches) == 1 and matches[0].get("completed_at") == session.get("completed_at")
              and matches[0].get("provenance") == kind, "training_bundle_session_mismatch")
    eligible, dev_labels = [], []
    seen_training_exposure = set()
    for label in labels.values():
        backed(label, "training_label", "recorded_at")
        check(label.get("provenance") == kind, "training_label_provenance_mismatch")
        check(without(label, "source_id") == expected_labels.get(label["event_id"]), "training_bundle_label_mismatch")
        exposure_key = (label.get("exposure_id"), label.get("target"))
        check(type(label.get("exposure_id")) is str and exposure_key not in seen_training_exposure,
              "training_duplicate_exposure_target")
        seen_training_exposure.add(exposure_key)
        check(label.get("session_id") in train_sessions, "training_label_orphan")
        check(label.get("target") == "scenario_acceptance" and type(label.get("value")) is int
              and label["value"] in (0, 1), "training_label_invalid")
        check(isinstance(label.get("snapshot"), dict) and label["snapshot"].get("feature_hash") == versions.get("feature_hash"), "training_feature_mismatch")
        session = train_sessions.get(label.get("session_id"), {})
        check(number(label.get("recorded_at")) and number(session.get("started_at"))
              and number(session.get("completed_at"))
              and session["started_at"] <= label["recorded_at"] <= session["completed_at"] < freeze,
              "training_label_time_invalid")
        cid = label.get("content_id")
        if type(cid) is str and re.fullmatch(r"sha256:[0-9a-f]{64}", cid) and label.get("target") == "scenario_acceptance" and type(label.get("value")) is int:
            split = song_split(cid)
            if split != "sealed":
                eligible.append(without(label, "source_id"))
            if split == "development":
                dev_labels.append(without(label, "source_id"))
        else:
            check(False, "training_content_invalid")
    dev_labels.sort(key=lambda x: (x["recorded_at"], x["event_id"]))
    def enough(group, total, each, sessions):
        return (len(group) >= total and sum(x.get("value") == 1 for x in group) >= each
                and sum(x.get("value") == 0 for x in group) >= each
                and len({x.get("session_id") for x in group if x.get("session_id") in train_sessions
                         and (kind == "synthetic" or x.get("session_complete") is True)}) >= sessions)
    check(enough(eligible, 40, 10, 5) and enough(dev_labels, 30, 8, 4), "p2_training_ineligible")
    model = evidence.get("model", {})
    if not isinstance(model, dict):
        model = {}
    check(plan.get("model_hash") == digest(model), "model_hash_mismatch")
    check(model.get("status") == "TRAINED" and model.get("version") == "scenario-logistic-v1"
          and model.get("synthetic") is (kind == "synthetic"), "p2_model_untrained_or_provenance")
    check(model.get("params") == PARAMS and all(number(v) for v in (model.get("params") or {}).values())
          and model.get("seed") == SEED and type(model.get("seed")) is int, "model_parameters_changed")
    check(model.get("feature_hash") == versions.get("feature_hash"), "model_feature_mismatch")
    model_record = training.get("model_record", {})
    if not isinstance(model_record, dict):
        model_record = {}
    backed(model_record, "model_record", "created_at")
    check(model_record.get("model_hash") == digest(model), "model_record_hash_mismatch")
    check(model.get("evidence_bundle_hash") == digest(bundle)
          and model.get("training_data_hash") == digest(dev_labels)
          and model_record.get("fit_event_ids") == [x["event_id"] for x in dev_labels],
          "model_training_binding_mismatch")
    times = [x.get("recorded_at") for x in dev_labels]
    check(bool(times) and all(number(t) for t in times) and number(model.get("trained_until"))
          and model.get("trained_until") == max(times) and number(model_record.get("created_at"))
          and model["trained_until"] <= model_record["created_at"] < freeze,
          "p2_not_trained_before_scheduling")
    weights, transform = model.get("weights"), model.get("transform", {})
    check(isinstance(weights, list) and len(weights) == 63 and all(number(x) for x in weights),
          "model_weights_invalid")
    check(isinstance(transform, dict) and set(transform) == {"mean", "std", "median"}
          and all(isinstance(a, list) and len(a) == 3 and all(number(x) for x in a)
                  for a in transform.values())
          and all(x > 0 for x in transform.get("std", [])), "model_transform_invalid")
    registration = evidence.get("registration", {})
    if isinstance(registration, dict):
        backed(registration, "registration", "frozen_at")
        check(registration.get("core") == registration_core(plan) and registration.get("frozen_at") == frozen,
              "registration_plan_mismatch")
    else:
        check(False, "registration_missing")

    sessions = index(evidence.get("session_records"), "session_id", "trial_session")
    check(set(sessions) == trial_ids and bool(trial_ids), "trial_session_set_mismatch")
    for s in sessions.values():
        backed(s, "trial_session", "completed_at")
        check(number(s.get("started_at")) and number(s.get("completed_at"))
              and freeze < s["started_at"] < s["completed_at"] <= until, "trial_session_time_invalid")
    trial_units = [s.get("independent_unit") for s in sessions.values()]
    check(all(type(s) is str and s for s in trial_units) and len(set(trial_units)) == len(trial_units),
          "trial_sessions_not_independent")
    check(not (set(trial_units) & set(independence)), "development_trial_independent_unit_overlap")
    check(not (set(trial_units) & set(units)), "training_trial_independent_unit_overlap")
    predictions = index(evidence.get("predictions"), "prediction_id", "prediction")
    snapshots = index(evidence.get("snapshots"), "snapshot_id", "snapshot")
    exposures = index(evidence.get("exposures"), "exposure_id", "exposure")
    feedback = index(evidence.get("feedback"), "event_id", "feedback")
    row_index = index(rows, "exposure_id", "row")
    check(set(row_index) == set(exposures) and bool(exposures), "row_exposure_set_mismatch")
    prediction_refs, snapshot_refs, event_refs = [], [], []
    feedback_by_exposure = {}
    for f in feedback.values():
        backed(f, "feedback", "recorded_at")
        eid = f.get("exposure_id")
        check(eid in exposures and eid not in feedback_by_exposure, "feedback_orphan_or_duplicate")
        feedback_by_exposure[eid] = f
        check(f.get("target") == "scenario_acceptance"
              and (f.get("value") is None or type(f.get("value")) is int and f["value"] in (0, 1))
              and (f.get("interruption") is None or type(f.get("interruption")) is int and f["interruption"] in (0, 1))
              and (f.get("skipped") is None or type(f.get("skipped")) is bool), "feedback_label_invalid")
    session_exposures = {}
    seen_content = set()
    for eid, e in exposures.items():
        backed(e, "exposure", "exposed_at")
        sid, cid, p = e.get("session_id"), e.get("content_id"), e.get("policy")
        check(sid in sessions and type(cid) is str and bool(re.fullmatch(r"sha256:[0-9a-f]{64}", cid)) and p in POLICIES, "exposure_identity_invalid")
        check(e.get("effective_policy") == p, "policy_not_delivered")
        pair = (sid, cid)
        check(pair not in seen_content, "repeat_content_within_session")
        seen_content.add(pair)
        if type(sid) is str:
            session_exposures.setdefault(sid, []).append(e)
        snapshot = snapshots.get(e.get("snapshot_id"), {})
        snapshot_refs.append(e.get("snapshot_id"))
        check(bool(snapshot) and e.get("snapshot_hash") == snapshot.get("sha256")
              and snapshot.get("sha256") == digest(without(snapshot, "sha256")), "snapshot_hash_mismatch")
        prediction = predictions.get(snapshot.get("prediction_id"), {})
        prediction_refs.append(snapshot.get("prediction_id"))
        check(bool(prediction) and snapshot.get("prediction_hash") == digest(prediction), "prediction_hash_mismatch")
        if prediction:
            backed(prediction, "prediction", "predicted_at")
        check(all(prediction.get(k) == e.get(k) for k in ("session_id", "content_id", "policy", "effective_policy")),
              "prediction_exposure_mismatch")
        check(snapshot.get("versions") == versions and prediction.get("versions") == versions, "cross_version_or_request")
        if p == "P2":
            check(prediction.get("model_hash") == plan.get("model_hash"), "prediction_model_mismatch")
        times = [prediction.get("predicted_at"), snapshot.get("created_at"), e.get("exposed_at")]
        s = sessions.get(sid, {})
        check(all(number(t) for t in times) and number(s.get("started_at")) and number(s.get("completed_at"))
              and s["started_at"] <= times[0] <= times[1] <= times[2] <= s["completed_at"] <= until
              and freeze < times[0], "prediction_snapshot_exposure_time_chain")
        row = row_index.get(eid, {})
        f = feedback_by_exposure.get(eid)
        check(all(row.get(k) == e.get(k) for k in ("session_id", "content_id", "policy", "effective_policy", "exposed_at"))
              and all(row.get(k) == versions.get(k) for k in VERSION_KEYS)
              and row.get("snapshot_id") == e.get("snapshot_id")
              and row.get("prediction_id") == prediction.get("prediction_id")
              and row.get("provenance") == kind, "row_chain_or_version_mismatch")
        if f:
            event_refs.append(f["event_id"])
            check(row.get("feedback_id") == f["event_id"] and row.get("accept") == f.get("value")
                  and row.get("interruption") == f.get("interruption") and row.get("skipped") == f.get("skipped"),
                  "row_feedback_mismatch")
            check(number(f.get("recorded_at")) and number(e.get("exposed_at"))
                  and number(s.get("completed_at"))
                  and e["exposed_at"] <= f["recorded_at"] <= s["completed_at"] <= until, "future_feedback_or_time_chain")
        else:
            check(all(row.get(k) is None for k in ("feedback_id", "accept", "interruption", "skipped")),
                  "missing_feedback_invented_label")
        earlier = sorted(fb["event_id"] for fb in feedback.values()
                         if number(fb.get("recorded_at")) and number(prediction.get("predicted_at"))
                         and fb["recorded_at"] < prediction["predicted_at"]
                         and exposures.get(fb.get("exposure_id"), {}).get("session_id") == sid
                         and exposures.get(fb.get("exposure_id"), {}).get("policy") == p)
        check(prediction.get("prior_feedback_ids") == earlier, "prediction_update_chain_mismatch")
        check(prediction.get("state_id") == str(sid)+"/"+str(p), "policy_state_not_isolated")
    check(len(prediction_refs) == len(set(prediction_refs)) and set(prediction_refs) == set(predictions),
          "prediction_orphan_or_reused")
    check(len(snapshot_refs) == len(set(snapshot_refs)) and set(snapshot_refs) == set(snapshots),
          "snapshot_orphan_or_reused")
    check(set(event_refs) == set(feedback), "feedback_unreferenced")
    if valid_ids and valid_n:
        expected_schedule = schedule(n)
        previous_end = -math.inf
        for i, sid in enumerate(session_ids):
            current = session_exposures.get(sid, [])
            check(len(current) == 18 and all(sum(e.get("policy") == p for e in current) == 6 for p in POLICIES),
                  "six_exposures_each_required")
            if all(number(e.get("exposed_at")) for e in current):
                ordered = sorted(current, key=lambda e: e["exposed_at"])
                check(len({e["exposed_at"] for e in ordered}) == len(ordered)
                      and [e.get("policy") for e in ordered] == [p for p in expected_schedule[i]["policy_order"] for _ in range(6)],
                      "actual_policy_order_mismatch")
            s = sessions.get(sid, {})
            if number(s.get("started_at")) and number(s.get("completed_at")):
                check(previous_end < s["started_at"], "trial_sessions_overlap_or_reordered")
                previous_end = s["completed_at"]
    check(used_sources == set(sources), "source_orphan_or_unreferenced")
    return reasons


def pilot_metrics(rows, plan):
    # Validate arbitrary JSON-like inputs without raising on missing/type-invalid evidence.
    malformed = []
    def finite_tree(value, path="input"):
        if isinstance(value, float) and not math.isfinite(value):
            malformed.append("nonfinite_number:"+path)
        elif isinstance(value, dict):
            for k, v in value.items():
                if not isinstance(k, str):
                    malformed.append("invalid_key:"+path)
                    finite_tree(v, path+"."+str(k))
                    continue
                if (k.endswith("_id") or k.endswith("_hash") or k in ("sha256", "policy", "effective_policy", "independent_unit")) and v is not None and type(v) is not str:
                    malformed.append("invalid_string_field:"+path+"."+str(k))
                if k in ("versions", "params", "transform", "evidence", "development", "training", "model", "bundle", "registration") and not isinstance(v, dict):
                    malformed.append("invalid_object_field:"+path+"."+str(k))
                finite_tree(v, path+"."+str(k))
        elif isinstance(value, (list, tuple)):
            for i, v in enumerate(value):
                finite_tree(v, path+"["+str(i)+"]")
        elif value is not None and type(value) not in (str, int, float, bool):
            malformed.append("invalid_type:"+path)
    finite_tree(rows, "rows")
    finite_tree(plan, "plan")
    valid_rows = rows if isinstance(rows, list) else []
    valid_plan = plan if isinstance(plan, dict) else {}
    if not isinstance(rows, list) or not isinstance(plan, dict):
        malformed.append("rows_or_plan_invalid_type")
    # Type-invalid labels are rejected before arithmetic while retaining descriptive missing rates.
    safe_rows = []
    for r in valid_rows:
        if not isinstance(r, dict):
            malformed.append("row_invalid_type")
            continue
        row = dict(r)
        for k in ("accept", "interruption"):
            if row.get(k) is not None and not (type(row[k]) is int and row[k] in (0, 1)):
                malformed.append("row_"+k+"_invalid")
                row[k] = None
        if row.get("skipped") is not None and type(row["skipped"]) is not bool:
            malformed.append("row_skipped_invalid")
        safe_rows.append(row)
    stats = descriptive_metrics(safe_rows)
    reasons = list(dict.fromkeys(malformed))
    if not reasons:
        try:
            reasons = validate_protocol(valid_rows, valid_plan)
        except (TypeError, ValueError, KeyError, AttributeError, OverflowError) as exc:
            # Last-resort malformed schema containment, never used for positive validation.
            reasons = ["malformed_protocol:"+type(exc).__name__]
    gates = numerical_gates(stats, valid_plan.get("sessions"))
    reasons += [name for name, ok in gates.items() if not ok]
    protocol_valid = not any(reason not in gates for reason in reasons)
    passed = not reasons
    synthetic = valid_plan.get("evidence_kind") == "synthetic"
    status = ("SYNTHETIC_TEST_PROTOCOL_SUPPORTED" if synthetic else "PILOT_BENEFIT_SUPPORTED") if passed else "NO_USER_BENEFIT_EVIDENCE"
    return dict(stats, status=status, reasons=reasons, protocol_valid=protocol_valid,
                numerical_gates=gates, mechanism_pass=passed, real_benefit_supported=passed and not synthetic,
                benefit_award_gate="SOURCE_BOUND_PROTOCOL_V2",
                numerical_thresholds_only_would_pass=all(gates.values()),
                plan_precedes_exposures=protocol_valid,
                scope="this user and tested scenarios only; interface is not blinded",
                evidence_limit="Artifact integrity cannot independently authenticate a fabricated human record.")


if __name__ == "__main__":
    print(json.dumps(dict(audio=bpm_metrics([]), sample_plan=freeze_sample_size([]),
                          recommendation=pilot_metrics([], {}), activity="ACCURACY_UNVERIFIED",
                          jev="JEV_NOT_RUN"), indent=2))
