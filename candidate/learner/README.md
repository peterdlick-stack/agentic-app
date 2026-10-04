# Branch B delivery

Status: UNTRAINED; NO_USER_BENEFIT_EVIDENCE; SAMPLE_SIZE_BLOCKED. No genuine scenario-acceptance dataset was found in the inspected source state. No P2 model is enabled. S/state was empty and the bounded depth-4 search found no SQLite or events/preferences JSON; this does not assert that feedback cannot exist elsewhere.

## API

- `learner.model.rank(tracks, feature_rows, context, preferences, policy='P0', model=None, now=None)` implements frozen contract v1. Existing track metadata is preserved. P0 uses exactly 0.35*c/(abs(c)+2); P1 adds the fixed soft BPM rule; requested untrained P2 visibly falls back to P0. Scores are uncalibrated, never probabilities.
- `learner.store.EvidenceStore(state_dir)` provides snapshot, expose, record, complete_session, export, preferences(policy), close. Snapshot payload requires policy, predicted_at, context, feature_version, feature_hash and tracks. The feature_hash is digest(feature_rows); train requires the snapshot hash match.
- `train(store.export(), feature_rows, output_path=None, now=None)` only fits genuine scenario_acceptance values with preexisting immutable snapshots/exposures after frozen eligibility. Song likes and missing values cannot become scenario negatives. Sealed song labels are excluded from fit and eligibility.
- `predict_before_update(..., bundle, at)` takes a chronological evidence prefix before fitting. Future snapshots, exposures, session completion and ratings cannot enter prefix training.
- `python3 -B -m learner.model --events learner/state/events-export.json --features audio/features.json --output learner/state/model.json` trains only when actual evidence meets the frozen gate. Do not rename synthetic labels as real-user evidence.

The persisted state/model.json is explicitly UNTRAINED. Its current feature hash is the empty side-table hash because A's side table was not present at generation time; it cannot be used as a trained model. Integration generates current isolated state using the current feature table.

## Verified

17 mechanism tests, zero skips, exit 0 in test-iteration2.log. Includes P0 formula, P1 tempo, unknown/stationary behavior, expired context, missing feature schema, separate feedback targets, null handling, synthetic training exclusion, duplicate/future evidence rejection, snapshot integrity, prequential future-prefix exclusion, feature-hash binding, model restore, SQLite restart and immutable triggers. Mechanism-only fixtures that deliberately exercise the real_user gate are explicitly identified in the test source; they were never exported as observed feedback or benefit evidence.

Iteration 1 failed before tests because redirecting HOME hid installed NumPy. No dependency was installed. Explicit PYTHONPATH=/home/fanzhou/.local/lib/python3.12/site-packages exposes the existing package. Iteration 2 includes A's two review fixes, then passed. No third algorithm iteration was made.

## Reproduction and boundaries

From R in WSL, set PYTHONPATH to the existing package path above, PYTHONDONTWRITEBYTECODE=1, and HOME/TMPDIR/TMP/TEMP/XDG_CACHE_HOME/XDG_CONFIG_HOME/XDG_DATA_HOME to R/learner/tmp in the child process; run `python3 -B -m unittest learner.test_model -v`. Stop is Ctrl-C for that foreground process. No background process is created.

Only learner was written by branch B. Existing source/player/library and C's implementation were read only. All branch jobs completed with returned exits; none remained running at the environment interruption. B review of C is review-C.md, supported by review-C-check.log exit 0.

## Not verified

True preference benefit, observed-label ranking metrics, sample-size calculation, activity accuracy, song accuracy and human playback acceptance are not verified by B. Their values remain null or blocked in report.json. NumPy arithmetic tests and recovery checks are not user-benefit evidence. Jev was not called.
