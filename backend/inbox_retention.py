"""Bounded cleanup of generated history, never financial/user-authored records."""
import datetime as dt

HISTORY_DAYS = 90
HISTORY_LIMIT = 1000
USER_BATCH = 1000
ANNOUNCEMENT_BATCH = 20
AUDIENCE_BATCH = 100
SOURCE_BATCH = 100


def backfill_budget_sources(db, user_id, now, selected_ids):
    # Preserve dedup when upgrading a pre-retention build: deleting a 91-day
    # annual alert must not turn the same crossing into a new unread message.
    from .budget_inbox import MAX_SOURCES
    sources = db.execute('SELECT source_key FROM budget_inbox_sources WHERE user_id=? LIMIT ?', (user_id, MAX_SOURCES + 1)).fetchall()
    known = {row['source_key'] for row in sources}
    capacity = max(0, MAX_SOURCES - len(sources))
    protected = set()
    rows = []
    for start in range(0, len(selected_ids), 500):
        page = selected_ids[start:start + 500]
        rows.extend(db.execute('SELECT id,source_key FROM budget_inbox_notifications WHERE user_id=? AND id IN (' + ','.join('?' for _ in page) + ')', (user_id, *page)).fetchall())
    for row in rows:
        if row['source_key'] in known:
            continue
        try:
            end = dt.date.fromisoformat(row['source_key'].split(':')[2])
            expiry = int(dt.datetime.combine(end + dt.timedelta(days=2), dt.time.min, tzinfo=dt.timezone.utc).timestamp())
        except (ValueError, IndexError):
            continue
        if expiry > now:
            if capacity:
                db.execute('INSERT INTO budget_inbox_sources VALUES(?,?,?) ON CONFLICT(user_id,source_key) DO NOTHING', (user_id, row['source_key'], expiry))
                known.add(row['source_key'])
                capacity -= 1
            else:
                # A legacy overflow stays logically hidden, but keep this
                # source-bearing row until it can be safely tombstoned/pruned.
                db.execute("UPDATE budget_inbox_notifications SET title='',body='',link='' WHERE user_id=? AND id=?", (user_id, row['id']))
                protected.add(row['id'])
    return protected


def generated_sql():
    return """SELECT id,created_at,'inbox_notifications' AS source_table FROM inbox_notifications WHERE user_id=?
        UNION ALL SELECT id,created_at,'budget_inbox_notifications' AS source_table FROM budget_inbox_notifications WHERE user_id=?"""


def delete_generated(db, user_id, now, rows):
    for table in ('inbox_notifications', 'budget_inbox_notifications'):
        ids = [row['id'] for row in rows if row['source_table'] == table]
        if table == 'budget_inbox_notifications' and ids:
            protected = backfill_budget_sources(db, user_id, now, ids)
            ids = [nid for nid in ids if nid not in protected]
        for start in range(0, len(ids), 500):
            page = ids[start:start + 500]
            db.execute('DELETE FROM ' + table + ' WHERE user_id=? AND id IN (' + ','.join('?' for _ in page) + ')', (user_id, *page))


def sweep_user(db, user_id, now):
    cutoff = now - HISTORY_DAYS * 86400
    params = (user_id, user_id)
    rows = db.execute('SELECT * FROM (' + generated_sql() + ') n WHERE created_at<? ORDER BY created_at,id LIMIT ?', params + (cutoff, USER_BATCH)).fetchall()
    delete_generated(db, user_id, now, rows)
    remaining = USER_BATCH - len(rows)
    if remaining:
        excess = db.execute('SELECT * FROM (' + generated_sql() + ') n ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?', params + (remaining, HISTORY_LIMIT)).fetchall()
        delete_generated(db, user_id, now, excess)
    expired = db.execute('SELECT source_key FROM budget_inbox_sources WHERE user_id=? AND expires_at<=? ORDER BY expires_at,source_key LIMIT ?', (user_id, now, SOURCE_BATCH)).fetchall()
    if expired:
        db.execute('DELETE FROM budget_inbox_sources WHERE user_id=? AND source_key IN (' + ','.join('?' for _ in expired) + ')', (user_id, *(row['source_key'] for row in expired)))


def sweep_announcements(db, now):
    """Reclaim inactive audiences too, at most 100 recipient/state pairs/call.

    Parent rows are deleted only after children are gone, avoiding a potentially
    huge ON DELETE cascade from an ordinary inbox request. Audit is append-only.
    """
    rows = db.execute('SELECT id FROM announcements WHERE expires_at<? ORDER BY expires_at,id LIMIT ?',
        (now - HISTORY_DAYS * 86400, ANNOUNCEMENT_BATCH)).fetchall()
    remaining = AUDIENCE_BATCH
    for row in rows:
        nid = row['id']
        db.execute("UPDATE announcements SET title='',body='',link='' WHERE id=?", (nid,))
        if remaining:
            users = db.execute('SELECT user_id FROM announcement_recipients WHERE announcement_id=? UNION SELECT user_id FROM announcement_states WHERE announcement_id=? ORDER BY user_id LIMIT ?', (nid, nid, remaining)).fetchall()
            if users:
                marks = ','.join('?' for _ in users)
                values = (nid, *(user['user_id'] for user in users))
                db.execute('DELETE FROM announcement_states WHERE announcement_id=? AND user_id IN (' + marks + ')', values)
                db.execute('DELETE FROM announcement_recipients WHERE announcement_id=? AND user_id IN (' + marks + ')', values)
                remaining -= len(users)
        db.execute('DELETE FROM announcements WHERE id=? AND NOT EXISTS(SELECT 1 FROM announcement_recipients WHERE announcement_id=?) AND NOT EXISTS(SELECT 1 FROM announcement_states WHERE announcement_id=?)', (nid, nid, nid))
