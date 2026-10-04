"""Complete synthetic protocol and independent reference calculations; never real trial data."""
import copy
import hashlib
import math
from pathlib import Path
import sys
import unittest
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from metrics import (SEED, PARAMS, POLICIES, VERSION_KEYS, digest, without, freeze_sample_size,
                     schedule, song_split, registration_core, pilot_metrics, numerical_gates)


def source(plan, record, kind, time_key):
    artifacts = plan["evidence"]["sources"]
    sid = record.get("source_id")
    if sid is None:
        sid = "source-"+str(len(artifacts))
        record["source_id"] = sid
    payload = dict(kind=kind, evidence_kind=plan["evidence_kind"], collector="explicit-input-v1",
                   captured_at=record[time_key], data=without(record, "source_id"))
    artifact = dict(source_id=sid, payload=payload, sha256=digest(payload))
    for i, old in enumerate(artifacts):
        if old["source_id"] == sid:
            artifacts[i] = artifact
            break
    else:
        artifacts.append(artifact)


def register(plan):
    reg = plan["evidence"].setdefault("registration", {})
    reg.update(core=registration_core(plan), frozen_at=plan["frozen_at"])
    source(plan, reg, "registration", "frozen_at")


def rechain(rows, plan, sync_rows=True):
    e = plan["evidence"]
    exposures = {x["exposure_id"]: x for x in e["exposures"]}
    predictions = {x["prediction_id"]: x for x in e["predictions"]}
    snapshots = {x["snapshot_id"]: x for x in e["snapshots"]}
    feedback = {x["exposure_id"]: x for x in e["feedback"]}
    for f in e["feedback"]:
        source(plan, f, "feedback", "recorded_at")
    for p in e["predictions"]:
        p["prior_feedback_ids"] = sorted(f["event_id"] for f in e["feedback"]
            if f["recorded_at"] < p["predicted_at"]
            and exposures[f["exposure_id"]]["session_id"] == p["session_id"]
            and exposures[f["exposure_id"]]["policy"] == p["policy"])
        source(plan, p, "prediction", "predicted_at")
    for s in e["snapshots"]:
        s["prediction_hash"] = digest(predictions[s["prediction_id"]])
        s["sha256"] = digest(without(s, "sha256"))
    for x in e["exposures"]:
        x["snapshot_hash"] = snapshots[x["snapshot_id"]]["sha256"]
        source(plan, x, "exposure", "exposed_at")
    if sync_rows:
        for r in rows:
            x = exposures[r["exposure_id"]]
            s = snapshots[x["snapshot_id"]]
            f = feedback.get(x["exposure_id"])
            r.update({k: x[k] for k in ("session_id", "content_id", "policy", "effective_policy", "exposed_at", "snapshot_id")})
            r.update(plan["versions"], prediction_id=s["prediction_id"],
                     provenance=plan["evidence_kind"], feedback_id=f["event_id"] if f else None,
                     accept=f["value"] if f else None, interruption=f["interruption"] if f else None,
                     skipped=f["skipped"] if f else None)


def refresh_training(plan):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from learner.store import validate_bundle
    training = plan["evidence"]["training"]
    bundle = training["bundle"]
    prior_sources = {x["event_id"]: x["source_id"] for x in training["labels"]}
    labels = validate_bundle(bundle, plan["frozen_at"])
    training["labels"] = []
    for original in labels:
        label = copy.deepcopy(original)
        if label["event_id"] in prior_sources:
            label["source_id"] = prior_sources[label["event_id"]]
        source(plan, label, "training_label", "recorded_at")
        training["labels"].append(label)
    dev_labels = [x for x in labels if song_split(x["content_id"]) == "development"]
    model = dict(status="TRAINED", version="scenario-logistic-v1", synthetic=plan["evidence_kind"] == "synthetic", params=PARAMS.copy(),
                 seed=SEED, feature_hash=plan["versions"]["feature_hash"], evidence_bundle_hash=digest(bundle),
                 training_data_hash=digest(dev_labels),
                 trained_until=max(x["recorded_at"] for x in dev_labels),
                 weights=[0.]*63, transform=dict(mean=[0.]*3, median=[0.]*3, std=[1.]*3))
    plan["evidence"]["model"] = model
    plan["model_hash"] = digest(model)
    record = training.setdefault("model_record", {})
    record.update(created_at=500, model_hash=plan["model_hash"], fit_event_ids=[x["event_id"] for x in dev_labels])
    source(plan, record, "model_record", "created_at")


