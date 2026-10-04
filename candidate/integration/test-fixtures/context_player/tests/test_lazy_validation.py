import unittest
from test_recommend import make_catalog, manual
from context_player.recommend import load_catalog, recommend
from pathlib import Path
import tempfile

class LazyValidationTests(unittest.TestCase):
    def test_shortlisted_bytes_are_checked_after_header_loading(self):
        with tempfile.TemporaryDirectory() as root:
            make_catalog(root)
            catalog=load_catalog(root,verify_all=False)
            path=Path(root)/'library/t0.wav'
            data=bytearray(path.read_bytes());data[-1]^=1;path.write_bytes(data)
            result=recommend(catalog,manual('reading'),{},limit=4)
            self.assertNotIn('t0',[t['id'] for t in result['tracks']])
            self.assertTrue(any(r['id']=='t0' and r['reason']=='audio_hash_mismatch' for r in result['rejected']))
            self.assertTrue(all(t['verification']=='sha256_and_complete_pcm_wav' for t in result['tracks']))

    def test_pending_header_never_claims_full_verification(self):
        with tempfile.TemporaryDirectory() as root:
            make_catalog(root)
            catalog=load_catalog(root,verify_all=False)
            self.assertTrue(all(t['verification']=='metadata_pending_sha256' for t in catalog))
            tracks=recommend(catalog,{}, {},limit=1)['tracks']
            self.assertEqual(len(tracks),1)
            self.assertEqual(tracks[0]['verification'],'sha256_and_complete_pcm_wav')

if __name__=='__main__':unittest.main()
