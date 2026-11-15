import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const sourcePath=new URL('../backend/webassets/app/i18n.js',import.meta.url);
function boot(data,fetcher){
 const context={console,URLSearchParams,fetch:fetcher||(async()=>({ok:true,json:async()=>data}))};
 vm.createContext(context);
 if(fs.existsSync(sourcePath))vm.runInContext(fs.readFileSync(sourcePath,'utf8'),context);
 assert.ok(context.UladimI18n,'shared source-scoped localization engine is available');
 return context.UladimI18n;
}
const catalog={schemaVersion:1,languages:['en','ru','de'],source:{
 hello:{values:{en:'Hello',ru:'Привет'}},
 saved:{values:{en:'Saved {name}',ru:'Сохранено: {name}'}},
 native:{values:{en:'Cancel',ru:'Отмена'},native_key:'cancel'},
 appended:{values:{en:'Retry',ru:'Повторить'}},
},groups:{g:{title:'hello',nested:'saved',items:{'0':'native'}},extension:{'$value':'appended'},base:{retry:'appended'}},translations:{de:{hello:'Hallo',saved:'Gespeichert: {name}',appended:'Erneut versuchen'}},required:['hello','saved','native','appended']};

test('selected language is resolved before English and native keys are reused',async()=>{
 const i=boot(catalog);await i.load({de:{strings:{cancel:'Abbrechen'}}});i.setLanguage('de');
 assert.equal(i.text('hello'),'Hallo');assert.equal(i.text('native'),'Abbrechen');
});
test('copy resolves catalog loaded after source construction and preserves nested arrays',async()=>{
 const i=boot(catalog),original={en:{title:'Hello',nested:'Saved {name}',items:['Cancel']},ru:{title:'Привет',nested:'Сохранено: {name}',items:['Отмена']}};
 const copies=i.copy('g',original);assert.equal(copies.de.title,'Hello');
 await i.load({de:{strings:{cancel:'Abbrechen'}}});
 assert.equal(copies.de.title,'Hallo');assert.ok(Array.isArray(copies.de.items));assert.equal(copies.de.items[0],'Abbrechen');
 assert.deepEqual(original,{en:{title:'Hello',nested:'Saved {name}',items:['Cancel']},ru:{title:'Привет',nested:'Сохранено: {name}',items:['Отмена']}});
});
test('copy mutation from a top-level locale loop remains translated after async load',async()=>{
 const i=boot(catalog),base=i.copy('base',{en:{},ru:{}}),extension=i.copy('extension',{en:'Retry',ru:'Повторить'});
 for(const[lang,value]of Object.entries(extension))base[lang].retry=value;
 await i.load({});assert.equal(base.de.retry,'Erneut versuchen');assert.equal(base.ru.retry,'Повторить');
});
test('language changes affect later source text without a page reload',async()=>{
 const i=boot(catalog);await i.load({});i.setLanguage('ru');assert.equal(i.text('hello'),'Привет');i.setLanguage('de');assert.equal(i.text('hello'),'Hallo');
});
test('template values stay exact and are never recursively translated',async()=>{
 const i=boot(catalog);await i.load({});i.setLanguage('de');const customerRecordTitle='Hello <script>alert(1)</script>';
 assert.equal(i.text('saved',{name:customerRecordTitle}),'Gespeichert: '+customerRecordTitle);
 assert.equal(customerRecordTitle,'Hello <script>alert(1)</script>');
});
test('unknown IDs use explicit source fallback, never inspect arbitrary customer text',async()=>{
 const i=boot(catalog);await i.load({});i.setLanguage('de');assert.equal(i.text('unknown',{},'Private record title'),'Private record title');
 assert.equal(i.text('hello',{name:'Привет'}),'Hallo');
});
test('coverage distinguishes missing translations from English fallback',async()=>{
 const i=boot(catalog);await i.load({});assert.equal(i.complete('de'),false);await i.load({de:{strings:{cancel:'Abbrechen'}}});assert.equal(i.complete('de'),true);assert.equal(i.complete('fr'),false);
});
test('source modules may replace locale rows while canonical catalogs stay authoritative',async()=>{
 const i=boot(catalog),copies=i.copy('g',{en:{title:'Hello'},ru:{title:'Привет'}});
 copies.de={title:'Hello',custom:'Source-only extension'};
 await i.load({});assert.equal(copies.de.title,'Hallo');assert.equal(copies.de.custom,'Source-only extension');
});
test('only server-marked known system message kinds use localized templates',async()=>{
 const i=boot(catalog);await i.load({de:{strings:{system_task_reminder:'Aufgabe fällig',system_budget_threshold:'Budget: {threshold}%',module_budgets:'Budgets'}}});i.setLanguage('de');
 assert.equal(i.systemMessage({kind:'reminder',message_key:'system_task_reminder',title:'Private task title',body:'RU'}).body,'Aufgabe fällig');
 const budget=i.systemMessage({kind:'budget',message_key:'system_budget_threshold',message_args:{threshold:80},title_key:'module_budgets',title:'RU title',body:'RU'});
 assert.equal(budget.title,'Budgets');assert.equal(budget.body,'Budget: 80%');
});
test('announcement and unknown notification bodies and customer titles remain exact',async()=>{
 const i=boot(catalog);await i.load({de:{strings:{system_task_reminder:'Aufgabe fällig'}}});i.setLanguage('de');
 for(const item of [{kind:'announcement',message_key:'system_task_reminder',title:'Hello',body:'Привет'}, {kind:'reminder',message_key:'unknown',title:'Hello',body:'Привет'}]){
  const rendered=i.systemMessage(item);assert.equal(rendered.title,item.title);assert.equal(rendered.body,item.body);
 }
});
test('native public-language handoff accepts one known display tag only',()=>{
 const i=boot(catalog);assert.equal(i.queryLanguage('?lang=uz-Cyrl','ru').language,'uz-Cyrl');assert.equal(i.queryLanguage('?lang=de','ru').invalid,false);
 for(const query of ['?lang=de&lang=en','?lang=unknown','?lang=']){const result=i.queryLanguage(query,'ru');assert.equal(result.language,'ru');assert.equal(result.invalid,true);}
 assert.equal(i.queryLanguage('?unrelated=de','ru').language,'ru');
});
test('budget system templates reject malformed and out-of-range threshold data',async()=>{
 const i=boot(catalog);await i.load({de:{strings:{system_budget_threshold:'Budget: {threshold}%',module_budgets:'Budgets'}}});i.setLanguage('de');
 for(const threshold of ['80',0,101,1.5,null]){const item={kind:'budget',message_key:'system_budget_threshold',message_args:{threshold},title:'Original title',body:'Original body'};assert.equal(i.systemMessage(item).body,'Original body');}
});
test('failed catalog load retries with one concurrent request and no permanent fallback',async()=>{
 let calls=0;const i=boot(catalog,async()=>{calls++;return calls===1?{ok:false}:{ok:true,json:async()=>catalog};});
 const first=await Promise.all([i.load({}),i.load({})]);assert.equal(first[0],false);assert.equal(first[1],false);assert.equal(calls,1);
 assert.equal(await i.load({}),true);assert.equal(calls,2);i.setLanguage('de');assert.equal(i.text('hello'),'Hallo');
});
