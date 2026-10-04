import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from learner.model import digest,predict_before_update
p=dict(policy='P0',predicted_at=200,tracks=[dict(content_id='sha256:'+'a'*64)])
bundle=dict(events=[],exposures=[],sessions=[],snapshots=[dict(snapshot_id='future',snapshot=p,snapshot_hash=digest(p),created_at=200)])
try:
    predict_before_update([],[],{}, {},bundle,100)
except ValueError as e:
    print('REPRODUCED prefix prediction rejects retained future metadata:',e)
else:
    print('RESOLVED prefix prediction excludes future metadata')
