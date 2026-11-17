"""Scoped phone Today geometry against disposable real fixture records."""
import argparse
import os
from pathlib import Path
from uuid import uuid4
import json
from playwright.sync_api import sync_playwright, expect
from tool.check_web_platform import fixture, login
from tool.check_finance_filter_fit import source_styles


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',default='web_evidence/mobile-today-after')
    args=parser.parse_args()
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    results=[]
    with fixture() as (origin,backend,actor,wid),sync_playwright() as p:
        def put(kind,data):
            backend.batch(actor,wid,[{'id':str(uuid4()),'action':'record.put','record_id':str(uuid4()),'revision':0,
                'kind':kind,'visibility':'private','audience':[],'data':data}])
        for currency,opening in [('USD',203500),('UZS',202850000)]:
            put('account',{'name':'Накопления '+currency,'currency':currency,'opening_minor':opening})
        for i in range(5):
            put('task',{'title':'Важная задача на сегодня '+str(i),'completed':0,'assignment':'any','assignees':[],'review':0})
        browser=p.chromium.launch(**({'executable_path':os.environ['ULADIM_CHROMIUM']} if os.environ.get('ULADIM_CHROMIUM') else {}))
        context=browser.new_context(viewport={'width':390,'height':844},locale='ru-RU',service_workers='block',reduced_motion='reduce')
        css=source_styles()
        context.route('**/assets/design.css',lambda route:route.fulfill(status=200,content_type='text/css',body=css))
        page=context.new_page();login(page,origin)
        for width in (320,390,430):
            page.set_viewport_size({'width':width,'height':844})
            for theme in ('light','dark'):
                page.evaluate('(theme)=>{state.theme=theme;applyTheme()}',theme)
                data=page.locator('main.today-page').evaluate('''main=>{
                    const r=el=>{let b=el.getBoundingClientRect();return {y:b.y,bottom:b.bottom,height:b.height,width:b.width}};
                    const summary=main.querySelector('.reference-summary');
                    const tasks=main.querySelector('.today-tasks');
                    return {summary:r(summary),tasks:r(tasks),quick:r(tasks.querySelector('input[name=quick-task]')),
                      mainChildren:[...main.children].map(el=>({class:el.className,...r(el)})),
                      overflow:document.documentElement.scrollWidth>innerWidth,
                      currencies:[...main.querySelectorAll('.reference-tile-currencies .summary-currency-row')].map(el=>({currency:el.dataset.currency,...r(el)}))};
                }''')
                if width==390 and theme=='light':
                    page.screenshot(path=str(out/'today-phone.png'))
                    page.screenshot(path=str(out/'today-phone-full.png'),full_page=True)
                results.append({'width':width,'theme':theme,**data})
        (out/'geometry.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
        # Access the task entry before scrolling past duplicated dashboard summaries.
        assert all(x['tasks']['y']<x['summary']['y'] for x in results), results
        assert all(x['quick']['bottom']<620 for x in results), results
        assert all(x['summary']['height']<200 for x in results), results
        assert all(not x['overflow'] and len(x['currencies'])==3 for x in results), results
        expect(page.locator('.reference-summary-tile[data-summary=workspace]')).to_be_hidden()
        # The real add/edit and section actions remain reachable.
        expect(page.locator('.today-tasks .task-actions').get_by_role('button').first).to_be_visible()
        expect(page.locator('.today-finance .today-add-operation')).to_be_visible()
        browser.close()
    print('MOBILE_TODAY_GEOMETRY_OK',len(results),'phone/theme states')


if __name__=='__main__':main()
