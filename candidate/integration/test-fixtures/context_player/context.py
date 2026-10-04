"""Evidence-preserving context state. All local clocks return milliseconds."""
import copy
import math
import threading
import time
import uuid

VERSION = 'context-v1'
MAX_AGE_MS = 10000
STABILITY_MS = 1000
ACTIVITIES = {'unknown', 'stationary', 'walking', 'running', 'cycling', 'vehicle', 'reading', 'workout', 'relax'}
AUTOMATIC = {'unknown', 'stationary', 'walking', 'running', 'cycling', 'vehicle'}
SOURCES = {'manual', 'sdk', 'offline_rule', 'historical_replay', 'test_fixture'}


def valid_number(value):
    return type(value) in (int, float) and math.isfinite(value)


def validate_envelope(value):
    if not isinstance(value, dict) or value.get('schema_version') != 1 or type(value.get('schema_version')) is not int:
        raise ValueError('invalid_schema')
    if not isinstance(value.get('source_kind'), str) or value['source_kind'] not in SOURCES:
        raise ValueError('invalid_source')
    for field in ('source_version', 'session_id', 'mapping_basis', 'score_semantics', 'quality'):
        if not isinstance(value.get(field), str) or not value[field] or len(value[field]) > 256:
            raise ValueError('invalid_' + field)
    if type(value.get('sequence')) is not int or not 0 <= value['sequence'] < 2**53:
        raise ValueError('invalid_sequence')
    if type(value.get('raw_activity')) not in (str, int) or len(str(value['raw_activity'])) > 256:
        raise ValueError('invalid_raw_activity')
    if not isinstance(value.get('activity'), str) or value['activity'] not in ACTIVITIES:
        raise ValueError('invalid_activity')
    if value['source_kind'] == 'manual' and value['raw_activity'] != value['activity']:
        raise ValueError('manual_mapping_must_be_explicit_identity')
    for field in ('raw_score', 'observed_wall_ms', 'observed_elapsed_ms', 'sent_elapsed_ms'):
        if field not in value or (value[field] is not None and not valid_number(value[field])):
            raise ValueError('invalid_' + field)
    if type(value.get('historical')) is not bool:
        raise ValueError('invalid_historical')
    reasons = value.get('reasons')
    if not isinstance(reasons, list) or len(reasons) > 32 or any(not isinstance(r, str) or len(r) > 256 for r in reasons):
        raise ValueError('invalid_reasons')
    return copy.deepcopy(value)


