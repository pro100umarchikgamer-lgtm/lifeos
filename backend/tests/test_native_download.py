"""Local accepted-file downloads; no network, real APK or production paths."""
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from backend.native_download import NativeDownload, CERTIFICATE, CHUNK
from backend.production import Application
from backend.config import Settings
from cryptography.fernet import Fernet


class NativeDownloadTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(); self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        self.folder.chmod(0o750)
        self.apk = b'PK\x03\x04' + bytes(range(256)) * 500
        self.source = 'a' * 40
        self.path = '/download/android/' + self.source + '/ULADIM.apk'
        self.metadata = {'source': self.source, 'version_code': 400001, 'version_name': '0.4.0-test',
                         'bytes': len(self.apk), 'apk_sha256': hashlib.sha256(self.apk).hexdigest(),
                         'certificate_sha256': CERTIFICATE,
                         'apk_url': 'https://github.com/pro100umarchikgamer-lgtm/lifeos/releases/download/uladim-native-' + self.source[:12] + '/ULADIM.apk'}
        self.write(self.folder / 'ULADIM.apk', self.apk)
        self.write(self.folder / 'release.json', json.dumps(self.metadata).encode())
        self.download = NativeDownload(str(self.folder), trusted_uid=os.getuid())

    def write(self, path, body):
        path.write_bytes(body); path.chmod(0o640)

    def response(self, *, method='GET', path=None, query='', **headers):
        env = {'REQUEST_METHOD': method, 'PATH_INFO': path or self.path, 'QUERY_STRING': query, **headers}
        status, values, body = self.download.response(env)
        try: raw = b''.join(body)
        finally:
            if hasattr(body, 'close'): body.close()
        return status, dict(values), raw

    def test_streaming_get_and_head_are_bound_to_the_accepted_tuple(self):
        status, headers, body = self.response()
        self.assertEqual((status, body), (200, self.apk))
        self.assertEqual(headers['Content-Type'], 'application/vnd.android.package-archive')
        self.assertEqual(headers['Content-Disposition'], 'attachment; filename="ULADIM-400001.apk"')
        self.assertEqual(headers['Content-Length'], str(len(self.apk)))
        self.assertEqual(headers['ETag'], '"sha256-' + self.metadata['apk_sha256'] + '"')
        self.assertEqual(headers['X-ULADIM-Source'], self.source)
        self.assertEqual(headers['X-ULADIM-APK-SHA256'], self.metadata['apk_sha256'])
        self.assertEqual(headers['X-ULADIM-Certificate-SHA256'], CERTIFICATE)
        self.assertEqual(headers['Cache-Control'], 'no-store')
        status, head, body = self.response(method='HEAD', HTTP_RANGE='bytes=0-3')
        self.assertEqual((status, body, head['Content-Length']), (200, b'', str(len(self.apk))))
        self.assertNotIn('Content-Range', head)

    def test_single_ranges_and_if_range(self):
        for spec, start, stop in [('bytes=0-3', 0, 4), ('bytes=20-', 20, len(self.apk)),
                                  ('bytes=-7', len(self.apk)-7, len(self.apk)),
                                  ('bytes=0-999999999', 0, len(self.apk))]:
            with self.subTest(range=spec):
                status, headers, body = self.response(HTTP_RANGE=spec)
                self.assertEqual((status, body), (206, self.apk[start:stop]))
                self.assertEqual(headers['Content-Range'], f'bytes {start}-{stop-1}/{len(self.apk)}')
                self.assertEqual(headers['Content-Length'], str(stop-start))
        self.assertEqual(self.response(HTTP_RANGE='bytes=0-3', HTTP_IF_RANGE='"wrong"')[0:3:2], (200, self.apk))
        for spec in ('bytes=999999999-', 'bytes=8-2', 'bytes=-0', 'bytes=0-1,4-5', 'other=0-1', 'bytes=' + '1'*100 + '-'):
            with self.subTest(range=spec):
                status, headers, body = self.response(HTTP_RANGE=spec)
                self.assertEqual((status, body), (416, b''))
                self.assertEqual(headers['Content-Range'], f'bytes */{len(self.apk)}')

    def test_no_query_arbitrary_path_wrong_source_or_redirect(self):
        for path, query in [(self.path, 'path=/etc/passwd'), (self.path, 'url=https://evil.invalid/file'),
                            (self.path.replace(self.source, 'b'*40), ''), ('/download/android/../ULADIM.apk', ''),
                            (self.path + '/extra', ''), (self.path.replace('ULADIM.apk', 'release.json'), '')]:
            with self.subTest(path=path, query=query):
                self.assertEqual(self.response(path=path, query=query)[0], 404)
        self.assertEqual(self.response(method='POST')[0], 405)

    def test_size_hash_metadata_and_file_permissions_fail_closed(self):
        for key, value in [('apk_sha256', '0'*64), ('bytes', len(self.apk)+1), ('certificate_sha256', '0'*64),
                           ('apk_url', 'https://evil.invalid/a.apk'), ('version_code', True), ('version_name', 'bad\r\nHeader: x')]:
            with self.subTest(field=key):
                self.write(self.folder/'release.json', json.dumps(dict(self.metadata, **{key: value})).encode())
                self.assertEqual(self.response()[0], 404)
        self.write(self.folder/'release.json', json.dumps(self.metadata).encode())
        self.assertEqual(self.response()[0], 200)
        self.write(self.folder/'ULADIM.apk', b'x' * len(self.apk))
        self.assertEqual(self.response()[0], 404)  # A cached acceptance cannot survive changed bytes.
        self.write(self.folder/'ULADIM.apk', self.apk)
        (self.folder/'ULADIM.apk').chmod(0o666)
        self.assertEqual(self.response()[0], 404)

    def test_symlinks_hardlinks_duplicate_json_and_missing_cache_are_hidden(self):
        (self.folder/'ULADIM.apk').unlink()
        (self.folder/'ULADIM.apk').symlink_to(self.folder/'release.json')
        self.assertEqual(self.response()[0], 404)
        (self.folder/'ULADIM.apk').unlink()
        self.write(self.folder/'other.apk', self.apk)
        os.link(self.folder/'other.apk', self.folder/'ULADIM.apk')
        self.assertEqual(self.response()[0], 404)
        (self.folder/'ULADIM.apk').unlink(); (self.folder/'other.apk').unlink()
        self.write(self.folder/'ULADIM.apk', self.apk)
        raw = json.dumps(self.metadata)
        self.write(self.folder/'release.json', (raw[:-1] + ',"bytes":1}').encode())
        self.assertEqual(self.response()[0], 404)
        (self.folder/'release.json').unlink()
        self.assertEqual(self.response()[0], 404)
        self.assertEqual(NativeDownload('').response({'REQUEST_METHOD':'GET','PATH_INFO':self.path})[0], 404)

    def test_stream_is_bounded_closes_on_abort_and_refuses_in_place_changes(self):
        env = {'REQUEST_METHOD':'GET','PATH_INFO':self.path}
        status, headers, body = self.download.response(env)
        self.assertEqual(status, 200)
        iterator = iter(body)
        self.assertEqual(next(iterator), self.apk[:CHUNK])
        fd = body.fd
        body.close(); iterator.close()
        with self.assertRaises(OSError): os.fstat(fd)
        status, headers, body = self.download.response(env)
        self.write(self.folder/'ULADIM.apk', self.apk[:-1] + b'x')
        with self.assertRaises(OSError): next(iter(body))
        self.assertIsNone(body.fd)

    def test_cache_directory_and_manifest_authority_are_required(self):
        self.folder.chmod(0o777)
        self.assertEqual(self.response()[0], 404)
        self.folder.chmod(0o750)
        self.assertEqual(NativeDownload(str(self.folder), trusted_uid=os.getuid()+1).response({'REQUEST_METHOD':'HEAD','PATH_INFO':self.path})[0], 404)
        alias = self.folder/'alias'; alias.symlink_to(self.folder, target_is_directory=True)
        self.assertEqual(NativeDownload(str(alias), trusted_uid=os.getuid()).response({'REQUEST_METHOD':'HEAD','PATH_INFO':self.path})[0], 404)
        (self.folder/'release.json').chmod(0o666)
        self.assertEqual(self.response()[0], 404)

    def test_configuration_rejects_non_normalized_or_unbounded_cache_paths(self):
        env = {'DATABASE_URL':'postgresql://unused/test','EMAIL_QUEUE_KEY':Fernet.generate_key().decode(),
               'RATE_LIMIT_KEY':'r'*48,'SMTP_HOST':'127.0.0.1','SMTP_TLS':'none','EMAIL_FROM':'fixture@example.test'}
        self.assertEqual(Settings.load(env).native_download_dir, '')
        self.assertEqual(Settings.load(dict(env, NATIVE_DOWNLOAD_DIR='/run/uladim/native-download')).native_download_dir, '/run/uladim/native-download')
        for invalid in ('/', 'relative', '/a/../b', '/a//b', '//a/b', '/a/./b', '/a\nb', 'https://example.test/apk', '/a/' + 'b'*512):
            with self.subTest(path=invalid):
                with self.assertRaises(ValueError): Settings.load(dict(env, NATIVE_DOWNLOAD_DIR=invalid))

    def test_application_streams_only_on_site_origin_after_https_guard(self):
        env = {'DATABASE_URL':'postgresql://unused/test','EMAIL_QUEUE_KEY':Fernet.generate_key().decode(),
               'RATE_LIMIT_KEY':'r'*48,'SMTP_HOST':'127.0.0.1','SMTP_TLS':'none','EMAIL_FROM':'fixture@example.test'}
        app = Application(None, Settings.load(env))
        app.native_download = self.download
        def request(host, https='https', query='', method='GET', **extra):
            captured = []
            request = {'HTTP_HOST':host,'PATH_INFO':self.path,'QUERY_STRING':query,'REQUEST_METHOD':method,
                       'REMOTE_ADDR':'172.30.30.2','HTTP_X_FORWARDED_PROTO':https,'wsgi.input':io.BytesIO(), **extra}
            with patch.object(app,'limit'):
                body = app(request, lambda status, headers: captured.append((status, dict(headers))))
                try: raw = b''.join(body)
                finally:
                    if hasattr(body,'close'):body.close()
            return captured[0], raw
        (status, headers), raw = request('getuladim.space')
        self.assertEqual((status, raw), ('200 OK', self.apk))
        self.assertNotIn('Set-Cookie', headers)
        (status, headers), raw = request('getuladim.space', method='HEAD')
        self.assertEqual((status, raw, headers['Content-Length']), ('200 OK', b'', str(len(self.apk))))
        (status, headers), raw = request('getuladim.space', HTTP_RANGE='bytes=2-5')
        self.assertEqual((status, raw, headers['Content-Range']), ('206 Partial Content', self.apk[2:6], f'bytes 2-5/{len(self.apk)}'))
        self.assertEqual(request('getuladim.space', https='http')[0][0], '426 Upgrade Required')
        self.assertEqual(request('api.getuladim.space')[0][0], '404 Not Found')
        self.assertEqual(request('control.getuladim.space')[0][0], '404 Not Found')
        self.assertEqual(request('getuladim.space', query='file=release.json')[0][0], '404 Not Found')
