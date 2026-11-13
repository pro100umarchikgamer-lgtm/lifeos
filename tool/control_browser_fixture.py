"""Test-only real Control front door for synthetic rendering checks.

Disposable fixture data, loopback TLS and ordinary login/handoff requests only.
The Control document and assets always come from the real WSGI application.
"""
from contextlib import contextmanager
from dataclasses import replace
import os
import tempfile
import threading
from wsgiref.simple_server import make_server

from cryptography.fernet import Fernet
from playwright.sync_api import expect

from backend.config import Settings
from backend.control import Control
from backend.production import Application
from tool.check_pwa_browser import Quiet
from tool.check_web_platform import fixture, login
from tool.web_test_tls import enable_test_tls


@contextmanager
def control_fixture():
    # Reuse the existing disposable product data without changing its HTTP fixture.
    with fixture() as (customer_origin, backend, actor, wid), tempfile.TemporaryDirectory() as directory:
        Control(backend).bootstrap(actor['email'])
        settings = Settings.load({
            'DATABASE_URL': 'postgresql://unused/test',
            'EMAIL_QUEUE_KEY': Fernet.generate_key().decode(),
            'RATE_LIMIT_KEY': 'synthetic-control-browser-' + 'x' * 48,
            'SMTP_HOST': '127.0.0.1', 'SMTP_TLS': 'none',
            'EMAIL_FROM': 'fixture@example.test',
        })
        server = make_server('127.0.0.1', 0, lambda env, start: [], handler_class=Quiet)
        pin = enable_test_tls(server, directory, ('app.uladim.test', 'control.uladim.test'))
        origin = 'https://app.uladim.test:' + str(server.server_port)
        control = 'https://control.uladim.test:' + str(server.server_port)
        server.set_app(Application(backend, replace(settings, site_origin=origin,
                                                    control_origin=control, require_https=False)))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        launch = {
            'args': ['--host-resolver-rules=MAP *.uladim.test 127.0.0.1',
                     '--ignore-certificate-errors-spki-list=' + pin],
        }
        if os.environ.get('ULADIM_CHROMIUM'):
            launch['executable_path'] = os.environ['ULADIM_CHROMIUM']
        if os.environ.get('HTTPS_PROXY'):
            # Keep Chromium's subtractive token before the explicit local rules;
            # Playwright otherwise appends it last and proxies the HTTP fixture.
            launch['proxy'] = {'server': os.environ['HTTPS_PROXY'],
                               'bypass': '<-loopback>,.uladim.test,localhost,127.0.0.1'}
        try:
            yield customer_origin, origin, control, backend, actor, wid, launch
        finally:
            server.shutdown()
            server.server_close()
            thread.join(5)


def admit_control(page, origin, control):
    """Obtain browser admission before callers install any Control API mocks."""
    for path in ('/', '/assets/web.js', '/assets/web.css', '/assets/design.css',
                 '/control/api/session'):
        assert page.goto(control + path).status == 404, path
    login(page, origin)
    # A signed-in owner still cannot skip the one-use browser handoff.
    assert page.goto(control + '/').status == 404
    page.goto(origin + '/app')
    page.locator('header').get_by_role('button', name='Профиль', exact=True).click()
    with page.expect_response(origin + '/account/api/control/access') as ticket_response:
        with page.expect_response(control + '/admit') as admission_response:
            page.get_by_role('button', name='ULADIM Control', exact=True).click()
    assert ticket_response.value.status == 200
    admission = admission_response.value
    assert admission.status == 303 and admission.request.method == 'POST'
    cookie = admission.header_value('set-cookie')
    assert '__Host-uladim_control_admission=' in cookie
    assert 'HttpOnly' in cookie and 'Secure' in cookie and 'SameSite=Strict' in cookie
    assert 'Domain=' not in cookie
    expect(page.get_by_role('heading', name='ULADIM Control', exact=True)).to_be_visible()
    # Admission grants visibility only; actual staff authentication still needs MFA.
    assert page.goto(control + '/control/api/session').status == 401
    for path in ('/assets/web.js', '/assets/web.css', '/assets/design.css'):
        assert page.goto(control + path).status == 200, path
    assert page.goto(control + '/').status == 200
    expect(page.get_by_role('heading', name='ULADIM Control', exact=True)).to_be_visible()
