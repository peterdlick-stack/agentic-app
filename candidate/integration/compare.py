"""Local comparison console. Isolated local console; existing platform UI is unchanged."""
import argparse,json,sys,time,uuid,subprocess,os
from pathlib import Path
R=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(R),str(R/'integration')]
from context_player.recommend import load_catalog,parse_request,verify_track
from learner.model import rank,digest
from learner.store import EvidenceStore
LIBRARY=Path('/mnt/f/context-player-cache-20261004')

def features():
    p=R/'audio/features.json'
    return json.loads(p.read_text(encoding='utf-8-sig')) if p.exists() else []

def select(policy='P0',activity='unknown',request='',limit=4,state=None):
    state=Path(state or R/'integration/state');state.mkdir(parents=True,exist_ok=True)
    rows=features();now=time.time();context=dict(activity=activity,source_kind='manual',observed_at=now,valid_until=now+1800,allowed_for_current=activity!='unknown',historical=False)
    c=parse_request(request);catalog=load_catalog(LIBRARY,verify_all=False)
    # Original trusted metadata only for hard constraints; side-table estimates are soft.
    previous_file=state/policy/'latest.json'
    previous=json.loads(previous_file.read_text()).get('tracks',[]) if previous_file.exists() else []
    previous_ids={t['content_id'] for t in previous} if c['exclude_previous'] else set()
    eligible=[]
    for t in catalog:
        if t['content_id'] in previous_ids:continue
        if c['vocal_policy']=='none' and t['vocal'] is not False:continue
        if c['vocal_policy']=='required' and t['vocal'] is not True:continue
        if (c['min_bpm'] is not None or c['max_bpm'] is not None) and t['bpm'] is None:continue
        if c['min_bpm'] is not None and t['bpm']<c['min_bpm']:continue
        if c['max_bpm'] is not None and t['bpm']>c['max_bpm']:continue
        eligible.append(t)
    store=EvidenceStore(state/policy)
    try:
        model=json.loads((R/'learner/state/model.json').read_text()) # Frozen UNTRAINED; no training in repair scope
        rank_policy=policy
        pred=rank(eligible,rows,context,store.preferences('P0' if rank_policy=='P0' or policy=='P2' and model['status']!='TRAINED' else policy),rank_policy,model,now=time.time())
        selected=[];rejected=[]
        for t in pred['tracks']:
            if len(selected)>=limit:break
            try:verify_track(t)
            except (ValueError,OSError) as exc:rejected.append({'content_id':t['content_id'],'reason':str(exc)});continue
            selected.append(t)
        pred.update(tracks=selected,rejected=rejected,context=context,policy=pred['effective_policy'],feature_version=digest(rows),feature_hash=digest(rows),request=request,feature_status='FEATURES_ESTIMATED',platform_integration='NOT_TESTED_EXISTING_UI',interface='standalone_local_console')
        sid=str(uuid.uuid4());pred['snapshot_id']=sid
        if selected:store.snapshot(sid,pred)
        (state/policy/'latest.json').write_text(json.dumps(pred,ensure_ascii=False,indent=2))
        return pred
    finally:store.close()

def play(track,seconds=20):
    verify_track(track)
    win='F:\\context-player-cache-20261004\\'+track['path'].replace('/','\\')
    script=json.loads((R/'repair-config.json').read_text())['E1_windows']+'/play.ps1'
    result=subprocess.run(['powershell.exe','-NoProfile','-File',script,'-AudioPath',win,'-Seconds',str(seconds)],capture_output=True,text=True,timeout=seconds+30)
    if result.returncode:raise RuntimeError('playback_failed:'+result.stdout+result.stderr)
    return result.stdout

def interact():
    print('隔离情境音乐比较。P0默认；P1为可选软排序；P2未训练时明确回退。不是正式收益试验。输入 q 退出。')
    session=str(uuid.uuid4());touched=set()
    while True:
        policy=input('策略 P0/P1/P2 [P0]：').strip() or 'P0'
        if policy.lower()=='q':break
        activity=input('场景 unknown/walking/reading/relax [unknown]：').strip() or 'unknown'
        request=input('要求（可留空；未知BPM/人声不会满足硬约束）：').strip()
        try:
            pred=select(policy,activity,request)
            print(pred['status'], '实际策略',pred['effective_policy'])
            for i,t in enumerate(pred['tracks']):print(i+1,t.get('title',t['id']))
            choice=input('播放哪首20秒？回车跳过：').strip()
            if not choice:continue
            track=pred['tracks'][int(choice)-1]
            if int(choice)<1:raise ValueError('invalid_selection')
            store=EvidenceStore(R/'integration/state'/policy);touched.add(policy)
            try:
                # Exposure stored before playback; labels only after explicit human response.
                eid=str(uuid.uuid4());at=time.time();store.expose(eid,pred['snapshot_id'],track['content_id'],session,at)
                print(play(track))
                for target,prompt in ([('scenario_acceptance','此场景愿意听？')] if pred['effective_activity'] not in ('unknown','stationary') else [])+[('song_like','单纯喜欢这首歌？')]:
                    answer=input(prompt+' y/n/回车未知：').strip().lower()
                    if answer not in ('y','n',''):raise ValueError('answer_y_n_or_empty')
                    event=dict(event_id=str(uuid.uuid4()),session_id=session,exposure_id=eid,snapshot_id=pred['snapshot_id'],content_id=track['content_id'],policy=pred['policy'],context=pred['context'],feature_version=pred['feature_version'],target=target,value={'y':1,'n':0,'':None}[answer],exposed_at=at,recorded_at=time.time(),provenance='real_user',snapshot=pred)
                    store.record(event)
            finally:store.close()
        except (ValueError,RuntimeError,IndexError) as exc:print('未完成：',exc)
    for policy in touched:
        s=EvidenceStore(R/'integration/state'/policy)
        try:s.complete_session(session)
        finally:s.close()

def main():
    p=argparse.ArgumentParser();p.add_argument('--interactive',action='store_true');p.add_argument('--policy',choices=['P0','P1','P2'],default='P0');p.add_argument('--activity',default='unknown');p.add_argument('--request',default='');p.add_argument('--state');p.add_argument('--limit',type=int,default=4);a=p.parse_args()
    if a.interactive:interact()
    else:print(json.dumps(select(a.policy,a.activity,a.request,a.limit,a.state),ensure_ascii=False,indent=2))
if __name__=='__main__':main()


