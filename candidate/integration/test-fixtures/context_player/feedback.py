"""Isolated SQLite event store; immutable snapshots and exactly-once learning."""
import hashlib
import json
from pathlib import Path
import sqlite3
import re
import time
import uuid


def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _id(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 256:
        raise ValueError("invalid_identifier")
    return value


class FeedbackStore:
    def __init__(self, state_dir):
        self.state_dir = Path(state_dir).resolve()
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.state_dir / "events.sqlite3"
        self.db = sqlite3.connect(str(self.path), timeout=5)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS snapshots (
                snapshot_id TEXT PRIMARY KEY, condition TEXT NOT NULL,
                body TEXT NOT NULL, digest TEXT NOT NULL, created_ms INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY, snapshot_id TEXT NOT NULL REFERENCES snapshots(snapshot_id),
                track_id TEXT NOT NULL, content_id TEXT NOT NULL, value TEXT NOT NULL,
                created_ms INTEGER NOT NULL, UNIQUE(snapshot_id, track_id));
            CREATE TABLE IF NOT EXISTS corrections (
                event_id TEXT PRIMARY KEY, body TEXT NOT NULL, created_ms INTEGER NOT NULL);
            CREATE TRIGGER IF NOT EXISTS immutable_snapshot_update BEFORE UPDATE ON snapshots
                BEGIN SELECT RAISE(ABORT, 'immutable_snapshot'); END;
            CREATE TRIGGER IF NOT EXISTS immutable_snapshot_delete BEFORE DELETE ON snapshots
                BEGIN SELECT RAISE(ABORT, 'immutable_snapshot'); END;
            CREATE TRIGGER IF NOT EXISTS immutable_event_update BEFORE UPDATE ON events
                BEGIN SELECT RAISE(ABORT, 'immutable_event'); END;
            CREATE TRIGGER IF NOT EXISTS immutable_event_delete BEFORE DELETE ON events
                BEGIN SELECT RAISE(ABORT, 'immutable_event'); END;
        """)

    def create_snapshot(self, recommendation, condition="C"):
        if condition not in ("A", "B", "C"):
            raise ValueError("invalid_condition")
        payload = json.loads(_json(recommendation))
        tracks = payload.get("tracks")
        if not isinstance(tracks, list) or not tracks:
            raise ValueError("snapshot_requires_tracks")
        ids, content_ids = set(), set()
        for track in tracks:
            _id(track.get("id"))
            content_id = _id(track.get("content_id"))
            if content_id != "sha256:" + track.get("sha256", "") or not re.fullmatch(r"sha256:[0-9a-f]{64}", content_id):
                raise ValueError("snapshot_requires_content_hash")
            if track["id"] in ids:
                raise ValueError("duplicate_snapshot_track")
            if content_id in content_ids:
                raise ValueError("duplicate_snapshot_audio_identity")
            ids.add(track["id"])
            content_ids.add(content_id)
        snapshot_id = str(uuid.uuid4())
        payload.update(snapshot_id=snapshot_id, condition=condition)
        body = _json(payload)
        with self.db:
            self.db.execute("INSERT INTO snapshots VALUES (?,?,?,?,?)", (
                snapshot_id, condition, body, hashlib.sha256(body.encode()).hexdigest(), time.time_ns() // 1000000))
        return self.get_snapshot(snapshot_id)

    def get_snapshot(self, snapshot_id):
        row = self.db.execute("SELECT * FROM snapshots WHERE snapshot_id=?", (_id(snapshot_id),)).fetchone()
        if row is None:
            raise ValueError("unknown_snapshot")
        if hashlib.sha256(row["body"].encode()).hexdigest() != row["digest"]:
            raise ValueError("snapshot_integrity_failure")
        return json.loads(row["body"])

    def record(self, event_id, snapshot_id, track_id, value):
        _id(event_id)
        _id(track_id)
        if value not in ("like", "dislike", "defer"):
            raise ValueError("feedback_must_be_like_dislike_or_defer")
        snapshot = self.get_snapshot(snapshot_id)
        track = next((t for t in snapshot["tracks"] if t["id"] == track_id), None)
        if track is None:
            raise ValueError("track_not_in_snapshot")
        content_id = track["content_id"]
        duplicate = False
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            if self.db.execute("SELECT 1 FROM corrections WHERE event_id=?", (event_id,)).fetchone():
                raise ValueError("event_id_conflicts_with_correction")
            existing = self.db.execute("SELECT * FROM events WHERE event_id=?", (event_id,)).fetchone()
            if existing:
                if tuple(existing[k] for k in ("snapshot_id", "track_id", "content_id", "value")) != (snapshot_id, track_id, content_id, value):
                    raise ValueError("conflicting_event_id")
                duplicate = True
            else:
                if self.db.execute("SELECT 1 FROM events WHERE snapshot_id=? AND (track_id=? OR content_id=?)", (snapshot_id, track_id, content_id)).fetchone():
                    raise ValueError("snapshot_track_already_rated")
                self.db.execute("INSERT INTO events VALUES (?,?,?,?,?,?)", (
                    event_id, snapshot_id, track_id, content_id, value, time.time_ns() // 1000000))
        return {"saved": True, "duplicate": duplicate, "learned": not duplicate and value != "defer" and snapshot["condition"] == "C",
                "event_id": event_id, "snapshot_id": snapshot_id, "track_id": track_id, "value": value}

    def preferences(self, condition="C"):
        if condition not in ("A", "B", "C"):
            raise ValueError("invalid_condition")
        if condition != "C":
            return {"tracks": {}, "event_count": 0, "condition": condition}
        rows = self.db.execute("""SELECT e.content_id,e.value FROM events e
            JOIN snapshots s ON s.snapshot_id=e.snapshot_id WHERE s.condition='C'
            ORDER BY e.event_id""").fetchall()
        tracks, count = {}, 0
        for row in rows:
            if row["value"] != "defer":
                tracks[row["content_id"]] = tracks.get(row["content_id"], 0) + (1 if row["value"] == "like" else -1)
                count += 1
        return {"tracks": tracks, "event_count": count, "condition": condition}

    def record_activity_correction(self, event_id, observed_context, corrected_activity):
        _id(event_id)
        if corrected_activity not in ("unknown", "stationary", "walking", "running", "cycling", "vehicle", "reading", "workout", "relax"):
            raise ValueError("invalid_corrected_activity")
        body = _json({"observed_context": observed_context, "corrected_activity": corrected_activity})
        duplicate = False
        with self.db:
            self.db.execute("BEGIN IMMEDIATE")
            if self.db.execute("SELECT 1 FROM events WHERE event_id=?", (event_id,)).fetchone():
                raise ValueError("event_id_conflicts_with_song_feedback")
            row = self.db.execute("SELECT body FROM corrections WHERE event_id=?", (event_id,)).fetchone()
            if row:
                if row["body"] != body:
                    raise ValueError("conflicting_correction_event_id")
                duplicate = True
            else:
                self.db.execute("INSERT INTO corrections VALUES (?,?,?)", (event_id, body, time.time_ns() // 1000000))
        return {"saved": True, "duplicate": duplicate, "event_id": event_id, "learned": False}

    def list_events(self):
        return [dict(row) for row in self.db.execute("SELECT * FROM events ORDER BY created_ms,event_id")]

    def list_corrections(self):
        return [dict(row) for row in self.db.execute("SELECT * FROM corrections ORDER BY created_ms,event_id")]

    def close(self):
        self.db.close()
