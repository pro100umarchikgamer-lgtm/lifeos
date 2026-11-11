"""Browser OAuth integration with a synthetic RSA provider, never real Google.

This proves UI/callback/cookie/MFA wiring, not Cloud Console or device acceptance.
"""
import json
import tempfile
import threading
from dataclasses import replace
from pathlib import Path
from urllib.parse import parse_qs, urlsplit, urlencode
from wsgiref.simple_server import make_server

from cryptography.fernet import Fernet
from playwright.sync_api import sync_playwright, expect
from backend.config import Settings
from backend.production import Application
from backend.service import Backend, token_hash
from backend.customer_mfa import CustomerMFA
from backend.control import totp
from backend.tests.test_google_identity import SyntheticGoogle, CLIENT
from tool.check_pwa_browser import Quiet


def main():
    out=Path('web_evidence/google');out.mkdir(parents=True,exist_ok=True)
    password='synthetic-google-browser-password'; cases=[]
    with tempfile.TemporaryDirectory() as folder:
        mail={}
        backend=Backend(Path(folder)/'google-browser.db',deliver=lambda e,c:mail.update({e:c}))
        backend.cipher=Fernet(Fernet.generate_key())
        with backend.connect() as db:db.execute('CREATE TABLE http_limits(key TEXT PRIMARY KEY,count BIGINT NOT NULL,until_at BIGINT NOT NULL)')
        settings=Settings.load({'DATABASE_URL':'postgresql://unused/test','EMAIL_QUEUE_KEY':Fernet.generate_key().decode(),
            'RATE_LIMIT_KEY':'synthetic-test-only-'+'x'*40,'SMTP_HOST':'localhost','SMTP_TLS':'none',
            'EMAIL_FROM':'fixture@example.test','GOOGLE_OAUTH_CLIENT_ID':CLIENT,
            'GOOGLE_OAUTH_CLIENT_SECRET':'synthetic-test-only','REGISTRATION_MODE':'open'})
        server=make_server('127.0.0.1',0,lambda e,s:[],handler_class=Quiet)
        origin='http://localhost:'+str(server.server_port)
        app=Application(backend,replace(settings,site_origin=origin,control_origin='http://control.localhost:'+str(server.server_port),require_https=False))
        provider=SyntheticGoogle();app.google.verifier=provider
        session=backend.register('linked@example.test',password)
        actor=backend.authenticate(session['token']);backend.verify(actor,mail[actor['email']]);actor=backend.authenticate(session['token'])
        grant=app.google.start('android','fixture',actor=actor,password=password,auth_hash=token_hash(session['token']))
        app.google.finish(grant['challenge'],'android','fixture',id_token=provider.sign(grant['nonce'],sub='mfa-subject',email=actor['email']))
        mfa=CustomerMFA(backend);enrollment=mfa.begin(actor,password)
        backup=mfa.enable(actor,password,enrollment['enrollment'],totp(enrollment['totp_secret'],int(backend.clock())//30))
        server.set_app(app);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch()
                for index,(route,width,factor) in enumerate([('/app',390,False),('/account',1440,False),('/app',834,True)]):
                    context=browser.new_context(viewport={'width':width,'height':1000});page=context.new_page();errors=[]
                    page.on('pageerror',lambda e:errors.append(str(e)))
                    def authorize(request_route):
                        params=parse_qs(urlsplit(request_route.request.url).query)
                        assert params['code_challenge_method']==['S256']
                        token=provider.sign(params['nonce'][0],sub='mfa-subject' if factor else 'new-browser-subject',
                            email=actor['email'] if factor else 'synthetic@gmail.com')
                        destination=origin+'/account/api/google/callback?'+urlencode({'state':params['state'][0],'code':token})
                        request_route.fulfill(status=302,headers={'Location':destination},body='')
                    context.route('https://accounts.google.com/o/oauth2/v2/auth?*',authorize)
                    page.goto(origin+route)
                    expect(page.get_by_role('button',name='Продолжить с Google',exact=True)).to_be_visible()
                    page.get_by_role('button',name='Продолжить с Google',exact=True).click()
                    if factor:
                        expect(page.get_by_role('heading',name='Двухфакторная защита',exact=True)).to_be_visible()
                        expect(page.locator('input[type=password]')).to_have_count(0)
                        expect(page.locator('input[name=email]')).to_have_count(0)
                        page.screenshot(path=str(out/'google-mfa-834.png'),full_page=True)
                        page.locator('input[name=code]').fill(backup['recovery_codes'][0])
                        page.get_by_role('button',name='Войти',exact=True).click()
                    expect(page.locator('.nav')).to_be_visible()
                    assert urlsplit(page.url).query==''
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                    assert not page.evaluate("JSON.stringify(localStorage).includes('eyJ')")
                    if width==834:
                        for label in page.locator('.nav button>span:last-child').all():
                            assert label.evaluate('(e)=>e.getBoundingClientRect().height<=parseFloat(getComputedStyle(e).fontSize)*2'), 'Navigation label wraps character by character'
                    page.screenshot(path=str(out/f'google-authenticated-{width}.png'),full_page=True)
                    assert not errors,errors
                    cases.append({'case':route+' Google '+('with ULADIM MFA' if factor else 'without MFA'),
                                  'expected':'same account, no tokens in URL/storage; factor enforced','actual':'passed'})
                    context.close()
                browser.close()
        finally:
            server.shutdown();server.server_close();thread.join(5)
    (out/'RESULT.json').write_text(json.dumps({'scope':'synthetic RSA Google provider + real WSGI + Chromium; NOT real Google or physical Android', 'cases':cases},ensure_ascii=False,indent=2))
    print('Google browser integration:',len(cases),'passed (synthetic provider)')


if __name__=='__main__':main()
