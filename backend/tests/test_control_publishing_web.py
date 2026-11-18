"""Publishing authority through the ordinary admitted Control WSGI entry."""
import io
import json
import unittest
from urllib.parse import urlencode, urlsplit
from unittest.mock import patch

from backend.control import ROLE_PERMISSIONS
from backend.tests import test_control_web as fixtures


class UnreadableBody:
    def read(self, *args):
        raise AssertionError('Unapproved APK request body was consumed')


class ControlPublishingWebTests(unittest.TestCase):
    setUp = fixtures.WebControlTests.setUp
    user = fixtures.WebControlTests.user
    setup_admission = fixtures.WebControlTests.setup_admission

    def request(self, path, body=None, host='getuladim.space', cookie='', csrf='',
                origin=None, form=False, *, stream=None, raw=None, content_type=None,
                headers=None, method=None):
        target = urlsplit(path)
        data = (urlencode(body).encode() if form else json.dumps(body).encode()) if body is not None else b''
        if raw is not None:
            data = raw
        if host == 'control.getuladim.space' and getattr(self, 'admission', ''):
            cookie = (cookie + '; ' + self.admission).strip('; ')
        env = {'HTTP_HOST': host, 'REQUEST_METHOD': method or ('POST' if body is not None or raw is not None or stream is not None else 'GET'),
               'PATH_INFO': target.path, 'QUERY_STRING': target.query,
               'REMOTE_ADDR': '172.30.30.2', 'HTTP_X_FORWARDED_PROTO': 'https',
               'HTTP_USER_AGENT': 'fixture', 'HTTP_COOKIE': cookie,
               'HTTP_X_CSRF_TOKEN': csrf,
               'CONTENT_TYPE': content_type or ('application/x-www-form-urlencoded' if form else 'application/json'),
               'CONTENT_LENGTH': str(len(data) if stream is None else 1024),
               'wsgi.input': stream if stream is not None else io.BytesIO(data)}
        if origin is not None:
            env['HTTP_ORIGIN'] = origin
        env.update(headers or {})
        result = []
        with patch.object(self.app, 'limit'):
            chunks = self.app(env, lambda s, h: result.append((int(s.split()[0]), dict(h))))
            raw_result = b''.join(chunks)
        status, response_headers = result[0]
        value = json.loads(raw_result) if raw_result and response_headers['Content-Type'].startswith('application/json') else raw_result
        return status, response_headers, value

    @property
    def owner_cookie(self):
        return '__Host-uladim_control=' + self.staff_login['token']

    def binary(self, **kwargs):
        return self.request('/control/api/android-releases/upload',
                            host='control.getuladim.space', stream=UnreadableBody(),
                            content_type='application/vnd.android.package-archive',
                            origin='https://control.getuladim.space', **kwargs)

    def test_scoped_roles_do_not_grant_existing_staff_publication_rights(self):
        expected = {'pages.edit', 'pages.publish', 'android.read', 'android.upload', 'android.publish'}
        self.assertTrue(expected <= ROLE_PERMISSIONS['owner'])
        for role in ('admin', 'support', 'moderator', 'billing_manager', 'auditor'):
            self.assertFalse(expected & ROLE_PERMISSIONS[role])
        self.assertEqual(ROLE_PERMISSIONS['content_editor'], {'pages.edit'})
        self.assertEqual(ROLE_PERMISSIONS['content_publisher'], {'pages.edit', 'pages.publish'})
        self.assertEqual(ROLE_PERMISSIONS['release_manager'], {'android.read', 'android.upload', 'android.publish'})

    def test_upload_requires_staff_session_before_body_read(self):
        self.assertEqual(self.binary()[0], 401)

    def test_upload_requires_csrf_before_body_read(self):
        self.assertEqual(self.binary(cookie=self.owner_cookie)[0], 403)

    def test_upload_effective_permission_denial_precedes_body_read(self):
        with self.backend.transaction() as db:
            db.execute('INSERT INTO staff_permission_restrictions VALUES(?,?)', (self.owner.id, 'android.upload'))
        self.assertEqual(self.binary(cookie=self.owner_cookie, csrf=self.app.web.csrf(self.staff_login['token']))[0], 403)

    def test_public_document_endpoint_is_explicitly_scoped(self):
        status, _, value = self.request('/public-pages/document?page=%2Ffaq&lang=ru')
        self.assertEqual(status, 200)
        self.assertEqual((value['page'], value['locale'], value['revision']), ('/faq', 'ru', 0))
        self.assertEqual(value['content'], self.app.web.pages().handle(
            self.owner, 'pages/page', 'GET', {}, {'page': ['/faq'], 'lang': ['ru']})['baseline']['content'])
        self.assertEqual(self.request('/public-pages/document?page=%2Ffaq&lang=xx')[0], 400)
        self.assertEqual(self.request('/public-pages/document?page=%2Ffaq&lang=ru&lang=en')[0], 400)

    def test_pages_catalog_requires_control_capability(self):
        status, _, value = self.request('/control/api/pages', host='control.getuladim.space', cookie=self.owner_cookie)
        self.assertEqual(status, 200)
        self.assertIn('pages', value)
        with self.backend.transaction() as db:
            db.execute('INSERT INTO staff_permission_restrictions VALUES(?,?)', (self.owner.id, 'pages.edit'))
        self.assertEqual(self.request('/control/api/pages', host='control.getuladim.space', cookie=self.owner_cookie)[0], 403)


if __name__ == '__main__':
    unittest.main()
