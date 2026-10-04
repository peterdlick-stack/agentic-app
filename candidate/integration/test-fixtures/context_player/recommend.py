"""Deterministic recommendations over verified audio, without inferred features."""
import hashlib
import json
import math
from pathlib import Path
import re
import wave

ALGORITHM_VERSION = "real-catalog-v1"
TARGET_BPM = {"walking": 104, "running": 136, "cycling": 124,
              "reading": 70, "workout": 136, "relax": 68}


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def verify_track(track, root=None, full=True):
    """Revalidate bytes immediately before use; reject traversal and truncated PCM."""
    base = Path(root or track["catalog_root"]).resolve()
    path = (base / track["path"]).resolve()
    if not path.is_relative_to(base / "library") or not path.is_file():
        raise ValueError("audio_path_outside_library_or_missing")
    if full:
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != track["sha256"]:
            raise ValueError("audio_hash_mismatch")
    try:
        with wave.open(str(path), "rb") as audio:
            channels, width, rate, frames, compression, _ = audio.getparams()
            if compression != "NONE" or channels not in (1, 2) or width not in (1, 2, 3, 4) or rate <= 0 or frames <= 0:
                raise ValueError("unsupported_or_empty_wav")
            if full and len(audio.readframes(frames)) != frames * channels * width:
                raise ValueError("truncated_wav")
            return {"duration": frames / rate, "sample_rate": rate,
                    "channels": channels, "sample_width": width, "frames": frames}
    except (wave.Error, EOFError) as exc:
        raise ValueError("invalid_wav") from exc


def load_catalog(root, verify_all=True):
    root = Path(root).resolve()
    rows = json.loads((root / "library/catalog.json").read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError("catalog_must_be_array")
    tracks, ids, hashes = [], set(), set()
    for row in rows:
        ident, digest = row.get("id"), row.get("sha256")
        if not isinstance(ident, str) or not ident or ident in ids:
            raise ValueError("invalid_or_duplicate_track_id")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest) or digest in hashes:
            raise ValueError("invalid_or_duplicate_audio_hash")
        track = dict(row, catalog_root=str(root), content_id="sha256:" + digest)
        if not verify_all and isinstance(row.get("pcm_metadata"), dict):
            metadata = row["pcm_metadata"]
            if not _number(metadata.get("duration")) or metadata["duration"] <= 0:
                raise ValueError("invalid_imported_duration")
            track.update(metadata)
        else:
            track.update(verify_track(track, root, full=verify_all))
        source = row.get("source") or "catalog metadata; origin unspecified"
        provenance_kind = "generator_parameter" if "scripts/make_library.py" in source else "catalog_annotation_unverified"
        features = {}
        if _number(row.get("bpm")) and 20 <= row["bpm"] <= 400:
            features["bpm"] = {"value": row["bpm"], "kind": provenance_kind, "source": source}
        if type(row.get("vocal")) is bool:
            features["vocal"] = {"value": row["vocal"], "kind": provenance_kind, "source": source,
                                 "semantics": "presence flag, not vocal density"}
        track["features"] = features
        track["bpm"] = features.get("bpm", {}).get("value")
        track["vocal"] = features.get("vocal", {}).get("value")
        track["verification"] = "sha256_and_complete_pcm_wav" if verify_all else "metadata_pending_sha256"
        tracks.append(track)
        ids.add(ident)
        hashes.add(digest)
    return tracks


def parse_request(request):
    """Small visible request grammar; unsupported prose is reported, never guessed."""
    if not isinstance(request, str):
        raise ValueError("request_must_be_text")
    text = request.lower().strip()
    no_vocal = any(x in text for x in ("不要人声", "无人声", "少点人声", "纯音乐", "no vocals", "instrumental"))
    yes_vocal = any(x in text for x in ("要有人声", "需要人声", "with vocals"))
    if no_vocal and yes_vocal:
        raise ValueError("conflicting_vocal_constraints")
    constraints = {"vocal_policy": "none" if no_vocal else "required" if yes_vocal else "any",
                   "min_bpm": 95 if "别太催眠" in text else None, "max_bpm": None,
                   "exclude_previous": any(x in text for x in ("换一批", "换一组", "another batch"))}
    bounds = re.search(r"(?:bpm\s*)?(\d+(?:\.\d+)?)\s*[-–~至到]\s*(\d+(?:\.\d+)?)\s*bpm", text)
    if bounds:
        constraints["min_bpm"], constraints["max_bpm"] = map(float, bounds.groups())
        if constraints["min_bpm"] > constraints["max_bpm"]:
            raise ValueError("conflicting_bpm_constraints")
    remainder = text
    if bounds:
        remainder = remainder.replace(bounds.group(), "")
    for phrase in ("不要人声", "无人声", "少点人声", "纯音乐", "no vocals", "instrumental", "要有人声", "需要人声", "with vocals", "别太催眠", "换一批", "换一组", "another batch", "我要听歌了", "帮我选歌", "推荐音乐", "推荐", "请", "谢谢"):
        remainder = remainder.replace(phrase, "")
    if re.sub(r"[\s，,。.!！;；、]", "", remainder):
        raise ValueError("unsupported_request_use_explicit_forms: " + remainder)
    constraints["parser"] = "explicit-grammar-v1"
    constraints["supported_forms"] = "不要人声/少点人声/要有人声/别太催眠/换一批/90-110 bpm"
    constraints["unparsed_text"] = ""
    return constraints


