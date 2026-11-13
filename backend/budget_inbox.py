"""Bounded, read-only port of FamilyFinance / FinanceEngine budget arithmetic.

Only server-authorized synced records participate. No private offline data,
provider delivery, accounting writes, budget inputs or financial rules change.
"""
import calendar
import datetime as dt
import json
import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .service import Failure, canonical, require

MAX_BUDGETS = 100
MAX_EXPENSES = 5000
DEFAULTS = {'budget_enabled': False, 'budget_thresholds': [50, 80, 100], 'timezone': 'UTC'}


def budget_metrics(budget, at, expenses):
    """Exact integer equivalent of FinanceEngine.budgetRemaining plus spending.

    The participant filter is FamilyFinance.transactions. Period indexing,
    including repeating custom spans and partial first calendar periods, and
    carry rules follow lib/domain/finance_engine.dart without a per-day loop.
    """
    first = dt.date.fromisoformat(budget['start_on'])
    period, policy, allowance = budget['period'], budget['rollover'], budget['limit_minor']
    custom_days = (dt.date.fromisoformat(budget['end_on']) - first).days + 1 if period == 'custom' else 1

    def index(day):
        if period == 'month': return 12 * (day.year - first.year) + day.month - first.month
        if period == 'year': return day.year - first.year
        return (day - first).days // (7 if period == 'week' else custom_days)

    target = max(0, index(at))
    if period == 'month':
        start = max(first, dt.date(at.year, at.month, 1)) if at >= first else first
        end = dt.date(start.year, start.month, calendar.monthrange(start.year, start.month)[1])
    elif period == 'year':
        start = max(first, dt.date(at.year, 1, 1)) if at >= first else first
        end = dt.date(start.year, 12, 31)
    else:
        span = 7 if period == 'week' else custom_days
        start, end = first + dt.timedelta(days=target * span), first + dt.timedelta(days=(target + 1) * span - 1)
    result = {'start': start.isoformat(), 'end': end.isoformat(), 'spent': 0, 'available': allowance, 'future': at < first}
    if at < first:
        return result
    participants = set(budget.get('participants', []))
    buckets = {}
    for expense in expenses:
        if expense.get('kind', 'expense') != 'expense' or expense['currency'] != budget['currency']:
            continue
        if participants and not participants.intersection(expense['audience']):
            continue
        day = dt.date.fromisoformat(expense['date'])
        if day < first:
            continue
        number = index(day)
        if number <= target:
            buckets[number] = buckets.get(number, 0) + expense['amount_minor']

    def empty_periods(carry, count):
        if count <= 0: return carry
        if policy == 'none': return 0
        value = carry + allowance * count
        return 0 if policy == 'negative' and value >= 0 else value

    carry, position = 0, 0
    result['spent'] = buckets.get(target, 0)
    for number in sorted(buckets):
        carry = empty_periods(carry, number - position)
        remaining = allowance + carry - buckets[number]
        if number == target:
            result['available'] = allowance + carry
            return result
        carry = remaining if policy == 'both' or policy == 'positive' and remaining >= 0 or policy == 'negative' and remaining < 0 else 0
        position = number + 1
    result['available'] = allowance + empty_periods(carry, target - position)
    return result


