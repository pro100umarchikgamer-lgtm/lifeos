"""Exact future-account cohorts, allocated inside the existing inbox transaction."""

EVERGREEN_EXPIRY = 253402300799  # 9999-12-31; numeric for installed client compatibility.


def targeting_in(db, announcement_id):
    row = db.execute('SELECT mode,no_expiry,cohort_at FROM announcement_targeting WHERE announcement_id=?',
                     (announcement_id,)).fetchone()
    return dict(row) if row else None


def publish_in(db, announcement_id, now):
    """Timestamp plus exact second ties describes the committed publication cut.

    Account creation and publication already share the backend mutation lock.
    Existing earlier accounts are excluded by their timestamp, so no global
    user snapshot is persisted just to describe a future cohort.
    """
    db.execute('UPDATE announcement_targeting SET cohort_at=? WHERE announcement_id=?', (now, announcement_id))
    db.execute('INSERT INTO announcement_cohort_exclusions(announcement_id,user_id) '
               'SELECT ?,id FROM users WHERE created_at=?', (announcement_id, now))


def allocate_in(db, user_id, now):
    """Attach at most one active newcomer welcome to this authenticated account.

    A durable account claim survives announcement retention. The newest eligible
    campaign wins if multiple active welcomes overlap at the first app open.
    The calling inbox transaction serializes allocation on both backends.
    """
    if db.execute('SELECT 1 FROM newcomer_welcome_claims WHERE user_id=?', (user_id,)).fetchone():
        return
    row = db.execute("""SELECT a.id FROM announcements a
        JOIN announcement_targeting t ON t.announcement_id=a.id
        JOIN users u ON u.id=?
        LEFT JOIN account_state s ON s.user_id=u.id
        WHERE a.state='published' AND a.starts_at<=? AND a.expires_at>?
          AND t.mode='newcomers' AND u.created_at>=t.cohort_at
          AND u.verified=1 AND COALESCE(s.deleted_at,0)=0
          AND NOT EXISTS(SELECT 1 FROM deletion_jobs j WHERE j.user_id=u.id AND j.state='erasing')
          AND NOT EXISTS(SELECT 1 FROM announcement_cohort_exclusions e
                         WHERE e.announcement_id=a.id AND e.user_id=u.id)
        ORDER BY a.published_at DESC,a.id DESC LIMIT 1""", (user_id, now, now)).fetchone()
    if not row:
        return
    claim = db.execute('INSERT INTO newcomer_welcome_claims(user_id,announcement_id,claimed_at) '
                       'VALUES(?,?,?) ON CONFLICT(user_id) DO NOTHING RETURNING user_id',
                       (user_id, row['id'], now)).fetchone()
    if claim:
        db.execute('INSERT INTO announcement_recipients(announcement_id,user_id) VALUES(?,?) '
                   'ON CONFLICT(announcement_id,user_id) DO NOTHING', (row['id'], user_id))
