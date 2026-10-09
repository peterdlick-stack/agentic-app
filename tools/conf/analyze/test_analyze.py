"""Synthetic tests: no host, model, network, or real user data required."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import analyze


ACTIVITIES = ("walk", "commute", "study", "work", "relax", "workout", "sleep")


def act(eid, y="walk", sim=False, dup=False, tier="mid", eh=False, q=None):
    q = q or [[key, value] for key, value in zip(ACTIVITIES, (.7, .1, .06, .05, .04, .03, .02))]
    prior = [[key, value] for key, value in zip(ACTIVITIES, (.4, .2, .1, .1, .1, .05, .05))]
    return {"id": eid, "at": 1791504000 + eid, "sim": sim, "dv": 1, "e": "act", "pv": "act-v1",
            "b": "synthetic-weekday-am-walk", "lvl": "full", "n": 0, "q": q, "pr": prior,
            "rule": "walk", "maj": "study", "tier": tier, "eh": eh, "low": "", "how": "tap" if y else "skip",
            "y": y, "dup": dup, "hit": q[0][0] == y if y else None,
            "rhit": y == "walk" if y else None, "mhit": y == "study" if y else None,
            "br": analyze.full_brier(q, y) if y else None, "bp": analyze.full_brier(prior, y) if y else None}


def event(eid, kind, **values):
    return {"id": eid, "at": 1791504000 + eid, "sim": False, "dv": 1, "e": kind, **values}


def rec(eid, result="ai", att=1, e1=None, e2=None, picks=None, sim=False):
    return event(eid, "rec", pv="rec-v2", a=0, act="walk", asrc="tap", hard=[], ne=45, nc=45, att=att,
                 e1=e1 or [], e2=e2 or [], net="", res=result, ms1=1000, ms2=500 if att == 2 else None,
                 mact="unknown", p=picks if picks is not None else [["song|artist", "H", 1]], sim=sim)


def dstats(events):
    groups, _, _, _ = analyze.replay(events)
    return {"v": 1, "seq": max((ev["id"] for ev in events), default=0) + 1,
            "shard": len(events) // 50, "shard_n": len(events) % 50, **groups}


def write(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


class WilsonTests(unittest.TestCase):
    def test_report_q3_all_seven_rows(self):
        examples = [(7, 10, 39.7, 89.2), (14, 20, 48.1, 85.5), (21, 30, 52.1, 83.3),
                    (35, 50, 56.2, 80.9), (70, 100, 60.4, 78.1), (140, 200, 63.3, 75.9), (10, 10, 72.2, 100)]
        for hits, count, low, high in examples:
            with self.subTest(hits=hits, count=count):
                result = analyze.wilson(hits, count)
                self.assertAlmostEqual(result[0] * 100, low, delta=.051)
                self.assertAlmostEqual(result[1] * 100, high, delta=.051)

    def test_zero_denominator_is_unknown(self):
        self.assertIsNone(analyze.wilson(0, 0))
        self.assertIsNone(analyze.ratio(0, 0)["value"])

    def test_high_tier_checkpoints(self):
        self.assertLess(analyze.wilson(28, 30)[0], .80)
        self.assertGreater(analyze.wilson(29, 30)[0], .80)


class ActivityTests(unittest.TestCase):
    def test_undo_duplicates_skip_and_sim_have_distinct_counts(self):
        events = [act(1), act(2, dup=True), act(3, y="", tier="low"), act(4, y="study", sim=True),
                  event(5, "act_undo", a=1), act(6, eh=True)]
        groups, active, _, warnings = analyze.replay(events)
        real = groups["real"]["act"]
        self.assertEqual({key: real[key] for key in ("n", "lab", "hit", "dup", "skip", "undo", "eh_lab", "eh_hit")},
                         {"n": 2, "lab": 1, "hit": 1, "dup": 1, "skip": 1, "undo": 1, "eh_lab": 1, "eh_hit": 1})
        self.assertEqual(groups["sim"]["act"]["lab"], 1)
        self.assertEqual(warnings, [])
        metrics = analyze.describe(events, active, groups)
        self.assertEqual(metrics["label_n"], 1)
        self.assertEqual(metrics["accuracy"]["q"]["value"], 1)
        self.assertEqual(metrics["tiers"]["low"]["coverage"]["value"], .5)
        self.assertIsNone(metrics["tiers"]["low"]["error_rate"]["value"])
        self.assertEqual(analyze.describe(events, active, groups, True)["label_n"], 2)

    def test_undo_after_sim_toggle_reverses_target_group(self):
        events = [act(1, sim=True), event(2, "act_undo", a=1)]
        groups, _, _, warnings = analyze.replay(events)
        self.assertEqual(groups["sim"]["act"]["n"], 0)
        self.assertEqual(groups["sim"]["act"]["undo"], 1)
        self.assertEqual(groups["real"]["act"]["undo"], 0)
        self.assertEqual(warnings, [])

    def test_duplicate_undo_does_not_subtract_twice(self):
        events = [act(1), event(2, "act_undo", a=1), event(3, "act_undo", a=1)]
        groups, _, _, warnings = analyze.replay(events)
        self.assertEqual(groups["real"]["act"]["lab"], 0)
        self.assertEqual(groups["real"]["act"]["undo"], 1)
        self.assertEqual(len(warnings), 1)

    def test_missing_undo_target_is_not_silently_accepted(self):
        groups, _, _, warnings = analyze.replay([event(2, "act_undo", a=1)])
        self.assertIn("missing earlier act", warnings[0])
        self.assertEqual(groups["real"]["act"]["lab"], 0)

    def test_brier_is_multiclass_sum_not_divided_by_seven(self):
        row = act(1)
        # (.7-1)^2 + .1^2 + .06^2 + .05^2 + .04^2 + .03^2 + .02^2
        self.assertAlmostEqual(row["br"], .109)
        # (.4-1)^2 + .2^2 + .1^2*3 + .05^2*2
        self.assertAlmostEqual(row["bp"], .435)

    def test_truncated_vector_never_fabricates_missing_classes(self):
        row = act(1)
        row["q"] = row["q"][:3]
        row["pr"] = row["pr"][:3]
        analyze.validate_event(row, "test")
        groups, active, _, _ = analyze.replay([row])
        metrics = analyze.describe([row], active, groups)
        self.assertIsNone(metrics["brier"]["q"]["mean_from_full_vectors"])
        self.assertEqual(metrics["brier"]["q"]["truncated_or_missing_label_n"], 1)
        self.assertAlmostEqual(metrics["brier"]["q"]["mean_logged_scalar"], .109)

    def test_bin_boundaries_and_one_are_included_once(self):
        rows = []
        for eid, top in enumerate((.49, .5, .799, .8, 1), 1):
            q = [[ACTIVITIES[0], top]] + [[name, (1 - top) / 6] for name in ACTIVITIES[1:]]
            rows.append(act(eid, q=q))
        groups, active, _, _ = analyze.replay(rows)
        metrics = analyze.describe(rows, active, groups)
        self.assertEqual([bucket["n"] for bucket in metrics["reliability"]], [1, 2, 2])


class RecommendationTests(unittest.TestCase):
    def test_denominators_network_and_retry(self):
        rows = [rec(1), rec(2, "ai_retry", 2, ["E_COUNT"]), rec(3, "local_net"),
                rec(4, "local_fail", 2, ["E_WHY"]), rec(5, "local_fail", 1, ["E_COUNT"]),
                rec(6, "local_timeout"), rec(7, "local_nomodel"), rec(8, "local_insuff")]
        groups, active, _, _ = analyze.replay(rows)
        metrics = analyze.describe(rows, active, groups)["recommendation"]
        self.assertEqual(metrics["first_bad_rate"], analyze.ratio(3, 4))
        self.assertEqual(metrics["first_network_failure_rate"], analyze.ratio(1, 6))
        self.assertEqual(metrics["debug_network_failure_rate"], analyze.ratio(1, 8))
        self.assertEqual(metrics["retry_repair_rate"], analyze.ratio(1, 2))
        self.assertEqual(metrics["final_fallback_rate"], analyze.ratio(5, 8))
        self.assertEqual(groups["real"]["rec"]["net"], 1)
        self.assertEqual(groups["real"]["rec"]["fail"], 2)
        self.assertEqual(metrics["timing_ms"]["ms1"]["n"], 6)
        self.assertEqual(metrics["timing_ms"]["ms2"]["n"], 2)
        self.assertEqual(metrics["errors"]["E_COUNT"], 2)
        self.assertIsNone(metrics["pending"])

    def test_retry_network_failure_preserves_first_network_denominator(self):
        row = rec(1, "local_fail", 2, ["E_COUNT"])
        row["net"] = "synthetic second-attempt transport failure"
        analyze.validate_event(row, "test")
        groups, active, _, warnings = analyze.replay([row])
        metrics = analyze.describe([row], active, groups)["recommendation"]
        self.assertEqual(groups["real"]["rec"]["net"], 0)
        self.assertEqual(groups["real"]["rec"]["fail"], 1)
        self.assertEqual(metrics["first_network_failure_rate"], analyze.ratio(0, 1))
        self.assertEqual(metrics["final_fallback_rate"], analyze.ratio(1, 1))
        self.assertEqual(warnings, [])
        row["res"] = "local_net"
        with self.assertRaisesRegex(analyze.InputError, "retry network failure"):
            analyze.validate_event(row, "test")

    def test_frozen_scalar_contradiction_is_not_hidden_by_matching_dstats(self):
        row = act(1)
        row["hit"] = False
        row["br"] = 1.5
        groups, _, _, warnings = analyze.replay([row])
        result = analyze.check_dstats([row], groups, dstats([row]), warnings)
        self.assertEqual(result["differences"], [])
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(len(warnings), 2)

    def test_latency_median_and_max(self):
        rows = [rec(1), rec(2), rec(3)]
        for row, ms in zip(rows, (10, 20, 90000)):
            row["ms1"] = ms
        groups, active, _, _ = analyze.replay(rows)
        timing = analyze.describe(rows, active, groups)["recommendation"]["timing_ms"]["ms1"]
        self.assertEqual(timing, {"n": 3, "median": 20, "max": 90000})


class FeedbackTests(unittest.TestCase):
    def test_vote_changes_cross_shard_and_library_feedback_is_excluded(self):
        rows = [rec(1), event(2, "rate", r=1, k="song|artist", v=1, fb="H", pos=1),
                event(51, "rate", r=1, k="song|artist", v=-1, fb="H", pos=1),
                event(101, "rate", r=1, k="song|artist", v=1, fb="H", pos=1),
                event(102, "rate", r=0, k="song|artist", v=-1, fb="", pos=0),
                event(103, "click", r=1, k="song|artist", fb="H", pos=1)]
        groups, active, _, warnings = analyze.replay(rows)
        song = analyze.describe(rows, active, groups)["songs"]["H"]
        self.assertEqual({key: song[key] for key in ("exp", "like", "dis", "unrated", "click")},
                         {"exp": 1, "like": 1, "dis": 0, "unrated": 0, "click": 1})
        self.assertEqual(warnings, [])

    def test_repeated_same_vote_is_idempotent_and_different_rec_is_independent(self):
        rows = [rec(1), rec(2), event(3, "rate", r=1, k="song|artist", v=1, fb="H", pos=1),
                event(4, "rate", r=1, k="song|artist", v=1, fb="H", pos=1),
                event(5, "rate", r=2, k="song|artist", v=-1, fb="H", pos=1)]
        groups, active, _, _ = analyze.replay(rows)
        song = analyze.describe(rows, active, groups)["songs"]["H"]
        self.assertEqual(song["positive_rate"], analyze.ratio(1, 2))
        self.assertEqual(song["unrated"], 0)


class LoadingAndReconciliationTests(unittest.TestCase):
    def test_cli_nonzero_on_incomplete_history_even_if_no_counter_difference(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            device = root / "device"
            rows = [event(2, "rate", r=0, k="song", v=1, fb="", pos=0)]
            write(device / "decisions-0.json", rows)
            write(device / "dstats.json", dstats(rows))
            # Plot is stubbed only to isolate CLI status; real plotting is a
            # separate smoke test when matplotlib is available.
            with patch.object(analyze, "plot_reliability"):
                code = analyze.main([str(device), "--check-dstats", "--output", str(root / "output")])
            self.assertEqual(code, 3)
            saved = json.loads((root / "output" / "metrics.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["dstats_check"]["status"], "HISTORY_INCOMPLETE")

    def test_cli_default_excludes_sim_but_check_still_checks_both_groups(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            device = root / "device"
            rows = [act(1, sim=True)]
            write(device / "decisions-0.json", rows)
            actual = dstats(rows)
            actual["sim"]["act"]["hit"] = 0
            write(device / "dstats.json", actual)
            with patch.object(analyze, "plot_reliability"):
                code = analyze.main([str(device), "--check-dstats", "--output", str(root / "output")])
            self.assertEqual(code, 3)
            saved = json.loads((root / "output" / "metrics.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["metrics"]["label_n"], 0)
            self.assertEqual(saved["dstats_check"]["differences"][0]["field"], "sim.act.hit")

    def test_cli_never_overwrites_prior_report(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            device = root / "device"
            device.mkdir()
            output = root / "output"
            output.mkdir()
            report = output / "REPORT.md"
            report.write_text("keep me", encoding="utf-8")
            self.assertEqual(analyze.main([str(device), "--output", str(output)]), 2)
            self.assertEqual(report.read_text(encoding="utf-8"), "keep me")

    def test_overlapping_archive_sorts_and_deduplicates(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            device, archive = root / "device", root / "archive"
            write(device / "decisions-0.json", [act(3), act(2)])
            write(archive / "decisions-0.json", [act(1), act(2)])
            rows, provenance = analyze.load_events(device, [archive])
            self.assertEqual([row["id"] for row in rows], [1, 2, 3])
            self.assertEqual(provenance["identical_duplicates"], 1)

    def test_conflicting_same_id_fails_even_if_only_sim_is_different(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write(root / "device" / "decisions-0.json", [act(1)])
            write(root / "archive" / "decisions-0.json", [act(1, sim=True)])
            with self.assertRaisesRegex(analyze.InputError, "conflicting event id 1"):
                analyze.load_events(root / "device", [root / "archive"])

    def test_duplicate_json_keys_and_nonfinite_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "bad.json"
            for text in ('{"x":1,"x":2}', '{"x":NaN}'):
                path.write_text(text, encoding="utf-8")
                with self.assertRaises(analyze.InputError):
                    analyze.read_json(path)

    def test_missing_sim_and_string_vote_fail_validation(self):
        row = act(1)
        del row["sim"]
        with self.assertRaises(analyze.InputError):
            analyze.validate_event(row, "test")
        with self.assertRaises(analyze.InputError):
            analyze.validate_event(event(2, "rate", r=1, k="song", v="1", fb="H", pos=1), "test")

    def test_900_ring_without_snapshot_is_history_incomplete(self):
        all_rows = [act(eid) for eid in range(1, 901)]
        remaining = all_rows[100:]
        groups, _, _, warnings = analyze.replay(remaining)
        result = analyze.check_dstats(remaining, groups, dstats(all_rows), warnings)
        self.assertEqual(result["status"], "HISTORY_INCOMPLETE")
        self.assertEqual(result["missing_id_ranges"], [[1, 100]])
        difference = next(row for row in result["differences"] if row["field"] == "real.act.n")
        self.assertEqual((difference["events"], difference["dstats"]), (800, 900))

    def test_900_ring_plus_overlapping_snapshot_passes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            all_rows = [act(eid, sim=eid % 2 == 0) for eid in range(1, 901)]
            device, archive = root / "device", root / "archive"
            for index in range(2, 18):
                write(device / f"decisions-{index % 16}.json", all_rows[index * 50:index * 50 + 50])
            write(archive / "decisions-0.json", all_rows[:150])
            rows, provenance = analyze.load_events(device, [archive])
            self.assertEqual(len(rows), 900)
            self.assertEqual(provenance["identical_duplicates"], 50)
            groups, _, _, warnings = analyze.replay(rows)
            result = analyze.check_dstats(rows, groups, dstats(all_rows), warnings)
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["differences"], [])

    def test_missing_zero_contribution_history_still_does_not_pass(self):
        rows = [event(2, "rate", r=0, k="song", v=1, fb="", pos=0)]
        groups, _, _, warnings = analyze.replay(rows)
        result = analyze.check_dstats(rows, groups, {"v": 1, "seq": 3, "shard": 0, "shard_n": 2, **groups}, warnings)
        self.assertEqual(result["differences"], [])
        self.assertEqual(result["status"], "HISTORY_INCOMPLETE")

    def test_every_field_comparison_finds_missing_and_extra_fields(self):
        rows = [act(1)]
        groups, _, _, warnings = analyze.replay(rows)
        actual = dstats(rows)
        del actual["real"]["err"]["E_DUP"]
        actual["sim"]["song"]["L"]["like"] = 1
        actual["real"]["act"]["unexpected"] = 0
        result = analyze.check_dstats(rows, groups, actual, warnings)
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual({row["field"] for row in result["differences"]},
                         {"real.err.E_DUP", "sim.song.L.like", "real.act.unexpected"})

    def test_event_at_seq_detects_dstats_write_lag(self):
        rows = [act(1), act(2)]
        groups, _, _, warnings = analyze.replay(rows)
        result = analyze.check_dstats(rows, groups, dstats(rows[:1]), warnings)
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["events_at_or_after_seq"], [2])

    def test_empty_data_unknown_not_zero_accuracy(self):
        groups, active, _, _ = analyze.replay([])
        metrics = analyze.describe([], active, groups)
        self.assertIsNone(metrics["accuracy"]["q"]["value"])
        self.assertIsNone(metrics["songs"]["H"]["positive_rate"]["value"])
        self.assertIn("样本量 n=0；", analyze.render_report(metrics, {"files": [], "identical_duplicates": 0}, None, []).splitlines()[0])


if __name__ == "__main__":
    unittest.main()
