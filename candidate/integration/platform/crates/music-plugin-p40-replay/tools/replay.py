"""Read-only P40 replay. No persistent cache, writes, model calls, or event learning."""
import pathlib, hashlib, json, re, os, sys, statistics, math
VERSION='p40-replay-v1'
VALIDATOR_SHA='a3d4ac6ecc205dcc1a7587e2cb16dad883ecdd24ca8b9f3249bc4630a782141e'
THRESHOLD=200_000_000
class ReplayError(ValueError): pass
def digest(raw):return hashlib.sha256(raw).hexdigest()
def local_path(value):
    if not isinstance(value,str) or not value.strip():raise ReplayError('FILE_REQUIRED: 请输入文件路径')
    if os.name!='nt' and re.match(r'^[A-Za-z]:[\\/]',value):value='/mnt/'+value[0].lower()+'/'+value[3:].replace('\\','/')
    return pathlib.Path(value)
def seconds_ns(value):
    if not isinstance(value,str) or not re.fullmatch(r'[0-9]+(?:\.[0-9]{1,9})?',value):raise ReplayError('INVALID_TIME: 相对秒数须为非负十进制，最多9位小数')
    whole,_,fraction=value.partition('.');return int(whole)*1_000_000_000+int(fraction.ljust(9,'0') or '0')
def seconds(value):return f'{value//1_000_000_000}.{value%1_000_000_000:09d}'
def milliseconds(value):
    if value is None:return '未知'
    whole,_,fraction=value.partition('.');number=int(whole)
    return (f'{number//1_000_000}.{number%1_000_000:06d}'+fraction).rstrip('0').rstrip('.')
def pairs(items):
    out={}
    for key,value in items:
        if key in out:raise ReplayError('DUPLICATE_JSON_KEY: '+key)
        out[key]=value
    return out
