import sqlite3
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from context_player.feedback import FeedbackStore


def recommendation():
    return {"tracks": [{"id": "t01", "sha256": "a" * 64, "content_id": "sha256:" + "a" * 64}],
            "context": {"activity": "walking", "source_kind": "test_fixture"}, "algorithm_version": "test"}


class FeedbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = FeedbackStore(self.temp.name)
        self.snapshot = self.store.create_snapshot(recommendation())

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_durable_idempotence_after_restart(self):
        args = ("event-1", self.snapshot["snapshot_id"], "t01", "like")
        self.assertTrue(self.store.record(*args)["learned"])
        self.store.close()
        self.store = FeedbackStore(self.temp.name)
        self.assertTrue(self.store.record(*args)["duplicate"])
        self.assertEqual(self.store.preferences()["event_count"], 1)
        self.assertEqual(self.store.preferences()["tracks"]["sha256:" + "a" * 64], 1)

    def test_conflicts_and_new_event_cannot_repeat_learning(self):
        sid = self.snapshot["snapshot_id"]
        self.store.record("event-1", sid, "t01", "like")
        with self.assertRaisesRegex(ValueError, "conflicting_event"):
            self.store.record("event-1", sid, "t01", "dislike")
        with self.assertRaisesRegex(ValueError, "already_rated"):
            self.store.record("event-2", sid, "t01", "like")
        self.assertEqual(self.store.preferences()["event_count"], 1)

    def test_snapshot_is_copy_and_db_immutable(self):
        self.snapshot["tracks"][0]["id"] = "malicious"
        self.assertEqual(self.store.get_snapshot(self.snapshot["snapshot_id"])["tracks"][0]["id"], "t01")
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.db.execute("UPDATE snapshots SET body='{}'")
        self.store.db.rollback()

    def test_aliases_cannot_repeat_same_audio_in_snapshot(self):
        value = recommendation()
        value["tracks"].append(dict(value["tracks"][0], id="other-id"))
        with self.assertRaisesRegex(ValueError, "duplicate_snapshot_audio"):
            self.store.create_snapshot(value)

    def test_legacy_alias_snapshot_cannot_repeat_audio_learning(self):
        value = recommendation()
        value["tracks"].append(dict(value["tracks"][0], id="other-id"))
        value.update(snapshot_id="legacy-snapshot", condition="C")
        body = json.dumps(value)
        with self.store.db:
            self.store.db.execute("INSERT INTO snapshots VALUES (?,?,?,?,?)", (
                "legacy-snapshot", "C", body, hashlib.sha256(body.encode()).hexdigest(), 1))
        self.store.record("first", "legacy-snapshot", "t01", "like")
        with self.assertRaisesRegex(ValueError, "already_rated"):
            self.store.record("second", "legacy-snapshot", "other-id", "like")
        self.assertEqual(self.store.preferences()["event_count"], 1)

    def test_wrong_track_and_skip_rejected(self):
        sid = self.snapshot["snapshot_id"]
        with self.assertRaisesRegex(ValueError, "track_not_in"):
            self.store.record("x", sid, "t99", "like")
        with self.assertRaisesRegex(ValueError, "feedback_must"):
            self.store.record("x", sid, "t01", "skip")
        self.assertEqual(self.store.preferences()["event_count"], 0)

    def test_defer_and_conditions_ab_never_learn(self):
        self.store.record("defer", self.snapshot["snapshot_id"], "t01", "defer")
        for condition in "AB":
            snapshot = self.store.create_snapshot(recommendation(), condition)
            result = self.store.record(condition, snapshot["snapshot_id"], "t01", "like")
            self.assertFalse(result["learned"])
            self.assertEqual(self.store.preferences(condition)["tracks"], {})
        self.assertEqual(self.store.preferences()["event_count"], 0)

    def test_correction_separate_idempotent_and_no_learning(self):
        args = ("correction", {"activity": "stationary"}, "walking")
        self.assertFalse(self.store.record_activity_correction(*args)["learned"])
        self.assertTrue(self.store.record_activity_correction(*args)["duplicate"])
        with self.assertRaisesRegex(ValueError, "conflicts_with_correction"):
            self.store.record("correction", self.snapshot["snapshot_id"], "t01", "like")
        self.assertEqual(self.store.preferences()["event_count"], 0)

    def test_save_failure_never_returns_success(self):
        self.store.db.execute("PRAGMA query_only=ON")
        with self.assertRaises(sqlite3.OperationalError):
            self.store.record("failure", self.snapshot["snapshot_id"], "t01", "like")
        self.assertEqual(self.store.preferences()["event_count"], 0)
        self.store.db.execute("PRAGMA query_only=OFF")
        self.assertTrue(self.store.record("failure", self.snapshot["snapshot_id"], "t01", "like")["saved"])

    def test_corrupt_database_not_silently_replaced(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.sqlite3"
            path.write_bytes(b"CORRUPT USER BYTES")
            with self.assertRaises(sqlite3.DatabaseError):
                FeedbackStore(directory)
            self.assertEqual(path.read_bytes(), b"CORRUPT USER BYTES")


if __name__ == "__main__":
    unittest.main()
