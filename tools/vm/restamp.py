"""重新计算 bundle/manifest.json 的 bundle_blake3（与 tools/conf/stamp/verify_stamp.py 同一算法，按 git 暂存区字节算）。
用法（仓库根目录）：python3 tools/vm/restamp.py   → 会先 git add -A bundle，再改写 manifest 里的戳。
之后 git add bundle/manifest.json 并提交，再跑 verify_stamp.py 确认 PASS。需要 blake3（pip install --target <目录> blake3，
运行前 PYTHONPATH=<目录>）。"""
import json, subprocess, sys
from pathlib import Path
sys.path.insert(0, 'tools/conf/stamp')
from verify_stamp import archive_files, digest
subprocess.run(['git', 'add', '-A', 'bundle'], check=True)
tree = subprocess.check_output(['git', 'write-tree']).decode().strip()
d = digest(archive_files(Path('.').resolve(), tree))
p = 'bundle/manifest.json'
s = open(p, encoding='utf-8').read()
old = json.loads(s)['integrity']['bundle_blake3']
open(p, 'w', encoding='utf-8', newline='\n').write(s.replace(old, d))
print('stamp', old, '->', d)
