"""Existing Windows Python stdlib inventory transport; estimator unchanged."""
import hashlib,json,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
LIB=Path('F:/context-player-cache-20261004/library')
began=time.monotonic()
partial=ROOT/'native_inventory_checkpoint.json'
rows=json.loads(partial.read_text()) if partial.exists() else []
known={r['path']:r for r in rows}
for p in sorted(LIB.glob('*.wav')):
    key='/mnt/f/context-player-cache-20261004/library/'+p.name
    stat=p.stat()
    old=known.get(key)
    if old and old.get('mtime_ns')==stat.st_mtime_ns and old['bytes']==stat.st_size: continue
    if time.monotonic()-began>1700: raise SystemExit(2)
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''): h.update(block)
    known[key]=dict(path=key,content_id='sha256:'+h.hexdigest(),bytes=stat.st_size,mtime_ns=stat.st_mtime_ns)
    temp=partial.with_suffix('.tmp')
    temp.write_text(json.dumps(list(known.values()),indent=2))
    temp.replace(partial)
rows=sorted(known.values(),key=lambda r:r['content_id'])
(ROOT/'manifest_all_wav.json').write_text(json.dumps(rows,indent=2))
catalog=json.loads((LIB/'catalog.json').read_text(encoding='utf-8'))
catalog_by_name={Path(t['path']).name:t for t in catalog}
extra=[r for r in rows if Path(r['path']).name not in catalog_by_name]
rows=[r for r in rows if Path(r['path']).name in catalog_by_name]
mismatch=[r['path'] for r in rows if r['content_id']!='sha256:'+catalog_by_name[Path(r['path']).name]['sha256']]
missing=sorted(set(catalog_by_name)-{Path(r['path']).name for r in rows})
(ROOT/'catalog_hash_check.json').write_text(json.dumps(dict(catalog_entries=len(catalog),matched=len(rows)-len(mismatch),mismatch=mismatch,missing=missing,orphan_wavs=extra,policy='catalog members only; orphan preserved read-only'),indent=2))
if mismatch or missing: raise SystemExit(3)
(ROOT/'manifest.json').write_text(json.dumps(rows,indent=2))
(ROOT/'native_inventory_exit.json').write_text(json.dumps(dict(exit_code=0,elapsed_seconds=time.monotonic()-began,count=len(rows),bytes=sum(r['bytes'] for r in rows)),indent=2))
print('inventory complete',len(rows),time.monotonic()-began)
