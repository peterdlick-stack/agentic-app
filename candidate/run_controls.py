import json,sys
from pathlib import Path
R=Path(__file__).resolve().parent
from launcher import run
controls=[]
for control in ('corrupt_audio','missing_feature','duplicate_feedback','expired_context','future_label'):
 runs=[]
 for phase,broken in [('good',False),('broken',True),('restored',False)]:
  cmd=['python3','-B',str(R/'eval/negative_controls.py'),control]+(['--broken'] if broken else [])
  out=run(cmd);runs.append({'phase':phase,'exit_code':out.returncode,'output':out.stdout})
 controls.append({'control':control,'runs':runs,'detected_and_restored':[x['exit_code'] for x in runs]==[0,1,0]})
(R/'eval/negative-red-green.json').write_text(json.dumps(controls,indent=2))
print(json.dumps([{k:v for k,v in c.items() if k!='runs'} for c in controls]))
sys.exit(0 if all(c['detected_and_restored'] for c in controls) else 1)
