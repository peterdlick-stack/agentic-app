# Independent A review of B

Production diff:
```diff
--- 
+++ 
@@ -105,7 +105,7 @@
             raise ValueError("future_label_leakage")
         if model["feature_hash"] != digest(feature_rows):
             raise ValueError("model_feature_version_mismatch")
-    if activity == "unknown":
+    if activity in ("unknown", "stationary"):
         effective = "P0"
         if status == "OK" and policy != "P0":
             status = "CONTEXT_FALLBACK"
@@ -129,7 +129,7 @@
         result.append(dict(track, score=round(score, 8), context_evidence=evidence, reason=reason,
                            score_semantics="uncalibrated_ranking_score",
                            seen_in_training=cid in (model or {}).get("seen_content_ids", [])))
-    result.sort(key=lambda t: (-int(t["context_evidence"]), -t["score"], t["content_id"]))
+    result.sort(key=lambda t: (-t["score"], t["content_id"]))
     return dict(requested_policy=policy, effective_policy=effective, status=status, tracks=result,
                 effective_activity=activity, algorithm_version=VERSION, predicted_at=now)
 
```
No weight or target tuning. Removed evidence boolean sort priority; stable content_id tiebreak remains and aliases retain input order. Also marks valid stationary/unknown fallback as CONTEXT_FALLBACK instead of implying OK.

Independent call to actual production rank, using distinct a/b content IDs, returns unknown +100 first (0.34313725), known BPM60 -100 second (0.21686275). Exit 0
```
[('sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb', 0.34313725), ('sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 0.21686275)]
```
Re-ran full learner suite 23 tests, exit 0. Original 17 retained plus fixed counterexample/ties/all unknown/negative/P0/context/P2 coverage. No blocking finding; P1 may be restored as explicit soft ranking. Hard BPM remains disabled.
