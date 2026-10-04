"""Current candidate ownership and independent historical immutability."""
import json,hashlib,sys
from pathlib import Path
R=Path(__file__).resolve().parents[1]
config=json.loads((R/'repair-config.json').read_text());OLD=Path(config['R0'])
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
frozen=json.loads((OLD/'ledger/final-source-hashes.json').read_text());bad=[k for k,v in frozen.items() if sha(OLD/k)!=v];assert not bad,('R0_CHANGED',bad)
base=json.loads((R/'ledger/copy-baseline.json').read_text());allow=json.loads((R/'repair-allowlist.json').read_text());allowed=set(sum([allow[k] for k in ['A','B','C','main']],[]))
changed=[k for k,v in base.items() if sha(R/k)!=v];assert set(changed)<=allowed,('OUTSIDE_ALLOWLIST',set(changed)-allowed)
inputs=json.loads((R/'ledger/input-hashes.json').read_text()); immutable=[k for k in inputs if k.startswith(('integration/test-fixtures/','integration/context_player/tests/','contract/'))]
assert all(sha(R/k)==inputs[k] for k in immutable),'IMMUTABLE_TEST_OR_CONTRACT_CHANGED'
for k in base:
 if k.startswith(('audio/','activity/')):assert sha(R/k)==base[k],('UNCHANGED_ALGORITHM_INPUT',k)
assert not list(R.rglob('__pycache__')),'SOURCE_PYCACHE'
features=json.loads((R/'audio/features.json').read_text());assert len(features)==48
checks=json.loads((R/'activity/checks.json').read_text());assert len(checks)==22 and all(checks.values())
# These activity diagnostics are hash-bound historical results, not freshly replayed algorithms.
manifest=R/'ledger/final-source-hashes.json'
if manifest.exists():
 for k,v in json.loads(manifest.read_text()).items():assert sha(R/k)==v,('FROZEN_CANDIDATE_CHANGED',k)
print(json.dumps({'R0_81_unchanged':len(frozen),'original_tests_and_fixtures_unchanged':len(immutable),'authorized_changed_files':changed,'audio_features_retained':48,'activity_historical_checks_retained':22,'activity_algorithm_rerun':False}))

native=json.loads((Path(config['E1'])/'entrypoints.json').read_text(encoding='utf-8-sig'))
assert all(native[k]==0 for k in ['play_exit','stop_exit','controller_exit','start_exit','idle_stop_exit']), 'NATIVE_ENTRYPOINT_FAILURE'
assert native['matched_before_stop'] and native['exact_pid_stopped'], 'NATIVE_STOP_NOT_VERIFIED'
for k,v in native['hashes'].items():assert sha(Path(config['E1'])/k)==v,('NATIVE_SCRIPT_CHANGED',k)
print('Native current script hashes and actual START/STOP/muted playback evidence PASS; audibility NOT_RUN')

known=set(base)|allowed
runtime=sum(allow['runtime_roots'].values(),[])
unlisted=[str(p.relative_to(R)) for p in R.rglob('*') if p.is_file() and str(p.relative_to(R)) not in known and not any(p.is_relative_to(R/d) for d in runtime)]
assert not unlisted,('UNLISTED_NEW_FILE',unlisted)
print('All new files accounted for by exact file allowlist or preregistered runtime directories')
