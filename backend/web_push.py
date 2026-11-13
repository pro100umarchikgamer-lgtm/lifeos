"""Opt-in, encrypted Web Push delivery for authorized cloud calendar events.

The existing mail worker runs this small queue as well. No browser-open timer,
external scheduler, provider account, or new operator secret is required.
"""
import base64
import calendar
import datetime as dt
import hashlib
import hmac
import ipaddress
import json
import logging
import os
import re
import secrets
import socket
import struct
import uuid
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import jwt
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .service import Failure, canonical, identifier, require, token_hash

PROVIDERS = frozenset({'fcm.googleapis.com', 'updates.push.services.mozilla.com', 'web.push.apple.com'})
LEADS = frozenset({5, 15, 30, 60})
UTC = dt.timezone.utc
log = logging.getLogger('lifeos.web_push')


def b64(value):
    return base64.urlsafe_b64encode(value).rstrip(b'=').decode('ascii')


def unb64(value):
    require(isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_-]+', value), 'push_subscription_invalid')
    try: return base64.b64decode(value + '=' * (-len(value) % 4), altchars=b'-_', validate=True)
    except (ValueError, TypeError): raise Failure('push_subscription_invalid')


def validate_subscription(value):
    require(isinstance(value, dict), 'push_subscription_invalid')
    endpoint, keys = value.get('endpoint'), value.get('keys')
    require(isinstance(endpoint, str) and len(endpoint) <= 2048 and not re.search(r'[\s\\\x00-\x1f\x7f]', endpoint), 'push_endpoint_invalid')
    try:
        url = urlsplit(endpoint)
        # A fixed set of HTTPS provider authorities prevents arbitrary server
        # fetches, IP literals, userinfo, alternative ports, and DNS suffix tricks.
        require(url.scheme == 'https' and url.netloc in PROVIDERS and url.hostname in PROVIDERS
                and not url.username and not url.password and url.port is None and not url.fragment
                and url.path.startswith('/') and len(url.path) > 1, 'push_endpoint_invalid')
    except ValueError: raise Failure('push_endpoint_invalid')
    require(isinstance(keys, dict), 'push_subscription_invalid')
    public, auth = unb64(keys.get('p256dh')), unb64(keys.get('auth'))
    require(len(public) == 65 and public[0] == 4 and len(auth) == 16, 'push_subscription_invalid')
    try: ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), public)
    except ValueError: raise Failure('push_subscription_invalid')
    return {'endpoint':endpoint, 'keys':{'p256dh':b64(public), 'auth':b64(auth)}}


def encrypt_message(subscription, plaintext):
    """One RFC 8291 aes128gcm record, with a fresh ECDH key and random salt."""
    require(isinstance(plaintext, bytes) and len(plaintext) <= 3000, 'push_payload_invalid')
    receiver, auth = unb64(subscription['keys']['p256dh']), unb64(subscription['keys']['auth'])
    sender = ec.generate_private_key(ec.SECP256R1())
    public = sender.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    shared = sender.exchange(ec.ECDH(), ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), receiver))
    ikm = HKDF(algorithm=hashes.SHA256(), length=32, salt=auth, info=b'WebPush: info\0' + receiver + public).derive(shared)
    salt = os.urandom(16)
    cek = HKDF(algorithm=hashes.SHA256(), length=16, salt=salt, info=b'Content-Encoding: aes128gcm\0').derive(ikm)
    nonce = HKDF(algorithm=hashes.SHA256(), length=12, salt=salt, info=b'Content-Encoding: nonce\0').derive(ikm)
    return salt + struct.pack('!I', 4096) + bytes([len(public)]) + public + AESGCM(cek).encrypt(nonce, plaintext + b'\x02', None)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, file, code, message, headers, newurl):
        return None


def send_request(endpoint, body, headers):
    # Never follow an endpoint redirect into a different provider or private host.
    host = urlsplit(endpoint).hostname
    require(host in PROVIDERS, 'push_endpoint_invalid')
    addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    require(addresses and all(ipaddress.ip_address(item[4][0]).is_global for item in addresses), 'push_endpoint_invalid')
    try:
        with build_opener(NoRedirect()).open(Request(endpoint, data=body, headers=headers, method='POST'), timeout=5) as response:
            return response.status
    except HTTPError as error:
        error.close()
        return error.code


