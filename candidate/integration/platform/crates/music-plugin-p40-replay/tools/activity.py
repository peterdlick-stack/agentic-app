"""Sensor-only causal phone-motion baseline. Standard library, no learned state."""
import dataclasses, hashlib, json, math, statistics
VERSION = 'p40-activity-v0.1'
NS = 1_000_000_000
PARAMS = dict(window_ns=4*NS, step_ns=NS, min_samples=80, max_gap_ns=200_000_000,
              max_delay_ns=200_000_000, stationary_acc_sd=.12, stationary_gyro_rms=.08,
              walking_acc_sd_min=.35, walking_acc_sd_max=3., walking_gyro_rms_max=2.5,
              cadence_hz_min=.8, cadence_hz_max=2.5, periodicity_min=.55,
              rate_hz_min=20., rate_hz_max=30.)
PARAMETER_SHA256 = hashlib.sha256(json.dumps(PARAMS,sort_keys=True,separators=(',',':')).encode()).hexdigest()
@dataclasses.dataclass(frozen=True)
class Sample:
    sensor: int
    timestamp: int
    available: int
    received: int
    values: tuple
    valid: bool
    accuracy: int

def project(rows):
    """Whitelisted adapter. Labels, names, placement, identities are discarded."""
    return tuple(Sample(r['sensor_type'],int(r['sensor_timestamp_ns']),int(r['record_elapsed_ns']),
                        int(r['received_elapsed_ns']),tuple(r['values']),r['value_state']=='valid',r['accuracy'])
                 for r in rows if r.get('type')=='sensor_sample')

def predict(samples, start, at):
    """Uses only samples available by at; all ns arithmetic is integer."""
    left=max(start,at-PARAMS['window_ns'])
    result=dict(source='local_sensor_rule',algorithm_version=VERSION,parameter_sha256=PARAMETER_SHA256,
                evidence_time_ns=str(at),window_start_ns=str(left),window_end_ns=str(at),
                window_convention='(start,end]',result='unknown',human_activity='unknown',
                interpretation='phone_motion_only; walking is conditional walking-like movement, not verified human activity',
                quality_status='INSUFFICIENT',abstention_reasons=[],features={},score_kind='uncalibrated_feature_not_probability')
    reasons=result['abstention_reasons']
    if at-start<PARAMS['window_ns']:reasons.append('STARTUP_WAIT')
    mags={}
    for sensor in (1,4):
        selected=sorted((s for s in samples if s.sensor==sensor and left<s.timestamp<=at and s.available<=at and s.received<=at),key=lambda s:s.timestamp)
        prefix=f'SENSOR_{sensor}_'
        valid=[s for s in selected if s.valid and len(s.values)==3 and all(type(v) in (int,float) and math.isfinite(v) for v in s.values)]
        if len(valid)<PARAMS['min_samples']:reasons.append(prefix+'TOO_FEW_SAMPLES')
        if len(valid)!=len(selected):reasons.append(prefix+'INVALID_VALUES')
        if any(s.accuracy<=0 for s in selected):reasons.append(prefix+'UNRELIABLE_ACCURACY')
        if any(s.received<s.timestamp or s.available<s.received for s in selected):reasons.append(prefix+'INVALID_TIMING')
        if any(s.received-s.timestamp>PARAMS['max_delay_ns'] for s in selected):reasons.append(prefix+'DELAYED_CALLBACK')
        times=[left]+[s.timestamp for s in valid]+[at]
        if any(b-a>PARAMS['max_gap_ns'] for a,b in zip(times,times[1:])):reasons.append(prefix+'GAP')
        if len({s.timestamp for s in selected})!=len(selected):reasons.append(prefix+'DUPLICATE_TIMESTAMP')
        result['features'][prefix+'count']=len(valid)
        mags[sensor]=[math.sqrt(sum(v*v for v in s.values)) for s in valid]
        if len(valid)>1 and valid[-1].timestamp>valid[0].timestamp:
            result['features'][prefix+'rate_hz']=(len(valid)-1)*NS/(valid[-1].timestamp-valid[0].timestamp)
    if reasons:return result
    acc=mags[1];gyro=mags[4]
    sd=statistics.pstdev(acc);rms=math.sqrt(statistics.mean(v*v for v in gyro))
    rate=result['features']['SENSOR_1_rate_hz'];centered=[v-statistics.mean(acc) for v in acc]
    correlations=[]
    for lag in range(max(1,math.ceil(rate/PARAMS['cadence_hz_max'])),min(len(acc)//2,math.floor(rate/PARAMS['cadence_hz_min']))+1):
        a,b=centered[:-lag],centered[lag:];den=math.sqrt(sum(v*v for v in a)*sum(v*v for v in b))
        correlations.append((sum(x*y for x,y in zip(a,b))/den if den else 0.,rate/lag))
    score,cadence=max(correlations,default=(0.,0.))
    result['features'].update(acc_magnitude_sd=sd,gyro_magnitude_rms=rms,periodicity_score=score,cadence_hz=cadence)
    result['quality_status']='OK'
    if sd<=PARAMS['stationary_acc_sd'] and rms<=PARAMS['stationary_gyro_rms']:result['result']='stationary'
    elif (PARAMS['walking_acc_sd_min']<=sd<=PARAMS['walking_acc_sd_max'] and rms<=PARAMS['walking_gyro_rms_max'] and
          PARAMS['rate_hz_min']<=rate<=PARAMS['rate_hz_max'] and score>=PARAMS['periodicity_min']):result['result']='walking'
    else:reasons.append('OUTSIDE_RULE_SUPPORT')
    return result

def predict_rows(rows,start,at,input_sha256):
    # Provenance attached only after classification; never passed to predict().
    return dict(predict(project(rows),start,at),input_sha256=input_sha256)

def timeline(rows,start,end,input_sha256):
    samples=project(rows)
    return [dict(predict(samples,start,t),input_sha256=input_sha256) for t in range(start,end,PARAMS['step_ns'])]

if __name__=='__main__':
    import argparse,pathlib
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('file');p.add_argument('--output',required=True)
    a=p.parse_args();raw=pathlib.Path(a.file).read_bytes();rows=[json.loads(l) for l in raw.splitlines()]
    start=int(rows[0]['elapsed_ns'])
    last=rows[-1];end=int(last['elapsed_ns']) if last.get('event')=='end' else int(last.get('valid_end_elapsed_ns',int(last['record_elapsed_ns'])+1))
    with pathlib.Path(a.output).open('x',encoding='utf-8') as out:
        for result in timeline(rows,start,end,hashlib.sha256(raw).hexdigest()):out.write(json.dumps(result,allow_nan=False)+'\n')