def legal_fixture():
    versions = {k: digest(k) for k in VERSION_KEYS}
    e = dict(sources=[], development=dict(sessions=[], rows=[]), training=dict(sessions=[], labels=[]),
             predictions=[], snapshots=[], exposures=[], feedback=[], session_records=[])
    plan = dict(status="FROZEN", evidence_kind="synthetic", seed=SEED, frozen_at=1000,
                versions=versions, evidence=e)
    differences = []
    for i in range(6):
        sid = "development-"+str(i)
        s = dict(session_id=sid, started_at=i*30, completed_at=i*30+29, independent_unit="dev-unit-"+str(i))
        source(plan, s, "development_session", "completed_at")
        e["development"]["sessions"].append(s)
        for p in ("P0", "P2"):
            for j in range(6):
                t = i*30+(0 if p == "P0" else 12)+j*2
                accept = int(p == "P2" and j < (2 if i == 5 else 1))
                r = dict(exposure_id=sid+p+str(j), session_id=sid, content_id="sha256:"+hashlib.sha256((sid+p+str(j)).encode()).hexdigest(),
                         policy=p, effective_policy=p, accept=accept, exposed_at=t, recorded_at=t+1)
                source(plan, r, "development_observation", "recorded_at")
                e["development"]["rows"].append(r)
        differences.append((2 if i == 5 else 1)/6)
    size = freeze_sample_size(differences)
    plan.update(sessions=size["sessions"], paired_session_variance=size["paired_session_variance"],
                development_data_hash=digest(e["development"]))
    ids = []
    i = 0
    while len(ids) < 40:
        cid = "sha256:"+hashlib.sha256(("training-"+str(i)).encode()).hexdigest()
        if song_split(cid) == "development":
            ids.append(cid)
        i += 1
    bundle = dict(snapshots=[], exposures=[], events=[], sessions=[])
    e["training"]["bundle"] = bundle
    for i in range(5):
        s = dict(session_id="training-"+str(i), started_at=300+i*20, completed_at=319+i*20,
                 independent_unit="training-unit-"+str(i))
        source(plan, s, "training_session", "completed_at")
        e["training"]["sessions"].append(s)
        bundle["sessions"].append(dict(session_id=s["session_id"], completed_at=s["completed_at"], provenance="synthetic"))
        for j in range(8):
            serial = str(i*8+j)
            at = 301+i*20+j*2
            cid = ids[i*8+j]
            context = dict(activity="walking", source_kind="manual", observed_at=at-1,
                           valid_until=at+10, allowed_for_current=True, historical=False)
            prediction = dict(policy="P1", predicted_at=at-1, context=context, feature_version="fixture-v1",
                              feature_hash=versions["feature_hash"], tracks=[dict(content_id=cid)])
            snapshot = dict(snapshot_id="training-snapshot-"+serial, snapshot=prediction,
                            snapshot_hash=digest(prediction), created_at=at-1)
            exposure = dict(exposure_id="training-exposure-"+serial, snapshot_id=snapshot["snapshot_id"],
                            content_id=cid, session_id=s["session_id"], exposed_at=at)
            label = dict(exposure, event_id="training-event-"+serial, policy="P1", context=context,
                         feature_version="fixture-v1", target="scenario_acceptance", value=j%2,
                         recorded_at=at+1, provenance="synthetic", snapshot=prediction)
            bundle["snapshots"].append(snapshot)
            bundle["exposures"].append(exposure)
            bundle["events"].append(label)
    refresh_training(plan)
    plan["session_ids"] = ["trial-"+str(i) for i in range(plan["sessions"])]
    plan["schedule"] = schedule(plan["sessions"])
    plan["collected_until"] = 1200+plan["sessions"]*250
    rows = []
    for i, sid in enumerate(plan["session_ids"]):
        start = 1100+i*250
        s = dict(session_id=sid, started_at=start, completed_at=start+200, independent_unit="trial-unit-"+str(i))
        source(plan, s, "trial_session", "completed_at")
        e["session_records"].append(s)
        index = 0
        for p in plan["schedule"][i]["policy_order"]:
            for j in range(6):
                suffix = sid+"-"+p+"-"+str(j)
                cid = "sha256:"+hashlib.sha256(suffix.encode()).hexdigest()
                prediction = dict(prediction_id="pred-"+suffix, session_id=sid, content_id=cid, policy=p,
                                  effective_policy=p, predicted_at=start+index*10, versions=versions.copy(),
                                  state_id=sid+"/"+p, prior_feedback_ids=[], model_hash=plan["model_hash"] if p == "P2" else None)
                source(plan, prediction, "prediction", "predicted_at")
                e["predictions"].append(prediction)
                snapshot = dict(snapshot_id="snap-"+suffix, prediction_id=prediction["prediction_id"],
                                prediction_hash=digest(prediction), created_at=start+index*10+1, versions=versions.copy())
                snapshot["sha256"] = digest(snapshot)
                e["snapshots"].append(snapshot)
                exposure = dict(exposure_id="exp-"+suffix, snapshot_id=snapshot["snapshot_id"],
                                snapshot_hash=snapshot["sha256"], session_id=sid, content_id=cid, policy=p,
                                effective_policy=p, exposed_at=start+index*10+2)
                source(plan, exposure, "exposure", "exposed_at")
                e["exposures"].append(exposure)
                f = dict(event_id="feed-"+suffix, exposure_id=exposure["exposure_id"], target="scenario_acceptance",
                         value=1 if p == "P2" else int(p == "P1" and j < 3), interruption=0, skipped=False,
                         recorded_at=start+index*10+3)
                source(plan, f, "feedback", "recorded_at")
                e["feedback"].append(f)
                rows.append(dict(exposure_id=exposure["exposure_id"]))
                index += 1
    rechain(rows, plan)
    register(plan)
    return rows, plan


