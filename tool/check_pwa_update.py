"""Real Service Worker update lifecycle on copied assets and a disposable backend."""
import json, re, shutil, tempfile
from pathlib import Path
from time import monotonic, sleep
from unittest.mock import patch
from playwright.sync_api import sync_playwright, expect
from tool.check_web_platform import fixture, login

OUT=Path('web_evidence/pwa-update')

def wait_for_worker_state(page, predicate, *, argument=None):
    deadline = monotonic() + 15
    while monotonic() < deadline:
        if page.evaluate(predicate, argument):
            return
        sleep(.1)
    raise AssertionError(f'Service worker did not reach the expected state: {predicate}')

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as folder:
        assets=Path(folder)/'webassets';shutil.copytree('backend/webassets',assets)
        worker=assets/'app/sw.js';source=worker.read_text();match=re.search(r"const CACHE='([^']+)'",source)
        assert match,"Expected sw.js to declare const CACHE='cache-name'"
        old=match[1];new=old+'-update-test'
        with patch('backend.web.ASSETS',assets),fixture() as (origin,backend,actor,wid),sync_playwright() as p:
            browser=p.chromium.launch();context=browser.new_context();page=context.new_page()
            login(page,origin)
            page.evaluate('navigator.serviceWorker.ready.then(()=>true)')
            page.wait_for_function('Boolean(navigator.serviceWorker.controller)')
            page.evaluate('globalThis.originalWorker=navigator.serviceWorker.controller')
            worker.write_text(source.replace(old,new))
            page.evaluate('navigator.serviceWorker.getRegistration().then(r=>r.update())')
            wait_for_worker_state(page, '() => navigator.serviceWorker.getRegistration().then(r => r.waiting?.state === "installed")')
            assert page.evaluate('navigator.serviceWorker.controller===originalWorker'),'update took over active client'
            expect(page.get_by_role('heading',name='Сегодня',exact=True)).to_be_visible()
            page.screenshot(path=str(OUT/'update-waiting.png'))
            page.close()  # The update may activate only after the last old client leaves.
            page=context.new_page();page.goto(origin+'/app')
            expect(page.get_by_role('heading',name='Сегодня',exact=True)).to_be_visible()
            wait_for_worker_state(page, '([old, next]) => caches.keys().then(keys => keys.includes(next) && !keys.includes(old))',
                                  argument=[old, new])
            keys=page.evaluate('caches.keys()');assert new in keys and old not in keys,keys
            urls=page.evaluate('async()=>{const rows=[];for(const key of await caches.keys())for(const r of await(await caches.open(key)).keys())rows.push(new URL(r.url).pathname);return rows}')
            assert not any('/api/' in url for url in urls),urls
            assert backend.pull(actor,wid,0)['records'],'server data lost across shell update'
            page.screenshot(path=str(OUT/'update-active.png'))
            context.close();browser.close()
    (OUT/'RESULT.json').write_text(json.dumps({'result':'passed','active_client_takeover':False,'session_and_server_data_preserved':True,'private_responses_cached':False},indent=2)+'\n')
    print('PWA_UPDATE_PASSED: update waits, old shell removed, session and server data preserved')
if __name__=='__main__':main()
