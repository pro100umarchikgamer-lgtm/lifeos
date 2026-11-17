import {describe,it,expect} from 'vitest';
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
  const f=fixture();expect(f.wrapper,'shared enhancer exists').toBeTruthy();
  const trigger=f.wrapper.querySelector('button');trigger.click();
  expect(trigger.getAttribute('aria-expanded')).toBe('true');
  const options=f.wrapper.querySelectorAll('[role=option]');expect(options).toHaveLength(2);
  expect(options[0].getAttribute('aria-label')).toBe('Only me');
  options[1].click();expect(f.select.value).toBe('shared');expect(f.select.selectedOptions[0].textContent).toBe('Workspace');
  expect(new f.w.FormData(f.form).get('visibility')).toBe('shared');expect(trigger.textContent).toContain('Workspace');
  expect(f.select.hidden).toBe(false);expect(f.select.choiceField).toBe(f.wrapper);
  expect(f.w.document.querySelector('label').htmlFor).toBe(trigger.id);
 });
 it('syncs programmatic values, change events and pending disabled states without losing input',async()=>{
  const f=fixture();expect(f.wrapper).toBeTruthy();const trigger=f.wrapper.querySelector('button');
  f.select.value='shared';expect(trigger.textContent).toContain('Workspace');
  f.select.selectedIndex=0;expect(trigger.textContent).toContain('Only me');
  trigger.click();f.select.disabled=true;await Promise.resolve();expect(trigger.disabled).toBe(true);expect(trigger.getAttribute('aria-expanded')).toBe('false');
  f.select.disabled=false;f.form.querySelector('fieldset').disabled=true;await Promise.resolve();expect(trigger.disabled).toBe(true);
  f.form.querySelector('fieldset').disabled=false;await Promise.resolve();expect(trigger.disabled).toBe(false);expect(f.select.value).toBe('private');
 });
 it('supports keyboard selection, typeahead, Escape and outside dismissal',()=>{
  const f=fixture();expect(f.wrapper).toBeTruthy();const trigger=f.wrapper.querySelector('button'),list=f.wrapper.querySelector('[role=listbox]');
  trigger.dispatchEvent(new f.w.KeyboardEvent('keydown',{key:'ArrowDown',bubbles:true,cancelable:true}));
  list.dispatchEvent(new f.w.KeyboardEvent('keydown',{key:'w',bubbles:true,cancelable:true}));
  list.dispatchEvent(new f.w.KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true}));expect(f.select.value).toBe('shared');
  trigger.click();list.dispatchEvent(new f.w.KeyboardEvent('keydown',{key:'Escape',bubbles:true,cancelable:true}));expect(trigger.getAttribute('aria-expanded')).toBe('false');
  trigger.click();f.w.document.body.dispatchEvent(new f.w.Event('pointerdown',{bubbles:true}));expect(trigger.getAttribute('aria-expanded')).toBe('false');
 });
});