def independent_reference(rows):
    """Independent grouping and bootstrap calculation, not production helpers."""
    session_ids = sorted(set(r["session_id"] for r in rows))
    delta, other, worst, interruption = [], [], [], []
    acceptance = {}
    for policy in POLICIES:
        observed = [r["accept"] for r in rows if r["policy"] == policy and r["accept"] is not None]
        acceptance[policy] = sum(observed)/len(observed)
    for sid in session_ids:
        group = {p: [r for r in rows if r["session_id"] == sid and r["policy"] == p] for p in POLICIES}
        means = {}
        for p in POLICIES:
            values = [r["accept"] for r in group[p] if r["accept"] is not None]
            means[p] = sum(values)/len(values)
        delta.append(means["P2"]-means["P0"])
        other.append(means["P2"]-means["P1"])
        worst.append((sum(r["accept"] if r["accept"] is not None else 0 for r in group["P2"])
                     -sum(r["accept"] if r["accept"] is not None else 1 for r in group["P0"]))/6)
        interruption.append((sum(r["interruption"] if r["interruption"] is not None else 1 for r in group["P2"])
                             -sum(r["interruption"] if r["interruption"] is not None else 0 for r in group["P0"]))/6)
    def ci(values):
        rng = np.random.default_rng(20261004)
        draws = []
        for _ in range(10000):
            indices = rng.integers(0, len(values), size=len(values))
            draws.append(sum(values[int(k)] for k in indices)/len(values))
        draws.sort()
        def quantile(q):
            pos = (len(draws)-1)*q
            lo = math.floor(pos)
            return draws[lo]+(draws[min(lo+1, len(draws)-1)]-draws[lo])*(pos-lo)
        return [quantile(.025), quantile(.975)]
    return dict(acceptance=acceptance, difference=sum(delta)/len(delta), ci=ci(delta), other_ci=ci(other),
                worst_ci=ci(worst), interruption_ci=ci(interruption))


class ProtocolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = legal_fixture()

    def bundle(self):
        return copy.deepcopy(self.fixture)

    def assert_rejected(self, mutate, reason):
        rows, plan = self.bundle()
        mutate(rows, plan)
        result = pilot_metrics(rows, plan)
        self.assertFalse(result["mechanism_pass"], result)
        self.assertIn(reason, result["reasons"], result["reasons"])
        self.assertNotEqual(result["status"], "PILOT_BENEFIT_SUPPORTED")
        return result

    def test_legal_synthetic_positive_is_test_only(self):
        rows, plan = self.bundle()
        result = pilot_metrics(rows, plan)
        self.assertEqual(result["reasons"], [])
        self.assertTrue(result["protocol_valid"])
        self.assertTrue(result["mechanism_pass"])
        self.assertFalse(result["real_benefit_supported"])
        self.assertEqual(result["status"], "SYNTHETIC_TEST_PROTOCOL_SUPPORTED")

    def test_real_branch_is_reachable_with_consistent_evidence_not_real_proof(self):
        # A constructed all-real-kind bundle only unit-tests routing; never real participant evidence.
        rows, plan = self.bundle()
        plan["evidence_kind"] = "real_user"
        for record in plan["evidence"]["training"]["bundle"]["events"] + plan["evidence"]["training"]["bundle"]["sessions"]:
            record["provenance"] = "real_user"
        refresh_training(plan)
        for artifact in plan["evidence"]["sources"]:
            artifact["payload"]["evidence_kind"] = "real_user"
            artifact["sha256"] = digest(artifact["payload"])
        for prediction in plan["evidence"]["predictions"]:
            if prediction["policy"] == "P2":
                prediction["model_hash"] = plan["model_hash"]
        rechain(rows, plan)
        register(plan)
        result = pilot_metrics(rows, plan)
        self.assertEqual(result["reasons"], [])
        self.assertEqual(result["status"], "PILOT_BENEFIT_SUPPORTED")

    def test_independent_numerical_reference(self):
        rows, plan = self.bundle()
        e = plan["evidence"]
        # Nonconstant paired outcomes and missing outcomes exercise intervals and bounds.
        for i, f in enumerate(e["feedback"]):
            if i % 31 == 0:
                f["value"] = None
            elif i % 17 == 0:
                f["value"] = 1-f["value"]
            if i % 41 == 0:
                f["interruption"] = 1
        rechain(rows, plan)
        got = pilot_metrics(rows, plan)
        self.assertTrue(got["protocol_valid"], got["reasons"])
        ref = independent_reference(rows)
        self.assertAlmostEqual(got["p2_p0_difference"], ref["difference"], places=12)
        for key, rk in (("p2_p0_ci", "ci"), ("p2_p1_ci", "other_ci"),
                        ("worst_missing_difference_ci", "worst_ci"),
                        ("interruption_difference_ci", "interruption_ci")):
            np.testing.assert_allclose(got[key], ref[rk], atol=1e-12, rtol=0)
        for p in POLICIES:
            self.assertAlmostEqual(got["conditions"][p]["acceptance"], ref["acceptance"][p])

    def test_forged_schedule(self):
        self.assert_rejected(lambda r, p: p["schedule"][0].update(policy_order=["P0"]*3),
                             "schedule_not_frozen_balanced_order")

    def test_fixed_actual_order_rejected(self):
        def mutate(rows, plan):
            sid = plan["session_ids"][0]
            current = [x for x in plan["evidence"]["exposures"] if x["session_id"] == sid]
            current[0]["exposed_at"], current[6]["exposed_at"] = current[6]["exposed_at"], current[0]["exposed_at"]
        self.assert_rejected(mutate, "actual_policy_order_mismatch")

    def test_missing_training_qualification(self):
        self.assert_rejected(lambda r, p: p["evidence"]["training"].update(labels=[]), "p2_training_ineligible")

    def test_model_untrained(self):
        self.assert_rejected(lambda r, p: p["evidence"]["model"].update(status="UNTRAINED"),
                             "p2_model_untrained_or_provenance")

    def test_model_not_ready_before_schedule(self):
        self.assert_rejected(lambda r, p: p["evidence"]["training"]["model_record"].update(created_at=p["frozen_at"]),
                             "p2_not_trained_before_scheduling")

    def test_p2_fallback_rejected(self):
        def mutate(rows, plan):
            next(e for e in plan["evidence"]["exposures"] if e["policy"] == "P2")["effective_policy"] = "P0"
        self.assert_rejected(mutate, "policy_not_delivered")

    def test_changed_request(self):
        self.assert_rejected(lambda r, p: p["evidence"]["predictions"][0]["versions"].update(request_hash="a"*64),
                             "cross_version_or_request")

    def test_cross_feature_version(self):
        self.assert_rejected(lambda r, p: p["evidence"]["snapshots"][0]["versions"].update(feature_hash="b"*64),
                             "cross_version_or_request")

    def test_orphan_exposure(self):
        def mutate(rows, plan):
            plan["evidence"]["exposures"].append(dict(plan["evidence"]["exposures"][0], exposure_id="orphan"))
        self.assert_rejected(mutate, "row_exposure_set_mismatch")

    def test_duplicate_exposure(self):
        self.assert_rejected(lambda r, p: p["evidence"]["exposures"].append(copy.deepcopy(p["evidence"]["exposures"][0])),
                             "exposure_duplicate_id")

    def test_repeat_content(self):
        def mutate(rows, plan):
            plan["evidence"]["exposures"][1]["content_id"] = plan["evidence"]["exposures"][0]["content_id"]
        self.assert_rejected(mutate, "repeat_content_within_session")

    def test_six_per_strategy_required(self):
        def mutate(rows, plan):
            plan["evidence"]["exposures"].pop()
        self.assert_rejected(mutate, "six_exposures_each_required")

    def test_snapshot_tampered(self):
        self.assert_rejected(lambda r, p: p["evidence"]["snapshots"][0].update(created_at=999),
                             "snapshot_hash_mismatch")

    def test_future_feedback(self):
        self.assert_rejected(lambda r, p: p["evidence"]["feedback"][0].update(recorded_at=p["collected_until"]+1),
                             "future_feedback_or_time_chain")

    def test_future_label_used_in_prediction(self):
        self.assert_rejected(lambda r, p: p["evidence"]["predictions"][0].update(prior_feedback_ids=[p["evidence"]["feedback"][-1]["event_id"]]),
                             "prediction_update_chain_mismatch")

    def test_shared_policy_state(self):
        self.assert_rejected(lambda r, p: p["evidence"]["predictions"][0].update(state_id="shared"),
                             "policy_state_not_isolated")

    def test_missing_outcomes_too_many_with_valid_protocol(self):
        def mutate(rows, plan):
            exposures = {x["exposure_id"]: x for x in plan["evidence"]["exposures"]}
            for f in plan["evidence"]["feedback"]:
                x = exposures[f["exposure_id"]]
                if x["policy"] == "P2" and int(f["event_id"].rsplit("-", 1)[-1]) < 2:
                    f["value"] = None
            rechain(rows, plan)
        result = self.assert_rejected(mutate, "missing_at_most_20pct")
        self.assertTrue(result["protocol_valid"], result["reasons"])

    def test_selective_session_deletion(self):
        self.assert_rejected(lambda r, p: p["evidence"]["session_records"].pop(), "trial_session_set_mismatch")

    def test_forged_n(self):
        self.assert_rejected(lambda r, p: p.update(sessions=p["sessions"]+1), "sample_size_not_recomputed")

    def test_forged_variance(self):
        self.assert_rejected(lambda r, p: p.update(paired_session_variance=.999), "development_variance_mismatch")

    def test_forged_freeze_time(self):
        self.assert_rejected(lambda r, p: p.update(frozen_at=p["frozen_at"]+1), "registration_plan_mismatch")

    def test_development_overlap(self):
        self.assert_rejected(lambda r, p: p["session_ids"].__setitem__(0, p["evidence"]["development"]["sessions"][0]["session_id"]),
                             "development_trial_overlap")

    def test_provenance_string_cannot_upgrade_fixture(self):
        self.assert_rejected(lambda r, p: p.update(evidence_kind="real_user"), "source_kind_mismatch")

    def test_source_digest_tamper(self):
        self.assert_rejected(lambda r, p: p["evidence"]["sources"][0].update(sha256="0"*64),
                             "source_digest_mismatch")

    def test_source_content_must_match_not_just_hash(self):
        def mutate(rows, plan):
            a = plan["evidence"]["sources"][0]
            a["payload"]["data"]["completed_at"] += 1
            a["sha256"] = digest(a["payload"])
        self.assert_rejected(mutate, "development_session_source_mismatch")

    def test_missing_source(self):
        self.assert_rejected(lambda r, p: p["evidence"].update(sources=[]), "development_session_source_mismatch")

    def test_duplicate_training_observation_different_event_id(self):
        def mutate(rows, plan):
            label = copy.deepcopy(plan["evidence"]["training"]["labels"][0])
            label["event_id"] = "duplicated-observation"
            plan["evidence"]["training"]["labels"].append(label)
        self.assert_rejected(mutate, "training_duplicate_exposure_target")

    def test_training_content_hash_invalid(self):
        self.assert_rejected(lambda r, p: p["evidence"]["training"]["labels"][0].update(content_id="filename.wav"),
                             "training_content_invalid")

    def test_training_trial_renamed_same_independent_unit(self):
        self.assert_rejected(lambda r, p: p["evidence"]["session_records"][0].update(independent_unit="training-unit-0"),
                             "training_trial_independent_unit_overlap")

    def test_development_trial_renamed_same_independent_unit(self):
        self.assert_rejected(lambda r, p: p["evidence"]["session_records"][0].update(independent_unit="dev-unit-0"),
                             "development_trial_independent_unit_overlap")

    def test_versions_invalid_preserves_specific_reason(self):
        self.assert_rejected(lambda r, p: p.update(versions=None), "invalid_object_field:plan.versions")

    def test_row_order_does_not_change_seeded_interval(self):
        rows, plan = self.bundle()
        for i, f in enumerate(plan["evidence"]["feedback"]):
            if i % 17 == 0:
                f["value"] = 1-f["value"]
        rechain(rows, plan)
        first = pilot_metrics(rows, plan)
        rows.reverse()
        second = pilot_metrics(rows, plan)
        self.assertEqual(first["p2_p0_ci"], second["p2_p0_ci"])
        self.assertEqual(first["status"], second["status"])

    def test_malformed_inputs_return_reasons(self):
        for rows, plan in ((None, {}), ([], None), ([None], {}), ([], {"evidence": None}),
                           ([], {"evidence": {"sources": ["bad"]}})):
            with self.subTest(rows=rows, plan=plan):
                result = pilot_metrics(rows, plan)
                self.assertEqual(result["status"], "NO_USER_BENEFIT_EVIDENCE")
                self.assertTrue(result["reasons"])

    def test_nonstring_keys_return_structured_insufficiency(self):
        for location in ("plan", "row", "source"):
            for key in (7, None, ("invalid", "key")):
                with self.subTest(location=location, key=key):
                    rows, plan = self.bundle()
                    target = plan if location == "plan" else rows[0] if location == "row" else plan["evidence"]["sources"][0]["payload"]
                    target[key] = "invalid-key"
                    result = pilot_metrics(rows, plan)
                    self.assertEqual(result["status"], "NO_USER_BENEFIT_EVIDENCE")
                    self.assertFalse(result["mechanism_pass"])
                    self.assertTrue(any(reason.startswith("invalid_key:") for reason in result["reasons"]))

    def test_nonfinite_and_invalid_types_rejected(self):
        for value in (math.nan, math.inf, -math.inf, "15", True, None):
            with self.subTest(value=value):
                rows, plan = self.bundle()
                plan["sessions"] = value
                result = pilot_metrics(rows, plan)
                self.assertFalse(result["mechanism_pass"])
                self.assertTrue(result["reasons"])


