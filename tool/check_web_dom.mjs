// DOM integration with the actual disposable WSGI fixture. No mocked API data.
// This is supplemental to Playwright; jsdom does not prove rendering or PWA.
import {JSDOM} from 'jsdom';
import {randomUUID} from 'node:crypto';
import assert from 'node:assert/strict';
const origin=process.argv[2],documentURL=new URL('/app',origin);
const documentResponse=await fetch(documentURL);
assert.equal(documentResponse.status,200,'The real fixture serves the application document');
assert.equal(new URL(documentResponse.url).origin,documentURL.origin,'The fixture document stays on its own origin');
const dom=new JSDOM(await documentResponse.text(),{url:documentURL.href,runScripts:'outside-only',pretendToBeVisual:true});
const w=dom.window;let cookie='';
w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};
w.HTMLDialogElement.prototype.close=function(){this.open=false;this.dispatchEvent(new w.Event('close'));};
w.matchMedia=()=>({matches:false,addEventListener(){},removeEventListener(){}});
w.ResizeObserver=class{observe(){} disconnect(){}};
w.HTMLElement.prototype.scrollIntoView=function(){};
w.scrollTo=function(){}; // jsdom has no viewport; real scrolling is checked by Playwright.
w.HTMLCanvasElement.prototype.getContext=function(){return new Proxy({},{get:(_,key)=>key==='measureText'?()=>({width:40}):()=>{}});};
Object.defineProperty(w.crypto,'randomUUID',{value:randomUUID});
w.fetch=async(path,options={})=>{
 const headers={...options.headers,'User-Agent':'uladim-dom-fixture','Origin':origin,...(cookie?{Cookie:cookie}:{})};
 const response=await fetch(new URL(path,origin),{...options,headers});
 if(!response.ok&&options.body)console.error('API failure',path,options.body,await response.clone().text());
 const set=response.headers.get('set-cookie');if(set)cookie=set.split(';')[0];return response;
};
const scripts=[...w.document.querySelectorAll('script[src]')];
assert(scripts.length,'The fixture application document declares its scripts');
const sources=[];
for(const script of scripts){
 const url=new URL(script.getAttribute('src'),documentURL);
 assert.equal(url.origin,documentURL.origin,'The fixture loads only actual same-origin application scripts');
 assert(!script.type||['text/javascript','application/javascript'].includes(script.type),'The supplemental DOM fixture executes classic scripts; module coverage belongs to Playwright');
 const response=await w.fetch(url.href);
 assert.equal(response.status,200,'Application script is served: '+url.pathname);
 sources.push(await response.text());
}
// Classic deferred scripts share one global lexical environment in a browser.
// Separate window.eval calls would hide import.js's const bindings from app.js.
w.eval(sources.join('\n;\n')+'\nglobalThis.fixtureSpace=()=>state.space;');
const wait=async predicate=>{for(let n=0;n<100;n++){if(predicate())return;await new Promise(r=>setTimeout(r,30));}throw new Error('DOM timeout: '+w.document.body.textContent.slice(0,1000));};
const button=(text,scope=w.document)=>{const b=[...scope.querySelectorAll('button')].find(b=>b.textContent===text);assert(b,'Missing button '+text);return b;};
const change=(field,value)=>{field.value=value;field.dispatchEvent(new w.Event('change',{bubbles:true}));};
const submit=()=>w.document.querySelector('dialog form').dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));
try{
 await wait(()=>w.document.querySelector('input[name=email]'));
 w.document.querySelector('[name=email]').value='web@example.test';w.document.querySelector('[name=password]').value='synthetic-web-platform-password';
 w.document.querySelector('form').dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));
 await wait(()=>w.document.querySelector('.nav'));
 const home=w.document.querySelector('.today-page');
 assert(home.querySelector('.today-grid > .today-notes'),'Today notes have their own grid area');
 assert.equal(home.querySelector('.today-side').firstElementChild.classList.contains('today-finance'),true,'Finance starts the Today side column');
 assert(home.querySelector('.today-side .today-agenda'),'Today schedule belongs in the side column');
 button('История операций',home).click();
 const initialLedger=w.document.querySelector('#finance-ledger');
 assert(initialLedger?.querySelector('h2').textContent==='История операций','Today opens the finance ledger');
 assert.equal(w.document.activeElement,w.document.querySelector('main h1'),'Today directs focus to the finance page heading');
 assert.equal(w.document.querySelector('main').dataset.financeView,'ledger','Today opens the transaction-history view');
 const accountsTab=w.document.querySelector('.finance-navigation button[data-section="accounts"]');
 assert(accountsTab,'Finance exposes a direct account view');
 accountsTab.click();
 assert.equal(w.document.querySelector('main').dataset.financeView,'accounts','Finance account navigation opens its own view');
 assert(w.document.querySelector('#finance-accounts'),'Accounts are present in their own view');
 assert(!w.document.querySelector('#finance-ledger'),'Account navigation does not scroll through a combined page');
 button('Сегодня').click();
 button('Все задачи',w.document.querySelector('.today-page')).click();
 assert(w.document.querySelector('#tasks-open_tasks').closest('.task-group').textContent.includes('Подготовить план'));
 assert(w.document.querySelector('#tasks-completed').closest('.task-group').textContent.includes('Забрать заказ'));
 const search=w.document.querySelector('[name=task-search]');search.value='заказ';search.dispatchEvent(new w.Event('input'));
 assert(!w.document.querySelector('#tasks-open_tasks'),'Empty task groups are omitted after filtering');
 assert(w.document.querySelector('main').textContent.includes('Забрать заказ'));assert(!w.document.querySelector('main').textContent.includes('Подготовить план'));
 change(w.document.querySelector('[name=task-status]'),'open');assert(!w.document.querySelector('main').textContent.includes('Забрать заказ'));
 button('Календарь').click();
 change(w.document.querySelector('[name=calendar-day]'),'2026-11-12');
 const agenda=w.document.querySelector('.calendar-agenda');
 assert(agenda?.querySelector('h2').textContent.includes('12'),'Calendar agenda must show the selected date');
 agenda.querySelector('button').click();
 assert.equal(w.document.activeElement.tagName,'H2','Opening a dialog must focus its title');
 assert.equal(w.document.querySelector('[name=localStart]').value,'2026-11-12T09:00');
 const eventOptions=w.document.querySelector('dialog details.event-options');
 assert(eventOptions&&!eventOptions.open,'Advanced calendar fields are initially collapsed');
 assert.equal(eventOptions.querySelector('label[for="'+eventOptions.querySelector('[name=timezone]').id+'"]').textContent,'Часовой пояс');
 assert(eventOptions.querySelector('.event-repeat-options').hidden,'Additional recurrence fields are initially hidden');
 eventOptions.open=true;
 change(eventOptions.querySelector('[name=repeat]'),'weekly');
 assert(!eventOptions.querySelector('.event-repeat-options').hidden,'Weekly recurrence exposes interval and end date');
 change(eventOptions.querySelector('[name=repeat]'),'none');
 w.document.querySelector('dialog [name=name]').value='DOM shared event';w.document.querySelector('[name=localStart]').value='2026-11-12T14:30';w.document.querySelector('[name=timezone]').value='Asia/Tashkent';submit();
 await wait(()=>!w.document.querySelector('dialog'));assert.equal(w.document.querySelector('.error')?.textContent||'','');
 change(w.document.querySelector('[name=calendar-day]'),'2026-11-12');await wait(()=>w.document.querySelector('main').textContent.includes('DOM shared event'));
 button('Заметки').click();button('Редактировать').click();w.document.querySelector('textarea').value='DOM changed note';submit();await wait(()=>!w.document.querySelector('dialog')&&w.document.querySelector('main').textContent.includes('DOM changed note'));
 assert.equal(w.document.querySelectorAll('.note-preview').length,0,'single-line note must not repeat its heading as body');
 button('Редактировать').click();
 const noteEditor=w.document.querySelector('dialog'),more=noteEditor.querySelector('.editor-more');
 more.querySelector('summary').click();assert(more.open,'Record actions open before deletion');
 button('Удалить',more).click();
 // Deletion is queued after the reviewed editor/history close completes.
 await wait(()=>!w.document.querySelector('dialog')&&w.document.querySelector('#alerts .toast.undo'));
 const undoToast=w.document.querySelector('#alerts .toast.undo');
 button('Отменить',undoToast).click();
 assert(!undoToast.isConnected,'Undo removes the pending-deletion notice');
 assert(w.document.querySelector('main').textContent.includes('DOM changed note'),'Undo preserves the saved note without another save');
 button('Финансы').click();await wait(()=>w.document.querySelector('.finance-metric-grid'));assert(w.document.querySelector('main').textContent.includes('RUB'));
 button('Добавить операцию').click();
 w.document.querySelector('[name=amount]').value='125,50';w.document.querySelector('[name=label]').value='DOM coffee';submit();
 await wait(()=>!w.document.querySelector('dialog')&&w.document.querySelector('main').textContent.includes('DOM coffee'));
 button('Профиль',w.document.querySelector('.nav')).click();
 w.document.querySelector('.settings-navigation [data-section=security]').click();
 await wait(()=>w.document.querySelector('.settings-row-status')?.textContent==='Google не подключён');
 assert.equal(w.document.querySelectorAll('.settings-content .settings-group').length,3);
 button('Оформление',w.document.querySelector('.settings-navigation')).click();await wait(()=>w.document.querySelector('[name=theme]'));change(w.document.querySelector('[name=theme]'),'dark');assert.equal(w.document.body.dataset.theme,'dark');
 change(w.document.querySelector('[name=language]'),'uz-Latn');await wait(()=>w.document.querySelector('.nav').textContent.includes('Taqvim'));assert.equal(w.document.documentElement.lang,'uz-Latn');
 const response=await w.fetch('/account/api/sync?workspace='+encodeURIComponent(w.fixtureSpace()));const data=await response.json();assert(data.records.some(r=>r.data.title==='DOM shared event'));assert(data.records.some(r=>r.data.body==='DOM changed note'&&!r.deleted));assert(data.records.some(r=>r.kind==='transaction'&&r.data.label==='DOM coffee'&&r.data.amount_minor===12550));
 assert(!w.localStorage.getItem('uladim-interface').includes('DOM changed'));console.log('DOM_INTEGRATION_PASSED: task filters, event save, note save/undo, finance, Google status, theme, Uzbek, real server records');
}finally{w.close();}
