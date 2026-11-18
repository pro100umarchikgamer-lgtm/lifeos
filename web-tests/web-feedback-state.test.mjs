import assert from 'node:assert/strict';
import {describe, it} from 'node:test';
import {JSDOM} from 'jsdom';
import {readFileSync} from 'node:fs';
import {loadI18n} from './i18n-fixture.mjs';
const source=readFileSync(new URL('../backend/webassets/app/app.js',import.meta.url),'utf8').replace(/^\(async\(\)=>\{try\{packs=.*$/m,'').replace(/^setInterval\(.*$/m,'');
const wid='11111111-1111-4111-8111-111111111111',cid='22222222-2222-4222-8222-222222222222';
function fixture(search=''){
 const dom=new JSDOM('<body><div id="root"></div><div id="alerts"></div></body>',{url:'https://example.test/app'+search,runScripts:'outside-only',pretendToBeVisual:true}),w=dom.window;
 loadI18n(w);w.eval(source+`;globalThis.testApp={state,read:typeof readWorkspaceRoute==='function'?readWorkspaceRoute:null,write:typeof writeWorkspaceRoute==='function'?writeWorkspaceRoute:null,flag:typeof interfaceFlag==='function'?interfaceFlag:null,start,navigate:referenceNavigate,stub(){call=async()=>({user_id:'actor',csrf:'safe'});refresh=async preferred=>{state.spaces=[{id:'${wid}'}];state.space=preferred==='${wid}'?preferred:'${wid}';};render=()=>{if(typeof writeWorkspaceRoute==='function')writeWorkspaceRoute();};consumeNotificationLink=async()=>null;inboxCenter=()=>({refresh(){}});refreshNotificationTimezone=()=>{};}};`);
 w.scrollTo=()=>{};return {w,api:w.testApp};
}
describe('authenticated refresh route',()=>{
 it('restores a whitelisted section and writes only an authorized selected workspace',async()=>{
  const {w,api}=fixture('?view=money&section=ledger&selectedspace='+wid);api.stub();await api.start();
  assert.equal(api.state.tab, 'money');assert.equal(api.state.referenceSection, 'ledger');assert.equal(new URL(w.location.href).searchParams.get('selectedspace'), wid);
  api.state.space=cid;assert.equal(typeof api.write, 'function');api.write();assert.equal(new URL(w.location.href).searchParams.has('selectedspace'), false);
 });
 it('preserves higher-priority owner recovery and security routes over a saved section',async()=>{
  for(const section of ['security','deletion','recovery']){const {w,api}=fixture('?view=money&section=ledger&settings='+section+(section==='recovery'?'&case='+cid:''));api.stub();await api.start();assert.equal(api.state.tab, 'account');assert.equal(api.state.settingsTab, section);if(section==='recovery'){assert.equal(api.state.recoveryCaseId, cid);assert.ok(w.location.search.includes('case='+cid));}}
 });
 it('rejects unknown or duplicate route values and never writes session or record data',()=>{
  const {w,api}=fixture('?view=money&view=account&section=unknown&selectedspace=bad');assert.equal(typeof api.read, 'function');assert.partialDeepStrictEqual(api.read(), {tab:'today',section:'',space:null});
  Object.assign(api.state,{session:{user_id:'secret-user',csrf:'secret-token'},spaces:[{id:wid}],space:wid,tab:'notes',records:[{data:{title:'private-record'}}]});api.write();assert.ok(w.location.search.includes('view=notes'));assert.doesNotMatch(w.location.href, /secret|private-record|csrf/);
 });
 it('uses the owner setup link once, then preserves an explicit Calendar navigation on refresh',async()=>{
  const {w,api}=fixture('?setup=owner');api.stub();await api.start();assert.equal(api.state.tab, 'account');assert.equal(api.state.settingsTab, 'profile');assert.ok(w.location.search.includes('setup=owner'));api.navigate('calendar');assert.equal(w.location.search.includes('setup='), false);await api.start();assert.equal(api.state.tab, 'calendar');
 });
});
describe('current-session interface flags',()=>{
 it('uses assigned activity and the documented defaults without a flags request',()=>{
  const {api}=fixture();assert.equal(typeof api.flag, 'function');assert.deepEqual([api.flag('compact_onboarding'),api.flag('support_entry'),api.flag('chart_styles')], [false,false,true]);
  api.state.session={interface_flags:{compact_onboarding:{enabled:true,active:true},support_entry:{enabled:true,active:false},chart_styles:{enabled:false,active:false}}};assert.deepEqual([api.flag('compact_onboarding'),api.flag('support_entry'),api.flag('chart_styles')], [true,false,false]);
 });
});
describe('Web feedback bundled localization',()=>{
 it('resolves every new label in all 16 locales through the real i18n loader',async()=>{
  const catalog=JSON.parse(readFileSync(new URL('../backend/webassets/app/translations.json',import.meta.url),'utf8')),dom=new JSDOM('',{url:'https://example.test',runScripts:'outside-only'}),w=dom.window,api=loadI18n(w);
  const keys=Object.keys(catalog.source).filter(key=>key.startsWith('web_feedback_'));assert.equal(keys.length, 18);
  w.fetch=async()=>({ok:true,json:async()=>catalog});assert.equal(await api.load({}), true);
  assert.equal(catalog.languages.length, 16);for(const locale of api.languages){const reviewed=JSON.parse(readFileSync(new URL('../assets/web-locales/'+locale+'.json',import.meta.url),'utf8')).strings;api.setLanguage(locale);for(const key of keys)assert.equal(api.text(key), reviewed[key]);}
 });
});
