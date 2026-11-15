import {loadI18n} from './i18n-fixture.mjs';
import {describe,it,expect,vi} from 'vitest';
import {JSDOM} from 'jsdom';
import {readFileSync} from 'node:fs';
const source=readFileSync(new URL('../backend/webassets/app/layout-order.js',import.meta.url),'utf8');
function fixture(order=[]){
 const dom=new JSDOM('<body><section id="rows"></section></body>',{runScripts:'outside-only'}),window=dom.window;
 loadI18n(window);window.eval(source);const container=window.document.querySelector('#rows');
 const E=(tag,text,classes)=>{const el=window.document.createElement(tag);if(text!==undefined)el.textContent=text;if(classes)el.className=classes;return el;};
 const items=['a','b','c'].map(id=>{const element=E('article',id);element.dataset.record=id;container.append(element);return{id,label:'Account '+id,element};});
 const onSave=vi.fn().mockResolvedValue(undefined);
 const mount=()=>window.UladimLayoutOrder.mountOrderControls({container,items,kind:'account',order,onSave,E,lang:'en'});
 const ids=()=>[...container.querySelectorAll('article')].map(el=>el.dataset.record);
 const flush=()=>new Promise(resolve=>setTimeout(resolve,0));
 return {window,api:window.UladimLayoutOrder,container,items,onSave,mount,ids,flush};
}
describe('personal account and budget order',()=>{
 it('keeps default order and appends new records while ignoring stale or duplicate saved IDs',()=>{
  const f=fixture(),records=f.items.slice();
  expect(f.api.orderRecords(records,[])).toEqual(records);
  expect(f.api.orderRecords(records,['missing','b','b'])).toEqual([records[1],records[0],records[2]]);
  expect(records).toEqual(f.items);
 });
 it('requires explicit order mode and saves opaque IDs before moving the existing rows',async()=>{
  const f=fixture(['b','a']);let acknowledge;f.onSave.mockImplementation(()=>new Promise(resolve=>acknowledge=resolve));
  const controller=f.mount();expect(f.ids()).toEqual(['b','a','c']);
  const controls=f.items[0].element.querySelector('.layout-order-controls');expect(controls.hidden).toBe(true);
  const toggle=f.container.querySelector('.layout-order-toggle');toggle.click();expect(toggle.getAttribute('aria-pressed')).toBe('true');
  const firstUp=f.items[1].element.querySelector('button');expect(firstUp.disabled).toBe(true);
  const up=f.items[0].element.querySelector('button');expect(up.textContent).toContain('Up');expect(up.getAttribute('aria-label')).toContain('Account a');
  up.click();expect(f.onSave).toHaveBeenCalledWith(['a','b','c']);expect(f.ids()).toEqual(['b','a','c']);
  expect(toggle.disabled).toBe(true);acknowledge();await f.flush();
  expect(f.ids()).toEqual(['a','b','c']);expect(controller.getOrder()).toEqual(['a','b','c']);
  expect(f.items[0].element).toBe(f.container.querySelector('article'));
  toggle.click();expect(controls.hidden).toBe(true);expect(toggle.textContent).toBe('Order');
 });
 it('keeps the old order on a rejected save and removes only helper controls on destroy',async()=>{
  const f=fixture();f.onSave.mockRejectedValue(new Error('conflict'));const controller=f.mount();
  f.container.querySelector('.layout-order-toggle').click();f.items[1].element.querySelector('button').click();await f.flush();
  expect(f.ids()).toEqual(['a','b','c']);expect(f.container.querySelector('[role=status]').textContent).toContain('Could not save');
  controller.destroy();expect(f.ids()).toEqual(['a','b','c']);expect(f.container.querySelector('.layout-order-toolbar')).toBe(null);
  expect(f.container.querySelector('.layout-order-controls')).toBe(null);
 });
});
