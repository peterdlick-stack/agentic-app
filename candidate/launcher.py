"""Child-only isolation: keep HOME, pin candidate imports, native temporary root."""
import os, sys, subprocess, json
from pathlib import Path
R=Path(__file__).resolve().parent
E=Path('/mnt/f/context-recommend-repair-20261004-180749')
def run(cmd,cwd=None,interactive=False):
    env=os.environ.copy()
    temp=R/'tmp/launcher';temp.mkdir(parents=True,exist_ok=True)
    for k in ('TMPDIR','TMP','TEMP','XDG_CACHE_HOME','XDG_STATE_HOME','XDG_CONFIG_HOME'):
        env[k]=str(temp)
    env.update(PYTHONDONTWRITEBYTECODE='1',ISOLATION_ROOT=str(R),ISOLATION_EVIDENCE_ROOT=str(E),
               CANDIDATE_IMPORT_ROOT=str(R/'integration'),IMPORT_AUDIT_PATH=env.get('IMPORT_AUDIT_PATH',str(R/'repair-A/imports.jsonl')),
               PYTHONPATH=os.pathsep.join([str(R/'guard'),str(R/'integration'),str(R)]))
    if interactive:
        return subprocess.run(cmd,cwd=cwd or R,env=env,text=True,timeout=1800)
    return subprocess.run(cmd,cwd=cwd or R,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=1800)
if __name__=='__main__':
    if sys.argv[1]=='guard':
        good=run(['python3','-B','-c',"import tempfile; from pathlib import Path; p=Path(tempfile.mktemp());p.write_text('fixture');print(p)"])
        bad=run(['python3','-B','-c',"from pathlib import Path;Path('/tmp/context-recommend-forbidden').write_text('bad')"])
        result={'good_exit':good.returncode,'bad_exit':bad.returncode,'good':good.stdout,'bad':bad.stdout,'detected':'WRITE_OUTSIDE_R' in bad.stdout}
        (R/'eval/guard.json').write_text(json.dumps(result,indent=2));print(json.dumps(result));sys.exit(0 if good.returncode==0 and bad.returncode!=0 and result['detected'] else 1)
