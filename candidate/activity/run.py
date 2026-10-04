"""Offline reproduction and diagnostic candidate, writes exclusively beside this file."""
import collections, copy, hashlib, json, os, pathlib, time
import baseline, candidate
from reference_eval import stable_reference, metrics

ROOT = pathlib.Path(__file__).resolve().parent
OLD = pathlib.Path('/mnt/c/Users/admin/Downloads/Agentic Apps/work/p40-walking-diagnosis-20261003-221326')

def save(name, obj):
    (ROOT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')

def enhanced(items):
    m = metrics(items)
    for c,v in m['per_class'].items():
        tp=m['confusion_matrix'][c][c]
        fp=sum(m['confusion_matrix'][r][c] for r in m['confusion_matrix'] if r!=c)
        fn=v['reference_windows']-tp
        v['f1']=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None
    stationary=m['confusion_matrix']['stationary']
    m['nonwalking_false_positive_rate']=stationary['walking']/sum(stationary.values()) if sum(stationary.values()) else None
    m['delay_seconds']=None
    m['delay_status']='NOT_ESTIMABLE: historical reference synchronization not independently verified'
    return m

def main():
    started=time.monotonic()
    manifest=json.loads((OLD/'dataset-manifest.json').read_text(encoding='utf-8'))
    hashes={}
    predictions={'baseline':{},'candidate':{}}
    allrows={}
    checks={}
    for session in manifest['sessions']:
        path=pathlib.Path(session['wsl_path']); raw=path.read_bytes()
        digest=hashlib.sha256(raw).hexdigest()
        assert digest==session['sha256'], path
        hashes[str(path)]=digest
        rows=[json.loads(line) for line in raw.splitlines()]
        sid=session['session_id']; allrows[sid]=rows
        start,end=map(int,session['range_ns'])
        for name,mod in [('baseline',baseline),('candidate',candidate)]:
            result=mod.timeline(rows,start,end,digest)
            predictions[name][sid]=result
            # Label/file provenance leakage test: change every non-sensor record and add hostile metadata.
            altered=[dict(r,activity='walking',placement='pocket',filename='walking_truth',future_label='walking')
                     if r.get('type')=='sensor_sample' else {'type':'manual_label','activity':'CORRUPTED'} for r in rows]
            assert mod.timeline(altered,start,end,digest)==result
            checks[name+'_'+sid+'_metadata_invariance']=True
            # Prefix equivalence: removing every unavailable future sample must not affect current prediction.
            at=start+min(20*baseline.NS,(end-start)//2)
            samples=baseline.project(rows)
            prefix=tuple(s for s in samples if s.timestamp<=at and s.available<=at and s.received<=at)
            assert mod.predict(samples,start,at)==mod.predict(prefix,start,at)
            checks[name+'_'+sid+'_causal_prefix']=True
        assert time.monotonic()-started<1750, '30-minute checkpoint limit'
        save('checkpoint.json',{'completed_session':sid,'elapsed_seconds':time.monotonic()-started})
    # Serialize all predictions before any evaluator reads labels.
    save('predictions.json',predictions)
    report={}
    for name,by_session in predictions.items():
        scored=[]
        for session in manifest['sessions']:
            sid=session['session_id']; start,end=map(int,session['range_ns'])
            for p in by_session[sid]:
                ref,placement,reason=stable_reference(allrows[sid],start,end,p)
                scored.append({'session_id':sid,'time_ns':p['evidence_time_ns'],'reference':ref,'placement':placement,
                               'excluded_reason':reason,'prediction':p['result'],'quality':p['quality_status'],
                               'abstention_reasons':p['abstention_reasons']})
        save(name+'-scored.json',scored)
        report[name]={'overall':enhanced(scored),
                      'by_session':{s['session_id']:enhanced([x for x in scored if x['session_id']==s['session_id']]) for s in manifest['sessions']},
                      'by_placement':{p:enhanced([x for x in scored if x['placement']==p]) for p in ['hand','pocket']},
                      'abstention_reasons':dict(collections.Counter(r for x in scored for r in x['abstention_reasons']))}
    b=report['baseline']['overall']
    assert b['eligible_windows']==62 and b['confusion_matrix']['walking']['unknown']==33
    checks['baseline_expected_62_scoreable_33_walking_abstain']=True
    # Denominator negative control: abstention must reduce recall.
    fixture=[{'reference':'walking','prediction':'unknown','excluded_reason':None}]
    assert enhanced(fixture)['per_class']['walking']['recall']==0
    checks['abstention_in_recall_denominator']=True
    hashes[str(OLD/'dataset-manifest.json')]=hashlib.sha256((OLD/'dataset-manifest.json').read_bytes()).hexdigest()
    hashes[str(OLD/'activity.py')]=hashlib.sha256((OLD/'activity.py').read_bytes()).hexdigest()
    assert hashes[str(OLD/'activity.py')]==hashlib.sha256((ROOT/'baseline.py').read_bytes()).hexdigest()
    hashes.update({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.glob('*.py')})
    save('hashes.json',hashes)
    save('checks.json',checks)
    save('report.json',{'status':'ACCURACY_UNVERIFIED','baseline_retained':True,'development_iteration':1,
        'independent_test_sessions':0,'existing_sessions':5,'eligible_windows_are_not_independent':True,
        'reference_status':'historical manual annotations; not independently synchronized ground truth',
        'session_interval':'NOT_ESTIMABLE: only one labeled handheld session and no pocket sessions',
        'elapsed_seconds':time.monotonic()-started,'results':report})
    print(json.dumps({'status':'ACCURACY_UNVERIFIED','baseline':b,'candidate':report['candidate']['overall'],'checks':len(checks)},ensure_ascii=False))

if __name__=='__main__': main()
