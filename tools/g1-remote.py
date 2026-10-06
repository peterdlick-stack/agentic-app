"""Drive the existing OctoSense remote bridge; retain real framebuffer evidence."""
import base64
import json
from pathlib import Path
import sys
import time
import runpy
from urllib.parse import urlencode
from urllib.request import urlopen

root = Path('/mnt/f/context-dj-work/evidence/G1-ai')
runpy.run_path('/mnt/f/context-dj-work/repo/tools/disk-guard.py', run_name='__main__')
op, name, *args = sys.argv[1:]
if not name.replace('-', '').replace('_', '').isalnum():
    raise SystemExit('Invalid evidence name')
if any((root / (name + suffix)).exists() for suffix in ('-action.json', '-snap.json', '.png')):
    raise SystemExit('Evidence exists; choose a new name before any UI action')
params = {'wait': '1'}
route = op
if op == 'key':
    route = 'k'
    params.update(k='press', c=args[0])
elif op == 'click':
    params.update(x=args[0], y=args[1])
elif op == 'type':
    route = 't'
    params['t'] = base64.b64decode(args[0]).decode('utf-8')
elif op == 'scroll':
    route = 'm'
    params.update(k='scroll', x=args[0], y=args[1], dy=args[2])
elif op == 'keys':
    for code in args:
        with urlopen('http://127.0.0.1:8399/k?' + urlencode({'k': 'press', 'c': code, 'wait': '1'}), timeout=15) as r:
            print(r.read().decode())
    route = 'snap'
    params = {}
elif op == 'observe':
    route = 'snap'
    params = {}
elif op == 'wait':
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        with urlopen('http://127.0.0.1:8399/snap', timeout=10) as r:
            pending = json.load(r)
        plans = [e.get('t', '') for e in pending.get('s', []) if e.get('i') == 'plan']
        if plans and not any('AI 正在' in t for t in plans):
            break
        time.sleep(3)
    route = 'snap'
    params = {}
else:
    raise SystemExit('Unsupported operation')
with urlopen('http://127.0.0.1:8399/' + route + '?' + urlencode(params), timeout=20) as r:
    response = r.read()
(root / (name + '-action.json')).write_bytes(response)
if op != 'observe':
    print(response.decode()[:1000])
time.sleep(0.5)
with urlopen('http://127.0.0.1:8399/snap', timeout=10) as r:
    data = r.read()
(root / (name + '-snap.json')).write_bytes(data)
for item in json.loads(data).get('s', []):
    if (item.get('ty') == 'TextInput' or item.get('i') in ('plan', 'ctx_act', 'ctx_why')
            or (item.get('ty') in ('Label', 'Button') and item.get('r', [0, 0])[1] >= 600)):
        print(json.dumps(item, ensure_ascii=False))
frame = root / 'live-framebuffer.png'
for _ in range(10):
    try:
        before = frame.stat()
        body = frame.read_bytes()
        if body.startswith(b'\x89PNG\r\n\x1a\n') and before.st_size == len(body):
            (root / (name + '.png')).write_bytes(body)
            print('FRAME', name + '.png', 'mtime', before.st_mtime)
            break
    except OSError:
        pass
    time.sleep(0.2)
else:
    raise RuntimeError('Framebuffer was not stable')
