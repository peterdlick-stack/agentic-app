import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import wave

from context_player.recommend import load_catalog, recommend, verify_track


def make_catalog(root):
    library = Path(root) / "library"
    library.mkdir()
    rows = []
    for i, (bpm, vocal) in enumerate(((70, False), (105, True), (135, False), (None, None))):
        path = library / f"t{i}.wav"
        with wave.open(str(path), "wb") as audio:
            audio.setparams((1, 2, 8000, 0, "NONE", ""))
            audio.writeframes(bytes([i + 1, 0]) * 800)
        rows.append({"id": f"t{i}", "title": "running secret reading", "path": f"library/t{i}.wav",
                     "bpm": bpm, "vocal": vocal, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                     "source": "test fixture annotation"})
    (library / "catalog.json").write_text(json.dumps(rows))
    return load_catalog(root)


def manual(activity):
    return {"activity": activity, "source_kind": "manual", "freshness": "fresh", "allowed_for_current": True}


class RecommendationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.catalog = make_catalog(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_real_library(self):
        root = (Path(__file__).resolve().parents[2]/"test-fixtures")
        catalog = load_catalog(root)
        self.assertEqual(len(catalog), 24)
        self.assertEqual(len({t["content_id"] for t in catalog}), 24)
        self.assertEqual(sum(t["duration"] for t in catalog), 860)
        self.assertTrue(all(t["features"]["bpm"]["kind"] == "generator_parameter" for t in catalog))
        self.assertTrue(all("energy" not in t["features"] and "vocal_density" not in t["features"] for t in catalog))

    def test_context_and_explicit_constraints(self):
        result = recommend(self.catalog, manual("running"), {}, "不要人声", 4)
        self.assertEqual(result["tracks"][0]["id"], "t2")
        self.assertEqual({t["id"] for t in result["tracks"]}, {"t0", "t2"})
        result = recommend(self.catalog, manual("reading"), {}, "别太催眠", 4)
        self.assertTrue(all(t["bpm"] >= 95 for t in result["tracks"]))

    def test_missing_is_fallback_not_zero_tempo(self):
        result = recommend(self.catalog, manual("reading"), {}, limit=4)
        self.assertEqual(result["tracks"][-1]["id"], "t3")
        self.assertIsNone(result["tracks"][-1]["bpm"])
        self.assertFalse(result["tracks"][-1]["context_evidence"])

    def test_unknown_stale_and_stationary_use_preference(self):
        pref = {"tracks": {self.catalog[2]["content_id"]: 1}}
        for ctx in ({}, manual("stationary"), dict(manual("reading"), freshness="expired"),
                    dict(manual("reading"), allowed_for_current=False)):
            self.assertEqual(recommend(self.catalog, ctx, pref)["tracks"][0]["id"], "t2")

    def test_history_only_in_experiment(self):
        ctx = {"activity": "reading", "historical": True, "freshness": "historical"}
        self.assertEqual(recommend(self.catalog, ctx, {})["effective_activity"], "unknown")
        ctx["experiment_mode"] = True
        self.assertEqual(recommend(self.catalog, ctx, {})["tracks"][0]["id"], "t0")

    def test_history_cannot_spoof_fresh_current_flags(self):
        for flags in ({"historical": True}, {"source_kind": "historical_replay"}):
            ctx = dict(manual("reading"), **flags)
            self.assertEqual(recommend(self.catalog, ctx, {})["effective_activity"], "unknown")

    def test_title_and_order_do_not_drive_ranking(self):
        before = recommend(self.catalog, manual("reading"), {})
        renamed = copy.deepcopy(list(reversed(self.catalog)))
        for track in renamed:
            track["title"] = "totally unrelated"
        self.assertEqual([t["id"] for t in before["tracks"]], [t["id"] for t in recommend(renamed, manual("reading"), {})["tracks"]])

    def test_audio_changed_after_load_excluded(self):
        (Path(self.temp.name) / "library/t0.wav").write_bytes(b"bad")
        result = recommend(self.catalog, manual("reading"), {})
        self.assertNotIn("t0", [t["id"] for t in result["tracks"]])
        self.assertEqual(result["rejected"][0]["reason"], "audio_hash_mismatch")

    def test_truncated_wav_even_matching_hash_rejected(self):
        track = self.catalog[0]
        path = Path(self.temp.name) / track["path"]
        path.write_bytes(path.read_bytes()[:-4])
        track["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, "truncated"):
            verify_track(track)

    def test_traversal_rejected(self):
        track = dict(self.catalog[0], path="../../etc/passwd")
        with self.assertRaises(ValueError):
            verify_track(track)

    def test_request_fail_closed_and_excludes_previous(self):
        with self.assertRaisesRegex(ValueError, "unsupported_request"):
            recommend(self.catalog, {}, {}, "不要电子音乐")
        ctx = dict(manual("running"), previous_ids=["t2"])
        self.assertNotIn("t2", [t["id"] for t in recommend(self.catalog, ctx, {}, "换一批")["tracks"]])
        with self.assertRaises(ValueError):
            recommend(self.catalog, {}, {}, "不要人声，需要人声")


if __name__ == "__main__":
    unittest.main()