class BudgetInbox:
    def __init__(self, backend):
        self.backend = backend

    def settings(self, db, user_id, body=None):
        row = db.execute('SELECT * FROM inbox_settings WHERE user_id=?', (user_id,)).fetchone()
        current = {'budget_enabled': bool(row['budget_enabled']), 'budget_thresholds': json.loads(row['budget_thresholds']),
            'timezone': row['timezone']} if row else dict(DEFAULTS)
        if body is None:
            return current
        value = {key: body.get(key, current[key]) for key in DEFAULTS}
        thresholds = value['budget_thresholds']
        require(type(value['budget_enabled']) is bool and isinstance(thresholds, list)
            and 1 <= len(thresholds) <= 20
            and all(type(threshold) is int and 1 <= threshold <= 100 for threshold in thresholds), 'budget_settings_invalid')
        require(thresholds == sorted(set(thresholds)), 'budget_settings_invalid')
        require(isinstance(value['timezone'], str) and len(value['timezone']) <= 100, 'budget_settings_invalid')
        try: ZoneInfo(value['timezone'])
        except (ValueError, ZoneInfoNotFoundError): raise Failure('budget_settings_invalid')
        db.execute('INSERT INTO inbox_settings VALUES(?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET budget_enabled=excluded.budget_enabled,budget_thresholds=excluded.budget_thresholds,timezone=excluded.timezone',
            (user_id, int(value['budget_enabled']), canonical(thresholds), value['timezone']))
        return value

    def evaluate(self, db, actor, now):
        settings = self.settings(db, actor['id'])
        if not settings['budget_enabled']:
            return {'state': 'disabled'}
        # Both scans are capped before any inbox write. Incomplete source data
        # never produces a partial total or an invented threshold crossing.
        from .entitlements import resolve
        family_sync = resolve(db, actor['id'], now)['features']['family_sync']
        # The cap itself must not reveal another member's private row count.
        # Apply the exact _workspace / _readable authority BEFORE LIMIT. Audience
        # ids are validated UUID strings in canonical JSON; matching the quoted
        # token is portable across SQLite and PostgreSQL without JSON casts.
        common = """ JOIN memberships m ON m.workspace_id=r.workspace_id AND m.user_id=? AND m.active=1
            JOIN workspaces w ON w.id=r.workspace_id AND w.dissolved=0
            LEFT JOIN profiles p ON p.id=m.profile_id AND p.workspace_id=w.id AND p.archived=0
            WHERE r.deleted=0 AND (w.kind='personal' OR ?=1)
            AND (r.owner_id=?
                OR r.visibility='private' AND EXISTS(SELECT 1 FROM grants g WHERE g.record_id=r.id AND g.user_id=?)
                OR r.visibility='shared' AND (m.role<>'child'
                    OR p.id IS NOT NULL AND r.audience LIKE (? || p.id || ?)
                        AND (r.kind='transaction' OR r.kind='budget' AND p.permissions LIKE ?))) """
        acl_params = (actor['id'], int(family_sync), actor['id'], actor['id'], '%"', '"%', '%"view_budget"%')
        budgets = db.execute('SELECT r.*,b.currency,b.limit_minor,b.period,b.start_on,b.end_on,b.rollover,b.participants FROM records r JOIN budgets b ON b.id=r.id' + common + " AND r.kind='budget' ORDER BY r.id LIMIT ?", acl_params + (MAX_BUDGETS + 1,)).fetchall()
        if len(budgets) > MAX_BUDGETS:
            return {'state': 'skipped_limit'}
        spaces = {}

        def readable(row):
            wid = row['workspace_id']
            try:
                if wid not in spaces:
                    spaces[wid] = self.backend._workspace(db, actor, wid)
                return self.backend._readable(db, actor, spaces[wid], row)
            except Failure:
                return False

        budgets = [row for row in budgets if readable(row)]
        if not budgets:
            return {'state': 'evaluated'}
        workspace_ids = sorted({row['workspace_id'] for row in budgets})
        earliest_start = min(row['start_on'] for row in budgets)
        expenses = db.execute('SELECT r.*,t.kind AS transaction_kind,t.amount_minor,t.currency,t.date FROM records r JOIN transactions t ON t.id=r.id' + common
            + " AND r.kind='transaction' AND t.kind='expense' AND r.workspace_id IN ("
            + ','.join('?' for _ in workspace_ids) + ') AND t.date>=? ORDER BY r.id LIMIT ?',
            acl_params + (*workspace_ids, earliest_start, MAX_EXPENSES + 1)).fetchall()
        if len(expenses) > MAX_EXPENSES:
            return {'state': 'skipped_limit'}
        by_workspace = {}
        for expense in expenses:
            if readable(expense):
                by_workspace.setdefault(expense['workspace_id'], []).append({**dict(expense),
                    'kind': expense['transaction_kind'], 'audience': json.loads(expense['audience'])})
        at = dt.datetime.fromtimestamp(now, ZoneInfo(settings['timezone'])).date()
        pending = []
        for row in budgets:
            budget = {**dict(row), 'participants': json.loads(row['participants'])}
            metrics = budget_metrics(budget, at, by_workspace.get(row['workspace_id'], []))
            if metrics['future'] or metrics['spent'] <= 0:
                continue
            for threshold in settings['budget_thresholds']:
                if metrics['available'] > 0 and metrics['spent'] * 100 < threshold * metrics['available']:
                    continue
                source = row['id'] + ':' + metrics['start'] + ':' + metrics['end'] + ':' + str(threshold)
                pending.append((str(uuid.uuid4()), actor['id'], source, 'Бюджеты',
                    'Достигнут порог расходов бюджета: ' + str(threshold) + '%.', '/app?tab=money', now, now, now + 90 * 86400))
        # Generic text contains no budget names, transaction details, currencies,
        # categories, amounts or record/workspace ids. History stays safe after
        # access changes; every new calculation rechecks original authority.
        for values in pending:
            db.execute('INSERT INTO budget_inbox_notifications(id,user_id,source_key,title,body,link,created_at,starts_at,expires_at) VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(user_id,source_key) DO NOTHING', values)
        return {'state': 'evaluated'}
