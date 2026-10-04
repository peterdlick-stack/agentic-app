"""Private JSON-lines host bridge. EOF stops the opt-in phone receiver."""
import argparse
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import uuid

from context_player.context import ContextEngine
from context_player.transport import PhoneReceiver
from context_player.recommend import load_catalog, recommend, verify_track
from context_player.feedback import FeedbackStore
from context_player.experiments import ExperimentTrial

VERSION = 'context-player-1.0.0'

def selection_from_snapshot(snapshot, mode, condition, trial_id=None):
    tracks=snapshot['tracks']
    constraints=snapshot.get('constraints', {})
    return dict(ids=[t['id'] for t in tracks], reason='依据已标注节奏与显式反馈排序；缺少情境时使用普通偏好。',
        vocal_policy='prefer' if constraints.get('vocal_policy') == 'required' else constraints.get('vocal_policy','any'),
        min_bpm=int(constraints.get('min_bpm') or 0), max_bpm=int(constraints.get('max_bpm') or 240),
        target_seconds=round(sum(t['duration'] for t in tracks)), _request=snapshot.get('request',''),
        _context=snapshot['context'], _snapshot_id=snapshot['snapshot_id'], _mode=mode, _condition=condition,
        _local_context=True, _trial_id=trial_id, _track_reasons={t['id']:t['reason'] for t in tracks},
        _content_hashes={t['id']:t['sha256'] for t in tracks})

def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    with temp.open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, allow_nan=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, path)

