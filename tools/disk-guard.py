"""Read-only disk gate for this task, on Windows or WSL."""
import os
import json
from pathlib import Path
import shutil
import sys

root = Path('F:/context-dj-work' if os.name == 'nt' else '/mnt/f/context-dj-work')
recovery = root / 'evidence/G0-disk/recovery-baseline.json'
baseline_path = recovery if recovery.exists() else root / 'evidence/G0-disk/disk.txt'
baseline = json.loads(baseline_path.read_text(encoding='utf-8-sig'))
initial = next(d['Free'] for d in baseline['drives'] if d['Name'] == 'C')
current = shutil.disk_usage('C:/' if os.name == 'nt' else '/mnt/c').free
if current < 5 * 1024**3 or initial - current > 1024**3:
    print(f'STOP_DISK: C_free={current}, C_baseline={initial}, decrease={initial-current}', file=sys.stderr)
    sys.exit(2)
if (root / 'evidence/G1-ai/STOP-disk-state.json').exists() and not recovery.exists():
    print('STOP_DISK: recorded incident requires human review before resuming.', file=sys.stderr)
    sys.exit(2)
