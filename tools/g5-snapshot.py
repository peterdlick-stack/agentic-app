"""Copy only labels/history after real usage begins; never change app data."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import runpy

ROOT = Path('F:/context-dj-work' if os.name == 'nt' else '/mnt/f/context-dj-work')
FIRST_DAY = dt.date(2026, 10, 6)


def snapshot(source, output_root, today, confirmed, check=False):
    if today < FIRST_DAY:
        return {'status':'NOT_STARTED_BY_DATE','first_day':str(FIRST_DAY)}
    if not confirmed:
        return {'status':'AWAITING_REAL_USAGE_CONFIRMATION'}
    source=source.resolve(strict=True)
    names=('labels.json','history.json')
    missing=[name for name in names if not (source/name).is_file()]
    if missing:
        return {'status':'SOURCE_INCOMPLETE','missing':missing}
    bodies={name:(source/name).read_bytes() for name in names}
    values={name:json.loads(body.decode('utf-8-sig')) for name,body in bodies.items()}
    if not all(isinstance(value,list) for value in values.values()):
        raise ValueError('Expected JSON arrays; no inferred count or conversion')
    if any((source/name).read_bytes()!=body for name,body in bodies.items()):
        raise RuntimeError('Source changed during capture; no snapshot written')
    counts={name:len(value) for name,value in values.items()}
    if check:
        return {'status':'READY_CHECK_ONLY','counts':counts}
    target=output_root/str(today)
    if target.exists():
        return {'status':'EXISTS_NO_OVERWRITE','path':str(target)}
    target.mkdir(parents=True,exist_ok=False)
    for name,body in bodies.items():
        with (target/name).open('xb') as f:
            f.write(body)
        if (target/name).read_bytes()!=body:
            raise RuntimeError('Copy verification failed; partial evidence retained')
    lines=[f'snapshot_date={today}',f'captured_at={dt.datetime.now().astimezone().isoformat()}',f'source={source}',
           'real_usage_started=confirmed_by_caller',
           'counts_are_raw_array_totals_not_daily_new_or_individually_verified_real_entries']
    for name,body in bodies.items():
        lines += [f'{name}.count={counts[name]}',f'{name}.sha256={hashlib.sha256(body).hexdigest()}']
    with (target/'count.txt').open('x',encoding='utf-8') as f:
        f.write('\n'.join(lines)+'\n')
    return {'status':'COPIED_AND_BYTE_VERIFIED','path':str(target),'counts':counts}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True,help='Explicit accounts/device directory; no recursive discovery')
    parser.add_argument('--real-use-confirmed',action='store_true',help='Only after the human confirms actual use has begun')
    parser.add_argument('--check',action='store_true',help='Validate without writing a snapshot')
    args=parser.parse_args()
    runpy.run_path(str(ROOT/'repo/tools/disk-guard.py'),run_name='__main__')
    today=dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date()
    print(json.dumps(snapshot(args.source,ROOT/'evidence/G5-usage',today,args.real_use_confirmed,args.check),ensure_ascii=False))
