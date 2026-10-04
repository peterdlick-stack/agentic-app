"""Always execute immutable original tests; never reuse historical exit status."""
import os,sys,json,time,hashlib,re,uuid
from pathlib import Path
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R))
from launcher import run

def execute(outdir):
 outdir=Path(outdir);outdir.mkdir(parents=True,exist_ok=True)
 audit=outdir/'imports.jsonl';os.environ['IMPORT_AUDIT_PATH']=str(audit)
 cmd=['python3','-B','-m','unittest','discover','-s','context_player/tests','-p','test_*.py','-v']
 start=time.time();res=run(cmd,R/'integration');end=time.time()
 (outdir/'original34.log').write_text(res.stdout)
 imports=[json.loads(x) for x in audit.read_text().splitlines()] if audit.exists() else []
 expected={str(R/'integration/context_player'/n):hashlib.sha256((R/'integration/context_player'/n).read_bytes()).hexdigest() for n in ['backend.py','feedback.py']}
 import_ok=bool(imports) and all(x['path'] in expected and x['sha256']==expected[x['path']] for x in imports)
 bypid={}
 for x in imports:bypid.setdefault(x['pid'],set()).add(x['module'])
 parent_and_child=sum({'context_player.backend','context_player.feedback'}<=v for v in bypid.values())>=2
 count=re.search(r'Ran (\d+) tests',res.stdout)
 good=res.returncode==0 and count and int(count[1])==34 and '\nOK\n' in res.stdout and 'skipped=' not in res.stdout and import_ok and parent_and_child
 result={'command':cmd,'cwd':str(R/'integration'),'start_epoch':start,'end_epoch':end,'exit_code':res.returncode,'tests':int(count[1]) if count else None,'zero_skips':'skipped=' not in res.stdout,'imports':imports,'source_hashes':expected,'import_ok':import_ok,'parent_and_child_verified':parent_and_child,'passed':bool(good),'log':str(outdir/'original34.log')}
 (outdir/'original34.json').write_text(json.dumps(result,indent=2));return result
if __name__=='__main__':
 p=R/'eval/runs'/('original34-'+uuid.uuid4().hex);x=execute(p);print(json.dumps(x,indent=2));sys.exit(0 if x['passed'] else 1)
