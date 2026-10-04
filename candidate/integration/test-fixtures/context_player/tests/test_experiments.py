import copy
from pathlib import Path
import tempfile
import unittest

from context_player.experiments import ExperimentTrial
from context_player.feedback import FeedbackStore
from context_player.recommend import load_catalog


class ExperimentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.catalog = load_catalog((Path(__file__).resolve().parents[2]/"test-fixtures"))
        self.trial = ExperimentTrial(self.temp.name, self.catalog)
        self.context = {"activity": "reading", "historical": True, "freshness": "historical",
                        "source_kind": "historical_replay", "observed_wall_ms": 1, "allowed_for_current": False}

    def tearDown(self):
        self.trial.close()
        self.temp.cleanup()

    def test_conditions_fixed_order_and_no_shared_learning(self):
        result = self.trial.create_round("r1", self.context)
        self.assertEqual(sorted(result["order"]), list("ABC"))
        for condition in "ABC":
            snapshot = result["snapshots"][condition]
            self.trial.stores[condition].record(condition, snapshot["snapshot_id"], snapshot["tracks"][0]["id"], "like")
        self.assertEqual(self.trial.stores["A"].preferences("A")["event_count"], 0)
        self.assertEqual(self.trial.stores["B"].preferences("B")["event_count"], 0)
        self.assertEqual(self.trial.stores["C"].preferences()["event_count"], 1)
        self.assertEqual(result["snapshots"]["A"]["effective_activity"], "unknown")
        self.assertEqual(result["snapshots"]["B"]["effective_activity"], "reading")
        self.assertEqual(result["snapshots"]["C"]["context"]["observed_wall_ms"], 1)
        self.assertNotIn("experiment_mode", self.context)

    def test_restart_frozen_inputs_and_round(self):
        first = self.trial.create_round("r1", self.context)
        self.trial.close()
        self.trial = ExperimentTrial(self.temp.name, self.catalog)
        self.assertEqual(first, self.trial.create_round("r1", self.context))
        with self.assertRaisesRegex(ValueError, "frozen_round"):
            self.trial.create_round("r1", dict(self.context, activity="running"))
        changed = copy.deepcopy(self.catalog)
        changed[0]["features"]["bpm"]["value"] = 90
        with self.assertRaisesRegex(ValueError, "frozen_trial"):
            ExperimentTrial(self.temp.name, changed)

    def test_missing_feedback_and_skipping_not_dislike(self):
        result = self.trial.create_round("r1", self.context)
        snapshot = result["snapshots"]["C"]
        args = ("observation", "C", snapshot["snapshot_id"], snapshot["tracks"][0]["id"])
        self.trial.record_observation(*args, skipped=True)
        self.assertTrue(self.trial.record_observation(*args, skipped=True)["duplicate"])
        with self.assertRaisesRegex(ValueError, "already_recorded"):
            self.trial.record_observation("new-event", *args[1:], skipped=True)
        report = self.trial.report()
        self.assertEqual(report["conditions"]["C"]["missing_feedback"], 4)
        self.assertEqual(report["conditions"]["C"]["acceptance_observations"], 0)
        self.assertEqual(report["conditions"]["C"]["dislike"], 0)
        self.assertEqual(report["conditions"]["C"]["disturbance_values"], [])
        self.assertEqual(report["benefit_status"], "NO_USER_BENEFIT_EVIDENCE")

    def test_new_trial_refuses_existing_preferences(self):
        with tempfile.TemporaryDirectory() as directory:
            store = FeedbackStore(Path(directory) / "C")
            snapshot = store.create_snapshot({"tracks": [self.catalog[0]]})
            store.record("prior", snapshot["snapshot_id"], self.catalog[0]["id"], "like")
            store.close()
            with self.assertRaisesRegex(ValueError, "empty_condition"):
                ExperimentTrial(directory, self.catalog)
            store = FeedbackStore(Path(directory) / "C")
            self.assertEqual(store.preferences()["event_count"], 1)
            store.close()


if __name__ == "__main__":
    unittest.main()
