import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import uuid
from urllib.parse import urlsplit
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from backend.control import StaffPrincipal
from backend.native_download import CERTIFICATE, NativeDownload
from backend.service import Backend, Failure
from backend.tests.test_apk_verifier import FIXTURES, verifier


class AndroidReleaseTests(unittest.TestCase):
    def database(self):
        return Backend(self.folder / 'db')

    def setUp(self):
        from backend.android_releases import AndroidReleases
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        self.store = self.folder / 'managed'
        self.store.mkdir(mode=0o700)
        self.cache = self.folder / 'legacy'
        self.cache.mkdir()
        self.source = 'd' * 40
        apk = b'PK\x03\x04' + b'previously-accepted-by-operator'
        self.original = {'source': self.source, 'version_code': 400001, 'version_name': '0.1',
            'bytes': len(apk), 'apk_sha256': hashlib.sha256(apk).hexdigest(), 'certificate_sha256': CERTIFICATE,
            'apk_url': 'https://github.com/pro100umarchikgamer-lgtm/lifeos/releases/download/uladim-native-' + self.source[:12] + '/ULADIM.apk'}
        (self.cache / 'release.json').write_text(json.dumps(self.original))
        (self.cache / 'ULADIM.apk').write_bytes(apk)
        self.legacy = NativeDownload(str(self.cache), trusted_uid=os.getuid())
        self.backend = self.database()
        self.owner = StaffPrincipal('fixture', 'fixture-user', ('owner',))
        with self.backend.transaction() as db:
            db.execute("INSERT INTO users(id,email,password_hash,salt,created_at) VALUES('fixture-user','fixture@example.test','','',0)")
            db.execute("INSERT INTO staff(id,user_id,roles,mfa_secret,created_at) VALUES(?,?,?,?,0)",
                       (self.owner.id, self.owner.user_id, '["owner"]', b'fixture'))
        self.settings = SimpleNamespace(native_publish_dir=str(self.store))
        self.manager = AndroidReleases(self.backend, self.settings, self.legacy)

    def action(self, action, row=None, actor=None):
        return self.manager.handle(actor or self.owner, 'android-releases' + ('/' + action if action else ''),
            'POST' if action else 'GET', {'id': row['id'], 'revision': row['revision']} if row else {}, {})

    def upload(self, row, data, length=None, actor=None):
        return self.manager.upload(actor or self.owner, {'REQUEST_METHOD': 'POST',
            'CONTENT_TYPE': 'application/octet-stream', 'HTTP_X_RELEASE_ID': row['id'],
            'HTTP_X_RELEASE_REVISION': str(row['revision']), 'CONTENT_LENGTH': str(len(data) if length is None else length),
            'wsgi.input': io.BytesIO(data)})

    def validated(self, name='first.apk'):
        self.manager.verifier = verifier(self)
        row = self.action('draft')
        return self.action('validate', self.upload(row, (FIXTURES / name).read_bytes()))

    def download(self, path, method='GET', **kw):
        return self.manager.download_response({'PATH_INFO': path, 'REQUEST_METHOD': method, **kw})

    def test_legacy_pointer_and_incomplete_upload_leave_old_release_usable(self):
        self.assertEqual(self.manager.public_manifest(), self.original)
        row = self.action('draft')
        self.assertEqual(row['revision'], 1)
        with self.assertRaises(Failure):
            self.upload(row, b'abc', 500)
        self.assertEqual(self.action('')['drafts'][0]['state'], 'draft')
        self.assertEqual(self.action('cancel', row)['state'], 'cancelled')
        self.assertEqual(self.manager.public_manifest(), self.original)
        self.assertEqual(list(self.store.glob('*.apk')), [])
        status, _, it = self.download('/download/android/' + self.source + '/ULADIM.apk')
        self.assertEqual(status, 200)
        self.assertEqual(b''.join(it), (self.cache / 'ULADIM.apk').read_bytes())

    def test_role_checks_precede_upload_and_unconfigured_writes(self):
        actor = StaffPrincipal('staff', 'user', ('admin',))
        with self.assertRaises(Failure) as denied:
            self.manager.upload(actor, {})
        self.assertEqual(denied.exception.status, 403)
        self.settings.native_publish_dir = ''
        from backend.android_releases import AndroidReleases
        self.manager = AndroidReleases(self.backend, self.settings, self.legacy)
        with self.assertRaises(Failure) as disabled:
            self.action('draft')
        self.assertEqual(disabled.exception.status, 503)
        self.assertEqual(self.manager.public_manifest(), self.original)

    def test_published_and_prior_bytes_remain_immutable(self):
        row = self.validated()
        self.assertEqual(row['state'], 'validated')
        path = '/download/android/sha256/' + row['apk_sha256'] + '/ULADIM.apk'
        self.assertEqual(self.download(path)[0], 404)
        with patch.object(self.manager.control, 'audit', side_effect=RuntimeError('transaction rollback')), self.assertRaises(RuntimeError):
            self.action('publish', row)
        self.assertEqual(self.manager.public_manifest(), self.original)
        self.action('publish', row)
        manifest = self.manager.public_manifest()
        self.assertEqual(manifest['origin'], 'control')
        self.assertEqual(set(manifest), {'origin','version_code','version_name','bytes','apk_url','apk_sha256','certificate_sha256'})
        self.assertEqual(manifest['apk_url'], path)
        status, headers, body = self.download(path, 'HEAD')
        self.assertEqual((status, body), (200, []))
        self.assertEqual(dict(headers)['X-ULADIM-Origin'], 'control')
        self.assertNotIn('X-ULADIM-Source', dict(headers))
        status, _, old_stream = self.download(path)
        self.assertEqual(status, 200)
        second = self.validated('second.apk')
        self.action('publish', second)
        self.assertEqual(b''.join(old_stream), (FIXTURES / 'first.apk').read_bytes())
        status, headers, body = self.download(path, HTTP_RANGE='bytes=5-9')
        self.assertEqual((status, b''.join(body)), (206, (FIXTURES / 'first.apk').read_bytes()[5:10]))
        self.assertEqual(self.manager.public_manifest()['version_code'], 400003)
        self.assertEqual(self.validated()['error'], 'apk_version_not_newer')

    def test_two_same_version_publishers_have_one_winner(self):
        draft1, draft2 = self.validated(), self.validated()
        barrier, outcomes = threading.Barrier(2), []
        def publish(row):
            barrier.wait(timeout=4)
            try:
                outcomes.append(self.action('publish', row)['state'])
            except Failure as error:
                outcomes.append(error.status)
        workers = [threading.Thread(target=publish, args=(r,)) for r in (draft1, draft2)]
        for worker in workers: worker.start()
        for worker in workers: worker.join(8)
        self.assertCountEqual(outcomes, ['published', 409])
        self.assertEqual(len(self.action('')['history']), 1)

    def test_tamper_after_validation_prevents_publication(self):
        row = self.validated()
        files = list(self.store.glob('*.apk'))
        self.assertEqual(len(files), 1)
        files[0].chmod(0o600)
        with files[0].open('r+b') as stream:
            stream.seek(100)
            stream.write(b'tampered')
        with self.assertRaises(Failure):
            self.action('publish', row)
        self.assertEqual(self.manager.public_manifest(), self.original)

    def test_manifest_requires_actual_consistent_legacy_bytes(self):
        (self.cache / 'ULADIM.apk').write_bytes(b'wrong')
        self.assertIsNone(self.manager.public_manifest())

    def test_cancellation_wins_during_stream_without_orphan_or_publication(self):
        draft = self.action('draft')
        started, resume = threading.Event(), threading.Event()
        class SlowInput:
            def read(self, size):
                started.set()
                resume.wait(timeout=5)
                return b'x' * size
        result = []
        def worker():
            try:
                self.manager.upload(self.owner, {'REQUEST_METHOD':'POST', 'CONTENT_TYPE':'application/octet-stream',
                    'HTTP_X_RELEASE_ID':draft['id'], 'HTTP_X_RELEASE_REVISION':'1', 'CONTENT_LENGTH':'10', 'wsgi.input':SlowInput()})
            except Failure as error:
                result.append(error.code)
        thread = threading.Thread(target=worker)
        thread.start()
        try:
            self.assertTrue(started.wait(timeout=5))
            self.assertEqual(self.action('cancel', draft)['state'], 'cancelled')
        finally:
            resume.set()
            thread.join(timeout=7)
        self.assertEqual(result, ['revision_conflict'])
        self.assertEqual(list(self.store.iterdir()), [])
        self.assertEqual(self.manager.public_manifest(), self.original)

    def test_validation_rejects_modified_upload_and_unknown_baseline_blocks_intake(self):
        invalid = self.upload(self.action('draft'), b'PK\x03\x04junk')
        self.manager.verifier = verifier(self)
        rejected = self.action('validate', invalid)
        self.assertEqual((rejected['state'], rejected['error']), ('rejected', 'apk_signature'))
        with self.assertRaises(Failure):
            self.action('publish', rejected)
        (self.cache / 'release.json').unlink()
        row = self.upload(self.action('draft'), (FIXTURES / 'first.apk').read_bytes())
        with self.assertRaises(Failure) as missing:
            self.action('validate', row)
        self.assertEqual(missing.exception.code, 'apk_baseline_unavailable')
        self.assertIsNone(self.manager.public_manifest())

    def test_new_worker_missing_volume_preserves_committed_selection(self):
        from backend.android_releases import AndroidReleases
        self.action('publish', self.validated())
        other_worker = AndroidReleases(self.backend, SimpleNamespace(native_publish_dir=''), self.legacy)
        with self.assertRaises(Failure) as unavailable:
            other_worker.public_manifest()
        self.assertEqual(unavailable.exception.status, 503)

    def test_missing_published_object_does_not_advertise_legacy_or_dead_link(self):
        row = self.action('publish', self.validated())
        (self.store / (row['id'] + '.apk')).unlink()
        with self.assertRaises(Failure) as unavailable:
            self.manager.public_manifest()
        self.assertEqual(unavailable.exception.status, 503)
        listing = self.action('')
        self.assertIsNone(listing['current'])
        self.assertEqual(listing['history'][0]['id'], row['id'])

    def test_corrupt_current_file_rejects_manifest_even_after_cached_read(self):
        row = self.action('publish', self.validated())
        self.assertEqual(self.manager.public_manifest()['apk_sha256'], row['apk_sha256'])
        path = self.store / (row['id'] + '.apk')
        path.chmod(0o600)
        with path.open('r+b') as stream:
            stream.seek(150)
            stream.write(b'corrupted')
        with self.assertRaises(Failure) as unavailable:
            self.manager.public_manifest()
        self.assertEqual(unavailable.exception.status, 503)

    def test_publish_rereads_digest_even_when_filesystem_identity_is_cached(self):
        row = self.validated()
        original_read = os.pread
        def disk_read(fd, count, offset):
            if count > 4:
                raise OSError('simulated media read failure')
            return original_read(fd, count, offset)
        with patch('backend.native_download.os.pread', side_effect=disk_read), self.assertRaises(Failure):
            self.action('publish', row)
        self.assertEqual(self.manager.public_manifest(), self.original)

    def test_retry_recovers_crashed_cancellation_and_never_reaps_published_history(self):
        published = self.action('publish', self.validated())
        staged = self.upload(self.action('draft'), b'private staged data')
        staged_path = self.store / (staged['id'] + '.apk')
        with patch('backend.android_releases.os.unlink', side_effect=SystemExit('simulated worker death')), self.assertRaises(SystemExit):
            self.action('cancel', staged)
        self.assertTrue(staged_path.exists())
        self.assertEqual(self.action('cancel', staged)['state'], 'cancelled')
        self.assertFalse(staged_path.exists())
        self.assertEqual(self.manager.public_manifest()['apk_sha256'], published['apk_sha256'])
        self.assertTrue((self.store / (published['id'] + '.apk')).is_file())

    def test_next_draft_recovers_crash_without_retrying_the_original_request(self):
        staged = self.upload(self.action('draft'), b'private staged data')
        with patch('backend.android_releases.os.unlink', side_effect=SystemExit), self.assertRaises(SystemExit):
            self.action('cancel', staged)
        self.action('draft')
        self.assertEqual(list(self.store.iterdir()), [])

    def test_alternating_downloads_hash_each_historical_object_once(self):
        from backend.android_releases import AndroidReleases
        rows = [self.action('publish', self.validated(name)) for name in ('first.apk', 'second.apk')]
        self.manager = AndroidReleases(self.backend, self.settings, self.legacy)
        digests = []
        read = os.pread
        def observed(fd, length, offset):
            if length > 4:
                digests.append(os.fstat(fd).st_ino)
            return read(fd, length, offset)
        with patch('backend.native_download.os.pread', side_effect=observed):
            for row in (*rows, *rows):
                path = '/download/android/sha256/' + row['apk_sha256'] + '/ULADIM.apk'
                self.assertEqual(self.download(path, 'HEAD')[0], 200)
        self.assertEqual(len(digests), 2)
        self.assertEqual(len(set(digests)), 2)

    def test_unrelated_download_does_not_wait_for_another_digest(self):
        from backend.android_releases import AndroidReleases
        first = self.action('publish', self.validated('first.apk'))
        second = self.action('publish', self.validated('second.apk'))
        self.manager = AndroidReleases(self.backend, self.settings, self.legacy)
        waiting, resume, served = threading.Event(), threading.Event(), threading.Event()
        inode = (self.store / (first['id'] + '.apk')).stat().st_ino
        read = os.pread
        def delayed(fd, length, offset):
            if length > 4 and os.fstat(fd).st_ino == inode:
                waiting.set()
                resume.wait(timeout=5)
            return read(fd, length, offset)
        def fetch(row, completed=None):
            path = '/download/android/sha256/' + row['apk_sha256'] + '/ULADIM.apk'
            status, _, _ = self.download(path, 'HEAD')
            if completed and status == 200:
                completed.set()
        with patch('backend.native_download.os.pread', side_effect=delayed):
            thread1, thread2 = threading.Thread(target=fetch, args=(first,)), threading.Thread(target=fetch, args=(second, served))
            thread1.start()
            try:
                self.assertTrue(waiting.wait(timeout=3))
                thread2.start()
                self.assertTrue(served.wait(timeout=2))
            finally:
                resume.set()
                thread1.join(5)
                if thread2.ident is not None:
                    thread2.join(5)

    def test_read_only_permission_never_grants_upload_or_publication(self):
        actor = StaffPrincipal('staff', 'user', ('release_manager',), ('android.upload','android.publish'))
        self.assertEqual(self.action('', actor=actor)['current'], self.original)
        for action in ('draft','publish'):
            with self.subTest(action=action), self.assertRaises(Failure) as denied:
                self.action(action, actor=actor)
            self.assertEqual(denied.exception.status, 403)


@unittest.skipUnless(os.getenv('LIFEOS_TEST_DATABASE_URL'), 'Requires isolated lifeos_test PostgreSQL database')
class AndroidReleasePostgresTests(AndroidReleaseTests):
    def database(self):
        import psycopg
        from psycopg import sql
        from cryptography.fernet import Fernet
        from backend.postgres import PostgresBackend
        dsn = os.environ['LIFEOS_TEST_DATABASE_URL']
        if urlsplit(dsn).path != '/lifeos_test':
            raise RuntimeError('Requires isolated lifeos_test PostgreSQL database')
        schema = 'android_release_' + uuid.uuid4().hex
        with psycopg.connect(dsn, autocommit=True) as db:
            db.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        def drop():
            with psycopg.connect(dsn, autocommit=True) as db:
                db.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
        self.addCleanup(drop)
        backend = PostgresBackend(dsn, Fernet(Fernet.generate_key()), schema=schema, migrate=True)
        self.addCleanup(backend.close)
        return backend
