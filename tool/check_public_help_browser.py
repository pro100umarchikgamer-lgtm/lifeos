"""Targeted public help/legal acceptance. Disposable fixture; no real accounts."""
import json, os
from pathlib import Path
from urllib.request import urlopen
from playwright.sync_api import sync_playwright, expect
from tool.check_web_platform import fixture

OUT=Path(os.environ.get('ULADIM_PUBLIC_HELP_EVIDENCE','web_evidence/public-help'))
PAGES={'/faq':'.help-question','/privacy':'.help-document','/terms':'.help-document','/delete-account':'.help-steps','/support':'.help-support-grid','/download':'.help-download-grid','/plans':'.help-plans'}
ANCHORS=('today','tasks','calendar','notes','finances','account','security','notifications','recovery','family','import','support','privacy','deletion','plans','installation','delete-staff-account')


def visit_help(page, origin, path, selector, errors):
    response = None
    try:
        response = page.goto(origin + path)
        page.wait_for_selector(selector)
    except Exception:
        diagnostic = {
            'path': path, 'actual_url': page.url,
            'response_status': response.status if response else None,
            'selector': selector, 'page_errors': list(errors),
            'body_excerpt': page.locator('body').inner_text(timeout=1000)[:1600],
            'selector_nodes': page.locator(selector).evaluate_all("""nodes => nodes.slice(0,4).map(node => {
                const style=getComputedStyle(node),rect=node.getBoundingClientRect();
                return {tag:node.tagName,classes:node.className,display:style.display,
                    visibility:style.visibility,width:rect.width,height:rect.height,
                    text:node.textContent.slice(0,120)};
            })"""),
        }
        (OUT / 'navigation-failure.json').write_text(json.dumps(diagnostic, ensure_ascii=False, indent=2)+'\n')
        print(json.dumps({'public_help_navigation_failure': diagnostic}, ensure_ascii=False), flush=True)
        raise


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    results=[]
    with fixture() as (origin,backend,*_):
        with sync_playwright() as playwright:
            browser=playwright.chromium.launch(**({'executable_path':os.environ['ULADIM_CHROMIUM']} if os.environ.get('ULADIM_CHROMIUM') else {}),headless=True,args=['--no-sandbox'])
            page=browser.new_page(viewport={'width':1440,'height':1100},device_scale_factor=1)
            errors=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            for path,selector in PAGES.items():
                visit_help(page,origin,path,selector,errors)
                expect(page.locator('h1')).to_have_count(1)
                assert page.locator('a:not([href]), button:not([type])').count()==0,path
                for width in (320,390,768,1440):
                    page.set_viewport_size({'width':width,'height':900})
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),(path,width)
                links=page.locator('main a[href]').evaluate_all('(links)=>links.map(a=>({href:a.getAttribute("href"),path:a.pathname,hash:a.hash}))')
                for link in links:
                    if link['href'].startswith('#'):
                        assert page.locator('[id="'+link['hash'][1:]+'"]').count(),(path,link)
                    elif link['href'].startswith('/'):
                        with urlopen(origin+link['path']) as response: assert response.status==200,(path,link)
                if path in ('/faq','/privacy','/download','/plans'):
                    page.set_viewport_size({'width':1440,'height':1100})
                    page.screenshot(path=str(OUT/(path[1:]+'-desktop.png')),full_page=True)
                    page.set_viewport_size({'width':390,'height':844})
                    page.screenshot(path=str(OUT/(path[1:]+'-phone.png')),full_page=True)
                results.append({'page':path,'widths':[320,390,768,1440],'links':len(links),'heading':True,'overflow':False})
            page.goto(origin+'/faq')
            search=page.get_by_label('О чём хотите узнать?')
            search.fill('удалить аккаунт')
            expect(page.locator('.help-question:visible')).to_have_count(2)
            expect(page.locator('#deletion')).to_have_attribute('open','')
            search.fill('definitely-no-answer')
            expect(page.locator('.help-empty')).to_be_visible()
            search.fill('')
            expect(page.locator('.help-question:visible')).to_have_count(21)
            summary=page.locator('#today summary');summary.focus();page.keyboard.press('Enter')
            expect(page.locator('#today')).to_have_attribute('open','')
            for anchor in ANCHORS:
                page.goto(origin+'/faq#'+anchor)
                expect(page.locator('#'+anchor)).to_have_attribute('open','')
            page.set_viewport_size({'width':390,'height':844})
            page.goto(origin+'/privacy')
            expect(page.locator('.help-draft')).to_be_visible()
            page.emulate_media(color_scheme='dark',reduced_motion='reduce')
            page.screenshot(path=str(OUT/'privacy-phone-dark.png'),full_page=True)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            # The legal/help escape path must survive a failed account service.
            page.route('**/account/api/config',lambda route:route.fulfill(status=503,body='temporarily unavailable'))
            for path in ('/faq','/privacy','/terms','/support','/delete-account','/download'):
                visit_help(page,origin,path,PAGES[path],errors)
                assert page.locator('h1').inner_text()!='Не удалось загрузить',path
            # Publication never follows from one filled operator field alone.
            # These independent scenarios must not exhaust production's per-IP
            # budget by visiting dozens of pages within one synthetic minute.
            next_window=int(backend.clock())+61
            backend.clock=lambda:next_window
            page.unroute('**/account/api/config')
            metadata={'published':True,'operatorName':'Synthetic fixture operator'}
            page.route('**/account/api/config',lambda route:route.fulfill(status=200,content_type='application/json',body=json.dumps({'public_legal':metadata})))
            page.goto(origin+'/terms');expect(page.locator('.help-draft')).to_be_visible()
            metadata.update({key:'Synthetic fixture fact' for key in ('operatorCountry','operatorPostalAddress','processingRegion','minimumAgePolicy','legalBasis','securityRetention','backupRetention','correspondenceRetention','deletionPolicy')})
            metadata['supportEmail']='invalid-mailbox'
            page.goto(origin+'/terms');expect(page.locator('.help-draft')).to_be_visible()
            metadata['supportEmail']='support@example.test'
            page.goto(origin+'/terms');expect(page.locator('.help-draft')).to_be_visible()
            metadata.update({key:True for key in ('supportEmailReady','processingVerified','privacyLifecycleReady','retentionVerified','agePolicyEnforced')})
            page.goto(origin+'/terms');expect(page.locator('.help-document')).to_be_visible();expect(page.locator('.help-draft')).to_have_count(0)
            assert 'будут окончательно указаны' not in page.locator('main').inner_text()
            page.goto(origin+'/support');expect(page.locator('a[href="mailto:support@example.test"]')).to_be_visible()
            assert not errors,errors
            results.append({'legal_metadata':'partial/invalid/unverified facts retain draft; complete verified synthetic facts publish; public support email shown'})
            results.append({'search':'match/empty/clear passed','keyboard':'native details Enter passed','context_anchors':len(ANCHORS),'config_outage':'six informational routes passed','page_errors':errors})
            browser.close()
    (OUT/'browser-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
    print(json.dumps(results,ensure_ascii=False))

if __name__=='__main__':main()
