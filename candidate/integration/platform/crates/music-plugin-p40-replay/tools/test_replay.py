import unittest, tempfile, pathlib, json, sys, os, copy, importlib.util
HERE=pathlib.Path(__file__).parent
sys.path.insert(0,str(HERE))
from replay import replay, ReplayError
S=9007199254740993
def fixture():
    rows=[]
    def add(t,mono,**kw):
        rows.append(dict(schema_version=1,session_id='synthetic-session',source='test_fixture',seq=len(rows)+1,type=t,record_elapsed_ns=str(S+mono),**kw))
    add('session',0,event='start',utc_ms=0,elapsed_ns=str(S),timezone='UTC',duration_limit_ns='600000000000',requested_rate_hz=25,metadata=dict(app_version='synthetic-v1',model='fixture',api_level=29,os_release='test',os_incremental='test',capabilities=[]))
    add('manual_label',0,effective_elapsed_ns=str(S),activity='unknown',placement='unknown',label_role='self_reported_reference')
    add('manual_label',100_000_000,effective_elapsed_ns=str(S+100_000_000),activity='sitting',placement='desk',label_role='self_reported_reference')
    add('manual_label',100_000_000,effective_elapsed_ns=str(S+100_000_000),activity='walking',placement='hand',label_role='self_reported_reference')
    for st in (1,4):
        add('sensor_sample',500_000_000,sensor_type=st,unit='m/s²' if st==1 else 'rad/s',includes_gravity=st==1,coordinate_system='android_device_xyz_natural_orientation',requested_rate_hz=25,sensor_timestamp_ns=str(S+50_000_000),received_elapsed_ns=str(S+500_000_000),accuracy=3,values=[1.,2.,3.],invalid_components=[None]*3,value_state='valid')
    add('audio_devices',500_000_000,observed_elapsed_ns=str(S+500_000_000),state='read_failed',output_device_types=[],meaning='system_visible_available_outputs_not_active_route')
    add('session',1_000_000_000,event='end',state='stopped',reason='ui_stop',utc_ms=1000,elapsed_ns=str(S+1_000_000_000),timezone='UTC',sample_count=2)
    return rows
class SyntheticTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='p40-synthetic-');self.path=pathlib.Path(self.tmp.name)/'synthetic.jsonl';self.rows=fixture();self.write()
    def tearDown(self):self.tmp.cleanup()
    def write(self):self.path.write_text(''.join(json.dumps(x,allow_nan=False)+'\n' for x in self.rows))
    def call(self,t='0',**kw):return replay(dict(file=str(self.path),relative_seconds=t,**kw))
    def test_boundary_duplicate_unknown_and_delayed_samples(self):
        zero=self.call(); exact=self.call('0.1'); before=self.call('0.099999999')
        self.assertEqual(zero['self_reported']['activity'],'unknown')
        self.assertEqual(before['self_reported']['activity'],'unknown')
        self.assertEqual(exact['self_reported'],dict(activity='walking',placement='hand',label_role='self_reported_reference'))
        self.assertEqual(zero['sensors']['1']['aligned_samples'][0]['activity'],'unknown')
        self.assertEqual(zero['valid_range_elapsed_ns'][0],str(S))
        self.assertEqual(exact['query_interval_elapsed_ns'][0],str(S+100_000_000))
        self.assertEqual(self.call('0'),zero)
        self.assertEqual(self.call('0.1'),exact)
    def test_complete_is_not_continuous_and_read_failure_not_empty_available(self):
        r=self.call('0.5');self.assertEqual(r['file_integrity'],'COMPLETE');self.assertEqual(r['capture_continuity'],'ANOMALOUS')
        self.assertEqual(r['audio_observation']['state'],'read_failed');self.assertEqual(r['audio_observation']['output_device_types'],[])
    def test_initial_no_data_observation_is_preserved_without_false_gap(self):
        self.rows=fixture()
        for r in self.rows[4:7]:
            r['record_elapsed_ns']=str(S+150_000_000)
            if r['type']=='sensor_sample':r['received_elapsed_ns']=str(S+150_000_000)
            else:r['observed_elapsed_ns']=str(S+150_000_000)
        self.rows[-1]['elapsed_ns']=str(S+200_000_000);self.rows[-1]['record_elapsed_ns']=str(S+200_000_000)
        self.rows.insert(2,dict(schema_version=1,session_id='synthetic-session',source='test_fixture',seq=3,type='status',state='no_data',sensor_type=1,record_elapsed_ns=str(S)))
        for i,r in enumerate(self.rows):r['seq']=i+1
        self.write();r=self.call();self.assertEqual(r['capture_continuity'],'CONTIGUOUS_OBSERVED');self.assertEqual(r['quality_status_records'][0]['state'],'no_data')
    def test_bounds_precision_and_invalid_time(self):
        for t in ['-1','1','NaN','1e-1','0.0000000001',True]:
            with self.subTest(t=t),self.assertRaises(ReplayError):self.call(t)
        self.assertEqual(self.call('0.999999999')['query_interval_relative_ns'],['999999999','1000000000'])
    def test_corrupt_seq_session_values_and_duplicate_keys(self):
        for field,value in [('seq',1),('session_id','mixed-session'),('values',[None,2,3]),('sensor_type',True)]:
            with self.subTest(field=field):
                self.rows=fixture();self.rows[4][field]=value;self.write()
                with self.assertRaises(ReplayError):self.call()
        self.rows=fixture();self.write();self.path.write_text(self.path.read_text().replace('"seq": 1','"seq": 1, "seq": 1',1))
        with self.assertRaises(ReplayError):self.call()
    def test_truncated_prefix_explicit_unknown_end_and_no_extrapolation(self):
        self.rows=fixture()[:-1];self.write();self.path.write_bytes(self.path.read_bytes()+b'{bad')
        r=self.call('0.1');self.assertEqual(r['file_integrity'],'PREFIX_ONLY');self.assertFalse(r['actual_end_known']);self.assertEqual(r['tail_state'],'DAMAGED_TAIL')
        with self.assertRaises(ReplayError):self.call('0.6')
    def test_changed_file_hash_and_session_guard(self):
        old=self.call()['import']['sha256'];self.rows[3]['activity']='running';self.write()
        self.assertNotEqual(self.call()['import']['sha256'],old);self.assertEqual(self.call('0.1')['self_reported']['activity'],'running')
        with self.assertRaises(ReplayError):self.call(expected_sha256=old)
        with self.assertRaises(ReplayError):self.call(expected_session_id='wrong')
    def observed_prefix(self,recovery=False):
        self.rows=fixture()[:-1]
        for r in self.rows[4:7]:
            r['record_elapsed_ns']=str(S+150_000_000)
            if r['type']=='sensor_sample':r['received_elapsed_ns']=str(S+150_000_000)
            else:r['observed_elapsed_ns']=str(S+150_000_000)
        self.rows.append(dict(schema_version=1,session_id='synthetic-session',source='test_fixture',seq=len(self.rows)+1,type='status',record_elapsed_ns=str(S+5_000_000_000),state='recording'))
        if recovery:
            prefix_bytes=len(''.join(json.dumps(x,allow_nan=False)+'\n' for x in self.rows).encode())
            self.rows.append(dict(schema_version=1,session_id='synthetic-session',source='app_recovery',seq=len(self.rows)+1,type='status',record_elapsed_ns=str(S+5_000_000_000),state='interrupted',reason='synthetic',valid_end_elapsed_ns=str(S+5_000_000_000+1),recovery_observed_utc_ms=0,original_sha256='0'*64,original_bytes=prefix_bytes,valid_prefix_bytes=prefix_bytes,omitted_tail_bytes=0,end_time_known=False))
        self.write()
    def test_observed_prefix_trailing_gap_clean_truncated_and_recovered(self):
        for mode in ('clean','truncated','recovery'):
            with self.subTest(mode=mode):
                self.observed_prefix(mode=='recovery')
                if mode=='truncated':self.path.write_bytes(self.path.read_bytes()+b'{bad')
                r=self.call('2');self.assertFalse(r['actual_end_known']);self.assertEqual(r['capture_continuity'],'ANOMALOUS')
                self.assertEqual(len(r['sensors']['1']['window_gaps']),1);self.assertEqual(r['sensors']['1']['window_sample_count'],0)
                self.assertEqual(r['sensors']['1']['window_gaps'][0]['kind'],'observed_prefix_trailing')
    def test_recovery_byte_types_counts_and_record_boundary_are_strict(self):
        self.observed_prefix(True);self.assertEqual(self.call()['file_integrity'],'PREFIX_ONLY')
        for mutation in ('negative','float','bool','prefix_mismatch','record_shift'):
            with self.subTest(mutation=mutation):
                self.observed_prefix(True);r=self.rows[-1]
                if mutation=='negative':r.update(original_bytes=1,valid_prefix_bytes=-1,omitted_tail_bytes=2)
                elif mutation=='float':r['valid_prefix_bytes']=float(r['valid_prefix_bytes'])
                elif mutation=='bool':r.update(original_bytes=1,valid_prefix_bytes=True,omitted_tail_bytes=0)
                elif mutation=='prefix_mismatch':r['valid_prefix_bytes']+=1;r['original_bytes']+=1
                else:r['record_elapsed_ns']=str(S+5_000_000_100)
                self.write()
                with self.assertRaises(ReplayError):self.call()
    def test_audio_uses_observation_time_and_preserves_duplicates_and_empty(self):
        def audio(observed,record,state,types):return dict(schema_version=1,session_id='synthetic-session',source='test_fixture',seq=0,type='audio_devices',record_elapsed_ns=str(S+record),observed_elapsed_ns=str(S+observed),state=state,output_device_types=types,meaning='system_visible_available_outputs_not_active_route')
        self.rows=fixture()[:6]+[audio(100_000_000,650_000_000,'available',[3,3]),audio(10_000_000,700_000_000,'read_failed',[])]+fixture()[-1:]
        for i,r in enumerate(self.rows):r['seq']=i+1
        self.write();r=self.call('0.6');self.assertEqual(r['audio_observation']['state'],'available');self.assertEqual(r['audio_observation']['output_device_types'],[3,3])
        self.assertEqual(self.call('0')['audio_observation']['state'],'not_observed');self.assertIsNone(self.call('0')['audio_observation']['output_device_types'])
        self.rows[6]['output_device_types']=[];self.write();r=self.call('0.6');self.assertEqual(r['audio_observation']['state'],'available');self.assertEqual(r['audio_observation']['output_device_types'],[])
    def test_no_data_invalid_samples_and_sitting_not_inferred(self):
        self.rows[3]['activity']='sitting';self.rows[4]['values']=[None,2,3];self.rows[4]['invalid_components']=['NaN',None,None];self.rows[4]['value_state']='invalid_values';self.write()
        r=self.call('0.1');self.assertEqual(r['self_reported']['activity'],'sitting');self.assertEqual(r['activity_prediction']['result'],'unknown');self.assertTrue(r['historical_replay'])
        self.assertEqual(self.call()['sensors']['1']['valid_sample_count'],0)
        self.rows=[r for r in fixture() if r['type']!='sensor_sample']
        for i,r in enumerate(self.rows):r['seq']=i+1
        self.rows[-1]['sample_count']=0;self.write();r=self.call();self.assertEqual(r['capture_continuity'],'NO_DATA');self.assertEqual(r['sensors']['1']['aligned_samples'],[])
if __name__=='__main__':unittest.main(verbosity=2)
