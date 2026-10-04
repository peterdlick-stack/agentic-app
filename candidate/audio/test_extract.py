import json, tempfile, unittest, wave
from pathlib import Path
import numpy as np
from extract import ROOT, decode, extract, write_json

class ExtractTests(unittest.TestCase):
    def setUp(self):
        (ROOT/'tmp').mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'tmp'); self.path=Path(self.temp.name)
    def tearDown(self): self.temp.cleanup()
    def wav(self,name,x,rate=8000):
        p=self.path/name
        with wave.open(str(p),'wb') as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes((x*32767).astype('<i2').tobytes())
        return p
    def test_mechanism_click_tempos(self):
        for tempo in [90,120,150]:
            x=np.zeros(8000*20)
            for i in np.arange(0,len(x),8000*60/tempo).astype(int): x[i:i+80]=.7
            row=extract(self.wav(str(tempo)+'.wav',x))
            self.assertLess(abs(row['features']['bpm']['value']/tempo-1),.05)
            self.assertIsNone(row['features']['vocal']['value'])
    def test_silence_abstains(self):
        row=extract(self.wav('silence.wav',np.zeros(8000*6)))
        self.assertIsNone(row['features']['bpm']['value']); self.assertIsNotNone(row['features']['bpm']['reason'])
    def test_corrupt_audio(self):
        p=self.path/'bad.wav'; p.write_bytes(b'not wave')
        row=extract(p); self.assertEqual(row['status'],'FAILED'); self.assertTrue(all(v['value'] is None for v in row['features'].values()))
    def test_constant_amplitude_rms(self):
        row=extract(self.wav('dc.wav',np.ones(8000)*.5))
        self.assertAlmostEqual(row['features']['rms_dbfs']['value'],-6.0206,places=2)
    def test_write_boundary(self):
        with self.assertRaises(ValueError): write_json(ROOT.parent/'forbidden.json',{})
    def test_pcm24_sign(self):
        x=decode(bytes([0,0,128,255,255,127]),3,1).ravel()
        self.assertEqual(x[0],-1); self.assertGreater(x[1],.999)
    def test_source_hash_binding(self):
        p=self.wav('changing.wav',np.ones(8000)*.5)
        row=extract(p)
        self.wav('changing.wav',np.zeros(8000))
        with self.assertRaisesRegex(ValueError,'source_content_changed'):
            extract(p,row['content_id'])

if __name__=='__main__': unittest.main()
