import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from metrics import bpm_metrics,pilot_metrics,freeze_sample_size,schedule
class MetricsTests(unittest.TestCase):
 def test_null_denominator(self):
  m=bpm_metrics([dict(split='sealed',truth_source='independent human',truth_bpm=100,bpm=100),dict(split='sealed',truth_source='independent human',truth_bpm=100,bpm=None)])
  self.assertEqual(m['hit_rate'],.5);self.assertEqual(m['coverage'],.5);self.assertEqual(m['mae'],0);self.assertEqual(m['status'],'FEATURES_ESTIMATED')
 def test_no_data_no_pass(self):
  self.assertEqual(pilot_metrics([],{'status':'FROZEN','sessions':1})['status'],'NO_USER_BENEFIT_EVIDENCE');self.assertEqual(freeze_sample_size([])['status'],'SAMPLE_SIZE_BLOCKED')
 def test_synthetic_rejected(self):
  result=pilot_metrics([{'provenance':'synthetic'}],{})
  self.assertEqual(result['status'],'NO_USER_BENEFIT_EVIDENCE');self.assertIn('evidence_bundle_missing',result['reasons'])
 def test_balanced_order(self):
  x=schedule(6);self.assertEqual(len({tuple(r['policy_order']) for r in x}),6)
 def test_missing_worst_case(self):
  rows=[]
  for s in range(12):
   for p in ('P0','P1','P2'):
    for i in range(6):rows.append(dict(session_id=str(s),content_id=p+str(i),policy=p,effective_policy=p,provenance='real_user',accept=None if p=='P2' and i<2 else (1 if p=='P2' else 0),interruption=0))
  result=pilot_metrics(rows,{'status':'FROZEN','sessions':12})
  self.assertEqual(result['status'],'NO_USER_BENEFIT_EVIDENCE');self.assertGreater(result['conditions']['P2']['missing_rate'],.2)
if __name__=='__main__':unittest.main()
