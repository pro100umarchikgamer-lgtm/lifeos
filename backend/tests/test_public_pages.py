"""Public page revisions use real SQLite and optional isolated PostgreSQL."""
import base64
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from io import BytesIO
import os
from pathlib import Path
import tempfile
from threading import Barrier
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit
import uuid

from cryptography.fernet import Fernet
from PIL import Image, PngImagePlugin

from backend import public_pages
from backend.control import StaffPrincipal
from backend.public_pages import PublicPages
from backend.service import Backend, Failure


class PublicPageScenarios:
    def fixtures(self):
        self.pages = PublicPages(self.backend)
        uid, sid = str(uuid.uuid4()), str(uuid.uuid4())
        with self.backend.transaction() as db:
            db.execute('INSERT INTO users(id,email,password_hash,salt,verified,created_at) VALUES(?,?,?,?,1,1)',
                       (uid, 'pages@example.test', '', ''))
            db.execute('INSERT INTO staff(id,user_id,roles,mfa_secret,created_at) VALUES(?,?,?,?,1)',
                       (sid, uid, '["owner"]', b''))
        self.owner = StaffPrincipal(sid, uid, ('owner',))

    def read(self, action, actor=None, **query):
        return self.pages.handle(actor or self.owner, 'pages' + action, 'GET', {},
                                 {key: [str(value)] for key, value in query.items()})

    def write(self, action, actor=None, page='/', locale='en', **payload):
        data = {'page': page, 'locale': locale, **payload} if action != '/media' else payload
        return self.pages.handle(actor or self.owner, 'pages' + action, 'POST', data, {})

    def baseline(self, page='/', locale='en'):
        return self.read('/page', page=page, lang=locale)['baseline']['content']

    def error(self, code, status, fn, *args, **kwargs):
        with self.assertRaises(Failure) as caught:
            fn(*args, **kwargs)
        self.assertEqual((caught.exception.code, caught.exception.status), (code, status))

    def test_source_catalog_covers_routes_and_resolves_selected_locale(self):
        listing = self.read('')
        self.assertEqual({row['page'] for row in listing['pages']}, {'/', '/account', '/plans', '/privacy',
            '/terms', '/support', '/delete-account', '/status', '/download', '/faq', '/early-access', '/docs'})
        self.assertEqual(set(listing['locales']), {'az', 'de', 'en', 'es', 'fr', 'hy', 'it', 'ka', 'kk',
            'ky', 'pt', 'ru', 'tg', 'uk', 'uz-Cyrl', 'uz-Latn'})
        self.assertNotEqual(self.baseline('/privacy', 'en'), self.baseline('/privacy', 'de'))
        for page in listing['pages']:
            with self.subTest(page=page['page']):
                self.assertTrue(self.baseline(page['page'])['fields'])
                self.assertEqual(self.pages.public_document(page['page'], 'uz-Cyrl'),
                                 {'page': page['page'], 'locale': 'uz-Cyrl', 'revision': 0,
                                  'content': self.baseline(page['page'], 'uz-Cyrl')})
        self.error('invalid_fields', 400, self.pages.handle, self.owner, 'pages/page', 'GET', {},
                   {'page': ['/'], 'lang': ['en', 'ru']})
        self.error('page_not_found', 404, self.pages.public_document, '/app', 'en')
        self.error('invalid_locale', 400, self.pages.public_document, '/', 'uz')

    def test_draft_preview_publish_and_source_restore_are_scoped(self):
        source = self.baseline()
        content = deepcopy(source)
        region = next(iter(content['regions']))
        new_block = {'id': 'article-first', 'kind': 'text', 'title': 'Editorial update', 'body': 'Private draft copy'}
        content['regions'][region] = [new_block, *reversed(content['regions'][region][1:])]
        draft = self.write('/save', expected_version=0, content=content)
        self.assertEqual(draft['version'], 1)
        self.assertEqual(draft['draft']['content'], content)
        self.assertIsNone(draft['published'])
        self.assertEqual(self.pages.public_document('/', 'en')['revision'], 0)
        preview = self.read('/preview', page='/', lang='en', revision=1)
        self.assertEqual(preview['content'], content)
        self.error('revision_not_found', 404, self.read, '/preview', page='/', lang='de', revision=1)
        self.error('revision_conflict', 409, self.write, '/publish', expected_version=1,
                   draft_revision=2, reason='Review complete')
        published = self.write('/publish', expected_version=1, draft_revision=1, reason='Review complete')
        self.assertIsNone(published['draft'])
        self.assertEqual(published['published']['from_revision'], 1)
        self.assertEqual(self.pages.public_document('/', 'en'), {'page': '/', 'locale': 'en',
            'revision': 2, 'content': content})
        self.assertEqual(self.pages.public_document('/', 'de')['content'], self.baseline('/', 'de'))
        self.assertEqual(self.pages.public_document('/docs', 'en')['content'], self.baseline('/docs', 'en'))

        restored = self.write('/restore', expected_version=2, revision=0, reason='Restore source')
        self.assertEqual(restored['draft']['content'], source)
        self.assertEqual(restored['draft']['from_revision'], 0)
        self.assertEqual(self.pages.public_document('/', 'en')['content'], content)
        self.write('/publish', expected_version=3, draft_revision=3, reason='Publish source restore')
        self.assertEqual(self.pages.public_document('/', 'en')['content'], source)
        previous = self.write('/restore', expected_version=4, revision=2, reason='Recover previous publication')
        self.assertEqual(previous['draft']['content'], content)
        self.assertEqual(previous['draft']['from_revision'], 2)
        self.assertEqual(self.pages.public_document('/', 'en')['content'], source)
        self.write('/publish', expected_version=5, draft_revision=5, reason='Publish recovered copy')
        self.assertEqual(self.pages.public_document('/', 'en')['content'], content)
        history = self.read('/history', page='/', lang='en', before=2)
        self.assertEqual([item['revision'] for item in history['revisions']], [1, 0])
        self.assertTrue(all('content' not in item for item in history['revisions']))
        self.assertEqual(self.read('/revision', page='/', lang='en', revision=2)['content'], content)

    def test_source_revision_is_frozen_when_live_translation_changes(self):
        source = self.baseline()
        title_key = public_pages._catalog()['pages']['/']['fields']['title']['key']
        pack, native = public_pages._language_sources()
        live_translations = {**pack['translations'],
                             'en': {**pack['translations']['en'], title_key: 'New live translation'}}
        public_pages._language_sources.cache_clear()
        public_pages._frozen_baseline.cache_clear()
        with patch.object(public_pages, '_language_sources', return_value=(
                {**pack, 'translations': live_translations}, native)):
            self.assertEqual(self.baseline(), source)
            restored = self.write('/restore', expected_version=0, revision=0, reason='Restore source copy')
            self.assertEqual(restored['draft']['content'], source)
        caller_copy = self.baseline()
        caller_copy['fields']['title'] = 'Caller-local edit'
        self.assertEqual(self.baseline(), source)

    def test_public_source_fallback_matches_immutable_revision_zero(self):
        source = self.baseline()
        self.assertEqual(self.pages.public_document('/', 'en')['content'], source)
        changed = deepcopy(source)
        changed['fields']['title'] = 'Private draft must stay private'
        self.write('/save', expected_version=0, content=changed)
        self.assertEqual(self.pages.public_document('/', 'en')['content'], source)
        pack, native = public_pages._language_sources()
        key = public_pages._catalog()['pages']['/']['fields']['title']['key']
        with patch.object(public_pages, '_language_sources', return_value=(
                {**pack, 'translations': {**pack['translations'],
                  'en': {**pack['translations']['en'], key: 'Future application copy'}}}, native)):
            self.assertEqual(self.pages.public_document('/', 'en')['content'], source)

    def test_simultaneous_scoped_writes_have_one_winner(self):
        barrier = Barrier(2)
        source = self.baseline()
        field = next(iter(source['fields']))

        def save(value):
            content = deepcopy(source)
            content['fields'][field] = value
            barrier.wait(timeout=5)
            try:
                return self.write('/save', expected_version=0, content=content)['draft']['content']['fields'][field]
            except Failure as error:
                return error.code, error.status

        with ThreadPoolExecutor(max_workers=2) as workers:
            first, second = list(workers.map(save, ('First writer', 'Second writer')))
        self.assertEqual([first, second].count(('revision_conflict', 409)), 1)
        state = self.read('/page', page='/', lang='en')
        winner = second if first == ('revision_conflict', 409) else first
        self.assertEqual((state['version'], state['draft']['content']['fields'][field]), (1, winner))

    def test_publish_and_audit_roll_back_together(self):
        state = self.write('/save', expected_version=0, content=self.baseline())
        audit = self.pages.control.audit

        def fail_after_audit(*args):
            audit(*args)
            raise RuntimeError('simulated transaction failure')

        with patch.object(self.pages.control, 'audit', side_effect=fail_after_audit), self.assertRaises(RuntimeError):
            self.write('/publish', expected_version=1, draft_revision=1, reason='Review complete')
        self.assertEqual(self.read('/page', page='/', lang='en'), state)
        self.assertEqual(self.pages.public_document('/', 'en')['revision'], 0)
        with self.backend.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) AS n FROM control_audit').fetchone()['n'], 1)

    def test_role_and_deny_restrictions_apply_to_every_control_read_and_publish(self):
        no_edit = StaffPrincipal(self.owner.id, self.owner.user_id, ('owner',), ('pages.edit',))
        editor = StaffPrincipal(self.owner.id, self.owner.user_id, ('content_editor',))
        for action, query in (('', {}), ('/page', {'page': '/', 'lang': 'en'}),
                              ('/history', {'page': '/', 'lang': 'en'}),
                              ('/preview', {'page': '/', 'lang': 'en', 'revision': 0})):
            self.error('staff_forbidden', 403, self.read, action, actor=no_edit, **query)
        self.error('staff_forbidden', 403, self.pages.preview_media, no_edit, '0' * 64)
        self.write('/save', actor=editor, expected_version=0, content=self.baseline())
        self.error('staff_forbidden', 403, self.write, '/publish', actor=editor, expected_version=1,
                   draft_revision=1, reason='No publish capability')
        for role in ('support', 'moderator', 'billing_manager', 'admin', 'auditor'):
            self.error('staff_forbidden', 403, self.read, '', actor=StaffPrincipal(self.owner.id, self.owner.user_id, (role,)))

    def test_types_links_and_references_are_validated_before_state_changes(self):
        source = self.baseline()
        region = next(iter(source['regions']))
        invalid_blocks = (
            {'id': 'new-link', 'kind': 'link', 'label': 'Unsafe', 'href': 'javascript:alert(1)'},
            {'id': 'new-link', 'kind': 'link', 'label': 'Unsafe', 'href': '//example.test'},
            {'id': 'new-link', 'kind': 'link', 'label': 'Unsafe', 'href': '/app\\@example.test'},
            {'id': 'new-link', 'kind': 'link', 'label': 'Unsafe', 'href': 'https://name@example.test'},
            {'id': 'new-link', 'kind': 'link', 'label': 'Unsafe', 'href': '/control/api/pages'},
            {'id': 'new-link', 'kind': 'link', 'label': 'Invalid anchor', 'href': '#private%2Fscope'},
            {'id': 'new-html', 'kind': 'html', 'html': '<p>arbitrary markup</p>'},
            {'id': 'new-text', 'kind': 'text', 'title': '', 'body': '\ud800'},
            {'id': 'unknown-source', 'kind': 'source', 'fields': {}},
        )
        for block in invalid_blocks:
            with self.subTest(block=block):
                content = deepcopy(source)
                content['regions'][region].append(block)
                self.error('invalid_page_content', 400, self.write, '/save', expected_version=0, content=content)
        content = deepcopy(source)
        content['fields']['unapproved'] = 'extra field'
        self.error('invalid_page_content', 400, self.write, '/save', expected_version=0, content=content)
        content = deepcopy(source)
        content['regions'][region].append({'id': 'new-photo', 'kind': 'image', 'media_id': '0' * 64,
                                           'alt': 'Screenshot', 'caption': ''})
        self.error('media_not_found', 404, self.write, '/save', expected_version=0, content=content)
        self.assertEqual(self.read('/page', page='/', lang='en')['version'], 0)

    def test_image_is_normalized_and_visible_only_through_current_publication(self):
        metadata = PngImagePlugin.PngInfo()
        metadata.add_text('private-note', 'Fixture metadata stripped')
        image = BytesIO()
        Image.new('RGB', (32, 16), (120, 40, 80)).save(image, format='PNG', pnginfo=metadata)
        data = base64.b64encode(image.getvalue()).decode('ascii')
        media = self.write('/media', data=data)
        self.assertEqual(self.write('/media', data=data), media)
        self.assertEqual((media['width'], media['height']), (32, 16))
        raster, mime = self.pages.preview_media(self.owner, media['id'])
        self.assertEqual(mime, media['mime'])
        self.assertNotIn(b'Fixture metadata stripped', raster)
        with Image.open(BytesIO(raster)) as clean:
            self.assertEqual(clean.size, (32, 16))
        self.error('media_not_found', 404, self.pages.public_media, media['id'])
        content = self.baseline()
        region = next(iter(content['regions']))
        content['regions'][region].append({'id': 'new-photo', 'kind': 'image', 'media_id': media['id'],
                                           'alt': 'Screenshot', 'caption': ''})
        self.write('/save', expected_version=0, content=content)
        self.error('media_not_found', 404, self.pages.public_media, media['id'])
        self.write('/publish', expected_version=1, draft_revision=1, reason='Publish image')
        self.assertEqual(self.pages.public_media(media['id']), (raster, mime))
        self.write('/restore', expected_version=2, revision=0, reason='Restore original')
        self.write('/publish', expected_version=3, draft_revision=3, reason='Publish original')
        self.error('media_not_found', 404, self.pages.public_media, media['id'])
        self.assertEqual(self.pages.preview_media(self.owner, media['id']), (raster, mime))

    def test_invalid_and_multi_frame_images_are_rejected(self):
        for raw in (b'<svg xmlns="http://www.w3.org/2000/svg"/>', b'\x89PNG\r\n\x1a\ntruncated', b'x' * (1024 * 1024 + 1)):
            self.error('invalid_page_image', 400, self.write, '/media', data=base64.b64encode(raw).decode('ascii'))
        stream = BytesIO()
        Image.new('RGB', (1, 1), 'green').save(stream, format='PNG', save_all=True,
            append_images=[Image.new('RGB', (1, 1), 'blue')])
        self.error('invalid_page_image', 400, self.write, '/media', data=base64.b64encode(stream.getvalue()).decode('ascii'))

    def test_oversized_webp_is_rejected_before_native_decoder_opens_it(self):
        stream = BytesIO()
        Image.new('RGB', (4097, 2), 'blue').save(stream, format='WEBP')
        data = base64.b64encode(stream.getvalue()).decode('ascii')
        with patch.object(Image, 'open', side_effect=AssertionError('Oversized WebP reached the decoder')):
            self.error('invalid_page_image', 400, self.write, '/media', data=data)


