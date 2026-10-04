"""Bounded branch launcher with captured real process return code."""
import json, os, subprocess, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
mode=sys.argv[1] if len(sys.argv)>1 else 'test'
if mode not in ('test','pilot','all'): raise SystemExit('mode: test | pilot | all')
env=os.environ.copy()
for key in ('TMPDIR','TMP','TEMP','HOME','XDG_CACHE_HOME','XDG_STATE_HOME','XDG_CONFIG_HOME'):
    dest=ROOT/'tmp'/key; dest.mkdir(parents=True,exist_ok=True); env[key]=str(dest)
env['PYTHONDONTWRITEBYTECODE']='1'
env['PYTHONPATH']=str(ROOT.parent/'guard')+':'+str(ROOT)+':/home/fanzhou/.local/lib/python3.12/site-packages'
env['ISOLATION_ROOT']=str(ROOT)
cmd=[sys.executable,'-B','-m','unittest','-v','test_extract'] if mode=='test' else [sys.executable,'-B',str(ROOT/'extract.py'),'--library','/mnt/f/context-player-cache-20261004/library']+(['--pilot'] if mode=='pilot' else [])
began=time.monotonic()
try:
    result=subprocess.run(cmd,cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=1790)
    code=result.returncode; output=result.stdout
except subprocess.TimeoutExpired as e:
    code=124; output=str(e.stdout or '')+'\nTIMEOUT: completed feature rows are checkpointed.'
(ROOT/(mode+'.log')).write_text(output,encoding='utf-8')
(ROOT/(mode+'_exit.json')).write_text(json.dumps(dict(command=cmd,exit_code=code,elapsed_seconds=time.monotonic()-began,isolated_root=str(ROOT)),indent=2),encoding='utf-8')
print(output); raise SystemExit(code)
