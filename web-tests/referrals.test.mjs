import {loadI18n} from './i18n-fixture.mjs';
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {JSDOM} from 'jsdom';
const source=fs.readFileSync(new URL('../backend/webassets/app/referrals.js',import.meta.url),'utf8');
function setup(url='https://getuladim.space/app'){
 const dom=new JSDOM('<body><main></main></body>',{url,runScripts:'outside-only'});loadI18n(dom.window);dom.window.eval(source);return {dom,w:dom.window,container:dom.window.document.querySelector('main')};
}
test('customer renders only nonclickable short names, never detailed private fields',async()=>{
 const {dom,w,container}=setup();
 await w.UladimReferrals.customer(container,{session:{verified:true},lang:'ru',request:async()=>({confirmed_count:1,invite:null,people:[{display_name:'Умар U.',email:'private@example.test',activity:'secret-active',purchase_converted:'secret-paid',invitee_id:'secret-id'}],next_offset:null})});
 assert.match(container.textContent,/Умар U\./);assert.equal(container.querySelectorAll('.referral-people a,.referral-people button').length,0);
 for(const secret of ['private@example.test','secret-active','secret-paid','secret-id'])assert.ok(!container.textContent.includes(secret));
 dom.window.close();
});
test('invitation query is only a marker; claim requires explicit verified-user action',async()=>{
 const code='A'.repeat(43),{dom,w,container}=setup('https://getuladim.space/app?setup=owner&ref='+code);let writes=0;
 w.UladimReferrals.captureInvite();assert.equal(new URL(w.location.href).searchParams.get('setup'),'owner');assert.equal(new URL(w.location.href).searchParams.has('ref'),false);
 const request=async(path,body)=>{assert.equal(path,'referrals/claim');assert.equal(body.code,code);writes++;return {status:'confirmed'};};
 assert.equal(w.UladimReferrals.invitation(container,{request,session:{verified:false},lang:'ru'}),null);assert.equal(writes,0);
 w.UladimReferrals.invitation(container,{request,session:{verified:true},lang:'ru'});assert.equal(writes,0);
 container.querySelector('button').click();await new Promise(resolve=>setTimeout(resolve,0));assert.equal(writes,1);assert.equal(w.UladimReferrals.pending(),null);dom.window.close();
});
test('ambiguous or malformed invitation parameters never become pending',()=>{
 for(const query of ['ref=short','ref='+('A'.repeat(43))+'&ref='+('B'.repeat(43))]){
  const {dom,w}=setup('https://getuladim.space/app?'+query);w.UladimReferrals.captureInvite();assert.equal(w.UladimReferrals.pending(),null);dom.window.close();
 }
});
