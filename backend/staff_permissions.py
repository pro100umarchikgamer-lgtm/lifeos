"""Role baselines with explicit deny-only staff and invitation restrictions."""
import json
import re
import secrets

from .service import canonical, identifier, require, text, token_hash


def principal(db, row):
    from .control import StaffPrincipal
    denied = tuple(r['permission'] for r in db.execute(
        'SELECT permission FROM staff_permission_restrictions WHERE staff_id=? ORDER BY permission', (row['id'],)).fetchall())
    return StaffPrincipal(row['id'], row['user_id'], tuple(json.loads(row['roles'])), denied)


def authority(actor):
    return {'base_permissions': sorted(actor.base_permissions), 'permissions': sorted(actor.permissions),
        'denied_permissions': sorted(actor.denied_permissions)}


def catalog(actor):
    from .control import ROLE_PERMISSIONS, ROLE_RANK
    permissions = sorted(set().union(*ROLE_PERMISSIONS.values()))
    return {'roles': [{'key': role, 'rank': ROLE_RANK[role], 'permissions': sorted(value)}
            for role, value in ROLE_PERMISSIONS.items()],
        'permissions': [{'key': key} for key in permissions],
        'assignable_roles': [role for role in ROLE_RANK if role != 'owner' and ROLE_RANK[role] < actor.rank]}


def validate(actor, roles, denied):
    from .control import ROLE_PERMISSIONS, ROLE_RANK
    require(isinstance(roles, list) and roles and all(isinstance(role, str) for role in roles)
        and len(roles) == len(set(roles)) and set(roles) <= set(ROLE_RANK) - {'owner'})
    require(max(ROLE_RANK[role] for role in roles) < actor.rank, 'staff_hierarchy', 403)
    require(isinstance(denied, list) and all(isinstance(value, str) for value in denied)
        and len(denied) == len(set(denied)) and set(denied) <= set().union(*ROLE_PERMISSIONS.values()), 'permission_invalid')
    baseline = set().union(*(ROLE_PERMISSIONS[role] for role in roles))
    require(baseline - set(denied) <= actor.permissions, 'staff_delegation_forbidden', 403)
    return sorted(denied)


class StaffPermissions:
    def __init__(self, control):
        self.control, self.backend = control, control.backend

    def staff(self, actor):
        self.control.require(actor, 'staff.manage')
        with self.backend.connect() as db:
            rows = db.execute('SELECT s.id,s.user_id,u.email,s.roles,s.active,s.revision FROM staff s JOIN users u ON u.id=s.user_id ORDER BY s.created_at,s.id').fetchall()
            return {'staff': [dict(row, roles=json.loads(row['roles']), **authority(principal(db, row))) for row in rows]}

    def update(self, actor, sid, roles, active, revision, reason, denied=None):
        self.control.require(actor, 'staff.manage')
        identifier(sid)
        require(type(active) is bool and type(revision) is int)
        text(reason, 500)
        with self.backend.transaction() as db:
            row = db.execute('SELECT * FROM staff WHERE id=?', (sid,)).fetchone()
            require(row is not None, 'not_found', 404)
            self.control._target_rank(db, actor, row['user_id'])
            previous = principal(db, row)
            denied = validate(actor, roles, list(previous.denied_permissions) if denied is None else denied)
            require(row['revision'] == revision, 'revision_conflict', 409)
            old = {'roles': list(previous.roles), 'active': bool(row['active']), 'denied_permissions': list(previous.denied_permissions)}
            db.execute('UPDATE staff SET roles=?,active=?,revision=revision+1 WHERE id=?', (canonical(roles), int(active), sid))
            db.execute('DELETE FROM staff_permission_restrictions WHERE staff_id=?', (sid,))
            for permission in denied:
                db.execute('INSERT INTO staff_permission_restrictions VALUES(?,?)', (sid, permission))
            db.execute('DELETE FROM control_sessions WHERE staff_id=?', (sid,))
            self.control.audit(db, actor, row['user_id'], 'staff.update', old,
                {'roles': roles, 'active': active, 'denied_permissions': denied}, reason)
        return {'revision': revision + 1}

    def invite(self, actor, email, roles, reason, denied=None):
        self.control.require(actor, 'staff.manage')
        email = text(email, 254).casefold()
        require(re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email))
        denied = validate(actor, roles, [] if denied is None else denied)
        text(reason, 500)
        code, now = secrets.token_urlsafe(32), int(self.backend.clock())
        digest = token_hash(code)
        with self.backend.transaction() as db:
            db.execute('INSERT INTO staff_invitations VALUES(?,?,?,?,?,0)', (digest, email, canonical(roles), actor.id, now + 86400))
            for permission in denied:
                db.execute('INSERT INTO staff_invitation_restrictions VALUES(?,?)', (digest, permission))
            self.control.audit(db, actor, None, 'staff.invite', {},
                {'roles': roles, 'denied_permissions': denied, 'expires_at': now + 86400}, reason)
        return {'invitation': code, 'expires_at': now + 86400, 'denied_permissions': denied}
