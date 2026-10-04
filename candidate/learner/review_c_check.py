import json, pathlib, sys, hashlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'activity'))
from reference_eval import metrics
for name in ['baseline','candidate']:
    rows=json.loads((ROOT/'activity'/f'{name}-scored.json').read_text())
    report=json.loads((ROOT/'activity/report.json').read_text())
    m=metrics(rows)
    assert m['eligible_windows']==62
    assert m['confusion_matrix']==report['results'][name]['overall']['confusion_matrix']
    assert m['per_class']['walking']['recall']==report['results'][name]['overall']['per_class']['walking']['recall']
    print(name,json.dumps(m['confusion_matrix']), 'walking recall',m['per_class']['walking']['recall'])
assert report['baseline_retained'] is True and report['independent_test_sessions']==0
print('C read-only metric recomputation PASS; no files written in activity')
