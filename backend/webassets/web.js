'use strict';
const app=document.querySelector('#app');
try{const appearance=JSON.parse(localStorage.getItem('uladim-interface')||'{}');document.body.dataset.theme=appearance.theme||'system';}catch{document.body.dataset.theme='system';}
const staff=document.documentElement.dataset.surface==='control';
if(staff){document.body.dataset.control='true';document.title='ULADIM Control';}
const prefix=staff?'/control/api/':'/account/api/';
let csrf='',viewEpoch=0;
let controlNavigation=null,controlSection='dashboard',lastPublicConfig={};
let authPacks={},authLanguage='ru',googleEnabled=false;
try{authLanguage=JSON.parse(localStorage.getItem('uladim-interface')||'{}').lang||'ru';}catch{}
const languageQuery=staff?{language:authLanguage,invalid:false}:globalThis.UladimI18n.queryLanguage(location.search,authLanguage);
authLanguage=languageQuery.language;
if(!staff&&!languageQuery.invalid&&new URLSearchParams(location.search).has('lang'))try{const saved=JSON.parse(localStorage.getItem('uladim-interface')||'{}');saved.lang=authLanguage;localStorage.setItem('uladim-interface',JSON.stringify(saved));}catch{}
const tr=k=>authPacks[authLanguage]?.strings[k]||authPacks.ru?.strings[k]||k;
function globalLanguagePicker(){
 const header=document.querySelector('body > header');if(!header||header.querySelector('.global-language'))return;
 const label=el('label',undefined,'global-language'),select=el('select');select.setAttribute('aria-label',tr('language'));
 for(const[key,pack]of Object.entries(authPacks)){const option=el('option',pack.name);option.value=key;select.append(option);}select.value=authLanguage;
 label.append(select);header.append(label);
 if(languageQuery.invalid){const warning=el('p',tr('language')+': '+tr('family_error_invalid_input'),'language-query-error');warning.setAttribute('role','alert');header.insertAdjacentElement('afterend',warning);}
 select.addEventListener('change',async()=>{
  authLanguage=select.value;document.querySelector('.language-query-error')?.remove();await globalThis.UladimI18n.load(authPacks);viewEpoch++;const displayURL=new URL(location.href);if(displayURL.searchParams.has('lang')){displayURL.searchParams.set('lang',authLanguage);history.replaceState(null,'',displayURL.pathname+displayURL.search+displayURL.hash);}globalThis.UladimI18n.setLanguage(authLanguage);select.setAttribute('aria-label',tr('language'));
  try{const saved=JSON.parse(localStorage.getItem('uladim-interface')||'{}');saved.lang=authLanguage;localStorage.setItem('uladim-interface',JSON.stringify(saved));}catch{}
  select.disabled=true;try{
   if(staff){const previous=controlSection;try{await dashboard();if(previous!=='dashboard'&&controlNavigation){const nav=controlNavigation.querySelector('select');nav.value=previous;nav.dispatchEvent(new Event('change'));}}catch(error){if(['unauthorized','staff_unauthorized'].includes(error.code))login();else throw error;}}
   else await publicPage(lastPublicConfig);
  }catch(error){notice(error.message);}finally{select.disabled=false;}
 });
}
function authLanguages(){const f=el('div',undefined,'auth-language');const label=el('label',tr('language'));const select=el('select');select.setAttribute('aria-label',tr('language'));for(const [key,value]of Object.entries(authPacks)){const option=el('option',value.name);option.value=key;select.append(option);}select.value=authLanguage;select.addEventListener('change',async()=>{authLanguage=select.value;await globalThis.UladimI18n.load(authPacks);globalThis.UladimI18n.setLanguage(authLanguage);try{const saved=JSON.parse(localStorage.getItem('uladim-interface')||'{}');saved.lang=authLanguage;localStorage.setItem('uladim-interface',JSON.stringify(saved));}catch{}login();});add(f,label,select);app.append(f);document.documentElement.lang=authLanguage;}
const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
const add=(parent,...children)=>{for(const c of children)parent.append(c);return parent;};
const link=(label,path,secondary=false)=>{const a=el('a',label,'button'+(secondary?' secondary':''));a.href=path;return a;};
const errors={get unauthorized(){return globalThis.UladimI18n.text("literal_a4bdc0b45a45",{},"Войдите в аккаунт.");},get invalid_credentials(){return globalThis.UladimI18n.text("literal_f54913dfc216",{},"Проверьте почту и пароль.");},get staff_auth_invalid(){return globalThis.UladimI18n.text("literal_c0ac1c3f10a8",{},"Проверьте данные входа и новый код MFA.");},get rate_limited(){return globalThis.UladimI18n.text("literal_02d420308598",{},"Слишком много попыток. Подождите перед повтором.");},get staff_forbidden(){return globalThis.UladimI18n.text("literal_8b91fcda78c6",{},"Для этого действия нет разрешения.");},get csrf_invalid(){return globalThis.UladimI18n.text("literal_30de4e567000",{},"Обновите страницу и повторите действие.");},get verify_email(){return globalThis.UladimI18n.text("literal_37d927b71a38",{},"Сначала подтвердите почту в приложении.");},get registration_closed(){return globalThis.UladimI18n.text("literal_68193086d89f",{},"Регистрация пока доступна только приглашённым тестировщикам.");},get announcement_text_invalid(){return globalThis.UladimI18n.text("literal_1ce2af6e5384",{},"Укажите обычный текст: заголовок до 160, сообщение до 4000 знаков.");},get announcement_invalid(){return globalThis.UladimI18n.text("literal_06e546429b9e",{},"Проверьте формат сообщения и аудиторию.");},get announcement_audience_invalid(){return globalThis.UladimI18n.text("literal_11bfefb3a99e",{},"Проверьте ID получателей: нужны действующие подтверждённые аккаунты.");},get announcement_schedule_invalid(){return globalThis.UladimI18n.text("literal_1ab572610d43",{},"Проверьте начало показа и срок сообщения.");},get announcement_link_invalid(){return globalThis.UladimI18n.text("literal_aa77df868d6e",{},"Разрешены только внутренние ссылки /app.");},get announcement_expired(){return globalThis.UladimI18n.text("literal_138c65502f29",{},"Срок сообщения завершён. Создайте новый черновик.");},get revision_conflict(){return globalThis.UladimI18n.text("literal_15b206bccd75",{},"Сообщение изменилось. Обновите список черновиков.");}};
async function api(path,body){const epoch=viewEpoch;const response=await fetch(prefix+path,{method:body?'POST':'GET',credentials:'same-origin',headers:body?{'Content-Type':'application/json','X-CSRF-Token':csrf,'Accept-Language':authLanguage}:{'Accept-Language':authLanguage},body:body?JSON.stringify(body):undefined});const value=await response.json();if(epoch!==viewEpoch)throw new Error(globalThis.UladimI18n.text("literal_30de4e567000",{},"Обновите страницу и повторите действие."));if(!response.ok){const error=new Error(authPacks[authLanguage]?.strings['family_error_'+value.error]||errors[value.error]||tr('family_error_invalid_input'));error.code=value.error;throw error;}return value;}
async function earlyApi(path,body){
 const epoch=viewEpoch;
 const response=await fetch('/early-access/api/'+path,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','Accept-Language':authLanguage},body:JSON.stringify(body)});
 const value=await response.json();
 if(epoch!==viewEpoch)throw new Error(tr('retry'));
 if(!response.ok){const error=new Error(authPacks[authLanguage]?.strings['family_error_'+value.error]||errors[value.error]||tr('family_error_invalid_input'));error.code=value.error;throw error;}
 return value;
}
function heading(title,description){app.replaceChildren(el('div',staff?'ULADIM Control':'ULADIM','eyebrow'),el('h1',title));if(description)app.append(el('p',description));if(staff&&controlNavigation)app.append(controlNavigation);}
function notice(text){app.append(el('div',text,'notice'));}
function panel(title,body){return add(el('section',undefined,'card'),el('h2',title),el('p',body));}
function field(form,name,label,type='text'){const id='field-'+name+'-'+crypto.randomUUID();const l=el('label',label);l.htmlFor=id;const input=el(name==='message'?'textarea':'input');input.id=id;input.name=name;if(name!=='message')input.type=type;input.required=true;if(type==='password')input.autocomplete='current-password';if(name==='code'){input.autocomplete='one-time-code';input.spellcheck=false;}form.append(l,input);return input;}
function form(title,fields,submit,run){const f=el('form',undefined,'panel');f.append(el('h2',title));const inputs={};for(const [name,label,type]of fields)inputs[name]=field(f,name,label,type);const message=el('p');message.setAttribute('role','status');const button=el('button',submit);button.type='submit';f.append(message,button);f.addEventListener('submit',async e=>{e.preventDefault();button.disabled=true;message.textContent='';try{await run(Object.fromEntries(Object.entries(inputs).map(([k,v])=>[k,v.value])));message.textContent=tr('account_done');}catch(error){message.className='error';message.textContent=error.message;}finally{button.disabled=false;}});app.append(f);return f;}
function focusAuthHeading(title,description){
 heading(title,description);
 app.classList.add('focus-login');
 const brand=el('a','ULADIM','brand focus-login-brand');
 brand.href='/';
 app.firstElementChild.replaceWith(brand);
}

function login(){
 if(staff)controlNavigation=null;
 document.body.dataset.auth='true';
 app.classList.add('auth');
 if(staff)heading('ULADIM Control');
 else focusAuthHeading(tr('family_login'));
 const f=form('',[['email',tr('family_email'),'email'],['password',tr('web_password'),'password']],tr('family_login'),async b=>{
 let r;try{r=await api('login',b);}finally{f.elements.password.value='';b.password='';}
 if(r.mfa_required){loginMfa(r.challenge);return;}csrf=r.csrf;app.classList.remove('auth');await dashboard();
 });f.elements.email.autocomplete='username';
 if(!staff){
  f.querySelector('h2').remove();
  if(googleEnabled){
   const divider=el('div',(globalThis.UladimI18n.copy("grp_5d6e50103a43",{ru:'или','uz-Latn':'yoki','uz-Cyrl':'ёки'}))[authLanguage]||'or','focus-login-divider');
   divider.setAttribute('aria-hidden','true');
   app.append(divider);
   action(tr('account_google_sign_in'),async()=>{const value=await api('google/start',{});location.assign(value.authorization_url);});
   app.lastElementChild.classList.add('focus-login-google');
  }
  const links=el('div',undefined,'focus-login-links');
  action(tr('family_register'),registration,links);
  action(tr('family_recovery'),recovery,links);
  app.append(links);
 }
 authLanguages();
 if(!staff){
  app.lastElementChild.classList.add('focus-login-language');
  const panel=el('div',undefined,'auth-form-panel');
  panel.append(...app.childNodes);
  app.append(focusLoginStory(el,authLanguage),panel);
 }
}
function loginMfa(challenge){
 app.classList.remove('focus-login');
 heading(tr('account_mfa'),tr('web_mfa_hint'));
 const f=form('',[['code',tr('family_code'),'text']],tr('family_login'),async b=>{let r;try{r=await api('login/mfa',{challenge,code:b.code.trim()});}catch(e){if(e.code==='invalid_credentials')e.message=tr('web_mfa_hint');throw e;}finally{f.elements.code.value='';b.code='';}challenge='';csrf=r.csrf;app.classList.remove('auth');await dashboard();});
 f.elements.code.autocomplete='one-time-code';f.elements.code.spellcheck=false;f.elements.code.focus();action(tr('cancel'),()=>{challenge='';login();});
}

function action(label,run,parent=app){const button=el('button',label,'secondary');button.type='button';button.addEventListener('click',async()=>{button.disabled=true;try{await run();}catch(e){notice(e.message);}finally{button.disabled=false;}});parent.append(button);}
function showObject(value){const pre=el('pre',JSON.stringify(value,null,2));app.append(pre);}
function supportLabels(){return {
 categories:{account:globalThis.UladimI18n.text("literal_b263deaaa324",{},"Аккаунт и вход"),sync:globalThis.UladimI18n.text("literal_cf34108b06d6",{},"Синхронизация"),billing:globalThis.UladimI18n.text("literal_83468da6409d",{},"Тарифы и доступ"),bug:globalThis.UladimI18n.text("literal_ed31a0a17db9",{},"Ошибка в приложении"),complaint:globalThis.UladimI18n.text("literal_f292c6bf6ad6",{},"Жалоба"),privacy:globalThis.UladimI18n.text("literal_57787002be54",{},"Приватность"),deletion:globalThis.UladimI18n.text("literal_10d87746ac09",{},"Удаление аккаунта"),other:globalThis.UladimI18n.text("literal_3a7dccc84e29",{},"Другой вопрос")},
 states:{open:globalThis.UladimI18n.text("literal_a26855d237c7",{},"Открыто"),waiting:globalThis.UladimI18n.text("literal_3f2ab13b3576",{},"Ожидает ответа"),resolved:globalThis.UladimI18n.text("literal_63f6302a4dc9",{},"Решено")},
 priorities:{low:globalThis.UladimI18n.text("literal_200f7ac84987",{},"Низкий"),normal:globalThis.UladimI18n.text("literal_7c0ef1469bce",{},"Обычный"),high:globalThis.UladimI18n.text("literal_e24b10ae3b50",{},"Высокий"),urgent:globalThis.UladimI18n.text("literal_ea86473b7a4c",{},"Срочный")}
};}
async function support(){
 const result=await api('support'),labels=supportLabels();
 heading(staff?globalThis.UladimI18n.text("literal_e86b4e596146",{},"Обращения и жалобы"):globalThis.UladimI18n.text("literal_f0012086d52e",{},"Поддержка"),staff?globalThis.UladimI18n.text("literal_33bd89e44c64",{},"Работайте с сообщениями, которые пользователь отправил сам. Личные задачи, финансы и заметки недоступны."):globalThis.UladimI18n.text("literal_6bca0ca893f6",{},"Не отправляйте пароли, коды, банковские выписки или личные документы."));
 const filters=el('div',undefined,'control-queue-filters'),list=el('div',undefined,'control-ticket-list');
 const selections={};
 for(const [name,title,choices]of [['state',globalThis.UladimI18n.text("literal_ca285db3dd75",{},"Состояние"),labels.states],['category',globalThis.UladimI18n.text("literal_ee7d0deed36d",{},"Тип обращения"),labels.categories]]){
  const label=el('label',title),select=el('select');select.id='support-filter-'+name;select.setAttribute('aria-label',title);label.htmlFor=select.id;
  const all=el('option',globalThis.UladimI18n.text("literal_215816bf4210",{},"Все"));all.value='';select.append(all);
  for(const [value,text]of Object.entries(choices)){const option=el('option',text);option.value=value;select.append(option);}
  add(filters,add(el('div'),label,select));selections[name]=select;
 }
 add(app,filters,list);
 function renderTickets(){
  list.replaceChildren();
  const tickets=(result.tickets||[]).filter(ticket=>(!selections.state.value||ticket.state===selections.state.value)&&(!selections.category.value||ticket.category===selections.category.value));
  if(!tickets.length)list.append(el('p',globalThis.UladimI18n.text("literal_d66419537f32",{},"Обращений по этим условиям пока нет."),'notice'));
  for(const ticket of tickets){
   const row=add(el('section',undefined,'card control-ticket'),el('p',(labels.categories[ticket.category]||ticket.category)+' · '+(labels.states[ticket.state]||ticket.state),'control-ticket-meta'),el('h2',ticket.subject));
   row.dataset.category=ticket.category;
   if(staff)row.append(el('p',globalThis.UladimI18n.text("literal_76d0cf10c184",{},"Приоритет: ")+(labels.priorities[ticket.priority]||ticket.priority),'small'));
   action(globalThis.UladimI18n.text("literal_e25d5ba3ebe6",{},"Открыть обращение"),()=>supportThread(ticket.id),row);list.append(row);
  }
 }
 Object.values(selections).forEach(select=>select.addEventListener('change',renderTickets));renderTickets();
 if((result.tickets||[]).length===100)app.append(el('p',globalThis.UladimI18n.text("literal_dab13558b56b",{},"Показаны 100 последних обращений."),'small'));
 if(!staff){
  const f=form(globalThis.UladimI18n.text("literal_cbcad7402b24",{},"Новое обращение"),[['subject',globalThis.UladimI18n.text("literal_682f961a0751",{},"Тема"),'text'],['message',globalThis.UladimI18n.text("literal_3e0ccd92fa15",{},"Сообщение"),'text']],globalThis.UladimI18n.text("literal_ceb68a9287da",{},"Отправить"),async b=>{await api('support',{...b,category:f.elements.category.value});await support();});
  selectField(f,'category',globalThis.UladimI18n.text("literal_ee7d0deed36d",{},"Тип обращения"),Object.entries(labels.categories));f.elements.category.value='other';f.elements.subject.maxLength=160;f.elements.message.maxLength=8000;
 }
}
async function supportThread(id){
 const [result,session]=await Promise.all([api('thread?id='+encodeURIComponent(id)),staff?api('session'):Promise.resolve(null)]),labels=supportLabels();
 heading(result.ticket.subject,(labels.categories[result.ticket.category]||result.ticket.category)+' · '+(labels.states[result.ticket.state]||result.ticket.state));
 const actions=el('div',undefined,'actions');app.append(actions);action(globalThis.UladimI18n.text("literal_66fedf25fcb1",{},"Все обращения"),support,actions);
 if(session?.permissions.includes('users.read'))action(globalThis.UladimI18n.text("literal_612f724ec00f",{},"Открыть аккаунт"),()=>staffUser(result.ticket.user_id),actions);
 const thread=el('section',undefined,'control-support-thread');app.append(thread);
 for(const message of result.messages){const item=panel(message.is_staff?globalThis.UladimI18n.text("literal_f0012086d52e",{},"Поддержка"):staff?globalThis.UladimI18n.text("literal_2a5c42af7c00",{},"Пользователь"):globalThis.UladimI18n.text("literal_041bfceecc8f",{},"Вы"),message.body);item.classList.add('support-message');item.dataset.staff=String(Boolean(message.is_staff));thread.append(item);}
 if(!staff||session.permissions.includes('support.reply')){
  const reply=form(globalThis.UladimI18n.text("literal_b9af23eeff5d",{},"Ответить"),[['message',globalThis.UladimI18n.text("literal_3e0ccd92fa15",{},"Сообщение"),'text']],globalThis.UladimI18n.text("literal_6508aa82af4a",{},"Отправить ответ"),async b=>{await api('support/reply',{...b,ticket_id:id,state:staff?'waiting':'open'});await supportThread(id);});reply.elements.message.maxLength=8000;
 }
 if(session?.permissions.includes('support.reply')){
  const triage=form(globalThis.UladimI18n.text("literal_faba2cfb80ef",{},"Состояние и приоритет"),[['reason',globalThis.UladimI18n.text("literal_ed03812f47ce",{},"Причина изменения для журнала"),'text']],globalThis.UladimI18n.text("literal_c82c8b3ba2ef",{},"Сохранить состояние"),async b=>{await api('support/triage',{ticket_id:id,priority:triage.elements.priority.value,state:triage.elements.state.value,reason:b.reason});await supportThread(id);});
  triage.classList.add('control-triage');triage.elements.reason.maxLength=500;
  selectField(triage,'priority',globalThis.UladimI18n.text("literal_0e5ac36d3f46",{},"Приоритет"),Object.entries(labels.priorities)).value=result.ticket.priority;
  selectField(triage,'state',globalThis.UladimI18n.text("literal_ca285db3dd75",{},"Состояние"),Object.entries(labels.states)).value=result.ticket.state;
 }
}
async function dashboard(){const session=await api('session');csrf=session.csrf;if(!staff){location.replace('/app');return;}controlNavigation=null;delete document.body.dataset.auth;heading(staff?globalThis.UladimI18n.text("literal_bc3e379e3e73",{},"Обзор сервиса"):globalThis.UladimI18n.text("literal_506d1e756366",{},"Ваш ULADIM"),staff?globalThis.UladimI18n.text("literal_7222d3680fa1",{},"Операционные показатели без доступа к личным записям пользователей."):session.email);const tabs=el('div',undefined,'tabs');app.append(tabs);action(globalThis.UladimI18n.text("literal_5690c2e63b9d",{},"Выйти"),async()=>{await api('logout',{});csrf='';login();},tabs);if(staff){controlNavigation=makeControlNavigation(session,tabs);app.append(controlOverview(session));if(session.permissions.includes('dashboard.read')){const data=await api('dashboard');const grid=el('div',undefined,'grid metrics');for(const [key,value]of Object.entries(data)){if(typeof value==='number'||value===null)grid.append(metricCard(key,value));}app.append(grid);}else notice(globalThis.UladimI18n.text("literal_4e0881874cb6",{},"Выберите доступный раздел."));}else{action(globalThis.UladimI18n.text("literal_f0012086d52e",{},"Поддержка"),support,tabs);action(globalThis.UladimI18n.text("literal_af3e10c88b50",{},"Аккаунт и приватность"),accountPrivacy,tabs);const ent=await api('entitlements');const grid=el('div',undefined,'grid');grid.append(panel(globalThis.UladimI18n.text("literal_d26e20d8ad2b",{},"Ваш доступ: ")+ent.tier,ent.billing_managed_by?globalThis.UladimI18n.text("literal_0b377e3c7368",{},"Управляется через ")+ent.billing_managed_by:globalThis.UladimI18n.text("literal_47d084a7f892",{},"Платёж не оформлен. Текущий доступ не означает платную подписку.")));grid.append(panel(globalThis.UladimI18n.text("literal_47e443cadb08",{},"Данные на устройстве"),globalThis.UladimI18n.text("literal_93ea9b01d6d8",{},"Личные записи остаются в зашифрованной базе Android. Кабинет не предоставляет к ним доступ.")));app.append(grid);const devices=await api('devices');app.append(el('h2',globalThis.UladimI18n.text("literal_2e29ee032cc0",{},"Устройства")));for(const device of devices.devices){const row=add(el('div',undefined,'row'),el('span',device.label||globalThis.UladimI18n.text("literal_dba20ab53801",{},"Устройство")),el('span',new Date(device.last_seen_at*1000).toLocaleString(authLanguage),'badge'));if(!device.revoked_at)action(globalThis.UladimI18n.text("literal_de1aec86abbf",{},"Отозвать доступ"),async()=>{heading(globalThis.UladimI18n.text("literal_0da26522986c",{},"Отозвать доступ устройства"));form(device.label,[['password',globalThis.UladimI18n.text("literal_065cafb3b330",{},"Ваш пароль"),'password']],globalThis.UladimI18n.text("literal_6b6b8fbd6925",{},"Подтвердить отзыв"),async b=>{await api('devices/revoke',{device_id:device.id,password:b.password});await dashboard();});},row);app.append(row);}notice(globalThis.UladimI18n.text("literal_a668164aa6e2",{},"Покупки пока отключены. Free, Plus и Premium используют единый серверный каталог."));}}
function publicNavigation(path,entry='guest') {
 const header=document.querySelector('body > header');
 const nav=header.querySelector('nav');
 const signIn=nav.querySelector('.public-signin')||nav.querySelector('a[href="/account"]');
 signIn.textContent=entry==='guest'?globalThis.UladimI18n.text("literal_8fc9ab2eeb38",{},"Войти"):entry==='signed-in'?globalThis.UladimI18n.text("literal_eadf6cc873e5",{},"Моё пространство"):globalThis.UladimI18n.text("literal_17cc8a5ee310",{},"Открыть ULADIM");
 signIn.href=entry==='guest'?'/account':'/app';
 signIn.classList.add('public-signin');
 const compactEntry=entry==='guest'?globalThis.UladimI18n.text("literal_8fc9ab2eeb38",{},"Войти"):globalThis.UladimI18n.text("literal_ea1f40824607",{},"Открыть");
 const existingControls=header.querySelector('.public-header-controls');
 if(existingControls){
  const mobileSignIn=existingControls.querySelector('a');
  mobileSignIn.textContent=compactEntry;mobileSignIn.href=signIn.href;
  return;
 }
 const apps=el('a',globalThis.UladimI18n.text("literal_39c4b42c8d11",{},"Приложения"));
 apps.href='/download';apps.dataset.i18n='literal_39c4b42c8d11';
 nav.insertBefore(apps,signIn);
 nav.id='public-navigation';
 for(const entry of nav.querySelectorAll('a')) {
  if(entry.pathname===path)entry.setAttribute('aria-current','page');
 }

 const controls=el('div',undefined,'public-header-controls');
 const mobileSignIn=signIn.cloneNode(true);
 mobileSignIn.textContent=compactEntry;
 const toggle=el('button',globalThis.UladimI18n.text("literal_122f71765026",{},"Меню"),'public-menu-toggle');
 toggle.type='button';toggle.dataset.i18n='literal_122f71765026';
 toggle.setAttribute('aria-controls',nav.id);
 toggle.setAttribute('aria-expanded','false');
 add(controls,mobileSignIn,toggle);
 header.insertBefore(controls,nav);
 header.classList.add('public-header');

 const close=()=>toggle.setAttribute('aria-expanded','false');
 toggle.addEventListener('click',()=>{
  toggle.setAttribute('aria-expanded',String(toggle.getAttribute('aria-expanded')!=='true'));
 });
 document.addEventListener('keydown',event=>{
  if(event.key==='Escape' && toggle.getAttribute('aria-expanded')==='true' && toggle.getClientRects().length) {
   close();
   toggle.focus();
  }
 });
 document.addEventListener('click',event=>{if(!header.contains(event.target))close();});
}
function isInstalledLaunch(){
 return navigator.standalone===true||matchMedia('(display-mode: standalone)').matches;
}
async function customerEntryStatus(){
 // Read the HttpOnly session; never infer account state from stored preferences.
 const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),3000);
 try{
  const response=await fetch('/account/api/session',{credentials:'same-origin',cache:'no-store',signal:controller.signal});
  if(response.status===401)return 'guest';
  if(!response.ok)return 'unavailable';
  const session=await response.json();
  return typeof session.user_id==='string'&&typeof session.email==='string'?'signed-in':'unavailable';
 }catch{return 'unavailable';}finally{clearTimeout(timer);}
}
function startLink(config) {
 if(config.entry==='signed-in')return link(globalThis.UladimI18n.text("literal_06b98ec4e641",{},"Открыть моё пространство"),'/app');
 if(config.entry==='unavailable')return link(globalThis.UladimI18n.text("literal_17cc8a5ee310",{},"Открыть ULADIM"),'/app');
 return config.registration_open ? link(globalThis.UladimI18n.text("literal_4c78b1822b88",{},"Создать аккаунт"),'/app?action=signup') : link(globalThis.UladimI18n.text("literal_17cc8a5ee310",{},"Открыть ULADIM"),'/app');
}
async function publicPage(config={}) {
 lastPublicConfig=config;
 publicExperience.configure(config.public_legal);
 const path=location.pathname;
 if(path==='/account') {
  try{await dashboard();}catch(e){if(e.code==='unauthorized'||e.code==='staff_unauthorized')login();else throw e;}
  return;
 }
 if(path==='/')config={...config,entry:await customerEntryStatus()};
 document.body.classList.add('product-site');
 publicNavigation(path,config.entry);
 if(path==='/'){await landing(config);return;}
 document.body.classList.add('focus-public');
 app.classList.add('product-content','focus-info');
 if(['/privacy','/terms'].includes(path)){publicExperience.legal(path);return;}
 if(path==='/early-access'){await earlyAccess();return;}
 if(path==='/docs') {
  heading(globalThis.UladimI18n.text("literal_70918141d80e",{},"Порядок в ваших делах"),globalThis.UladimI18n.text("literal_646a7b3c6654",{},"Записывайте задачи и идеи, планируйте события и ведите финансы в одном аккаунте. Для общих дел можно создать семейное пространство."));
  const links=el('nav',undefined,'guide-navigation');links.setAttribute('aria-label',globalThis.UladimI18n.text("literal_140ed324f282",{},"Разделы руководства"));
  for(const [label,href] of [[globalThis.UladimI18n.text("literal_b5b75c376dc8",{},"Начало работы"),'#first-record'],[globalThis.UladimI18n.text("literal_a95642d636d1",{},"Установка"),'#installation'],[globalThis.UladimI18n.text("literal_c39c1b4d5d52",{},"Импорт данных"),'#import'],[globalThis.UladimI18n.text("literal_a3ca1c94161e",{},"Вопросы и ответы"),'/faq']]){
   const jump=el('a',label);jump.href=href;links.append(jump);
  }
  const first=panel(globalThis.UladimI18n.text("literal_6da878c95d8d",{},"Начните с одной записи"),globalThis.UladimI18n.text("literal_bd5072b2079b",{},"Добавьте задачу, заметку или финансовый счёт в личном пространстве. Если хотите планировать вместе с близкими, создайте семейное пространство и пригласите их."));
  first.id='first-record';
  add(app,startLink(config),links,first);
  installGuide(app);
  importGuide(app);
  return;
 }
 if(path==='/faq'){publicExperience.faq();return;}
 if(path==='/download'){publicExperience.download();return;}
 if(path==='/support'){publicExperience.support();return;}
 if(path==='/delete-account'){publicExperience.deletion();return;}
 if(path==='/plans') {
  heading(globalThis.UladimI18n.text("literal_67540d638d82",{},"Место для ваших планов"),globalThis.UladimI18n.text("literal_b3cdec462745",{},"Начните бесплатно. Все текущие возможности доступны без подписки и банковской карты."));
  await planComparison(app);
  app.append(startLink(config));
  return;
 }
 const pages={
  '/support':[globalThis.UladimI18n.text("literal_1fabc98b1337",{},"Поможем разобраться"),globalThis.UladimI18n.text("literal_59b7cccc1734",{},"Войдите в аккаунт, чтобы отправить обращение и прочитать ответ."),globalThis.UladimI18n.text("literal_c286f88778ef",{},"Опишите, что вы пытались сделать и на каком шаге возникла проблема. Пароли, коды и банковские выписки для обращения не нужны.")],
  '/delete-account':[globalThis.UladimI18n.text("literal_10d87746ac09",{},"Удаление аккаунта"),globalThis.UladimI18n.text("literal_81299659ddfc",{},"Удаление облачного аккаунта и очистка локальной базы — разные действия. Эта операция не должна удалять данные других участников семьи."),globalThis.UladimI18n.text("literal_fb4c1e2aac6a",{},"Запрос на удаление доступен в кабинете и имеет 24-часовой срок отмены. Владение семьёй нужно заранее передать с согласием второго родителя. Сроки очистки резервных копий ещё не подтверждены.")],
  '/status':[globalThis.UladimI18n.text("literal_fb3af7870fa3",{},"Состояние сервиса"),globalThis.UladimI18n.text("literal_5371a22b5c09",{},"Если страница не загружается или синхронизация не завершается, повторите действие после восстановления соединения и обратитесь в поддержку. Эта страница не показывает внутренние метрики сервера."),globalThis.UladimI18n.text("literal_114507413f4e",{},"Локальные функции Android работают независимо от облачного аккаунта.")]
 };
 const [title,description,details]=pages[path];
 heading(title,description);
 app.append(panel(path==='/support'?globalThis.UladimI18n.text("literal_9755f4b567c5",{},"Как описать проблему"):globalThis.UladimI18n.text("literal_74740f3ee8dc",{},"Что важно знать"),details));
 if(path==='/support'||path==='/delete-account')app.append(link(globalThis.UladimI18n.text("literal_612f724ec00f",{},"Открыть аккаунт"),'/account'));
}
(async()=>{
 await Promise.resolve();
 try{authPacks=await (await fetch('/assets/locales.json',{cache:'no-store'})).json();}catch{}
 if(!authPacks[authLanguage])authLanguage='ru';
 await globalThis.UladimI18n.load(authPacks);globalThis.UladimI18n.setLanguage(authLanguage);window.UladimReferrals?.configureCopies(authPacks);globalLanguagePicker();
 if(!staff&&['/privacy','/terms','/faq','/support','/delete-account','/download'].includes(location.pathname)){
  await publicPage({});document.body.classList.remove('surface-loading');
  fetch('/account/api/config',{credentials:'same-origin',cache:'no-store'}).then(r=>r.ok?r.json():null).then(config=>{if(config?.public_legal)publicPage(config);}).catch(()=>{});
  return;
 }
 if(!staff&&location.pathname==='/'&&isInstalledLaunch()){location.replace('/app');return;}
 try {
  if(!staff&&location.pathname==='/'){
   // Initialize shared icon definitions, then paint before any network wait.
   await Promise.resolve();
   document.body.classList.add('product-site');
   publicNavigation('/','unavailable');
   await landing({entry:'unavailable'});
   document.body.classList.remove('surface-loading');
  }
  if(!Object.keys(authPacks).length)authPacks=await (await fetch('/assets/locales.json',{cache:'no-store'})).json();
  if(!authPacks[authLanguage])authLanguage='ru';
  if(staff) {
   try{await dashboard();}catch(e){if(e.code==='unauthorized'||e.code==='staff_unauthorized')login();else throw e;}
  }else{
   const config=await api('config');
   googleEnabled=Boolean(config.google_enabled);
   await publicPage(config);
  }
 }catch(e){heading(globalThis.UladimI18n.text("literal_209cd070147d",{},"Не удалось загрузить"));notice(e.message);}
 finally{document.body.classList.remove('surface-loading');}
})();

