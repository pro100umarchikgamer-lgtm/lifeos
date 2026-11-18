import {loadI18n} from './i18n-fixture.mjs';
import assert from 'node:assert/strict';
import {describe, it, mock} from 'node:test';
import {isDeepStrictEqual} from 'node:util';
import {JSDOM} from 'jsdom';
import {readFileSync} from 'node:fs';
const source=readFileSync(new URL('../backend/webassets/app/layout-order.js',import.meta.url),'utf8');
function fixture(order=[]){
 const dom=new JSDOM('<body><section id="rows"></section></body>',{runScripts:'outside-only'}),window=dom.window;
 loadI18n(window);window.eval(source);const container=window.document.querySelector('#rows');
 const E=(tag,text,classes)=>{const el=window.document.createElement(tag);if(text!==undefined)el.textContent=text;if(classes)el.className=classes;return el;};
 const items=['a','b','c'].map(id=>{const element=E('article',id);element.dataset.record=id;container.append(element);return{id,label:'Account '+id,element};});
 const onSave=mock.fn(async () => {});
 const mount=()=>window.UladimLayoutOrder.mountOrderControls({container,items,kind:'account',order,onSave,E,lang:'en'});
 const ids=()=>[...container.querySelectorAll('article')].map(el=>el.dataset.record);
 const flush=()=>new Promise(resolve=>setTimeout(resolve,0));
 return {window,api:window.UladimLayoutOrder,container,items,onSave,mount,ids,flush};
}
describe('personal account and budget order',()=>{
 it('keeps default order and appends new records while ignoring stale or duplicate saved IDs',()=>{
  const f=fixture(),records=f.items.slice();
  assert.deepEqual(f.api.orderRecords(records,[]), records);
  assert.deepEqual(f.api.orderRecords(records,['missing','b','b']), [records[1],records[0],records[2]]);
  assert.deepEqual(records, f.items);
 });
 it('requires explicit order mode and saves opaque IDs before moving the existing rows',async()=>{
  const f=fixture(['b','a']);let acknowledge;f.onSave.mock.mockImplementation(() => new Promise(resolve => { acknowledge = resolve; }));
  const controller=f.mount();assert.deepEqual(f.ids(), ['b','a','c']);
  const controls=f.items[0].element.querySelector('.layout-order-controls');assert.equal(controls.hidden, true);
  const toggle=f.container.querySelector('.layout-order-toggle');toggle.click();assert.equal(toggle.getAttribute('aria-pressed'), 'true');
  const firstUp=f.items[1].element.querySelector('button');assert.equal(firstUp.disabled, true);
  const up=f.items[0].element.querySelector('button');assert.ok(up.textContent.includes('Up'));assert.ok(up.getAttribute('aria-label').includes('Account a'));
  up.click();assert.ok(f.onSave.mock.calls.some(({arguments: args}) =>
   isDeepStrictEqual(structuredClone(args), [['a','b','c']])
  ));assert.deepEqual(f.ids(), ['b','a','c']);
  assert.equal(toggle.disabled, true);acknowledge();await f.flush();
  assert.deepEqual(f.ids(), ['a','b','c']);assert.deepEqual(controller.getOrder(), ['a','b','c']);
  assert.equal(f.items[0].element, f.container.querySelector('article'));
  toggle.click();assert.equal(controls.hidden, true);assert.equal(toggle.textContent, 'Order');
 });
 it('keeps the old order on a rejected save and removes only helper controls on destroy',async()=>{
  const f=fixture();f.onSave.mock.mockImplementation(async () => { throw new Error('conflict'); });const controller=f.mount();
  f.container.querySelector('.layout-order-toggle').click();f.items[1].element.querySelector('button').click();await f.flush();
  assert.deepEqual(f.ids(), ['a','b','c']);assert.ok(f.container.querySelector('[role=status]').textContent.includes('Could not save'));
  controller.destroy();assert.deepEqual(f.ids(), ['a','b','c']);assert.equal(f.container.querySelector('.layout-order-toolbar'), null);
  assert.equal(f.container.querySelector('.layout-order-controls'), null);
 });
});