class Backend:
    def __init__(self, root, state, allow_test=False):
        self.root, self.state = Path(root).resolve(), Path(state).resolve()
        # Launcher explicitly validates this read-only shared library target.
        self.catalog_root = (self.root/'library').resolve().parent
        self.state.mkdir(parents=True, exist_ok=True)
        self.engine = ContextEngine()
        self.receiver = PhoneReceiver(self.engine, allow_test=allow_test)
        self.allow_test = allow_test
        self.mode, self.condition = 'normal', 'C'
        self.history = None
        self.trial = None
        self.trial_config = None
        self.stores = {}
        self.restore_error = None
        try:
            if (self.state/'settings.json').exists():
                saved = json.loads((self.state/'settings.json').read_text())
                if saved.get('mode') not in ('normal', 'history', 'live') or saved.get('condition') not in ('A', 'B', 'C'):
                    raise ValueError('invalid saved mode')
                self.mode, self.condition = saved['mode'], saved['condition']
                self.history = saved.get('history')
                self.trial_config = saved.get('trial')
                if self.trial_config:
                    cfg = self.trial_config
                    uuid.UUID(cfg['id'])
                    self.trial = ExperimentTrial(self.state/'trials'/cfg['id'], load_catalog(self.catalog_root, verify_all=False), cfg['id'], cfg['request'], cfg.get('limit',2))
        except (OSError, ValueError) as e:
            self.restore_error = str(e)

    def store(self):
        if self.trial:
            return self.trial.stores[self.condition]
        scope = ('history' if self.mode == 'history' else 'current') + '-' + self.condition
        if scope not in self.stores:
            self.stores[scope] = FeedbackStore(self.state / scope)
        return self.stores[scope]

    def persist(self):
        atomic_json(self.state/'settings.json', {'mode': self.mode, 'condition': self.condition, 'history': self.history, 'trial': self.trial_config})

    def context(self):
        if self.mode == 'history':
            return copy.deepcopy(self.history or dict(activity='unknown', source_kind='historical_replay', freshness='historical', historical=True, allowed_for_current=False, reasons=['no_history_loaded']))
        result = self.engine.snapshot()
        if self.mode == 'normal' and result.get('source_kind') != 'manual':
            return dict(activity='unknown', source_kind='manual', freshness='unverifiable', historical=False, allowed_for_current=False, reasons=['ordinary_preference_mode'])
        return result

    def status(self):
        return {'version': VERSION, 'mode': self.mode, 'condition': self.condition, 'context': self.context(), 'receiver': self.receiver.status(), 'restore_error': self.restore_error, 'test_mode': self.allow_test,
                'trial': None if not self.trial else {'id':self.trial_config['id'], 'round':self.trial_config['round'], 'order':self.trial.protocol['order'], 'index':self.trial_config['index'], 'meaning':'fixed_round_snapshot_not_live_activity'}}

    def trial_round(self):
        return self.trial.create_round('round-'+str(self.trial_config['round']), self.trial_config['context'])

    def history_import(self, request):
        source = Path(__file__).resolve().parents[1]/'platform/crates/music-plugin-p40-replay/tools'
        if str(source) not in sys.path:
            sys.path.insert(0, str(source))
        from replay import replay
        result = replay({'file': request['file'], 'relative_seconds': request.get('relative_seconds', '0')})
        prediction = result['activity_prediction']
        # Reference/manual labels and filename are deliberately absent from rank inputs.
        context = dict(schema_version=1, source_kind='historical_replay', source_version=prediction.get('algorithm_version', 'unknown'),
            session_id=result['import']['session_id'], sequence=0, raw_activity=prediction.get('result', 'unknown'),
            activity=prediction.get('result', 'unknown'), mapping_basis='unchanged offline phone-motion prediction; not human activity',
            raw_score=None, score_semantics='uncalibrated_rule', observed_wall_ms=None,
            observed_elapsed_ms=int(result['query_interval_elapsed_ns'][0])/1e6,
            sent_elapsed_ms=None, received_wall_ms=int(time.time()*1000), age_upper_bound_ms=None,
            freshness='historical', historical=True, experiment_mode=True, allowed_for_current=False,
            quality=prediction.get('quality_status', 'unknown'), reasons=prediction.get('abstention_reasons', []),
            input_sha256=result['import']['sha256'], cursor_seconds=result['cursor_seconds'])
        self.history = context
        self.mode = 'history'
        self.persist()
        return {'context': context, 'message': '历史实验已载入；只使用原离线预测，未读取本人标签作推荐特征。'}

    def dispatch(self, request):
        op = request.get('op')
        if op == 'status':
            return self.status()
        if op == 'mode':
            mode, condition = request.get('mode'), request.get('condition', self.condition)
            if mode not in ('normal', 'history', 'live') or condition not in ('A', 'B', 'C'):
                raise ValueError('invalid mode/condition')
            if self.trial:
                raise ValueError('试用期间请按预定顺序点击下一条件，或先结束试用')
            if mode != 'live':
                self.receiver.stop()
            self.mode, self.condition = mode, condition
            self.persist()
        elif op == 'manual':
            activity = request['activity']
            if self.mode == 'history':
                raise ValueError('历史实验不接受当前活动覆盖；请切回普通模式')
            observed = self.context()
            self.store().record_activity_correction(str(uuid.uuid4()), observed, activity)
            self.engine.set_manual(activity, request.get('ttl_ms', 1800000))
        elif op == 'clear_manual':
            self.engine.clear_manual()
        elif op == 'history':
            if self.trial:
                raise ValueError('请先结束固定输入试用，再更换历史记录')
            self.receiver.stop()
            return {**self.history_import(request), 'status': self.status()}
        elif op == 'connect':
            if self.mode != 'live':
                raise ValueError('先显式选择实时手机模式')
            return {'connection': self.receiver.start(host=request.get('host', '127.0.0.1'), port=request.get('port', 0)), 'status': self.status()}
        elif op == 'pair':
            if self.mode != 'live':
                raise ValueError('实时手机模式未启用')
            # Only this reply carries secret. Host must display ephemerally, never snapshot/log.
            return {'pairing': self.receiver.pair(request['session_id']), 'status': self.status()}
        elif op == 'disconnect':
            self.receiver.stop()
            self.engine.disconnect()
        elif op == 'recommend':
            if self.trial:
                if request.get('request','') != self.trial_config['request']:
                    raise ValueError('试用请求已冻结；请恢复本轮请求或结束试用后更改')
                snapshot = self.trial_round()['snapshots'][self.condition]
                rec = snapshot
                context = rec['context']
                for track in rec['tracks']:
                    verify_track(track)
            else:
                catalog = load_catalog(self.catalog_root, verify_all=False)
                context = self.context()
                context['previous_ids'] = request.get('previous_ids', [])
                if self.condition == 'A':
                    context = dict(activity='unknown', source_kind='manual', freshness='unverifiable', historical=self.mode == 'history', allowed_for_current=False, reasons=['condition_A_no_context'], previous_ids=request.get('previous_ids', []))
                rec = recommend(catalog, context, self.store().preferences(condition=self.condition), request=request.get('request', ''), limit=4)
                snapshot = self.store().create_snapshot(rec, condition=self.condition)
            selection = selection_from_snapshot(snapshot,self.mode,self.condition,self.trial_config['id'] if self.trial else None)
            return {'selection': selection, 'recommendation': rec, 'status': self.status()}
        elif op == 'restore_queue':
            scope = 'trials/'+self.trial_config['id']+'/'+self.condition if self.trial else ('history' if self.mode == 'history' else 'current') + '-' + self.condition
            filename = 'live-queue.json' if self.mode == 'live' and not self.trial else 'queue.json'
            selection = json.loads((self.state/scope/filename).read_text())
            frozen = self.store().get_snapshot(selection['_snapshot_id'])
            if selection.get('_mode') != self.mode or selection.get('_condition') != self.condition or selection.get('ids') != [t['id'] for t in frozen['tracks']]:
                raise ValueError('saved_queue_snapshot_mismatch')
            canonical=selection_from_snapshot(frozen,self.mode,self.condition,self.trial_config['id'] if self.trial else None)
            if selection != canonical:
                raise ValueError('saved_queue_metadata_modified')
            for track in frozen['tracks']:
                verify_track(track)
            return {'selection': canonical, 'status': self.status()}
        elif op == 'feedback':
            if request.get('mode') != self.mode or request.get('condition') != self.condition:
                raise ValueError('模式已改变；请对当前模式的已载入推荐评价')
            if request.get('trial_id') != (self.trial_config['id'] if self.trial else None):
                raise ValueError('试用已改变；请重新载入对应歌单')
            result = self.store().record(request['event_id'], request['snapshot_id'], request['track_id'], request['value'])
            return {'feedback': result, 'status': self.status()}
        elif op == 'trial_start':
            if self.trial or self.mode == 'live':
                raise ValueError('请在普通/历史模式中开始一次新的固定输入试用')
            ident = str(uuid.uuid4())
            candidate = ExperimentTrial(self.state/'trials'/ident, load_catalog(self.catalog_root, verify_all=False), ident, request.get('request',''),2)
            config = {'id':ident,'request':request.get('request',''),'limit':2,'round':1,'index':0,'context':self.context()}
            old_condition=self.condition
            try:
                candidate.create_round('round-1',config['context'])
                self.trial, self.trial_config = candidate, config
                self.condition = candidate.protocol['order'][0]
                self.persist()
            except Exception:
                candidate.close()
                self.trial,self.trial_config,self.condition=None,None,old_condition
                raise
        elif op == 'trial_next':
            if not self.trial:
                raise ValueError('尚未开始试用')
            old_config,old_condition=copy.deepcopy(self.trial_config),self.condition
            try:
                index = self.trial_config['index']+1
                if index == 3:
                    self.trial_config['round'] += 1
                    self.trial_config['context'] = self.context()
                    self.trial_round()
                    index = 0
                self.trial_config['index'] = index
                self.condition = self.trial.protocol['order'][index]
                self.persist()
            except Exception:
                self.trial_config,self.condition=old_config,old_condition
                raise
        elif op == 'trial_observe':
            if not self.trial or request.get('trial_id') != self.trial_config['id'] or request.get('condition') != self.condition:
                raise ValueError('请先载入当前试用条件的推荐歌曲')
            result = self.trial.record_observation(request['event_id']+':observation', self.condition, request['snapshot_id'], request['track_id'],
                accepted=request.get('accepted'), disturbance=request.get('disturbance'))
            return {'message':'试用感受已保存；留空项目仍为缺失', 'observation':result, 'status':self.status()}
        elif op == 'trial_report':
            if not self.trial:
                raise ValueError('尚未开始试用')
            output=self.trial.root/'report.json'
            atomic_json(output,self.trial.report())
            return {'message':'试用记录已导出：'+str(output), 'status':self.status()}
        elif op == 'trial_end':
            if self.trial:
                atomic_json(self.trial.root/'report.json',self.trial.report())
                self.trial.close()
            self.trial=None
            self.trial_config=None
            self.condition='C'
            self.persist()
        elif op == 'stop':
            self.close()
            return {'stopped': True}
        else:
            raise ValueError('unknown operation')
        return self.status()

    def close(self):
        self.receiver.stop()
        if self.trial:
            self.trial.close()
        for store in self.stores.values():
            store.close()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True)
    parser.add_argument('--state', required=True)
    parser.add_argument('--test-mode', action='store_true')
    args = parser.parse_args()
    backend = Backend(args.root, args.state, args.test_mode)
    try:
        for line in sys.stdin:
            try:
                if len(line.encode('utf-8')) > 65536:
                    raise ValueError('host request too large')
                request = json.loads(line)
                result = {'ok': True, 'result': backend.dispatch(request)}
            except Exception as e:
                result = {'ok': False, 'error': type(e).__name__ + ': ' + str(e)}
            print(json.dumps(result, ensure_ascii=False, allow_nan=False), flush=True)
            if result.get('result', {}).get('stopped'):
                break
    finally:
        backend.close()

if __name__ == '__main__':
    main()