async function registration(){
 const config=await api('config');
 focusAuthHeading(tr('family_register'));
 const fields=[['email',tr('family_email'),'email'],['password',tr('family_password'),'password']];if(!config.registration_open)fields.push(['invitation',tr('family_invitation'),'text']);
 const f=form('',fields,tr('family_register'),async b=>{const email=b.email;try{await api('signup',b);}finally{f.elements.password.value='';b.password='';}heading(tr('family_verify'),tr('family_verify_hint'));
 form('',[['code',tr('family_code'),'text']],tr('family_verify'),async code=>{await api('confirm-signup',{email,code:code.code.trim()});login();notice(tr('account_done'));});action(tr('ux3_resend_verification'),async()=>{await api('resend-signup',{email});notice(tr('family_verify_hint'));});});
 if(config.google_enabled)action(tr('account_google_sign_in'),async()=>{const result=await api('google/start',{invitation:f.elements.invitation?.value});location.assign(result.authorization_url);});
 f.elements.password.autocomplete='new-password';window.UladimPassword?.attach(f.elements.password,()=>authLanguage);app.append(link(tr('account_privacy'),'/privacy',true));
}

const RECOVERY_COPY = globalThis.UladimI18n.copy("grp_ee9362a841fd",{
 ru: ['Восстановление пароля','Введите почту, которую используете в ULADIM.','Если аккаунт существует, код придёт на эту почту.','Отправить код','Сохранить пароль','Вернуться ко входу'],
 en: ['Reset your password','Enter the email you use for ULADIM.','If an account exists, a code will be sent to this email.','Send code','Save password','Back to sign in'],
 'uz-Latn': ['Parolni tiklash','ULADIM uchun ishlatadigan email manzilingizni kiriting.','Hisob mavjud bo‘lsa, shu manzilga kod yuboriladi.','Kodni yuborish','Parolni saqlash','Kirishga qaytish'],
 'uz-Cyrl': ['Паролни тиклаш','ULADIM учун ишлатадиган email манзилингизни киритинг.','Ҳисоб мавжуд бўлса, шу манзилга код юборилади.','Кодни юбориш','Паролни сақлаш','Киришга қайтиш']
});

function recovery(){
 const [title,intro,sent,send,save,back]=RECOVERY_COPY[authLanguage]||RECOVERY_COPY.en;
 const recoveryHeading=description=>{
  focusAuthHeading(title,description);
  const h=app.querySelector('h1');
  h.tabIndex=-1;
  h.focus();
 };
 const backToLogin=()=>{
  const links=el('div',undefined,'focus-login-links focus-recovery-links');
  action(back,login,links);
  app.append(links);
 };
 recoveryHeading(intro);
 form('',[['email',tr('family_email'),'email']],send,async b=>{
  const email=b.email;
  await api('recovery',{email});
  recoveryHeading(sent);
  const f=form('',[['code',tr('family_code'),'text'],['password',tr('family_new_password'),'password']],save,async value=>{
   try { await api('reset',{email,...value}); }
   finally { f.elements.password.value='';f.elements.code.value='';value.password='';value.code=''; }
   login();
   notice(tr('account_done'));
  });
  f.querySelector('h2').remove();
  f.elements.code.autocomplete='one-time-code';
  f.elements.password.autocomplete='new-password';window.UladimPassword?.attach(f.elements.password,()=>authLanguage);
  backToLogin();
 }).querySelector('h2').remove();
 backToLogin();
}

async function accountPrivacy(){location.assign('/app?settings=security');}
async function staffUsers(){heading(globalThis.UladimI18n.text("literal_845595d6e899",{},"Пользователи"),globalThis.UladimI18n.text("literal_0f6ca3e23abf",{},"Поиск только по ID или почте. Личные записи не доступны."));form(globalThis.UladimI18n.text("literal_180f58ab9753",{},"Поиск"),[['search',globalThis.UladimI18n.text("literal_ef375ca1bcc6",{},"ID или почта"),'text']],globalThis.UladimI18n.text("literal_be6156b8e4de",{},"Найти"),async b=>{const result=await api('users?search='+encodeURIComponent(b.search));const list=el('div',undefined,'grid');for(const user of result.users){const card=panel(user.email,user.verified?globalThis.UladimI18n.text("literal_759357b911db",{},"Почта подтверждена"):globalThis.UladimI18n.text("literal_023787f38ff9",{},"Почта не подтверждена"));action(globalThis.UladimI18n.text("literal_612f724ec00f",{},"Открыть аккаунт"),()=>staffUser(user.id),card);list.append(card);}app.append(list);});}
function selectField(form,name,label,choices){
  const caption=el('label',label);caption.htmlFor='select-'+name+'-'+crypto.randomUUID();
  const select=el('select');select.name=name;select.id=caption.htmlFor;
  for(const [value,title]of choices){const option=el('option',title);option.value=value;select.append(option);}
  form.insertBefore(caption,form.querySelector('button'));form.insertBefore(select,form.querySelector('button'));
  return select;
}
const sourceName=value=>({manual:globalThis.UladimI18n.text("literal_21cbcc331200",{},"Ручная выдача"),promo:globalThis.UladimI18n.text("literal_004afabb30ed",{},"Подарок / тест"),google_play:'Google Play',rustore:'RuStore',web:globalThis.UladimI18n.text("literal_fac9b5dbc1fd",{},"Веб-провайдер")}[value]||globalThis.UladimI18n.text("literal_5a6bcd471d70",{},"Бесплатный доступ"));
const accessUntil=value=>value?new Date(value*1000).toLocaleString(authLanguage):globalThis.UladimI18n.text("literal_5175176fcde0",{},"Без ограничения срока");
async function staffUser(id){
  const result=await api('user?id='+encodeURIComponent(id));const session=await api('session');const ent=result.entitlements;
  heading(result.user.email,globalThis.UladimI18n.text("literal_f8f8c3347a38",{},"Карточка аккаунта без финансов, заметок или семейного содержимого."));
  app.append(panel(globalThis.UladimI18n.text("literal_0a3f69dac71c",{},"Доступ: ")+ent.tier,sourceName(ent.source)+' · '+accessUntil(ent.valid_until)));
  app.append(el('p',result.user.verified?globalThis.UladimI18n.text("literal_759357b911db",{},"Почта подтверждена"):globalThis.UladimI18n.text("literal_023787f38ff9",{},"Почта не подтверждена")));
  if(session.permissions.includes('users.recover')&&result.user.verified&&id!==session.user_id&&(!result.user.disabled_until||result.user.disabled_until<=Math.floor(Date.now()/1000)))action(globalThis.UladimI18n.text("literal_c11c8ad8cfc2",{},"Отправить письмо восстановления"),()=>staffRecovery(id,result.user.email));
  for(const device of result.devices)app.append(panel(device.label,new Date(device.last_seen_at*1000).toLocaleString(authLanguage)));
  const canGrant=session.permissions.includes('plans.grant');
  app.append(el('h2',globalThis.UladimI18n.text("literal_2035bf8144d4",{},"История выдачи доступа")));
  if(!ent.grants.length)app.append(el('p',globalThis.UladimI18n.text("literal_99e38dff61b8",{},"Ручных выдач пока нет.")));
  for(const grant of ent.grants){
    const expired=grant.valid_until!==null&&grant.valid_until<=Math.floor(Date.now()/1000);
    const state=grant.revoked_at?globalThis.UladimI18n.text("literal_c9b3ac9dd940",{},"Отозван"):expired?globalThis.UladimI18n.text("literal_38af69011901",{},"Срок завершён"):globalThis.UladimI18n.text("literal_527028c7a1b1",{},"Действует");
    const card=panel(grant.tier+' · '+state,sourceName(grant.source)+' · '+accessUntil(grant.valid_until));
    card.append(el('p',grant.reason));app.append(card);
    if(canGrant&&!grant.revoked_at&&!expired)action(globalThis.UladimI18n.text("literal_b22fdc66f6e1",{},"Отозвать выдачу"),async()=>{
      heading(globalThis.UladimI18n.text("literal_2721327b1859",{},"Отозвать ручную выдачу"),grant.tier+' · '+sourceName(grant.source));
      notice(globalThis.UladimI18n.text("literal_0f1060bf117d",{},"Отзывается только эта выдача. Другие действующие основания сохранятся. Списание или отмена магазинной подписки не выполняются."));
      form(globalThis.UladimI18n.text("literal_8f57aeaadbed",{},"Подтверждение отзыва"),[['reason',globalThis.UladimI18n.text("literal_276b853ba897",{},"Причина отзыва"),'text']],globalThis.UladimI18n.text("literal_578b099c6f33",{},"Подтвердить отзыв выдачи"),async b=>{
        await api('revoke-grant',{grant_id:grant.id,reason:b.reason});await staffUser(id);
      });
      action(globalThis.UladimI18n.text("literal_7c47f7292ba4",{},"Отменить"),async()=>staffUser(id));
    },card);
  }
  if(canGrant){
    const f=form(globalThis.UladimI18n.text("literal_e5f0d08fbb9a",{},"Выдать тестовый доступ"),[['reason',globalThis.UladimI18n.text("literal_b9d0ebee3d71",{},"Причина выдачи"),'text']],globalThis.UladimI18n.text("literal_0d6da455684f",{},"Выдать доступ"),async b=>{
      const days=f.elements.duration.value;
      await api('grant',{user_id:id,tier:f.elements.tier.value,source:f.elements.source.value,
        valid_until:days==='unlimited'?null:Math.floor(Date.now()/1000)+Number(days)*86400,reason:b.reason});
      await staffUser(id);
    });
    selectField(f,'tier',globalThis.UladimI18n.text("literal_7f67af3d6cd9",{},"Уровень"),[['Plus','Plus']]);
    f.append(el('p',globalThis.UladimI18n.text("literal_0f1b808d7bf0",{},"Premium и ИИ пока недоступны. Текущие рабочие возможности открыты бесплатно."),'small'));
    selectField(f,'source',globalThis.UladimI18n.text("literal_0369683b41e6",{},"Основание"),[['manual',globalThis.UladimI18n.text("literal_21cbcc331200",{},"Ручная выдача")],['promo',globalThis.UladimI18n.text("literal_004afabb30ed",{},"Подарок / тест")]]);
    selectField(f,'duration',globalThis.UladimI18n.text("literal_a1db8374181a",{},"Срок доступа"),[['30',globalThis.UladimI18n.text("literal_254d55672b1d",{},"30 дней")],['90',globalThis.UladimI18n.text("literal_add2e2fe3047",{},"90 дней")],['365',globalThis.UladimI18n.text("literal_b4061c863603",{},"1 год")],['unlimited',globalThis.UladimI18n.text("literal_5175176fcde0",{},"Без ограничения срока")]]);
    notice(globalThis.UladimI18n.text("literal_ad53fdb61bac",{},"Это ручная выдача доступа. Платёж и магазинная подписка не создаются."));
  }
  if(session.permissions.includes('users.moderate')){
    const services=[['account',globalThis.UladimI18n.text("literal_f0a4daddb0a6",{},"Весь аккаунт")],['family_write',globalThis.UladimI18n.text("literal_2d4a000c5fda",{},"Изменения в семье")],['premium',globalThis.UladimI18n.text("literal_3bba5d534a7f",{},"Премиальные сервисы")],['support_write',globalThis.UladimI18n.text("literal_eba33a087b63",{},"Новые сообщения поддержки")]];
    const holds={...ent.holds};if(result.user.disabled_until>Math.floor(Date.now()/1000))holds.account=result.user.disabled_until;
    app.append(el('h2',globalThis.UladimI18n.text("literal_f82ed31d74f8",{},"Ограничения и модерация")),el('p',globalThis.UladimI18n.text("literal_d0cc8cc6ba5f",{},"Ограничения временные и не удаляют записи. Каждое действие сохраняется в журнале с причиной."),'small'));
    if(!Object.keys(holds).length)app.append(el('p',globalThis.UladimI18n.text("literal_42e605b241dc",{},"Активных ограничений нет."),'control-no-holds'));
    for(const [service,until]of Object.entries(holds)){
      const name=services.find(row=>row[0]===service)?.[1]||service;
      const card=panel(globalThis.UladimI18n.text("literal_d7a67d2d76c6",{},"Ограничение: ")+name,globalThis.UladimI18n.text("literal_5a347316dd36",{},"До ")+accessUntil(until));app.append(card);
      action(globalThis.UladimI18n.text("literal_20f2098bb371",{},"Снять ограничение"),async()=>{
        heading(globalThis.UladimI18n.text("literal_34968b4156da",{},"Снять ограничение: ")+name,globalThis.UladimI18n.text("literal_a34635daa7ef",{},"Снятие не удалит историю и другие ограничения."));
        form(globalThis.UladimI18n.text("literal_8fe12b16bfd7",{},"Подтверждение"),[['reason',globalThis.UladimI18n.text("literal_cc431f267cc0",{},"Причина снятия"),'text']],globalThis.UladimI18n.text("literal_4e55d2f9db19",{},"Подтвердить снятие"),async b=>{
          await api('moderate',{user_id:id,service,until_at:0,reason:b.reason});await staffUser(id);
        });action(globalThis.UladimI18n.text("literal_7c47f7292ba4",{},"Отменить"),async()=>staffUser(id));
      },card);
    }
    const f=form(globalThis.UladimI18n.text("literal_010a77879265",{},"Временное ограничение"),[['reason',globalThis.UladimI18n.text("literal_bd6b83ad106a",{},"Обязательная причина"),'text']],globalThis.UladimI18n.text("literal_6b41980e6102",{},"Применить ограничение"),async b=>{
      await api('moderate',{user_id:id,service:f.elements.service.value,until_at:Math.floor(Date.now()/1000)+Number(f.elements.duration.value),reason:b.reason});await staffUser(id);
    });f.classList.add('control-moderation');f.elements.reason.maxLength=500;
    const service=selectField(f,'service',globalThis.UladimI18n.text("literal_f0e96a2c5753",{},"Ограничиваемый сервис"),services);service.value='family_write';
    selectField(f,'duration',globalThis.UladimI18n.text("literal_24c13957f94f",{},"Срок ограничения"),[['86400',globalThis.UladimI18n.text("literal_7941488fa3af",{},"24 часа")],['604800',globalThis.UladimI18n.text("literal_7867a2095f60",{},"7 дней")],['2592000',globalThis.UladimI18n.text("literal_254d55672b1d",{},"30 дней")]]);
    const warning=el('p',globalThis.UladimI18n.text("literal_fd1e29b704ed",{},"Блокировка всего аккаунта завершит его активные сеансы. Данные сохранятся."),'notice');warning.hidden=true;f.insertBefore(warning,f.querySelector('button'));service.addEventListener('change',()=>{warning.hidden=service.value!=='account';});
  }
}

