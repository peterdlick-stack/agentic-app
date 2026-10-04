from pathlib import Path
p=Path('/mnt/f/context-recommend-v1-20261004-154611/learner/model.py')
s=p.read_text(encoding='utf-8-sig')
s=s.replace('    if ready:\n        if len(', '    if eligible and any(e["snapshot"].get("feature_hash") != digest(feature_rows) for e in eligible):\n        raise ValueError("training_snapshot_feature_hash_mismatch")\n    if ready:\n        if len(')
s=s.replace('    prefix = dict(bundle, events=[e for e in bundle["events"] if e["recorded_at"] < at])', '''    kept_events = [e for e in bundle["events"] if e["recorded_at"] < at]
    exposure_ids = {e["exposure_id"] for e in kept_events}
    exposures = [e for e in bundle["exposures"] if e["exposure_id"] in exposure_ids and e["exposed_at"] < at]
    snapshot_ids = {e["snapshot_id"] for e in exposures}
    prefix = dict(events=kept_events, exposures=exposures,
                  snapshots=[s for s in bundle["snapshots"] if s["snapshot_id"] in snapshot_ids and s["created_at"] < at],
                  sessions=[s for s in bundle["sessions"] if s["completed_at"] < at])''')
p.write_text(s,encoding='utf-8')
p=Path('/mnt/f/context-recommend-v1-20261004-154611/learner/test_model.py')
s=p.read_text(encoding='utf-8-sig')
s=s.replace('    return result, f', '''    for snap in result["snapshots"]:
        snap["snapshot"]["feature_hash"] = digest(f)
        snap["snapshot_hash"] = digest(snap["snapshot"])
    return result, f''')
s=s.replace('    def test_alias_split_is_content_based(self):', '''    def test_prequential_prefix_ignores_future_evidence(self):
        b,f=bundle(45)
        r=predict_before_update([],f,CONTEXT,{},b,1050.)
        self.assertEqual(r["status"],"UNTRAINED")

    def test_snapshot_feature_hash_binding(self):
        b,f=bundle(45,"real_user")
        f[0]["features"]["bpm"]["value"]=300.
        with self.assertRaisesRegex(ValueError,"snapshot_feature_hash"):
            train(b,f,now=NOW)

    def test_alias_split_is_content_based(self):''')
p.write_text(s,encoding='utf-8')
