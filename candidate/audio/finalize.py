"""Record branch source/input versions and unmeasured accuracy without invented truth."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def hash_file(p): return hashlib.sha256(p.read_bytes()).hexdigest()
manifest=json.loads((ROOT/'manifest.json').read_text())
features=json.loads((ROOT/'features.json').read_text())
splits={}
for row in manifest:
    cid=row['content_id']; bucket=int(hashlib.sha256((cid+'|20261004').encode()).hexdigest(),16)%10
    splits[cid]='sealed' if bucket<2 else 'validation' if bucket==2 else 'development'
(ROOT/'splits.json').write_text(json.dumps(splits,indent=2))
metrics=dict(status='FEATURES_ESTIMATED',independent_sealed_truth_songs=0,bpm_all_truth_hit_rate=None,
    bpm_valid_estimate_mae=None,bpm_conditional_hit_rate=None,bpm_half_double_error_rate=None,
    bpm_truth_coverage=None,vocal_precision=None,vocal_recall=None,vocal_f1=None,
    extracted_unique=len(features),bpm_extraction_coverage=sum(r['features']['bpm']['value'] is not None for r in features)/len(features),
    vocals_unknown=sum(r['features']['vocal']['value'] is None for r in features),
    accuracy_gate='NOT_RUN',hard_bpm_constraints_enabled=False,
    reason='No independently verified music truth labels available; mechanism fixtures are not accuracy evidence.')
(ROOT/'accuracy.json').write_text(json.dumps(metrics,indent=2))
versions={p.name:hash_file(p) for p in ROOT.glob('*.py')}
versions.update({name:hash_file(ROOT/name) for name in ('manifest.json','features.json','splits.json','accuracy.json')})
(ROOT/'versions.json').write_text(json.dumps(versions,indent=2))
print(json.dumps(metrics))
