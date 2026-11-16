import {describe,it,expect} from 'vitest';
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
  expect(api.state.tab).toBe('money');expect(api.state.referenceSection).toBe('ledger');expect(new URL(w.location.href).searchParams.get('selectedspace')).toBe(wid);
  api.state.space=cid;expect(api.write).toBeTypeOf('function');api.write();expect(new URL(w.location.href).searchParams.has('selectedspace')).toBe(false);
 });
 it('preserves higher-priority owner recovery and security routes over a saved section',async()=>{
  for(const section of ['security','deletion','recovery']){const {w,api}=fixture('?view=money&section=ledger&settings='+section+(section==='recovery'?'&case='+cid:''));api.stub();await api.start();expect(api.state.tab).toBe('account');expect(api.state.settingsTab).toBe(section);if(section==='recovery'){expect(api.state.recoveryCaseId).toBe(cid);expect(w.location.search).toContain('case='+cid);}}
 });
 it('rejects unknown or duplicate route values and never writes session or record data',()=>{
  const {w,api}=fixture('?view=money&view=account&section=unknown&selectedspace=bad');expect(api.read).toBeTypeOf('function');expect(api.read()).toMatchObject({tab:'today',section:'',space:null});
  Object.assign(api.state,{session:{user_id:'secret-user',csrf:'secret-token'},spaces:[{id:wid}],space:wid,tab:'notes',records:[{data:{title:'private-record'}}]});api.write();expect(w.location.search).toContain('view=notes');expect(w.location.href).not.toMatch(/secret|private-record|csrf/);
 });
 it('uses the owner setup link once, then preserves an explicit Calendar navigation on refresh',async()=>{
  const {w,api}=fixture('?setup=owner');api.stub();await api.start();expect(api.state.tab).toBe('account');expect(api.state.settingsTab).toBe('profile');expect(w.location.search).toContain('setup=owner');api.navigate('calendar');expect(w.location.search).not.toContain('setup=');await api.start();expect(api.state.tab).toBe('calendar');
 });
});
describe('current-session interface flags',()=>{
 it('uses assigned activity and the documented defaults without a flags request',()=>{
  const {api}=fixture();expect(api.flag).toBeTypeOf('function');expect([api.flag('compact_onboarding'),api.flag('support_entry'),api.flag('chart_styles')]).toEqual([false,false,true]);
  api.state.session={interface_flags:{compact_onboarding:{enabled:true,active:true},support_entry:{enabled:true,active:false},chart_styles:{enabled:false,active:false}}};expect([api.flag('compact_onboarding'),api.flag('support_entry'),api.flag('chart_styles')]).toEqual([true,false,false]);
 });
});
describe('Web feedback localization packet',()=>{
 it('resolves every new label in all 16 locales through the real i18n loader',async()=>{
  const packet=JSON.parse(readFileSync(new URL('../delivery/control-feedback-nov16/web-feedback-copy.json',import.meta.url),'utf8')),dom=new JSDOM('',{url:'https://example.test',runScripts:'outside-only'}),w=dom.window,api=loadI18n(w);
  w.fetch=async()=>({ok:true,json:async()=>({schemaVersion:1,groups:{},...packet})});expect(await api.load({})).toBe(true);
  expect(Object.keys(packet.translations)).toHaveLength(16);for(const locale of api.languages){api.setLanguage(locale);for(const key of packet.required)expect(api.text(key)).toBe(packet.translations[locale][key]);}
 });
});
