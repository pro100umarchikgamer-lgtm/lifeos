"""Voluntary account display names and bounded metadata-only staff lookup."""
import unicodedata

from .service import identifier, require


def cursor(value, code='invalid_cursor'):
    if value is None:
        return 9223372036854775807, 'ffffffff-ffff-ffff-ffff-ffffffffffff'
    require(isinstance(value, str) and len(value) <= 64, code)
    parts = value.split(':')
    require(len(parts) == 2 and parts[0].isdigit() and len(parts[0]) <= 19, code)
    stamp = int(parts[0])
    require(stamp <= 9223372036854775807, code)
    return stamp, identifier(parts[1])


PROJECTION = """u.id,u.email,u.verified,u.created_at,
 COALESCE(a.disabled_until,0) AS disabled_until,COALESCE(a.deleted_at,0) AS deleted_at,
 i.display_name,
 COALESCE((SELECT MAX(d.last_seen_at) FROM devices d WHERE d.user_id=u.id),0) AS last_seen_at,
 (SELECT COUNT(*) FROM devices d WHERE d.user_id=u.id AND d.revoked_at=0) AS active_devices,
 CASE WHEN EXISTS(SELECT 1 FROM account_mfa m WHERE m.user_id=u.id) THEN 1 ELSE 0 END AS mfa_enabled,
 CASE WHEN EXISTS(SELECT 1 FROM google_identities g WHERE g.user_id=u.id) THEN 1 ELSE 0 END AS google_linked"""
FROM = ' FROM users u LEFT JOIN account_state a ON a.user_id=u.id LEFT JOIN account_identity i ON i.user_id=u.id'
AVAILABLE = " COALESCE(a.deleted_at,0)=0 AND NOT EXISTS(SELECT 1 FROM deletion_jobs j WHERE j.user_id=u.id AND j.state='erasing')"


def public_user(row):
    value = dict(row)
    value['name_source'] = 'account_identity' if value.get('display_name') else None
    value['mfa_enabled'] = bool(value['mfa_enabled'])
    value['google_linked'] = bool(value['google_linked'])
    return value


def user_in(db, uid):
    row = db.execute('SELECT ' + PROJECTION + FROM + ' WHERE u.id=? AND ' + AVAILABLE, (identifier(uid),)).fetchone()
    require(row is not None, 'not_found', 404)
    return public_user(row)


def directory(backend, actor, query='', before=None, limit=50):
    from .control import Control
    Control(backend).require(actor, 'users.read')
    require(isinstance(query, str) and len(query) <= 254)
    require(type(limit) is int and 1 <= limit <= 100, 'invalid_cursor')
    stamp, last = cursor(before)
    query = unicodedata.normalize('NFC', query.strip()).casefold()
    pattern = '%' + query.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
    with backend.connect() as db:
        rows = db.execute('SELECT ' + PROJECTION + FROM + ' WHERE ' + AVAILABLE +
            " AND (LOWER(u.email) LIKE ? ESCAPE '\\' OR i.search_name LIKE ? ESCAPE '\\' OR u.id=?)"
            ' AND (u.created_at<? OR (u.created_at=? AND u.id<?)) ORDER BY u.created_at DESC,u.id DESC LIMIT ?',
            (pattern, pattern, query, stamp, stamp, last, limit + 1)).fetchall()
    page = rows[:limit]
    return {'users': [public_user(row) for row in page], 'limit': limit,
        'next_before': str(page[-1]['created_at']) + ':' + page[-1]['id'] if len(rows) > limit else None}


class AccountIdentity:
    def __init__(self, backend):
        self.backend = backend

    def identity(self, actor, body=None):
        with self.backend.transaction() as db:
            self.backend._account_available(db, actor['id'])
            require(actor.get('verified') == 1, 'verify_email', 403)
            if body is not None:
                require(isinstance(body, dict) and set(body) == {'display_name'}, 'invalid_fields')
                name = body['display_name']
                require(isinstance(name, str) and len(name) <= 120, 'identity_invalid')
                name = unicodedata.normalize('NFC', name.strip())
                require(not any(unicodedata.category(char).startswith('C') for char in name), 'identity_invalid')
                if name:
                    db.execute('INSERT INTO account_identity VALUES(?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET display_name=excluded.display_name,search_name=excluded.search_name,updated_at=excluded.updated_at',
                        (actor['id'], name, name.casefold(), int(self.backend.clock())))
                else:
                    db.execute('DELETE FROM account_identity WHERE user_id=?', (actor['id'],))
            row = db.execute('SELECT display_name FROM account_identity WHERE user_id=?', (actor['id'],)).fetchone()
            return {'display_name': row['display_name'] if row else None}
