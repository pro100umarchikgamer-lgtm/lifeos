"""Bounded task-date acceptance against real WSGI, metadata and browser UI.

All accounts are disposable. The final worker check uses an injected push and
the real Notification API; it does not claim provider or physical-device sound.
"""
import json
import os
from pathlib import Path
import time
import uuid

from playwright.sync_api import sync_playwright, expect

from backend.task_reminders import TaskReminders
from tool.check_finance_filter_fit import source_styles
from tool.check_web_platform import fixture, login
from tool.check_web_push_browser import synthetic_notification_api, SUBSCRIPTION
from tool.web_browser_navigation import open_tab


OUT = Path('web_evidence/task-reminders')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    checks = []
    with synthetic_notification_api() as (push_status, receipts, _), fixture() as (origin, backend, actor, workspace), sync_playwright() as p:
        scenario_clock=[int(backend.clock())]
        backend.clock=lambda:scenario_clock[0]
        browser = p.chromium.launch(**({'executable_path':os.environ['ULADIM_CHROMIUM']} if os.environ.get('ULADIM_CHROMIUM') else {}))
        context = browser.new_context(viewport={'width': 390, 'height': 844}, locale='ru-RU',
                                      timezone_id='Europe/Moscow', service_workers='block', reduced_motion='reduce')
        styles = source_styles()
        context.route('**/assets/design.css', lambda route: route.fulfill(status=200, content_type='text/css', body=styles))
        page = context.new_page()
        errors, main_writes = [], []
        page.on('pageerror', lambda error: errors.append(str(error)))

        def track_main(route):
            if route.request.method == 'POST':
                main_writes.extend(route.request.post_data_json.get('operations', []))
            route.continue_()

        page.route('**/account/api/sync*', track_main)
        login(page, origin)
        reminders = TaskReminders(backend)

        def tasks():
            return [record for record in backend.pull(actor, workspace, 0)['records'] if record['kind'] == 'task' and not record['deleted']]

        def task_named(title):
            matching = [record for record in tasks() if record['data']['title'] == title]
            assert len(matching) == 1, (title, matching)
            return matching[0]

        def new_task(title, day, clock='18:35', notify=True):
            open_tab(page, 'Задачи')
            page.locator('.tasks-page .intro button').click()
            editor = page.get_by_role('dialog')
            editor.get_by_label('Название задачи', exact=True).fill(title)
            expect(editor.get_by_label('Дата задачи', exact=True)).to_be_enabled()
            editor.get_by_label('Дата задачи', exact=True).fill(day)
            if clock:
                editor.get_by_label('Время (необязательно)', exact=True).fill(clock)
            if notify:
                editor.get_by_label('Напомнить об этой задаче', exact=True).check()
            return editor

        def edit_task(title):
            open_tab(page, 'Задачи')
            page.locator('.task-row').filter(has_text=title).locator('button').first.click()
            editor = page.get_by_role('dialog')
            expect(editor.get_by_label('Дата задачи', exact=True)).to_be_visible()
            return editor

        editor = new_task('Task date persists after reload', '2026-12-15')
        expect(editor.get_by_role('button', name='Сохранить', exact=True)).to_be_in_viewport(ratio=1)
        page.screenshot(path=str(OUT / 'task-date-phone-light.png'), full_page=True)
        editor.get_by_role('button', name='Сохранить', exact=True).click()
        expect(editor).to_have_count(0)
        task = task_named('Task date persists after reload')
        metadata = reminders.get(actor, workspace, task['id'])
        assert metadata['schedule']['localStart'] == '2026-12-15T18:35:00' and metadata['reminder']
        assert set(task['data']) == {'title', 'completed', 'assignment', 'assignees', 'review'}
        page.reload()
        expect(page.get_by_role('heading', name='Сегодня', exact=True)).to_be_visible()
        editor = edit_task(task['data']['title'])
        expect(editor.get_by_label('Дата задачи', exact=True)).to_have_value('2026-12-15')
        expect(editor.get_by_label('Время (необязательно)', exact=True)).to_have_value('18:35')
        expect(editor.get_by_label('Напомнить об этой задаче', exact=True)).to_be_checked()
        page.set_viewport_size({'width': 320, 'height': 844})
        page.evaluate('state.theme="dark";preferences()')
        assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
        expect(editor.get_by_role('button', name='Сохранить', exact=True)).to_be_in_viewport(ratio=1)
        page.screenshot(path=str(OUT / 'task-date-reloaded-phone-dark.png'), full_page=True)
        editor.get_by_role('button', name='Отмена', exact=True).click()
        page.set_viewport_size({'width': 390, 'height': 844})
        page.evaluate('state.theme="light";preferences()')
        checks.append('date_time_and_opt_in_persist_in_backend_after_real_page_reload')

        posts = []
        def reject_schedule(route):
            if route.request.method == 'POST':
                posts.append(route.request.post_data_json)
                route.fulfill(status=500, content_type='application/json', body='{"error":"server_error"}')
            else:
                route.continue_()
        page.route('**/account/api/task-reminders**', reject_schedule)
        before = len(main_writes)
        editor = new_task('Accepted task survives metadata failure', '2026-12-16', '19:10')
        editor.get_by_role('button', name='Сохранить', exact=True).click()
        expect(editor.locator('.error')).to_contain_text('Задача сохранена')
        expect(editor.get_by_label('Название задачи', exact=True)).to_be_disabled()
        expect(editor.get_by_label('Дата задачи', exact=True)).to_have_value('2026-12-16')
        assert len(main_writes) == before + 1 and len(posts) == 1
        task_named('Accepted task survives metadata failure')
        page.screenshot(path=str(OUT / 'task-date-save-retry.png'), full_page=True)
        page.unroute('**/account/api/task-reminders**', reject_schedule)
        editor.get_by_role('button', name='Повторить', exact=True).click()
        expect(editor).to_have_count(0)
        assert len(main_writes) == before + 1
        retried = task_named('Accepted task survives metadata failure')
        assert reminders.get(actor, workspace, retried['id'])['schedule']['localStart'] == '2026-12-16T19:10:00'
        checks.append('metadata_failure_retains_input_and_retries_without_duplicate_main_task')

        lost_posts = []
        def lose_schedule_response(route):
            if route.request.method == 'POST':
                lost_posts.append(route.request.post_data_json)
                route.fetch()
                route.abort()
            else:
                route.continue_()
        page.route('**/account/api/task-reminders**', lose_schedule_response)
        before = len(main_writes)
        editor = new_task('Task date reconciles lost response', '2026-12-17', '17:20', False)
        editor.get_by_role('button', name='Сохранить', exact=True).click()
        expect(editor).to_have_count(0)
        page.unroute('**/account/api/task-reminders**', lose_schedule_response)
        assert len(lost_posts) == 1 and len(main_writes) == before + 1
        lost = task_named('Task date reconciles lost response')
        assert reminders.get(actor, workspace, lost['id'])['schedule']['localStart'] == '2026-12-17T17:20:00'
        checks.append('lost_metadata_response_is_read_reconciled_without_another_write')

        def block_metadata_read(route):
            if route.request.method == 'GET':
                route.abort()
            else:
                route.continue_()
        page.route('**/account/api/task-reminders**', block_metadata_read)
        open_tab(page, 'Задачи')
        page.locator('.task-row').filter(has_text=task['data']['title']).locator('button').first.click()
        editor = page.get_by_role('dialog')
        expect(editor.locator('.task-schedule-status')).to_contain_text('Не удалось загрузить')
        before = len(main_writes)
        editor.get_by_label('Название задачи', exact=True).fill('Unsaved title remains while date reloads')
        editor.get_by_role('button', name='Сохранить', exact=True).click()
        expect(editor.locator('.error')).to_contain_text('Сохранённая дата не изменена')
        assert len(main_writes) == before
        assert reminders.get(actor, workspace, task['id']) == metadata
        page.unroute('**/account/api/task-reminders**', block_metadata_read)
        editor.get_by_role('button', name='Загрузить сохранённую дату', exact=True).click()
        expect(editor.get_by_label('Дата задачи', exact=True)).to_have_value('2026-12-15')
        expect(editor.get_by_label('Название задачи', exact=True)).to_have_value('Unsaved title remains while date reloads')
        editor.get_by_role('button', name='Отмена', exact=True).click()
        checks.append('failed_initial_metadata_get_never_clears_saved_date_or_submits_task')

        editor = edit_task(lost['data']['title'])
        editor.get_by_role('button', name='Без даты', exact=True).click()
        editor.get_by_role('button', name='Сохранить', exact=True).click()
        expect(editor).to_have_count(0)
        assert reminders.get(actor, workspace, lost['id'])['schedule'] is None
        checks.append('clear_date_persists_without_leaving_an_enabled_reminder')

        peer = str(uuid.uuid4())
        with backend.transaction() as db:
            db.execute('INSERT INTO users VALUES(?,?,?,?,1,?)', (peer, peer + '@example.test', 'unused', 'unused', int(time.time())))
            db.execute("INSERT INTO memberships(workspace_id,user_id,role) VALUES(?,?,'adult')", (workspace, peer))
        peer_actor = {'id': peer, 'verified': 1}
        readonly = str(uuid.uuid4())
        backend.batch(peer_actor, workspace, [{'id': str(uuid.uuid4()), 'action': 'record.put', 'record_id': readonly, 'revision': 0,
            'kind': 'task', 'visibility': 'private', 'audience': [], 'data': {'title': 'Read only scheduled task', 'completed': 0, 'assignment': 'any', 'assignees': [], 'review': 0}}])
        reminders.save(peer_actor, {'workspace_id': workspace, 'task_id': readonly, 'revision': 0, 'schedule': metadata['schedule'], 'reminder': False})
        with backend.transaction() as db:
            db.execute('INSERT INTO grants VALUES(?,?,0)', (readonly, actor['id']))
        page.reload()
        expect(page.get_by_role('heading', name='Сегодня', exact=True)).to_be_visible()
        editor = edit_task('Read only scheduled task')
        expect(editor.get_by_label('Дата задачи', exact=True)).to_be_disabled()
        expect(editor.get_by_label('Напомнить об этой задаче', exact=True)).to_be_disabled()
        editor.get_by_role('button', name='Отмена', exact=True).click()
        checks.append('read_only_task_can_view_persisted_date_but_cannot_edit_it')

        scenario_clock[0]+=61
        link = '/app?notification=task&workspace=' + workspace + '&task=' + task['id']
        page.goto(origin + link)
        editor = page.get_by_role('dialog')
        expect(editor.get_by_label('Название задачи', exact=True)).to_have_value(task['data']['title'])
        expect(editor.get_by_label('Дата задачи', exact=True)).to_have_value('2026-12-15')
        editor.get_by_role('button', name='Отмена', exact=True).click()
        for suffix in ['&task=' + task['id'], '&extra=1']:
            page.goto(origin + link + suffix)
            expect(page.get_by_role('heading', name='Сегодня', exact=True)).to_be_visible()
            expect(page.get_by_role('dialog')).to_have_count(0)
        page.goto(origin + '/app?notification=task&workspace=' + workspace + '&task=' + str(uuid.uuid4()))
        expect(page.get_by_role('heading', name='Сегодня', exact=True)).to_be_visible()
        expect(page.get_by_role('dialog')).to_have_count(0)
        checks.append('task_deep_link_opens_only_a_visible_task_and_rejects_duplicate_unknown_keys')

        denied = context.request.post(origin + '/account/api/task-reminders', data={
            'workspace_id': workspace, 'task_id': task['id'], 'revision': metadata['revision'],
            'schedule': metadata['schedule'], 'reminder': True})
        assert denied.status == 403
        checks.append('new_mutation_route_retains_existing_csrf_guard')

        # A real worker/Notification API accepts the new link. The push and
        # provider consent status are synthetic, as in the existing push fixture.
        scenario_clock[0]+=61
        notification_context = browser.new_context(storage_state=context.storage_state(), permissions=['notifications'])
        worker_page = notification_context.new_page()
        cdp = notification_context.new_cdp_session(worker_page)
        registrations = []
        cdp.on('ServiceWorker.workerRegistrationUpdated', lambda event: registrations.extend(event['registrations']))
        cdp.send('ServiceWorker.enable')
        worker_page.goto(origin + '/app/assets/offline.html')
        worker_page.evaluate("async()=>{await navigator.serviceWorker.register('/app/sw.js',{scope:'/app'});await navigator.serviceWorker.ready;}")
        push_status.update(enabled=True, subscription_id=SUBSCRIPTION)
        registration = next(item['registrationId'] for item in reversed(registrations) if item['scopeURL'] == origin + '/app')
        delivery = str(uuid.uuid4())
        payload = {'v': 1, 'delivery_id': delivery, 'subscription_id': SUBSCRIPTION, 'recipient_user_id': actor['id'],
            'receipt_token': 'R' * 43, 'title': 'ULADIM', 'body': 'Напоминание о задаче', 'url': link,
            'tag': 'uladim-' + delivery, 'priority': 'high', 'sent_at': int(time.time() * 1000)}
        cdp.send('ServiceWorker.deliverPushMessage', {'origin': origin, 'registrationId': registration, 'data': json.dumps(payload)})
        worker_page.wait_for_function('async()=> (await (await navigator.serviceWorker.ready).getNotifications()).length===1')
        shown = worker_page.evaluate('async()=>{const item=(await (await navigator.serviceWorker.ready).getNotifications())[0];return {body:item.body,url:item.data.url};}')
        assert shown == {'body': 'Напоминание о задаче', 'url': link}
        assert any(receipt['delivery_id'] == delivery and receipt['state'] == 'displayed' for receipt in receipts)
        checks.append('actual_service_worker_shows_task_notification_and_posts_display_receipt_for_injected_push')
        assert not errors, errors
        notification_context.close()
        context.close()
        browser.close()
    (OUT / 'checks.json').write_text(json.dumps({'checks': checks, 'notification_scope': 'Actual browser worker/Notification API; synthetic injected push and provider status. No physical-device or sound claim.'}, ensure_ascii=False, indent=2) + '\n')
    print('TASK_REMINDERS_BROWSER_OK', len(checks), 'focused checks')


if __name__ == '__main__':
    main()
