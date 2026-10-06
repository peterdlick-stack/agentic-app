"""Three bounded curl requests; run once on Windows and once in WSL."""
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

WINDOWS = os.name == 'nt'
ROOT = Path('F:/context-dj-work' if WINDOWS else '/mnt/f/context-dj-work')
OUT = ROOT/'evidence/G3-net'
platform = 'windows' if WINDOWS else 'wsl'
deadline = dt.datetime.fromisoformat(json.loads((OUT/'timer.json').read_text(encoding='utf-8-sig'))['deadline'])
baseline = json.loads((ROOT/'evidence/G0-disk/recovery-baseline.json').read_text(encoding='utf-8-sig'))
initial = next(d['Free'] for d in baseline['drives'] if d['Name']=='C')
ua = 'ContextDJ/0.3 ( https://github.com/peterdlick-stack/agentic-app )'
queries = [
    ('open-meteo','https://api.open-meteo.com/v1/forecast?latitude=31.82&longitude=117.23&current=temperature_2m'),
    ('musicbrainz-zh','https://musicbrainz.org/ws/2/recording?query=recording:%22%E6%99%B4%E5%A4%A9%22%20AND%20artist:%22%E5%91%A8%E6%9D%B0%E4%BC%A6%22&fmt=json&limit=1'),
    ('musicbrainz-en','https://musicbrainz.org/ws/2/recording?query=recording:%22Blinding%20Lights%22%20AND%20artist:%22The%20Weeknd%22&fmt=json&limit=1'),
]
curl = 'curl.exe' if WINDOWS else 'curl'
(OUT/(platform+'-curl-version.txt')).write_bytes(subprocess.check_output([curl,'--version']))
results=[]
for label,url in queries:
    if dt.datetime.now().astimezone() >= deadline:
        raise SystemExit('G3 30-minute deadline reached')
    free = shutil.disk_usage('C:/' if WINDOWS else '/mnt/c').free
    if free < 5*1024**3 or initial-free > 1024**3:
        raise SystemExit(f'STOP_DISK C_free={free} decrease={initial-free}')
    prefix=OUT/(platform+'-'+label)
    body_path=prefix.with_suffix('.body.txt')
    if body_path.exists():
        raise SystemExit('Evidence exists; choose a new run explicitly')
    started=dt.datetime.now().astimezone().isoformat()
    cmd=[curl,'--silent','--show-error','--connect-timeout','10','--max-time','30','--user-agent',ua,'--output',str(body_path),'--write-out','%{http_code}\n%{time_total}\n%{time_connect}\n%{time_starttransfer}\n',url]
    p=subprocess.run(cmd,capture_output=True,timeout=40)
    prefix.with_suffix('.metrics.txt').write_bytes(p.stdout)
    prefix.with_suffix('.stderr.txt').write_bytes(p.stderr)
    metrics=p.stdout.decode('utf-8','replace').splitlines()
    body=body_path.read_text(encoding='utf-8',errors='replace') if body_path.exists() else ''
    row={'platform':platform,'test':label,'started':started,'url':url,'user_agent':ua,'exit_code':p.returncode,'http_code':metrics[0] if metrics else None,'total_seconds':metrics[1] if len(metrics)>1 else None,'first_500_characters':body[:500],'stderr':p.stderr.decode('utf-8','replace')}
    if label.startswith('musicbrainz'):
        try:
            obj=json.loads(body)
            records=obj.get('recordings',[])
            row['recording_count_returned']=len(records)
            row['recordings']=[{'title':r.get('title'),'id':r.get('id'),'length_present':'length' in r,'length':r.get('length'),'releases_present':'releases' in r,'release_count':len(r.get('releases',[])),'release_dates':[release.get('date') for release in r.get('releases',[])],'date_present':any('date' in release for release in r.get('releases',[]))} for r in records]
        except (ValueError,TypeError,AttributeError):
            row['recordings']='UNKNOWN: no valid MusicBrainz JSON'
    results.append(row)
    (OUT/(platform+'-results.json')).write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:row[k] for k in ('platform','test','exit_code','http_code','total_seconds')},ensure_ascii=False),flush=True)
    time.sleep(1.1)
