"""Full acceptance damage/restore in a dedicated expendable copy only."""
import sys,json,uuid,shutil,time,hashlib
from pathlib import Path
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R))
from launcher import run

def main():
 destination=R/'tmp/destructive-copy'/uuid.uuid4().hex
 def ignore(path,names):
  p=Path(path)
  return [n for n in names if n=='__pycache__' or (p==R and n=='tmp') or (p==R/'eval' and n in ('runs','integration-smoke','control-fixtures','activity-retest')) or (p==R/'integration' and n=='state')]
 shutil.copytree(R,destination,ignore=ignore)
 target=destination/'integration/context_player/feedback.py';original=target.read_bytes()
 corrupted=original.replace(b'    def __init__(self, state_dir):',b'    def __init__(self, state_dir):\n        raise RuntimeError("INTENTIONAL_ENGINEERING_NEGATIVE_CONTROL")',1)
 assert corrupted!=original
 target.write_bytes(corrupted)
 records=[]
 for phase in ('broken','restored'):
  if phase=='restored':target.write_bytes(original)
  start=time.time();cmd=['python3','-B',str(destination/'verify.py')];o=run(cmd,destination)
  log=R/'eval/runs'/('full-'+phase+'-'+destination.name+'.log');log.write_text(o.stdout)
  receipt=json.loads((destination/'eval/acceptance.json').read_text())
  records.append({'phase':phase,'command':cmd,'start_epoch':start,'exit_code':o.returncode,'checks':receipt['checks'],'log':str(log)})
 result={'copy':str(destination),'changed_path':str(target),'restored_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'phases':records,'passed':[x['exit_code'] for x in records]==[1,0] and records[0]['checks'][0]['exit_code']==1 and records[1]['checks'][0]['exit_code']==0}
 (R/'ledger/engineering-red-green.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2));return 0 if result['passed'] else 1
if __name__=='__main__':sys.exit(main())
