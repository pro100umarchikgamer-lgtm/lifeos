import {describe,it,expect} from 'vitest';
import {JSDOM} from 'jsdom';
import {readFileSync} from 'node:fs';
import {loadI18n} from './i18n-fixture.mjs';
const source=readFileSync(new URL('../backend/webassets/app/recovery.js',import.meta.url),'utf8');
const actor='11111111-1111-4111-8111-111111111111',cid='22222222-2222-4222-8222-222222222222';
const settle=async()=>{for(let i=0;i<8;i++)await Promise.resolve();};
function fixture({wrong=false,denied=false,pending=false}={}){
 const dom=new JSDOM('<main><section id="recovery"></section></main>',{url:'https://example.test/app?settings=recovery&case='+cid,runScripts:'outside-only'}),w=dom.window;loadI18n(w);w.eval(source);
 const state={session:{user_id:actor,verified:true,record_recovery_available:true},spaces:[{id:actor,name:'Private'}],space:actor,records:[],lang:'en',tab:'account',settingsTab:'recovery',recoveryCaseId:cid};
 const calls=[],E=(tag,text,classes)=>{const node=w.document.createElement(tag);if(text!==undefined)node.textContent=text;if(classes)node.className=classes;return node;},append=(node,...items)=>{node.append(...items);return node;},button=(text,action,classes)=>{const node=E('button',text,classes);node.type='button';node.addEventListener('click',action);return node;};
 let release;const detail={case:{id:cid,target_user_id:wrong?'other':actor,kind:'records',state:'waiting_owner',revision:1,expires_at:Math.floor(Date.now()/1000)+3600},target:{id:wrong?'other':actor,email:'owner@example.test'},source:{kind:'ticket',author_user_id:'must-not-render'},requests:[]};
 const request=async(path,body)=>{calls.push({path,body});if(path.startsWith('trash?'))return {records:[]};if(path==='recovery/requests')return {requests:[]};if(path==='recovery-cases')return {cases:[detail.case]};if(path.startsWith('recovery-case?')){if(denied)throw {status:404,code:'not_found'};return detail;}if(path==='recovery-cases/confirm'){if(pending)await new Promise(resolve=>{release=resolve;});return {...detail,case:{...detail.case,state:'confirmed',revision:2}};}throw Error(path);};
 const api=w.UladimRecovery.create({state,epoch:()=>1,request,E,append,button,icon:()=>E('span'),report:()=>{},refresh:async()=>{},money:()=>''}),host=w.document.querySelector('#recovery');api.page(host);
 return {w,state,calls,api,host,release:()=>release?.()};
}
describe('original-owner assistance cases',()=>{
 it('confirms the original account separately from per-record recovery consent',async()=>{
  const f=fixture();await settle();const confirm=[...f.host.querySelectorAll('button')].find(node=>node.textContent==='Confirm my original account');expect(confirm).toBeTruthy();confirm.click();await settle();
  expect(f.calls.filter(call=>call.body)).toEqual([{path:'recovery-cases/confirm',body:{id:cid,revision:1}}]);expect(f.host.textContent).toContain('Original account confirmed');expect(f.host.textContent).toContain('separate recovery request');expect(f.host.textContent).not.toContain('must-not-render');
 });
 it('treats a wrong account or a 404 as unavailable without exposing target identity',async()=>{
  for(const options of [{wrong:true},{denied:true}]){const f=fixture(options);await settle();expect(f.host.textContent).toContain('unavailable for this account');expect(f.host.textContent).not.toContain('owner@example.test');expect(f.host.textContent).not.toContain('Confirm my original account');expect(f.calls.some(call=>call.body)).toBe(false);}
 });
 it('locks confirmation while pending and discards a response after leaving the account',async()=>{
  const f=fixture({pending:true});await settle();const confirm=[...f.host.querySelectorAll('button')].find(node=>node.textContent==='Confirm my original account');expect(confirm).toBeTruthy();confirm.click();confirm.click();await settle();expect(f.calls.filter(call=>call.path==='recovery-cases/confirm')).toHaveLength(1);expect(f.host.querySelector('.recovery-case-confirm')?.disabled).toBe(true);f.api.clear();f.host.replaceChildren();f.release();await settle();expect(f.host.textContent).toBe('');
 });
});
