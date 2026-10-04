"""Opt-in authenticated private-network receiver; stdlib, no secret logs."""
import base64
import binascii
import hashlib
import hmac
import ipaddress
import json
import re
import secrets
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from .context import MAX_AGE_MS, validate_envelope

VERSION = 'phone-wire-v1'
MAX_BODY = 16384
CHALLENGE_MS = 3000


def _pairs(items):
    value = {}
    for key, item in items:
        if key in value:
            raise ValueError('duplicate_key')
        value[key] = item
    return value


def _bad_constant(value):
    raise ValueError('nonfinite_json')


def parse_json(raw):
    value = json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs, parse_constant=_bad_constant)
    if not isinstance(value, dict):
        raise ValueError('object_required')
    return value


def signature(secret_hex, epoch, session_id, challenge, payload_b64):
    message = '\n'.join(('context-v1', epoch, session_id, challenge, payload_b64)).encode('utf-8')
    return hmac.new(bytes.fromhex(secret_hex), message, hashlib.sha256).hexdigest()


class PhoneReceiver:
    def __init__(self, engine, allow_test=False, clock=None):
        self.engine = engine
        self.allow_test = allow_test
        self._clock = clock or (lambda: time.monotonic_ns() / 1_000_000)
        self._lock = threading.RLock()
        self._server = None
        self._thread = None
        self._session = None
        self._secret = None
        self._epoch = None
        self._challenges = {}
        self._sequence = -1
        self._last_error = None
        self._accepted_count = 0
        self._active_socket = None

    def start(self, host='127.0.0.1', port=0):
        address = ipaddress.ip_address(host)
        private = any(address in ipaddress.ip_network(net) for net in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16')) if address.version == 4 else False
        if address.version != 4 or not (address.is_loopback or private) or type(port) is not int or not 0 <= port <= 65535:
            raise ValueError('explicit_private_ipv4_required')
        with self._lock:
            if self._server:
                raise ValueError('already_started')
            receiver = self

            class Handler(BaseHTTPRequestHandler):
                protocol_version = 'HTTP/1.0'

                def setup(self):
                    super().setup()
                    self.connection.settimeout(1.0)
                    with receiver._lock:
                        receiver._active_socket = self.connection
                    # Inactivity timeouts alone permit indefinitely slow clients.
                    self._deadline = threading.Timer(3.0, self._close_request)
                    self._deadline.daemon = True
                    self._deadline.start()

                def _close_request(self):
                    try:
                        self.connection.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass

                def finish(self):
                    self._deadline.cancel()
                    with receiver._lock:
                        if receiver._active_socket is self.connection:
                            receiver._active_socket = None
                    super().finish()

                def log_message(self, *args):
                    pass

                def _reply(self, status, value):
                    raw = json.dumps(value, ensure_ascii=True, allow_nan=False).encode('utf-8')
                    try:
                        self.send_response(status)
                        self.send_header('Content-Type', 'application/json')
                        self.send_header('Content-Length', str(len(raw)))
                        self.send_header('Cache-Control', 'no-store')
                        self.end_headers()
                        self.wfile.write(raw)
                    except OSError:
                        pass  # Peer cancellation/receiver stop has no successful delivery.

                def do_POST(self):
                    try:
                        sizes = self.headers.get_all('Content-Length', [])
                        if self.headers.get('Transfer-Encoding') is not None or len(sizes) != 1 or not sizes[0].isdigit():
                            self._reply(400, {'ok': False, 'error': 'invalid_framing'})
                            return
                        size = int(sizes[0])
                        if size > MAX_BODY:
                            self._reply(413, {'ok': False, 'error': 'body_too_large'})
                            return
                        raw = self.rfile.read(size)
                        if len(raw) != size:
                            raise ValueError('truncated_body')
                        data = parse_json(raw)
                        code, result = receiver._request(self.path, data)
                        self._reply(code, result)
                    except (ValueError, UnicodeError, RecursionError, OverflowError):
                        self._reply(400, {'ok': False, 'error': 'malformed_json'})
                    except (OSError, TimeoutError):
                        return

                def do_GET(self):
                    self._reply(405, {'ok': False, 'error': 'post_required'})

            self._server = HTTPServer((host, port), Handler)
            self._epoch = secrets.token_hex(16)
            self._thread = threading.Thread(target=self._server.serve_forever, kwargs={'poll_interval': 0.1}, daemon=True)
            self._thread.start()
            return self.status()

    def pair(self, session_id):
        if not isinstance(session_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,128}', session_id):
            raise ValueError('invalid_session_id')
        with self._lock:
            if not self._server:
                raise ValueError('receiver_disabled')
            self._session = session_id
            self._secret = secrets.token_hex(32)
            self._challenges.clear()
            self._sequence = -1
            self.engine.disconnect('session_repaired')
            return dict(session_id=session_id, secret_hex=self._secret, receiver_epoch=self._epoch, url=self._url())

    def _url(self):
        host, port = self._server.server_address
        return 'http://%s:%d' % (host, port)

    def status(self):
        with self._lock:
            return dict(enabled=self._server is not None, paired=self._session is not None,
                url=self._url() if self._server else None, receiver_epoch=self._epoch,
                accepted_count=self._accepted_count, last_error=self._last_error,
                allow_test=self.allow_test, protocol_version=VERSION)

    def stop(self):
        with self._lock:
            server, thread = self._server, self._thread
            active_socket = self._active_socket
            self._server = None
            self._thread = None
            self._session = None
            self._secret = None
            self._epoch = None
            self._challenges.clear()
            self._sequence = -1
            self.engine.disconnect('receiver_stopped')
        if server:
            if active_socket:
                try:
                    active_socket.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
        return self.status()

    def _reject(self, error, code=403):
        self._last_error = error
        return code, {'ok': False, 'error': error}

    def _request(self, path, data):
        with self._lock:
            if self._server is None or self._session is None or data.get('session_id') != self._session:
                return self._reject('unpaired_session')
            now = self._clock()
            if path == '/challenge':
                self._challenges = {key: issued for key, issued in self._challenges.items() if 0 <= now - issued <= CHALLENGE_MS}
                if len(self._challenges) >= 32:
                    return self._reject('challenge_limit', 429)
                challenge = secrets.token_hex(24)
                self._challenges[challenge] = now
                return 200, dict(ok=True, schema_version=1, receiver_epoch=self._epoch, challenge=challenge, expires_in_ms=CHALLENGE_MS)
            if path != '/context':
                return self._reject('unknown_endpoint', 404)
            if any(not isinstance(data.get(key), str) for key in ('receiver_epoch', 'challenge', 'payload_b64', 'mac')):
                return self._reject('invalid_fields', 400)
            if not re.fullmatch(r'[0-9a-f]{64}', data['mac']):
                return self._reject('invalid_mac', 400)
            if data['receiver_epoch'] != self._epoch:
                return self._reject('receiver_epoch_mismatch')
            challenge = data['challenge']
            issued = self._challenges.get(challenge)
            if issued is None:
                return self._reject('unknown_or_used_challenge')
            expected = signature(self._secret, self._epoch, self._session, challenge, data['payload_b64'])
            if not hmac.compare_digest(expected, data['mac']):
                return self._reject('authentication_failed')
            del self._challenges[challenge]
            elapsed = now - issued
            if not 0 <= elapsed <= CHALLENGE_MS:
                return self._reject('challenge_expired')
            try:
                payload = base64.b64decode(data['payload_b64'], validate=True)
                envelope = validate_envelope(parse_json(payload))
            except (ValueError, UnicodeError, binascii.Error, RecursionError, OverflowError):
                return self._reject('invalid_envelope', 400)
            if envelope['session_id'] != self._session:
                return self._reject('payload_session_mismatch')
            if envelope['sequence'] <= self._sequence:
                return self._reject('duplicate_or_out_of_order', 409)
            if envelope['source_kind'] == 'test_fixture' and not self.allow_test:
                return self._reject('test_source_disabled')
            if envelope['historical'] or envelope['source_kind'] == 'historical_replay':
                return self._reject('historical_not_live', 422)
            self._sequence = envelope['sequence']
            observed, sent = envelope['observed_elapsed_ms'], envelope['sent_elapsed_ms']
            if observed is None or sent is None:
                age = None
            elif observed < 0 or sent < observed:
                self.engine.disconnect('invalid_source_age')
                return self._reject('invalid_source_age', 422)
            else:
                age = sent - observed + elapsed
            context = self.engine.ingest(envelope, age_upper_bound_ms=age)
            if age is not None and age > MAX_AGE_MS:
                return self._reject('source_expired', 422)
            self._accepted_count += 1
            self._last_error = None
            return 200, {'ok': True, 'context': context}
