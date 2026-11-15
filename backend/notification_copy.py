"""Public, bundled translations for system messages; never translates user text."""
from functools import lru_cache
import json
from pathlib import Path


@lru_cache(maxsize=1)
def packs():
    return json.loads(Path(__file__).with_name('webassets').joinpath('app','locales.json').read_text())


def supported_locale(locale):
    return isinstance(locale,str) and locale in packs()


def message(key,locale='ru'):
    # Callers supply fixed system keys, not account or announcement content.
    catalog=packs()
    return catalog.get(locale,catalog['ru'])['strings'].get(key,catalog['en']['strings'][key])


def subscription_locale(backend,subscription):
    try:
        value=json.loads(backend.cipher.decrypt(bytes(subscription['secret'])))
        locale=value.get('locale','ru')
        return locale if supported_locale(locale) else 'ru'
    except Exception:
        return 'ru'


def inbox_template(row):
    """Annotate only messages created by fixed, non-editable system producers."""
    kind,body=row['kind'],row['body']
    if kind=='reminder':
        from urllib.parse import urlsplit,parse_qs
        query=parse_qs(urlsplit(row['link']).query)
        return {'message_key':'system_task_reminder' if query.get('notification')==['task'] else 'system_calendar_reminder','message_args':{}}
    if kind=='test':
        return {'message_key':'system_test_notification_queued','message_args':{}}
    if kind=='budget':
        import re
        threshold=re.fullmatch(r'Достигнут порог расходов бюджета: ([1-9][0-9]?|100)%\.',body)
        if threshold:
            return {'title_key':'module_budgets','message_key':'system_budget_threshold','message_args':{'threshold':int(threshold[1])}}
    return {}
