import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from context_player.backend import Backend

ROOT=(Path(__file__).resolve().parents[2]/"test-fixtures")

class BackendTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.state=Path(self.tmp.name)/'state'
        self.backend=Backend(ROOT,self.state,True)
    def tearDown(self):
        self.backend.close();self.tmp.cleanup()
    def rec(self):
        return self.backend.dispatch({'op':'recommend','request':'少点人声'})
    def test_manual_recommend_feedback_exact_snapshot_restart(self):
        self.backend.dispatch({'op':'manual','activity':'reading'})
        result=self.rec();selected=result['selection']
        self.assertEqual(selected['_context']['activity'],'reading')
        self.assertTrue(selected['ids'])
        event=dict(op='feedback',event_id='exposure-1',snapshot_id=selected['_snapshot_id'],track_id=selected['ids'][0],value='like',mode='normal',condition='C')
        self.assertTrue(self.backend.dispatch(event)['feedback']['saved'])
        self.backend.close();self.backend=Backend(ROOT,self.state,True)
        self.assertTrue(self.backend.dispatch(event)['feedback']['duplicate'])
        self.assertEqual(self.backend.context()['activity'],'unknown')
    def test_mode_scope_prevents_wrong_feedback_and_a_has_no_context(self):
        selected=self.rec()['selection']
        self.backend.dispatch({'op':'mode','mode':'history','condition':'A'})
        with self.assertRaises(ValueError):
            self.backend.dispatch(dict(op='feedback',event_id='bad',snapshot_id=selected['_snapshot_id'],track_id=selected['ids'][0],value='like',mode='normal',condition='C'))
        hist=self.rec()['selection'];self.assertEqual(hist['_context']['activity'],'unknown')
        self.assertEqual(hist['_condition'],'A')
        self.assertEqual(self.backend.store().preferences('A')['tracks'],{})
    def test_real_history_stays_history_and_no_reference_leak(self):
        source=Path('/mnt/c/Users/admin/Downloads/Agentic Apps/work/p40-activity-v0-20261003-214102/inputs.json')
        if not source.exists():self.skipTest('historical input unavailable')
        item=json.loads(source.read_text(encoding='utf-8-sig'))[0]
        os.environ['P40_VALIDATOR']='/mnt/c/Users/admin/Downloads/Agentic Apps/context-sense-p40/tools/validate_jsonl.py'
        result=self.backend.dispatch({'op':'history','file':item['wsl_path'],'relative_seconds':'0'})
        c=result['context'];self.assertTrue(c['historical']);self.assertFalse(c['allowed_for_current'])
        self.assertNotIn('self_reported',c);self.assertNotIn('file',c)
        result=self.rec();self.assertTrue(result['selection']['_context']['historical'])
        self.assertEqual(result['selection']['_mode'],'history')
    def test_broken_settings_are_reported_and_not_overwritten(self):
        self.backend.close();raw=b'broken';(self.state/'settings.json').write_bytes(raw)
        self.backend=Backend(ROOT,self.state)
        self.assertIsNotNone(self.backend.status()['restore_error'])
        self.assertEqual((self.state/'settings.json').read_bytes(),raw)
    def test_shared_readonly_library_and_failed_request(self):
        run=Path(self.tmp.name)/'run';run.mkdir();(run/'library').symlink_to(ROOT/'library')
        b=Backend(run,run/'state')
        self.assertTrue(b.dispatch({'op':'recommend','request':'少点人声'})['selection']['ids'])
        with self.assertRaises(ValueError):b.dispatch({'op':'recommend','request':'火星音乐禁止鼓声'})
        b.close()
    def test_stdio_eof_releases_receiver(self):
        import socket
        p=subprocess.Popen([sys.executable,'-B','-m','context_player.backend','--root',str(ROOT),'--state',str(self.state/'child')],cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
        def call(obj):
            p.stdin.write(json.dumps(obj)+'\n');p.stdin.flush();return json.loads(p.stdout.readline())
        self.assertTrue(call({'op':'mode','mode':'live'})['ok'])
        result=call({'op':'connect'})['result']['connection'];url=result['url'];port=int(url.rsplit(':',1)[1])
        p.stdin.close();self.assertEqual(p.wait(timeout=8),0);p.stdout.close()
        with socket.socket() as s:self.assertNotEqual(s.connect_ex(('127.0.0.1',port)),0)

    def test_normal_and_live_restore_distinct_frozen_queues(self):
        ordinary=self.rec()['selection']
        folder=self.state/'current-C'
        (folder/'queue.json').write_text(json.dumps(ordinary))
        self.backend.dispatch({'op':'mode','mode':'live'})
        live=self.rec()['selection']
        (folder/'live-queue.json').write_text(json.dumps(live))
        self.assertEqual(self.backend.dispatch({'op':'restore_queue'})['selection'],live)
        self.backend.dispatch({'op':'mode','mode':'normal'})
        self.assertEqual(self.backend.dispatch({'op':'restore_queue'})['selection'],ordinary)
        self.assertEqual(json.loads((folder/'live-queue.json').read_text()),live)

if __name__=='__main__':unittest.main()
