"""Synthetic mechanism-only tests. No synthetic result is accuracy or benefit evidence."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from .model import rank, train, digest, effective_context, song_split, predict_before_update
from .store import EvidenceStore, validate_bundle

NOW = 10000.
CID = "sha256:" + "1" * 64
CONTEXT = dict(activity="walking", source_kind="manual", observed_at=100., valid_until=20000., allowed_for_current=True, historical=False)


def features(cid=CID, bpm=104):
    values = dict(bpm=bpm, rms_dbfs=-20., dynamic_db=8., vocal=None)
    return {"content_id": cid, "features": {name:dict(value=value, unit="BPM" if name=="bpm" else "dB", method_version="fixture-v1", source="synthetic test", kind="unknown" if value is None else "estimate", quality=dict(score=None, calibrated=False), reason="unknown" if value is None else None) for name,value in values.items()}}


def bundle(n=0, provenance="synthetic"):
    result = dict(snapshots=[], exposures=[], events=[], sessions=[])
    f = []
    i = 0
    while len(result["events"]) < n:
        cid = "sha256:" + hashlib.sha256(str(i).encode()).hexdigest()
        i += 1
        if song_split(cid) != "development":
            continue
        j = len(result["events"])
        f.append(features(cid, 60+j))
        p = dict(policy="P1", predicted_at=1000+j*3, context=CONTEXT, feature_version="fixture-v1", tracks=[dict(content_id=cid)])
        snap = dict(snapshot_id=f"s{j}", snapshot=p, snapshot_hash=digest(p), created_at=1000+j*3)
        x = dict(exposure_id=f"x{j}", snapshot_id=f"s{j}", content_id=cid, session_id=f"session{j%5}", exposed_at=1001+j*3)
        e = dict(x, event_id=f"e{j}", policy="P1", context=CONTEXT, feature_version="fixture-v1", target="scenario_acceptance", value=j%2, recorded_at=1002+j*3, provenance=provenance, snapshot=p)
        result["snapshots"].append(snap)
        result["exposures"].append(x)
        result["events"].append(e)
    result["sessions"] = [dict(session_id=f"session{j}", completed_at=9000., provenance=provenance) for j in range(5)]
    for snap in result["snapshots"]:
        snap["snapshot"]["feature_hash"] = digest(f)
        snap["snapshot_hash"] = digest(snap["snapshot"])
    return result, f


class MechanismTests(unittest.TestCase):
    def test_p0_exact_ordinary_score_and_alias_ties(self):
        tracks=[dict(id="a", content_id=CID, path="a")]
        r=rank(tracks, [], CONTEXT, {"tracks":{CID:3}}, now=NOW)
        self.assertEqual(r["tracks"][0]["score"], .21)
        self.assertEqual(r["tracks"][0]["path"], "a")

    def test_p1_soft_tempo(self):
        r=rank([dict(content_id=CID)], [features()], CONTEXT, {}, "P1", now=NOW)
        self.assertEqual(r["tracks"][0]["score"], 1.)

    def test_missing_unknown_and_stationary_not_reading(self):
        r=rank([dict(content_id=CID)], [features(bpm=None)], dict(CONTEXT, activity="stationary"), {}, "P1", now=NOW)
        self.assertEqual(r["tracks"][0]["score"], 0.)
        self.assertEqual(r["effective_activity"], "stationary")

    def test_expired_context_fallback_and_strict_detection(self):
        c=dict(CONTEXT, valid_until=999.)
        self.assertEqual(rank([],[],c,{},"P1",now=NOW)["effective_policy"], "P0")
        with self.assertRaisesRegex(ValueError, "expired"):
            effective_context(c,NOW,strict=True)

    def test_sdk_reading_rejected(self):
        self.assertEqual(effective_context(dict(CONTEXT, activity="reading", source_kind="sdk"),NOW),"unknown")

    def test_missing_required_feature_detected(self):
        f=features()
        del f["features"]["bpm"]["source"]
        with self.assertRaisesRegex(ValueError,"missing_required"):
            rank([], [f], CONTEXT, {}, now=NOW)

    def test_synthetic_labels_never_train(self):
        b,f=bundle(45)
        self.assertEqual(train(b,f,now=NOW)["status"],"UNTRAINED")

    def test_song_like_never_trains_scenario(self):
        b,f=bundle(45,"real_user") # structural test fixture; never exported as observed evidence
        for e in b["events"]:
            e["target"]="song_like"
        self.assertEqual(train(b,f,now=NOW)["status"],"UNTRAINED")

    def test_skips_not_negative(self):
        b,f=bundle(45,"real_user")
        for e in b["events"]:
            e["value"]=None
        m=train(b,f,now=NOW)
        self.assertEqual(m["eligibility_counts"]["negative"],0)

    def test_untrained_p2_falls_back(self):
        self.assertEqual(rank([],[],CONTEXT,{},"P2",now=NOW)["status"],"UNTRAINED")

    def test_duplicate_and_future_feedback_detected(self):
        b,f=bundle(1)
        b["events"].append(dict(b["events"][0],event_id="second"))
        with self.assertRaisesRegex(ValueError,"duplicate_feedback"):
            train(b,f,now=NOW)
        b["events"].pop()
        b["events"][0]["recorded_at"]=NOW+1
        with self.assertRaisesRegex(ValueError,"future_label"):
            train(b,f,now=NOW)

    def test_snapshot_mutation_and_unexposed_rejected(self):
        b,f=bundle(1)
        b["events"][0]["snapshot"]=dict(b["events"][0]["snapshot"], policy="P2")
        with self.assertRaisesRegex(ValueError,"snapshot_mutated"):
            train(b,f,now=NOW)
        b,f=bundle(1)
        b["exposures"]=[]
        with self.assertRaisesRegex(ValueError,"without_exposure"):
            train(b,f,now=NOW)

    def test_fit_restore_and_future_model_guard(self):
        # Deliberately marked fake real_user records exercise mechanism only.
        b,f=bundle(45,"real_user")
        m=train(b,f,now=NOW)
        self.assertEqual(m["status"],"TRAINED")
        tracks=[dict(content_id=f[0]["content_id"])]
        r=rank(tracks,f,CONTEXT,{},"P2",m,NOW)
        self.assertEqual(r,rank(tracks,f,CONTEXT,{},"P2",json.loads(json.dumps(m)),NOW))
        with self.assertRaisesRegex(ValueError,"future_label"):
            rank(tracks,f,CONTEXT,{},"P2",m,1005.)
        changed=copy.deepcopy(f)
        changed[0]["features"]["bpm"]["value"]=400
        with self.assertRaisesRegex(ValueError,"feature_version"):
            rank(tracks,changed,CONTEXT,{},"P2",m,NOW)

    def test_prequential_prefix_ignores_future_evidence(self):
        b,f=bundle(45)
        r=predict_before_update([],f,CONTEXT,{},b,1050.)
        self.assertEqual(r["status"],"UNTRAINED")

    def test_snapshot_feature_hash_binding(self):
        b,f=bundle(45,"real_user")
        f[0]["features"]["bpm"]["value"]=300.
        with self.assertRaisesRegex(ValueError,"snapshot_feature_hash"):
            train(b,f,now=NOW)

    def test_alias_split_is_content_based(self):
        self.assertEqual(song_split(CID),song_split(CID))

    def test_store_idempotency_immutable_and_separate_targets(self):
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as path:
            s=EvidenceStore(path)
            b,_=bundle(1,"real_user")
            snap=b["snapshots"][0]
            x=b["exposures"][0]
            e=b["events"][0]
            s.snapshot(snap["snapshot_id"],snap["snapshot"],snap["created_at"])
            s.expose(**x)
            self.assertFalse(s.record(e)["duplicate"])
            self.assertTrue(s.record(e)["duplicate"])
            self.assertEqual(s.preferences("P1"),{"tracks":{}})
            with self.assertRaisesRegex(ValueError,"duplicate_feedback"):
                s.record(dict(e,event_id="new"))
            s.record(dict(e,event_id="song",target="song_like",value=1))
            self.assertEqual(s.preferences("P1")["tracks"][e["content_id"]],1)
            with self.assertRaises(sqlite3.IntegrityError):
                s.db.execute("DELETE FROM events")
            s.db.rollback()
            s.close()
            restored=EvidenceStore(path)
            self.assertEqual(len(restored.export()["events"]),2)
            restored.close()


class SoftRankingRepairTests(unittest.TestCase):
    def test_fixed_counterexample(self):
        other = "sha256:" + "2" * 64
        r = rank([dict(content_id=CID), dict(content_id=other)],
                 [features(CID, 60), features(other, None)], CONTEXT,
                 {"tracks": {CID: -100, other: 100}}, "P1", now=NOW)
        self.assertEqual([t["content_id"] for t in r["tracks"]], [other, CID])
        self.assertEqual([t["score"] for t in r["tracks"]], [.34313725, .21686275])

    def test_equal_score_stable_alias_order(self):
        other = "sha256:" + "2" * 64
        r = rank([dict(content_id=other, id="z"), dict(content_id=CID, id="a"),
                  dict(content_id=CID, id="b")], [], CONTEXT, {}, "P1", now=NOW)
        self.assertEqual([t["id"] for t in r["tracks"]], ["a", "b", "z"])

    def test_all_unknown_same_as_p0(self):
        other = "sha256:" + "2" * 64
        args = ([dict(content_id=CID), dict(content_id=other)],
                [features(CID, None), features(other, None)], CONTEXT,
                {"tracks": {CID: -7, other: 3}})
        self.assertEqual(rank(*args, "P1", now=NOW)["tracks"],
                         rank(*args, "P0", now=NOW)["tracks"])

    def test_negative_preference_p0_unchanged(self):
        ids = ["sha256:" + str(i) * 64 for i in range(1, 6)]
        counts = [-100, -3, 0, 3, 100]
        r = rank([dict(content_id=cid) for cid in ids],
                 [features(cid, 104) for cid in ids], CONTEXT,
                 {"tracks": dict(zip(ids, counts))}, "P0", now=NOW)
        self.assertEqual([t["content_id"] for t in r["tracks"]], list(reversed(ids)))
        self.assertEqual([t["score"] for t in r["tracks"]],
                         [round(.35 * n / (abs(n) + 2), 8) for n in reversed(counts)])

    def test_expired_stationary_p0_fallback(self):
        for c in (dict(CONTEXT, valid_until=999.), dict(CONTEXT, activity="stationary")):
            with self.subTest(context=c):
                args = ([dict(content_id=CID)], [features()], c, {"tracks": {CID: -3}})
                r = rank(*args, "P1", now=NOW)
                self.assertEqual(r["effective_policy"], "P0")
                self.assertEqual(r["status"], "CONTEXT_FALLBACK")
                self.assertEqual(r["tracks"], rank(*args, "P0", now=NOW)["tracks"])

    def test_untrained_p2_same_as_p0(self):
        other = "sha256:" + "2" * 64
        args = ([dict(content_id=CID), dict(content_id=other)],
                [features(CID, 104), features(other, None)], CONTEXT,
                {"tracks": {CID: -100, other: 100}})
        r = rank(*args, "P2", model={"status": "UNTRAINED"}, now=NOW)
        self.assertEqual(r["effective_policy"], "P0")
        self.assertEqual(r["status"], "UNTRAINED")
        self.assertEqual(r["tracks"], rank(*args, "P0", now=NOW)["tracks"])


if __name__ == "__main__":
    unittest.main()