class PublicPagesTests(PublicPageScenarios, unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.backend = Backend(Path(folder.name) / 'pages.db')
        self.backend.cipher = Fernet(Fernet.generate_key())
        self.fixtures()


DSN = os.environ.get('LIFEOS_TEST_DATABASE_URL', '')


@unittest.skipUnless(DSN, 'Requires isolated lifeos_test PostgreSQL database')
class PublicPagesPostgresTests(PublicPageScenarios, unittest.TestCase):
    def setUp(self):
        if urlsplit(DSN).path != '/lifeos_test':
            raise RuntimeError('Tests refuse a non-test database')
        import psycopg
        from psycopg import sql
        from backend.postgres import PostgresBackend

        schema = 'public_pages_test_' + uuid.uuid4().hex
        with psycopg.connect(DSN, autocommit=True) as db:
            db.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))

        def drop_schema():
            with psycopg.connect(DSN, autocommit=True) as db:
                db.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))

        self.addCleanup(drop_schema)
        self.backend = PostgresBackend(DSN, Fernet(Fernet.generate_key()), schema=schema, migrate=True)
        self.addCleanup(self.backend.close)
        self.fixtures()

    def test_repeated_migration_keeps_published_revision(self):
        content = self.baseline()
        self.write('/save', expected_version=0, content=content)
        self.write('/publish', expected_version=1, draft_revision=1, reason='Publish before repeat')
        self.backend.migrate()
        self.backend.migrate()
        self.assertEqual(self.pages.public_document('/', 'en')['content'], content)
