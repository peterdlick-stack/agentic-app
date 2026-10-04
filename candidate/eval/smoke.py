import json,sys,time,uuid
from pathlib import Path
R=Path(__file__).resolve().parents[1];sys.path[:0]=[str(R),str(R/'integration')]
import context_player
from integration.compare import select
from learner.store import EvidenceStore
from learner.model import digest
state=R/'eval/integration-smoke'/str(uuid.uuid4())
results=[]
for policy in ('P0','P1','P2'):
 p=select(policy,'walking',limit=1,state=state);assert len(p['tracks'])==1
 if policy=='P1':assert p['effective_policy']=='P1' and p['status']=='OK'
 if policy=='P2':assert p['effective_policy']=='P0' and p['status']=='UNTRAINED'
 results.append({'requested':policy,'effective':p['effective_policy'],'status':p['status'],'content_id':p['tracks'][0]['content_id']})
 if policy=='P0':
  s=EvidenceStore(state/policy);eid=str(uuid.uuid4());session='synthetic-smoke';at=time.time();t=p['tracks'][0]
  s.expose(eid,p['snapshot_id'],t['content_id'],session,at)
  e=dict(event_id=str(uuid.uuid4()),session_id=session,exposure_id=eid,snapshot_id=p['snapshot_id'],content_id=t['content_id'],policy=p['policy'],context=p['context'],feature_version=p['feature_version'],target='scenario_acceptance',value=1,exposed_at=at,recorded_at=time.time(),provenance='synthetic',snapshot=p)
  s.record(e);before=digest(s.export());s.close();s=EvidenceStore(state/policy);assert digest(s.export())==before;assert s.record(e)['duplicate'];s.close()
x=select('P1','walking','90-110 bpm',1,state);assert not x['tracks']
result={'status':'PASS','actual_import':context_player.__file__,'policies':results,'feedback_restart':'synthetic_only_pass','hard_bpm_unknown_excluded':True,'state':str(state),'audio_audibility':'NOT_RUN'}
assert str(R) in context_player.__file__
(R/'eval/integration-smoke.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))

