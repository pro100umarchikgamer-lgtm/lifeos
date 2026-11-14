"""A late note save cannot restore a draft erased by an in-flight privacy delta.
Synthetic tombstone/reply, actual app editor and local WSGI auth. No real erasure.
Set ULADIM_WEB_ASSETS_ROOT only to review another checkout's actual UI bytes.
"""
from pathlib import Path
import json,os
from playwright.sync_api import sync_playwright,expect
from tool.check_web_platform import fixture,login
from backend import web as web_assets


def main():
 original=web_assets.ASSETS;assets=Path(os.environ.get('ULADIM_WEB_ASSETS_ROOT',str(original))).resolve();source=(assets/'app/app.js').read_text();checks=[]
 web_assets.ASSETS=assets
 try:
  with fixture() as (origin,backend,actor,wid),sync_playwright() as p:
   browser=p.chromium.launch(**({'executable_path':os.environ['ULADIM_CHROMIUM']} if os.environ.get('ULADIM_CHROMIUM') else {}))
   for outcome in ['rejected','accepted']:
    context=browser.new_context(viewport={'width':390,'height':844},service_workers='block',reduced_motion='reduce');page=context.new_page();errors=[];page.on('pageerror',lambda error:errors.append(str(error)));held=[];inject={'value':False};marker={}
    # Freeze the reviewed app bytes while independent integration continues.
    page.route('**/app/assets/app.js',lambda route:route.fulfill(body=source,content_type='text/javascript'))
    def asset(name):
     def serve(route):route.fulfill(path=str(assets/'app'/name),content_type='text/javascript' if name.endswith('.js') else 'text/css')
     return serve
    for name in ['inbox.js','inbox.css','recovery.js','recovery.css','account-deletion.js','account-deletion.css']:page.route('**/app/assets/'+name,asset(name))
    def sync(route):
     if route.request.method=='POST':held.append(route);return
     if not inject['value']:route.continue_();return
     response=route.fetch();result=response.json();cursor=int(result['cursor'])+1;result.update(records=[{**marker,'seq':cursor}],cursor=cursor,more=False,reset=False);route.fulfill(response=response,json=result)
    page.route('**/account/api/sync**',sync);login(page,origin);page.evaluate("referenceNavigate('notes')");page.locator('.note-card').filter(has_text='Планы на выходные').get_by_role('button').click();editor=page.locator('dialog[open]');body=editor.locator('textarea[name=body]');body.fill('Privacy-erased held save must not survive');editor.get_by_role('button',name='Сохранить',exact=True).click()
    for attempt in range(100):
     if held:break
     page.wait_for_timeout(10)
    assert held,'note write did not start before privacy delta';operation=held[0].request.post_data_json['operations'][0];rid=operation['record_id'];key='uladim-note-draft:'+actor['id']+':'+wid+':'+rid;assert page.evaluate('key=>sessionStorage.getItem(key)!==null',key)
    marker.update(id=rid,workspace_id=wid,owner_id=actor['id'],kind='note',visibility='private',audience=[],revision=operation['revision']+1,deleted=1,privacy_erased=True,data={},editable=False);inject['value']=True;page.evaluate('refresh()');expect(page.locator('dialog[open]')).to_have_count(0);assert not page.evaluate('key=>sessionStorage.getItem(key)!==null',key)
    if outcome=='rejected':held[0].fulfill(status=403,json={'error':'invalid_record'})
    else:held[0].fulfill(json={'results':[{'id':operation['id'],'status':'accepted'}]})
    page.wait_for_timeout(150);assert not page.evaluate('key=>sessionStorage.getItem(key)!==null',key);expect(page.locator('dialog[open]')).to_have_count(0);assert not errors,errors;checks.append('privacy_tombstone_keeps_note_draft_absent_after_late_'+outcome+'_save');context.close()
   browser.close()
 finally:web_assets.ASSETS=original
 print(json.dumps({'checks':checks,'scope':'Actual reviewed app editor with local auth; synthetic privacy delta and held save response, no real user erasure.'}))
if __name__=='__main__':main()
