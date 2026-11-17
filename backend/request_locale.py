"""Bounded display locale for one request; never an account or auth property."""
from contextlib import contextmanager
from contextvars import ContextVar
import re

SUPPORTED_LOCALES = ('ru', 'en', 'uz-Latn', 'uz-Cyrl', 'de', 'fr', 'es', 'it',
                     'pt', 'kk', 'uk', 'ka', 'az', 'hy', 'tg', 'ky')
_TAGS = {tag.casefold(): tag for tag in SUPPORTED_LOCALES}
_CURRENT = ContextVar('uladim_request_locale', default='ru')
_RANGE = re.compile(r'([A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*)(?:\s*;\s*q=(0(?:\.\d{1,3})?|1(?:\.0{1,3})?))?')


def normalize_locale(value):
    return _TAGS.get(value.casefold(), 'ru') if isinstance(value, str) else 'ru'


def negotiate_locale(header):
    if not isinstance(header, str) or len(header) > 512 or not header.isascii() or '\r' in header or '\n' in header:
        return 'ru'
    selected, best = 'ru', 0.0
    for item in header.split(',')[:16]:
        match = _RANGE.fullmatch(item.strip())
        if not match:
            continue
        weight = float(match[2]) if match[2] is not None else 1.0
        parts = match[1].casefold().split('-')
        tag = _TAGS.get(match[1].casefold())
        if tag is None and parts[0] == 'uz':
            tag = _TAGS.get('uz-' + parts[1]) if len(parts) > 1 and len(parts[1]) == 4 else 'uz-Latn'
        elif tag is None:
            tag = _TAGS.get(parts[0])
        if tag is not None and weight > best:
            selected, best = tag, weight
    return selected


def current_locale():
    return _CURRENT.get()


@contextmanager
def request_locale(header):
    token = _CURRENT.set(negotiate_locale(header))
    try:
        yield _CURRENT.get()
    finally:
        _CURRENT.reset(token)
