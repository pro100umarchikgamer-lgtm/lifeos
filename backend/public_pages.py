"""Localized editorial snapshots for the existing public page renderers."""
import base64
import hashlib
import json
import re
from copy import deepcopy
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit

from .control import Control
from .request_locale import SUPPORTED_LOCALES, current_locale
from .service import Failure, canonical, require

PUBLIC_PAGE_ROUTES = ('/', '/account', '/plans', '/privacy', '/terms', '/support',
                      '/delete-account', '/status', '/download', '/faq', '/early-access', '/docs')
_ASSETS = Path(__file__).with_name('webassets')
_BASELINE_GENERATION = '604a5c2'
_MAX_CONTENT_BYTES = 128 * 1024
_MAX_IMAGE_BYTES = 1024 * 1024
_MAX_IMAGE_PIXELS = 8_000_000
_MAX_REVISION = 9223372036854775807
_HISTORY_LIMIT = 50
_ID = re.compile(r'[a-z0-9][a-z0-9_.-]{0,79}\Z')
_MEDIA_ID = re.compile(r'[0-9a-f]{64}\Z')
_INVALID_TEXT = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\ud800-\udfff]')
_BAD_URL_CHAR = re.compile(r'[\s\\\x00-\x1f\x7f-\x9f]')
_LOCAL_ANCHOR = re.compile(r'#[a-z][a-z0-9-]*\Z')
_PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'


@lru_cache(maxsize=1)
def _catalog():
    catalog = json.loads((_ASSETS / 'public-pages-source.json').read_text(encoding='utf-8'))
    if set(catalog['pages']) != set(PUBLIC_PAGE_ROUTES):
        raise RuntimeError('Public page catalog does not match the public routes')
    return catalog


@lru_cache(maxsize=1)
def _language_sources():
    directory = _ASSETS / 'app'
    return (json.loads((directory / 'translations.json').read_text(encoding='utf-8')),
            json.loads((directory / 'locales.json').read_text(encoding='utf-8')))


@lru_cache(maxsize=1)
def _frozen_baseline():
    path = _ASSETS / f'public-pages-baseline-{_BASELINE_GENERATION}.json'
    bundle = json.loads(path.read_text(encoding='utf-8'))
    locales = bundle['locales']
    if (bundle['source_generation'] != _BASELINE_GENERATION or set(locales) != set(SUPPORTED_LOCALES)
            or any(set(pages) != set(PUBLIC_PAGE_ROUTES) for pages in locales.values())):
        raise RuntimeError('Incomplete public page source revision')
    return locales


def _source_value(ref, locale):
    if isinstance(ref, str):
        return ref
    catalog, packs = _language_sources()
    key = ref['key']
    value = catalog['source'].get(key, {})
    source = value.get('values', {})
    return (catalog['translations'].get(locale, {}).get(key)
            or packs.get(locale, {}).get('strings', {}).get(value.get('native_key'))
            or source.get(locale) or source.get('en') or source.get('ru') or ref.get('fallback') or key)


def _source_metadata():
    return {'revision': 0, 'kind': 'source', 'source_generation': _BASELINE_GENERATION,
            'from_revision': None, 'created_at': None, 'author_id': None}


def _source_document(page, locale):
    return {**_source_metadata(), 'content': deepcopy(_frozen_baseline()[locale][page])}


def _scope(page, locale):
    require(isinstance(page, str) and page in PUBLIC_PAGE_ROUTES, 'page_not_found', 404)
    require(isinstance(locale, str) and locale in SUPPORTED_LOCALES, 'invalid_locale')
    return page, locale


def _query(query, required=(), optional=()):
    require(set(required) <= set(query) <= set(required) | set(optional)
            and all(isinstance(values, list) and len(values) == 1 and isinstance(values[0], str)
                    for values in query.values()), 'invalid_fields')
    return {key: values[0] for key, values in query.items()}


def _fields(value, keys, error='invalid_page_content'):
    require(isinstance(value, dict) and set(value) == set(keys), error)


