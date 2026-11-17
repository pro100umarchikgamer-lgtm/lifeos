"""Focused source-account acceptance on the real stable backend API."""
import json
import os
from pathlib import Path
from uuid import uuid4
from playwright.sync_api import expect
import tool.check_statement_browser as harness
from tool.web_browser_navigation import open_tab

OUT=Path(os.environ.get('ULADIM_STATEMENT_ACCOUNT_EVIDENCE','web_evidence/statement-accounts'))


def run(browser, backend, actor, workspace, origin):
    OUT.mkdir(parents=True, exist_ok=True)
    context=browser.new_context(viewport={'width':1180,'height':900},locale='ru-RU',service_workers='block')
    page=context.new_page()
    errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto(origin+'/app/')
    page.locator('input[name=email]').fill(actor['email'])
    page.locator('input[name=password]').fill(harness.PASSWORD)
    page.get_by_role('button',name='Войти',exact=True).click()
    expect(page.get_by_role('heading',name='Сегодня',exact=True)).to_be_visible()
    open_tab(page,'Финансы')
    launch=page.locator('.reference-finance-group button:visible,.finance-toolbar button:visible').filter(has_text='Импортировать выписку')

    def all_records(kind):
        cursor=0
        result=[]
        while True:
            batch=backend.pull(actor,workspace,cursor)
            result.extend(row for row in batch['records'] if row['kind']==kind and not row['deleted'])
            if not batch['more']:
                return result
            cursor=batch['cursor']

    def upload(content,name='owners.csv'):
        launch.click()
        dialog=page.get_by_role('dialog')
        dialog.locator('input[type=file]').set_input_files({'name':name,'mimeType':'text/csv','buffer':content.encode()})
        expect(dialog.locator('tbody tr').first).to_be_visible()
        return dialog

    def close(dialog):
        dialog.get_by_role('button',name='Закрыть',exact=True).click()
        expect(dialog).to_have_count(0)

    def save(dialog,count):
        expect(dialog.locator('.statement-source-confirm')).to_be_hidden()
        for checkbox in dialog.locator('tbody input[type=checkbox]:enabled').all():
            checkbox.check()
        dialog.get_by_role('button',name='Импортировать выбранное',exact=True).click()
        expect(dialog.locator('.statement-receipt')).to_contain_text('Сохранено операций · '+str(count))

    text='Date;Amount;Currency;Description;account_id;Transaction ID\n2026-11-11;-1.25;USD;One;synthetic-source-10001;bank-same\n2026-11-12;2.50;USD;Two;synthetic-source-20002;bank-same'
    dialog=upload(text)
    group=dialog.locator('.statement-source-accounts')
    expect(group).to_be_visible()
    expect(group).to_contain_text('•••• 0001')
    assert 'synthetic-source-10001' not in group.inner_text()
    expect(group.locator('.statement-source-confirm')).to_have_text('Создать счета и использовать · 2')
    expect(dialog.get_by_role('button',name='Импортировать выбранное',exact=True)).to_be_disabled()
    assert not all_records('account') and not all_records('transaction')
    page.screenshot(path=str(OUT/'separate-before-confirm.png'))

    captured=[]
    lost=[False]
    def lost_response(route):
        body=route.request.post_data_json
        if body and any(op.get('kind')=='account' for op in body.get('operations',[])):
            captured.append(body['operations'])
            if not lost[0]:
                lost[0]=True
                response=route.fetch()
                assert response.ok
                route.abort()
                return
        route.continue_()
    page.route('**/account/api/sync',lost_response)
    group.locator('.statement-source-confirm').click()
    expect(group).to_contain_text('Повторите запрос')
    assert len(all_records('account'))==2 and not all_records('transaction')
    expect(dialog.get_by_role('button',name='Импортировать выбранное',exact=True)).to_be_disabled()
    group.locator('.statement-source-confirm').click()
    expect(group.locator('.statement-source-confirm')).to_be_hidden()
    assert len(captured)==2 and captured[0]==captured[1], 'Account operations must survive a lost response unchanged'
    page.unroute('**/account/api/sync',lost_response)
    assert all(row['data']['opening_minor']==0 for row in all_records('account'))
    save(dialog,2)
    transactions=all_records('transaction')
    assert len({row['data']['account_id'] for row in transactions})==2
    close(dialog)

    # New dialog and changed filename reuse deterministic accounts and skip rows.
    dialog=upload(text,'renamed.csv')
    expect(dialog.locator('.statement-source-confirm')).to_have_text('Использовать счета')
    dialog.locator('.statement-source-confirm').click()
    expect(dialog.get_by_role('button',name='Импортировать выбранное',exact=True)).to_be_disabled()
    assert len(all_records('account'))==2 and len(all_records('transaction'))==2
    close(dialog)

    # Combine is explicit, creates no accounts and routes both sources to the chosen one.
    combined=text.replace('One;','Combined one;').replace('Two;','Combined two;').replace('bank-same','bank-combined')
    dialog=upload(combined)
    dialog.locator('select[name=statement-account-strategy]').select_option('combine')
    target=all_records('account')[1]['id']
    dialog.locator('select[name=statement-combine-account]').select_option(target)
    dialog.locator('.statement-source-confirm').click()
    save(dialog,2)
    combined_rows=[row for row in all_records('transaction') if row['data']['label'].startswith('Combined')]
    assert len(combined_rows)==2 and all(row['data']['account_id']==target for row in combined_rows)
    assert len(all_records('account'))==2
    close(dialog)

    # Different currencies cannot combine; splitting can create only the missing EUR account.
    mixed=text.replace('2.50;USD','2.50;EUR').replace('bank-same','bank-mixed')
    dialog=upload(mixed)
    dialog.locator('select[name=statement-account-strategy]').select_option('combine')
    expect(dialog.locator('.statement-source-accounts')).to_contain_text('Разные валюты нельзя объединить')
    expect(dialog.locator('.statement-source-confirm')).to_be_disabled()
    assert len(all_records('account'))==2
    dialog.locator('select[name=statement-account-strategy]').select_option('separate')
    expect(dialog.locator('.statement-source-confirm')).to_have_text('Создать счета и использовать · 1')
    dialog.locator('.statement-source-confirm').click()
    save(dialog,2)
    assert len(all_records('account'))==3
    close(dialog)

    # Counterparty fields and descriptions do not activate the split feature.
    generic='Date;Amount;Currency;Description;counterparty_account_number\n2026-11-10;1;USD;Account source-12345;counterparty-67890'
    dialog=upload(generic)
    expect(dialog.locator('.statement-source-accounts')).to_be_hidden()
    for content,shown in [(text,True),(generic,False)]:
        dialog.locator('input[type=file]').set_input_files({'name':'changed.csv','mimeType':'text/csv','buffer':content.encode()})
        if shown:
            expect(dialog.locator('.statement-source-accounts')).to_be_visible()
            expect(dialog.locator('select[name=import-account]')).to_be_hidden()
        else:
            expect(dialog.locator('.statement-source-accounts')).to_be_hidden()
            expect(dialog.locator('select[name=import-account]')).to_be_visible()
    close(dialog)

    # Check compact sizes before applying an account choice.
    dialog=upload(text)
    for width,height,name in [(390,844,'phone'),(768,900,'tablet')]:
        page.set_viewport_size({'width':width,'height':height})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.screenshot(path=str(OUT/f'accounts-{name}.png'))
    close(dialog)
    # A lost account response remains safe after closing and reopening the file.
    reopen_text='Date;Amount;Currency;Description;account_id\n2026-11-13;-3;USD;Reopen;synthetic-reopen-30003'
    dialog=upload(reopen_text)
    lost[0]=False
    page.route('**/account/api/sync',lost_response)
    dialog.locator('.statement-source-confirm').click()
    expect(dialog.locator('.statement-source-accounts')).to_contain_text('Повторите запрос')
    assert len(all_records('account'))==4 and len(all_records('transaction'))==6
    page.unroute('**/account/api/sync',lost_response)
    close(dialog)
    page.evaluate('async()=>{await refresh();render()}')
    dialog=upload(reopen_text)
    expect(dialog.locator('.statement-source-confirm')).to_have_text('Использовать счета')
    dialog.locator('.statement-source-confirm').click()
    save(dialog,1)
    assert len(all_records('account'))==4 and len(all_records('transaction'))==7
    close(dialog)

    # Deterministic-ID collisions never overwrite another kind or currency.
    for kind in ['note','account']:
        owner='synthetic-collision-'+kind
        record_id=page.evaluate("async owner=>statementID(JSON.stringify([state.session.user_id,state.space,'uladim-statement-owner-account-v1',JSON.stringify(['',owner,'USD'])]))",owner)
        data={'body':'Collision must stay unchanged'} if kind=='note' else {'name':'Collision account','currency':'EUR','opening_minor':42}
        result=backend.batch(actor,workspace,[{'id':str(uuid4()),'action':'record.put','record_id':record_id,'revision':0,'kind':kind,'visibility':'private','audience':[],'data':data}])
        assert result['results'][0]['status']=='accepted'
        page.evaluate('async()=>{await refresh();render()}')
        launch.click()
        dialog=page.get_by_role('dialog')
        content='Date;Amount;Currency;account_id\n2026-11-13;9;USD;'+owner
        dialog.locator('input[type=file]').set_input_files({'name':'collision.csv','mimeType':'text/csv','buffer':content.encode()})
        expect(dialog.locator('.import-status')).to_have_text('Не удалось подтвердить счёт. Проверьте доступ и повторите.')
        expect(dialog.get_by_role('button',name='Импортировать выбранное',exact=True)).to_be_disabled()
        original=next(row for row in all_records(kind) if row['id']==record_id)
        assert original['data']==data and len(all_records('transaction'))==7
        close(dialog)

    # Row corrections recover the owning source and require renewed confirmation
    # if they add an account/currency missing from the valid preview.
    correction=text.replace('One;','Corrected one;').replace('Two;','Corrected two;').replace('bank-same','bank-correction').replace('2026-11-12','invalid-date')
    dialog=upload(correction)
    dialog.locator('.statement-source-confirm').click()
    expect(dialog.locator('.statement-source-confirm')).to_be_hidden()
    dialog.get_by_role('button',name='Исправить строку',exact=True).click()
    editor=dialog.locator('.statement-row-correction')
    editor.locator('input[name=date]').fill('2026-11-12')
    editor.get_by_role('button',name='Сохранить',exact=True).click()
    expect(editor).to_be_hidden()
    expect(dialog.locator('.statement-source-confirm')).to_be_visible()
    dialog.locator('.statement-source-confirm').click()
    save(dialog,2)
    close(dialog)

    assert not errors,errors
    result={'checks':['explicit separate and combine choices','no writes before account confirmation','lost account response retains operation IDs','accounts confirmed before transaction writes','repeat import reuses accounts and transaction IDs','zero opening balances','mixed currencies split and combine rejection','counterparty metadata ignored','phone and tablet fit','lost response followed by close and reopen','wrong-kind and wrong-currency ID collision rejection','generic-file switch restores account selector','row correction restores source mapping'], 'accounts':len(all_records('account')),'transactions':len(all_records('transaction')),'page_errors':errors}
    (OUT/'browser-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False))
    context.close()


if __name__=='__main__':
    harness.run=run
    harness.OUT=OUT
    harness.main()
