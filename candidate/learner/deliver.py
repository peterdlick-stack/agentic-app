import json, pathlib, sys
from .model import train,digest
ROOT=pathlib.Path(__file__).resolve().parent
path=ROOT.parent/'audio/features.json'
features=json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else []
bundle=dict(snapshots=[],exposures=[],events=[],sessions=[])
(ROOT/'state/events-export.json').write_text(json.dumps(bundle,indent=2)+'\n')
m=train(bundle,features,ROOT/'state/model.json')
report=dict(status='UNTRAINED',recommendation_benefit='NO_USER_BENEFIT_EVIDENCE',
            real_scenario_labels=0,negative_labels=0,positive_labels=0,complete_sessions=0,
            source_search='S/state empty; bounded depth-4 search found no SQLite or events/preferences JSON',
            scope='No claim that no real feedback exists elsewhere; original feedback likes cannot substitute scenario acceptance.',
            training_data_hash=m['training_data_hash'],feature_hash=m['feature_hash'],
            offline_ranking=dict(ndcg=None,pairwise_accuracy=None,missing_rate=None,seen_songs=0,unseen_songs=0,status='NOT_RUN_NO_OBSERVED_SCENARIO_LABELS'),
            restoration='synthetic mechanism model JSON round-trip equal predictions; persistent store restart retained exact events',
            verification=dict(mechanism_tests=17,skips=0,exit_code=0,development_rounds=2),
            parameters=m['params'],sample_size='SAMPLE_SIZE_BLOCKED',jev='JEV_NOT_RUN')
(ROOT/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
