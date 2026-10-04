"""Append-only SQLite provenance store; no rating exists without a prior exposure."""
import json
from pathlib import Path
import re
import sqlite3
import time
from .model import canonical, digest, effective_context, number


def _id(value):
    if not isinstance(value, str) or not value or len(value) > 256:
        raise ValueError("invalid_id")
    return value


def validate_bundle(bundle, cutoff=None):
    cutoff = time.time() if cutoff is None else cutoff
    if not isinstance(bundle, dict) or not {"snapshots", "exposures", "events", "sessions"}.issubset(bundle):
        raise ValueError("training_requires_evidence_bundle")
    def indexed(kind, key):
        items = bundle[kind]
        out = {_id(x[key]): x for x in items}
        if len(out) != len(items):
            raise ValueError("duplicate_" + kind)
        return out
    snaps = indexed("snapshots", "snapshot_id")
    exposures = indexed("exposures", "exposure_id")
    sessions = indexed("sessions", "session_id")
    indexed("events", "event_id")
    for s in snaps.values():
        if s["snapshot_hash"] != digest(s["snapshot"]):
            raise ValueError("snapshot_integrity_failure")
        if not number(s["created_at"]) or s["created_at"] > cutoff:
            raise ValueError("future_snapshot")
        p = s["snapshot"]
        if p["policy"] not in ("P0", "P1", "P2") or not number(p["predicted_at"]) or p["predicted_at"] > s["created_at"]:
            raise ValueError("invalid_snapshot_prediction")
        if not p["tracks"] or len({t["content_id"] for t in p["tracks"]}) != len(p["tracks"]):
            raise ValueError("empty_or_duplicate_snapshot_tracks")
    for x in exposures.values():
        s = snaps.get(x["snapshot_id"])
        if not s or not number(x["exposed_at"]) or not s["created_at"] <= x["exposed_at"] <= cutoff:
            raise ValueError("exposure_without_prior_snapshot")
        if x["content_id"] not in {t["content_id"] for t in s["snapshot"]["tracks"]}:
            raise ValueError("unshown_content")
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", x["content_id"]):
            raise ValueError("invalid_content_hash")
    keys, output = set(), []
    for event in bundle["events"]:
        e = dict(event)
        x = exposures.get(e["exposure_id"])
        if not x:
            raise ValueError("feedback_without_exposure")
        s = snaps[x["snapshot_id"]]
        p = s["snapshot"]
        for k in ("snapshot_id", "content_id", "session_id", "exposed_at"):
            if e[k] != x[k]:
                raise ValueError("feedback_exposure_mismatch:" + k)
        for k in ("policy", "context", "feature_version"):
            if e[k] != p[k]:
                raise ValueError("feedback_snapshot_mismatch:" + k)
        if e["snapshot"] != p:
            raise ValueError("feedback_snapshot_mutated")
        if (not number(e["recorded_at"]) or e["recorded_at"] < e["exposed_at"]
                or e["recorded_at"] >= cutoff):
            raise ValueError("future_label_leakage")
        if e["target"] not in ("song_like", "scenario_acceptance") or e["provenance"] not in ("real_user", "synthetic"):
            raise ValueError("invalid_feedback_target_or_provenance")
        if e["value"] is not None and (type(e["value"]) is not int or e["value"] not in (0, 1)):
            raise ValueError("invalid_feedback_value")
        key = (e["exposure_id"], e["target"])
        if key in keys:
            raise ValueError("duplicate_feedback")
        keys.add(key)
        if e["target"] == "scenario_acceptance":
            effective_context(e["context"], e["exposed_at"], strict=True)
        session = sessions.get(e["session_id"], {})
        e["session_complete"] = (number(session.get("completed_at"))
                                 and e["recorded_at"] <= session["completed_at"] < cutoff
                                 and session.get("provenance") == "real_user")
        output.append(e)
    return sorted(output, key=lambda e: (e["recorded_at"], e["event_id"]))


class EvidenceStore:
    def __init__(self, state_dir):
        self.root = Path(state_dir)
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(self.root / "scenario.sqlite3"))
        self.db.execute("PRAGMA synchronous=FULL")
        for table in ("snapshots", "exposures", "events", "sessions"):
            self.db.execute(f"CREATE TABLE IF NOT EXISTS {table} (id TEXT PRIMARY KEY, body TEXT NOT NULL, hash TEXT NOT NULL)")
            for op in ("UPDATE", "DELETE"):
                self.db.execute(f"CREATE TRIGGER IF NOT EXISTS immutable_{table}_{op} BEFORE {op} ON {table} BEGIN SELECT RAISE(ABORT, 'immutable_evidence'); END")
        self.db.commit()

    def export(self):
        out = {}
        for table in ("snapshots", "exposures", "events", "sessions"):
            out[table] = []
            for body, hash_value in self.db.execute(f"SELECT body,hash FROM {table} ORDER BY id"):
                obj = json.loads(body)
                if digest(obj) != hash_value:
                    raise ValueError("store_integrity_failure")
                out[table].append(obj)
        return out

    def _append(self, table, key, obj, now):
        ident = _id(obj[key])
        payload = json.loads(canonical(obj))
        # BEGIN IMMEDIATE serializes idempotency and uniqueness checks across processes.
        try:
            self.db.execute("BEGIN IMMEDIATE")
            prior = self.db.execute(f"SELECT body FROM {table} WHERE id=?", (ident,)).fetchone()
            if prior:
                if prior[0] != canonical(payload):
                    raise ValueError("conflicting_event_or_evidence_id")
                self.db.rollback()
                return {"saved": True, "duplicate": True}
            bundle = self.export()
            bundle[table].append(payload)
            validate_bundle(bundle, now)
            self.db.execute(f"INSERT INTO {table} VALUES (?,?,?)", (ident, canonical(payload), digest(payload)))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return {"saved": True, "duplicate": False}

    def snapshot(self, snapshot_id, prediction, created_at=None):
        created_at = time.time() if created_at is None else created_at
        p = json.loads(canonical(prediction))
        return self._append("snapshots", "snapshot_id", dict(snapshot_id=snapshot_id, snapshot=p,
                            snapshot_hash=digest(p), created_at=created_at), created_at + 1e-6)

    def expose(self, exposure_id, snapshot_id, content_id, session_id, exposed_at=None):
        exposed_at = time.time() if exposed_at is None else exposed_at
        return self._append("exposures", "exposure_id", dict(exposure_id=exposure_id, snapshot_id=snapshot_id,
                            content_id=content_id, session_id=_id(session_id), exposed_at=exposed_at), exposed_at + 1e-6)

    def record(self, event):
        return self._append("events", "event_id", event, time.time())

    def complete_session(self, session_id, provenance="real_user", completed_at=None):
        completed_at = time.time() if completed_at is None else completed_at
        return self._append("sessions", "session_id", dict(session_id=session_id, completed_at=completed_at,
                            provenance=provenance), completed_at + 1e-6)

    def preferences(self, policy):
        tracks = {}
        for e in validate_bundle(self.export()):
            if e["policy"] == policy and e["target"] == "song_like" and e["value"] is not None and e["provenance"] == "real_user":
                tracks[e["content_id"]] = tracks.get(e["content_id"], 0) + (1 if e["value"] else -1)
        return {"tracks": tracks}

    def close(self):
        self.db.close()
