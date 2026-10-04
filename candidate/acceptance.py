"""Repair acceptance: current subprocess evidence for every live gate."""
import hashlib,json,sys,time,uuid,os,importlib.util
from pathlib import Path
R=Path(__file__).resolve().parent
from launcher import run

def full():
 start=time.time();folder=R/'eval/runs'/('acceptance-'+uuid.uuid4().hex);folder.mkdir(parents=True)
 os.environ['IMPORT_AUDIT_PATH']=str(folder/'imports.jsonl');checks=[]
 def command(name,args,cwd=R):
  t=time.time();cmd=['python3','-B',*args];o=run(cmd,cwd);(folder/(name+'.log')).write_text(o.stdout)
  checks.append({'name':name,'command':cmd,'cwd':str(cwd),'start_epoch':t,'end_epoch':time.time(),'exit_code':o.returncode,'log':str(folder/(name+'.log'))});return o
 spec=importlib.util.spec_from_file_location('original_runner',R/'eval/run-original34.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
 x=mod.execute(folder/'original34');checks.append({'name':'original34','exit_code':0 if x['passed'] else 1,'actual_subprocess_exit':x['exit_code'],'result':str(folder/'original34/original34.json')})
 command('learner',['-m','unittest','learner.test_model','-v'])
 command('audio',['-m','unittest','discover','-s',str(R/'audio'),'-p','test_extract.py','-v'],R/'audio')
 command('metrics',[str(R/'eval/test_metrics.py')])
 command('protocol',[str(R/'eval/test_protocol.py')])
 command('resources',[str(R/'repair-A/test_resources.py')])
 command('controls',[str(R/'run_controls.py')])
 command('activity-denominators',[str(R/'learner/review_c_check.py')])
 command('integration',[str(R/'eval/smoke.py')])
 command('guard',[str(R/'launcher.py'),'guard'])
 command('environment-probes',[str(R/'repair-A/probe.py')])
 command('artifacts',[str(R/'eval/artifact_checks.py')])
 result={'version':'repair-v2','run_id':folder.name,'start_epoch':start,'end_epoch':time.time(),'checks':checks,'engineering':'ENGINEERING_REPAIRED' if all(c['exit_code']==0 for c in checks) else 'ENGINEERING_BLOCKED','features':'FEATURES_ESTIMATED','activity':'ACCURACY_UNVERIFIED','benefit':'NO_USER_BENEFIT_EVIDENCE','jev':'JEV_NOT_RUN','research':'AWAITING_USER_EVIDENCE','activity_replay':'NOT_RUN_UNCHANGED_RESULTS_HASH_VERIFIED','no_overall_research_pass':True}
 (folder/'acceptance.json').write_text(json.dumps(result,indent=2));(R/'eval/acceptance.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2));return int(result['engineering']!='ENGINEERING_REPAIRED')
if __name__=='__main__':sys.exit(full())
