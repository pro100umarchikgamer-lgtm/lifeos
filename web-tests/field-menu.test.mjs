import assert from 'node:assert/strict';
import {describe, it} from 'node:test';
import {JSDOM} from 'jsdom';
import {existsSync,readFileSync} from 'node:fs';
const path=new URL('../backend/webassets/app/field-menu.js',import.meta.url);
function fixture(){
 const dom=new JSDOM('<form><fieldset><label for="visibility">Visibility</label><select id="visibility" name="visibility"><option value="private">Only me</option><option value="shared">Workspace</option><option value="off" disabled>Unavailable</option></select></fieldset></form>',{url:'https://example.test/app',runScripts:'outside-only',pretendToBeVisual:true});
 const w=dom.window;w.HTMLElement.prototype.scrollIntoView=()=>{};
 if(existsSync(path))w.eval(readFileSync(path,'utf8'));
 const select=w.document.querySelector('select');
 const wrapper=w.UladimFieldMenu?.enhance(select,'Visibility');
 return {w,select,wrapper,form:w.document.querySelector('form')};
}
describe('shared field menus',()=>{
 it('opens app-owned choices and preserves the native form value and selectedOptions',()=>{
  const f=fixture();assert.ok(f.wrapper, 'shared enhancer exists');
  const trigger=f.wrapper.querySelector('button');trigger.click();
  assert.equal(trigger.getAttribute('aria-expanded'), 'true');
  const options=f.wrapper.querySelectorAll('[role=option]');assert.equal(options.length, 2);
  assert.equal(options[0].getAttribute('aria-label'), 'Only me');
  options[1].click();assert.equal(f.select.value, 'shared');assert.equal(f.select.selectedOptions[0].textContent, 'Workspace');
  assert.equal(new f.w.FormData(f.form).get('visibility'), 'shared');assert.ok(trigger.textContent.includes('Workspace'));
  assert.equal(f.select.hidden, false);assert.equal(f.select.choiceField, f.wrapper);
  assert.equal(f.w.document.querySelector('label').htmlFor, trigger.id);
 });
 it('syncs programmatic values, change events and pending disabled states without losing input',async()=>{
  const f=fixture();assert.ok(f.wrapper);const trigger=f.wrapper.querySelector('button');
  f.select.value='shared';assert.ok(trigger.textContent.includes('Workspace'));
  f.select.selectedIndex=0;assert.ok(trigger.textContent.includes('Only me'));
  trigger.click();f.select.disabled=true;await Promise.resolve();assert.equal(trigger.disabled, true);assert.equal(trigger.getAttribute('aria-expanded'), 'false');
  f.select.disabled=false;f.form.querySelector('fieldset').disabled=true;await Promise.resolve();assert.equal(trigger.disabled, true);
  f.form.querySelector('fieldset').disabled=false;await Promise.resolve();assert.equal(trigger.disabled, false);assert.equal(f.select.value, 'private');
 });
 it('supports keyboard selection, typeahead, Escape and outside dismissal',()=>{
  const f=fixture();assert.ok(f.wrapper);const trigger=f.wrapper.querySelector('button'),list=f.wrapper.querySelector('[role=listbox]');
  trigger.dispatchEvent(new f.w.KeyboardEvent('keydown',{key:'ArrowDown',bubbles:true,cancelable:true}));
  list.dispatchEvent(new f.w.KeyboardEvent('keydown',{key:'w',bubbles:true,cancelable:true}));
  list.dispatchEvent(new f.w.KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true}));assert.equal(f.select.value, 'shared');
  trigger.click();list.dispatchEvent(new f.w.KeyboardEvent('keydown',{key:'Escape',bubbles:true,cancelable:true}));assert.equal(trigger.getAttribute('aria-expanded'), 'false');
  trigger.click();f.w.document.body.dispatchEvent(new f.w.Event('pointerdown',{bubbles:true}));assert.equal(trigger.getAttribute('aria-expanded'), 'false');
 });
});