def _revision(value, minimum=0, from_query=False):
    if from_query:
        require(isinstance(value, str) and value.isascii() and value.isdecimal()
                and len(value) <= 19, 'invalid_revision')
        value = int(value)
    require(type(value) is int and minimum <= value <= _MAX_REVISION, 'invalid_revision')
    return value


def _plain(value, limit, required=False, error='invalid_page_content'):
    require(isinstance(value, str) and len(value) <= limit and not _INVALID_TEXT.search(value)
            and (not required or value.strip()), error)


def _href(value):
    _plain(value, 1024, True)
    require(not _BAD_URL_CHAR.search(value), 'invalid_page_content')
    if value.startswith('#'):
        require(_LOCAL_ANCHOR.fullmatch(value), 'invalid_page_content')
        return
    try:
        url = urlsplit(value)
        port = url.port
    except ValueError:
        raise Failure('invalid_page_content') from None
    if value.startswith('/') and not value.startswith('//'):
        require(not url.netloc and url.path in (*PUBLIC_PAGE_ROUTES, '/app', '/app/'), 'invalid_page_content')
        return
    require(value.startswith('https://') and url.hostname and '%' not in url.hostname
            and url.username is None and url.password is None and (port is None or port > 0), 'invalid_page_content')


def _validate_source_fields(values, source):
    _fields(values, source)
    for key, value in values.items():
        if key == 'href' or key.endswith('.href'):
            _href(value)
        else:
            _plain(value, 4096)


def _validate_content(page, content):
    source = _catalog()['pages'][page]
    _fields(content, ('fields', 'regions'))
    _validate_source_fields(content['fields'], source['fields'])
    regions = content['regions']
    _fields(regions, source['regions'])
    total = 0
    media = set()
    for region, blocks in regions.items():
        require(isinstance(blocks, list) and len(blocks) <= 64, 'invalid_page_content')
        total += len(blocks)
        require(total <= 128, 'invalid_page_content')
        source_blocks = {block['id']: block['fields'] for block in source['regions'][region]}
        used = set()
        for block in blocks:
            require(isinstance(block, dict), 'invalid_page_content')
            block_id, kind = block.get('id'), block.get('kind')
            require(isinstance(block_id, str) and _ID.fullmatch(block_id) and block_id not in used, 'invalid_page_content')
            used.add(block_id)
            if block_id in source_blocks:
                _fields(block, ('id', 'kind', 'fields'))
                require(kind == 'source', 'invalid_page_content')
                _validate_source_fields(block['fields'], source_blocks[block_id])
            elif kind == 'text':
                _fields(block, ('id', 'kind', 'title', 'body'))
                _plain(block['title'], 200)
                _plain(block['body'], 4096, True)
            elif kind == 'link':
                _fields(block, ('id', 'kind', 'label', 'href'))
                _plain(block['label'], 200, True)
                _href(block['href'])
            elif kind == 'image':
                _fields(block, ('id', 'kind', 'media_id', 'alt', 'caption'))
                asset_id = block['media_id']
                require(isinstance(asset_id, str) and _MEDIA_ID.fullmatch(asset_id), 'invalid_page_content')
                media.add(asset_id)
                _plain(block['alt'], 300, True)
                _plain(block['caption'], 1000)
            else:
                raise Failure('invalid_page_content')
    encoded = canonical(content)
    require(len(encoded.encode('utf-8')) <= _MAX_CONTENT_BYTES, 'invalid_page_content')
    return encoded, sorted(media)


def _png_pixels(raw):
    """Pass PNG pixel chunks only, so compressed metadata is never expanded."""
    offset = len(_PNG_SIGNATURE)
    chunks = [_PNG_SIGNATURE]
    while offset + 12 <= len(raw):
        end = offset + 12 + int.from_bytes(raw[offset:offset + 4], 'big')
        kind = raw[offset + 4:offset + 8]
        require(end <= len(raw) and kind not in (b'acTL', b'fcTL', b'fdAT'), 'invalid_page_image')
        if kind in (b'IHDR', b'PLTE', b'tRNS', b'IDAT', b'IEND'):
            chunks.append(raw[offset:end])
        if kind == b'IEND':
            return b''.join(chunks)
        offset = end
    raise Failure('invalid_page_image')


