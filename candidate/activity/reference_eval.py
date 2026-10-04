"""Frozen exploratory experiment. Inference is saved before references are scored."""
import pathlib,json,hashlib,collections,sys
from baseline import timeline,PARAMS,PARAMETER_SHA256,VERSION
R=pathlib.Path(__file__).resolve().parent
OUTPUT=R
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def save(n,v):
 with (OUTPUT/n).open('x',encoding='utf-8') as f:json.dump(v,f,ensure_ascii=False,indent=2,allow_nan=False)
def stable_reference(rows,start,end,p):
 labels=[]
 for r in rows:
  if r['type']=='manual_label':
   item=(int(r['effective_elapsed_ns']),r['activity'],r['placement'])
   if labels and labels[-1][0]==item[0]:labels[-1]=item
   elif not labels or labels[-1][1:]!=item[1:]:labels.append(item)
 t=int(p['evidence_time_ns']);left=int(p['window_start_ns'])
 current=next((x for x in reversed(labels) if x[0]<=t),None)
 if current is None:return None,'unknown','NO_REFERENCE'
 if left<labels[0][0]:return None,current[2],'INCOMPLETE_REFERENCE_WINDOW'
 boundaries=[x[0] for x in labels[1:]]
 if any(left-2_000_000_000<b<=t+2_000_000_000 for b in boundaries):return None,current[2],'TRANSITION_MARGIN'
 if current[1] not in ('sitting','walking'):return None,current[2],'UNSUPPORTED_REFERENCE_'+current[1]
 if current[2] not in ('hand','pocket'):return None,current[2],'UNSUPPORTED_PLACEMENT_'+current[2]
 return {'sitting':'stationary','walking':'walking'}[current[1]],current[2],None
def metrics(items,field='prediction'):
 eligible=[x for x in items if x['reference'] is not None];classes=('stationary','walking');outputs=classes+('unknown',)
 matrix={c:{o:sum(x['reference']==c and x[field]==o for x in eligible) for o in outputs} for c in classes}
 n=len(eligible);known=sum(x[field]!='unknown' for x in eligible);correct=sum(x[field]==x['reference'] for x in eligible)
 return dict(total_windows=len(items),eligible_windows=n,excluded_windows=len(items)-n,exclusions=dict(collections.Counter(x['excluded_reason'] for x in items if x['excluded_reason'])),
  all_window_abstention_rate=sum(x[field]=='unknown' for x in items)/len(items) if items else None,
  eligible_abstentions=n-known,eligible_coverage=known/n if n else None,eligible_abstention_rate=(n-known)/n if n else None,
  exploratory_agreement_all_eligible=correct/n if n else None,conditional_agreement_non_abstained=correct/known if known else None,
  confusion_matrix=matrix,per_class={c:dict(reference_windows=sum(matrix[c].values()),precision=matrix[c][c]/sum(matrix[r][c] for r in classes) if sum(matrix[r][c] for r in classes) else None,recall=matrix[c][c]/sum(matrix[c].values()) if sum(matrix[c].values()) else None) for c in classes})
def main():
 manifest=read(R/'dataset-manifest.json');split=read(R/'split-manifest.json');assert not split['test'] and not split['validation']
 assert len({x['session_id'] for x in split['development']})==len(manifest['sessions'])
 allrows={};predictions={}
 for s in manifest['sessions']:
  p=pathlib.Path(s['path']);raw=p.read_bytes();assert hashlib.sha256(raw).hexdigest()==s['sha256']
  rows=[json.loads(l) for l in raw.splitlines()];allrows[s['session_id']]=rows
  start,end=map(int,s['range_ns']);predictions[s['session_id']]=timeline(rows,start,end,s['sha256'])
  save(s['session_id']+'-predictions.json',predictions[s['session_id']])
 # Labels are accessed by the independent evaluator only after all predictions are on disk.
 items=[]
 for s in manifest['sessions']:
  start,end=map(int,s['range_ns'])
  for p in read(OUTPUT/(s['session_id']+'-predictions.json')):
   ref,placement,reason=stable_reference(allrows[s['session_id']],start,end,p)
   items.append(dict(session_id=s['session_id'],time_ns=p['evidence_time_ns'],reference=ref,placement=placement,excluded_reason=reason,prediction=p['result'],quality=p['quality_status'],abstention_reasons=p['abstention_reasons']))
 counts=collections.Counter(x['reference'] for x in items if x['reference']);majority=sorted(counts,key=lambda k:(-counts[k],k))[0] if counts else 'unknown'
 for x in items:x['majority']=majority
 save('scored-windows.json',items)
 result=dict(title='现有记录上的探索性结果',status='INSUFFICIENT_INDEPENDENT_DATA',algorithm_version=VERSION,parameter_sha256=PARAMETER_SHA256,parameters=PARAMS,
  split_sha256=hashlib.sha256((R/'split-manifest.json').read_bytes()).hexdigest(),independent_test_sessions=0,generalization_accuracy=None,
  denominator_rules='All scheduled windows in coverage; stable sitting/walking hand/pocket references only in supervision; unknown prediction retained in recall/unconditional agreement. Overlapping windows not independent.',
  overall=metrics(items),comparator=dict(rule='development eligible-window majority; lexical tie break',class_=majority,reference_counts=dict(counts),metrics=metrics(items,'majority')),
  sessions={s['session_id']:metrics([x for x in items if x['session_id']==s['session_id']]) for s in manifest['sessions']},
  placement={k:metrics([x for x in items if x['placement']==k]) for k in sorted({x['placement'] for x in items})},
  quality={k:metrics([x for x in items if x['quality']==k]) for k in sorted({x['quality'] for x in items})},
  abstention_reasons=dict(collections.Counter(r for x in items for r in x['abstention_reasons'])))
 save('evaluation.json',result);print(json.dumps(result['overall'],ensure_ascii=False))
if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser();parser.add_argument('--output-dir',type=pathlib.Path)
 args=parser.parse_args()
 if args.output_dir:
  OUTPUT=args.output_dir;OUTPUT.mkdir(parents=True,exist_ok=False)
 main()

