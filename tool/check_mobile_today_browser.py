"""Populated mobile acceptance: readable Today, exact currencies and bounded ledger DOM."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import uuid

from playwright.sync_api import expect, sync_playwright
from tool.check_web_platform import fixture, login
from tool.web_browser_navigation import open_tab, open_finance_section

OUT=Path('web_evidence/mobile-today')


def operation(kind,data):
    return {'id':str(uuid.uuid4()),'action':'record.put','record_id':str(uuid.uuid4()),'revision':0,
            'kind':kind,'visibility':'private','audience':[],'data':data}


def all_records(backend,actor,workspace):
    cursor=0;rows=[]
    while True:
        page=backend.pull(actor,workspace,cursor);rows.extend(page['records']);cursor=page['cursor']
        if not page['more']:return [row for row in rows if not row.get('deleted')]


def formatted_ru(minor):
    return format(minor//100,',').replace(',',' ')+','+str(minor%100).zfill(2)


def main():
    OUT.mkdir(parents=True,exist_ok=True);checks=[]
    with fixture() as (origin,backend,actor,workspace):
        rows=all_records(backend,actor,workspace)
        rub=next(row['id'] for row in rows if row['kind']=='account')
        uzs,usd=[str(uuid.uuid4()) for _ in range(2)]
        accounts=[operation('account',{'name':'Семейный счёт в сумах','currency':'UZS','opening_minor':0}),
                  operation('account',{'name':'Резерв в долларах','currency':'USD','opening_minor':0})]
        accounts[0]['record_id']=uzs;accounts[1]['record_id']=usd
        work=accounts
        for code,account,amount in [('RUB',rub,123456789012),('UZS',uzs,67890123456789),('USD',usd,987654321)]:
            work.append(operation('transaction',{'kind':'expense','amount_minor':amount,'currency':code,'date':'2026-11-13','label':'Крупный платёж по семейному плану '+code,'account_id':account}))
        for number in range(100):
            work.append(operation('transaction',{'kind':'expense','amount_minor':100,'currency':'RUB','date':'2026-11-13','label':'Проверка страницы '+str(number).zfill(3),'account_id':rub}))
        for number in range(18):
            work.append(operation('task',{'title':'Задача '+str(number+1)+': подготовить документы для семейной поездки, проверить бронирование и согласовать удобное время встречи','completed':0,'assignment':'any','assignees':[],'review':0}))
        for number in range(8):
            work.append(operation('event',{'title':'Встреча '+str(number+1)+': обсудить планы семьи, расписание поездки и подготовку к следующей неделе','schedule':{'localStart':'2026-11-13T19:'+str(number).zfill(2)+':00','timezone':'Europe/Moscow','allDay':False,'repeat':'none','interval':1,'until':None}}))
        for number in range(8):
            work.append(operation('note',{'body':'Заметка '+str(number+1)+' о семейных планах и важных делах на следующую неделю\nПодробности поездки, полезные адреса и список вещей, которые нужно подготовить заранее.\nЕщё один абзац с важной информацией.'}))
        for start in range(0,len(work),25):
            result=backend.batch(actor,workspace,work[start:start+25]);assert all(row['status']=='accepted' for row in result['results']),result
        rows=all_records(backend,actor,workspace)
        expenses={code:sum(row['data']['amount_minor'] for row in rows if row['kind']=='transaction' and row['data']['kind']=='expense' and row['data']['currency']==code and row['data']['date'].startswith('2026-11')) for code in ['RUB','UZS','USD']}
        count_transactions=sum(row['kind']=='transaction' for row in rows)
        with sync_playwright() as p:
            browser=p.chromium.launch(**({'executable_path':os.environ['ULADIM_CHROMIUM']} if os.environ.get('ULADIM_CHROMIUM') else {}))
            context=browser.new_context(locale='ru-RU',timezone_id='Europe/Moscow',viewport={'width':390,'height':844},service_workers='block',reduced_motion='reduce')
            page=context.new_page();page.clock.install(time=datetime(2026,11,13,12,tzinfo=timezone.utc));errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            login(page,origin)
            for width,height in [(320,900),(375,900),(390,844),(430,932),(834,1112)]:
                page.set_viewport_size({'width':width,'height':height})
                for theme in ['light','dark']:
                    page.evaluate('theme=>{state.theme=theme;preferences();render();}',theme)
                    expect(page.locator('input[name=quick-task]')).to_be_visible()
                    page.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),(width,theme,'overflow')
                    money_rows=page.locator('[data-summary=expenses] .summary-currency-row')
                    assert money_rows.count()==3
                    for code,amount in expenses.items():
                        row=page.locator('[data-summary=expenses] [data-currency="'+code+'"]')
                        expect(row.locator('.summary-currency-code')).to_have_text(code)
                        expect(row.locator('.summary-currency-amount')).to_have_text(formatted_ru(amount))
                        assert row.evaluate('(e)=>e.scrollWidth<=e.clientWidth'),(width,theme,code,'amount clipped')
                    if width<760:
                        for caption in page.locator('.header-tool-label').all():
                            expect(caption).to_be_visible()
                            assert caption.evaluate('(e)=>e.getBoundingClientRect().height<=parseFloat(getComputedStyle(e).lineHeight)+1'),(width,caption.inner_text(),'wrapped header label')
                        assert page.locator('.reference-summary-tile:visible').count()==2
                        assert page.locator('.today-tasks>.task-row:visible').count()==3
                        assert page.locator('.today-timeline>li:visible').count()==3
                        quick=page.locator('input[name=quick-task]').bounding_box();assert quick and quick['y']+quick['height']<height-90,(width,theme,'quick capture below first screen',quick)
                        assert page.locator('.reference-summary').bounding_box()['height']<210,(width,theme,'oversized summary')
                        assert page.locator('.today-schedule').bounding_box()['y']<page.locator('.today-finance').bounding_box()['y']
                        assert page.locator('.today-secondary-actions button:visible').count()==2
                        for text in page.locator('.today-tasks>.task-row:visible>.text').all():
                            assert text.evaluate('(e)=>e.getBoundingClientRect().height<=parseFloat(getComputedStyle(e).lineHeight)*2+1')
                    else:
                        assert page.locator('.reference-summary-tile:visible').count()==4
                        assert page.locator('.today-tasks>.task-row:visible').count()==6
                    page.screenshot(path=str(OUT/('today-'+str(width)+'-'+theme+'.png')),full_page=False)
            checks.append('populated Today fits 320/375/390/430/834 in both themes, with exact independent RUB/UZS/USD rows')
            checks.append('phone first screen includes quick entry and two compact summaries; tasks and schedule previews are bounded without losing full destinations')
            page.set_viewport_size({'width':390,'height':844})
            page.locator('.today-secondary-actions').get_by_role('button',name='Календарь',exact=True).click()
            expect(page.locator('.calendar-layout')).to_be_visible();open_tab(page,'Сегодня')
            page.locator('.today-secondary-actions').get_by_role('button',name='Семья и участники',exact=True).click()
            expect(page.locator('.reference-space-grid')).to_be_visible();open_tab(page,'Сегодня')
            page.locator('.today-tasks').get_by_role('button',name='Все задачи',exact=True).click()
            assert page.locator('.task-list .task-row').count()>=19
            checks.append('calendar, family and complete task list remain available from labeled controls')
            open_tab(page,'Финансы');open_finance_section(page,'ledger')
            expect(page.locator('.ledger-row')).to_have_count(25)
            expect(page.locator('.ledger-pagination')).to_contain_text('Показано 25 из '+str(count_transactions))
            expect(page.locator('.finance-metric.expense')).to_contain_text(formatted_ru(expenses['RUB'])+' RUB')
            page.locator('.ledger-pagination button').click();expect(page.locator('.ledger-row')).to_have_count(50)
            expect(page.locator('.ledger-pagination')).to_contain_text('Показано 50 из '+str(count_transactions))
            page.locator('.finance-filter-panel>summary').click();page.locator('input[name=finance-search]').fill('Проверка страницы 099')
            expect(page.locator('.ledger-row')).to_have_count(1)
            expect(page.locator('.ledger-pagination')).to_contain_text('Показано 1 из 1')
            expect(page.locator('.ledger-pagination button')).to_be_hidden()
            expect(page.locator('.finance-metric.expense')).to_contain_text('1,00 RUB')
            page.locator('input[name=finance-search]').fill('');expect(page.locator('.ledger-row')).to_have_count(25)
            page.screenshot(path=str(OUT/'ledger-phone-paginated.png'),full_page=False)
            checks.append('105 actual transactions render 25 rows, then 50; filters reset page size while totals use the full filtered data')
            # More than 25 existing entries share this date. A new successful
            # save must still appear first, rather than disappearing on page 5.
            page.get_by_role('button',name='Добавить операцию',exact=True).click()
            editor=page.get_by_role('dialog')
            editor.locator('[name=amount]').fill('2.00')
            editor.locator('[name=account]').select_option(rub)
            editor.locator('[name=date]').fill('2026-11-13')
            editor.locator('[name=label]').fill('Новая операция за тот же день')
            editor.locator('button[type=submit]').click()
            expect(editor).to_have_count(0)
            expect(page.locator('.ledger-row').first).to_contain_text('Новая операция за тот же день')
            expect(page.locator('.ledger-row')).to_have_count(25)
            expect(page.locator('.ledger-pagination')).to_contain_text('Показано 25 из '+str(count_transactions+1))
            actual=next(row for row in all_records(backend,actor,workspace) if row['kind']=='transaction' and row['data']['label']=='Новая операция за тот же день')
            assert actual['data']['amount_minor']==200
            checks.append('new same-day transaction is saved exactly and appears first despite a full first page')
            empty=str(uuid.uuid4());backend.family(actor,{'id':str(uuid.uuid4()),'action':'workspace.create','workspace_id':empty,'kind':'personal','name':'Пустое пространство'})
            page.evaluate('async()=>{await refresh();render();}')
            page.locator('select[name=workspace]').select_option(empty);open_tab(page,'Сегодня')
            expect(page.locator('[data-summary=expenses]')).to_contain_text('—')
            assert page.locator('.summary-currency-row').count()==0
            assert page.locator('.reference-summary').bounding_box()['height']<210
            page.screenshot(path=str(OUT/'today-empty-phone.png'),full_page=False)
            checks.append('empty workspace stays compact and shows an honest dash without invented money')
            assert not errors,errors
            context.close();browser.close()
    (OUT/'checks.json').write_text(json.dumps({'status':'passed','environment':'real Chromium / production WSGI / synthetic populated records','checks':checks},ensure_ascii=False,indent=2)+'\n')
    print('MOBILE_TODAY_BROWSER_PASSED',len(checks))


if __name__=='__main__':main()