class ContextEngine:
    def __init__(self, clock=None, wall_clock=None):
        self._clock = clock or (lambda: time.monotonic_ns() / 1_000_000)
        self._wall = wall_clock or (lambda: time.time_ns() / 1_000_000)
        self._lock = threading.RLock()
        self._manual = None
        self._live = None
        self._candidate = None
        self._accepted = False
        self._reason = 'no_observation'
        self._conflicts = []

    def set_manual(self, activity, ttl_ms=1800000):
        if activity not in ACTIVITIES or not valid_number(ttl_ms) or not 0 < ttl_ms <= 86400000:
            raise ValueError('invalid_manual_context')
        with self._lock:
            now = self._clock()
            self._manual = dict(schema_version=1, source_kind='manual', source_version=VERSION,
                session_id=str(uuid.uuid4()), sequence=0, raw_activity=activity, activity=activity,
                mapping_basis='explicit_user_input', raw_score=None, score_semantics='not_a_probability',
                observed_wall_ms=self._wall(), observed_elapsed_ms=None, sent_elapsed_ms=None,
                received_wall_ms=self._wall(), age_upper_bound_ms=0, freshness='fresh', quality='explicit',
                reasons=[], historical=False, allowed_for_current=activity != 'unknown',
                expires_at_local_ms=now + ttl_ms)
            return self.snapshot()

    def clear_manual(self):
        with self._lock:
            self._manual = None
            return self.snapshot()

    def disconnect(self, reason='disconnected'):
        with self._lock:
            self._live = None
            self._candidate = None
            self._accepted = False
            self._reason = reason
            return self.snapshot()

    def ingest(self, envelope, age_upper_bound_ms=None):
        value = validate_envelope(envelope)
        with self._lock:
            now = self._clock()
            previous = self._live
            value['received_wall_ms'] = self._wall()
            value['allowed_for_current'] = False
            value['age_upper_bound_ms'] = age_upper_bound_ms
            value['reasons'] = list(value['reasons'])
            historical = value['historical'] or value['source_kind'] == 'historical_replay'
            value['historical'] = historical
            if historical:
                value['freshness'] = 'historical'
                value['reasons'].append('historical_not_current')
            elif value['observed_elapsed_ms'] is None or value['sent_elapsed_ms'] is None or not valid_number(age_upper_bound_ms) or age_upper_bound_ms < 0:
                value['freshness'] = 'unverifiable'
                value['reasons'].append('source_time_unverifiable')
            elif value['observed_elapsed_ms'] < 0 or value['sent_elapsed_ms'] < value['observed_elapsed_ms'] or age_upper_bound_ms < value['sent_elapsed_ms'] - value['observed_elapsed_ms']:
                value['freshness'] = 'unverifiable'
                value['reasons'].append('invalid_source_age')
            elif age_upper_bound_ms > MAX_AGE_MS:
                value['freshness'] = 'expired'
                value['reasons'].append('source_expired')
            else:
                value['freshness'] = 'fresh'
            if value['source_kind'] != 'manual':
                raw = value['raw_activity']
                # No undocumented integer SDK mappings or semantic expansion.
                mapped = raw.lower() if isinstance(raw, str) and raw.lower() in AUTOMATIC else 'unknown'
                if mapped != value['activity']:
                    value['reasons'].append('mapping_not_supported')
                value['activity'] = mapped
            if value['quality'] not in ('ok', 'good', 'explicit'):
                value['reasons'].append('quality_not_usable')
                value['activity'] = 'unknown'
            if previous and previous['envelope']['activity'] != value['activity']:
                self._conflicts.append(dict(previous_source=previous['envelope']['source_kind'],
                    previous_activity=previous['envelope']['activity'], incoming_source=value['source_kind'],
                    incoming_activity=value['activity'], policy='latest_observation_requires_stability'))
                self._conflicts = self._conflicts[-8:]
            self._live = {'envelope': value, 'received': now}
            if value['freshness'] != 'fresh' or value['activity'] == 'unknown':
                self._candidate = None
                self._accepted = False
                self._reason = value['reasons'][-1] if value['reasons'] else 'unknown_activity'
            else:
                key = (value['source_kind'], value['session_id'], value['activity'])
                if self._candidate is None or self._candidate['key'] != key or now < self._candidate['since'] or now - self._candidate['since'] > MAX_AGE_MS:
                    self._candidate = {'key': key, 'since': now, 'sequence': value['sequence']}
                    self._accepted = False
                elif value['sequence'] > self._candidate['sequence'] and now - self._candidate['since'] >= STABILITY_MS:
                    self._accepted = True
                self._reason = 'stable' if self._accepted else 'stabilizing'
            return self.snapshot()

    def snapshot(self):
        with self._lock:
            now = self._clock()
            if self._manual is not None and now >= self._manual['expires_at_local_ms']:
                self._manual = None
            if self._manual:
                result = copy.deepcopy(self._manual)
                result['manual_remaining_ms'] = max(0, self._manual['expires_at_local_ms'] - now)
                if self._live and self._live['envelope']['activity'] != result['activity']:
                    result['reasons'].append('manual_priority_over_' + self._live['envelope']['source_kind'])
                    result['suppressed_observation'] = copy.deepcopy(self._live['envelope'])
            elif self._live:
                result = copy.deepcopy(self._live['envelope'])
                age = result['age_upper_bound_ms']
                residence = now - self._live['received']
                if valid_number(age):
                    result['age_upper_bound_ms'] = age + max(0, residence)
                if residence < 0:
                    result['freshness'] = 'unverifiable'
                    result['reasons'].append('local_clock_reversed')
                    self._accepted = False
                    self._candidate = None
                elif valid_number(age) and age + residence > MAX_AGE_MS:
                    result['freshness'] = 'expired'
                    result['reasons'].append('source_expired')
                    self._accepted = False
                    self._candidate = None
                result['observed_activity'] = result['activity']
                if not self._accepted or result['freshness'] != 'fresh':
                    result['activity'] = 'unknown'
                    result['reasons'].append(self._reason)
                result['allowed_for_current'] = result['activity'] != 'unknown' and result['freshness'] == 'fresh'
            else:
                result = dict(schema_version=1, activity='unknown', source_kind=None, freshness='unverifiable',
                    historical=False, allowed_for_current=False, age_upper_bound_ms=None, reasons=[self._reason])
            result['conflicts'] = copy.deepcopy(self._conflicts)
            result['stability_delay_ms'] = STABILITY_MS
            result['context_version'] = VERSION
            return result