class BoundaryTests(unittest.TestCase):
    def stats(self):
        return dict(complete_sessions=15, missing_rates=dict(P0=.1, P1=.1, P2=.1),
                    p2_p0_difference=.2, p2_p0_ci=[.1, .3],
                    worst_missing_difference_ci=[.05, .25], interruption_difference_ci=[-.1, -.01])

    def check_single(self, key, field, values, expected):
        for value, want in zip(values, expected):
            stats = self.stats()
            stats[field] = value
            got = numerical_gates(stats, 15)
            with self.subTest(field=field, value=value):
                self.assertEqual(got[key], want)
                self.assertTrue(all(ok for name, ok in got.items() if name != key))

    def test_n_below_equal_above(self):
        self.check_single("fixed_sample_size", "complete_sessions", [14, 15, 16], [False, True, True])

    def test_missing_below_equal_above(self):
        self.check_single("missing_at_most_20pct", "missing_rates",
                          [dict(P0=.1, P1=.1, P2=x) for x in (.199999, .20, .200001)], [True, True, False])

    def test_gain_below_equal_above(self):
        self.check_single("gain_at_least_10pp", "p2_p0_difference", [.099999, .10, .100001], [False, True, True])

    def test_gain_lower_below_equal_above(self):
        self.check_single("gain_lower_positive", "p2_p0_ci", [[x, .3] for x in (-.000001, 0, .000001)],
                          [False, False, True])

    def test_worst_lower_below_equal_above(self):
        self.check_single("worst_missing_lower_positive", "worst_missing_difference_ci",
                          [[x, .3] for x in (-.000001, 0, .000001)], [False, False, True])

    def test_interruption_upper_below_equal_above(self):
        self.check_single("interruption_upper_nonpositive", "interruption_difference_ci",
                          [[-.1, x] for x in (-.000001, 0, .000001)], [True, True, False])

    def test_huge_integer_numeric_gate_returns_false(self):
        stats = self.stats()
        stats["p2_p0_difference"] = 10**1000
        result = numerical_gates(stats, 15)
        self.assertFalse(result["gain_at_least_10pp"])
        self.assertTrue(all(ok for name, ok in result.items() if name != "gain_at_least_10pp"))

    def test_huge_integer_sample_planning_is_blocked(self):
        self.assertEqual(freeze_sample_size([10**1000]*6)["status"], "SAMPLE_SIZE_BLOCKED")

    def test_every_numeric_gate_rejects_invalid_types(self):
        for value in (math.nan, math.inf, -math.inf, "0", True, None, [], {}):
            for key, field in (("fixed_sample_size", "complete_sessions"), ("gain_at_least_10pp", "p2_p0_difference"),
                               ("gain_lower_positive", "p2_p0_ci"), ("worst_missing_lower_positive", "worst_missing_difference_ci"),
                               ("interruption_upper_nonpositive", "interruption_difference_ci"),
                               ("missing_at_most_20pct", "missing_rates")):
                with self.subTest(value=value, key=key):
                    stats = self.stats()
                    stats[field] = value if "ci" not in field else [value, value]
                    self.assertFalse(numerical_gates(stats, 15)[key])
        for value in (True, "15", math.nan, math.inf, None, 0):
            self.assertFalse(numerical_gates(self.stats(), value)["fixed_sample_size"])


if __name__ == "__main__":
    unittest.main()
