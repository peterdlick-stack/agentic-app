# B review of C (read-only)

Decision: no implementation-blocking issue found in the inspected offline path. Retain the baseline. This review is not an accuracy approval.

Inspected activity/candidate.py, run.py, baseline.py, reference_eval.py and saved scored rows/report. Ran learner/review_c_check.py with python3 -B; actual exit code 0, log review-C-check.log. The review script only reads activity and writes its log in learner. No C code was edited.

- The predictor projects sensor-only fields, reads causal trailing windows, and rejects invalid baseline quality before six-axis features. Label, filename and placement metadata do not enter candidate.predict.
- The baseline reference scorer retains unknown predictions in true-class recall denominators. Independent recomputation from scored rows reproduces 62 eligible windows.
- Baseline walking: 0 true positives, 33 unknown; recall 0. Candidate walking: 4 true positives, 29 unknown; recall 4/33. Candidate also introduces 8 walking false positives among 29 stationary windows. Its walking precision is 4/(4+8), below the frozen gate.
- All five existing sessions remain development diagnostics. No new independent test session, pocket precision or delay claim is made. Saved report retains ACCURACY_UNVERIFIED and baseline_retained=true.
- The original reference synchronization is not independently verified; repeated overlapping windows do not establish independent accuracy. Session intervals and delays correctly remain not estimable.

Limit: this is a static review plus metric recomputation, not a full independent rerun of the sensor pipeline. The final fresh reviewer owns the full acceptance rerun.