def recommend(catalog, context, preferences, request="", limit=4):
    if type(limit) is not int or not 1 <= limit <= 24:
        raise ValueError("limit_must_be_1_to_24")
    context = json.loads(json.dumps(context or {}, allow_nan=False))
    constraints = parse_request(request)
    activity = context.get("activity", "unknown")
    is_history = context.get("historical") is True or context.get("source_kind") == "historical_replay"
    admissible = not is_history and context.get("allowed_for_current") is True and context.get("freshness") == "fresh"
    historical = is_history and context.get("experiment_mode") is True
    if not admissible and not historical:
        activity = "unknown"
    # Stationary has no scenario prototype; no lifestyle inference.
    target = TARGET_BPM.get(activity)
    previous = context.get("previous_ids", []) if constraints["exclude_previous"] else []
    learned = (preferences or {}).get("tracks", {})
    candidates, rejected = [], []
    for source in catalog:
        track = dict(source)
        try:
            if track.get("verification") != "metadata_pending_sha256":
                verify_track(track)
        except (OSError, ValueError, KeyError) as exc:
            rejected.append({"id": track.get("id"), "reason": str(exc)})
            continue
        if track["id"] in previous:
            continue
        bpm = track.get("features", {}).get("bpm", {}).get("value")
        vocal = track.get("features", {}).get("vocal", {}).get("value")
        if constraints["vocal_policy"] == "none" and vocal is not False:
            continue
        if constraints["vocal_policy"] == "required" and vocal is not True:
            continue
        low, high = constraints["min_bpm"], constraints["max_bpm"]
        if (low is not None or high is not None) and not _number(bpm):
            continue
        if low is not None and bpm < low or high is not None and bpm > high:
            continue
        pref = learned.get(track["content_id"], 0)
        if not _number(pref):
            raise ValueError("invalid_preference_value")
        pref_score = 0.35 * pref / (abs(pref) + 2)
        evidence = target is not None and _number(bpm)
        # Missing tempo is not replaced by 0. Unknown candidates form a disclosed fallback tier.
        score = (1 - min(abs(bpm - target) / 100, 1) if evidence else 0) + pref_score
        reason = (f"{activity}: target {target} BPM, catalog {bpm} BPM (heuristic, metadata)"
                  if evidence else "ordinary preference; no supported context/tempo evidence")
        if pref:
            reason += f"; explicit feedback balance {pref}"
        track.update(score=round(score, 8), reason=reason,
                     context_evidence=bool(evidence), missing_features=[k for k in ("bpm", "vocal") if k not in track.get("features", {})])
        candidates.append(track)
    candidates.sort(key=lambda t: (-int(t["context_evidence"]), -t["score"], t["content_id"]))
    selected = []
    for track in candidates:
        if len(selected) >= limit:
            break
        if track.get("verification") == "metadata_pending_sha256":
            try:
                verify_track(track)
                track["verification"] = "sha256_and_complete_pcm_wav"
            except (OSError, ValueError, KeyError) as exc:
                rejected.append({"id": track.get("id"), "reason": str(exc)})
                continue
        selected.append(track)
    return {"tracks": selected, "reason": "deterministic metadata ranking; missing context uses local preferences",
            "context": context, "effective_activity": activity, "request": request, "constraints": constraints,
            "algorithm_version": ALGORITHM_VERSION, "rejected": rejected,
            "missing_policy": "exclude unknown required features; unsupported context uses preferences; missing context features form fallback tier"}
