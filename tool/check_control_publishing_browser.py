"""Control publication journeys on isolated WSGI, SQLite and loopback TLS."""
import io
import hashlib
import json
import os
from pathlib import Path
from dataclasses import replace
import shutil

from PIL import Image
from playwright.sync_api import expect, sync_playwright

from backend.control import totp
from backend.android_releases import AndroidReleases
from backend.apk_verifier import ApkVerifier
from backend.native_download import CERTIFICATE, NativeDownload
from backend.tests.test_apk_verifier import FIXTURES
from tool.check_web_platform import PASSWORD
from tool.control_browser_fixture import admit_control, choose_control_field, choose_control_section, control_fixture

OUT = Path(os.environ.get('ULADIM_PUBLISHING_EVIDENCE', '/tmp/uladim-control-publishing'))
TITLE = 'Synthetic status update'
EDITORIAL = '<script>window.testInjection=true</script> Add status details here.'


def android_tools():
    return [os.environ.get('ULADIM_TEST_' + name.upper()) or shutil.which(name) for name in ('apksigner', 'aapt')]


def configure_android(application, root):
    apksigner, aapt = android_tools()
    if not apksigner or not aapt:
        return
    store = root / 'managed'
    store.mkdir(mode=0o700)
    previous = root / 'legacy'
    previous.mkdir()
    source = 'd' * 40
    data = b'PK\x03\x04' + b'synthetic prior release'
    manifest = {'source': source, 'version_code': 400001, 'version_name': '1.2.2',
                'bytes': len(data), 'apk_sha256': hashlib.sha256(data).hexdigest(), 'certificate_sha256': CERTIFICATE,
                'apk_url': f'https://github.com/pro100umarchikgamer-lgtm/lifeos/releases/download/uladim-native-{source[:12]}/ULADIM.apk'}
    (previous / 'release.json').write_text(json.dumps(manifest))
    (previous / 'ULADIM.apk').write_bytes(data)
    legacy = NativeDownload(str(previous), trusted_uid=os.getuid())
    service = AndroidReleases(application.backend, replace(application.settings, native_publish_dir=str(store)), legacy)
    service.verifier = ApkVerifier(apksigner=apksigner, aapt=aapt,
                                   certificate=(FIXTURES / 'certificate.sha256').read_text().strip())
    application.web._android = service


def check_android(staff, guest, site):
    choose_control_section(staff, 'android-releases')
    expect(staff.get_by_role('heading', name='Релизы Android')).to_be_visible()

    def upload(filename):
        staff.get_by_role('button', name='Новый кандидат').click()
        staff.get_by_label('Файл APK', exact=True).set_input_files(FIXTURES / filename)
        with staff.expect_response('**/control/api/android-releases/upload') as response:
            staff.get_by_role('button', name='Загрузить APK', exact=True).click()
        result = response.value
        assert result.ok and result.request.headers['content-type'] == 'application/vnd.android.package-archive'
        digest = hashlib.sha256((FIXTURES / filename).read_bytes()).hexdigest()
        expect(staff.locator('.publishing-releases code').filter(has_text=digest)).to_be_visible()
        staff.get_by_role('button', name='Проверить APK', exact=True).click()

    upload('wrong-package.apk')
    expect(staff.get_by_text('Неверный пакет Android.', exact=True)).to_be_visible()
    staff.get_by_text('Отменить кандидата', exact=True).click()
    staff.get_by_role('button', name='Подтвердить', exact=True).click()
    expect(staff.get_by_role('heading', name='Отменено')).to_be_visible()
    upload('first.apk')
    expect(staff.get_by_role('heading', name='Подпись проверена')).to_be_visible()
    read_manifest = "fetch('/download/release.json', {credentials:'omit'}).then(response => response.json())"
    assert guest.evaluate(read_manifest)['version_code'] == 400001
    staff.get_by_text('Проверить публикацию', exact=True).click()
    staff.get_by_role('button', name='Опубликовать APK', exact=True).click()
    expect(staff.get_by_role('heading', name='Опубликовано')).to_be_visible()
    manifest = guest.evaluate(read_manifest)
    assert manifest['origin'] == 'control' and manifest['version_code'] == 400002
    assert manifest['apk_sha256'] == hashlib.sha256((FIXTURES / 'first.apk').read_bytes()).hexdigest()
    assert staff.evaluate('document.documentElement.scrollWidth <= innerWidth')
    staff.screenshot(path=str(OUT / 'android-releases.png'), full_page=True)