def _image_dimensions(width, height):
    require(0 < width <= 4096 and 0 < height <= 4096 and width * height <= _MAX_IMAGE_PIXELS,
            'invalid_page_image')


def _check_webp(raw):
    """Check dimensions before libwebp creates its decoding canvas."""
    require(len(raw) == 8 + int.from_bytes(raw[4:8], 'little'), 'invalid_page_image')
    offset = 12
    canvas = pixels = None
    while offset + 8 <= len(raw):
        kind = raw[offset:offset + 4]
        size = int.from_bytes(raw[offset + 4:offset + 8], 'little')
        start = offset + 8
        offset = start + size + (size % 2)
        require(offset <= len(raw) and kind not in (b'ANIM', b'ANMF'), 'invalid_page_image')
        if kind == b'VP8X':
            require(canvas is None and size == 10 and not (raw[start] & 2), 'invalid_page_image')
            canvas = (1 + int.from_bytes(raw[start + 4:start + 7], 'little'),
                      1 + int.from_bytes(raw[start + 7:start + 10], 'little'))
            _image_dimensions(*canvas)
        elif kind == b'VP8 ':
            require(pixels is None and size >= 10 and raw[start + 3:start + 6] == b'\x9d\x01\x2a',
                    'invalid_page_image')
            pixels = (int.from_bytes(raw[start + 6:start + 8], 'little') & 0x3fff,
                      int.from_bytes(raw[start + 8:start + 10], 'little') & 0x3fff)
            _image_dimensions(*pixels)
        elif kind == b'VP8L':
            require(pixels is None and size >= 5 and raw[start] == 0x2f, 'invalid_page_image')
            packed = int.from_bytes(raw[start + 1:start + 5], 'little')
            pixels = (1 + (packed & 0x3fff), 1 + ((packed >> 14) & 0x3fff))
            _image_dimensions(*pixels)
    require(offset == len(raw) and pixels and (canvas is None or canvas == pixels), 'invalid_page_image')


def _image(encoded):
    from PIL import Image, ImageOps

    max_base64 = (_MAX_IMAGE_BYTES + 2) // 3 * 4
    require(isinstance(encoded, str) and 0 < len(encoded) <= max_base64, 'invalid_page_image')
    try:
        raw = base64.b64decode(encoded, validate=True)
        require(0 < len(raw) <= _MAX_IMAGE_BYTES, 'invalid_page_image')
        if raw.startswith(_PNG_SIGNATURE):
            raw = _png_pixels(raw)
        elif raw[:4] == b'RIFF' and raw[8:12] == b'WEBP':
            _check_webp(raw)
        with Image.open(BytesIO(raw), formats=('PNG', 'JPEG', 'WEBP')) as image:
            _image_dimensions(*image.size)
            require(getattr(image, 'n_frames', 1) == 1, 'invalid_page_image')
            ImageOps.exif_transpose(image, in_place=True)
            alpha = 'A' in image.getbands() or 'transparency' in image.info
            with image.convert('RGBA' if alpha else 'RGB') as pixels:
                pixels.thumbnail((1920, 1920), Image.Resampling.LANCZOS)
                normalized = BytesIO()
                pixels.save(normalized, format='WEBP', quality=85, method=3)
                width, height = pixels.size
        data = normalized.getvalue()
    except (ValueError, OSError, SyntaxError, Image.DecompressionBombError):
        raise Failure('invalid_page_image') from None
    require(0 < len(data) <= _MAX_IMAGE_BYTES, 'invalid_page_image')
    return data, width, height


_REVISION_METADATA = 'revision,kind,source_generation,from_revision,created_at,author_id'


