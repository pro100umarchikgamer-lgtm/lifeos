import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const source=readFileSync('backend/webassets/app/app.js','utf8');
const start=source.indexOf('function refresh()');const code=source.slice(source.slice(start-6,start)==='async '?start-6:start,source.indexOf('async function start()'));
let release,reads=0,version=0;
const gate=new Promise(r=>release=r);
const context=vm.createContext({Promise,privateEpoch:0,refreshTail:Promise.resolve(),state:{busy:false,space:'personal',spaces:[],records:[]},call:async()=>({spaces:[{id:'personal'}]}),readSpace:async()=>{const captured=version;if(++reads===1)await gate;context.state.records=[captured];}});
vm.runInContext(code,context);
const first=context.refresh();await new Promise(r=>setTimeout(r,0));version=1;const followUp=context.refresh();release();await Promise.all([first,followUp]);
assert.equal(reads,2,'a post-write refresh must run after an in-flight stale read');
assert.equal(context.state.records[0],1,'the deleted record cannot return from a stale read');
console.log('REFRESH_SERIALIZATION_PASSED');

context.document={querySelectorAll:()=>[]};context.alerts={replaceChildren(){}};context.pendingDeletes=new Map();context.state.taskQuery='private query';context.state.taskStatus='done';
vm.runInContext(source.slice(source.indexOf('function clearIdentity()'),source.indexOf('function money(')),context);context.clearIdentity();assert.equal(context.state.taskQuery,'');assert.equal(context.state.taskStatus,'all');console.log('IDENTITY_SEARCH_RESET_PASSED');
