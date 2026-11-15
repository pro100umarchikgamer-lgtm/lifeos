"""Per-viewer financial list order; never changes records or record permissions."""
import json

from .service import Failure, canonical, identifier, require

MAX_ORDER = 1000
MAX_REVISION = 9223372036854775807


class LayoutPreferences:
    def __init__(self, backend):
        self.backend = backend

    def _scope(self, db, actor, workspace_id, kind):
        require(kind in ('account', 'budget'), 'layout_kind_invalid')
        return self.backend._workspace(db, actor, identifier(workspace_id))

    def _visible(self, db, actor, space, kind, ids):
        """Use current membership and read visibility, including read-only grants."""
        visible = set()
        for offset in range(0, len(ids), 100):
            chunk = ids[offset:offset + 100]
            placeholders = ','.join('?' for _ in chunk)
            rows = db.execute(
                'SELECT * FROM records WHERE workspace_id=? AND kind=? AND deleted=0 AND id IN (' + placeholders + ')',
                (space['id'], kind, *chunk),
            ).fetchall()
            visible.update(row['id'] for row in rows if self.backend._readable(db, actor, space, row))
        return visible

    def _response(self, db, actor, space, kind, row):
        ids = json.loads(row['order_ids']) if row else []
        allowed = self._visible(db, actor, space, kind, ids)
        return {'workspace_id': space['id'], 'kind': kind,
                'order': [rid for rid in ids if rid in allowed], 'revision': row['revision'] if row else 0}

    def get(self, actor, workspace_id, kind):
        with self.backend.connect() as db:
            space = self._scope(db, actor, workspace_id, kind)
            row = db.execute('SELECT order_ids,revision FROM user_layout_preferences WHERE user_id=? AND workspace_id=? AND kind=?',
                             (actor['id'], space['id'], kind)).fetchone()
            return self._response(db, actor, space, kind, row)

    def put(self, actor, workspace_id, kind, order, revision=None):
        require(isinstance(order, list) and len(order) <= MAX_ORDER, 'layout_order_invalid')
        try:
            for rid in order:
                identifier(rid)
        except Failure:
            raise Failure('layout_order_invalid')
        require(len(set(order)) == len(order), 'layout_order_invalid')
        require(revision is None or type(revision) is int and 0 <= revision <= MAX_REVISION,
                'layout_revision_invalid')
        with self.backend.transaction() as db:
            space = self._scope(db, actor, workspace_id, kind)
            allowed = self._visible(db, actor, space, kind, order)
            # Uniformly reject unknown, deleted, hidden, wrong-kind and foreign
            # IDs. Do not silently save a partial order or reveal which ID failed.
            require(len(allowed) == len(order), 'layout_record_forbidden', 403)
            row = db.execute('SELECT order_ids,revision FROM user_layout_preferences WHERE user_id=? AND workspace_id=? AND kind=?',
                             (actor['id'], space['id'], kind)).fetchone()
            current = row['revision'] if row else 0
            require(revision is None or revision == current, 'layout_revision_conflict', 409)
            require(current < MAX_REVISION, 'layout_revision_conflict', 409)
            db.execute('INSERT INTO user_layout_preferences(user_id,workspace_id,kind,order_ids,revision) VALUES(?,?,?,?,?) '
                       'ON CONFLICT(user_id,workspace_id,kind) DO UPDATE SET order_ids=excluded.order_ids,revision=excluded.revision',
                       (actor['id'], space['id'], kind, canonical(order), current + 1))
            return {'workspace_id': space['id'], 'kind': kind, 'order': list(order), 'revision': current + 1}