class PublicPages:
    def __init__(self, backend):
        self.backend = backend
        self.control = Control(backend)

    def handle(self, actor, action, method, body, query):
        self.control.require(actor, 'pages.edit')
        if method == 'GET' and action == 'pages':
            _query(query)
            return {'pages': [{'page': page, 'label': _source_value(_catalog()['pages'][page]['label'], current_locale())}
                              for page in PUBLIC_PAGE_ROUTES], 'locales': list(SUPPORTED_LOCALES)}
        if method == 'GET' and action in ('pages/page', 'pages/history', 'pages/revision', 'pages/preview'):
            required = ('page', 'lang') if action in ('pages/page', 'pages/history') else ('page', 'lang', 'revision')
            params = _query(query, required, ('before',) if action == 'pages/history' else ())
            page, locale = _scope(params['page'], params['lang'])
            with self.backend.connect() as db:
                if action == 'pages/page':
                    return self._state_result(db, page, locale)
                if action == 'pages/history':
                    before = _revision(params['before'], 1, from_query=True) if 'before' in params else _MAX_REVISION
                    return self._history(db, page, locale, before)
                revision = _revision(params['revision'], from_query=True)
                return {'page': page, 'locale': locale, **self._document(db, page, locale, revision)}
        if method != 'POST':
            raise Failure('not_found', 404)
        _query(query)
        if action == 'pages/media':
            _fields(body, ('data',), 'invalid_fields')
            return self._upload(actor, body['data'])
        if action in ('pages/save', 'pages/publish', 'pages/restore'):
            return self._mutate(actor, action, body)
        raise Failure('not_found', 404)

    def _read_state(self, db, page, locale):
        row = db.execute('SELECT version,draft_revision,published_revision FROM public_page_states WHERE page=? AND locale=?',
                         (page, locale)).fetchone()
        return dict(row) if row else {'version': 0, 'draft_revision': None, 'published_revision': None}

    def _document(self, db, page, locale, revision):
        if revision == 0:
            return _source_document(page, locale)
        row = db.execute('SELECT ' + _REVISION_METADATA + ',content FROM public_page_revisions '
                         'WHERE page=? AND locale=? AND revision=?', (page, locale, revision)).fetchone()
        require(row is not None, 'revision_not_found', 404)
        return dict(row, content=json.loads(row['content']))

    def _state_result(self, db, page, locale):
        state = self._read_state(db, page, locale)
        draft = state['draft_revision']
        published = state['published_revision']
        return {'page': page, 'locale': locale, 'version': state['version'],
                'baseline': _source_document(page, locale),
                'draft': self._document(db, page, locale, draft) if draft is not None else None,
                'published': self._document(db, page, locale, published) if published is not None else None}

    def _history(self, db, page, locale, before):
        rows = db.execute('SELECT ' + _REVISION_METADATA + ' FROM public_page_revisions '
                          'WHERE page=? AND locale=? AND revision<? ORDER BY revision DESC LIMIT ?',
                          (page, locale, before, _HISTORY_LIMIT + 1)).fetchall()
        entries = [dict(row) for row in rows]
        if len(entries) <= _HISTORY_LIMIT:
            entries.append(_source_metadata())
        result = entries[:_HISTORY_LIMIT]
        return {'revisions': result, 'next_before': result[-1]['revision'] if len(entries) > _HISTORY_LIMIT else None}

    def _mutate(self, actor, action, body):
        mode = action.removeprefix('pages/')
        operation_fields = {'save': ('content',), 'publish': ('draft_revision', 'reason'),
                            'restore': ('revision', 'reason')}
        if mode == 'publish':
            self.control.require(actor, 'pages.publish')
        _fields(body, ('page', 'locale', 'expected_version', *operation_fields[mode]), 'invalid_fields')
        page, locale = _scope(body['page'], body['locale'])
        expected = _revision(body['expected_version'])
        revision = expected + 1
        kind = {'save': 'draft', 'publish': 'published', 'restore': 'restored'}[mode]
        event = {'save': 'page.draft.save', 'publish': 'page.publish', 'restore': 'page.restore_draft'}[mode]
        if mode == 'save':
            reason = 'Public page draft saved'
            encoded, media = _validate_content(page, body['content'])
            generation = _catalog()['source_generation']
        else:
            reason = body['reason']
            _plain(reason, 500, True, 'invalid_fields')
        with self.backend.transaction() as db:
            before = self._read_state(db, page, locale)
            require(expected == before['version'] and revision <= _MAX_REVISION, 'revision_conflict', 409)
            if mode == 'save':
                from_revision = before['draft_revision'] or before['published_revision'] or 0
            else:
                if mode == 'publish':
                    from_revision = _revision(body['draft_revision'], 1)
                    require(from_revision == before['draft_revision'], 'revision_conflict', 409)
                else:
                    from_revision = _revision(body['revision'])
                source = self._document(db, page, locale, from_revision)
                generation = source['source_generation']
                encoded, media = _validate_content(page, source['content'])
            self._require_media(db, media)
            db.execute('INSERT INTO public_page_revisions '
                       '(page,locale,revision,kind,from_revision,source_generation,content,created_at,author_id) '
                       'VALUES(?,?,?,?,?,?,?,?,?)', (page, locale, revision, kind, from_revision, generation, encoded,
                                                   int(self.backend.clock()), actor.id))
            for media_id in media:
                db.execute('INSERT INTO public_page_revision_media(page,locale,revision,media_id) VALUES(?,?,?,?)',
                           (page, locale, revision, media_id))
            draft = None if mode == 'publish' else revision
            published = revision if mode == 'publish' else before['published_revision']
            db.execute('INSERT INTO public_page_states(page,locale,version,draft_revision,published_revision) VALUES(?,?,?,?,?) '
                       'ON CONFLICT(page,locale) DO UPDATE SET version=excluded.version,draft_revision=excluded.draft_revision,'
                       'published_revision=excluded.published_revision', (page, locale, revision, draft, published))
            after = {'page': page, 'locale': locale, 'revision': revision, 'draft_revision': draft,
                     'published_revision': published, 'from_revision': from_revision, 'asset_count': len(media)}
            self.control.audit(db, actor, None, event, before, after, reason)
            return self._state_result(db, page, locale)

    def _require_media(self, db, media):
        if media:
            placeholders = ','.join('?' for _ in media)
            count = db.execute('SELECT COUNT(*) AS n FROM public_page_media WHERE id IN (' + placeholders + ')',
                               tuple(media)).fetchone()['n']
            require(count == len(media), 'media_not_found', 404)

    def _upload(self, actor, encoded):
        data, width, height = _image(encoded)
        media_id = hashlib.sha256(data).hexdigest()
        mime = 'image/webp'
        with self.backend.transaction() as db:
            inserted = db.execute('INSERT INTO public_page_media(id,data,mime,width,height,created_at,author_id) '
                                  'VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO NOTHING',
                                  (media_id, data, mime, width, height, int(self.backend.clock()), actor.id))
            if inserted.rowcount:
                self.control.audit(db, actor, None, 'page.media.upload', {},
                                   {'media_id': media_id, 'width': width, 'height': height, 'bytes': len(data)},
                                   'Public page raster uploaded')
        return {'id': media_id, 'mime': mime, 'width': width, 'height': height}

    def public_document(self, page, locale):
        page, locale = _scope(page, locale)
        with self.backend.connect() as db:
            row = db.execute('SELECT r.revision,r.content FROM public_page_states s JOIN public_page_revisions r '
                             'ON r.page=s.page AND r.locale=s.locale AND r.revision=s.published_revision '
                             'WHERE s.page=? AND s.locale=?', (page, locale)).fetchone()
        return {'page': page, 'locale': locale, 'revision': row['revision'] if row else 0,
                'content': json.loads(row['content']) if row else _source_document(page, locale)['content']}

    def public_media(self, media_id):
        return self._media(media_id, public=True)

    def preview_media(self, actor, media_id):
        self.control.require(actor, 'pages.edit')
        return self._media(media_id, public=False)

    def _media(self, media_id, public):
        require(isinstance(media_id, str) and _MEDIA_ID.fullmatch(media_id), 'media_not_found', 404)
        sql = 'SELECT m.data,m.mime FROM public_page_media m WHERE m.id=?'
        if public:
            sql += (' AND EXISTS (SELECT 1 FROM public_page_revision_media r JOIN public_page_states s '
                    'ON s.page=r.page AND s.locale=r.locale AND s.published_revision=r.revision WHERE r.media_id=m.id)')
        with self.backend.connect() as db:
            row = db.execute(sql, (media_id,)).fetchone()
        require(row is not None, 'media_not_found', 404)
        return bytes(row['data']), row['mime']
