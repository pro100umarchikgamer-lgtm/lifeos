"""Verified one-time referrals. No rewards, billing writes or new tracking."""
import re
import secrets
import unicodedata

from .control import Control
from .service import Failure, identifier, require

PAGE = 50
GENERIC_NAME = 'Участник'


def erase_in(db, uid):
    """Remove this subject while preserving another invitee's consumed slot."""
    db.execute('DELETE FROM referral_codes WHERE user_id=?', (uid,))
    db.execute('DELETE FROM referral_aliases WHERE user_id=?', (uid,))
    db.execute('DELETE FROM referral_attributions WHERE invitee_id=?', (uid,))
    db.execute('UPDATE referral_attributions SET referrer_id=NULL,confirmed_at=0 WHERE referrer_id=?', (uid,))


class Referrals:
    def __init__(self, backend, site='https://getuladim.space'):
        self.backend, self.site = backend, site

    def _user(self, db, actor):
        require(isinstance(actor, dict) and isinstance(actor.get('id'), str), 'unauthorized', 401)
        row = db.execute('SELECT id,verified FROM users WHERE id=?', (actor['id'],)).fetchone()
        require(row is not None, 'unauthorized', 401)
        self.backend._account_available(db, row['id'])
        require(row['verified'] == 1, 'verify_email', 403)
        return row['id']

    @staticmethod
    def _query(query, allowed):
        require(isinstance(query, dict) and set(query) <= set(allowed), 'invalid_fields')
        require(all(isinstance(values, list) and len(values) == 1 and isinstance(values[0], str)
                    for values in query.values()), 'invalid_input')
        return {key: values[0] for key, values in query.items()}

    @staticmethod
    def _valid_invitees():
        return """FROM referral_attributions r JOIN users i ON i.id=r.invitee_id
            LEFT JOIN account_state s ON s.user_id=i.id
            WHERE r.referrer_id=? AND i.verified=1 AND COALESCE(s.deleted_at,0)=0
            AND NOT EXISTS(SELECT 1 FROM deletion_jobs j WHERE j.user_id=i.id AND j.state='erasing')"""

    def _summary(self, db, uid, offset=0):
        code = db.execute('SELECT code FROM referral_codes WHERE user_id=?', (uid,)).fetchone()
        base = self._valid_invitees()
        count = db.execute('SELECT COUNT(*) AS n '+base, (uid,)).fetchone()['n']
        rows = db.execute("SELECT COALESCE((SELECT a.display_name FROM referral_aliases a WHERE a.user_id=i.id),?) AS display_name "+base+
                          ' ORDER BY r.confirmed_at DESC,r.invitee_id DESC LIMIT 51 OFFSET ?',
                          (GENERIC_NAME,uid,offset)).fetchall()
        return {'confirmed_count':int(count),
                'invite':{'code':code['code'],'url':self.site+'/app?ref='+code['code']} if code else None,
                'people':[{'display_name':row['display_name']} for row in rows[:PAGE]],
                'next_offset':offset+PAGE if len(rows)>PAGE else None}

    def summary(self, actor, query=None):
        values = self._query(query or {}, {'offset'})
        offset = values.get('offset', '0')
        require(re.fullmatch(r'[0-9]{1,6}', offset) and int(offset) <= 100000, 'invalid_cursor')
        with self.backend.connect() as db:
            return self._summary(db, self._user(db, actor), int(offset))

    def create_code(self, actor, body):
        require(isinstance(body, dict) and not body, 'invalid_fields')
        with self.backend.transaction() as db:
            uid = self._user(db, actor)
            if not db.execute('SELECT 1 FROM referral_codes WHERE user_id=?', (uid,)).fetchone():
                db.execute('INSERT INTO referral_codes VALUES(?,?,?)', (uid,secrets.token_urlsafe(32),int(self.backend.clock())))
            return self._summary(db, uid)

    def claim(self, actor, body):
        require(isinstance(body, dict) and set(body) == {'code'}, 'invalid_fields')
        code = body['code']
        require(isinstance(code, str) and re.fullmatch(r'[A-Za-z0-9_-]{43}', code), 'referral_invalid')
        with self.backend.transaction() as db:
            uid = self._user(db, actor)
            target = db.execute('SELECT user_id FROM referral_codes WHERE code=?', (code,)).fetchone()
            require(target is not None, 'referral_invalid')
            referrer = target['user_id']
            require(referrer != uid, 'referral_self')
            prior = db.execute('SELECT referrer_id FROM referral_attributions WHERE invitee_id=?', (uid,)).fetchone()
            if prior:
                require(prior['referrer_id'] == referrer, 'referral_already_attributed', 409)
                return {'status':'confirmed'}
            try: self._user(db, {'id':referrer})
            except Failure: raise Failure('referral_invalid') from None
            db.execute('INSERT INTO referral_attributions VALUES(?,?,?)', (uid,referrer,int(self.backend.clock())))
            return {'status':'confirmed'}

    def alias(self, actor, body=None):
        if body is None:
            with self.backend.connect() as db:
                uid = self._user(db, actor)
                row = db.execute('SELECT display_name FROM referral_aliases WHERE user_id=?', (uid,)).fetchone()
                return {'display_name':row['display_name'] if row else GENERIC_NAME}
        require(isinstance(body, dict) and set(body) == {'first_name','surname_initial'}, 'invalid_fields')
        first, initial = body['first_name'], body['surname_initial']
        require(isinstance(first, str) and isinstance(initial, str), 'invalid_alias')
        first, initial = (unicodedata.normalize('NFC', value.strip()) for value in (first, initial))
        require(len(first) <= 32 and len(initial) <= 1, 'invalid_alias')
        require(not first or first[0].isalpha() and first[-1].isalpha()
                and all(char.isalpha() or char in "-'’‘" for char in first), 'invalid_alias')
        require(not initial or initial.isalpha() and len(initial.upper()) == 1, 'invalid_alias')
        require(first or not initial, 'invalid_alias')
        name = first + (' '+initial.upper()+'.' if initial else '')
        with self.backend.transaction() as db:
            uid = self._user(db, actor)
            if name:
                db.execute('INSERT INTO referral_aliases VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET display_name=excluded.display_name', (uid,name))
            else: db.execute('DELETE FROM referral_aliases WHERE user_id=?', (uid,))
        return {'display_name':name or GENERIC_NAME}

    def graph(self, actor, query=None):
        Control(self.backend).require(actor, 'referrals.read')
        values = self._query(query or {}, {'before','referrer','activity','converted'})
        referrer = values.get('referrer')
        if referrer is not None: identifier(referrer)
        require(values.get('activity', 'active') in ('active','inactive'), 'invalid_input')
        require(values.get('converted', 'yes') in ('yes','no'), 'invalid_input')
        cursor = None
        if 'before' in values:
            pieces = values['before'].split(':')
            require(len(pieces) == 2 and re.fullmatch(r'[0-9]{1,19}', pieces[0]), 'invalid_cursor')
            cursor = (int(pieces[0]), identifier(pieces[1]))
            require(0 <= cursor[0] <= 9223372036854775807, 'invalid_cursor')
        now = int(self.backend.clock())
        base = """WITH referral_state AS (
            SELECT r.referrer_id,r.invitee_id,r.confirmed_at,
            CASE WHEN EXISTS(
                SELECT 1 FROM devices d WHERE d.user_id=i.id AND d.revoked_at=0
                AND d.last_seen_at>=? AND d.last_seen_at<=?) THEN 1 ELSE 0 END AS active,
            CASE WHEN EXISTS(SELECT 1 FROM provider_purchases p JOIN provider_events e
                ON e.source=p.source AND e.reference_hash=p.reference_hash
                WHERE p.user_id=i.id AND p.source IN ('google_play','rustore')
                AND p.state IN ('active','cancelled') AND p.valid_until>?
                AND (p.trial_until IS NULL OR p.trial_until<=?)
                AND p.updated_at>=r.confirmed_at AND e.received_at>=r.confirmed_at
                AND e.result LIKE ?) THEN 1 ELSE 0 END AS purchase_converted
            FROM referral_attributions r JOIN users i ON i.id=r.invitee_id
            JOIN users f ON f.id=r.referrer_id
            LEFT JOIN account_state si ON si.user_id=i.id
            LEFT JOIN account_state sf ON sf.user_id=f.id
            WHERE i.verified=1 AND f.verified=1
            AND COALESCE(si.deleted_at,0)=0 AND COALESCE(sf.deleted_at,0)=0
            AND NOT EXISTS(SELECT 1 FROM deletion_jobs j WHERE j.user_id IN(i.id,f.id) AND j.state='erasing')"""
        # Only trusted store state with a matching applied reconciliation event;
        # manual grants, web invoices and current trials cannot count.
        parameters = [now-30*86400,now,now,now,'{"applied":true,%']
        if referrer is not None: base += ' AND r.referrer_id=?';parameters.append(referrer)
        base += ') '
        where, page_parameters = [], list(parameters)
        if 'activity' in values: where.append('active=?');page_parameters.append(int(values['activity']=='active'))
        if 'converted' in values: where.append('purchase_converted=?');page_parameters.append(int(values['converted']=='yes'))
        if cursor:
            where.append('(confirmed_at<? OR (confirmed_at=? AND invitee_id<?))')
            page_parameters.extend((cursor[0],cursor[0],cursor[1]))
        with self.backend.connect() as db:
            self._user(db, {'id':actor.user_id})
            counts = db.execute(base+'SELECT COUNT(*) AS confirmed,COALESCE(SUM(active),0) AS active,COALESCE(SUM(purchase_converted),0) AS purchase_converted FROM referral_state', parameters).fetchone()
            rows = db.execute(base+'SELECT * FROM referral_state'+(' WHERE '+' AND '.join(where) if where else '')+
                              ' ORDER BY confirmed_at DESC,invitee_id DESC LIMIT 51', page_parameters).fetchall()
        edges = [{'referrer_id':row['referrer_id'],'invitee_id':row['invitee_id'],'confirmed_at':row['confirmed_at'],
                  'activity':'active' if row['active'] else 'inactive','purchase_converted':bool(row['purchase_converted'])} for row in rows[:PAGE]]
        totals = {key:int(counts[key]) for key in ('confirmed','active','purchase_converted')}
        totals['inactive'] = totals['confirmed']-totals['active']
        return {'counts':totals,'edges':edges,
                'next_before':str(edges[-1]['confirmed_at'])+':'+edges[-1]['invitee_id'] if len(rows)>PAGE else None,
                'activity_window_days':30,'activity_basis':'existing_device_last_seen',
                'purchase_basis':'verified_nontrial_store_purchase','purchase_conversion_available':False,
                'sales_enabled':False,'rewards_enabled':False,'payouts_enabled':False}
