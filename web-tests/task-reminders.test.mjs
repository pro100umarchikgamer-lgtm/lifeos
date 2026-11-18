import {loadI18n} from './i18n-fixture.mjs';
import assert from 'node:assert/strict';
import {describe, it, mock} from 'node:test';
import {JSDOM} from 'jsdom';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const source=readFileSync(new URL('../backend/webassets/app/task-reminders.js',import.meta.url),'utf8');
function fixture(){const dom=new JSDOM('<form id="task"></form>',{url:'https://getuladim.space/app',runScripts:'outside-only'});loadI18n(dom.window);dom.window.eval(source);return {window:dom.window,api:dom.window.UladimTaskReminders,form:dom.window.document.querySelector('form')};}
function change(f,field,value){field.value=value;field.dispatchEvent(new f.window.Event('change',{bubbles:true}));}
describe('task schedule editor',()=>{
 it('keeps an unscheduled task optional and separates a due date from opt-in reminders',()=>{
  const f=fixture(),editor=f.api.mount(f.form,{lang:'ru',timezone:'Europe/Moscow'});
  assert.deepEqual(structuredClone(editor.value()), {schedule:null,reminder:false});
  assert.equal(editor.reminder.disabled, true);
  change(f,editor.date,'2026-12-01');
  assert.deepEqual(structuredClone(editor.value()), {
   schedule:{localStart:'2026-12-01T09:00:00',timezone:'Europe/Moscow',allDay:true,repeat:'none',interval:1,until:null},
   reminder:false,
  });
  change(f,editor.time,'18:45');
  editor.reminder.checked=true;
  editor.reminder.dispatchEvent(new f.window.Event('change'));
  assert.partialDeepStrictEqual(editor.value(), {schedule:{localStart:'2026-12-01T18:45:00',allDay:false},reminder:true});
  assert.equal(editor.date.labels[0].textContent, 'Дата задачи');
  assert.ok(editor.reminder.labels[0].textContent.includes('Напомнить'));
  assert.equal(f.window.localStorage.length, 0);
  assert.equal(f.window.sessionStorage.length, 0);
 });
 it('loads persisted timezone and repeat details, clears an invalid repeat end when moving the date, and supports no date',()=>{
  const f=fixture(),editor=f.api.mount(f.form,{lang:'en',initial:{schedule:{localStart:'2026-11-20T14:30:00',timezone:'Asia/Tashkent',allDay:false,repeat:'weekly',interval:2,until:'2026-12-01'},reminder:true}});
  assert.deepEqual([editor.date.value,editor.time.value,editor.reminder.checked], ['2026-11-20','14:30',true]);
  change(f,editor.date,'2026-12-02');
  assert.partialDeepStrictEqual(editor.value(), {schedule:{timezone:'Asia/Tashkent',repeat:'weekly',interval:2,until:null}});
  f.form.querySelector('button').click();
  assert.deepEqual(structuredClone(editor.value()), {schedule:null,reminder:false});
 });
 it('enforces readonly authority and temporary save state without changing persisted input',()=>{
  const f=fixture(),initial={schedule:{localStart:'2026-11-20T14:30:00',timezone:'UTC',allDay:false,repeat:'none',interval:1,until:null},reminder:false};
  const locked=f.api.mount(f.form,{initial:{...initial,can_edit:false}});
  assert.equal([...locked.element.querySelectorAll('input,button')].every(node=>node.disabled), true);
  const editor=f.api.mount(f.form,{initial});
  editor.setBusy(true);
  assert.equal(editor.date.disabled, true);
  editor.setBusy(false);
  assert.deepEqual(structuredClone(editor.value()), {schedule:initial.schedule,reminder:false});
  assert.equal(editor.date.disabled, false);
 });
 it('uses supplied authenticated transport for persisted metadata without adding fields to task record data',async()=>{
  const f=fixture(),api=mock.fn(async(path,body)=>({path,body}));
  await f.api.get(api,'workspace with space','task/id');
  assert.deepEqual(structuredClone(api.mock.calls.at(-1)?.arguments), [
   'task-reminders?workspace=workspace%20with%20space&task_id=task%2Fid',
  ]);
  const body={workspace_id:'workspace',task_id:'task',revision:0,schedule:null,reminder:false};
  await f.api.save(api,body);
  assert.deepEqual(structuredClone(api.mock.calls.at(-1)?.arguments), ['task-reminders', body]);
  assert.equal(f.window.localStorage.length, 0);
 });
});
describe('task notification destinations',()=>{
 it('accepts only exact same-origin task/calendar routes and rejects duplicate or mixed query keys',()=>{
  const worker={self:{location:{origin:'https://getuladim.space'},addEventListener(){}} ,URL};
  vm.runInNewContext(readFileSync(new URL('../backend/webassets/app/sw.js',import.meta.url),'utf8'),worker);
  const workspace='11111111-1111-4111-8111-111111111111',task='22222222-2222-4222-8222-222222222222';
  const target='/app?notification=task&workspace='+workspace+'&task='+task;
  assert.equal(worker.notificationDestination(target), target);
  assert.ok(worker.notificationDestination('/app?notification=calendar&workspace='+workspace+'&day=2026-11-15').includes('day=2026-11-15'));
  for(const value of [target+'&task='+task,target+'&workspace='+workspace,target+'&day=2026-11-15',target.replace('task='+task,'task=invalid'),'https://external.invalid'+target,target+'#fragment',target.replace('notification=task','notification=calendar')])assert.equal(worker.notificationDestination(value), null);
 });
});
