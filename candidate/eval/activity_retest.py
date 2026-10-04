"""Re-execute frozen activity implementation; redirect only its output sink to eval."""
import importlib.util,json,sys
from pathlib import Path
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'activity'))
spec=importlib.util.spec_from_file_location('frozen_activity_run',R/'activity/run.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
out=R/'eval/activity-retest';out.mkdir(exist_ok=True)
def save(name,obj):
 (out/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False))
module.save=save
module.main()
