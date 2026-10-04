import argparse,copy,hashlib,json,sys,wave
from pathlib import Path
R=Path(__file__).resolve().parents[1];sys.path[:0]=[str(R),str(R/'integration')]
from learner.test_model import bundle,features,CONTEXT,NOW
from learner.model import validate_features,effective_context
from learner.store import validate_bundle
from context_player.recommend import verify_track
p=argparse.ArgumentParser();p.add_argument('control');p.add_argument('--broken',action='store_true');a=p.parse_args()
if a.control=='corrupt_audio':
 root=R/'eval/control-fixtures';(root/'library').mkdir(parents=True,exist_ok=True);f=root/'library/control.wav'
 with wave.open(str(f),'wb') as w:w.setparams((1,2,8000,0,'NONE',''));w.writeframes(b'\x01\x00'*800)
 h=hashlib.sha256(f.read_bytes()).hexdigest()
 if a.broken:f.write_bytes(b'CORRUPT')
 verify_track(dict(catalog_root=str(root),path='library/control.wav',sha256=h))
elif a.control=='missing_feature':
 f=features()
 if a.broken:del f['features']['bpm']['source']
 validate_features([f])
elif a.control=='expired_context':
 effective_context(dict(CONTEXT,valid_until=999. if a.broken else 20000.),NOW,strict=True)
elif a.control in ('duplicate_feedback','future_label'):
 b,f=bundle(1)
 if a.broken and a.control=='duplicate_feedback':b['events'].append(dict(b['events'][0],event_id='another'))
 if a.broken and a.control=='future_label':b['events'][0]['recorded_at']=NOW+1
 validate_bundle(b,NOW)
else:raise ValueError('unknown_control')
print(a.control,'accepted')
