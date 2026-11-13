"""Bounded download-manifest acceptance using only local synthetic responses."""
import json, os
from pathlib import Path
from playwright.sync_api import sync_playwright, expect, Error
from tool.check_web_platform import fixture

OUT=Path(os.environ.get('ULADIM_DOWNLOAD_EVIDENCE','web_evidence/download-release'))
CERT='5fa37e4abf1ec90d5787bd0d7dc4cf0b3f49022172f9d25e91f4d8a76702a96e'
FALLBACK_SOURCE='84b0bdf2c6d54132691d22323553496f6b3b1d43'
FALLBACK_SHA='66d123cef79f85b7b2665bdcad0e6309db4a694e9a5076ed871450154c762872'
SOURCE='a'*40
NEXT={'source':SOURCE,'version_code':400001,'version_name':'0.4.0-test','bytes':81234567,
      'apk_url':'https://github.com/pro100umarchikgamer-lgtm/lifeos/releases/download/uladim-native-'+SOURCE[:12]+'/ULADIM.apk',
      'apk_sha256':'b'*64,'certificate_sha256':CERT}

def snapshot(page):
    return page.locator('.help-android-release').evaluate('''card=>({source:card.dataset.source,build:Number(card.dataset.versionCode),bytes:Number(card.dataset.apkBytes),sha:card.dataset.apkSha256,cert:card.dataset.certificateSha256,meta:card.querySelector('.help-download-meta').textContent,url:card.querySelector('[data-release-download]').href,release:card.querySelector('[data-release-notes]').href,digest:card.querySelector('.help-digest').textContent})''')