def mfa(page, backend, actor):
    with backend.connect() as db:
        encrypted = db.execute('SELECT mfa_secret FROM staff WHERE user_id=?', (actor['id'],)).fetchone()['mfa_secret']
    secret = backend.cipher.decrypt(bytes(encrypted)).decode()
    page.get_by_label('Электронная почта', exact=True).fill(actor['email'])
    page.locator('input[name=password]').fill(PASSWORD)
    page.get_by_role('button', name='Войти', exact=True).click()
    page.get_by_label('Код подтверждения', exact=True).fill(totp(secret, int(backend.clock()) // 30))
    page.get_by_role('button', name='Войти', exact=True).click()
    expect(page.get_by_role('heading', name='Обзор сервиса')).to_be_visible()


def check_reconcile_and_urls(staff):
    choose_control_field(staff, 'Страница сайта', '/plans')
    editor = staff.locator('.publishing-editor')
    fields = editor.locator('details').first
    fields.get_by_label('Заголовок', exact=True).fill('My edited title')
    fields.get_by_label('Адрес ссылки').fill('https://docs.example.test/validated-link')
    assert staff.evaluate('''async () => {
      const get = path => fetch('/control/api/' + path).then(response => response.json());
      const [session, state] = await Promise.all([get('session'), get('pages/page?page=%2Fplans&lang=en')]);
      const content = structuredClone(state.baseline.content);
      content.fields.title = 'Separately saved title';
      content.fields.lead = 'Separately saved introduction';
      return (await fetch('/control/api/pages/save', {method:'POST', headers:{'Content-Type':'application/json','X-CSRF-Token':session.csrf},
        body:JSON.stringify({page:'/plans',locale:'en',expected_version:state.version,content})})).ok;
    }''')
    editor.get_by_role('button', name='Сохранить черновик', exact=True).click()
    staff.get_by_role('button', name='Сравнить с новой версией', exact=True).click(timeout=5000)
    review = staff.locator('.publishing-reconciliation')
    expect(review).to_contain_text('Separately saved title')
    expect(review).to_contain_text('Separately saved introduction')
    expect(review).to_contain_text('My edited title')
    staff.get_by_role('button', name='Продолжить с выбранными правками', exact=True).click()
    expect(fields.get_by_label('Заголовок', exact=True)).to_have_value('My edited title')
    expect(fields.get_by_label('Введение', exact=True)).to_have_value('Separately saved introduction')
    editor.get_by_role('button', name='Сохранить черновик', exact=True).click()
    expect(staff.get_by_role('status').filter(has_text='Черновик сохранён')).to_be_visible()
    editor.get_by_role('button', name='Предпросмотр черновика').click()
    content = staff.locator('.publishing-preview-content')
    expect(content.get_by_text('https://docs.example.test/validated-link', exact=True)).to_be_visible()
    expect(content.locator('a[href]')).to_have_count(0)
    choose_control_field(staff, 'Страница сайта', '/docs')
    editor.get_by_role('button', name='Сохранить черновик', exact=True).click()
    expect(staff.get_by_role('status').filter(has_text='Черновик сохранён')).to_be_visible()
    editor.get_by_role('button', name='Предпросмотр черновика').click()
    expect(content.get_by_text('#first-record', exact=True)).to_be_visible()
    expect(content.locator('a[href]')).to_have_count(0)


def check_pending_save(staff):
    choose_control_field(staff, 'Страница сайта', '/status')
    editor = staff.locator('.publishing-editor')
    editor.locator('details').first.get_by_label('Заголовок', exact=True).fill('Pending save survives scope changes')
    held = []
    pattern = '**/control/api/pages/save'
    staff.route(pattern, lambda route: held.append(route))
    editor.get_by_role('button', name='Сохранить черновик', exact=True).click()
    choose_control_field(staff, 'Страница сайта', '/docs')
    expect(staff.locator('.publishing-editor')).to_be_visible()
    choose_control_field(staff, 'Страница сайта', '/status')
    assert held
    expect(staff.locator('.publishing-editor')).to_have_count(0)
    held.pop().continue_()
    staff.unroute(pattern)
    expect(editor.locator('details').first.get_by_label('Заголовок', exact=True)).to_have_value('Pending save survives scope changes')


def check_discarded_upload(staff):
    editor = staff.locator('.publishing-editor')
    guidance = editor.locator('details').filter(has_text='Рекомендации').first
    guidance.locator('summary').click()
    choose_control_field(staff, 'Тип блока', 'image')
    guidance.get_by_role('button', name='Добавить блок', exact=True).click()
    image = guidance.locator('fieldset').last
    image.get_by_label('Описание изображения', exact=True).fill('Image from discarded draft')
    png = io.BytesIO()
    Image.new('RGB', (16, 16), '#6e2431').save(png, format='PNG')
    image.locator('input[type=file]').set_input_files({'name': 'discard.png', 'mimeType': 'image/png', 'buffer': png.getvalue()})
    held = []
    pattern = '**/control/api/pages/media'
    staff.route(pattern, lambda route: held.append(route))
    image.get_by_role('button', name='Загрузить изображение', exact=True).click()
    editor.get_by_role('button', name='Отменить несохранённые изменения', exact=True).click()
    expect(editor.get_by_label('Описание изображения', exact=True)).to_have_count(0)
    with staff.expect_response(pattern) as upload:
        held.pop().continue_()
    assert upload.value.ok
    staff.unroute(pattern)
    choose_control_field(staff, 'Страница сайта', '/docs')
    choose_control_field(staff, 'Страница сайта', '/status')
    expect(editor.locator('details').first.get_by_label('Заголовок', exact=True)).to_have_value('Pending save survives scope changes')
    expect(editor.get_by_label('Описание изображения', exact=True)).to_have_count(0)


def check_frozen_source(browser, site):
    page = browser.new_context(viewport={'width': 390, 'height': 844}, service_workers='block').new_page()
    catalog = json.loads(Path('backend/webassets/app/translations.json').read_text())
    catalog['translations']['en']['literal_fb3af7870fa3'] = 'Changed live translation'
    page.route('**/app/assets/translations.json', lambda route: route.fulfill(json=catalog))
    held = []
    page.route('**/public-pages/document?*', lambda route: held.append(route))
    page.goto(site + '/status?lang=en', wait_until='domcontentloaded')
    expect(page.get_by_role('heading', name='Changed live translation')).to_be_visible()
    assert held
    held.pop().continue_()
    expect(page.get_by_role('heading', name='Service status')).to_be_visible()
    page.context.close()


def check_control_language(staff):
    choose_control_section(staff, 'public-pages')
    staff.locator('header .global-language select').select_option('de')
    expect(staff.get_by_role('heading', name='Öffentliche Seiten', exact=True)).to_be_visible()
    choose_control_field(staff, 'Seite der Website', '/docs')
    expect(staff.get_by_role('button', name='Seite der Website', exact=True)).to_have_text('Funktionen · /docs')
    expect(staff.locator('.publishing-editor').get_by_label('Einleitung', exact=True)).to_be_visible()
    staff.locator('.publishing-editor > details').nth(1).locator('summary').click()
    expect(staff.get_by_role('button', name='Blocktyp', exact=True)).to_be_visible()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    if os.environ.get('ULADIM_REQUIRE_APK_TOOLS') == '1' and not all(android_tools()):
        raise RuntimeError('Required Android verification tools are unavailable')
    checks, errors = [], []
    with control_fixture(configure=configure_android) as (_, site, control, backend, actor, _, launch), sync_playwright() as playwright:
        # Keep each independent scenario under its own fixture rate window.
        now = [int(backend.clock())]
        backend.clock = lambda: now[0]
        browser = playwright.chromium.launch(**launch)
        staff = browser.new_context(viewport={'width': 1100, 'height': 900}, service_workers='block').new_page()
        guest = browser.new_context(viewport={'width': 390, 'height': 844}, service_workers='block').new_page()
        for page in (staff, guest):
            page.on('pageerror', lambda err: errors.append(str(err)))
        admit_control(staff, site, control)
        mfa(staff, backend, actor)
        check_frozen_source(browser, site)
        checks.append('real public revision zero restores the frozen copy after live UI translations change')
        choose_control_section(staff, 'public-pages')
        choose_control_field(staff, 'Страница сайта', '/status')
        choose_control_field(staff, 'Язык страницы', 'en')
        editor = staff.locator('.publishing-editor')
        editor.get_by_label('Заголовок', exact=True).first.fill(TITLE)
        guidance = editor.locator('details').filter(has_text='Рекомендации').first
        guidance.locator('summary').click()
        guidance.get_by_role('button', name='Добавить блок', exact=True).click()
        new_text = guidance.locator('fieldset').last
        new_text.get_by_label('Заголовок', exact=True).fill('Operations')
        new_text.get_by_label('Текст', exact=True).fill(EDITORIAL)
        new_text.get_by_role('button', name='Выше', exact=True).click()
        expect(guidance.locator('fieldset').first.get_by_label('Текст', exact=True)).to_have_value(EDITORIAL)
        choose_control_field(staff, 'Тип блока', 'image')
        guidance.get_by_role('button', name='Добавить блок', exact=True).click()
        image = guidance.locator('fieldset').last
        image.get_by_label('Описание изображения', exact=True).fill('Status illustration')
        png = io.BytesIO()
        Image.new('RGB', (16, 16), '#215341').save(png, format='PNG')
        image.locator('input[type=file]').set_input_files({'name': 'status.png', 'mimeType': 'image/png', 'buffer': png.getvalue()})
        image.get_by_role('button', name='Загрузить изображение', exact=True).click()
        expect(image.get_by_alt_text('Status illustration')).to_be_visible()
        private_path = image.get_by_alt_text('Status illustration').get_attribute('src')
        public_path = private_path.replace('/control/api/pages/media/', '/public-pages/media/')
        assert guest.goto(site + public_path).status == 404
        editor.get_by_role('button', name='Сохранить черновик', exact=True).click()
        expect(staff.get_by_role('status').filter(has_text='Черновик сохранён')).to_be_visible()
        guest.goto(site + '/status?lang=en')
        expect(guest.get_by_role('heading', name=TITLE)).to_have_count(0)
        editor.get_by_role('button', name='Предпросмотр черновика').click()
        expect(staff.locator('.publishing-preview-content')).to_contain_text(EDITORIAL)
        expect(staff.locator('.publishing-preview-content script')).to_have_count(0)
        staff.get_by_label('Причина для журнала аудита', exact=True).fill('Synthetic browser acceptance')
        staff.get_by_role('button', name='Опубликовать', exact=True).click()
        expect(staff.get_by_role('status').filter(has_text='Опубликовано')).to_be_visible()
        now[0] += 61
        guest.goto(site + '/status?lang=en')
        expect(guest.get_by_role('heading', name=TITLE)).to_be_visible()
        expect(guest.get_by_text(EDITORIAL, exact=True)).to_be_visible()
        expect(guest.get_by_alt_text('Status illustration')).to_be_visible()
        assert guest.evaluate("!window.testInjection && document.querySelector('main script') === null")
        guest.goto(site + '/status?lang=ru')
        expect(guest.get_by_role('heading', name='Состояние сервиса')).to_be_visible()
        checks.append('real scoped draft media preview publish and safe public DOM')

        staff.get_by_role('button', name='История версий', exact=True).click()
        baseline = staff.locator('.publishing-history-row').filter(has_text='Редакция 0')
        baseline.get_by_role('button', name='Восстановить как черновик').click()
        baseline.get_by_label('Причина для журнала аудита').fill('Restore shipped status copy')
        baseline.get_by_role('button', name='Сохранить восстановленный черновик').click()
        expect(staff.get_by_role('status').filter(has_text='Версия восстановлена в черновик')).to_be_visible()
        guest.goto(site + '/status?lang=en')
        expect(guest.get_by_role('heading', name=TITLE)).to_be_visible()
        for width in (320, 390, 820):
            staff.set_viewport_size({'width': width, 'height': 900})
            assert staff.evaluate('document.documentElement.scrollWidth <= innerWidth')
        staff.screenshot(path=str(OUT / 'pages-editor.png'), full_page=True)
        checks.append('restore stages independently of publication; editor fits narrow widths')
        now[0] += 61
        check_reconcile_and_urls(staff)
        checks.append('stale drafts preserve local edits and merge reviewed remote values; saved URL previews are inert')
        check_pending_save(staff)
        checks.append('returning to a scope during a pending save cannot lose newer edits')
        check_discarded_upload(staff)
        checks.append('a detached media response cannot resurrect discarded edits')

        # Hold only the unauthenticated publication GET to exercise a customer's
        # in-progress application while an editorial response is delayed.
        held = []
        guest.route('**/public-pages/document?*', lambda route: held.append(route))
        guest.goto(site + '/early-access?lang=ru', wait_until='domcontentloaded')
        email = guest.get_by_label('Электронная почта', exact=True)
        email.fill('guest@example.test')
        assert held
        held.pop().fulfill(json={'page': '/early-access', 'locale': 'ru', 'revision': 2,
                                 'content': {'fields': {'closed.title': 'Обновлённое введение'}, 'regions': {}}})
        expect(guest.get_by_role('heading', name='Обновлённое введение')).to_be_visible()
        expect(email).to_have_value('guest@example.test')
        checks.append('late editorial update preserves typed early-access form')
        guest.set_viewport_size({'width': 1100, 'height': 900})
        guest.goto(site + '/account?lang=ru', wait_until='domcontentloaded')
        email = guest.get_by_label('Электронная почта', exact=True)
        email.fill('guest@example.test')
        assert held
        held.pop().fulfill(json={'page': '/account', 'locale': 'ru', 'revision': 2,
                                 'content': {'fields': {'title': 'Новая история входа'}, 'regions': {}}})
        expect(guest.get_by_text('Новая история входа', exact=True)).to_be_visible()
        expect(email).to_have_value('guest@example.test')
        guest.locator('.focus-login-language select').select_option('en')
        expect(guest.locator('input[name=email]')).to_have_value('guest@example.test')
        expect(guest).to_have_title('ULADIM')
        expect(guest.locator('html')).to_have_attribute('lang', 'en')
        assert held
        held.pop().fulfill(json={'page': '/account', 'locale': 'en', 'revision': 3,
                                 'content': {'fields': {'title': 'A different sign-in story'}, 'regions': {}}})
        expect(guest.get_by_text('A different sign-in story', exact=True)).to_be_visible()
        expect(guest.locator('input[name=email]')).to_have_value('guest@example.test')
        checks.append('late and switched-locale account copy preserves typed sign-in form')
        now[0] += 61
        if all(android_tools()):
            check_android(staff, guest, site)
            checks.append('real binary APK upload, wrong package, cancellation, verification and explicit publication')
        else:
            checks.append('Android browser journey requires Android verification tools')
        check_control_language(staff)
        checks.append('German Control displays translated route names, editor fields and block controls')
        assert not errors, errors
        browser.close()
    output = {'checks': checks, 'scope': 'Real isolated WSGI and Control MFA; synthetic held editorial response'}
    (OUT / 'checks.json').write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(output, ensure_ascii=False))


if __name__ == '__main__':
    main()
