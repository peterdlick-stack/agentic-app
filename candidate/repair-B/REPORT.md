# B repair
Root cause: context_evidence boolean preceded numerical soft score in production rank key. Deleted boolean priority; weights, BPM estimates and input fixture unchanged. Stationary now reports explicit P0 fallback, preserving stationary activity.
Actual command: python3 -B -m unittest learner.test_model -v from R1; subprocess TMP/TEMP/TMPDIR=R1/tmp/repair-B, HOME unchanged.
RED 23 tests, 2 failures, exit 1. GREEN 23 tests, zero failures/skips, exit 0. Original17 unchanged; six actual-rank tests appended. All inputs synthetic and no accuracy/benefit evidence.
model SHA256 79500fa5f1c59a0a8383cb94f079a818919280797f1ad231831e95d514d4e98d
