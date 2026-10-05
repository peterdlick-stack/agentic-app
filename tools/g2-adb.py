"""Use an existing Windows adb, retaining task evidence only on F:. No builds."""
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path('F:/context-dj-work')
OUT = ROOT / 'evidence/G2-phone'
ADB = Path('C:/Users/admin/Downloads/Agentic Apps/context-sense-p40/.toolchain/sdk/platform-tools/adb.exe')
baseline = json.loads((ROOT/'evidence/G0-disk/recovery-baseline.json').read_text(encoding='utf-8-sig'))
initial = next(d['Free'] for d in baseline['drives'] if d['Name']=='C')
current = shutil.disk_usage('C:/').free
name, *args = sys.argv[1:]
if not name.replace('-', '').isalnum():
    raise SystemExit('Invalid evidence name')
if args != ['kill-server']:
    deadline = dt.datetime.fromisoformat(json.loads((OUT/'timer.json').read_text(encoding='utf-8-sig'))['deadline'])
    if dt.datetime.now().astimezone() >= deadline:
        raise SystemExit('G2 90-minute deadline reached')
    if current < 5*1024**3 or initial-current > 1024**3:
        raise SystemExit('STOP_DISK')
env = dict(os.environ)
tmp = ROOT/'tmp/g2'
tmp.mkdir(parents=True, exist_ok=True)
env.update(TMP=str(tmp), TEMP=str(tmp))
cmd = [str(ADB), '-P', '5038']
if args and args[0] not in ('devices','start-server','kill-server','version'):
    binding = json.loads((OUT/'device-binding.json').read_text(encoding='utf-8'))
    cmd += ['-s', binding['serial']]
cmd += args
meta = {'args':args,'port':5038,'started':dt.datetime.now().astimezone().isoformat()}
for suffix in ('.stdout','.stderr','.json'):
    if (OUT/(name+suffix)).exists():
        raise SystemExit('Evidence already exists')
with (OUT/(name+'.stdout')).open('xb') as stdout, (OUT/(name+'.stderr')).open('xb') as stderr:
    try:
        result = subprocess.run(cmd, stdout=stdout, stderr=stderr, env=env, timeout=55)
        meta['exit_code'] = result.returncode
    except subprocess.TimeoutExpired:
        meta['exit_code'] = None
        meta['status'] = 'TIMEOUT; inspect installed state before any retry'
(OUT/(name+'.json')).write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
if args == ['devices','-l']:
    lines = (OUT/(name+'.stdout')).read_text().splitlines()
    found=[line.split() for line in lines if len(line.split()) >= 2 and line.split()[1] == 'device']
    print(json.dumps({'connected_authorized_devices':len(found),'unauthorized':sum('unauthorized' in line for line in lines)}))
    if len(found)==1:
        dest=OUT/'device-binding.json'
        if not dest.exists():
            dest.write_text(json.dumps({'serial':found[0][0],'description':' '.join(found[0][1:])}),encoding='utf-8')
elif args[:2] == ['exec-out', 'screencap']:
    body = (OUT/(name+'.stdout')).read_bytes()
    if body.startswith(b'\x89PNG\r\n\x1a\n'):
        (OUT/(name+'.png')).write_bytes(body)
        print('Saved screenshot:',name+'.png')
else:
    print((OUT/(name+'.stdout')).read_text(encoding='utf-8',errors='replace')[:4000])
print(json.dumps(meta,ensure_ascii=False))