async function staffTeam(){const result=await api('staff');const session=await api('session');heading(globalThis.UladimI18n.text("literal_e9f5abaae55c",{},"Команда Control"),globalThis.UladimI18n.text("literal_237909752909",{},"Права ограничены ролью и проверяются сервером при каждом действии. Для каждого сотрудника обязателен MFA."));for(const member of result.staff){const card=panel(member.email,member.roles.join(' · '));card.append(el('span',member.active?globalThis.UladimI18n.text("literal_14471cfe57f8",{},"Доступ активен"):globalThis.UladimI18n.text("literal_06f373b9a35d",{},"Доступ отозван"),'badge'));app.append(card);if(!member.roles.includes('owner')&&member.id!==session.staff_id)action(globalThis.UladimI18n.text("literal_589d87db3a42",{},"Изменить права"),async()=>{heading(member.email);const f=form(globalThis.UladimI18n.text("literal_feade646bba8",{},"Права сотрудника"),[['reason',globalThis.UladimI18n.text("literal_bd6b83ad106a",{},"Обязательная причина"),'text']],globalThis.UladimI18n.text("literal_116869de9ecb",{},"Сохранить и отозвать сессии"),async b=>{await api('staff/update',{staff_id:member.id,roles:[f.elements.role.value],active:f.elements.active.checked,revision:member.revision,reason:b.reason});await staffTeam();});roleSelect(f,session.roles.includes('owner'));const l=el('label',globalThis.UladimI18n.text("literal_14471cfe57f8",{},"Доступ активен"));const checkbox=el('input');checkbox.type='checkbox';checkbox.name='active';checkbox.checked=!!member.active;l.append(checkbox);f.insertBefore(l,f.querySelector('button'));},card);}const f=form(globalThis.UladimI18n.text("literal_7ec79166913b",{},"Пригласить сотрудника"),[['email',globalThis.UladimI18n.text("literal_364080f170fa",{},"Почта получателя"),'email'],['reason',globalThis.UladimI18n.text("literal_d49d15ccc86d",{},"Причина приглашения"),'text']],globalThis.UladimI18n.text("literal_2ba2bcfbf488",{},"Создать приглашение"),async b=>{const result=await api('staff/invite',{email:b.email,roles:[f.elements.role.value],reason:b.reason});heading(globalThis.UladimI18n.text("literal_c8558deeb515",{},"Приглашение создано"),globalThis.UladimI18n.text("literal_b7e6c0696b3e",{},"Передайте код только выбранному получателю по защищённому каналу. Он должен войти в свой подтверждённый аккаунт и настроить MFA. Срок — 24 часа."));const code=el('textarea');code.readOnly=true;code.value=result.invitation;code.setAttribute('aria-label',globalThis.UladimI18n.text("literal_d41e207576c2",{},"Одноразовое приглашение"));app.append(code);});roleSelect(f,session.roles.includes('owner'));}
function roleSelect(form,owner){const label=el('label',globalThis.UladimI18n.text("literal_ebd4563f5ac7",{},"Роль"));label.htmlFor='role-select';const select=el('select');select.name='role';select.id='role-select';const roles={support:globalThis.UladimI18n.text("literal_f0012086d52e",{},"Поддержка"),moderator:globalThis.UladimI18n.text("literal_94166e547005",{},"Модератор"),billing_manager:globalThis.UladimI18n.text("literal_266d9aff666f",{},"Управление доступом"),auditor:globalThis.UladimI18n.text("literal_e85778a3959e",{},"Аудитор"),admin:globalThis.UladimI18n.text("literal_6c7719973e58",{},"Администратор")};for(const [value,title]of Object.entries(roles)){if(value==='admin'&&!owner)continue;const option=el('option',title);option.value=value;select.append(option);}form.insertBefore(label,form.querySelector('button'));form.insertBefore(select,form.querySelector('button'));}

