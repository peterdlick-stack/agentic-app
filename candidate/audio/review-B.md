# A read-only review of B

Scope: `learner/model.py`, `learner/store.py`; review only, no changes to B files.

1. RESOLVED in B iteration2. Historical prequential API originally retained future snapshot/exposure metadata. Reviewer reran `audio/review_b_probe.py` and verified the prior `future_snapshot` rejection is gone; prefix metadata is now filtered.
2. RESOLVED in B iteration2. Eligible labels now require their immutable snapshot.feature_hash to equal the exact provided feature table digest. Reviewer inspected code and author regression test log (17 tests passed); reviewer did not rerun B's full suite, leaving full independent rerun to final reviewer.

Positive checks: actual scalar scores are explicitly uncalibrated; fixed logistic parameters, development-only transform, sealed labels excluded from fitting; scenario labels and song likes separated; append-only evidence and duplicate exposure/target rejection present. No synthetic training is eligible.
