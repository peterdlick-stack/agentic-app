"""One fixed causal six-axis rule candidate; development diagnostic only."""
import math, statistics
import baseline

VERSION = 'six-axis-causal-rule-v1'
PARAMETERS = {'axis_periodicity_min': .55, 'cadence_hz_min': .8, 'cadence_hz_max': 2.5,
              'acc_axis_sd_norm_min': .35, 'acc_axis_sd_norm_max': 3., 'gyro_rms_max': 2.5}

def predict(samples, start, at):
    result = baseline.predict(samples, start, at)
    result['algorithm_version'] = VERSION
    result.pop('parameter_sha256', None)
    result['parameters'] = PARAMETERS
    if result['quality_status'] != 'OK':
        return result
    left = max(start, at - baseline.PARAMS['window_ns'])
    channels = []
    peaks = []
    for sensor in (1, 4):
        selected = sorted((s for s in samples if s.sensor == sensor and left < s.timestamp <= at
                           and s.available <= at and s.received <= at), key=lambda s: s.timestamp)
        rate = (len(selected)-1)*baseline.NS/(selected[-1].timestamp-selected[0].timestamp)
        for axis in range(3):
            values = [s.values[axis] for s in selected]
            mean = statistics.mean(values)
            sd = statistics.pstdev(values)
            centered = [v-mean for v in values]
            corrs = []
            for lag in range(max(1, math.ceil(rate/2.5)), min(len(values)//2, math.floor(rate/.8))+1):
                a, b = centered[:-lag], centered[lag:]
                den = math.sqrt(sum(v*v for v in a)*sum(v*v for v in b))
                corrs.append((sum(x*y for x,y in zip(a,b))/den if den else 0., rate/lag))
            peak, hz = max(corrs, default=(0.,0.))
            channels.append({'sensor':sensor, 'axis':axis, 'mean':mean, 'sd':sd,
                             'periodicity':peak, 'cadence_hz':hz, 'calibrated':False})
            if sensor == 1 and sd >= .12:
                peaks.append(peak)
    result['features']['six_axis'] = channels
    acc_sd = math.sqrt(sum(c['sd']**2 for c in channels[:3]))
    result['features']['acc_axis_sd_norm'] = acc_sd
    result['abstention_reasons'] = []
    # Stationary baseline is preserved; only a fixed walking rule is substituted.
    if result['result'] == 'stationary':
        return result
    if .35 <= acc_sd <= 3. and result['features']['gyro_magnitude_rms'] <= 2.5 and max(peaks, default=0.) >= .55:
        result['result'] = 'walking'
    else:
        result['result'] = 'unknown'
        result['abstention_reasons'] = ['OUTSIDE_CANDIDATE_SUPPORT']
    return result

def timeline(rows, start, end, input_sha256):
    samples = baseline.project(rows)
    return [dict(predict(samples,start,t),input_sha256=input_sha256)
            for t in range(start,end,baseline.PARAMS['step_ns'])]