def wall_time(local, zone):
    """Match calendar JS/Dart: earlier overlap, and move a DST gap forward."""
    candidates = [local.replace(tzinfo=zone, fold=fold) for fold in (0, 1)]
    valid = [candidate.timestamp() for candidate in candidates
             if dt.datetime.fromtimestamp(candidate.timestamp(), zone).replace(tzinfo=None) == local]
    return min(valid) if valid else candidates[0].timestamp()


def occurrences(schedule, subscriber_zone, lower, upper):
    """Yield only a small time window; never materialize years of repeats."""
    base = dt.datetime.fromisoformat(schedule['localStart'])
    zone = ZoneInfo(subscriber_zone if schedule['allDay'] or schedule['timezone'] == 'device' else schedule['timezone'])
    if schedule['allDay']: base = base.replace(hour=9, minute=0, second=0, microsecond=0)
    start = dt.datetime.fromtimestamp(lower, zone).replace(tzinfo=None)
    step, repeat = schedule['interval'], schedule['repeat']
    months = (start.year - base.year) * 12 + start.month - base.month
    near = (months // (step * (12 if repeat == 'yearly' else 1)) if repeat in ('monthly', 'yearly')
            else (start - base).days // (step * (7 if repeat == 'weekly' else 1)))
    first = 0 if repeat == 'none' else max(0, near - 2)
    for number in range(first, first + 12):
        if repeat in ('monthly', 'yearly'):
            month = base.year * 12 + base.month - 1 + number * step * (12 if repeat == 'yearly' else 1)
            year, index = divmod(month, 12)
            if not 1900 <= year <= 2200: break
            local = base.replace(year=year, month=index + 1, day=min(base.day, calendar.monthrange(year, index + 1)[1]))
        else:
            local = base + dt.timedelta(days=number * step * (7 if repeat == 'weekly' else 1)) if repeat != 'none' else base
        day = local.date().isoformat()
        if schedule['until'] and day > schedule['until']: break
        stamp = int(wall_time(local, zone))
        if lower <= stamp <= upper: yield stamp, day
        if stamp > upper or repeat == 'none': break


class WebPush:
    def __init__(self, backend, site='https://getuladim.space', transport=None):
        self.backend, self.site = backend, site.rstrip('/')
        self.transport = transport or send_request
        self.next_scan, self.scan_cursor = 0, ''
        self.event_cursors, self.scan_windows = {}, {}

    def _encrypt(self, value):
        require(hasattr(self.backend, 'cipher'), 'push_unavailable', 503)
        return self.backend.cipher.encrypt(value)

    def _active(self, db, uid, device):
        now = int(self.backend.clock())
        user = db.execute('SELECT id,email,verified FROM users WHERE id=?', (uid,)).fetchone()
        valid = db.execute('SELECT 1 FROM devices d JOIN web_sessions w ON w.device_id=d.id AND w.user_id=d.user_id WHERE d.id=? AND d.user_id=? AND d.revoked_at=0 AND w.expires_at>?', (device, uid, now)).fetchone()
        require(user and user['verified'] and valid, 'unauthorized', 401)
        self.backend._account_available(db, uid)
        return {**dict(user), 'device_id':device}

    def prepare(self, actor):
        now = int(self.backend.clock())
        with self.backend.transaction() as db:
            self._active(db, actor['id'], actor['device_id'])
            row = db.execute("SELECT * FROM web_push_keys WHERE id='v1'").fetchone()
            if not row:
                key = ec.generate_private_key(ec.SECP256R1())
                public = b64(key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint))
                secret = self._encrypt(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
                db.execute("INSERT INTO web_push_keys VALUES('v1',?,?,?)", (secret, public, now))
            else: public = row['public_key']
        return {'application_server_key':public}

    def status(self, actor):
        with self.backend.connect() as db:
            self._active(db, actor['id'], actor['device_id'])
            key = db.execute("SELECT public_key FROM web_push_keys WHERE id='v1'").fetchone()
            row = db.execute('SELECT * FROM web_push_subscriptions WHERE user_id=? AND device_id=? ORDER BY enabled DESC,updated_at DESC,id DESC LIMIT 1', (actor['id'], actor['device_id'])).fetchone()
            last = db.execute('SELECT d.* FROM web_push_deliveries d JOIN web_push_subscriptions s ON s.id=d.subscription_id WHERE s.user_id=? AND s.device_id=? ORDER BY d.created_at DESC,d.id DESC LIMIT 1', (actor['id'], actor['device_id'])).fetchone()
            fields = ('id','state','created_at','accepted_at','displayed_at','error_code')
            return {'supported':hasattr(self.backend, 'cipher'), 'application_server_key':key['public_key'] if key else None,
                    'enabled':bool(row and row['enabled']), 'subscription_id':row['id'] if row else None,
                    'lead_minutes':row['lead_minutes'] if row else 15, 'priority':row['priority'] if row else 'high',
                    'last_delivery':{field:last[field] for field in fields} if last else None}

    def subscribe(self, actor, body):
        subscription = validate_subscription(body.get('subscription'))
        lead, priority, timezone = body.get('lead_minutes', 15), body.get('priority', 'high'), body.get('timezone')
        require(type(lead) is int and lead in LEADS and priority in ('high', 'normal'), 'push_preferences_invalid')
        require(isinstance(timezone, str) and len(timezone) <= 100, 'push_timezone_invalid')
        try: ZoneInfo(timezone)
        except (ValueError, ZoneInfoNotFoundError): raise Failure('push_timezone_invalid')
        self.prepare(actor)
        now, digest = int(self.backend.clock()), token_hash(subscription['endpoint'])
        secret = self._encrypt(canonical(subscription).encode())
        with self.backend.transaction() as db:
            self._active(db, actor['id'], actor['device_id'])
            previous = db.execute('SELECT * FROM web_push_subscriptions WHERE user_id=? AND device_id=? AND endpoint_hash=?', (actor['id'], actor['device_id'], digest)).fetchone()
            unchanged = previous and previous['enabled'] and (previous['lead_minutes'], previous['priority'], previous['timezone']) == (lead, priority, timezone)
            if unchanged:
                # App startup refreshes the browser key material and timezone.
                # An unchanged refresh must preserve pending reminders and the
                # original opt-in boundary, even if browser key material rotated.
                db.execute('UPDATE web_push_subscriptions SET secret=?,error_code=NULL WHERE id=?', (secret, previous['id']))
            else:
                self._replace_subscription(db, actor, previous, digest, secret, lead, priority, timezone, now)
        return self.status(actor)

    def _replace_subscription(self, db, actor, previous, digest, secret, lead, priority, timezone, now):
        # One current subscription per authenticated browser device. Turning
        # the setting off and on does not replay earlier occurrences.
        db.execute('UPDATE web_push_subscriptions SET enabled=0,secret=?,updated_at=? WHERE user_id=? AND device_id=?', (b'', now, actor['id'], actor['device_id']))
        if previous:
            sid = previous['id']
            enabled_at = previous['enabled_at'] if previous['enabled'] else now
            scanned_until = max(enabled_at, now - 3600)
            db.execute('UPDATE web_push_subscriptions SET secret=?,enabled=1,lead_minutes=?,priority=?,timezone=?,updated_at=?,scanned_until=?,enabled_at=?,error_code=NULL WHERE id=?', (secret, lead, priority, timezone, now, scanned_until, enabled_at, sid))
        else:
            sid = str(uuid.uuid4())
            db.execute('INSERT INTO web_push_subscriptions(id,user_id,device_id,endpoint_hash,secret,created_at,updated_at,enabled,lead_minutes,priority,timezone,scanned_until,enabled_at) VALUES(?,?,?,?,?,?,?,1,?,?,?,?,?)', (sid, actor['id'], actor['device_id'], digest, secret, now, now, lead, priority, timezone, now, now))
        db.execute("UPDATE web_push_deliveries SET state='cancelled',payload=?,error_code='settings_changed' WHERE subscription_id IN (SELECT id FROM web_push_subscriptions WHERE user_id=? AND device_id=?) AND state IN ('queued','sending')", (b'', actor['id'], actor['device_id']))

    def unsubscribe(self, actor):
        with self.backend.transaction() as db:
            self._active(db, actor['id'], actor['device_id'])
            db.execute('UPDATE web_push_subscriptions SET enabled=0,secret=?,updated_at=? WHERE user_id=? AND device_id=?', (b'', int(self.backend.clock()), actor['id'], actor['device_id']))
            db.execute("UPDATE web_push_deliveries SET state='cancelled',payload=?,error_code='disabled' WHERE subscription_id IN (SELECT id FROM web_push_subscriptions WHERE user_id=? AND device_id=?) AND state IN ('queued','sending')", (b'', actor['id'], actor['device_id']))
        return self.status(actor)

    def _enqueue(self, db, sub, now, event=None, occurrence=None, day=None):
        previous = db.execute('SELECT * FROM web_push_deliveries WHERE subscription_id=? AND event_id=? AND occurrence_at=?', (sub['id'], event['id'], occurrence)).fetchone() if event else None
        if previous:
            refresh = (previous['state'] == 'cancelled' and previous['error_code'] == 'settings_changed' or
                       previous['event_revision'] != event['revision'] and
                       (previous['state'] == 'queued' or previous['state'] == 'cancelled' and previous['error_code'] == 'event_changed'))
            if not refresh: return {'delivery_id':previous['id'], 'state':previous['state']}
        did, receipt = previous['id'] if previous else str(uuid.uuid4()), secrets.token_urlsafe(32)
        payload = {'v':1, 'delivery_id':did, 'subscription_id':sub['id'], 'receipt_token':receipt, 'recipient_user_id':sub['user_id'],
                   'title':'ULADIM', 'body':'Напоминание о событии календаря' if event else 'Проверка уведомлений',
                   'url':'/app?notification=calendar&workspace=' + event['workspace_id'] + '&day=' + day if event else '/app',
                   'tag':'uladim-' + did, 'priority':sub['priority'], 'sent_at':now * 1000}
        encrypted = self._encrypt(canonical(payload).encode())
        expiry = min(now + 3600, occurrence - (0 if json.loads(event['schedule'])['allDay'] else sub['lead_minutes'] * 60) + 3600) if event else now + 3600
        if previous:
            # Recheck a changed event without losing its occurrence. An accepted
            # or displayed occurrence is never replayed after an ordinary edit.
            db.execute("UPDATE web_push_deliveries SET event_revision=?,created_at=?,state='queued',attempts=0,next_attempt=?,leased_until=0,expires_at=?,payload=?,receipt_hash=?,error_code=NULL WHERE id=?", (event['revision'], now, now, expiry, encrypted, token_hash(receipt), did))
        else:
            db.execute("INSERT INTO web_push_deliveries(id,subscription_id,event_id,event_revision,occurrence_at,created_at,state,attempts,next_attempt,leased_until,expires_at,payload,receipt_hash) VALUES(?,?,?,?,?,?,'queued',0,?,0,?,?,?) ON CONFLICT(subscription_id,event_id,occurrence_at) DO NOTHING", (did, sub['id'], event['id'] if event else None, event['revision'] if event else None, occurrence, now, now, expiry, encrypted, token_hash(receipt)))
        from .inbox import Inbox
        Inbox(self.backend).append_delivery(db, sub, now, did, event, occurrence, day)
        return {'delivery_id':did, 'state':'queued'}

    def test(self, actor):
        now = int(self.backend.clock())
        with self.backend.transaction() as db:
            self._active(db, actor['id'], actor['device_id'])
            sub = db.execute('SELECT * FROM web_push_subscriptions WHERE user_id=? AND device_id=? AND enabled=1', (actor['id'], actor['device_id'])).fetchone()
            require(sub is not None, 'push_not_enabled', 409)
            recent = db.execute('SELECT 1 FROM web_push_deliveries d JOIN web_push_subscriptions s ON s.id=d.subscription_id WHERE s.user_id=? AND s.device_id=? AND d.event_id IS NULL AND d.created_at>?', (actor['id'], actor['device_id'], now - 60)).fetchone()
            require(recent is None, 'rate_limited', 429)
            return self._enqueue(db, sub, now)

    def receipt(self, body):
        did, token, state = body.get('delivery_id'), body.get('receipt_token'), body.get('state')
        identifier(did)
        require(isinstance(token, str) and len(token) == 43 and state in ('displayed', 'suppressed'), 'push_receipt_invalid')
        now = int(self.backend.clock())
        with self.backend.transaction() as db:
            row = db.execute('SELECT * FROM web_push_deliveries WHERE id=?', (did,)).fetchone()
            require(row and row['expires_at'] > now and hmac.compare_digest(row['receipt_hash'], token_hash(token)), 'push_receipt_invalid', 403)
            if row['state'] in ('sending', 'accepted'):
                db.execute('UPDATE web_push_deliveries SET state=?,displayed_at=?,payload=? WHERE id=?', (state, now if state == 'displayed' else None, b'', did))
        return {'accepted':True}

    def scan(self):
        now = int(self.backend.clock())
        with self.backend.connect() as db:
            subs = db.execute('SELECT * FROM web_push_subscriptions WHERE enabled=1 AND id>? ORDER BY id LIMIT 20', (self.scan_cursor,)).fetchall()
        self.scan_cursor = subs[-1]['id'] if len(subs) == 20 else ''
        for sub in subs:
            with self.backend.transaction() as db:
                sub = db.execute('SELECT * FROM web_push_subscriptions WHERE id=? AND enabled=1', (sub['id'],)).fetchone()
                if not sub: continue
                try: actor = self._active(db, sub['user_id'], sub['device_id'])
                except Failure:
                    self._disable(db, sub['id'], 'session_unavailable')
                    continue
                # Query only calendar rows, never the first page of a mixed sync
                # history. Reuse the original workspace and record authority.
                window = self.scan_windows.get(sub['id'])
                signature = (sub['updated_at'], sub['lead_minutes'], sub['timezone'], sub['priority'])
                if not window or window[1] != signature:
                    # A live preference change restarts this bounded scan with
                    # its new due times instead of continuing an old page.
                    self.event_cursors.pop(sub['id'], None)
                    self.scan_windows[sub['id']] = window = (now, signature)
                rows = db.execute("SELECT r.*,e.schedule FROM records r JOIN events e ON e.id=r.id JOIN memberships m ON m.workspace_id=r.workspace_id AND m.user_id=? AND m.active=1 JOIN workspaces w ON w.id=r.workspace_id AND w.dissolved=0 WHERE r.kind='event' AND r.deleted=0 AND r.id>? ORDER BY r.id LIMIT 501", (sub['user_id'], self.event_cursors.get(sub['id'], ''))).fetchall()
                through = window[0]
                lower = max(now - 3600, min(sub['scanned_until'], now - 300), sub['enabled_at'])
                if len(rows) > 500: self.event_cursors[sub['id']] = rows[499]['id']
                else: self.event_cursors.pop(sub['id'], None)
                spaces = {}
                for row in rows[:500]:
                    try:
                        wid = row['workspace_id']
                        if wid not in spaces: spaces[wid] = self.backend._workspace(db, actor, wid)
                        if not self.backend._readable(db, actor, spaces[wid], row): continue
                        schedule = json.loads(row['schedule'])
                        lead = 0 if schedule['allDay'] else sub['lead_minutes'] * 60
                        for at, day in occurrences(schedule, sub['timezone'], lower + lead, through + lead):
                            # Enabling notifications never triggers old reminders.
                            if at - lead < sub['enabled_at']: continue
                            self._enqueue(db, sub, now, row, at, day)
                    except (Failure, ValueError, TypeError, KeyError, ZoneInfoNotFoundError):
                        continue
                if len(rows) <= 500:
                    db.execute('UPDATE web_push_subscriptions SET scanned_until=? WHERE id=?', (through, sub['id']))
                    self.scan_windows.pop(sub['id'], None)
        return bool(self.scan_cursor or any(sub['id'] in self.event_cursors for sub in subs))

    def _disable(self, db, sid, reason):
        self.event_cursors.pop(sid, None)
        self.scan_windows.pop(sid, None)
        db.execute('UPDATE web_push_subscriptions SET enabled=0,secret=?,error_code=? WHERE id=?', (b'', reason, sid))
        db.execute("UPDATE web_push_deliveries SET state='cancelled',payload=?,error_code=? WHERE subscription_id=? AND state IN ('queued','sending')", (b'', reason, sid))

    def _authorized(self, db, sub, job):
        actor = self._active(db, sub['user_id'], sub['device_id'])
        require(sub['enabled'], 'disabled', 403)
        if job['event_id']:
            row = db.execute('SELECT * FROM records WHERE id=?', (job['event_id'],)).fetchone()
            require(row and not row['deleted'] and row['revision'] == job['event_revision'], 'event_changed', 403)
            space = self.backend._workspace(db, actor, row['workspace_id'])
            require(self.backend._readable(db, actor, space, row), 'event_forbidden', 403)

    def tick(self):
        now = int(self.backend.clock())
        if now >= self.next_scan:
            more = self.scan()
            self.next_scan = now if more else now + 15
        with self.backend.transaction() as db:
            db.execute("UPDATE web_push_deliveries SET state='cancelled',payload=?,error_code='expired' WHERE expires_at<=? AND state IN ('queued','sending')", (b'', now))
            job = db.execute("SELECT * FROM web_push_deliveries WHERE state IN ('queued','sending') AND next_attempt<=? AND leased_until<=? AND expires_at>? ORDER BY next_attempt,created_at,id LIMIT 1", (now, now, now)).fetchone()
            if not job: return False
            sub = db.execute('SELECT * FROM web_push_subscriptions WHERE id=?', (job['subscription_id'],)).fetchone()
            try: self._authorized(db, sub, job)
            except Failure as error:
                db.execute("UPDATE web_push_deliveries SET state='cancelled',payload=?,error_code=? WHERE id=?", (b'', error.code, job['id']))
                return True
            key = db.execute("SELECT * FROM web_push_keys WHERE id='v1'").fetchone()
            db.execute("UPDATE web_push_deliveries SET state='sending',attempts=attempts+1,leased_until=? WHERE id=?", (now + 30, job['id']))
        try:
            subscription = validate_subscription(json.loads(self.backend.cipher.decrypt(bytes(sub['secret']))))
            payload = self.backend.cipher.decrypt(bytes(job['payload']))
            private = serialization.load_pem_private_key(self.backend.cipher.decrypt(bytes(key['secret'])), password=None)
            endpoint = subscription['endpoint']
            url = urlsplit(endpoint)
            bearer = jwt.encode({'aud':url.scheme + '://' + url.netloc, 'exp':now + 43200, 'sub':self.site + '/support'}, private, algorithm='ES256')
            headers = {'Authorization':'vapid t=' + bearer + ',k=' + key['public_key'], 'Content-Encoding':'aes128gcm',
                       'Content-Type':'application/octet-stream', 'TTL':str(min(3600, job['expires_at'] - now)),
                       'Urgency':sub['priority'], 'Topic':b64(hashlib.sha256(job['id'].encode()).digest()[:24])}
            code = self.transport(endpoint, encrypt_message(subscription, payload), headers)
        except Exception as error:
            # Provider errors can contain credentials or endpoints. Persist/log a
            # short classification only; retry within the original queue expiry.
            code = 0
            log.warning('push_delivery_failed class=%s', type(error).__name__)
        with self.backend.transaction() as db:
            if code in (201, 202):
                # The SW receipt can race this update. Preserve a display ACK.
                db.execute("UPDATE web_push_deliveries SET state=CASE WHEN state='sending' THEN 'accepted' ELSE state END,accepted_at=?,leased_until=0,payload=?,error_code=NULL WHERE id=?", (int(self.backend.clock()), b'', job['id']))
            elif code in (404, 410):
                self._disable(db, sub['id'], 'subscription_gone')
                db.execute("UPDATE web_push_deliveries SET state='failed',error_code='subscription_gone' WHERE id=?", (job['id'],))
            elif (code == 0 or code == 429 or 500 <= code < 600) and job['attempts'] < 4:
                db.execute("UPDATE web_push_deliveries SET state='queued',next_attempt=?,leased_until=0,error_code='provider_retry' WHERE id=? AND state='sending'", (now + min(300, 30 * 2 ** job['attempts']), job['id']))
            else:
                db.execute("UPDATE web_push_deliveries SET state='failed',leased_until=0,payload=?,error_code='provider_rejected' WHERE id=? AND state='sending'", (b'', job['id']))
        return True
