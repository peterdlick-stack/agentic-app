import unittest,copy,math,json,pathlib,tempfile,hashlib,dataclasses
import activity
from activity import Sample,predict,project,timeline,NS
S=9007199254740993
def samples(seconds=9,walking=False):
 return tuple(Sample(st,S+i*40_000_000,S+i*40_000_000,S+i*40_000_000,(0.,0.,9.81+math.sin(i*.04*2*math.pi*1.5) if walking and st==1 else (9.81 if st==1 else 0.)),True,3) for i in range(seconds*25) for st in (1,4))
class ActivityTests(unittest.TestCase):
 def test_stationary_walking_unknown_are_functional_not_real_accuracy(self):
  self.assertEqual(predict(samples(),S,S+4*NS)['result'],'stationary')
  self.assertEqual(predict(samples(walking=True),S,S+4*NS)['result'],'walking')
  self.assertEqual(predict(samples(),S,S+NS)['result'],'unknown')
 def test_future_mutation_and_arrival_causality(self):
  original=samples();at=S+4*NS
  changed=tuple(dataclasses.replace(x,values=(100.,100.,100.)) if x.timestamp>at else x for x in original)
  self.assertEqual(predict(original,S,at),predict(changed,S,at))
  delayed=tuple(dataclasses.replace(x,received=at+NS,available=at+NS) for x in original)
  self.assertEqual(predict(delayed,S,at)['result'],'unknown')
 def test_large_integer_boundary(self):
  r=predict(samples(),S,S+4*NS);self.assertEqual(r['window_start_ns'],str(S));self.assertEqual(r['window_end_ns'],str(S+4*NS))
  self.assertEqual(predict(samples(),S,S+4*NS-1)['result'],'unknown')
 def test_missing_invalid_gap_accuracy_delay(self):
  base=samples()
  cases=[(),tuple(x for x in base if x.sensor==1),tuple(x for x in base if not S+NS<x.timestamp<S+3*NS),tuple(dataclasses.replace(x,valid=False,values=(None,0,0)) for x in base),tuple(dataclasses.replace(x,accuracy=0) for x in base),tuple(dataclasses.replace(x,received=x.timestamp+300_000_000,available=x.timestamp+300_000_000) for x in base)]
  for case in cases:
   with self.subTest(case=len(case)):self.assertEqual(predict(case,S,S+4*NS)['result'],'unknown')
 def test_projection_no_label_placement_identity_or_filename(self):
  rows=[dict(type='sensor_sample',sensor_type=x.sensor,sensor_timestamp_ns=str(x.timestamp),record_elapsed_ns=str(x.available),received_elapsed_ns=str(x.received),values=x.values,value_state='valid',accuracy=3) for x in samples()]
  changed=copy.deepcopy(rows)
  for r in changed:r.update(activity='running',placement='pocket',session_id='answer',filename='walking.jsonl')
  changed.insert(0,dict(type='manual_label',activity='walking',placement='desk'))
  self.assertEqual(project(rows),project(changed));self.assertEqual(predict(project(rows),S,S+4*NS),predict(project(changed),S,S+4*NS))
 def test_repeat_deterministic_and_human_unknown(self):
  a=predict(samples(),S,S+4*NS);self.assertEqual(a,predict(samples(),S,S+4*NS));self.assertEqual(a['human_activity'],'unknown')
 def test_order_independence(self):self.assertEqual(predict(samples(),S,S+4*NS),predict(tuple(reversed(samples())),S,S+4*NS))
if __name__=='__main__':unittest.main(verbosity=2)