def assert_fallback(page):
    value=snapshot(page)
    assert value['source']==FALLBACK_SOURCE and value['build']==312001 and value['bytes']==77458893 and value['sha']==FALLBACK_SHA and value['digest']==FALLBACK_SHA,value
    assert value['cert']==CERT and 'Версия 0.3.1' in value['meta'] and '77,5 МБ' in value['meta'],value
    assert value['url'].endswith('/uladim-native-84b0bdf2c6d5/ULADIM.apk') and value['release'].endswith('/uladim-native-84b0bdf2c6d5'),value

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    results=[]
    with fixture() as (origin,*_):
        with sync_playwright() as playwright:
            browser=playwright.chromium.launch(executable_path=os.environ.get('ULADIM_CHROMIUM','/usr/bin/chromium'),headless=True,args=['--no-sandbox'])
            context=browser.new_context(viewport={'width':390,'height':844})
            page=context.new_page();errors=[];external=[];page.on('pageerror',lambda error:errors.append(str(error)))
            page.on('request',lambda request:external.append(request.url) if not request.url.startswith(origin+'/') else None)
            # Capture fetch arguments and every observed rendered tuple. A valid
            # response may only replace the old tuple with the complete new one.
            page.add_init_script('''window.releaseFetches=[];window.releaseSnapshots=[];
              const originalFetch=window.fetch;window.fetch=function(url,options){if(url==='/download/release.json')window.releaseFetches.push({url,method:options.method,credentials:options.credentials,cache:options.cache,redirect:options.redirect});return originalFetch.apply(this,arguments);};
              new MutationObserver(()=>{const card=document.querySelector('.help-android-release');if(card)window.releaseSnapshots.push({build:Number(card.dataset.versionCode),bytes:Number(card.dataset.apkBytes),sha:card.querySelector('.help-digest').textContent,url:card.querySelector('[data-release-download]').href});}).observe(document,{childList:true,subtree:true});''')
            state={'body':json.dumps(NEXT),'status':200,'content_type':'application/json'}
            def reply(route):
                if state.get('abort'):route.abort('failed')
                else:route.fulfill(status=state['status'],content_type=state['content_type'],body=state['body'],headers=state.get('headers',{}))
            page.route('**/download/release.json',reply)
            page.goto(origin+'/download')
            expect(page.locator('.help-android-release')).to_have_attribute('data-version-code','400001')
            value=snapshot(page)
            assert value['source']==SOURCE and value['bytes']==NEXT['bytes'] and value['sha']==NEXT['apk_sha256'] and value['digest']==NEXT['apk_sha256'] and value['cert']==CERT,value
            assert value['url']==NEXT['apk_url'] and value['release'].endswith('/uladim-native-'+SOURCE[:12]) and '0.4.0-test' in value['meta'] and '81,2 МБ' in value['meta'],value
            for item in page.evaluate('window.releaseSnapshots'):
                assert (item['build'],item['bytes'],item['sha']) in [(312001,77458893,FALLBACK_SHA),(400001,NEXT['bytes'],NEXT['apk_sha256'])],item
            assert page.evaluate('window.releaseFetches')==[{'url':'/download/release.json','method':'GET','credentials':'omit','cache':'no-store','redirect':'error'}]
            page.screenshot(path=str(OUT/'download-next-phone.png'),full_page=True)
            results.append({'valid':'all immutable fields replaced together','fetch':'same-origin GET, omit credentials, no-store, redirect error'})
            # Missing cosmetic versionName never reuses the old version or size.
            for name in (None,''):
                state['body']=json.dumps({**NEXT,'version_name':name})
                page.goto(origin+'/download');expect(page.locator('.help-android-release')).to_have_attribute('data-version-code','400001')
                value=snapshot(page);assert value['meta'].startswith('Android · сборка 400001') and '0.3.1' not in value['meta'] and value['bytes']==NEXT['bytes'],value
            results.append({'missing_name':'explicit Android/build display, verified new bytes and links'})
            state['body']=json.dumps({**NEXT,'version_name':'<img src=x onerror=window.injected=true>'})
            page.goto(origin+'/download');expect(page.locator('.help-android-release')).to_have_attribute('data-version-code','400001')
            assert '<img src=x' in snapshot(page)['meta'] and page.locator('.help-android-release img').count()==0 and page.evaluate('typeof window.injected')=='undefined'
            results.append({'text_safety':'manifest version renders only as plain text'})
            invalid=[
                ('external_url',{'apk_url':'https://example.test/ULADIM.apk'}),
                ('github_other_repo',{'apk_url':NEXT['apk_url'].replace('/lifeos/','/other/')}),
                ('github_query',{'apk_url':NEXT['apk_url']+'?download=1'}),
                ('github_source_mismatch',{'source':'c'*40}),
                ('source_not_full',{'source':SOURCE[:12]}),
                ('wrong_certificate',{'certificate_sha256':'0'*64}),
                ('malformed_digest',{'apk_sha256':'not-a-digest'}),
                ('old_version',{'version_code':312000}),
                ('fractional_bytes',{'bytes':123.5}),
                ('zero_bytes',{'bytes':0}),
                ('invalid_name_type',{'version_name':12}),
                ('unexpected_key',{'extra':'ignored?'}),
            ]
            for label,change in invalid:
                state['body']=json.dumps({**NEXT,**change})
                page.goto(origin+'/download');page.wait_for_selector('.help-android-release')
                page.wait_for_function('window.releaseFetches.length===1');page.wait_for_timeout(40)
                assert_fallback(page);results.append({'invalid':label,'fallback':312001})
            for label,change in [('service_503',{'status':503}),('malformed_json',{'body':'{'}),('wrong_content_type',{'content_type':'text/html'}),('offline',{'abort':True}),('redirect',{'status':302,'headers':{'Location':'https://example.test/release.json'}})]:
                state.update(body=json.dumps(NEXT),status=200,content_type='application/json',abort=False,headers={});state.update(change)
                page.goto(origin+'/download');page.wait_for_selector('.help-android-release');page.wait_for_timeout(40);assert_fallback(page);results.append({'unavailable':label,'fallback':312001})
            # A delayed response may not overwrite a new public route.
            page.unroute('**/download/release.json');pending=[]
            page.route('**/download/release.json',lambda route:pending.append(route))
            page.goto(origin+'/download');page.wait_for_function('window.releaseFetches.length===1')
            page.evaluate("history.pushState({},'', '/faq'); publicPage({});")
            expect(page.locator('.help-question')).to_have_count(21)
            pending.pop().fulfill(status=200,content_type='application/json',body=json.dumps(NEXT))
            page.wait_for_timeout(60);assert page.locator('.help-android-release').count()==0
            expect(page.locator('h1')).to_have_text('Найдём ответ');results.append({'late_response':'cannot overwrite navigated FAQ'})
            # The time limit aborts a stalled manifest while the fallback remains
            # usable throughout; no metadata is applied after the deadline.
            page.goto(origin+'/download');page.wait_for_function('window.releaseFetches.length===1')
            page.wait_for_timeout(2700);assert_fallback(page)
            for route in pending:
                try:route.abort()
                except Error:pass
            pending.clear();page.unroute('**/download/release.json');results.append({'timeout_ms':2500,'fallback':312001})
            page.route('**/account/api/config',lambda route:route.fulfill(status=503,body='unavailable'))
            page.goto(origin+'/privacy');expect(page.locator('.help-document')).to_be_visible();assert page.evaluate('window.releaseFetches.length')==0
            assert not errors,errors;assert not external,external;results.append({'external_requests':external});results.append({'config_outage':'public privacy loads; no manifest request outside download','page_errors':errors})
            browser.close()
    (OUT/'browser-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
    print(json.dumps(results,ensure_ascii=False))

if __name__=='__main__':main()