const ANNOUNCEMENT_FORMATS=()=>([['inbox',globalThis.UladimI18n.text("literal_6e032dfc75da",{},"В центре уведомлений"),globalThis.UladimI18n.text("literal_ac9ef9be4cda",{},"Сообщение в истории. Без показа при входе.")],['banner',globalThis.UladimI18n.text("literal_c5f82bac7e71",{},"Баннер при входе"),globalThis.UladimI18n.text("literal_9a04fd13d828",{},"Компактное сообщение над обзором.")],['fullscreen',globalThis.UladimI18n.text("literal_6691f520fb66",{},"Полный экран при входе"),globalThis.UladimI18n.text("literal_a57d77a2bf3f",{},"Отдельное сообщение с кнопкой продолжения.")]]);
function announcementPreview(item){
 const area=el('section',undefined,'control-announcement-preview');area.dataset.format=item.presentation||'inbox';area.setAttribute('aria-label',globalThis.UladimI18n.text("literal_471539e85de2",{},"Предварительный просмотр"));
 const frame=el('div',undefined,'control-preview-frame'),sample=el('div',undefined,'control-preview-message');
 add(sample,el('p','ULADIM','eyebrow'),el('h3',item.title||globalThis.UladimI18n.text("literal_c246f42e4eb4",{},"Заголовок сообщения")),el('p',item.body||globalThis.UladimI18n.text("literal_75c253feb717",{},"Текст сообщения появится здесь."),'control-preview-body'));
 if(item.link)add(sample,el('span',globalThis.UladimI18n.text("literal_ea1f40824607",{},"Открыть"),'control-preview-button'));
 if(item.presentation==='fullscreen')add(sample,el('span',globalThis.UladimI18n.text("literal_a42aee58d60a",{},"Продолжить"),'control-preview-button'));
 if(item.presentation==='banner')sample.append(el('span','×','control-preview-close'));
 if(item.presentation==='inbox')frame.append(el('p',globalThis.UladimI18n.text("literal_d4baf8f6b173",{},"Уведомления"),'control-preview-caption'));
 else frame.append(el('p',globalThis.UladimI18n.text("literal_b688b4c0d783",{},"Сегодня"),'control-preview-caption'));
 frame.append(sample);area.append(frame);return area;
}
function announcementDate(value){return value?new Date(value*1000).toLocaleString(authLanguage):globalThis.UladimI18n.text("literal_2dee72ef4816",{},"Сразу после публикации");}
async function staffAnnouncements(){
 const result=await api('announcements');heading(globalThis.UladimI18n.text("literal_d4baf8f6b173",{},"Уведомления"),globalThis.UladimI18n.text("literal_63b4410ee857",{},"Сообщения в приложении: история, баннер или полный экран при входе."));
 const tools=el('div',undefined,'actions');action(globalThis.UladimI18n.text("literal_d8379a6b2215",{},"Новое сообщение"),announcementCompose,tools);app.append(tools);
 if(!result.announcements.length){notice(globalThis.UladimI18n.text("literal_e403d427d50a",{},"Сообщений пока нет. Начните с проверки только для своего аккаунта."));return;}
 const states={draft:globalThis.UladimI18n.text("literal_65fd24f1cb37",{},"Черновик"),published:globalThis.UladimI18n.text("literal_382ded9c6877",{},"Опубликовано"),cancelled:globalThis.UladimI18n.text("literal_23a2a9bfcf74",{},"Отменено")},list=el('div',undefined,'control-announcement-list');app.append(list);
 for(const item of result.announcements){const row=el('section',undefined,'card control-announcement-row');add(row,el('p',(states[item.state]||item.state)+' · '+(ANNOUNCEMENT_FORMATS().find(format=>format[0]===item.presentation)?.[1]||globalThis.UladimI18n.text("literal_6e032dfc75da",{},"В центре уведомлений")),'small'),el('h2',item.title),el('p',item.body,'control-preview-body'),el('p',(item.audience==='all'?globalThis.UladimI18n.text("literal_d308ab1735e5",{},"Все подтверждённые аккаунты"):globalThis.UladimI18n.text("literal_5f360857875b",{},"Выбранные аккаунты"))+globalThis.UladimI18n.text("literal_938897e4633e",{}," · получателей: ")+item.recipient_count+' · '+announcementDate(item.starts_at),'small'));const controls=el('div',undefined,'actions');if(item.state==='draft')action(globalThis.UladimI18n.text("literal_0d54787744b2",{},"Проверить публикацию"),()=>announcementReview(item),controls);if(item.state==='published')action(globalThis.UladimI18n.text("literal_6f4d7594f834",{},"Остановить показ"),()=>announcementCancel(item),controls);row.append(controls);list.append(row);}
}
async function announcementCompose(){
 const session=await api('session');heading(globalThis.UladimI18n.text("literal_d8379a6b2215",{},"Новое сообщение"),globalThis.UladimI18n.text("literal_ef249e2e45e2",{},"Сначала сохраните черновик и проверьте получателей. По умолчанию сообщение увидите только вы."));
 const layout=el('div',undefined,'control-announcement-layout'),f=el('form',undefined,'panel control-announcement-form'),preview=el('aside',undefined,'control-announcement-preview-host');add(app,layout);add(layout,f,preview);
 const addField=(name,label,type='text',required=true)=>{const wrap=el('div',undefined,'control-announcement-field'),l=el('label',label),n=el(type==='textarea'?'textarea':'input');n.id='announcement-'+name;l.htmlFor=n.id;n.name=name;if(type!=='textarea')n.type=type;n.required=required;add(wrap,l,n);f.append(wrap);return n;};
 const title=addField('title',globalThis.UladimI18n.text("literal_5f77cb92e071",{},"Заголовок"));title.maxLength=160;
 const body=addField('body',globalThis.UladimI18n.text("literal_eb8051efbc7e",{},"Текст сообщения"),'textarea');body.maxLength=4000;body.rows=7;
 const format=el('fieldset',undefined,'control-announcement-choice');format.append(el('legend',globalThis.UladimI18n.text("literal_3d1d6f2f1f9a",{},"Где показать")));f.append(format);
 for(const [value,label,hint]of ANNOUNCEMENT_FORMATS()){const option=el('label'),radio=el('input');radio.type='radio';radio.name='presentation';radio.value=value;radio.setAttribute('aria-label',label);radio.checked=value==='inbox';add(option,radio,add(el('span'),el('strong',label),el('small',hint)));format.append(option);}
 const audience=el('fieldset',undefined,'control-announcement-choice');audience.append(el('legend',globalThis.UladimI18n.text("literal_ae0e8e65022e",{},"Получатели")));f.append(audience);
 for(const [value,label,hint]of [['self',globalThis.UladimI18n.text("literal_8535da5b574e",{},"Только мне — проверка"),globalThis.UladimI18n.text("literal_1d04bb66103e",{},"Один ваш аккаунт. Другие пользователи не получат сообщение.")],['users',globalThis.UladimI18n.text("literal_5f360857875b",{},"Выбранные аккаунты"),globalThis.UladimI18n.text("literal_3ad9a824043b",{},"До 100 проверенных идентификаторов аккаунтов.")],['all',globalThis.UladimI18n.text("literal_d308ab1735e5",{},"Все подтверждённые аккаунты"),globalThis.UladimI18n.text("literal_1a5212c3976f",{},"Публикация для всех потребует отдельного подтверждения.")]]){const option=el('label'),radio=el('input');radio.type='radio';radio.name='audience';radio.value=value;radio.setAttribute('aria-label',label);radio.checked=value==='self';add(option,radio,add(el('span'),el('strong',label),el('small',hint)));audience.append(option);}
 const recipients=addField('user_ids',globalThis.UladimI18n.text("literal_3b24c1025094",{},"ID аккаунтов — по одному на строку"),'textarea',false);recipients.rows=3;recipients.parentElement.hidden=true;
 const link=addField('link',globalThis.UladimI18n.text("literal_8a6db7c9755c",{},"Ссылка в ULADIM — необязательно"),'text',false);link.placeholder='/app';link.maxLength=512;
 const timing=el('details',undefined,'control-announcement-timing');timing.append(el('summary',globalThis.UladimI18n.text("literal_375557e2eb68",{},"Время показа и срок")));f.append(timing);
 const starts=addField('starts_at',globalThis.UladimI18n.text("literal_97546ab5ef96",{},"Начало показа — необязательно"),'datetime-local',false),expires=addField('expires_at',globalThis.UladimI18n.text("literal_dad9300bf19d",{},"Завершение показа — необязательно"),'datetime-local',false);timing.append(starts.parentElement,expires.parentElement);timing.append(el('p',globalThis.UladimI18n.text("literal_f56ac1bd2d40",{},"Без даты сообщение доступно сразу на 30 дней. Запланировать можно на 30 дней вперёд, срок показа — до 90 дней."),'small'));
 const reason=addField('reason',globalThis.UladimI18n.text("literal_09304513f121",{},"Причина для журнала аудита"));reason.maxLength=500;
 const feedback=el('p','','control-announcement-feedback');feedback.setAttribute('role','status');const submit=el('button',globalThis.UladimI18n.text("literal_6a4e14990b20",{},"Сохранить черновик"));submit.type='submit';add(f,feedback,submit);
 const draft=()=>({title:title.value.trim(),body:body.value.trim(),presentation:f.elements.presentation.value,audience:f.elements.audience.value==='all'?'all':'users',user_ids:f.elements.audience.value==='self'?[session.user_id]:f.elements.audience.value==='users'?[...new Set(recipients.value.split(/[\s,;]+/).filter(Boolean))]:[],link:link.value.trim(),...(starts.value?{starts_at:Math.floor(new Date(starts.value).getTime()/1000)}:{}),...(expires.value?{expires_at:Math.floor(new Date(expires.value).getTime()/1000)}:{}),reason:reason.value.trim()});
 const draw=()=>{recipients.parentElement.hidden=f.elements.audience.value!=='users';recipients.required=f.elements.audience.value==='users';preview.replaceChildren(el('h2',globalThis.UladimI18n.text("literal_32060a34f5be",{},"Предпросмотр")),announcementPreview(draft()),el('p',globalThis.UladimI18n.text("literal_646a07e99d54",{},"Показ при входе не прерывает ввод и открытые формы. После закрытия сообщение остаётся в истории."),'small'));};
 f.addEventListener('input',draw);f.addEventListener('change',draw);draw();
 f.addEventListener('submit',async event=>{event.preventDefault();if(!f.reportValidity())return;submit.disabled=true;feedback.textContent=globalThis.UladimI18n.text("literal_ad1536bcf646",{},"Проверяем сообщение…");try{const payload=draft();if(payload.user_ids.some(id=>!id))throw new Error(globalThis.UladimI18n.text("literal_9f59c396f919",{},"Не удалось определить ваш аккаунт. Обновите страницу."));if(payload.link&&!/^\/app(?:[/?#]|$)/.test(payload.link))throw new Error(globalThis.UladimI18n.text("literal_effa23fb147e",{},"Укажите внутреннюю ссылку, начинающуюся с /app."));await api('announcements/preview',payload);const saved=await api('announcements',payload);await announcementReview({...saved,reason:payload.reason});}catch(error){feedback.className='error control-announcement-feedback';feedback.textContent=error.message;}finally{submit.disabled=false;}});
 const cancel=el('button',globalThis.UladimI18n.text("literal_00cf11520cc7",{},"Назад к черновикам"),'secondary');cancel.type='button';cancel.addEventListener('click',()=>staffAnnouncements().catch(error=>{feedback.textContent=error.message;}));f.append(cancel);title.focus({preventScroll:true});
}
async function announcementReview(item){
 heading(globalThis.UladimI18n.text("literal_099a20316798",{},"Проверьте публикацию"),globalThis.UladimI18n.text("literal_4b4e487b919c",{},"Черновик сохранён. Сообщение ещё не отправлено."));
 const layout=el('div',undefined,'control-announcement-layout'),summary=el('section',undefined,'card control-publish-summary');add(app,layout);add(layout,summary,announcementPreview(item));
 add(summary,el('h2',item.title),el('p',item.body,'control-preview-body'));
 const rows=[[globalThis.UladimI18n.text("literal_ae0e8e65022e",{},"Получатели"),item.audience==='all'?globalThis.UladimI18n.text("literal_d308ab1735e5",{},"Все подтверждённые аккаунты"):globalThis.UladimI18n.text("literal_07337285d78b",{},"Только выбранные аккаунты")],[globalThis.UladimI18n.text("literal_7f32bcb38b55",{},"Количество получателей"),String(item.recipient_count)],[globalThis.UladimI18n.text("literal_63fdd980cf43",{},"Формат"),ANNOUNCEMENT_FORMATS().find(format=>format[0]===item.presentation)?.[1]||item.presentation],[globalThis.UladimI18n.text("literal_a3a589a97264",{},"Начало показа"),announcementDate(item.starts_at)],[globalThis.UladimI18n.text("literal_b2ca159ea1c8",{},"Завершение показа"),announcementDate(item.expires_at)],[globalThis.UladimI18n.text("literal_f4cb2c0e2410",{},"Ссылка"),item.link||globalThis.UladimI18n.text("literal_f47146b39965",{},"Без ссылки")]];
 if(item.audience!=='all')rows.splice(2,0,[globalThis.UladimI18n.text("literal_998ea633d145",{},"ID аккаунтов"),(item.user_ids||[]).join('\n')]);
 const details=el('dl');for(const [label,value]of rows)add(details,el('dt',label),el('dd',value));summary.append(details);
 const f=el('form',undefined,'control-publish-form');summary.append(f);const reason=field(f,'reason',globalThis.UladimI18n.text("literal_09304513f121",{},"Причина для журнала аудита"));reason.value=item.reason||'';reason.maxLength=500;
 const phrase=globalThis.UladimI18n.text("literal_c1cb78bfd8f7",{},"ВСЕМ ")+item.recipient_count;let confirmation=null;if(item.audience==='all'){f.append(el('p',globalThis.UladimI18n.text("literal_7f70e724a5d1",{},"Это сообщение увидят все подтверждённые аккаунты (")+item.recipient_count+globalThis.UladimI18n.text("literal_0279a999a961",{},"). Проверьте текст, формат и время."),'notice'));confirmation=field(f,'confirmation',globalThis.UladimI18n.text("literal_b4afd99ff058",{},"Введите ")+phrase);confirmation.autocomplete='off';confirmation.addEventListener('input',()=>{publish.disabled=confirmation.value!==phrase;});}
 const feedback=el('p');feedback.setAttribute('role','status');const publish=el('button',globalThis.UladimI18n.text("literal_4d0fa33cdbdd",{},"Опубликовать"));publish.type='submit';publish.disabled=Boolean(confirmation);add(f,feedback,publish);
 const back=el('button',globalThis.UladimI18n.text("literal_00cf11520cc7",{},"Назад к черновикам"),'secondary');back.type='button';back.addEventListener('click',()=>staffAnnouncements().catch(error=>{feedback.textContent=error.message;}));f.append(back);
 f.addEventListener('submit',async event=>{event.preventDefault();if(!f.reportValidity()||confirmation&&confirmation.value!==phrase)return;publish.disabled=true;try{const current=await api('announcements/preview',{title:item.title,body:item.body,presentation:item.presentation,audience:item.audience,user_ids:item.user_ids||[],starts_at:item.starts_at,expires_at:item.expires_at,link:item.link,reason:reason.value.trim()});if(current.recipient_count!==item.recipient_count){await announcementReview({...item,recipient_count:current.recipient_count,reason:reason.value.trim()});notice(globalThis.UladimI18n.text("literal_8c5a659c2cd3",{},"Количество получателей изменилось. Проверьте и подтвердите обновлённую аудиторию."));return;}const result=await api('announcements/publish',{id:item.id,revision:item.revision,reason:reason.value.trim()});heading(globalThis.UladimI18n.text("literal_382ded9c6877",{},"Опубликовано"),globalThis.UladimI18n.text("literal_dd4e7a00432e",{},"Сообщение будет доступно выбранным получателям в указанное время."));app.append(panel(result.title,globalThis.UladimI18n.text("literal_5b29a31c2937",{},"Получателей: ")+result.recipient_count));action(globalThis.UladimI18n.text("literal_d9a2f9662dac",{},"К уведомлениям"),staffAnnouncements);}catch(error){feedback.className='error';feedback.textContent=error.message;}finally{publish.disabled=Boolean(confirmation&&confirmation.value!==phrase);}});
}
function announcementCancel(item){heading(globalThis.UladimI18n.text("literal_523b2b058f79",{},"Остановить показ?"),item.title);form(globalThis.UladimI18n.text("literal_2cf5f825d875",{},"Сообщение останется в истории получателей."),[['reason',globalThis.UladimI18n.text("literal_09304513f121",{},"Причина для журнала аудита"),'text']],globalThis.UladimI18n.text("literal_b1036004aa21",{},"Подтвердить остановку"),async body=>{await api('announcements/cancel',{id:item.id,revision:item.revision,reason:body.reason});await staffAnnouncements();});action(globalThis.UladimI18n.text("literal_00cf11520cc7",{},"Назад к черновикам"),staffAnnouncements);}


async function staffRecordRecovery(before=''){
 const result=await api('record-recovery'+(before?'?before='+encodeURIComponent(before):''));if(!Array.isArray(result.requests))throw new Error(globalThis.UladimI18n.text("literal_b738bc09bd2d",{},"Не удалось загрузить запросы."));
 heading(globalThis.UladimI18n.text("literal_b64517fcec2e",{},"Запросы восстановления"),globalThis.UladimI18n.text("literal_44e93c66b7eb",{},"Содержимое удалённых записей скрыто. Одобрение разрешает владельцу выполнить восстановление самостоятельно."));
 const status=el('p','','control-recovery-status');status.setAttribute('role','status');app.append(status);const filters=el('div',undefined,'actions control-recovery-filters'),list=el('div',undefined,'control-recovery-list');let filter='pending';
 const states={pending:globalThis.UladimI18n.text("literal_4800516916e2",{},"Ожидает проверки"),approved:globalThis.UladimI18n.text("literal_c11870baed2e",{},"Одобрен"),rejected:globalThis.UladimI18n.text("literal_aba57c13e094",{},"Отклонён"),cancelled:globalThis.UladimI18n.text("literal_c9b3ac9dd940",{},"Отозван"),completed:globalThis.UladimI18n.text("literal_778cf49f34b2",{},"Восстановлен")},kinds={note:globalThis.UladimI18n.text("literal_025e14681a4c",{},"Заметка"),task:globalThis.UladimI18n.text("literal_b9ce27191d40",{},"Задача"),event:globalThis.UladimI18n.text("literal_4212693d845d",{},"Событие"),account:globalThis.UladimI18n.text("literal_54121f46afa0",{},"Счёт"),transaction:globalThis.UladimI18n.text("literal_822d93cab5c7",{},"Операция"),budget:globalThis.UladimI18n.text("literal_84e960d40ad5",{},"Бюджет"),transfer:globalThis.UladimI18n.text("literal_c581c83538fb",{},"Перевод"),shopping:globalThis.UladimI18n.text("literal_651f75da9874",{},"Список покупок"),request:globalThis.UladimI18n.text("literal_9169085063e9",{},"Денежный запрос")};
 const pendingButton=el('button',globalThis.UladimI18n.text("literal_b40581a7156f",{},"Ожидают"),'secondary'),allButton=el('button',globalThis.UladimI18n.text("literal_2d23dcbc20b2",{},"Все запросы"),'secondary');for(const b of [pendingButton,allButton])b.type='button';add(filters,pendingButton,allButton);add(app,filters,list);
 function draw(){list.replaceChildren();pendingButton.setAttribute('aria-pressed',String(filter==='pending'));allButton.setAttribute('aria-pressed',String(filter==='all'));const visible=result.requests.filter(item=>filter==='all'||item.state==='pending');if(!visible.length)list.append(el('p',result.next_before?globalThis.UladimI18n.text("literal_1c913bbec242",{},"В этой части списка нет ожидающих запросов."):globalThis.UladimI18n.text("literal_d124afecf1ab",{},"Запросов по этим условиям пока нет."),'notice'));
  for(const item of visible){const card=el('section',undefined,'card control-recovery-card'),expired=item.expires_at*1000<=Date.now();add(card,el('p',(states[item.state]||globalThis.UladimI18n.text("literal_e08bc1c8b18c",{},"Запрос"))+(expired&&item.state!=='completed'?globalThis.UladimI18n.text("literal_afa561fc4d0f",{}," · срок завершён"):''),'small'),el('h2',kinds[item.kind]||globalThis.UladimI18n.text("literal_1d80e1757a7a",{},"Запись")));
   const metadata=el('dl');for(const [label,value]of [[globalThis.UladimI18n.text("literal_e2c19d1b1363",{},"ID запроса"),item.id],[globalThis.UladimI18n.text("literal_ac6955643960",{},"ID аккаунта"),item.user_id],[globalThis.UladimI18n.text("literal_d73726444ac1",{},"ID пространства"),item.workspace_id],[globalThis.UladimI18n.text("literal_a1d21ea2bf16",{},"ID записи"),item.record_id],[globalThis.UladimI18n.text("literal_6cf5abc4da1e",{},"Создан"),announcementDate(item.created_at)],[globalThis.UladimI18n.text("literal_97b8783453d5",{},"Действует до"),announcementDate(item.expires_at)]])add(metadata,el('dt',label),el('dd',String(value)));card.append(metadata);
   if(item.state==='pending'&&!expired){const open=el('button',globalThis.UladimI18n.text("literal_da5f8f3e147a",{},"Рассмотреть запрос"),'secondary');open.type='button';open.addEventListener('click',()=>{open.hidden=true;const f=el('form',undefined,'control-recovery-review');f.append(el('p',globalThis.UladimI18n.text("literal_dab8e0c80344",{},"Согласие относится к выбранной версии записи. Сотрудник не получает содержимое и не восстанавливает запись от имени владельца."),'small'));const reason=field(f,'reason',globalThis.UladimI18n.text("literal_09304513f121",{},"Причина для журнала аудита"));reason.maxLength=500;const feedback=el('p');feedback.setAttribute('role','status');const submit=el('button',globalThis.UladimI18n.text("literal_91b04b83802b",{},"Одобрить запрос"));submit.type='submit';add(f,feedback,submit);card.append(f);reason.focus({preventScroll:true});f.addEventListener('submit',async event=>{event.preventDefault();if(!f.reportValidity())return;submit.disabled=true;try{const approved=await api('record-recovery/approve',{request_id:item.id,revision:item.revision,consent_hash:item.consent_hash,reason:reason.value.trim()});Object.assign(item,approved.request);status.textContent=globalThis.UladimI18n.text("literal_1a81463a9ca6",{},"Запрос одобрен. Восстановление выполнит владелец аккаунта.");draw();}catch(error){feedback.className='error';feedback.textContent=error.message;}finally{submit.disabled=false;}});});card.append(open);}
   list.append(card);
  }
 }
 pendingButton.addEventListener('click',()=>{filter='pending';draw();});allButton.addEventListener('click',()=>{filter='all';draw();});draw();if(result.next_before)action(globalThis.UladimI18n.text("literal_75072f638ed5",{},"Следующая страница"),()=>staffRecordRecovery(result.next_before));
}

async function staffFlags(){const flags=await api('flags');heading(globalThis.UladimI18n.text("literal_574528b98c2f",{},"Настройки интерфейса"),globalThis.UladimI18n.text("literal_2afbfd9f236d",{},"Только предусмотренные UI-флаги. Защиту, MFA и проверку TLS здесь отключить нельзя."));for(const [name,value]of Object.entries(flags))app.append(panel(name,(value.enabled?globalThis.UladimI18n.text("literal_0b8162990567",{},"Включён"):globalThis.UladimI18n.text("literal_5a577d905660",{},"Выключен"))+globalThis.UladimI18n.text("literal_de6d4df8e7d4",{}," · охват ")+value.rollout+globalThis.UladimI18n.text("literal_d3f26b2d141b",{},"% · версия ")+value.revision));const f=form(globalThis.UladimI18n.text("literal_471539e85de2",{},"Предварительный просмотр"),[['rollout',globalThis.UladimI18n.text("literal_ba4e24e8d260",{},"Охват: 0–100%"),'number'],['reason',globalThis.UladimI18n.text("literal_034ecde73c90",{},"Причина изменения"),'text']],globalThis.UladimI18n.text("literal_ebb0d1ad2f3c",{},"Показать изменения"),async b=>{const name=f.elements.flag.value;const prior=flags[name]||{enabled:false,rollout:0,revision:0};const proposal=await api('flags/preview',{name,enabled:f.elements.enabled.checked,rollout:Number(b.rollout),revision:prior.revision,reason:b.reason});heading(globalThis.UladimI18n.text("literal_badb2f85d6b9",{},"Проверьте изменение"));app.append(panel(name,globalThis.UladimI18n.text("literal_783117175264",{},"Было: ")+(prior.enabled?globalThis.UladimI18n.text("literal_35cfe273a48c",{},"включён"):globalThis.UladimI18n.text("literal_2d2d65e8e86a",{},"выключен"))+', '+prior.rollout+globalThis.UladimI18n.text("literal_f6fa236e7b5d",{},"%. Будет: ")+(proposal.preview.enabled?globalThis.UladimI18n.text("literal_35cfe273a48c",{},"включён"):globalThis.UladimI18n.text("literal_2d2d65e8e86a",{},"выключен"))+', '+proposal.preview.rollout+'%.'));notice(globalThis.UladimI18n.text("literal_359fd0365d95",{},"Изменение затронет соответствующий процент аккаунтов. Предложение действует 10 минут."));action(globalThis.UladimI18n.text("literal_a9074f7f8a75",{},"Подтвердить применение"),async()=>{await api('flags/commit',{proposal_id:proposal.proposal_id,digest:proposal.digest});await staffFlags();});action(globalThis.UladimI18n.text("literal_7c47f7292ba4",{},"Отменить"),staffFlags);});const select=el('select');select.name='flag';select.setAttribute('aria-label',globalThis.UladimI18n.text("literal_7c50e466fc25",{},"Настройка"));for(const [name,title]of [['compact_onboarding',globalThis.UladimI18n.text("literal_5dd13320df94",{},"Компактное знакомство")],['chart_styles',globalThis.UladimI18n.text("literal_53a1fa62f530",{},"Варианты диаграмм")],['support_entry',globalThis.UladimI18n.text("literal_124ab18650f1",{},"Вход в поддержку")]]){const option=el('option',title);option.value=name;select.append(option);}f.prepend(select);const label=el('label',globalThis.UladimI18n.text("literal_a54eaf37858d",{},"Включить"));const enabled=el('input');enabled.name='enabled';enabled.type='checkbox';label.append(enabled);f.insertBefore(label,f.querySelector('button'));f.elements.rollout.min='0';f.elements.rollout.max='100';f.elements.rollout.value='0';}

async function customerMfa(){const status=await api('mfa');heading(globalThis.UladimI18n.text("literal_f9cea70a4827",{},"Двухфакторная защита"),status.enabled?globalThis.UladimI18n.text("literal_4b9b413bb3b8",{},"Включена. Для отключения нужны пароль и второй фактор."):globalThis.UladimI18n.text("literal_7ebc62fae986",{},"Добавьте второй фактор к паролю аккаунта. Восстановление почты не отключает эту защиту."));if(status.enabled){form(globalThis.UladimI18n.text("literal_aa62b7da2585",{},"Отключить защиту"),[['password',globalThis.UladimI18n.text("literal_d83e5a22c025",{},"Текущий пароль"),'password'],['code',globalThis.UladimI18n.text("literal_06a8f667edb9",{},"Код аутентификатора или восстановления"),'text']],globalThis.UladimI18n.text("literal_98c76257589c",{},"Отключить и выйти"),async b=>{await api('mfa/disable',b);login();});}else{form(globalThis.UladimI18n.text("literal_4c3c41d1b2d2",{},"Подключить аутентификатор"),[['password',globalThis.UladimI18n.text("literal_d83e5a22c025",{},"Текущий пароль"),'password']],globalThis.UladimI18n.text("literal_a42aee58d60a",{},"Продолжить"),async b=>{const enrollment=await api('mfa/begin',b);heading(globalThis.UladimI18n.text("literal_9ef23733c35a",{},"Добавьте ключ в аутентификатор"),globalThis.UladimI18n.text("literal_0f12e9293208",{},"Сохраните ключ в своём приложении-аутентификаторе. Не передавайте его поддержке."));const secret=el('textarea');secret.readOnly=true;secret.value=enrollment.totp_secret;secret.setAttribute('aria-label',globalThis.UladimI18n.text("literal_97fa2c204ef8",{},"Секрет настройки MFA"));app.append(secret);form(globalThis.UladimI18n.text("literal_98465c602922",{},"Подтвердить второй фактор"),[['code',globalThis.UladimI18n.text("literal_eae3f0955064",{},"Текущий шестизначный код"),'text']],globalThis.UladimI18n.text("literal_57a027191bab",{},"Включить защиту"),async value=>{const result=await api('mfa/enable',{password:b.password,enrollment:enrollment.enrollment,code:value.code});heading(globalThis.UladimI18n.text("literal_d748ad4dfdd0",{},"Сохраните коды восстановления"),globalThis.UladimI18n.text("literal_67176cd1eaf1",{},"Каждый код действует один раз вместе с паролем. Храните их офлайн. Все прежние сессии отозваны. После сохранения войдите с новым кодом аутентификатора."));const codes=el('textarea');codes.readOnly=true;codes.value=result.recovery_codes.join('\n');codes.setAttribute('aria-label',globalThis.UladimI18n.text("literal_b3e3f0796466",{},"Одноразовые коды восстановления"));app.append(codes);action(globalThis.UladimI18n.text("literal_171c26dbcb62",{},"Коды сохранены. Вернуться ко входу"),async()=>login());});});}}

function metricCard(key,value){const labels={accounts:globalThis.UladimI18n.text("literal_44e6d3c10df0",{},"Аккаунты"),users:globalThis.UladimI18n.text("literal_44e6d3c10df0",{},"Аккаунты"),new_24h:globalThis.UladimI18n.text("literal_2bba80981704",{},"Новые за сутки"),active_24h:globalThis.UladimI18n.text("literal_f45760aa75e5",{},"Активные за сутки"),mail_pending:globalThis.UladimI18n.text("literal_f6f7120739f6",{},"Очередь писем"),support_pending:globalThis.UladimI18n.text("literal_3ab916e6e7fe",{},"Обращения"),load_1m:globalThis.UladimI18n.text("literal_d540d4496944",{},"Нагрузка CPU"),disk_free_bytes:globalThis.UladimI18n.text("literal_3db932f1b796",{},"Свободное место"),api_latency_ms:globalThis.UladimI18n.text("literal_0e80e9d64af5",{},"Задержка API"),sync_errors:globalThis.UladimI18n.text("literal_f5aaa1eecba3",{},"Ошибки синхронизации"),backup_last_success:globalThis.UladimI18n.text("literal_9eb508eda2fc",{},"Резервная копия")};let text=globalThis.UladimI18n.text("literal_d316433a25c9",{},"Нет измерений");if(value!==null){if(key==='disk_free_bytes')text=(value/1073741824).toLocaleString(authLanguage,{maximumFractionDigits:1})+globalThis.UladimI18n.text("literal_9fd219660ff0",{}," ГБ");else if(key==='backup_last_success')text=new Date(value*1000).toLocaleString(authLanguage);else text=value.toLocaleString(authLanguage,{maximumFractionDigits:key==='load_1m'?2:0})+(key==='api_latency_ms'?globalThis.UladimI18n.text("literal_3d28ff50f586",{}," мс"):'');}return add(el('section',undefined,'card metric-card'),el('h2',labels[key]||key),el('div',text,value===null?'metric-unavailable':'metric-value'));}
function controlOverview(session){
 const section=el('section',undefined,'control-overview-links');section.setAttribute('aria-label',globalThis.UladimI18n.text("literal_942a156cb6db",{},"Разделы Control"));
 for(const [permission,title,description,path]of [['users.read',globalThis.UladimI18n.text("literal_845595d6e899",{},"Пользователи"),globalThis.UladimI18n.text("literal_75a5eccb3985",{},"Аккаунты, устройства, доступ и ограничения."),'users'],['applications.manage',globalThis.UladimI18n.text("literal_4cba08a1baae",{},"Заявки на тест"),globalThis.UladimI18n.text("literal_638191739767",{},"Приглашения и решения по заявкам."),'applications'],['staff.manage',globalThis.UladimI18n.text("literal_8b372c12c268",{},"Команда"),globalThis.UladimI18n.text("literal_3eaafd2845fa",{},"Роли сотрудников и защищённые приглашения."),'staff'],['support.read',globalThis.UladimI18n.text("literal_f0012086d52e",{},"Поддержка"),globalThis.UladimI18n.text("literal_8a70afa7533e",{},"Обращения пользователей и ответы команды."),'support'],['announcements.manage',globalThis.UladimI18n.text("literal_d4baf8f6b173",{},"Уведомления"),globalThis.UladimI18n.text("literal_a833bfd7a2ad",{},"Черновики сообщений, аудитория и время показа."),'announcements'],['records.recover',globalThis.UladimI18n.text("literal_306587ae17a0",{},"Восстановление записей"),globalThis.UladimI18n.text("literal_3557cbec6df5",{},"Запросы владельцев без доступа к содержимому."),'record-recovery'],['referrals.read',globalThis.UladimI18n.text("literal_b0b0c93a7c1e",{},"Приглашения"),globalThis.UladimI18n.text("literal_5d5ab455fe85",{},"Кто приглашает пользователей и как они пользуются платформой."),'referrals'],['audit.read',globalThis.UladimI18n.text("literal_f02dd0fa22cd",{},"Аудит"),globalThis.UladimI18n.text("literal_37dfd2721fea",{},"Журнал действий с причинами и изменениями."),'audit'],['flags.manage',globalThis.UladimI18n.text("literal_574528b98c2f",{},"Настройки интерфейса"),globalThis.UladimI18n.text("literal_02dac3d6b5f4",{},"Разрешённые настройки и предварительная проверка."),'flags']]){
  if(!session.permissions.includes(permission))continue;const card=el('button',undefined,'secondary control-overview-link');card.type='button';add(card,el('strong',title),el('span',description));card.addEventListener('click',()=>{const select=controlNavigation?.querySelector('select');if(select){select.value=path;select.dispatchEvent(new Event('change'));}});section.append(card);
 }
 return section;
}
function staffRecovery(id,email){
 heading(globalThis.UladimI18n.text("literal_c11c8ad8cfc2",{},"Отправить письмо восстановления"),email);notice(globalThis.UladimI18n.text("literal_e6a71768fa3c",{},"Письмо придёт владельцу аккаунта. Пароль и коды остаются недоступны сотруднику; защита MFA сохраняется."));
 const f=form(globalThis.UladimI18n.text("literal_1e53ee1273ea",{},"Подтверждение запроса"),[['reason',globalThis.UladimI18n.text("literal_09304513f121",{},"Причина для журнала аудита"),'text']],globalThis.UladimI18n.text("literal_74bdd15eedbd",{},"Отправить письмо"),async body=>{await api('user/recovery',{user_id:id,reason:body.reason});heading(globalThis.UladimI18n.text("literal_a6d9096f3c1a",{},"Письмо восстановления запрошено"),globalThis.UladimI18n.text("literal_5b1c834c72af",{},"Запрос поставлен в очередь. Дальнейшие действия выполняет владелец аккаунта."));action(globalThis.UladimI18n.text("literal_587a908fd236",{},"К аккаунту"),()=>staffUser(id));});f.elements.reason.maxLength=500;action(globalThis.UladimI18n.text("literal_7c47f7292ba4",{},"Отменить"),()=>staffUser(id));
}

function makeControlNavigation(session,container){container.replaceChildren();const select=el('select');select.setAttribute('aria-label',globalThis.UladimI18n.text("literal_f18e0846eae8",{},"Раздел Control"));const routes=[['dashboard.read',globalThis.UladimI18n.text("literal_bd3a5be11e2a",{},"Обзор"),'dashboard'],['users.read',globalThis.UladimI18n.text("literal_845595d6e899",{},"Пользователи"),'users'],['applications.manage',globalThis.UladimI18n.text("literal_4cba08a1baae",{},"Заявки на тест"),'applications'],['staff.manage',globalThis.UladimI18n.text("literal_8b372c12c268",{},"Команда"),'staff'],['support.read',globalThis.UladimI18n.text("literal_f0012086d52e",{},"Поддержка"),'support'],['referrals.read',globalThis.UladimI18n.text("literal_b0b0c93a7c1e",{},"Приглашения"),'referrals'],['audit.read',globalThis.UladimI18n.text("literal_f02dd0fa22cd",{},"Аудит"),'audit'],['flags.manage',globalThis.UladimI18n.text("literal_574528b98c2f",{},"Настройки интерфейса"),'flags'],['announcements.manage',globalThis.UladimI18n.text("literal_d4baf8f6b173",{},"Уведомления"),'announcements'],['records.recover',globalThis.UladimI18n.text("literal_306587ae17a0",{},"Восстановление записей"),'record-recovery']];for(const [permission,title,path]of routes)if(session.permissions.includes(permission)){const option=el('option',title);option.value=path;select.append(option);}if(!session.permissions.includes('dashboard.read')){const choose=el('option',globalThis.UladimI18n.text("literal_ddbb4b70bb4d",{},"Выберите раздел"));choose.value='';choose.disabled=true;choose.selected=true;select.prepend(choose);}container.append(select);select.addEventListener('change',async()=>{try{const path=select.value;controlSection=path;if(path==='dashboard'){await dashboard();return;}if(path==='users'){await staffUsers();return;}if(path==='applications'){await staffApplications();return;}if(path==='staff'){await staffTeam();return;}if(path==='support'){await support();return;}if(path==='flags'){await staffFlags();return;}if(path==='announcements'){await staffAnnouncements();return;}if(path==='record-recovery'){await staffRecordRecovery();return;}if(path==='referrals'){await staffReferrals();return;}heading(globalThis.UladimI18n.text("literal_6211d2fa390b",{},"Журнал аудита"));const result=await api('audit');for(const event of result.events){const card=panel(event.action,new Date(event.created_at*1000).toLocaleString(authLanguage));card.append(el('p',event.reason));const details=el('details');details.append(el('summary',globalThis.UladimI18n.text("literal_c7951fd569fc",{},"Изменения")));details.append(el('pre',JSON.stringify({before:JSON.parse(event.before_value),after:JSON.parse(event.after_value)},null,2)));card.append(details);app.append(card);}}catch(e){notice(e.message);}});action(globalThis.UladimI18n.text("literal_5690c2e63b9d",{},"Выйти"),async()=>{await api('logout',{});csrf='';login();},container);return container;}


const HOME_ICON_PATHS = {
 today: 'M8 2v4M16 2v4M3 10h18M5 4h14a2 2 0 0 1 2 2v14H3V6a2 2 0 0 1 2-2m3 11 2 2 5-5',
 tasks: 'm3 6 1 1 2-2M10 6h11m-18 6 1 1 2-2M10 12h11m-18 6 1 1 2-2M10 18h11',
 calendar: 'M8 2v4M16 2v4M3 10h18M5 4h14a2 2 0 0 1 2 2v14H3V6a2 2 0 0 1 2-2M8 14h2M14 14h2',
 notes: 'M5 3h14v18H5zM8 8h8M8 12h8M8 16h5',
 money: 'M4 20V10m6 10V4m6 16v-8m5 8H2',
 account: 'M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0M4 21v-2a8 8 0 0 1 16 0v2'
};

function homeIcon(name) {
 const namespace = 'http://www.w3.org/2000/svg';
 const icon = document.createElementNS(namespace, 'svg');
 for (const [key, value] of Object.entries({
  viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '1.7',
  'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'aria-hidden': 'true', focusable: 'false'
 })) icon.setAttribute(key, value);
 const path = document.createElementNS(namespace, 'path');
 path.setAttribute('d', HOME_ICON_PATHS[name]);
 icon.append(path);
 return icon;
}

function todayPreview() {
 const preview = el('section', undefined, 'workspace-preview');
 preview.setAttribute('aria-label', globalThis.UladimI18n.text("literal_d85805b43c95",{},"Пример интерфейса ULADIM"));
 const rail = el('div', undefined, 'preview-rail');
 rail.setAttribute('aria-hidden', 'true');
 rail.append(el('strong', 'ULADIM'));
 const views = [
  ['today', globalThis.UladimI18n.text("literal_b688b4c0d783",{},"Сегодня")], ['tasks', globalThis.UladimI18n.text("literal_03cc1c2d5ac2",{},"Задачи")], ['calendar', globalThis.UladimI18n.text("literal_2ea15d96b2d0",{},"Календарь")],
  ['notes', globalThis.UladimI18n.text("literal_04a18b51cdc2",{},"Заметки")], ['money', globalThis.UladimI18n.text("literal_d833b857223f",{},"Финансы")], ['account', globalThis.UladimI18n.text("literal_7bdb1f26464a",{},"Семья")]
 ];
 for (const [icon, label] of views) {
  rail.append(add(el('div', undefined, 'preview-view'), homeIcon(icon), el('span', label)));
 }

 const desk = el('div', undefined, 'preview-workspace');
 const top = add(el('div', undefined, 'preview-top'),
  add(el('div'), el('h2', globalThis.UladimI18n.text("literal_b688b4c0d783",{},"Сегодня")), el('p', globalThis.UladimI18n.text("literal_b3dd9eaa6408",{},"Четверг, 12 ноября"))),
  el('span', globalThis.UladimI18n.text("literal_c77ad94944b7",{},"Пример интерфейса"), 'preview-label'));

 const tasks = el('div', undefined, 'preview-tasks');
 const progress = el('span', globalThis.UladimI18n.text("literal_63465cf1638a",{},"2 из 3"));
 progress.setAttribute('aria-label', globalThis.UladimI18n.text("literal_d3e336b32b80",{},"Выполнено 2 из 3 задач"));
 tasks.append(add(el('div', undefined, 'preview-task-heading'), el('h3', globalThis.UladimI18n.text("literal_bda54b51402c",{},"Задачи на сегодня")), progress));
 const list = el('ul', undefined, 'preview-task-list');
 for (const [done, label] of [[true, globalThis.UladimI18n.text("literal_77005228ad4a",{},"Ответить на письма")], [true, globalThis.UladimI18n.text("literal_316a787233b6",{},"Оплатить интернет")], [false, globalThis.UladimI18n.text("literal_b071f5afd6eb",{},"Подготовить план на неделю")]]) {
  const row = el('li', undefined, 'preview-task');
  const mark = el('span', undefined, 'preview-check' + (done ? ' checked' : ''));
  mark.setAttribute('role', 'img');
  mark.setAttribute('aria-label', done ? globalThis.UladimI18n.text("literal_c045c25ac488",{},"Выполнено") : globalThis.UladimI18n.text("literal_a26855d237c7",{},"Открыто"));
  list.append(add(row, mark, el(done ? 's' : 'span', label)));
 }
 tasks.append(list);

 const time = el('time', '18:30');
 time.dateTime = '18:30';
 const event = add(el('div', undefined, 'preview-event'), homeIcon('calendar'), time, el('strong', globalThis.UladimI18n.text("literal_bf8c74bdefe8",{},"Встреча с семьёй")));
 const finance = add(el('div', undefined, 'preview-finance'), el('h3', globalThis.UladimI18n.text("literal_f03d1eb3692f",{},"Финансы за ноябрь")));
 const totals = el('dl', undefined, 'preview-totals');
 for (const [label, amount] of [[globalThis.UladimI18n.text("literal_384d916bbcef",{},"Доход"), '150 000 ₽'], [globalThis.UladimI18n.text("literal_a3140a45c029",{},"Расход"), '3 520 ₽']]) {
  totals.append(add(el('div'), el('dt', label), el('dd', amount)));
 }
 finance.append(totals);
 add(desk, top, tasks, event, finance);
 return add(preview, rail, desk);
}

async function landing(config) {
 document.body.classList.add('focus-home');
 app.replaceChildren();
 app.classList.add('landing');
 const hero=el('section',undefined,'product-hero');
 const copy=el('div',undefined,'hero-copy');
 const title=add(el('h1'),el('span',globalThis.UladimI18n.text("literal_89b6d34cb65a",{},"Важное —")),' ',el('span',globalThis.UladimI18n.text("literal_653aaacf3b2d",{},"в одном месте.")));
 add(copy,el('p',globalThis.UladimI18n.text("literal_f681e9d89ea8",{},"ULADIM · Личное и семейное пространство"),'hero-eyebrow'),title,
  el('p',globalThis.UladimI18n.text("literal_3b798334ab05",{},"Задачи, заметки, календарь и финансы. Соберите повседневные дела в одном спокойном пространстве."),'hero-description'));
 const actions=el('div',undefined,'hero-actions');
 actions.append(startLink(config));copy.append(actions);
 copy.append(el('p',config.entry==='signed-in'?globalThis.UladimI18n.text("literal_91a004c79995",{},"Ваш аккаунт уже открыт в этом браузере."):globalThis.UladimI18n.text("literal_6f4d88788598",{},"Сейчас все возможности доступны бесплатно."),'hero-caption'));
 app.append(add(hero,copy,todayPreview()));

 const overview=el('section',undefined,'welcome-overview');
 overview.setAttribute('aria-label',globalThis.UladimI18n.text("literal_356b36b87ada",{},"Возможности ULADIM"));
 for(const [symbol,title,description]of [
  ['calendar',globalThis.UladimI18n.text("literal_736e8b8178ad",{},"Планируйте день"),globalThis.UladimI18n.text("literal_df9bf0f7f1a0",{},"Задачи, заметки и события рядом.")],
  ['money',globalThis.UladimI18n.text("literal_e9042c3f5512",{},"Ведите финансы"),globalThis.UladimI18n.text("literal_016f5d4e2585",{},"Счета, операции и бюджеты без суеты.")],
  ['account',globalThis.UladimI18n.text("literal_5a0699214354",{},"Делайте вместе"),globalThis.UladimI18n.text("literal_f0666a80a518",{},"Личное пространство и общие семейные дела.")]
 ]){
  const item=el('div',undefined,'welcome-capability');
  add(item,homeIcon(symbol),add(el('div'),el('h2',title),el('p',description)));
  overview.append(item);
 }
 app.append(overview);
 const learn=el('nav',undefined,'welcome-resources');learn.setAttribute('aria-label',globalThis.UladimI18n.text("literal_6ed487146e23",{},"Узнать больше"));
 for(const [label,path]of [[globalThis.UladimI18n.text("literal_04afc09e60bd",{},"Возможности"),'/docs'],[globalThis.UladimI18n.text("literal_5db38a3be3e8",{},"Как установить"),'/download'],[globalThis.UladimI18n.text("literal_b2fbb44bb3e3",{},"Тарифы"),'/plans'],[globalThis.UladimI18n.text("literal_a3ca1c94161e",{},"Вопросы и ответы"),'/faq'],[globalThis.UladimI18n.text("literal_f0012086d52e",{},"Поддержка"),'/support']]){
  const entry=el('a',label);entry.href=path;learn.append(entry);
 }
 app.append(learn);
}
function applicationCards(full) {
 const grid=el('div',undefined,'application-grid');
 const web=panel(globalThis.UladimI18n.text("literal_c47768319233",{},"Телефон, планшет и компьютер"),globalThis.UladimI18n.text("literal_9fb825e1ca0a",{},"ULADIM работает в браузере на iPhone, iPad, Android, Windows, macOS и Linux. На телефоне или планшете его можно добавить на домашний экран."));
 add(web,link(globalThis.UladimI18n.text("literal_e1e440f7bb62",{},"Открыть веб-приложение"),'/app'),link(globalThis.UladimI18n.text("literal_5db38a3be3e8",{},"Как установить"),full?'#installation':'/download#installation',true));
 const android=panel(globalThis.UladimI18n.text("literal_f3233bf59e09",{},"Приложение для Android"),globalThis.UladimI18n.text("literal_ee1220d26580",{},"Отдельный Android-клиент. Опубликованные сборки и сведения о версиях доступны в GitHub Releases."));
 android.append(link(globalThis.UladimI18n.text("literal_1d822b05016b",{},"Сборки Android"),'https://github.com/pro100umarchikgamer-lgtm/lifeos/releases',true));
 if(!full)android.append(link(globalThis.UladimI18n.text("literal_0e2fa7ba77cc",{},"Об Android-приложении"),'/download#android',true));
 android.id='android';
 return add(grid,web,android);
}
function applicationPage() {
 heading(globalThis.UladimI18n.text("literal_c701d2b3f26e",{},"Приложения ULADIM"),globalThis.UladimI18n.text("literal_4b0ef34157fc",{},"Работайте в браузере или добавьте ULADIM на домашний экран."));
 app.append(applicationCards(true));
 installGuide(app);
 const target=document.getElementById(location.hash.slice(1));
 if(target)requestAnimationFrame(()=>target.scrollIntoView());
}
async function planComparison(target){
 const data=await api('plans');const section=el('section',undefined,'plan-comparison help-plans');
 add(section,el('h2',globalThis.UladimI18n.text("literal_bcb6c49db733",{},"Планируйте в своём ритме")),el('p',globalThis.UladimI18n.text("literal_3c107369393b",{},"Все текущие возможности доступны бесплатно."),'access-free-note'),el('p',globalThis.UladimI18n.text("literal_2cdea298da98",{},"Задачи, заметки, календарь, финансы, импорт и семейное пространство. Начните без карты и обязательств.")));
 const grid=el('div',undefined,'access-plan-grid');
 for(const [tier,label,title,text,items]of [
  ['Free',globalThis.UladimI18n.text("literal_fcbfc557515d",{},"Можно начать сейчас"),globalThis.UladimI18n.text("literal_3f555b1a8a35",{},"Важное под рукой"),globalThis.UladimI18n.text("literal_de7c0c72a41d",{},"Всё, что уже работает в ULADIM, доступно бесплатно."),[globalThis.UladimI18n.text("literal_8f0a73b78579",{},"Задачи, заметки и календарь"),globalThis.UladimI18n.text("literal_44fb43cb1fc3",{},"Финансовый учёт и бюджеты"),globalThis.UladimI18n.text("literal_4e57e09d4a3c",{},"Импорт записей и выписок"),globalThis.UladimI18n.text("literal_4b2d66df8a80",{},"Личное и семейное пространство")]],
  ['Plus',globalThis.UladimI18n.text("literal_d1f0f0adeb4a",{},"Бесплатный доступ к текущим функциям"),globalThis.UladimI18n.text("literal_68d83e2dffc7",{},"Больше места для вашего ритма"),globalThis.UladimI18n.text("literal_10da5c6ba3f9",{},"Будущий вариант доступа. Окончательные условия ещё готовятся."),[globalThis.UladimI18n.text("literal_e3b829e6107c",{},"Текущие функции остаются доступны бесплатно"),globalThis.UladimI18n.text("literal_10cd48f7e890",{},"Дополнительные возможности — после анонса"),globalThis.UladimI18n.text("literal_a66c83592898",{},"Без оформления подписки сегодня")]],
  ['Premium',globalThis.UladimI18n.text("literal_71a59de862eb",{},"Появится позже"),globalThis.UladimI18n.text("literal_671e1bf3d0ac",{},"Помощь с искусственным интеллектом"),globalThis.UladimI18n.text("literal_c77ce683b745",{},"Будущий уровень с ИИ. Сейчас эти возможности недоступны."),[globalThis.UladimI18n.text("literal_cca531c62e55",{},"ИИ-функции пока недоступны"),globalThis.UladimI18n.text("literal_091e6a6dc9c4",{},"Срок запуска и цена не объявлены"),globalThis.UladimI18n.text("literal_213c628a6f3f",{},"Подключить этот уровень пока нельзя")]]
 ]){
  if(!data.tiers[tier])continue;
  const card=el('article',undefined,'card access-plan-card');card.dataset.tier=tier;
  if(tier==='Premium')card.setAttribute('aria-label',globalThis.UladimI18n.text("literal_4356cd03c107",{},"Premium: недоступен, появится позже"));
  add(card,el('p',label,'access-plan-label'),el('h3',tier),el('strong',title),el('p',text));const list=el('ul');for(const item of items)list.append(el('li',item));card.append(list);
  if(tier==='Free')card.append(link(globalThis.UladimI18n.text("literal_4f1591dbadb5",{},"Начать бесплатно"),'/app'));
  else card.append(el('span',tier==='Plus'?globalThis.UladimI18n.text("literal_e708e2dd5fe3",{},"Продажи ещё не открыты"):globalThis.UladimI18n.text("literal_43b730bef241",{},"Сейчас недоступен"),'help-plan-state'));
  grid.append(card);
 }
 section.append(grid);
 const note=el('aside',undefined,'help-callout');note.append(el('strong',globalThis.UladimI18n.text("literal_533ebaf42f4e",{},"Сначала понятные условия — затем ваш выбор")),el('p',globalThis.UladimI18n.text("literal_0bc844ae8905",{},"Если платные возможности появятся, заранее укажем цену, состав, продление, отмену и возвраты. Сегодня покупки и автоматические списания отключены.")));section.append(note);
 const details=el('details',undefined,'access-plan-details');details.append(el('summary',globalThis.UladimI18n.text("literal_d546f4cbe084",{},"Что доступно сейчас")));
 const labels={personal_core:globalThis.UladimI18n.text("literal_0c6a5b748c4e",{},"Задачи, заметки, календарь и финансы"),family_sync:globalThis.UladimI18n.text("literal_3f7c9491d6bb",{},"Семейное пространство"),custom_charts:globalThis.UladimI18n.text("literal_b774b32f322a",{},"Настройка диаграмм"),extended_personalization:globalThis.UladimI18n.text("literal_c2d36c8aa703",{},"Темы и палитры"),statement_import:globalThis.UladimI18n.text("literal_b9167b1cb66d",{},"Импорт выписок"),advanced_planning:globalThis.UladimI18n.text("literal_adbd2426fa1d",{},"Расширенное планирование")};
 const features=el('ul');for(const [key,label]of Object.entries(labels))if(data.tiers.Free?.features.includes(key))features.append(el('li',label+globalThis.UladimI18n.text("literal_9f4e7d240793",{}," — бесплатно")));details.append(features);section.append(details);target.append(section);
 const help=el('p');help.append(el('span',globalThis.UladimI18n.text("literal_3db5f628d8da",{},"Есть вопросы? ")));const faq=el('a',globalThis.UladimI18n.text("literal_7b260990784f",{},"Ответы о доступе и оплате"));faq.href='/faq#plans';help.append(faq);target.append(help);
}
function installGuide(target){
 const section=el('section',undefined,'install-guide');
 section.id='installation';
 add(section,el('h2',globalThis.UladimI18n.text("literal_027fffde5f5d",{},"Установка на домашний экран")),el('p',globalThis.UladimI18n.text("literal_fd054920e248",{},"Откройте веб-приложение и выберите инструкцию для своего устройства.")));
 for(const [title,body]of [[globalThis.UladimI18n.text("literal_295d80e4ac37",{},"iPhone и iPad"),globalThis.UladimI18n.text("literal_d5b7b973405f",{},"Откройте /app в Safari. Нажмите «Поделиться» → «На экран Домой». Запускайте ULADIM с появившегося значка.")],['Android',globalThis.UladimI18n.text("literal_d540ea300874",{},"Откройте /app в Chrome. В меню браузера выберите «Установить приложение» или «Добавить на главный экран».")],[globalThis.UladimI18n.text("literal_9329c3a242fd",{},"Компьютер"),globalThis.UladimI18n.text("literal_8f92f2d98748",{},"В поддерживаемом браузере откройте /app и используйте кнопку установки рядом с адресной строкой. Можно работать и в обычной вкладке.")]]){const d=el('details');add(d,el('summary',title),el('p',body));section.append(d);}target.append(section);
}

async function earlyAccess(){
  const config=await api('config');if(config.registration_open){heading(globalThis.UladimI18n.text("literal_53ab8486a274",{},"Прежние заявки"),globalThis.UladimI18n.text("literal_c1f9aa66ebc5",{},"Обычная регистрация открыта. Приглашение больше не требуется; прежние заявки сохранены."));app.append(link(globalThis.UladimI18n.text("literal_4f1591dbadb5",{},"Начать бесплатно"),'/app?action=signup'));form(globalThis.UladimI18n.text("literal_0fcc659da30c",{},"Проверить прежнюю заявку"),[['email',globalThis.UladimI18n.text("literal_9738aeca2427",{},"Электронная почта"),'email']],globalThis.UladimI18n.text("literal_385c4681b363",{},"Получить код подтверждения"),async b=>{await earlyApi('recover',{email:b.email});confirmEarly(b.email);});return;}
  heading(globalThis.UladimI18n.text("literal_efe4bf771211",{},"Ваше место в ULADIM"),globalThis.UladimI18n.text("literal_808e58479099",{},"Оставьте заявку на закрытый тест. Мы приглашаем участников постепенно. Аккаунт и подписка при подаче заявки не создаются."));
  const f=form(globalThis.UladimI18n.text("literal_02a580ada00c",{},"Заявка на участие"),[['email',globalThis.UladimI18n.text("literal_9738aeca2427",{},"Электронная почта"),'email']],globalThis.UladimI18n.text("literal_385c4681b363",{},"Получить код подтверждения"),async b=>{if(!consent.checked)throw new Error(globalThis.UladimI18n.text("literal_e3e12221780c",{},"Подтвердите согласие с политикой обработки данных."));await earlyApi('apply',{...b,consent_version:'2026-11-08',website:trap.value});confirmEarly(b.email);});
  f.elements.email.autocomplete='email';f.elements.email.maxLength=254;
  const row=el('label',undefined,'consent');const consent=el('input');consent.type='checkbox';consent.required=true;const label=el('span',globalThis.UladimI18n.text("literal_c50b52d15696",{},"Согласен с обработкой email для заявки, её статуса и приглашения. "));const policy=el('a',globalThis.UladimI18n.text("literal_3ba8eaa5d624",{},"Политика конфиденциальности"));policy.href='/privacy';add(label,policy);add(row,consent,label);f.insertBefore(row,f.querySelector('button'));
  const trap=el('input');trap.name='website';trap.tabIndex=-1;trap.autocomplete='off';trap.className='honeypot';trap.setAttribute('aria-hidden','true');f.append(trap);
  action(globalThis.UladimI18n.text("literal_4b3dfe3519a9",{},"Уже есть код? Проверить статус заявки"),()=>{heading(globalThis.UladimI18n.text("literal_e3cd0c6efbe0",{},"Подтверждение заявки"));form(globalThis.UladimI18n.text("literal_b0fbb3839356",{},"Почта заявки"),[['email',globalThis.UladimI18n.text("literal_9738aeca2427",{},"Электронная почта"),'email']],globalThis.UladimI18n.text("literal_a42aee58d60a",{},"Продолжить"),b=>confirmEarly(b.email));});
  notice(globalThis.UladimI18n.text("literal_38692827730d",{},"Код действует 15 минут. Повторная заявка не даёт приоритета. После подтверждения можно отменить участие."));
}
function confirmEarly(email){
  heading(globalThis.UladimI18n.text("literal_ce3e6aa2df00",{},"Проверьте почту"),globalThis.UladimI18n.text("literal_e4635c1a5d1d",{},"Введите код из письма ULADIM. Если письма нет, проверьте папку «Спам»; повторная отправка доступна через 5 минут."));
  const f=form(globalThis.UladimI18n.text("literal_c0c32978fbe2",{},"Подтвердить ")+email,[['code',globalThis.UladimI18n.text("literal_a3ea51126e90",{},"Код подтверждения"),'text']],globalThis.UladimI18n.text("literal_81737c923f89",{},"Подтвердить email"),async b=>{const result=await earlyApi('confirm',{email,code:b.code.trim()});earlyStatus(result.management_token,result.state);});f.elements.code.autocomplete='one-time-code';f.elements.code.maxLength=43;
  action(globalThis.UladimI18n.text("literal_ab8911b395ce",{},"Запросить другое письмо"),earlyAccess);
}
function earlyStatus(token,state){
  const labels={pending:[globalThis.UladimI18n.text("literal_249ed4028009",{},"Заявка в очереди"),globalThis.UladimI18n.text("literal_c12aeca6d56d",{},"Адрес подтверждён. Когда появится место, мы отправим приглашение на почту.")],approved:[globalThis.UladimI18n.text("literal_be8c4dab4ba4",{},"Вы приглашены"),globalThis.UladimI18n.text("literal_9b1c29f73151",{},"Приглашение отправлено на подтверждённый email. Оно действует 7 дней.")],rejected:[globalThis.UladimI18n.text("literal_5b00e2d6b548",{},"Набор пока ограничен"),globalThis.UladimI18n.text("literal_b4a8a7b682a1",{},"Сейчас мы не можем включить вас в тест. Аккаунт не создан.")],cancelled:[globalThis.UladimI18n.text("literal_e64b7698a9eb",{},"Заявка отменена"),globalThis.UladimI18n.text("literal_fa11b5861ae3",{},"Приглашение, если оно было, больше не действует.")]};
  const [title,description]=labels[state]||[globalThis.UladimI18n.text("literal_77b3e0166b0d",{},"Заявка"),globalThis.UladimI18n.text("literal_f34e98caf356",{},"Подтвердите почту.")];heading(title,description);
  if(state!=='cancelled'){action(globalThis.UladimI18n.text("literal_83553fb55857",{},"Обновить статус"),async()=>{const result=await earlyApi('status',{management_token:token});earlyStatus(token,result.state);});action(globalThis.UladimI18n.text("literal_65c9be48801e",{},"Отменить заявку"),async()=>{const result=await earlyApi('cancel',{management_token:token});earlyStatus(token,result.state);});}
  if(state==='approved')app.append(link(globalThis.UladimI18n.text("literal_17c532084d2c",{},"Создать аккаунт по приглашению"),'/account'));
  notice(globalThis.UladimI18n.text("literal_aeb42bae9644",{},"Доступ к статусу хранится только в памяти этой страницы. После её закрытия подтвердите почту новым кодом."));
}
async function staffApplications(state='pending',before=''){
  heading(globalThis.UladimI18n.text("literal_c166b56a6ca1",{},"Заявки на закрытый тест"),globalThis.UladimI18n.text("literal_26ee7b1a61cc",{},"Подтверждённая заявка не является аккаунтом. Одобрение отправляет приглашение на 7 дней."));
  const filters=el('div',undefined,'actions');app.append(filters);for(const [key,label]of [['pending',globalThis.UladimI18n.text("literal_b40581a7156f",{},"Ожидают")],['approved',globalThis.UladimI18n.text("literal_5bbe71aea517",{},"Приглашены")],['rejected',globalThis.UladimI18n.text("literal_c5a69ac5e6a4",{},"Отклонены")],['cancelled',globalThis.UladimI18n.text("literal_c7f97e972951",{},"Отменены")]])action(label,()=>staffApplications(key),filters);
  const result=await api('applications?state='+encodeURIComponent(state)+(before?'&before='+encodeURIComponent(before):''));
  if(!result.applications.length)notice(globalThis.UladimI18n.text("literal_da2b115edc61",{},"Заявок в этой категории пока нет."));
  for(const item of result.applications){const card=panel(item.email,globalThis.UladimI18n.text("literal_b9de27d3ebba",{},"Почта подтверждена: ")+(item.verified_at?new Date(item.verified_at*1000).toLocaleString(authLanguage):globalThis.UladimI18n.text("literal_dc9337ff5b42",{},"нет")));app.append(card);if(state==='pending')for(const [decision,label]of [['approved',globalThis.UladimI18n.text("literal_4e313d1664c2",{},"Пригласить")],['rejected',globalThis.UladimI18n.text("literal_899c5d6de891",{},"Отклонить")]])action(label,()=>{heading(label+': '+item.email);form(globalThis.UladimI18n.text("literal_a6a5c0a7d601",{},"Решение по заявке"),[['reason',globalThis.UladimI18n.text("literal_09304513f121",{},"Причина для журнала аудита"),'text']],globalThis.UladimI18n.text("literal_27bca309f5f8",{},"Подтвердить"),async b=>{await api('applications/decide',{...b,id:item.id,revision:item.revision,decision});await staffApplications(state);});},card);}
  if(result.next)action(globalThis.UladimI18n.text("literal_75072f638ed5",{},"Следующая страница"),()=>staffApplications(state,result.next));
}

// Scrub private views before the browser stores a history snapshot.
window.addEventListener('pagehide',()=>{viewEpoch++;csrf='';controlNavigation=null;app.replaceChildren();});
window.addEventListener('pageshow',event=>{if(!event.persisted)return;app.replaceChildren();if(staff)dashboard().catch(()=>login());else publicPage().catch(error=>{heading(globalThis.UladimI18n.text("literal_209cd070147d",{},"Не удалось загрузить"));notice(error.message);});});

// Public legal documents and help share the factual configuration below.
function legalPage(path){publicExperience.legal(path);}

function importGuide(host){
 const guide=el('section',undefined,'import-guide');
 guide.id='import';
 guide.append(el('h2',globalThis.UladimI18n.text("literal_3c5ae3f26a99",{},"Перенос данных в ULADIM")));
 const steps=el('ol');
 for(const [title,body] of [
  [globalThis.UladimI18n.text("literal_db5a8160c29b",{},"Выберите пространство"),globalThis.UladimI18n.text("literal_bb0e9569deeb",{},"Войдите в веб-приложение. В переключателе вверху выберите личное или доступное семейное пространство. Откройте «Профиль → Импорт и синхронизация».")],
  [globalThis.UladimI18n.text("literal_7803e5139b06",{},"Откройте экспорт"),globalThis.UladimI18n.text("literal_e9114c99df9a",{},"Выберите календари, заметки или задачи. Можно выбрать несколько файлов за раз. Браузер распознаёт поддерживаемые форматы и показывает, что нашёл.")],
  [globalThis.UladimI18n.text("literal_d9dbbece5722",{},"Проверьте и сохраните"),globalThis.UladimI18n.text("literal_e78e0165fd3a",{},"Проверьте названия, даты и предупреждения. Снимите отметку с ненужных записей и нажмите «Импортировать». Откройте соответствующий раздел в том же пространстве.")],
 ]){
  steps.append(add(el('li'),el('strong',title),el('p',body)));
 }
 guide.append(steps);
 for(const [title,body] of [
  [globalThis.UladimI18n.text("literal_cc44faa7e8bc",{},"Apple Notes и обычные файлы"),globalThis.UladimI18n.text("literal_ccc0c4aad878",{},"На iPad откройте заметку, нажмите «Поделиться → Экспортировать как Markdown» и сохраните файл в «Файлы». В ULADIM выберите этот файл в разделе заметок. TXT и Markdown переносятся как редактируемый текст. PDF, HTML и вложения пока не поддерживаются.")],
  ['Google Keep',globalThis.UladimI18n.text("literal_8f1992578112",{},"Запросите экспорт Google Keep в Google Takeout. Выберите скачанный ZIP с папкой Keep или отдельные JSON-файлы заметок. Текст и чек-листы сохраняются как редактируемый текст. Метки, закрепление, архивный статус, даты и вложения пока не переносятся. Заметки из корзины пропускаются.")],
  [globalThis.UladimI18n.text("literal_2ea15d96b2d0",{},"Календарь"),globalThis.UladimI18n.text("literal_5714255d7b3e",{},"Выберите файл .ics из прежнего календаря. Импортируются названия, начало, часовой пояс и поддерживаемые повторения. Проверьте предупреждения о длительности, описаниях и исключениях до сохранения. Файл .ics даёт разовую копию. Для обновлений с Google Calendar потребуется отдельное подключение, которое пока готовится.")],
  [globalThis.UladimI18n.text("literal_72b0940b8eb1",{},"Задачи и планировщики"),globalThis.UladimI18n.text("literal_493a9727f369",{},"Совместимый JSON переносит название и состояние выполнения. Если в файле есть время, описание, подзадачи или другие поля, ULADIM предупредит, что они пока не перенесутся. Поддержка официального экспорта Structured ещё проверяется.")],
 ]) guide.append(panel(title,body));
 guide.append(link(globalThis.UladimI18n.text("literal_17cc8a5ee310",{},"Открыть ULADIM"),'/app'),link(globalThis.UladimI18n.text("literal_654eda15d607",{},"Вопросы об импорте"),'/faq#import',true));
 host.append(guide);
 if(location.hash==='#import')requestAnimationFrame(()=>guide.scrollIntoView());
}

function importFaq(host){
 heading(globalThis.UladimI18n.text("literal_4663fcb25b2d",{},"Частые вопросы"),globalThis.UladimI18n.text("literal_7efb20b53ddd",{},"Вход, перенос данных и работа с записями на разных устройствах."));
 const faq=el('section',undefined,'import-faq');
 faq.id='import';
 for(const [question,answer] of [
  [globalThis.UladimI18n.text("literal_fb36e01cd3c6",{},"Где открыть импорт?"),globalThis.UladimI18n.text("literal_f364de37a738",{},"В веб-приложении откройте «Профиль → Импорт и синхронизация». На телефоне профиль находится в меню «Ещё».")],
  [globalThis.UladimI18n.text("literal_8221e669e80a",{},"Что будет при повторной загрузке?"),globalThis.UladimI18n.text("literal_4c4c8a3223df",{},"ULADIM показывает найденные совпадения в предпросмотре. Если существующая запись отличается, её текущая версия сохраняется. Для обновления внешнего календаря потребуется отдельное подключение.")],
  [globalThis.UladimI18n.text("literal_b3ad28a3038c",{},"Изменятся ли исходные записи?"),globalThis.UladimI18n.text("literal_4088744ee3c4",{},"Исходные файлы и записи в других приложениях остаются у вас. Файлы читаются в браузере. После подтверждения сервер получает только выбранные записи для указанного пространства.")],
  [globalThis.UladimI18n.text("literal_2e4955963ad4",{},"Где найти результат?"),globalThis.UladimI18n.text("literal_94f0a7669587",{},"Откройте «Заметки», «Задачи» или «Календарь» в пространстве, куда выполнили импорт. На другом устройстве войдите в веб-версию под тем же аккаунтом и выберите это же пространство. Возможности Android зависят от версии клиента.")],
  [globalThis.UladimI18n.text("literal_361b8c96009c",{},"Почему некоторые события пропущены?"),globalThis.UladimI18n.text("literal_778c28410b54",{},"Проверьте предупреждение в предпросмотре. События с неподдерживаемым правилом или исключением пропускаются, чтобы календарь не показал неверное расписание. Исходный файл можно открыть в прежнем календаре.")],
  [globalThis.UladimI18n.text("literal_0cea6a8b59d7",{},"Нужен ли интернет?"),globalThis.UladimI18n.text("literal_5e301c028cee",{},"Для сохранения через веб-приложение и просмотра записей на другом устройстве нужен интернет. Локальные функции Android работают независимо от облачного аккаунта.")],
 ]) faq.append(add(el('details'),el('summary',question),el('p',answer)));
 faq.append(link(globalThis.UladimI18n.text("literal_4c2a7790d22f",{},"Пошаговое руководство"),'/docs#import'));
 host.append(faq);
 if(location.hash==='#import')requestAnimationFrame(()=>faq.scrollIntoView());
}

function focusLoginStory(create,lang){
 const copy=globalThis.UladimI18n.copy("grp_93cfb0f22e01",{
  ru:['Меньше суеты.','Больше ясности.','Важное — в одном месте. Задачи, планы и финансы в вашем ритме.','Задачи и заметки','События и календарь','Личные и семейные финансы','В браузере на телефоне, планшете и компьютере.'],
  en:['Less to juggle.','More clarity.','Keep what matters together. Tasks, plans and finances at your pace.','Tasks and notes','Events and calendar','Personal and family finances','In your browser on phone, tablet and desktop.'],
  'uz-Latn':['Kamroq tashvish.','Ko‘proq aniqlik.','Muhim ishlar bir joyda. Vazifalar, rejalar va moliya o‘z maromingizda.','Vazifalar va qaydlar','Tadbirlar va taqvim','Shaxsiy va oilaviy moliya','Telefon, planshet va kompyuter brauzerida.'],
  'uz-Cyrl':['Камроқ ташвиш.','Кўпроқ аниқлик.','Муҳим ишлар бир жойда. Вазифалар, режалар ва молия ўз маромингизда.','Вазифалар ва қайдлар','Тадбирлар ва тақвим','Шахсий ва оилавий молия','Телефон, планшет ва компьютер браузерида.']
 })[lang]||['Less to juggle.','More clarity.','Keep what matters together. Tasks, plans and finances at your pace.','Tasks and notes','Events and calendar','Personal and family finances','In your browser on phone, tablet and desktop.'];
 const aside=create('aside',undefined,'focus-login-story');
 const heading=create('h2');heading.append(create('span',copy[0]),create('span',copy[1]));
 const list=create('ul');for(const text of copy.slice(3,6))list.append(create('li',text));
 aside.append(create('div','ULADIM · '+(globalThis.UladimI18n.text("loc_b05681c1e896",{},"FOCUS")),'focus-story-label'),heading,create('p',copy[2]),list,create('p',copy[6],'focus-story-footnote'));
 return aside;
}

// Public facts have one reviewable source. Blank operator facts keep documents
// in draft; an API public_legal object can supply the same keys at deployment.
// Do not infer legal identity, residency, retention or age rules from branding.
const PUBLIC_RELEASE_FACTS=Object.freeze({
 version:'2026-11-13',get updated(){return globalThis.UladimI18n.text("literal_801c7f15da0a",{},"13 ноября 2026 года");},published:false,
 operatorName:'Usmonov Umar',get operatorCountry(){return globalThis.UladimI18n.text("literal_4099cf97a59c",{},"Узбекистан");},operatorPostalAddress:null,supportEmail:'support@getuladim.space',supportEmailReady:false,
 processingRegion:null,processingVerified:false,privacyLifecycleReady:false,retentionVerified:false,agePolicyEnforced:false,
 get minimumAgePolicy(){return globalThis.UladimI18n.text("literal_9664dfa6753f",{},"Самостоятельный аккаунт предназначен для пользователей от 18 лет. До появления подтверждаемого письменного согласия законного представителя не создавайте аккаунты несовершеннолетних и не добавляйте их персональные данные. Семейная роль сама по себе не подтверждает согласие родителя или опекуна.");},
 get legalBasis(){return globalThis.UladimI18n.text("literal_896df49cd3cf",{},"Необходимые данные аккаунта и ваши записи обрабатываются для предоставления запрошенных вами функций и исполнения условий использования. Отдельное согласие запрашивается там, где его требует закон. Необходимая обработка также допускается для исполнения законных обязанностей и защиты прав пользователей в пределах законодательства Узбекистана. Отзыв согласия не отменяет обработку, для которой сохраняется самостоятельное законное основание.");},
 get securityRetention(){return globalThis.UladimI18n.text("literal_fc2ba2a103ed",{},"Сведения о действиях, необходимых для защиты сервиса, могут сохраняться в виде служебного номера аккаунта, вида действия и времени — без почты, средств входа и содержимого ваших записей. Для этих сведений срок автоматического удаления пока не установлен. Текстовые пояснения сотрудников хранятся отдельно в защищённом виде: до 90 дней или до удаления связанного аккаунта, если оно наступит раньше. Обращения в поддержку не включаются в такой журнал.");},
 backupRetention:null,correspondenceRetention:null,plannedBackupDays:7,supportProviderRetentionDays:30,
 deletionGraceHours:24,get deletionPolicy(){return globalThis.UladimI18n.text("literal_21bb00dc841b",{},"После завершения удаления стираются данные входа, почта, связь с Google, устройства и сеансы, обращения внутри приложения, а также все созданные вами личные и общие записи, включая их содержимое, доступное для восстановления. Личные записи других участников сохраняются: их суммы, даты, валюты и описания не переписываются. Общие итоги могут измениться, потому что ваши записи больше не участвуют в расчётах. Для отображения операций других участников может остаться только отметка об удалённом счёте и его валюта, без вашего имени и исходного содержимого. Служебный номер удалённого аккаунта и дата удаления сохраняются для предотвращения возврата данных при восстановлении.");},
 android:{source:'84b0bdf2c6d54132691d22323553496f6b3b1d43',certificateSha256:'5fa37e4abf1ec90d5787bd0d7dc4cf0b3f49022172f9d25e91f4d8a76702a96e',version:'0.3.1',build:312001,minAndroid:'Android 7.0',bytes:77458893,
  url:'https://github.com/pro100umarchikgamer-lgtm/lifeos/releases/download/uladim-native-84b0bdf2c6d5/ULADIM.apk',
  sha256:'66d123cef79f85b7b2665bdcad0e6309db4a694e9a5076ed871450154c762872',
  release:'https://github.com/pro100umarchikgamer-lgtm/lifeos/releases/tag/uladim-native-84b0bdf2c6d5'}
});
const publicExperience=(()=>{
 const factOverrides={};const facts=new Proxy({},{get:(_target,key)=>Object.hasOwn(factOverrides,key)?factOverrides[key]:PUBLIC_RELEASE_FACTS[key]});
 const node=(tag,text,cls)=>el(tag,text,cls);
 const a=(text,href,cls)=>{const n=node('a',text,cls);n.href=href;return n;};
 const block=(title,...paragraphs)=>{const n=node('section',undefined,'help-prose');n.append(node('h2',title));for(const text of paragraphs)if(text)n.append(node('p',text));return n;};
 const inline=(text,href)=>a(text,href,'help-inline-link');
 const required=['operatorName','operatorCountry','operatorPostalAddress','supportEmail','processingRegion','minimumAgePolicy','legalBasis','securityRetention','backupRetention','correspondenceRetention','deletionPolicy'];
 const ready=()=>facts.published===true&&required.every(key=>typeof facts[key]==='string'&&facts[key].trim())&&Boolean(contact())&&facts.processingVerified===true&&facts.privacyLifecycleReady===true&&facts.retentionVerified===true&&facts.agePolicyEnforced===true;
 const contactAddress=()=>typeof facts.supportEmail==='string'&&/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(facts.supportEmail)?facts.supportEmail:null;
 const contact=()=>facts.supportEmailReady===true?contactAddress():null;
 function configure(value){if(value&&typeof value==='object'){for(const key of Object.keys(PUBLIC_RELEASE_FACTS))if(key!=='android'&&Object.hasOwn(value,key))factOverrides[key]=value[key];}}
 function intro(kicker,title,description){
  document.title=title+' · ULADIM';app.classList.add('help-center');
  app.replaceChildren(node('div',kicker,'help-kicker'),node('h1',title),node('p',description,'help-lead'));
 }
 function related(items=[[globalThis.UladimI18n.text("literal_a3ca1c94161e",{},"Вопросы и ответы"),'/faq'],[globalThis.UladimI18n.text("literal_f0012086d52e",{},"Поддержка"),'/support']]){
  const nav=node('nav',undefined,'help-related');nav.setAttribute('aria-label',globalThis.UladimI18n.text("literal_e49558f3eb38",{},"По теме"));
  for(const [label,href]of items)nav.append(a(label,href));app.append(nav);
 }
 function contactLink(parent,label=globalThis.UladimI18n.text("literal_dbe91db5dc01",{},"Написать в поддержку")){
  const email=contact();if(email)parent.append(link(label,'mailto:'+email,true));
  else parent.append(node('p',contactAddress()?globalThis.UladimI18n.text("literal_e292770b0302",{},"Почтовая поддержка ")+contactAddress()+globalThis.UladimI18n.text("literal_7f6b440cea4e",{}," готовится к запуску. Пока отправьте обращение из своего аккаунта."):globalThis.UladimI18n.text("literal_45ba5937295b",{},"Публичный адрес поддержки будет указан после подтверждения сведений об операторе. Пока обращение можно отправить из своего аккаунта."),'help-muted'));
 }
 function draft(){
  if(ready())return;
  const n=node('aside',undefined,'help-draft');n.setAttribute('aria-label',globalThis.UladimI18n.text("literal_2ff1580fdb74",{},"Статус документа"));
  n.append(node('strong',globalThis.UladimI18n.text("literal_d317ff657f61",{},"Редакция готовится к публикации")),node('p',globalThis.UladimI18n.text("literal_ceebb4f27c48",{},"Ниже приведён проект правил. Условия размещения данных, хранения резервных копий и доступность почтовой поддержки ещё подтверждаются. Окончательная редакция пока не опубликована.")));app.append(n);
 }
 function reader(sections){
  const layout=node('div',undefined,'help-reader'),toc=node('nav',undefined,'help-toc'),article=node('article',undefined,'help-document');
  toc.setAttribute('aria-label',globalThis.UladimI18n.text("literal_6c43a76d4cd6",{},"Содержание документа"));toc.append(node('p',globalThis.UladimI18n.text("literal_8ac5f596c28e",{},"На этой странице"),'help-kicker'));const list=node('ol');
  for(const [id,title,paragraphs]of sections){list.append(add(node('li'),a(title,'#'+id)));const section=block(title,...paragraphs);section.id=id;article.append(section);}
  toc.append(list);layout.append(toc,article);app.append(layout);
 }
 const safety=()=>globalThis.UladimI18n.text("literal_38291337a9b4",{},"Не отправляйте пароли, одноразовые коды, полные банковские реквизиты, выписки или документы. Достаточно описать действие и сообщение на экране.");
 function legal(path){
  const privacy=path==='/privacy';
  intro(globalThis.UladimI18n.text("literal_185fd23dda83",{},"ДАННЫЕ И ПРАВИЛА"),privacy?globalThis.UladimI18n.text("literal_6d5c24967752",{},"Конфиденциальность"):globalThis.UladimI18n.text("literal_4b5ef4dc258e",{},"Условия использования"),privacy?globalThis.UladimI18n.text("literal_9b5d8db27cb6",{},"Какие данные нужны ULADIM, зачем они используются и как ими управлять."):globalThis.UladimI18n.text("literal_f45c999d5948",{},"Понятные правила работы с аккаунтом, личными и общими записями."));
  const meta=node('div',undefined,'help-document-meta');meta.append(node('span',globalThis.UladimI18n.text("literal_9d371f780de1",{},"Обновлено ")+facts.updated),node('span',globalThis.UladimI18n.text("literal_83c21cec4c45",{},"Версия ")+facts.version));
  const print=node('button',globalThis.UladimI18n.text("literal_462e125503f6",{},"Распечатать"),'secondary');print.type='button';print.addEventListener('click',()=>window.print());meta.append(print);app.append(meta);draft();
  const highlights=node('section',undefined,'help-highlights');highlights.setAttribute('aria-label',globalThis.UladimI18n.text("literal_b757623f24f4",{},"Главное"));
  for(const [title,text]of privacy?[
   [globalThis.UladimI18n.text("literal_7218fca38969",{},"Без рекламной аналитики"),globalThis.UladimI18n.text("literal_a46587c7f203",{},"ULADIM не использует рекламные трекеры и не продаёт ваши данные.")],
   [globalThis.UladimI18n.text("literal_b25c6a2d47d7",{},"Данные по делу"),globalThis.UladimI18n.text("literal_deaf390f59d4",{},"Аккаунт и ваши записи нужны для выбранных вами функций.")],
   [globalThis.UladimI18n.text("literal_e18451f23049",{},"Контроль у вас"),globalThis.UladimI18n.text("literal_c86d2a26dbc8",{},"Управляйте доступом, устройствами и удалением аккаунта.")]
  ]:[[globalThis.UladimI18n.text("literal_e932af24560d",{},"Сейчас бесплатно"),globalThis.UladimI18n.text("literal_ce3f169b44a9",{},"Подписка и банковская карта для текущих функций не нужны.")],[globalThis.UladimI18n.text("literal_8dde14ed1892",{},"Ваши записи — ваши"),globalThis.UladimI18n.text("literal_1e5342ad93d4",{},"Добавляйте данные, которыми вправе пользоваться и делиться.")],[globalThis.UladimI18n.text("literal_3b1d04aa2f19",{},"Финансы для учёта"),globalThis.UladimI18n.text("literal_f4a23a3b8348",{},"Приложение не проводит платежи и банковские переводы.")]])highlights.append(add(node('div'),node('strong',title),node('p',text)));
  app.append(highlights);
  const operator=facts.operatorName?globalThis.UladimI18n.text("template_01b861a1acc8",{"arg0":(facts.operatorName),"arg1":(facts.operatorCountry?globalThis.UladimI18n.text("literal_c8f63987b51f",{},"Страна: ")+facts.operatorCountry+'.':''),"arg2":(facts.operatorPostalAddress?globalThis.UladimI18n.text("literal_91c1740adcfb",{},"Почтовый адрес: ")+facts.operatorPostalAddress+'.':'')},"Оператор сервиса: {arg0}. {arg1} {arg2}"):globalThis.UladimI18n.text("literal_b5906d66ca19",{},"Наименование и страна оператора будут добавлены в окончательную редакцию.");
  const email=contact();
  const sections=privacy?[
   ['operator',globalThis.UladimI18n.text("literal_0e7d0a284bf5",{},"Кто отвечает за данные"),[operator,email?globalThis.UladimI18n.text("literal_a07e1492a691",{},"Вопросы о данных можно направить по адресу ")+email+'.':contactAddress()?globalThis.UladimI18n.text("literal_3195c9b215f6",{},"Адрес для вопросов о данных: ")+contactAddress()+'. Приём почты готовится к запуску. Пока действующий пользователь может создать обращение в своём аккаунте.':globalThis.UladimI18n.text("literal_90987b85de1c",{},"Публичный адрес для вопросов о данных ещё не подтверждён. Действующий пользователь может создать обращение в разделе поддержки своего аккаунта.")]],
   ['data',globalThis.UladimI18n.text("literal_b110ddb1ee17",{},"Какие данные используются"),[
    globalThis.UladimI18n.text("literal_8aeaa61a861a",{},"Для облачного аккаунта нужны адрес электронной почты, подтверждение адреса и сведения о выбранном способе входа. При входе по паролю сохраняется его защищённая проверочная запись, а не открытый пароль. Для безопасности используются сведения о сеансах и подключённых устройствах."),
    globalThis.UladimI18n.text("literal_61b02c0881b3",{},"Когда вы создаёте или синхронизируете записи, сервис обрабатывает их содержимое: задачи, заметки, события, счета, финансовые операции, переводы, бюджеты и другие выбранные вами данные. Не добавляйте сведения о других людях без достаточного основания."),
    globalThis.UladimI18n.text("literal_f1e769c59884",{},"В общих пространствах обрабатываются состав участников, их роли, назначения и общие записи. Финансовая запись может содержать введённое вами имя контрагента, назначение или комментарий. Такие сведения также требуют бережного обращения."),
    globalThis.UladimI18n.text("literal_1f67a8e502d2",{},"Сервис не предназначен для хранения биометрических и генетических материалов, медицинских документов и иных избыточных чувствительных сведений. Не добавляйте такие материалы в заметки, общие записи и обращения в поддержку."),
    globalThis.UladimI18n.text("literal_8270cbb104c1",{},"Если вы пишете в поддержку, обрабатываются тема обращения и сообщения, которые вы сами отправили. ")+safety()]],
   ['purpose',globalThis.UladimI18n.text("literal_c4e977d24cd8",{},"Зачем это нужно"),[
    globalThis.UladimI18n.text("literal_088e26657065",{},"Данные аккаунта нужны для входа, восстановления доступа и связи по вопросам безопасности. Содержимое записей используется для выбранных вами функций: хранения, планирования, отображения и синхронизации между устройствами и участниками пространства."),
    globalThis.UladimI18n.text("literal_fca48b580699",{},"Служебные письма связаны с вашим действием или безопасностью аккаунта. Рекламная рассылка и реклама в приложении не используются. ULADIM не подключает рекламную аналитику, межсайтовое отслеживание и продажу персональных данных."),
    facts.legalBasis||globalThis.UladimI18n.text("literal_f982ec37b1d0",{},"Правовые основания обработки и особенности осуществления ваших прав будут указаны после подтверждения страны и статуса оператора.")]],
   ['sharing',globalThis.UladimI18n.text("literal_e0b04a87ab0b",{},"Кто может видеть записи"),[
    globalThis.UladimI18n.text("literal_30c33ac81404",{},"Личные и общие пространства разделены. Другие участники получают доступ к общим данным в пределах своей роли и настроек записи. Проверьте пространство и доступ перед сохранением личной информации."),
    globalThis.UladimI18n.text("literal_fc0882d81d50",{},"Сотрудники поддержки получают сообщения, которые вы отправили в обращении. Обычная панель поддержки не предоставляет им просмотр личных задач, заметок и финансов. Для эксплуатации сервиса доступ к инфраструктуре имеют уполномоченные лица в пределах своих обязанностей."),
    globalThis.UladimI18n.text("literal_387f6d32dfeb",{},"Данные могут передаваться по законному требованию в случаях и объёме, предусмотренных применимым правом. Мы не обещаем абсолютную недоступность данных при обстоятельствах, когда закон требует их раскрытия.")]],
   ['providers',globalThis.UladimI18n.text("literal_ce609ca44fd1",{},"Сервисы, которые помогают работе"),[
    globalThis.UladimI18n.text("literal_7261c0e0577a",{},"Для размещения сервиса используется инфраструктура Hostinger. Служебные письма отправляются через Resend. Эти поставщики обрабатывают данные, необходимые для своей услуги. Почтовая переписка с поддержкой хранится отдельно от обращений внутри приложения."),
    facts.correspondenceRetention||globalThis.UladimI18n.text("literal_0c44ddf4b4a8",{},"Стандартный срок хранения писем у поставщика почтовой поддержки — ")+facts.supportProviderRetentionDays+globalThis.UladimI18n.text("literal_7a4ce88671d7",{}," дней. Удаление аккаунта само по себе не удаляет отправленные отдельно письма и копии у почтовых поставщиков. Порядок очистки этой переписки будет указан после подтверждения работы почтовой поддержки."),
    globalThis.UladimI18n.text("literal_f6ca8542e1e7",{},"Вход через Google используется только по вашему выбору. Запрашиваются подтверждение личности и адрес электронной почты. Доступ к вашим контактам, Google Drive, заметкам и календарям этот вход не предоставляет. Подключение Google само по себе не импортирует записи."),
    facts.processingRegion?globalThis.UladimI18n.text("literal_76e04ebc81df",{},"Место обработки и международная передача: ")+facts.processingRegion:globalThis.UladimI18n.text("literal_6b09fa0c6ad2",{},"Регион размещения данных, условия международной передачи и сведения о поставщиках будут уточнены в окончательной редакции.")]],
   ['device',globalThis.UladimI18n.text("literal_86ba4af72f09",{},"Что остаётся на устройстве"),[
    globalThis.UladimI18n.text("literal_8c868b764a2f",{},"Браузер использует необходимый файл cookie для сохранения входа. На устройстве также сохраняются выбранные язык, тема и другие настройки интерфейса. Файлы интерфейса могут сохраняться для его загрузки. Рекламные cookie не используются."),
    globalThis.UladimI18n.text("literal_843de3ff70b3",{},"Локальные записи Android хранятся на устройстве. Сам вход в аккаунт не означает автоматическую загрузку всех локальных данных. Облачная обработка начинается для записей, которые вы создаёте в веб-приложении или явно синхронизируете."),
    globalThis.UladimI18n.text("literal_2431c67bafb4",{},"Файлы импорта обрабатываются на устройстве. После проверки и подтверждения в облако отправляются выбранные записи. Этот инструмент не загружает исходный файл выписки целиком.")]],
   ['retention',globalThis.UladimI18n.text("literal_9875bf9df1a0",{},"Сроки хранения и удаление"),[
    globalThis.UladimI18n.text("literal_5c0b61da977c",{},"Данные действующего аккаунта используются, пока нужны для предоставления выбранных вами функций. Удалить отдельные записи и запросить удаление аккаунта можно в приложении."),
    globalThis.UladimI18n.text("literal_4d3e526f8ded",{"arg0":(facts.deletionGraceHours)},"Запрос удаления аккаунта можно отменить в течение {arg0} часов, до указанного времени. После этого вход блокируется и начинается удаление; завершение может занять время. Удаление облачного аккаунта не стирает сохранённые на ваших устройствах копии."),
    facts.deletionPolicy||globalThis.UladimI18n.text("literal_dec5642ebc21",{},"Точный объём удаления личных данных, порядок обращения с общими записями и действия при исключительных обстоятельствах будут зафиксированы после проверки обновлённого процесса удаления."),
    facts.backupRetention?globalThis.UladimI18n.text("literal_f1d8e8b81538",{},"Резервные копии: ")+facts.backupRetention:globalThis.UladimI18n.text("literal_ac2886695e9f",{},"Срок хранения резервных копий и порядок исключения удалённых данных при восстановлении ещё уточняются. До подтверждения этих условий мы не обещаем мгновенное исчезновение данных из всех копий."),
    facts.securityRetention?globalThis.UladimI18n.text("literal_5865973630aa",{},"Данные безопасности: ")+facts.securityRetention:globalThis.UladimI18n.text("literal_e5fa14b1d1e3",{},"Состав и сроки хранения необходимых сведений безопасности будут указаны отдельно. Они не используются для рекламного профилирования.")]],
   ['rights',globalThis.UladimI18n.text("literal_eac9b6769e9c",{},"Как управлять своими данными"),[
    globalThis.UladimI18n.text("literal_82ae4d3e8279",{},"В профиле можно изменить доступные сведения аккаунта, проверить устройства, отозвать доступ, настроить защиту и запросить удаление. Экспортируйте нужные записи и проверьте созданный файл перед удалением."),
    globalThis.UladimI18n.text("literal_e5b2b5155e90",{},"Если нужно получить сведения об обработке, исправить данные, сообщить об ошибке или обратиться по поводу прав другого человека, используйте поддержку. Для защиты аккаунта может потребоваться подтвердить, что запрос относится к вам. Не передавайте пароль или одноразовый код сотруднику поддержки."),
    globalThis.UladimI18n.text("literal_64059f70ea74",{},"Право на обращение в компетентный орган и другие предусмотренные законом права сохраняются. Срок ответа и применимые процедуры зависят от подтверждённой юрисдикции оператора.")]],
   ['children',globalThis.UladimI18n.text("literal_11a600f8ecf0",{},"Семейные пространства и возраст"),[facts.minimumAgePolicy||globalThis.UladimI18n.text("literal_9fc7af3a547a",{},"Возрастные условия и порядок участия несовершеннолетних должны быть утверждены оператором до окончательной публикации. Наличие детской роли в семейном пространстве само по себе не заменяет согласие или участие законного представителя, если оно требуется законом."),globalThis.UladimI18n.text("literal_59f141a492d1",{},"Участник, добавляющий данные другого человека, должен иметь право на такое действие. Не размещайте в общих записях избыточные сведения о детях и других членах семьи.")]],
   ['changes',globalThis.UladimI18n.text("literal_cd65a8c51047",{},"Изменения политики"),[globalThis.UladimI18n.text("literal_850151f3ca93",{},"Дата и версия указаны в начале страницы. При изменении состава обработки или существенных условий новая редакция должна описывать эти изменения понятным языком. Согласие запрашивается отдельно там, где оно требуется законом.")]]
  ]:[
   ['operator',globalThis.UladimI18n.text("literal_d26f9e70635e",{},"О сервисе и операторе"),[operator,globalThis.UladimI18n.text("literal_7d1e02d74658",{},"ULADIM помогает вести задачи, заметки, календарь, личный финансовый учёт и общие семейные дела. Текущие функции предоставляются бесплатно."),ready()?globalThis.UladimI18n.text("literal_3fc9ccab6147",{},"Настоящая редакция описывает условия использования сервиса. Дата и версия указаны в начале страницы."):globalThis.UladimI18n.text("literal_13980ad0e528",{},"Окончательная публичная редакция условий будет действовать после заполнения и подтверждения сведений оператора.")]],
   ['account',globalThis.UladimI18n.text("literal_2b7dc80f13f1",{},"Аккаунт и безопасность"),[globalThis.UladimI18n.text("literal_a6b832042a7a",{},"Указывайте доступную вам электронную почту и подтверждайте её. Берегите пароль, коды подтверждения и резервные коды. Не передавайте аккаунт другому человеку. Если устройство потеряно, отзовите его доступ из профиля."),globalThis.UladimI18n.text("literal_4053c16afa84",{},"Используйте только аккаунты и пространства, к которым у вас есть право доступа. Не пытайтесь обходить защиту, читать чужие записи, мешать работе сервиса или распространять через него незаконный и вредоносный контент.")]],
   ['records',globalThis.UladimI18n.text("literal_e22dc5d4d5b2",{},"Ваши записи и общие пространства"),[globalThis.UladimI18n.text("literal_3dcd9109071d",{},"Вы сохраняете права на собственное содержимое. Размещая запись, вы разрешаете обработку, необходимую для выбранных вами функций и настроек доступа. Это не передаёт сервису право продавать ваши записи."),globalThis.UladimI18n.text("literal_9f670d6554d2",{},"Перед добавлением данных другого человека убедитесь, что вправе это сделать. Выбирайте пространство и участников осознанно. Изменение общих записей может повлиять на других участников; проверяйте последствия перед подтверждением.")]],
   ['availability',globalThis.UladimI18n.text("literal_65920b5d54ed",{},"Сохранение, синхронизация и доступность"),[globalThis.UladimI18n.text("literal_85a31ac3d53d",{},"Для сохранения и просмотра облачных записей нужно соединение. Локальные функции Android могут работать отдельно от облака. Если соединение пропало во время сохранения, проверьте состояние записи перед повторным вводом."),globalThis.UladimI18n.text("literal_bf01091cca8f",{},"Технические работы и сбои могут временно ограничивать доступ. Для важных записей сохраняйте собственную копию. Возможность восстановления зависит от доступных данных и срока хранения; поддержка не обещает восстановить любую удалённую запись.")]],
   ['finance',globalThis.UladimI18n.text("literal_70ed37ca6907",{},"Финансовый учёт"),[globalThis.UladimI18n.text("literal_27224901eec4",{},"ULADIM предназначен для записи и анализа введённых вами данных. Создание перевода в приложении не переводит деньги, не подключает банковский счёт и не выполняет платёж. Приложение не оказывает банковские, кредитные, брокерские или инвестиционные услуги."),globalThis.UladimI18n.text("literal_defe84c751b5",{},"Проверяйте исходные суммы, валюты и импорт перед сохранением. Финансовые результаты зависят от полноты и правильности введённых записей. Суммы в разных валютах не следует складывать без выбранного вами способа пересчёта.")]],
   ['plans',globalThis.UladimI18n.text("literal_f03459015fb8",{},"Бесплатный доступ и будущие подписки"),[globalThis.UladimI18n.text("literal_0950c4130218",{},"Все текущие функции доступны бесплатно. Банковская карта и оформление подписки не требуются. Отображаемый уровень доступа сам по себе не означает покупку или согласие на списания."),globalThis.UladimI18n.text("literal_b982908ebe6b",{},"Plus готовится как будущий вариант доступа. Его окончательные функции, цена, срок и условия продления пока не опубликованы. Возможности с искусственным интеллектом относятся к более поздним планам и сейчас недоступны."),globalThis.UladimI18n.text("literal_bb2a70232952",{},"До появления платной услуги её условия должны отдельно сообщать полную цену, период, правила продления, отмены, восстановления покупки и возврата. Новые платные условия не создают согласие на оплату автоматически.")]],
   ['refunds',globalThis.UladimI18n.text("literal_66ac80bd2d68",{},"Отмена и возвраты"),[globalThis.UladimI18n.text("literal_70c948fae8c0",{},"Сейчас реальные покупки и списания в ULADIM отключены, поэтому платная подписка здесь не оформляется. Если вы заметили незнакомое списание с похожим названием, проверьте получателя и обратитесь в банк или площадку, где оно было совершено."),globalThis.UladimI18n.text("literal_e4da3c6f3442",{},"Если платные услуги будут запущены, способ управления и возврата будет зависеть от места покупки и применимого закона. Для каждого способа оплаты понадобятся опубликованные правила и доступная поддержка. Эти условия не ограничивают обязательные права потребителя.")]],
   ['ending',globalThis.UladimI18n.text("literal_25672d9828a1",{},"Прекращение доступа и удаление"),[globalThis.UladimI18n.text("literal_ea67f4f4f096",{},"Вы можете перестать пользоваться сервисом и запросить удаление аккаунта. Облачное удаление и очистка данных на вашем устройстве выполняются отдельно. Перед удалением сохраните нужные записи и проверьте общие пространства."),globalThis.UladimI18n.text("literal_28dc3c660e18",{},"Доступ может быть ограничен для защиты пользователей и сервиса при нарушении правил или выявлении угрозы. Причина и доступный способ обращения должны сообщаться в пределах, допустимых законом и требованиями безопасности. Порядок удаления описан на отдельной странице.")]],
   ['age',globalThis.UladimI18n.text("literal_bafbb28e450a",{},"Семья и возраст"),[facts.minimumAgePolicy||globalThis.UladimI18n.text("literal_12a278dea57e",{},"Условия участия несовершеннолетних и законного представительства будут указаны после утверждения оператором. Не следует считать, что семейная роль автоматически подтверждает право использовать сервис в любом возрасте.")]],
   ['law',globalThis.UladimI18n.text("literal_e26a688464ce",{},"Ответственность и обращения"),[globalThis.UladimI18n.text("literal_b526fc5062e5",{},"Обязательные права, предоставленные вам применимым законом, сохраняются. Эти условия не исключают ответственность, которую нельзя исключить по закону."),ready()?globalThis.UladimI18n.text("literal_74671df00ce9",{},"Споры рассматриваются в порядке, предусмотренном применимым законом, с сохранением обязательных прав потребителя. Сведения об операторе и контакт для обращения указаны выше. Для начала можно описать вопрос в поддержке."):globalThis.UladimI18n.text("literal_b1818ce4f484",{},"Применяется законодательство Республики Узбекистан с сохранением обязательных прав, которые предоставляет вам применимый закон. Сначала можно направить обращение оператору. Подсудность и порядок рассмотрения спора определяются законом; эти условия не отменяют право обратиться в компетентный орган или суд.")]],
   ['changes',globalThis.UladimI18n.text("literal_4fef4a5eb736",{},"Обновления условий"),[globalThis.UladimI18n.text("literal_eb933a03c94e",{},"Дата и версия находятся в начале страницы. Существенные изменения публикуются в новой редакции. Появление новых платных возможностей требует отдельного понятного предложения и вашего согласия там, где оно необходимо.")]]
  ];
  reader(sections);related([[privacy?globalThis.UladimI18n.text("literal_4b5ef4dc258e",{},"Условия использования"):globalThis.UladimI18n.text("literal_6d5c24967752",{},"Конфиденциальность"),privacy?'/terms':'/privacy'],[globalThis.UladimI18n.text("literal_10d87746ac09",{},"Удаление аккаунта"),'/delete-account'],[globalThis.UladimI18n.text("literal_f0012086d52e",{},"Поддержка"),'/support']]);openHash();
 }
 const groups=[
  ['start',globalThis.UladimI18n.text("literal_b5b75c376dc8",{},"Начало работы"),globalThis.UladimI18n.text("literal_220146ba1295",{},"От первой записи до удобного дня"),[
   ['today',globalThis.UladimI18n.text("literal_cca4c262ad16",{},"С чего начать?"),globalThis.UladimI18n.text("literal_73103a2b3eb0",{},"Откройте ULADIM и добавьте одну задачу или заметку. Выберите личное пространство. После этого настройте календарь и финансовые счета — в том порядке, который удобен вам."),globalThis.UladimI18n.text("literal_be432c828c4d",{},"Открыть приложение"),'/app'],
   ['tasks',globalThis.UladimI18n.text("literal_d846e7692586",{},"Как вести задачи?"),globalThis.UladimI18n.text("literal_de785ebfd0a0",{},"Добавьте понятное название и дату, если она нужна. Завершённые задачи отмечайте выполненными. Для общих дел сначала выберите семейное пространство и проверьте исполнителя."),globalThis.UladimI18n.text("literal_53965ae5bf64",{},"Руководство"),'/docs#first-record'],
   ['notes',globalThis.UladimI18n.text("literal_29d6bd3f6f1e",{},"Где сохранять идеи и списки?"),globalThis.UladimI18n.text("literal_3fee821f6597",{},"Используйте заметки для текста, идей и списков. Перед сохранением проверьте личное или общее пространство. Перенести текст из другого приложения можно через импорт."),globalThis.UladimI18n.text("literal_2fa3a99f64a7",{},"О переносе заметок"),'/faq#import'],
   ['calendar',globalThis.UladimI18n.text("literal_9cc76f91a7ca",{},"Как планировать события?"),globalThis.UladimI18n.text("literal_97eb43370217",{},"Укажите начало события и часовой пояс. Для повторяющегося события проверьте правило повторения и ближайшие даты. Уведомления настраиваются отдельно на каждом устройстве."),globalThis.UladimI18n.text("literal_1255e657430d",{},"Об уведомлениях"),'/faq#notifications']
  ]],
  ['devices',globalThis.UladimI18n.text("literal_eb84ca12fa84",{},"Устройства и перенос"),globalThis.UladimI18n.text("literal_09035d6ee0d1",{},"Установка, синхронизация и файлы"),[
   ['installation',globalThis.UladimI18n.text("literal_081bbd37a711",{},"Как установить ULADIM?"),globalThis.UladimI18n.text("literal_acae2b7f904e",{},"На Android доступен отдельный APK. На iPhone, iPad и компьютере открывайте веб-приложение в браузере; его можно добавить на домашний экран. Отдельная версия для iOS пока не выпущена."),globalThis.UladimI18n.text("literal_99aea9c89143",{},"Приложения и установка"),'/download'],
   ['sync',globalThis.UladimI18n.text("literal_f3dcfdeec39d",{},"Почему записи отличаются на устройствах?"),globalThis.UladimI18n.text("literal_9aec3dd3de81",{},"Проверьте, что вошли в один аккаунт и выбрали одно пространство. Для облачной синхронизации нужно соединение. Сам вход в Android не переносит все локальные записи автоматически: используйте доступные средства импорта и синхронизации."),globalThis.UladimI18n.text("literal_fcd4605b0310",{},"Как перенести данные"),'/docs#import'],
   ['import',globalThis.UladimI18n.text("literal_751a77333f8a",{},"Как перенести записи из другого приложения?"),globalThis.UladimI18n.text("literal_8f53dbfa558c",{},"В веб-приложении откройте «Профиль → Импорт и синхронизация». Выберите тип данных и файл, проверьте предпросмотр и подтвердите только нужные записи. Заметки: TXT, Markdown и экспорт Google Keep. Календарь: ICS. Вложения и неподдерживаемые правила могут не перенестись — проверьте предупреждения."),globalThis.UladimI18n.text("literal_2e518dc76a07",{},"Пошаговый перенос"),'/docs#import'],
   ['import-original',globalThis.UladimI18n.text("literal_8f6db5e8aed0",{},"Изменит ли импорт исходные файлы?"),globalThis.UladimI18n.text("literal_decb5da45bdf",{},"Исходные файлы и записи в других приложениях остаются у вас. Файл читается на устройстве; после подтверждения в облако передаются выбранные записи. При повторном импорте проверьте совпадения в предпросмотре."),globalThis.UladimI18n.text("literal_aa97feeebb85",{},"Руководство по импорту"),'/docs#import'],
   ['notifications',globalThis.UladimI18n.text("literal_6af36a057c18",{},"Почему не пришло напоминание?"),globalThis.UladimI18n.text("literal_3f88c6fdd446",{},"Проверьте дату, время и часовой пояс события, разрешение уведомлений и настройки самого устройства. На Android ограничения батареи могут задерживать напоминания. В браузере разрешите уведомления именно для ULADIM. Включайте только те напоминания, которые вам нужны."),globalThis.UladimI18n.text("literal_6894f99e6bc4",{},"Помощь с устройством"),'/support']
  ]],
  ['money-family',globalThis.UladimI18n.text("literal_d827a1dd5678",{},"Финансы и семья"),globalThis.UladimI18n.text("literal_fd529d9eaeab",{},"Личный учёт и общие дела"),[
   ['finances',globalThis.UladimI18n.text("literal_6d6668cd9dc8",{},"Можно ли переводить деньги через ULADIM?"),globalThis.UladimI18n.text("literal_21962e2b43cf",{},"ULADIM ведёт учёт введённых вами сумм. Запись перевода перемещает сумму между счетами в вашем учёте; деньги в банке она не переводит. Проверяйте валюту и исходные данные, особенно после импорта."),globalThis.UladimI18n.text("literal_15d8243d39f9",{},"О финансовом учёте"),'/terms#finance'],
   ['family',globalThis.UladimI18n.text("literal_45b05db35b79",{},"Кто видит записи семьи?"),globalThis.UladimI18n.text("literal_11172e16f936",{},"Доступ зависит от выбранного пространства, роли участника и настроек записи. Личную заметку сохраняйте в личном пространстве. Перед добавлением в общую запись сведений о другом человеке убедитесь, что вправе ими делиться."),globalThis.UladimI18n.text("literal_e22fe57e8e8e",{},"Как устроен доступ"),'/privacy#sharing'],
   ['family-leave',globalThis.UladimI18n.text("literal_037b13d76cd7",{},"Что проверить перед уходом из семьи?"),globalThis.UladimI18n.text("literal_d62491a39562",{},"Сохраните нужные личные копии и проверьте общие дела. Владельцу может потребоваться передать управление другому взрослому участнику или явно завершить работу семейного пространства. Внимательно прочитайте последствия в окне подтверждения."),globalThis.UladimI18n.text("literal_e8b4671088a8",{},"Об удалении аккаунта"),'/delete-account']
  ]],
  ['account-group',globalThis.UladimI18n.text("literal_024c259f41e0",{},"Аккаунт и защита"),globalThis.UladimI18n.text("literal_c53f13bea273",{},"Вход, восстановление и приватность"),[
   ['account',globalThis.UladimI18n.text("literal_3b5cba98021e",{},"Нужен ли аккаунт?"),globalThis.UladimI18n.text("literal_f2e0b51d7fc3",{},"Аккаунт нужен для облачных записей и общих пространств. Локальные функции Android могут использоваться отдельно. Для входа используйте свой подтверждённый адрес почты или подключённый Google."),globalThis.UladimI18n.text("literal_612f724ec00f",{},"Открыть аккаунт"),'/account'],
   ['security',globalThis.UladimI18n.text("literal_50d22e97f77b",{},"Как защитить аккаунт?"),globalThis.UladimI18n.text("literal_181c94ecd6f2",{},"Выберите уникальный пароль и включите доступную двухфакторную защиту. Сохраните резервные коды в безопасном месте. В профиле проверьте устройства и отзовите потерянные. Никому не сообщайте коды и пароль, в том числе в поддержке."),globalThis.UladimI18n.text("literal_3ba8eaa5d624",{},"Политика конфиденциальности"),'/privacy'],
   ['recovery',globalThis.UladimI18n.text("literal_27edc9f43d34",{},"Как восстановить доступ?"),globalThis.UladimI18n.text("literal_6ed0f3a60301",{},"На странице входа выберите восстановление пароля и укажите почту аккаунта. Проверьте входящие и папку «Спам». Если использовали Google, попробуйте тот же Google-аккаунт. Если вход недоступен или доступ ограничен, обратитесь в поддержку."),globalThis.UladimI18n.text("literal_667f75f36121",{},"Войти или восстановить"),'/account'],
   ['privacy',globalThis.UladimI18n.text("literal_ae8bbabbe46a",{},"Есть ли реклама и сбор аналитики?"),globalThis.UladimI18n.text("literal_95c072bd7545",{},"Рекламных трекеров и рекламной аналитики нет. Сервис обрабатывает необходимые данные аккаунта, записи, которые вы сохраняете, и сведения для безопасности. Подробности о поставщиках, доступе и сроках приведены в политике."),globalThis.UladimI18n.text("literal_b110ddb1ee17",{},"Какие данные используются"),'/privacy#data'],
   ['deletion',globalThis.UladimI18n.text("literal_21ca19d58fc5",{},"Как удалить аккаунт и данные?"),globalThis.UladimI18n.text("literal_bbdb310e9901",{},"Откройте удаление аккаунта в профиле. Сначала сохраните нужное и проверьте общие пространства. Запрос можно отменить в течение 24 часов до указанного времени. Затем вход блокируется и начинается удаление; завершение может занять время. Все созданные вами записи, в том числе общие, удаляются. Копии на устройствах очищаются отдельно."),globalThis.UladimI18n.text("literal_1738fd6a9134",{},"Открыть удаление аккаунта"),'/app?settings=deletion'],
   ['delete-staff-account',globalThis.UladimI18n.text("literal_98d5abc6cfc7",{},"Как удалить аккаунт, если я сотрудник сервиса?"),globalThis.UladimI18n.text("literal_497a542cb499",{},"Сначала передайте рабочие обязанности и завершите служебный доступ через уполномоченного владельца сервиса. Для единственного владельца потребуется сохранить возможность управления сервисом после передачи. Эта страница не выдаёт новые права и не выполняет передачу автоматически. Затем вернитесь к обычному удалению аккаунта."),globalThis.UladimI18n.text("literal_90db24a173da",{},"Обратиться в поддержку"),'/support']
  ]],
  ['access',globalThis.UladimI18n.text("literal_d1532fee320a",{},"Доступ и поддержка"),globalThis.UladimI18n.text("literal_acd036ab319b",{},"Бесплатные функции и помощь"),[
   ['plans',globalThis.UladimI18n.text("literal_9e6bc58208dc",{},"Нужно ли платить за ULADIM?"),globalThis.UladimI18n.text("literal_ae25c9661d9e",{},"Сейчас все доступные функции бесплатны. Карта и подписка не нужны. Plus готовится на будущее; цены и окончательные различия ещё не опубликованы. Возможности с искусственным интеллектом сейчас недоступны."),globalThis.UladimI18n.text("literal_b2fbb44bb3e3",{},"Тарифы"),'/plans'],
   ['refund',globalThis.UladimI18n.text("literal_de4bcbe3983d",{},"Как отменить подписку или вернуть оплату?"),globalThis.UladimI18n.text("literal_7f1ba3e1d91b",{},"Сейчас покупки отключены и подписка в ULADIM не оформляется. Если платные услуги появятся, условия цены, продления, отмены и возврата будут опубликованы до оплаты. Незнакомое списание проверьте у банка или площадки покупки."),globalThis.UladimI18n.text("literal_4b5ef4dc258e",{},"Условия использования"),'/terms#refunds'],
   ['support',globalThis.UladimI18n.text("literal_8545a69006f8",{},"Как получить помощь?"),globalThis.UladimI18n.text("literal_1943f3c7cb7d",{},"Опишите, что хотели сделать, на каком шаге возникла проблема и какой текст появился на экране. Укажите устройство и версию приложения. Скройте личные данные на снимке экрана. Пароли, коды и банковские документы не нужны."),globalThis.UladimI18n.text("literal_1162749e334c",{},"Связаться с поддержкой"),'/support']
  ]]
 ];
 function openHash(){
  let id;try{id=decodeURIComponent(location.hash.slice(1));}catch{return;}if(!id)return;const target=document.getElementById(id);if(!target)return;
  if(target.tagName==='DETAILS')target.open=true;
  requestAnimationFrame(()=>{target.scrollIntoView({block:'start'});});
 }
 function faq(){
  intro(globalThis.UladimI18n.text("literal_bc4d55d87d90",{},"ЦЕНТР ПОМОЩИ"),globalThis.UladimI18n.text("literal_586ce98ef5aa",{},"Найдём ответ"),globalThis.UladimI18n.text("literal_87acdc423c70",{},"Начало работы, перенос записей, семья и приватность — всё в одном месте."));
  const search=node('div',undefined,'help-search');const label=node('label',globalThis.UladimI18n.text("literal_e7168d12aa92",{},"О чём хотите узнать?"));label.htmlFor='help-search';const input=node('input');input.id='help-search';input.type='search';input.placeholder=globalThis.UladimI18n.text("literal_f0e4ab6a93f2",{},"Например: импорт, уведомления, удаление");input.autocomplete='off';
  const count=node('p','','help-result-count');count.setAttribute('role','status');count.setAttribute('aria-live','polite');add(search,label,input,count);app.append(search);
  const layout=node('div',undefined,'help-reader'),nav=node('nav',undefined,'help-toc'),content=node('div',undefined,'help-faq-groups');nav.setAttribute('aria-label',globalThis.UladimI18n.text("literal_e1ba2ef51839",{},"Темы помощи"));nav.append(node('p',globalThis.UladimI18n.text("literal_4604dc444bab",{},"Выберите тему"),'help-kicker'));
  const entries=[];
  for(const [id,title,subtitle,questions]of groups){
   nav.append(a(title,'#'+id));const section=node('section',undefined,'help-faq-group');section.id=id;section.append(node('h2',title),node('p',subtitle,'help-muted'));
   for(const [anchor,q,answer,label,href]of questions){const details=node('details',undefined,'help-question');details.id=anchor;const body=node('div',undefined,'help-answer');body.append(node('p',answer),inline(label,href));details.append(node('summary',q),body);section.append(details);entries.push({details,section,text:(title+' '+q+' '+answer).toLocaleLowerCase(authLanguage)});}
   content.append(section);
  }
  const empty=node('section',undefined,'help-empty');empty.hidden=true;empty.append(node('h2',globalThis.UladimI18n.text("literal_5e66543c50c2",{},"Пока не нашли подходящий ответ")),node('p',globalThis.UladimI18n.text("literal_0f63f541fe17",{},"Попробуйте другое слово или напишите нам — подскажем, с чего начать.")),inline(globalThis.UladimI18n.text("literal_611cda719a59",{},"Получить помощь"),'/support'));content.append(empty);layout.append(nav,content);app.append(layout);
  function filter(){const query=input.value.trim().toLocaleLowerCase(authLanguage);const words=query.split(/\s+/).filter(Boolean);let visible=0;
   for(const entry of entries){const match=words.every(word=>entry.text.includes(word));entry.details.hidden=!match;if(match)visible++;if(query&&match)entry.details.open=true;else if(!query)entry.details.open=entry.details.id===location.hash.slice(1);}
   for(const section of content.querySelectorAll('.help-faq-group'))section.hidden=!entries.some(entry=>entry.section===section&&!entry.details.hidden);
   empty.hidden=visible>0;count.textContent=query?globalThis.UladimI18n.text("literal_94f789754a4a",{},"Найдено ответов: ")+visible:globalThis.UladimI18n.text("literal_0827a176a4d6",{},"Ответы по темам: ")+entries.length;
  }
  input.addEventListener('input',filter);nav.addEventListener('click',()=>{if(input.value){input.value='';filter();}});
  window.addEventListener('hashchange',openHash);filter();openHash();related([[globalThis.UladimI18n.text("literal_53965ae5bf64",{},"Руководство"),'/docs'],[globalThis.UladimI18n.text("literal_a95642d636d1",{},"Установка"),'/download'],[globalThis.UladimI18n.text("literal_4baae6995fd4",{},"Задать вопрос"),'/support']]);
 }
 function support(){
  intro(globalThis.UladimI18n.text("literal_cbcaa985d7d6",{},"МЫ РЯДОМ"),globalThis.UladimI18n.text("literal_1fabc98b1337",{},"Поможем разобраться"),globalThis.UladimI18n.text("literal_99d6ca68e466",{},"Вопрос о записи, входе или своих данных — начните с удобного способа связи."));
  const grid=node('div',undefined,'help-support-grid');
  const own=block(globalThis.UladimI18n.text("literal_d7e86e0aa9e5",{},"Есть доступ к аккаунту"),globalThis.UladimI18n.text("literal_e1bfd4b93806",{},"Отправьте обращение из профиля: там сохранятся ваш вопрос и ответ. Выберите подходящую тему — так будет проще разобраться."));own.append(link(globalThis.UladimI18n.text("literal_612f724ec00f",{},"Открыть аккаунт"),'/account'));grid.append(own);
  const no=block(globalThis.UladimI18n.text("literal_4676b0db9bd2",{},"Не получается войти?"),globalThis.UladimI18n.text("literal_c8549a27d3d7",{},"Попробуйте восстановить пароль или войти тем же Google-аккаунтом. Для вопроса об ограничении доступа или своих данных не передавайте средства входа."));no.append(inline(globalThis.UladimI18n.text("literal_779b8c2386ff",{},"Помощь со входом"),'/faq#recovery'));contactLink(no);grid.append(no);app.append(grid);
  const how=block(globalThis.UladimI18n.text("literal_ae7e6bcda6de",{},"Что поможет быстрее найти решение"),globalThis.UladimI18n.text("literal_eed37ed7f3c2",{},"Опишите ожидаемый результат, действие перед ошибкой и сообщение на экране. Добавьте модель устройства, браузер и версию приложения, если знаете их."),globalThis.UladimI18n.text("literal_24621ae0e8c1",{},"На снимке экрана закройте имена, адреса, суммы и другие личные сведения, которые не относятся к вопросу."),safety());app.append(how);
  related([[globalThis.UladimI18n.text("literal_a3ca1c94161e",{},"Вопросы и ответы"),'/faq'],[globalThis.UladimI18n.text("literal_651cff325357",{},"Запрос о данных"),'/privacy#rights'],[globalThis.UladimI18n.text("literal_10d87746ac09",{},"Удаление аккаунта"),'/delete-account']]);
 }
 function deletion(){
  intro(globalThis.UladimI18n.text("literal_3458fb2e8588",{},"ВАШ АККАУНТ"),globalThis.UladimI18n.text("literal_10d87746ac09",{},"Удаление аккаунта"),globalThis.UladimI18n.text("literal_0d703b0a48fb",{},"Проверьте последствия, сохраните нужное и подтвердите решение."));
  const callout=node('aside',undefined,'help-callout');callout.append(node('strong',globalThis.UladimI18n.text("literal_b88de35d8444",{},"Есть время передумать")),node('p',globalThis.UladimI18n.text("literal_d7dfae9fab62",{"arg0":(facts.deletionGraceHours)},"Запрос можно отменить в течение {arg0} часов до указанного времени. Затем вход блокируется и начинается удаление; завершение может занять время.")));app.append(callout);
  const steps=node('ol',undefined,'help-steps');for(const [title,text]of [
   [globalThis.UladimI18n.text("literal_90eaabcf59b4",{},"Сохраните нужные записи"),globalThis.UladimI18n.text("literal_0e291f1319d2",{},"Экспортируйте данные, которые хотите оставить, и убедитесь, что созданный файл открывается.")],
   [globalThis.UladimI18n.text("literal_2f9129c7fd44",{},"Проверьте общие пространства"),globalThis.UladimI18n.text("literal_27a279ab8d58",{},"Если управляете семьёй, передайте управление другому взрослому участнику или явно закройте семейное пространство. При закрытии участники потеряют облачный доступ к этому пространству. Сначала прочитайте последствия; записи других участников не становятся вашими и не передаются вам.")],
   [globalThis.UladimI18n.text("literal_b49347d36b08",{},"Откройте удаление в профиле"),globalThis.UladimI18n.text("literal_f1b44ce13755",{},"Войдите в аккаунт, откройте раздел аккаунта и приватности и выберите удаление. Подтвердите, что действие выполняете вы, и прочитайте итоговое предупреждение.")],
   [globalThis.UladimI18n.text("literal_a9fad6768933",{},"Дождитесь окончания срока отмены"),globalThis.UladimI18n.text("literal_85b1e59a1e4a",{},"Если передумали, вернитесь в тот же раздел до окончания 24 часов и отмените запрос. После окончания 24 часов вход блокируется и начинается удаление. Завершение может занять время; окончание срока отмены не означает, что данные уже стёрты.")]
  ])steps.append(add(node('li'),node('h2',title),node('p',text)));app.append(steps,link(globalThis.UladimI18n.text("literal_1738fd6a9134",{},"Открыть удаление аккаунта"),'/app?settings=deletion'));
  reader([
   ['removed',globalThis.UladimI18n.text("literal_fdd6315df1fc",{},"Что будет удалено"),[facts.deletionPolicy||globalThis.UladimI18n.text("literal_cb6a1ac1d4c9",{},"Удаление предназначено для прекращения облачного аккаунта и удаления связанных с ним личных данных. Точный перечень и порядок для общих записей уточняются в проверяемом процессе удаления; окончательная политика ещё не опубликована.")]],
   ['separate-mail',globalThis.UladimI18n.text("literal_7eaa7b9f5efe",{},"Письма в поддержку"),[facts.correspondenceRetention||globalThis.UladimI18n.text("literal_973d04eaedce",{},"Обращения внутри приложения удаляются вместе с аккаунтом. Письма, которые вы отправляли отдельно по электронной почте, и копии у почтовых поставщиков обрабатываются отдельно. Стандартный срок хранения писем у поставщика поддержки — ")+facts.supportProviderRetentionDays+globalThis.UladimI18n.text("literal_04042d99e696",{}," дней; работа почтового канала и порядок очистки ещё подтверждаются.")]],
   ['local-copy',globalThis.UladimI18n.text("literal_d5adbef28180",{},"Что проверить на устройствах"),[globalThis.UladimI18n.text("literal_288ca7a93d56",{},"Удаление облачного аккаунта не очищает автоматически локальную базу Android, сделанные вами экспорты и копии на других устройствах. Если хотите удалить и их, отдельно очистите данные приложения и собственные файлы после сохранения нужного. Не удаляйте приложение ради обычного обновления.")]],
   ['backups',globalThis.UladimI18n.text("literal_e69afbe6f5f9",{},"Резервные копии"),[facts.backupRetention||globalThis.UladimI18n.text("literal_458e067f5afb",{},"Подтверждённый срок хранения резервных копий и порядок исключения удалённых данных при восстановлении будут указаны в окончательной политике. Мгновенное стирание всех резервных копий пока не заявляется.")]],
   ['no-access',globalThis.UladimI18n.text("literal_dd0aed1ba2cf",{},"Если вход недоступен"),[globalThis.UladimI18n.text("literal_88d815fae682",{},"Попробуйте восстановить доступ. Если это невозможно, обратитесь по вопросу удаления через доступный контакт поддержки. Для защиты ваших данных потребуется подтвердить принадлежность аккаунта. Пароль и одноразовый код сообщать поддержке не нужно.")]]
  ]);contactLink(app,globalThis.UladimI18n.text("literal_48f48c65f176",{},"Обратиться по вопросу удаления"));related([[globalThis.UladimI18n.text("literal_2a3c80d1c3b9",{},"Восстановление доступа"),'/faq#recovery'],[globalThis.UladimI18n.text("literal_6d5c24967752",{},"Конфиденциальность"),'/privacy#retention'],[globalThis.UladimI18n.text("literal_f0012086d52e",{},"Поддержка"),'/support']]);openHash();
 }
 // The optional edge manifest is published only after the signed APK is
 // verified. Validate the whole immutable tuple before replacing any content.
 let downloadRequest=null;
 function validatedAndroidRelease(value){
  const keys=['source','version_code','version_name','bytes','apk_url','apk_sha256','certificate_sha256'];
  if(!value||typeof value!=='object'||Array.isArray(value)||Object.keys(value).length!==keys.length||!keys.every(key=>Object.hasOwn(value,key)))return null;
  if(typeof value.source!=='string'||!/^[a-f0-9]{40}$/.test(value.source))return null;
  if(!Number.isSafeInteger(value.version_code)||value.version_code<312001||value.version_code>2100000000)return null;
  if(!Number.isSafeInteger(value.bytes)||value.bytes<1||value.bytes>2147483647)return null;
  const name=value.version_name;
  if(name!==null&&(typeof name!=='string'||name.length>80||/[\u0000-\u001f\u007f]/.test(name)||name.trim()!==name))return null;
  const release='https://github.com/pro100umarchikgamer-lgtm/lifeos/releases/tag/uladim-native-'+value.source.slice(0,12);
  const url='https://github.com/pro100umarchikgamer-lgtm/lifeos/releases/download/uladim-native-'+value.source.slice(0,12)+'/ULADIM.apk';
  if(value.apk_url!==url||typeof value.apk_sha256!=='string'||!/^[a-f0-9]{64}$/.test(value.apk_sha256)||value.certificate_sha256!==PUBLIC_RELEASE_FACTS.android.certificateSha256)return null;
  return Object.freeze({source:value.source,certificateSha256:value.certificate_sha256,version:name||null,build:value.version_code,bytes:value.bytes,url,sha256:value.apk_sha256,release,minAndroid:PUBLIC_RELEASE_FACTS.android.minAndroid});
 }
 async function sameOriginAndroidRelease(android,signal){
  const url='/download/android/'+android.source+'/ULADIM.apk';
  try{
   const response=await fetch(url,{method:'HEAD',credentials:'omit',cache:'no-store',redirect:'error',signal});
   const h=response.headers;
   if(response.status!==200||(h.get('Content-Type')||'').split(';')[0].trim().toLowerCase()!=='application/vnd.android.package-archive'||h.get('Content-Length')!==String(android.bytes)||h.get('ETag')!=='"sha256-'+android.sha256+'"'||h.get('X-ULADIM-Source')!==android.source||h.get('X-ULADIM-Version-Code')!==String(android.build)||h.get('X-ULADIM-APK-SHA256')!==android.sha256||h.get('X-ULADIM-Certificate-SHA256')!==android.certificateSha256)return android;
   return Object.freeze({...android,url,sameOrigin:true});
  }catch{return android;}
 }
 function androidReleaseCard(android){
  const card=block(globalThis.UladimI18n.text("literal_f3233bf59e09",{},"Приложение для Android"),globalThis.UladimI18n.text("literal_4412e7cf1974",{},"Доступная сборка для прямой установки. Скачивайте APK только по официальной ссылке ниже."));card.id='android';card.classList.add('help-android-release');
  card.dataset.source=android.source;card.dataset.versionCode=String(android.build);card.dataset.apkBytes=String(android.bytes);card.dataset.apkSha256=android.sha256;card.dataset.certificateSha256=android.certificateSha256;
  const title=android.version?globalThis.UladimI18n.text("literal_83c21cec4c45",{},"Версия ")+android.version:'Android';
  const download=link(globalThis.UladimI18n.text("literal_df5db67a6789",{},"Скачать APK для Android"),android.url);download.dataset.releaseDownload='';if(android.sameOrigin){download.download='ULADIM.apk';download.dataset.delivery='same-origin';}
  const notes=inline(android.sameOrigin?globalThis.UladimI18n.text("literal_60c68404b7b0",{},"Как установить приложение?"):globalThis.UladimI18n.text("literal_0436a8c80cfb",{},"Сведения об этой сборке"),android.sameOrigin?'/faq':android.release);notes.dataset.releaseNotes='';
  card.append(node('p',globalThis.UladimI18n.text("template_1639ae3b8823",{"arg0":(title),"arg1":(android.build),"arg2":((android.bytes/1000000).toLocaleString(authLanguage,{maximumFractionDigits:1})),"arg3":(android.minAndroid)},"{arg0} · сборка {arg1} · {arg2} МБ · {arg3} и новее"),'help-download-meta'),download,notes);
  const hash=node('details',undefined,'help-question');hash.append(node('summary',globalThis.UladimI18n.text("literal_89bd120c1894",{},"Как проверить скачанный файл?")));const body=node('div',undefined,'help-answer');body.append(node('p',globalThis.UladimI18n.text("literal_2e92fb309bd3",{},"Для доступной сборки контрольная сумма SHA-256:")),node('code',android.sha256,'help-digest'),node('p',globalThis.UladimI18n.text("literal_66354fdb6aae",{},"Контрольная сумма помогает убедиться, что файл совпадает с опубликованным. Если значения отличаются, не устанавливайте файл и сообщите в поддержку.")));hash.append(body);card.append(hash);
  return card;
 }
 async function refreshAndroidRelease(card){
  downloadRequest?.abort();
  const controller=new AbortController();downloadRequest=controller;
  const epoch=viewEpoch,timer=setTimeout(()=>controller.abort(),8000);
  try{
   const response=await fetch('/download/release.json',{method:'GET',credentials:'omit',cache:'no-store',redirect:'error',signal:controller.signal});
   if(response.status!==200||(response.headers.get('Content-Type')||'').split(';')[0].trim().toLowerCase()!=='application/json'||Number(response.headers.get('Content-Length')||0)>4096)return;
   const text=await response.text();if(text.length>4096)return;
   const verified=validatedAndroidRelease(JSON.parse(text));if(!verified)return;
   const android=await sameOriginAndroidRelease(verified,controller.signal);
   if(!android||controller.signal.aborted||epoch!==viewEpoch||location.pathname!=='/download'||!card.isConnected||!app.contains(card))return;
   // One subtree replacement publishes version, size, URLs and digest together.
   card.replaceWith(androidReleaseCard(android));
  }catch{/* Keep the complete verified fallback for unavailable or invalid metadata. */}
  finally{clearTimeout(timer);if(downloadRequest===controller)downloadRequest=null;}
 }
 function download(){
  intro(globalThis.UladimI18n.text("literal_32f2e663143a",{},"ULADIM НА ВАШИХ УСТРОЙСТВАХ"),globalThis.UladimI18n.text("literal_ce402064b0c3",{},"Ближе к вашему дню"),globalThis.UladimI18n.text("literal_8ef098988ba7",{},"В браузере на телефоне и компьютере. Отдельное приложение — для Android."));
  const grid=node('div',undefined,'help-download-grid'),web=block(globalThis.UladimI18n.text("literal_5a07ca917db2",{},"Открыть в браузере"),globalThis.UladimI18n.text("literal_57936cce6e13",{},"На iPhone, iPad, Android, Windows, macOS и Linux. Можно пользоваться во вкладке или добавить значок на домашний экран."));web.append(link(globalThis.UladimI18n.text("literal_17cc8a5ee310",{},"Открыть ULADIM"),'/app'),inline(globalThis.UladimI18n.text("literal_e1b2f32fe7ae",{},"Добавить на домашний экран"),'#installation'));grid.append(web);
  const card=androidReleaseCard(PUBLIC_RELEASE_FACTS.android);grid.append(card);app.append(grid);
  const update=block(globalThis.UladimI18n.text("literal_01761fcb1308",{},"Обновление без потери записей"),globalThis.UladimI18n.text("literal_64ad3309d540",{},"Установите новую официальную версию поверх уже установленной. Не удаляйте приложение и не очищайте его данные ради обновления. Если Android предлагает удалить прежнюю версию, остановитесь и обратитесь в поддержку."),globalThis.UladimI18n.text("literal_6012bd3aa9eb",{},"Перед обновлением важных локальных данных сделайте собственную резервную копию. Установка APK может потребовать временно разрешить установку из выбранного браузера или файлового приложения; после установки разрешение можно отключить."));app.append(update);
  installGuide(app);related([[globalThis.UladimI18n.text("literal_32072150adca",{},"Помощь с установкой"),'/faq#installation'],[globalThis.UladimI18n.text("literal_f0012086d52e",{},"Поддержка"),'/support']]);openHash();
  refreshAndroidRelease(card);
 }
 return {configure,legal,faq,support,deletion,download};
})();

async function staffReferrals(){heading(globalThis.UladimI18n.text("literal_b0b0c93a7c1e",{},"Приглашения"),globalThis.UladimI18n.text("literal_a2273fdc4fee",{},"Приглашённые пользователи и подтверждённые результаты."));const container=el('div');app.append(container);if(window.UladimReferrals)await UladimReferrals.admin(container,{request:api,onUser:staffUser});}
