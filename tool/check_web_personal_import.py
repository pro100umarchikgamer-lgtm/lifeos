"""Exercise personal file import through the existing authenticated workspace API."""

import os

import argparse
import io
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from playwright.sync_api import expect, sync_playwright

from tool.check_web_platform import fixture, login
from tool.web_browser_navigation import open_settings, open_tab


CALENDAR = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:test-weekly
DTSTART;TZID=Europe/Moscow:20261110T173000
RRULE:FREQ=WEEKLY;INTERVAL=1
SUMMARY:Учебный созвон
END:VEVENT
BEGIN:VEVENT
UID:test-utc
DTSTART:20261111T101500Z
SUMMARY:Встреча UTC
END:VEVENT
BEGIN:VEVENT
UID:test-exception
DTSTART:20261110T110000Z
EXDATE:20261117T110000Z
RRULE:FREQ=WEEKLY
SUMMARY:Не переносить без исключения
END:VEVENT
END:VCALENDAR
"""


def upload(name, data):
    return {
        'name': name, 'mimeType': 'application/octet-stream',
        'buffer': data.encode() if isinstance(data, str) else data,
    }


def keep_archive():
    buffer = io.BytesIO()
    with ZipFile(buffer, 'w', ZIP_DEFLATED) as archive:
        archive.writestr('Takeout/Keep/checklist.json', json.dumps({
            'title': 'Список из Keep', 'isPinned': True, 'isArchived': False,
            'listContent': [{'text': 'Проверить данные', 'isChecked': True}],
        }))
        archive.writestr('Takeout/Keep/photo.png', b'synthetic attachment')
    return buffer.getvalue()


def run(output, engine):
    with fixture(https=True) as (origin, backend, actor, workspace), sync_playwright() as playwright:
        executable = os.environ.get('ULADIM_CHROMIUM') if engine == 'chromium' else None
        browser = getattr(playwright, engine).launch(**({'executable_path': executable} if executable else {}))
        # The refresh failure must be injected by the page route, including in WebKit.
        page = browser.new_page(viewport={'width': 390, 'height': 844}, locale='ru-RU',
                                service_workers='block', ignore_https_errors=True)
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        login(page, origin)
        nav = page.locator('.nav')
        expect(nav.get_by_role('button', name='Импорт и синхронизация')).to_have_count(0)
        open_tab(page, 'Профиль')
        open_settings(page, 'personal-import')
        expect(page.get_by_role('heading', name='Импорт и синхронизация')).to_be_visible()
        expect(page.get_by_text('Подключение Google Calendar готовится.')).to_be_visible()
        if output:
            page.screenshot(path=output / 'personal-import-profile.png')
        launch = page.get_by_role('button', name='Импортировать заметки')
        launch.click()
        dialog = page.get_by_role('dialog')
        picker = dialog.locator('input[type=file]')
        picker.set_input_files(upload('broken.json', '{"records":'))
        expect(dialog.get_by_text('Файл повреждён или его формат не распознан.')).to_be_visible()
        expect(dialog.get_by_role('button', name='Импортировать', exact=True)).to_be_hidden()

        samples = [
            upload('note.txt', 'Тестовая заметка\nТекст для синхронизации'),
            upload('readme.md', '# План\n- Пункт'),
            upload('keep.zip', keep_archive()),
            upload('calendar.ics', CALENDAR),
            upload('tasks.json', json.dumps({
                'format':'uladim-import', 'version':1,
                'records':[{'kind':'task', 'title':'Импортированная задача',
                            'completed':True, 'due':'2026-11-12', 'id':'task-1'}],
            })),
        ]
        picker.set_input_files(samples)
        expect(dialog.get_by_text('Календари: 2 · Заметки: 3 · Задачи: 1')).to_be_visible()
        expect(dialog.get_by_text('Вложения не перенесутся.')).to_be_visible()
        expect(dialog.get_by_text('Событие с исключением', exact=False)).to_be_visible()
        expect(dialog.get_by_text('Дополнительные поля задачи', exact=False)).to_be_visible()
        assert page.evaluate('document.documentElement.scrollWidth === innerWidth')
        if output:
            page.screenshot(path=output / 'personal-import-review.png')
        writes = []
        failed_refresh = []

        def lose_refresh(route):
            if route.request.method == 'POST':
                writes.append(route.request.post_data_json)
            elif writes and not failed_refresh:
                failed_refresh.append(True)
                return route.fulfill(status=503, json={'error': 'service_unavailable'})
            return route.continue_()

        page.route('**/account/api/sync*', lose_refresh)
        dialog.get_by_role('button', name='Импортировать', exact=True).click()
        expect(dialog.get_by_text('Сохранено: 6')).to_have_count(0)
        dialog.get_by_role('button', name='Повторить', exact=True).click(timeout=3500)
        expect(dialog.get_by_text('Сохранено: 6')).to_be_visible()
        assert len(writes) == 1, 'Refresh retry resent the accepted import'
        page.unroute('**/account/api/sync*', lose_refresh)
        if output:
            page.screenshot(path=output / 'personal-import-saved.png')

        snapshot = backend.pull(actor, workspace, 0)['records']
        imported = {record['data'].get('title') or record['data'].get('body','').splitlines()[0]:record for record in snapshot
                    if record['kind'] in ('event','task','note')}
        assert imported['Импортированная задача']['data']['completed'] == 1
        assert imported['Учебный созвон']['data']['schedule']['repeat'] == 'weekly'
        assert imported['Учебный созвон']['data']['schedule']['timezone'] == 'Europe/Moscow'
        assert imported['Встреча UTC']['data']['schedule']['timezone'] == 'UTC'
        assert '- [x] Проверить данные' in imported['Список из Keep']['data']['body']
        assert 'Не переносить без исключения' not in imported
        assert imported['Тестовая заметка']['visibility'] == 'private'

        picker.set_input_files(samples)
        expect(dialog.get_by_text('Уже есть: 6 · Пропущено: 2')).to_be_visible()
        expect(dialog.get_by_role('button', name='Импортировать', exact=True)).to_be_hidden()
        assert len(backend.pull(actor, workspace, 0)['records']) == len(snapshot)

        another = browser.new_page(locale='ru-RU', ignore_https_errors=True)
        login(another, origin)
        open_tab(another, 'Заметки')
        expect(another.get_by_role('heading', name='Тестовая заметка')).to_be_visible()
        expect(another.get_by_role('heading', name='Список из Keep')).to_be_visible()
        if output:
            another.screenshot(path=output / 'personal-import-notes.png')
        note = another.locator('article').filter(has_text='Тестовая заметка')
        note.get_by_role('button', name='Редактировать').click()
        editor = another.get_by_role('dialog')
        editor.locator('textarea').fill('Тестовая заметка после правки')
        editor.get_by_role('button', name='Сохранить').click()
        expect(another.get_by_role('heading', name='Тестовая заметка после правки')).to_be_visible()
        open_tab(another, 'Задачи')
        # Completed tasks are folded in the All view; open their visible group.
        another.locator('details.task-group[aria-labelledby="tasks-completed"] > summary').click()
        expect(another.get_by_role('checkbox', name='Импортированная задача')).to_be_checked()

        open_tab(another, 'Профиль')
        open_settings(another, 'personal-import')
        another.get_by_role('button', name='Импортировать задачи').click()
        reopened = another.get_by_role('dialog')
        reopened.locator('input[type=file]').set_input_files(upload('updated.json', json.dumps({
            'format':'uladim-import', 'version':1,
            'records':[{'kind':'task', 'title':'Изменённая задача', 'completed':False, 'id':'task-1'}],
        })))
        expect(reopened.get_by_text('Запись уже есть и отличается.', exact=False)).to_be_visible()
        expect(reopened.get_by_role('button', name='Импортировать', exact=True)).to_be_hidden()

        guide = browser.new_page(viewport={'width': 980, 'height': 960}, ignore_https_errors=True)
        guide.goto(origin + '/docs#import')
        expect(guide.get_by_role('heading', name='Перенос данных в ULADIM')).to_be_visible()
        if output:
            guide.screenshot(path=output / 'personal-import-guide.png')
        guide.goto(origin + '/faq#import')
        import_help = guide.locator('#import')
        expect(import_help).to_have_attribute('open', '')
        expect(import_help.locator('summary')).to_have_text('Как перенести записи из другого приложения?')
        expect(import_help.locator('.help-answer')).to_be_visible()
        expect(import_help.locator('.help-answer')).to_contain_text('Профиль → Импорт и синхронизация')
        expect(import_help.get_by_role('link', name='Пошаговый перенос', exact=True)).to_have_attribute('href', '/docs#import')
        assert not errors, errors
        browser.close()
    print(f'PERSONAL_IMPORT_OK ({engine}): 6 saved; duplicate prevention, second session, notes editing, FAQ')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path)
    parser.add_argument('--engine', choices=('chromium', 'webkit', 'firefox'), default='chromium')
    args = parser.parse_args()
    if args.output:
        args.output.mkdir(parents=True, exist_ok=True)
    run(args.output, args.engine)
