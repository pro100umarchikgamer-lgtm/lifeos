'use strict';
/* Explicit source catalogs only. This module never scans or translates record text. */
(function(root){
 const LANGUAGES=['az','de','en','es','fr','hy','it','ka','kk','ky','pt','ru','tg','uk','uz-Cyrl','uz-Latn'];
 let language='ru',packs={},catalog={source:{},groups:{},translations:{},required:[]},loading=null;
 const own=(o,k)=>o&&Object.hasOwn(o,k)?o[k]:undefined;
 const plain=o=>o!==null&&typeof o==='object'&&!Array.isArray(o);
 const validString=v=>typeof v==='string'&&v.length>0;
 function value(id,lang,fallback=''){
  const source=own(catalog.source,id),translated=own(own(catalog.translations,lang),id);
  if(validString(translated))return translated;
  const native=source?.native_key&&own(packs[lang]?.strings,source.native_key);
  if(validString(native))return native;
  return own(source?.values,lang)||own(source?.values,'en')||own(source?.values,'ru')||fallback||id;
 }
 function text(id,values={},fallback=''){
  return String(value(id,language,fallback)).replace(/\{([A-Za-z_][\w.]*)\}/g,(token,key)=>Object.hasOwn(values,key)?String(values[key]):token);
 }
 function systemMessage(item){
  const known={reminder:['system_task_reminder','system_calendar_reminder'],test:['system_test_notification_queued'],budget:['system_budget_threshold']};
  const unchanged={title:item?.title,body:item?.body};
  if(!known[item?.kind]?.includes(item.message_key))return unchanged;
  const template=own(packs[language]?.strings,item.message_key);if(!validString(template))return unchanged;
  const threshold=item.message_args?.threshold;
  if(item.kind==='budget'&&(!Number.isInteger(threshold)||threshold<1||threshold>100))return unchanged;
  const body=template.replace(/\{threshold\}/g,String(threshold));
  const title=item.kind==='budget'&&item.title_key==='module_budgets'?(own(packs[language]?.strings,'module_budgets')||item.title):item.title;
  return {title,body};
 }
 function setLanguage(lang){if(LANGUAGES.includes(lang))language=lang;if(root.document?.documentElement)root.document.documentElement.lang=language;bindStatic();return language;}
 function queryLanguage(search,fallback){
  const entries=new URLSearchParams(search).getAll('lang');
  if(!entries.length)return {language:fallback,invalid:false};
  return entries.length===1&&LANGUAGES.includes(entries[0])?{language:entries[0],invalid:false}:{language:fallback,invalid:true};
 }
 function complete(lang){
  if(!catalog.required.length||!LANGUAGES.includes(lang))return false;
  return catalog.required.every(id=>{const s=own(catalog.source,id);return validString(own(own(catalog.translations,lang),id))||validString(own(s?.values,lang))||Boolean(s?.native_key&&validString(own(packs[lang]?.strings,s.native_key)));});
 }
 function copy(groupId,original){
  const result={},rows=new Map();
  function clone(x){if(Array.isArray(x))return x.map(clone);if(plain(x))return Object.fromEntries(Object.entries(x).map(([k,v])=>[k,clone(v)]));return x;}
  function resolve(raw,lang,path){
   if(typeof raw==='string'){
    const group=own(catalog.groups,groupId),id=own(group,path||'$value')||path.split('.').reduce((v,k)=>own(v,k),group);
    return id?value(id,lang,raw):raw;
   }
   if(!raw||typeof raw!=='object')return raw;
   return new Proxy(raw,{get(target,key,receiver){const item=Reflect.get(target,key,receiver);if(typeof key==='symbol'||typeof item==='function')return item;return resolve(item,lang,path?path+'.'+key:String(key));}});
  }
  for(const lang of [...new Set([...LANGUAGES,...Object.keys(original)])]){
   rows.set(lang,clone(own(original,lang)??original.en??original.ru));
   Object.defineProperty(result,lang,{enumerable:true,configurable:false,get(){return resolve(rows.get(lang),lang,'');},set(next){rows.set(lang,clone(next));}});
  }
  return result;
 }
 function bindStatic(container=root.document){
  if(!container?.querySelectorAll)return;
  for(const node of container.querySelectorAll('[data-i18n]'))node.textContent=text(node.dataset.i18n,{},node.textContent);
  for(const node of container.querySelectorAll('[data-i18n-aria]'))node.setAttribute('aria-label',text(node.dataset.i18nAria,{},node.getAttribute('aria-label')||''));
 }
 async function load(nextPacks){
  if(nextPacks&&typeof nextPacks==='object')packs=nextPacks;
  if(!loading)loading=(async()=>{
   try{
    const response=await root.fetch('/app/assets/translations.json',{credentials:'omit',cache:'no-store'});
    if(!response.ok)return false;
    const data=await response.json();
    if(data.schemaVersion!==1||!plain(data.source)||!plain(data.groups)||!plain(data.translations)||!Array.isArray(data.required))return false;
    for(const [id,s]of Object.entries(data.source))if(!/^[A-Za-z0-9_:-]+$/.test(id)||!plain(s)||!plain(s.values)||Object.values(s.values).some(v=>typeof v!=='string'))return false;
    for(const strings of Object.values(data.translations))if(!plain(strings)||Object.values(strings).some(v=>typeof v!=='string'))return false;
    catalog=data;bindStatic();return true;
   }catch{return false;}
  })();
  const current=loading,result=await current;if(!result&&loading===current)loading=null;return result;
 }
 root.UladimI18n={languages:LANGUAGES,text,copy,load,setLanguage,language:()=>language,complete,bindStatic,systemMessage,queryLanguage};
})(globalThis);
