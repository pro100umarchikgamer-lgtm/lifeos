import {loadI18n} from './i18n-fixture.mjs';
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {JSDOM} from 'jsdom';
const source=fs.readFileSync(new URL('../backend/webassets/app/record-erasure.js',import.meta.url),'utf8');
const record={id:'11111111-1111-4111-8111-111111111111',owner_id:'owner',workspace_id:'space',deleted:true,revision:2,consent_hash:'a'.repeat(64)};
const settle=()=>new Promise(resolve=>setTimeout(resolve,0));
function setup(request){
 const dom=new JSDOM('<body><article></article></body>',{url:'https://getuladim.space/app',runScripts:'outside-only'}),w=dom.window,panel=w.document.querySelector('article');loadI18n(w);w.eval(source);
 const E=(tag,text,cls)=>{const e=w.document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
 const append=(p,...items)=>p.append(...items);
 const button=(text,fn,cls)=>{const b=E('button',text,cls);b.type='button';b.addEventListener('click',fn);return b;};
 let current=true,completed=0;
 w.UladimRecordErasure.attach(panel,{record,language:()=> 'en',request,E,append,button,isCurrent:()=>current,onErased:()=>{completed++;}});
 return {dom,w,panel,get completed(){return completed;},leave(){current=false;}};
}
function preview(extra={}){return {record:{...record},permanent_delete_available:true,pending_operation_id:null,...extra};}
async function review(f){f.panel.querySelector('details').open=true;f.panel.querySelector('button').click();await settle();}
async function confirm(f){const check=f.panel.querySelector('input');check.checked=true;check.dispatchEvent(new f.w.Event('change'));f.panel.querySelector('form').dispatchEvent(new f.w.Event('submit',{bubbles:true,cancelable:true}));await settle();}
test('folded destructive action requires separate preview and checked consent; only exact accepted receipt completes',async()=>{
 const calls=[];const f=setup(async(path,body)=>{calls.push({path,body});return body?{id:body.operation_id,record_id:record.id,status:'accepted',erased:true}:preview();});
 assert.equal(f.panel.querySelector('details').open,false);assert.equal(calls.length,0);await review(f);
 assert.equal(calls.length,1);assert.equal(f.panel.querySelector('[type=submit]').disabled,true);assert.equal(f.completed,0);
 await confirm(f);assert.equal(calls.length,2);assert.equal(calls[1].body.consent_hash,record.consent_hash);assert.equal(f.completed,1);assert.match(f.panel.textContent,/Record permanently deleted/);f.dom.window.close();
});
test('changed preview cannot consent to unseen content; unavailable durability has no submit',async()=>{
 for(const response of [preview({record:{...record,revision:3}}),preview({record:{...record,consent_hash:'b'.repeat(64)}}),preview({permanent_delete_available:false})]){
  let posts=0;const f=setup(async(path,body)=>{if(body)posts++;return response;});await review(f);assert.equal(f.panel.querySelector('form'),null);assert.equal(posts,0);assert.equal(f.completed,0);f.dom.window.close();
 }
});
test('lost reply preserves operation identity; checking durable erased state does not post twice',async()=>{
 let phase=0,operation,posts=0;const f=setup(async(path,body)=>{
  if(body){posts++;operation=body.operation_id;phase=1;throw {code:'offline'};}
  return phase?{erased:true,record_id:record.id,permanent_delete_available:true,pending_operation_id:null}:preview();
 });
 await review(f);await confirm(f);assert.equal(f.completed,0);assert.match(f.panel.textContent,/not confirmed/);await review(f);assert.equal(posts,1);assert.ok(operation);assert.equal(f.completed,1);f.dom.window.close();
});
test('pending durable intent retries the same operation after failed acknowledgment',async()=>{
 let operation,posts=0;const f=setup(async(path,body)=>{
  if(!body)return preview({pending_operation_id:operation||null});
  posts++;if(!operation){operation=body.operation_id;throw {code:'record_erasure_unavailable'};}
  assert.equal(body.operation_id,operation);return {id:operation,record_id:record.id,status:'accepted',erased:true};
 });await review(f);await confirm(f);assert.equal(f.completed,0);await review(f);await confirm(f);assert.equal(posts,2);assert.equal(f.completed,1);f.dom.window.close();
});
test('late preview after account navigation cannot expose consent or post',async()=>{
 let resolve;const f=setup(()=>new Promise(r=>{resolve=r;}));f.panel.querySelector('button').click();f.leave();resolve(preview());await settle();assert.equal(f.panel.querySelector('form'),null);assert.equal(f.completed,0);f.dom.window.close();
});
