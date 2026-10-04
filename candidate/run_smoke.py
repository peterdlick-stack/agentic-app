import json,sys
from pathlib import Path
R=Path(__file__).resolve().parent
from launcher import run
out=run(['python3','-B',str(R/'eval/smoke.py')])
(R/'eval/smoke.log').write_text(out.stdout);print(out.stdout);sys.exit(out.returncode)