def stats(values):
    if not values:return None
    ordered=sorted(values);n=len(ordered)
    # Median kept exact as a decimal string, including half-nanoseconds.
    middle=ordered[n//2]*2 if n%2 else ordered[n//2-1]+ordered[n//2]
    return dict(min_ns=str(ordered[0]),median_ns=str(middle//2)+('.5' if middle%2 else ''),p95_ns=str(ordered[math.ceil(.95*n)-1]),max_ns=str(ordered[-1]))
def replay(request):
    path=local_path(request.get('file'));raw=path.read_bytes();sha=digest(raw)
    validator=local_path(os.environ['P40_VALIDATOR']) if os.environ.get('P40_VALIDATOR') else next((p/'tools/validate_jsonl.py' for p in path.resolve().parents if (p/'tools/validate_jsonl.py').is_file()),None)
    if validator is None:raise ReplayError('VALIDATOR_UNAVAILABLE: 请在启动时设置 P40_VALIDATOR 为冻结验证器路径')
    validator_raw=validator.read_bytes()
    if digest(validator_raw)!=VALIDATOR_SHA:raise ReplayError('VALIDATOR_HASH_MISMATCH: 冻结验证器摘要不符，停止导入')
    namespace={'__name__':'p40_frozen_readonly','__file__':str(validator)}
    exec(compile(validator_raw,str(validator),'exec'),namespace)
    try: report=namespace['audit'](path)
    except (KeyError,TypeError,ValueError,OverflowError,IndexError) as e:raise ReplayError('VALIDATOR_REJECTED: '+str(e)) from e
    if digest(validator.read_bytes())!=VALIDATOR_SHA:raise ReplayError('VALIDATOR_CHANGED_DURING_IMPORT')
    if report['sha256']!=sha or digest(path.read_bytes())!=sha:raise ReplayError('FILE_CHANGED_DURING_IMPORT: 请重新导入')
    if request.get('expected_sha256') is not None and request['expected_sha256']!=sha:raise ReplayError('FILE_HASH_CONFLICT: 文件已改变')
    if request.get('expected_session_id') is not None and request['expected_session_id']!=report['session_id']:raise ReplayError('SESSION_CONFLICT: 会话不一致')
    if report['result']=='FAIL':raise ReplayError('INVALID_FILE: '+'; '.join(report['errors']))
    rows=[]
    for line in raw[:report['valid_json_prefix_bytes']].splitlines():
        try:row=json.loads(line,object_pairs_hook=pairs)
        except (ValueError,UnicodeDecodeError) as e:raise ReplayError('INVALID_JSON: '+str(e)) from e
        if type(row['schema_version']) is not int or row['schema_version']!=1:raise ReplayError('INVALID_SCHEMA_TYPE')
        rows.append(row)
    start,end=map(int,report['valid_range_elapsed_ns'])
    if end<=start:raise ReplayError('NO_REPLAY_RANGE: 无可查询区间')
    if report['actual_end_known'] and end-start>600_000_000_000:raise ReplayError('SESSION_EXCEEDS_DURATION_LIMIT')
    labels=[r for r in rows if r['type']=='manual_label']
    if any(int(r['effective_elapsed_ns'])>=end for r in labels):raise ReplayError('LABEL_OUTSIDE_RANGE')
    if rows[-1]['source']=='app_recovery':
        recovery=rows[-1]
        if recovery.get('end_time_known') is not False or int(recovery['valid_end_elapsed_ns'])!=int(rows[-2]['record_elapsed_ns'])+1 or recovery['record_elapsed_ns']!=rows[-2]['record_elapsed_ns']:raise ReplayError('INVALID_RECOVERY_BOUNDARY')
        if any(type(recovery[k]) is not int or recovery[k]<0 for k in ('original_bytes','valid_prefix_bytes','omitted_tail_bytes')):raise ReplayError('INVALID_RECOVERY_LENGTH_TYPE')
        prefix_bytes=sum(len(line) for line in raw[:report['valid_json_prefix_bytes']].splitlines(keepends=True)[:-1])
        if recovery['valid_prefix_bytes']!=prefix_bytes:raise ReplayError('RECOVERY_PREFIX_LENGTH_MISMATCH')
    cursor=seconds_ns(request.get('relative_seconds','0'));window=seconds_ns(request.get('window_seconds','1'))
    if window<=0:raise ReplayError('INVALID_WINDOW: 查询窗口须大于0')
    if cursor>=end-start:raise ReplayError('OUTSIDE_SESSION: 游标须小于会话有效时长 '+seconds(end-start)+' 秒')
    qstart=start+cursor;qend=min(end,qstart+window)
    def label_at(ts):
        label=next((r for r in reversed(labels) if int(r['effective_elapsed_ns'])<=ts),None)
        return dict(activity=label['activity'],placement=label['placement'],label_role='self_reported_reference') if label else dict(activity='unknown',placement='unknown',label_role='self_reported_reference')
    sensors={};anomalous=False;missing=False
    for st in (1,4):
        all_samples=[r for r in rows if r['type']=='sensor_sample' and r['sensor_type']==st]
        samples=[r for r in all_samples if qstart<=int(r['sensor_timestamp_ns'])<qend]
        gaps=[]
        points=[start]+[int(r['sensor_timestamp_ns']) for r in all_samples]
        # Even an unfinished session has a known observed-prefix boundary.
        # Check coverage within that boundary without inventing an actual stop.
        points.append(end)
        for i,(left,right) in enumerate(zip(points,points[1:])):
            if right-left>THRESHOLD:gaps.append(dict(start_relative_ns=str(left-start),end_relative_ns=str(right-start),interval_ns=str(right-left),kind='leading' if i==0 else (('trailing' if report['actual_end_known'] else 'observed_prefix_trailing') if i==len(points)-2 else 'between_samples')))
        for r in all_samples:
            valid=all(type(v) in (int,float) and math.isfinite(v) for v in r['values'])
            if (r['value_state']=='valid')!=valid:raise ReplayError('INCONSISTENT_VALUE_STATE')
        intervals=[int(b['sensor_timestamp_ns'])-int(a['sensor_timestamp_ns']) for a,b in zip(all_samples,all_samples[1:])]
        delays=[int(r['received_elapsed_ns'])-int(r['sensor_timestamp_ns']) for r in all_samples]
        relevant_gaps=[g for g in gaps if int(g['start_relative_ns'])<qend-start and int(g['end_relative_ns'])>cursor]
        missing=missing or not all_samples
        anomalous=anomalous or bool(gaps) or any(d>THRESHOLD for d in delays) or any(r['value_state']!='valid' for r in all_samples)
        sensors[str(st)]={'sample_count':len(all_samples),'valid_sample_count':sum(r['value_state']=='valid' for r in all_samples),'window_sample_count':len(samples),'window_valid_sample_count':sum(r['value_state']=='valid' for r in samples),'interval':stats(intervals),'arrival_delay':stats(delays),'delayed_arrivals':sum(d>THRESHOLD for d in delays),'gaps':gaps,'window_gaps':relevant_gaps,'window_arrival_delay':stats([int(r['received_elapsed_ns'])-int(r['sensor_timestamp_ns']) for r in samples]),'aligned_samples':[dict(seq=r['seq'],sensor_relative_ns=str(int(r['sensor_timestamp_ns'])-start),received_relative_ns=str(int(r['received_elapsed_ns'])-start),value_state=r['value_state'],**label_at(int(r['sensor_timestamp_ns']))) for r in samples]}
    warning_records=[r for r in rows if r['type']=='status' and (r.get('state') in ('continuity_anomaly','temporarily_no_data','no_data','invalid_timestamp','read_failed','missing','permission_denied') or r.get('continuity_warning') is True or r.get('scheduler_warning') is True)]
    # Initial no_data is an observation before the first callback, not a gap.
    # Missing sensor samples are represented separately by NO_DATA.
    anomalous=anomalous or any(r['state']!='no_data' for r in warning_records)
    audio=max((r for r in rows if r['type']=='audio_devices' and int(r['observed_elapsed_ns'])<=qstart),key=lambda r:(int(r['observed_elapsed_ns']),r['seq']),default=None)
    audio_output={k:audio[k] for k in ['state','output_device_types','meaning','observed_elapsed_ns']} if audio else dict(state='not_observed',output_device_types=None,meaning='system_visible_available_outputs_not_active_route',observed_elapsed_ns=None)
    continuity='NO_DATA' if missing else ('ANOMALOUS' if anomalous else 'CONTIGUOUS_OBSERVED')
    result=dict(historical_replay=True,automatic_activity_prediction='NOT_IMPLEMENTED',algorithm_version=VERSION,import_={'file':str(path),'sha256':sha,'bytes':len(raw),'session_id':report['session_id'],'app_version':rows[0]['metadata']['app_version'],'schema_version':1,'source':report['source'],'validator_sha256':VALIDATOR_SHA},file_integrity=report['result'],capture_continuity=continuity,actual_end_known=report['actual_end_known'],tail_state='DAMAGED_TAIL' if report['unparsed_bytes'] else 'NO_UNPARSED_BYTES',unparsed_bytes=report['unparsed_bytes'],valid_range_elapsed_ns=[str(start),str(end)],valid_range_relative_ns=['0',str(end-start)],duration_seconds=seconds(end-start),cursor_seconds=seconds(cursor),query_interval_elapsed_ns=[str(qstart),str(qend)],query_interval_relative_ns=[str(cursor),str(qend-start)],self_reported=label_at(qstart),sensors=sensors,audio_observation=audio_output,label_intervals=report['label_intervals'],warnings=report['warnings'],quality_status_records=[{k:r[k] for k in ['seq','state','sensor_type','record_elapsed_ns'] if k in r} for r in warning_records],errors=[])
    result['import']=result.pop('import_')
    if rows[-1]['source']=='app_recovery':
        result['import']['original_record_identity']={k:rows[-1][k] for k in ('original_sha256','original_bytes','valid_prefix_bytes','omitted_tail_bytes')}
        result['import']['original_record_identity']['independently_verified']=False
    label=result['self_reported'];names={'unknown':'未知','sitting':'静坐','walking':'步行','running':'跑步','other':'其他','hand':'手持','pocket':'口袋','desk':'桌面'}
    integrity={'COMPLETE':'结构完整','PREFIX_ONLY':'仅可读前缀，实际结束未知'}[report['result']]
    quality={'CONTIGUOUS_OBSERVED':'观察范围内连续','ANOMALOUS':'存在采集异常','NO_DATA':'至少一个传感器无样本'}[continuity]
    tail=f"；损坏尾部 {report['unparsed_bytes']} 字节" if report['unparsed_bytes'] else ''
    median=' / '.join(milliseconds(sensors[k]['interval']['median_ns']) if sensors[k]['interval'] else '未知' for k in ('1','4'))
    latency=' / '.join(milliseconds(sensors[k]['arrival_delay']['max_ns']) if sensors[k]['arrival_delay'] else '未知' for k in ('1','4'))
    result['message']=f"历史回放 · {path.name}\n会话 {report['session_id']} · 采集 {result['import']['app_version']}\n回放 {seconds(cursor)} / {seconds(end-start)} 秒\n本人报告活动：{names[label['activity']]}；放置：{names[label['placement']]}\n文件{integrity}；{quality}{tail}\n窗口 加速度 {sensors['1']['window_valid_sample_count']} / 陀螺 {sensors['4']['window_valid_sample_count']} 个有效样本；缺口 {len(sensors['1']['window_gaps'])} / {len(sensors['4']['window_gaps'])}\n会话采样中位间隔 {median} 毫秒；最大到达延迟 {latency} 毫秒\n自动活动识别尚未实现；历史记录不参与在线选歌或偏好学习。"
    # Prediction errors must not invalidate the already verified historical replay.
    try:
        from activity import predict_rows
        prediction=predict_rows(rows,start,qstart,sha)
        result['activity_prediction']=prediction
        result['automatic_activity_prediction']='EXPERIMENTAL_PHONE_MOTION'
        title={'stationary':'手机静止（不证明人静止或在场）','walking':'步行样运动（携带条件待核实）','unknown':'未知 / 弃判'}[prediction['result']]
        interval=seconds(int(prediction['window_start_ns'])-start)+'–'+seconds(int(prediction['window_end_ns'])-start)
        reasons=', '.join(prediction['abstention_reasons']) or '无弃判；人的活动仍未知'
        result['message']=result['message'].replace('自动活动识别尚未实现；','')
        result['message']+=f"\n算法预测：{title}\n依据过去窗口 ({interval}] 秒；质量 {prediction['quality_status']}\n原因：{reasons}\n版本 {prediction['algorithm_version']}；仅探索性，未经独立效果验收"
    except Exception as error:
        result['activity_prediction']={'status':'PREDICTION_FAILED','result':'unknown','human_activity':'unknown','error':str(error)}
        result['automatic_activity_prediction']='PREDICTION_FAILED'
        result['message']=result['message'].replace('自动活动识别尚未实现；','')
        result['message']+='\n预测失败，原始回放仍可用：'+str(error)
    return result
if __name__=='__main__':
    try:
        request=json.load(sys.stdin);answer=replay(request);print(json.dumps(answer,ensure_ascii=False,allow_nan=False))
    except (ReplayError,OSError,ValueError,KeyError,TypeError) as e:
        print(json.dumps(dict(status='IMPORT_OR_QUERY_FAILED',historical_replay=True,automatic_activity_prediction='NOT_IMPLEMENTED',error=str(e)),ensure_ascii=False));sys.exit(1)
