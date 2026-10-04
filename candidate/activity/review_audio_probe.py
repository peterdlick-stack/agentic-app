import sys, pathlib, wave, json
sys.path.insert(0,'/mnt/f/context-recommend-v1-20261004-154611/audio')
import extract
root=pathlib.Path(__file__).resolve().parent
p=root/'tmp'/'review-one-frame.wav'
with wave.open(str(p),'wb') as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(8000); w.writeframes(b'\0\0')
try:
    row=extract.extract(p)
    print(json.dumps({'status':row['status'],'features':row['features']}))
except Exception as e:
    print(json.dumps({'raised':type(e).__name__,'message':str(e)}))
