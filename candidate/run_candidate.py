import sys,subprocess,os
from pathlib import Path
from launcher import run
R=Path(__file__).resolve().parent
if '--interactive' in sys.argv:
    # Launcher supplies guarded child environment; interactive stdio is inherited.
    import launcher
    result=launcher.run(['python3','-B',str(R/'integration/compare.py'),'--interactive'],interactive=True)
    sys.exit(result.returncode)
result=run(['python3','-B',str(R/'eval/run-original34.py')]);print(result.stdout);sys.exit(result.returncode)
