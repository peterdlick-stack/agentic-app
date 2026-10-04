"""Read-only PCM WAV feature extraction. Never infers vocals or accuracy."""
import argparse, hashlib, json, os, time, wave
from pathlib import Path
import numpy as np

VERSION = 'pcm-onset-acf-v1'
ROOT = Path(__file__).resolve().parent

def write_json(path, data):
    path = Path(path).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError('output outside audio branch')
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
    tmp.replace(path)

def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()

def field(value, unit, kind, source, reason=None, quality=None):
    return dict(value=value, unit=unit, method_version=VERSION, source=source,
                kind=kind, quality=dict(score=quality, calibrated=False), reason=reason)

def decode(raw, width, channels):
    if width == 1:
        x = (np.frombuffer(raw, np.uint8).astype(float)-128)/128
    elif width in (2, 4):
        x = np.frombuffer(raw, '<i'+str(width)).astype(float)/(2**(8*width-1))
    elif width == 3:
        b = np.frombuffer(raw, np.uint8).reshape(-1, 3).astype(np.int32)
        x = b[:,0] | (b[:,1]<<8) | (b[:,2]<<16)
        x = ((x ^ 0x800000)-0x800000).astype(float)/8388608
    else:
        raise ValueError('unsupported PCM sample width')
    return x.reshape(-1, channels)

def estimate_bpm(envelopes):
    # Independent windows; no artificial seam between audio intervals.
    acfs=[]
    for env in envelopes:
        onset=np.maximum(0, np.diff(env))
        if len(onset)<400 or np.std(onset)<1e-8:
            continue
        onset=onset-np.mean(onset)
        ac=np.correlate(onset,onset,mode='full')[len(onset)-1:]
        ac=ac/(np.arange(len(onset),0,-1)*np.var(onset)+1e-15)
        acfs.append(ac[:101])
    if not acfs:
        return None, None, 'insufficient rhythmic onset energy'
    ac=np.mean(acfs,axis=0)
    # Fixed search 60--200 BPM; high ACF is uncalibrated periodicity, not probability.
    lag=int(np.argmax(ac[30:101])+30)
    strength=float(ac[lag])
    if strength<0.10:
        return None, strength, 'weak periodicity'
    return float(6000/lag), strength, None

def extract(path, content_id=None):
    path=Path(path)
    cid=content_id or 'sha256:'+digest(path)
    source=dict(path=str(path), intervals_seconds=[], sample_policy='up to three nonoverlapping 30s intervals at start/middle/end', sampled_only=True)
    try:
        envelopes=[]; energy=0.; values=0
        with wave.open(str(path),'rb') as w:
            rate=w.getframerate(); count=w.getnframes(); channels=w.getnchannels(); width=w.getsampwidth()
            if rate<=0 or count==0 or channels<1 or w.getcomptype()!='NONE':
                raise ValueError('empty or unsupported PCM WAV')
            duration=count/rate
            starts=[0] if duration<=90 else [0,max(30,duration/2-15),duration-30]
            if duration<=90:
                starts=list(np.arange(0,duration,30))
            for start in starts:
                w.setpos(int(start*rate)); n=min(int(30*rate),count-int(start*rate))
                raw=w.readframes(n)
                if len(raw)!=n*channels*width:
                    raise ValueError('truncated PCM payload')
                x=decode(raw,width,channels)
                # RMS across channels avoids antiphase stereo cancellation.
                sq=np.mean(x*x,axis=1); energy+=float(np.sum(sq)); values+=len(sq)
                block=max(1,round(rate/100)); usable=len(sq)//block*block
                env=np.sqrt(sq[:usable].reshape(-1,block).mean(axis=1))
                # Resample envelope to exactly 100 Hz if source rate is not divisible by 100.
                env=np.interp(np.arange(0,len(env)*block/rate,0.01),np.arange(len(env))*block/rate,env)
                envelopes.append(env)
                source['intervals_seconds'].append([float(start),float(start+n/rate)])
            source.update(sample_rate_hz=rate,channels=channels,pcm_width_bytes=width,duration_seconds=duration)
        bpm,quality,reason=estimate_bpm(envelopes)
        levels=20*np.log10(np.maximum(np.concatenate(envelopes),1e-12))
        rms=10*np.log10(max(energy/values,1e-24))
        features=dict(bpm=field(bpm,'beats/min','estimate',source,reason,quality),
                      rms_dbfs=field(float(rms),'dBFS','measurement',source),
                      dynamic_db=field(float(np.percentile(levels,95)-np.percentile(levels,10)),'dB','measurement',source),
                      vocal=field(None,None,'unknown',source,'no credible vocal model available'))
        return dict(content_id=cid,features=features,status='FEATURES_ESTIMATED',reason=reason)
    except (wave.Error,EOFError,ValueError,OSError) as e:
        reason=type(e).__name__+': '+str(e)
        return dict(content_id=cid,features={k:field(None,u,'unknown',source,reason) for k,u in [('bpm','beats/min'),('rms_dbfs','dBFS'),('dynamic_db','dB'),('vocal',None)]},status='FAILED',reason=reason)

def main():
    p=argparse.ArgumentParser(); p.add_argument('--library',required=True); p.add_argument('--pilot',action='store_true'); p.add_argument('--budget-seconds',type=float,default=1700); args=p.parse_args()
    began=time.monotonic(); lib=Path(args.library)
    manifest_path=ROOT/'manifest.json'
    # Complete bytes hashed on first inventory; no names used as semantic labels.
    if manifest_path.exists():
        manifest=json.loads(manifest_path.read_text())
    else:
        manifest=[]
        for path in sorted(lib.glob('*.wav')):
            manifest.append(dict(path=str(path),content_id='sha256:'+digest(path),bytes=path.stat().st_size))
        manifest.sort(key=lambda r:r['content_id'])
        write_json(manifest_path,manifest)
    target=manifest[:48] if args.pilot else manifest
    old=json.loads((ROOT/'features.json').read_text()) if (ROOT/'features.json').exists() else []
    by_id={r['content_id']:r for r in old}
    for item in target:
        if time.monotonic()-began>args.budget_seconds: break
        cid=item['content_id']
        if cid not in by_id:
            tick=time.monotonic(); row=extract(item['path'],cid); row['elapsed_seconds']=time.monotonic()-tick
            by_id[cid]=row
            write_json(ROOT/'features.json',list(by_id.values()))
    report=dict(version=VERSION,library_entries=len(manifest),unique_contents=len({r['content_id'] for r in manifest}),requested_entries=len(target),completed_unique=len(by_id),failed=sum(r['status']=='FAILED' for r in by_id.values()),bpm_nonnull=sum(r['features']['bpm']['value'] is not None for r in by_id.values()),elapsed_seconds=time.monotonic()-began,accuracy='NOT_RUN',status='FEATURES_ESTIMATED',hard_bpm_constraints_enabled=False)
    write_json(ROOT/('pilot_report.json' if args.pilot else 'report.json'),report)
    print(json.dumps(report)); return 0 if all(i['content_id'] in by_id for i in target) else 2

if __name__=='__main__':
    raise SystemExit(main())
