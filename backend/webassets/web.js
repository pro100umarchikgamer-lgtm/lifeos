'use strict';
const app=document.querySelector('#app');
try{const appearance=JSON.parse(localStorage.getItem('uladim-interface')||'{}');document.body.dataset.theme=appearance.theme||'system';}catch{document.body.dataset.theme='system';}
const staff=document.documentElement.dataset.surface==='control';
if(staff){document.body.dataset.control='true';document.title='ULADIM Control';}
const prefix=staff?'/control/api/':'/account/api/';
let csrf='',viewEpoch=0;
let controlNavigation=null;
let authPacks={},authLanguage='ru',googleEnabled=false;
try{authLanguage=JSON.parse(localStorage.getItem('uladim-interface')||'{}').lang||'ru';}catch{}
const tr=k=>authPacks[authLanguage]?.strings[k]||authPacks.ru?.strings[k]||k;
function authLanguages(){const f=el('div',undefined,'auth-language');const label=el('label',tr('language'));const select=el('select');select.setAttribute('aria-label',tr('language'));for(const [key,value]of Object.entries(authPacks)){const option=el('option',value.name);option.value=key;select.append(option);}select.value=authLanguage;select.addEventListener('change',()=>{authLanguage=select.value;try{const saved=JSON.parse(localStorage.getItem('uladim-interface')||'{}');saved.lang=authLanguage;localStorage.setItem('uladim-interface',JSON.stringify(saved));}catch{}login();});add(f,label,select);app.append(f);document.documentElement.lang=authLanguage;}
const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
const add=(parent,...children)=>{for(const c of children)parent.append(c);return parent;};
const link=(label,path,secondary=false)=>{const a=el('a',label,'button'+(secondary?' secondary':''));a.href=path;return a;};
const errors={unauthorized:'Войдите в аккаунт.',invalid_credentials:'Проверьте почту и пароль.',staff_auth_invalid:'Проверьте данные входа и новый код MFA.',rate_limited:'Слишком много попыток. Подождите перед повтором.',staff_forbidden:'Для этого действия нет разрешения.',csrf_invalid:'Обновите страницу и повторите действие.',verify_email:'Сначала подтвердите почту в приложении.',registration_closed:'Регистрация пока доступна только приглашённым тестировщикам.',announcement_text_invalid:'Укажите обычный текст: заголовок до 160, сообщение до 4000 знаков.',announcement_invalid:'Проверьте формат сообщения и аудиторию.',announcement_audience_invalid:'Проверьте ID получателей: нужны действующие подтверждённые аккаунты.',announcement_schedule_invalid:'Проверьте начало показа и срок сообщения.',announcement_link_invalid:'Разрешены только внутренние ссылки /app.',announcement_expired:'Срок сообщения завершён. Создайте новый черновик.',revision_conflict:'Сообщение изменилось. Обновите список черновиков.'};
async function api(path,body){const epoch=viewEpoch;const response=await fetch(prefix+path,{method:body?'POST':'GET',credentials:'same-origin',headers:body?{'Content-Type':'application/json','X-CSRF-Token':csrf}:{},body:body?JSON.stringify(body):undefined});const value=await response.json();if(epoch!==viewEpoch)throw new Error('Обновите страницу и повторите действие.');if(!response.ok){const error=new Error(authPacks[authLanguage]?.strings['family_error_'+value.error]||errors[value.error]||tr('family_error_invalid_input'));error.code=value.error;throw error;}return value;}
function heading(title,description){app.replaceChildren(el('div',staff?'ULADIM Control':'ULADIM','eyebrow'),el('h1',title));if(description)app.append(el('p',description));if(staff&&controlNavigation)app.append(controlNavigation);}
function notice(text){app.append(el('div',text,'notice'));}
function panel(title,body){return add(el('section',undefined,'card'),el('h2',title),el('p',body));}
function field(form,name,label,type='text'){const id='field-'+name+'-'+crypto.randomUUID();const l=el('label',label);l.htmlFor=id;const input=el(name==='message'?'textarea':'input');input.id=id;input.name=name;if(name!=='message')input.type=type;input.required=true;if(type==='password')input.autocomplete='current-password';form.append(l,input);return input;}
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
   const divider=el('div',({ru:'или','uz-Latn':'yoki','uz-Cyrl':'ёки'})[authLanguage]||'or','focus-login-divider');
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
 categories:{account:'Аккаунт и вход',sync:'Синхронизация',billing:'Тарифы и доступ',bug:'Ошибка в приложении',complaint:'Жалоба',privacy:'Приватность',deletion:'Удаление аккаунта',other:'Другой вопрос'},
 states:{open:'Открыто',waiting:'Ожидает ответа',resolved:'Решено'},
 priorities:{low:'Низкий',normal:'Обычный',high:'Высокий',urgent:'Срочный'}
};}
async function support(){
 const result=await api('support'),labels=supportLabels();
 heading(staff?'Обращения и жалобы':'Поддержка',staff?'Работайте с сообщениями, которые пользователь отправил сам. Личные задачи, финансы и заметки недоступны.':'Не отправляйте пароли, коды, банковские выписки или личные документы.');
 const filters=el('div',undefined,'control-queue-filters'),list=el('div',undefined,'control-ticket-list');
 const selections={};
 for(const [name,title,choices]of [['state','Состояние',labels.states],['category','Тип обращения',labels.categories]]){
  const label=el('label',title),select=el('select');select.id='support-filter-'+name;select.setAttribute('aria-label',title);label.htmlFor=select.id;
  const all=el('option','Все');all.value='';select.append(all);
  for(const [value,text]of Object.entries(choices)){const option=el('option',text);option.value=value;select.append(option);}
  add(filters,add(el('div'),label,select));selections[name]=select;
 }
 add(app,filters,list);
 function renderTickets(){
  list.replaceChildren();
  const tickets=(result.tickets||[]).filter(ticket=>(!selections.state.value||ticket.state===selections.state.value)&&(!selections.category.value||ticket.category===selections.category.value));
  if(!tickets.length)list.append(el('p','Обращений по этим условиям пока нет.','notice'));
  for(const ticket of tickets){
   const row=add(el('section',undefined,'card control-ticket'),el('p',(labels.categories[ticket.category]||ticket.category)+' · '+(labels.states[ticket.state]||ticket.state),'control-ticket-meta'),el('h2',ticket.subject));
   row.dataset.category=ticket.category;
   if(staff)row.append(el('p','Приоритет: '+(labels.priorities[ticket.priority]||ticket.priority),'small'));
   action('Открыть обращение',()=>supportThread(ticket.id),row);list.append(row);
  }
 }
 Object.values(selections).forEach(select=>select.addEventListener('change',renderTickets));renderTickets();
 if((result.tickets||[]).length===100)app.append(el('p','Показаны 100 последних обращений.','small'));
 if(!staff){
  const f=form('Новое обращение',[['subject','Тема','text'],['message','Сообщение','text']],'Отправить',async b=>{await api('support',{...b,category:f.elements.category.value});await support();});
  selectField(f,'category','Тип обращения',Object.entries(labels.categories));f.elements.category.value='other';f.elements.subject.maxLength=160;f.elements.message.maxLength=8000;
 }
}
async function supportThread(id){
 const [result,session]=await Promise.all([api('thread?id='+encodeURIComponent(id)),staff?api('session'):Promise.resolve(null)]),labels=supportLabels();
 heading(result.ticket.subject,(labels.categories[result.ticket.category]||result.ticket.category)+' · '+(labels.states[result.ticket.state]||result.ticket.state));
 const actions=el('div',undefined,'actions');app.append(actions);action('Все обращения',support,actions);
 if(session?.permissions.includes('users.read'))action('Открыть аккаунт',()=>staffUser(result.ticket.user_id),actions);
 const thread=el('section',undefined,'control-support-thread');app.append(thread);
 for(const message of result.messages){const item=panel(message.is_staff?'Поддержка':staff?'Пользователь':'Вы',message.body);item.classList.add('support-message');item.dataset.staff=String(Boolean(message.is_staff));thread.append(item);}
 if(!staff||session.permissions.includes('support.reply')){
  const reply=form('Ответить',[['message','Сообщение','text']],'Отправить ответ',async b=>{await api('support/reply',{...b,ticket_id:id,state:staff?'waiting':'open'});await supportThread(id);});reply.elements.message.maxLength=8000;
 }
 if(session?.permissions.includes('support.reply')){
  const triage=form('Состояние и приоритет',[['reason','Причина изменения для журнала','text']],'Сохранить состояние',async b=>{await api('support/triage',{ticket_id:id,priority:triage.elements.priority.value,state:triage.elements.state.value,reason:b.reason});await supportThread(id);});
  triage.classList.add('control-triage');triage.elements.reason.maxLength=500;
  selectField(triage,'priority','Приоритет',Object.entries(labels.priorities)).value=result.ticket.priority;
  selectField(triage,'state','Состояние',Object.entries(labels.states)).value=result.ticket.state;
 }
}
async function dashboard(){const session=await api('session');csrf=session.csrf;if(!staff){location.replace('/app');return;}controlNavigation=null;delete document.body.dataset.auth;heading(staff?'Обзор сервиса':'Ваш ULADIM',staff?'Операционные показатели без доступа к личным записям пользователей.':session.email);const tabs=el('div',undefined,'tabs');app.append(tabs);action('Выйти',async()=>{await api('logout',{});csrf='';login();},tabs);if(staff){controlNavigation=makeControlNavigation(session,tabs);app.append(controlOverview(session));if(session.permissions.includes('dashboard.read')){const data=await api('dashboard');const grid=el('div',undefined,'grid metrics');for(const [key,value]of Object.entries(data)){if(typeof value==='number'||value===null)grid.append(metricCard(key,value));}app.append(grid);}else notice('Выберите доступный раздел.');}else{action('Поддержка',support,tabs);action('Аккаунт и приватность',accountPrivacy,tabs);const ent=await api('entitlements');const grid=el('div',undefined,'grid');grid.append(panel('Ваш доступ: '+ent.tier,ent.billing_managed_by?'Управляется через '+ent.billing_managed_by:'Платёж не оформлен. Текущий доступ не означает платную подписку.'));grid.append(panel('Данные на устройстве','Личные записи остаются в зашифрованной базе Android. Кабинет не предоставляет к ним доступ.'));app.append(grid);const devices=await api('devices');app.append(el('h2','Устройства'));for(const device of devices.devices){const row=add(el('div',undefined,'row'),el('span',device.label||'Устройство'),el('span',new Date(device.last_seen_at*1000).toLocaleString(),'badge'));if(!device.revoked_at)action('Отозвать доступ',async()=>{heading('Отозвать доступ устройства');form(device.label,[['password','Ваш пароль','password']],'Подтвердить отзыв',async b=>{await api('devices/revoke',{device_id:device.id,password:b.password});await dashboard();});},row);app.append(row);}notice('Покупки пока отключены. Free, Plus и Premium используют единый серверный каталог.');}}
function publicNavigation(path,entry='guest') {
 const header=document.querySelector('body > header');
 const nav=header.querySelector('nav');
 const signIn=nav.querySelector('.public-signin')||nav.querySelector('a[href="/account"]');
 signIn.textContent=entry==='guest'?'Войти':entry==='signed-in'?'Моё пространство':'Открыть ULADIM';
 signIn.href=entry==='guest'?'/account':'/app';
 signIn.classList.add('public-signin');
 const compactEntry=entry==='guest'?'Войти':'Открыть';
 const existingControls=header.querySelector('.public-header-controls');
 if(existingControls){
  const mobileSignIn=existingControls.querySelector('a');
  mobileSignIn.textContent=compactEntry;mobileSignIn.href=signIn.href;
  return;
 }
 const apps=el('a','Приложения');
 apps.href='/download';
 nav.insertBefore(apps,signIn);
 nav.id='public-navigation';
 for(const entry of nav.querySelectorAll('a')) {
  if(entry.pathname===path)entry.setAttribute('aria-current','page');
 }

 const controls=el('div',undefined,'public-header-controls');
 const mobileSignIn=signIn.cloneNode(true);
 mobileSignIn.textContent=compactEntry;
 const toggle=el('button','Меню','public-menu-toggle');
 toggle.type='button';
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
 if(config.entry==='signed-in')return link('Открыть моё пространство','/app');
 if(config.entry==='unavailable')return link('Открыть ULADIM','/app');
 return config.registration_open ? link('Создать аккаунт','/app?action=signup') : link('Открыть ULADIM','/app');
}
async function publicPage(config={}) {
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
  heading('Порядок в ваших делах','Записывайте задачи и идеи, планируйте события и ведите финансы в одном аккаунте. Для общих дел можно создать семейное пространство.');
  const links=el('nav',undefined,'guide-navigation');links.setAttribute('aria-label','Разделы руководства');
  for(const [label,href] of [['Начало работы','#first-record'],['Установка','#installation'],['Импорт данных','#import'],['Вопросы и ответы','/faq']]){
   const jump=el('a',label);jump.href=href;links.append(jump);
  }
  const first=panel('Начните с одной записи','Добавьте задачу, заметку или финансовый счёт в личном пространстве. Если хотите планировать вместе с близкими, создайте семейное пространство и пригласите их.');
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
  heading('Место для ваших планов','Начните бесплатно. Все текущие возможности доступны без подписки и банковской карты.');
  await planComparison(app);
  app.append(startLink(config));
  return;
 }
 const pages={
  '/support':['Поможем разобраться','Войдите в аккаунт, чтобы отправить обращение и прочитать ответ.','Опишите, что вы пытались сделать и на каком шаге возникла проблема. Пароли, коды и банковские выписки для обращения не нужны.'],
  '/delete-account':['Удаление аккаунта','Удаление облачного аккаунта и очистка локальной базы — разные действия. Эта операция не должна удалять данные других участников семьи.','Запрос на удаление доступен в кабинете и имеет 24-часовой срок отмены. Владение семьёй нужно заранее передать с согласием второго родителя. Сроки очистки резервных копий ещё не подтверждены.'],
  '/status':['Состояние сервиса','Если страница не загружается или синхронизация не завершается, повторите действие после восстановления соединения и обратитесь в поддержку. Эта страница не показывает внутренние метрики сервера.','Локальные функции Android работают независимо от облачного аккаунта.']
 };
 const [title,description,details]=pages[path];
 heading(title,description);
 app.append(panel(path==='/support'?'Как описать проблему':'Что важно знать',details));
 if(path==='/support'||path==='/delete-account')app.append(link('Открыть аккаунт','/account'));
}
(async()=>{
 await Promise.resolve();
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
  authPacks=await (await fetch('/assets/locales.json',{cache:'no-store'})).json();
  if(!authPacks[authLanguage])authLanguage='ru';
  if(staff) {
   try{await dashboard();}catch(e){if(e.code==='unauthorized'||e.code==='staff_unauthorized')login();else throw e;}
  }else{
   const config=await api('config');
   googleEnabled=Boolean(config.google_enabled);
   await publicPage(config);
  }
 }catch(e){heading('Не удалось загрузить');notice(e.message);}
 finally{document.body.classList.remove('surface-loading');}
})();

async function registration(){
 const config=await api('config');
 focusAuthHeading(tr('family_register'));
 const fields=[['email',tr('family_email'),'email'],['password',tr('family_password'),'password']];if(!config.registration_open)fields.push(['invitation',tr('family_invitation'),'text']);
 const f=form('',fields,tr('family_register'),async b=>{const email=b.email;try{await api('signup',b);}finally{f.elements.password.value='';b.password='';}heading(tr('family_verify'),tr('family_verify_hint'));
 form('',[['code',tr('family_code'),'text']],tr('family_verify'),async code=>{await api('confirm-signup',{email,code:code.code.trim()});login();notice(tr('account_done'));});action(tr('ux3_resend_verification'),async()=>{await api('resend-signup',{email});notice(tr('family_verify_hint'));});});
 if(config.google_enabled)action(tr('account_google_sign_in'),async()=>{const result=await api('google/start',{invitation:f.elements.invitation?.value});location.assign(result.authorization_url);});
 f.elements.password.autocomplete='new-password';app.append(link(tr('account_privacy'),'/privacy',true));
}

const RECOVERY_COPY = {
 ru: ['Восстановление пароля','Введите почту, которую используете в ULADIM.','Если аккаунт существует, код придёт на эту почту.','Отправить код','Сохранить пароль','Вернуться ко входу'],
 en: ['Reset your password','Enter the email you use for ULADIM.','If an account exists, a code will be sent to this email.','Send code','Save password','Back to sign in'],
 'uz-Latn': ['Parolni tiklash','ULADIM uchun ishlatadigan email manzilingizni kiriting.','Hisob mavjud bo‘lsa, shu manzilga kod yuboriladi.','Kodni yuborish','Parolni saqlash','Kirishga qaytish'],
 'uz-Cyrl': ['Паролни тиклаш','ULADIM учун ишлатадиган email манзилингизни киритинг.','Ҳисоб мавжуд бўлса, шу манзилга код юборилади.','Кодни юбориш','Паролни сақлаш','Киришга қайтиш']
};

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
  f.elements.password.autocomplete='new-password';
  backToLogin();
 }).querySelector('h2').remove();
 backToLogin();
}

async function accountPrivacy(){heading('Аккаунт и приватность');action('Двухфакторная защита',customerMfa);const status=await api('deletion');for(const transfer of status.incoming_transfers||[]){form('Принять владение: '+transfer.name,[['password','Ваш пароль','password']],'Принять владение семьёй',async b=>{await api('accept-transfer',{transfer_id:transfer.id,password:b.password});await accountPrivacy();});}form('Сменить пароль',[['old_password','Текущий пароль','password'],['new_password','Новый пароль: от 7 символов','password']],'Сменить и выйти',async b=>{await api('password',b);login();});form('Сменить почту',[['email','Новый адрес','email'],['password','Текущий пароль','password']],'Отправить код',async b=>{await api('email',b);heading('Подтвердить новую почту');form('Код из письма',[['code','Код','text']],'Подтвердить и выйти',async value=>{await api('confirm-email',{code:value.code,password:b.password});login();});});app.append(el('h2','Удаление облачного аккаунта'));notice('Запрос можно отменить в течение 24 часов. Локальная база Android и общие записи семьи сохраняются. Срок очистки резервных копий требует отдельной проверки оператором.');if(status.ownership_transfer_required.length){notice('Сначала передайте владение семейным пространством другому родителю с его подтверждением.');for(const family of status.ownership_transfer_required){if(family.eligible_parent_id)form('Передать владение: '+family.name,[['password','Ваш пароль','password']],'Запросить согласие другого родителя',async b=>{await api('transfer',{workspace_id:family.id,user_id:family.eligible_parent_id,password:b.password});notice('Запрос создан. Другой родитель может принять его в разделе приватности своего аккаунта.');});}}else if(status.request?.state==='pending'){notice('Запрос ожидает исполнения после '+new Date(status.request.due_at*1000).toLocaleString());form('Отменить запрос',[['password','Текущий пароль','password']],'Отменить удаление',async b=>{await api('cancel-deletion',b);await accountPrivacy();});}else{if(status.request?.state==='attention')notice('Для исполнения нужна отдельная проверка: общие ссылки или права изменились. Данные не удалены.');form('Подтвердить запрос удаления',[['password','Текущий пароль','password'],['confirmation','Введите DELETE для подтверждения','text']],'Запросить удаление',async b=>{await api('deletion',b);await accountPrivacy();});}}
async function staffUsers(){heading('Пользователи','Поиск только по ID или почте. Личные записи не доступны.');form('Поиск',[['search','ID или почта','text']],'Найти',async b=>{const result=await api('users?search='+encodeURIComponent(b.search));const list=el('div',undefined,'grid');for(const user of result.users){const card=panel(user.email,user.verified?'Почта подтверждена':'Почта не подтверждена');action('Открыть аккаунт',()=>staffUser(user.id),card);list.append(card);}app.append(list);});}
function selectField(form,name,label,choices){
  const caption=el('label',label);caption.htmlFor='select-'+name+'-'+crypto.randomUUID();
  const select=el('select');select.name=name;select.id=caption.htmlFor;
  for(const [value,title]of choices){const option=el('option',title);option.value=value;select.append(option);}
  form.insertBefore(caption,form.querySelector('button'));form.insertBefore(select,form.querySelector('button'));
  return select;
}
const sourceName=value=>({manual:'Ручная выдача',promo:'Подарок / тест',google_play:'Google Play',rustore:'RuStore',web:'Веб-провайдер'}[value]||'Бесплатный доступ');
const accessUntil=value=>value?new Date(value*1000).toLocaleString('ru-RU'):'Без ограничения срока';
async function staffUser(id){
  const result=await api('user?id='+encodeURIComponent(id));const session=await api('session');const ent=result.entitlements;
  heading(result.user.email,'Карточка аккаунта без финансов, заметок или семейного содержимого.');
  app.append(panel('Доступ: '+ent.tier,sourceName(ent.source)+' · '+accessUntil(ent.valid_until)));
  app.append(el('p',result.user.verified?'Почта подтверждена':'Почта не подтверждена'));
  if(session.permissions.includes('users.recover')&&result.user.verified&&id!==session.user_id&&(!result.user.disabled_until||result.user.disabled_until<=Math.floor(Date.now()/1000)))action('Отправить письмо восстановления',()=>staffRecovery(id,result.user.email));
  for(const device of result.devices)app.append(panel(device.label,new Date(device.last_seen_at*1000).toLocaleString('ru-RU')));
  const canGrant=session.permissions.includes('plans.grant');
  app.append(el('h2','История выдачи доступа'));
  if(!ent.grants.length)app.append(el('p','Ручных выдач пока нет.'));
  for(const grant of ent.grants){
    const expired=grant.valid_until!==null&&grant.valid_until<=Math.floor(Date.now()/1000);
    const state=grant.revoked_at?'Отозван':expired?'Срок завершён':'Действует';
    const card=panel(grant.tier+' · '+state,sourceName(grant.source)+' · '+accessUntil(grant.valid_until));
    card.append(el('p',grant.reason));app.append(card);
    if(canGrant&&!grant.revoked_at&&!expired)action('Отозвать выдачу',async()=>{
      heading('Отозвать ручную выдачу',grant.tier+' · '+sourceName(grant.source));
      notice('Отзывается только эта выдача. Другие действующие основания сохранятся. Списание или отмена магазинной подписки не выполняются.');
      form('Подтверждение отзыва',[['reason','Причина отзыва','text']],'Подтвердить отзыв выдачи',async b=>{
        await api('revoke-grant',{grant_id:grant.id,reason:b.reason});await staffUser(id);
      });
      action('Отменить',async()=>staffUser(id));
    },card);
  }
  if(canGrant){
    const f=form('Выдать тестовый доступ',[['reason','Причина выдачи','text']],'Выдать доступ',async b=>{
      const days=f.elements.duration.value;
      await api('grant',{user_id:id,tier:f.elements.tier.value,source:f.elements.source.value,
        valid_until:days==='unlimited'?null:Math.floor(Date.now()/1000)+Number(days)*86400,reason:b.reason});
      await staffUser(id);
    });
    selectField(f,'tier','Уровень',[['Plus','Plus']]);
    f.append(el('p','Premium и ИИ пока недоступны. Текущие рабочие возможности открыты бесплатно.','small'));
    selectField(f,'source','Основание',[['manual','Ручная выдача'],['promo','Подарок / тест']]);
    selectField(f,'duration','Срок доступа',[['30','30 дней'],['90','90 дней'],['365','1 год'],['unlimited','Без ограничения срока']]);
    notice('Это ручная выдача доступа. Платёж и магазинная подписка не создаются.');
  }
  if(session.permissions.includes('users.moderate')){
    const services=[['account','Весь аккаунт'],['family_write','Изменения в семье'],['premium','Премиальные сервисы'],['support_write','Новые сообщения поддержки']];
    const holds={...ent.holds};if(result.user.disabled_until>Math.floor(Date.now()/1000))holds.account=result.user.disabled_until;
    app.append(el('h2','Ограничения и модерация'),el('p','Ограничения временные и не удаляют записи. Каждое действие сохраняется в журнале с причиной.','small'));
    if(!Object.keys(holds).length)app.append(el('p','Активных ограничений нет.','control-no-holds'));
    for(const [service,until]of Object.entries(holds)){
      const name=services.find(row=>row[0]===service)?.[1]||service;
      const card=panel('Ограничение: '+name,'До '+accessUntil(until));app.append(card);
      action('Снять ограничение',async()=>{
        heading('Снять ограничение: '+name,'Снятие не удалит историю и другие ограничения.');
        form('Подтверждение',[['reason','Причина снятия','text']],'Подтвердить снятие',async b=>{
          await api('moderate',{user_id:id,service,until_at:0,reason:b.reason});await staffUser(id);
        });action('Отменить',async()=>staffUser(id));
      },card);
    }
    const f=form('Временное ограничение',[['reason','Обязательная причина','text']],'Применить ограничение',async b=>{
      await api('moderate',{user_id:id,service:f.elements.service.value,until_at:Math.floor(Date.now()/1000)+Number(f.elements.duration.value),reason:b.reason});await staffUser(id);
    });f.classList.add('control-moderation');f.elements.reason.maxLength=500;
    const service=selectField(f,'service','Ограничиваемый сервис',services);service.value='family_write';
    selectField(f,'duration','Срок ограничения',[['86400','24 часа'],['604800','7 дней'],['2592000','30 дней']]);
    const warning=el('p','Блокировка всего аккаунта завершит его активные сеансы. Данные сохранятся.','notice');warning.hidden=true;f.insertBefore(warning,f.querySelector('button'));service.addEventListener('change',()=>{warning.hidden=service.value!=='account';});
  }
}

async function staffTeam(){const result=await api('staff');const session=await api('session');heading('Команда Control','Права ограничены ролью и проверяются сервером при каждом действии. Для каждого сотрудника обязателен MFA.');for(const member of result.staff){const card=panel(member.email,member.roles.join(' · '));card.append(el('span',member.active?'Доступ активен':'Доступ отозван','badge'));app.append(card);if(!member.roles.includes('owner')&&member.id!==session.staff_id)action('Изменить права',async()=>{heading(member.email);const f=form('Права сотрудника',[['reason','Обязательная причина','text']],'Сохранить и отозвать сессии',async b=>{await api('staff/update',{staff_id:member.id,roles:[f.elements.role.value],active:f.elements.active.checked,revision:member.revision,reason:b.reason});await staffTeam();});roleSelect(f,session.roles.includes('owner'));const l=el('label','Доступ активен');const checkbox=el('input');checkbox.type='checkbox';checkbox.name='active';checkbox.checked=!!member.active;l.append(checkbox);f.insertBefore(l,f.querySelector('button'));},card);}const f=form('Пригласить сотрудника',[['email','Почта получателя','email'],['reason','Причина приглашения','text']],'Создать приглашение',async b=>{const result=await api('staff/invite',{email:b.email,roles:[f.elements.role.value],reason:b.reason});heading('Приглашение создано','Передайте код только выбранному получателю по защищённому каналу. Он должен войти в свой подтверждённый аккаунт и настроить MFA. Срок — 24 часа.');const code=el('textarea');code.readOnly=true;code.value=result.invitation;code.setAttribute('aria-label','Одноразовое приглашение');app.append(code);});roleSelect(f,session.roles.includes('owner'));}
function roleSelect(form,owner){const label=el('label','Роль');label.htmlFor='role-select';const select=el('select');select.name='role';select.id='role-select';const roles={support:'Поддержка',moderator:'Модератор',billing_manager:'Управление доступом',auditor:'Аудитор',admin:'Администратор'};for(const [value,title]of Object.entries(roles)){if(value==='admin'&&!owner)continue;const option=el('option',title);option.value=value;select.append(option);}form.insertBefore(label,form.querySelector('button'));form.insertBefore(select,form.querySelector('button'));}

const ANNOUNCEMENT_FORMATS=[['inbox','В центре уведомлений','Сообщение в истории. Без показа при входе.'],['banner','Баннер при входе','Компактное сообщение над обзором.'],['fullscreen','Полный экран при входе','Отдельное сообщение с кнопкой продолжения.']];
function announcementPreview(item){
 const area=el('section',undefined,'control-announcement-preview');area.dataset.format=item.presentation||'inbox';area.setAttribute('aria-label','Предварительный просмотр');
 const frame=el('div',undefined,'control-preview-frame'),sample=el('div',undefined,'control-preview-message');
 add(sample,el('p','ULADIM','eyebrow'),el('h3',item.title||'Заголовок сообщения'),el('p',item.body||'Текст сообщения появится здесь.','control-preview-body'));
 if(item.link)add(sample,el('span','Открыть','control-preview-button'));
 if(item.presentation==='fullscreen')add(sample,el('span','Продолжить','control-preview-button'));
 if(item.presentation==='banner')sample.append(el('span','×','control-preview-close'));
 if(item.presentation==='inbox')frame.append(el('p','Уведомления','control-preview-caption'));
 else frame.append(el('p','Сегодня','control-preview-caption'));
 frame.append(sample);area.append(frame);return area;
}
function announcementDate(value){return value?new Date(value*1000).toLocaleString('ru-RU'):'Сразу после публикации';}
async function staffAnnouncements(){
 const result=await api('announcements');heading('Уведомления','Сообщения в приложении: история, баннер или полный экран при входе.');
 const tools=el('div',undefined,'actions');action('Новое сообщение',announcementCompose,tools);app.append(tools);
 if(!result.announcements.length){notice('Сообщений пока нет. Начните с проверки только для своего аккаунта.');return;}
 const states={draft:'Черновик',published:'Опубликовано',cancelled:'Отменено'},list=el('div',undefined,'control-announcement-list');app.append(list);
 for(const item of result.announcements){const row=el('section',undefined,'card control-announcement-row');add(row,el('p',(states[item.state]||item.state)+' · '+(ANNOUNCEMENT_FORMATS.find(format=>format[0]===item.presentation)?.[1]||'В центре уведомлений'),'small'),el('h2',item.title),el('p',item.body,'control-preview-body'),el('p',(item.audience==='all'?'Все подтверждённые аккаунты':'Выбранные аккаунты')+' · получателей: '+item.recipient_count+' · '+announcementDate(item.starts_at),'small'));const controls=el('div',undefined,'actions');if(item.state==='draft')action('Проверить публикацию',()=>announcementReview(item),controls);if(item.state==='published')action('Остановить показ',()=>announcementCancel(item),controls);row.append(controls);list.append(row);}
}
async function announcementCompose(){
 const session=await api('session');heading('Новое сообщение','Сначала сохраните черновик и проверьте получателей. По умолчанию сообщение увидите только вы.');
 const layout=el('div',undefined,'control-announcement-layout'),f=el('form',undefined,'panel control-announcement-form'),preview=el('aside',undefined,'control-announcement-preview-host');add(app,layout);add(layout,f,preview);
 const addField=(name,label,type='text',required=true)=>{const wrap=el('div',undefined,'control-announcement-field'),l=el('label',label),n=el(type==='textarea'?'textarea':'input');n.id='announcement-'+name;l.htmlFor=n.id;n.name=name;if(type!=='textarea')n.type=type;n.required=required;add(wrap,l,n);f.append(wrap);return n;};
 const title=addField('title','Заголовок');title.maxLength=160;
 const body=addField('body','Текст сообщения','textarea');body.maxLength=4000;body.rows=7;
 const format=el('fieldset',undefined,'control-announcement-choice');format.append(el('legend','Где показать'));f.append(format);
 for(const [value,label,hint]of ANNOUNCEMENT_FORMATS){const option=el('label'),radio=el('input');radio.type='radio';radio.name='presentation';radio.value=value;radio.setAttribute('aria-label',label);radio.checked=value==='inbox';add(option,radio,add(el('span'),el('strong',label),el('small',hint)));format.append(option);}
 const audience=el('fieldset',undefined,'control-announcement-choice');audience.append(el('legend','Получатели'));f.append(audience);
 for(const [value,label,hint]of [['self','Только мне — проверка','Один ваш аккаунт. Другие пользователи не получат сообщение.'],['users','Выбранные аккаунты','До 100 проверенных идентификаторов аккаунтов.'],['all','Все подтверждённые аккаунты','Публикация для всех потребует отдельного подтверждения.']]){const option=el('label'),radio=el('input');radio.type='radio';radio.name='audience';radio.value=value;radio.setAttribute('aria-label',label);radio.checked=value==='self';add(option,radio,add(el('span'),el('strong',label),el('small',hint)));audience.append(option);}
 const recipients=addField('user_ids','ID аккаунтов — по одному на строку','textarea',false);recipients.rows=3;recipients.parentElement.hidden=true;
 const link=addField('link','Ссылка в ULADIM — необязательно','text',false);link.placeholder='/app';link.maxLength=512;
 const timing=el('details',undefined,'control-announcement-timing');timing.append(el('summary','Время показа и срок'));f.append(timing);
 const starts=addField('starts_at','Начало показа — необязательно','datetime-local',false),expires=addField('expires_at','Завершение показа — необязательно','datetime-local',false);timing.append(starts.parentElement,expires.parentElement);timing.append(el('p','Без даты сообщение доступно сразу на 30 дней. Запланировать можно на 30 дней вперёд, срок показа — до 90 дней.','small'));
 const reason=addField('reason','Причина для журнала аудита');reason.maxLength=500;
 const feedback=el('p','','control-announcement-feedback');feedback.setAttribute('role','status');const submit=el('button','Сохранить черновик');submit.type='submit';add(f,feedback,submit);
 const draft=()=>({title:title.value.trim(),body:body.value.trim(),presentation:f.elements.presentation.value,audience:f.elements.audience.value==='all'?'all':'users',user_ids:f.elements.audience.value==='self'?[session.user_id]:f.elements.audience.value==='users'?[...new Set(recipients.value.split(/[\s,;]+/).filter(Boolean))]:[],link:link.value.trim(),...(starts.value?{starts_at:Math.floor(new Date(starts.value).getTime()/1000)}:{}),...(expires.value?{expires_at:Math.floor(new Date(expires.value).getTime()/1000)}:{}),reason:reason.value.trim()});
 const draw=()=>{recipients.parentElement.hidden=f.elements.audience.value!=='users';recipients.required=f.elements.audience.value==='users';preview.replaceChildren(el('h2','Предпросмотр'),announcementPreview(draft()),el('p','Показ при входе не прерывает ввод и открытые формы. После закрытия сообщение остаётся в истории.','small'));};
 f.addEventListener('input',draw);f.addEventListener('change',draw);draw();
 f.addEventListener('submit',async event=>{event.preventDefault();if(!f.reportValidity())return;submit.disabled=true;feedback.textContent='Проверяем сообщение…';try{const payload=draft();if(payload.user_ids.some(id=>!id))throw new Error('Не удалось определить ваш аккаунт. Обновите страницу.');if(payload.link&&!/^\/app(?:[/?#]|$)/.test(payload.link))throw new Error('Укажите внутреннюю ссылку, начинающуюся с /app.');await api('announcements/preview',payload);const saved=await api('announcements',payload);await announcementReview({...saved,reason:payload.reason});}catch(error){feedback.className='error control-announcement-feedback';feedback.textContent=error.message;}finally{submit.disabled=false;}});
 const cancel=el('button','Назад к черновикам','secondary');cancel.type='button';cancel.addEventListener('click',()=>staffAnnouncements().catch(error=>{feedback.textContent=error.message;}));f.append(cancel);title.focus({preventScroll:true});
}
async function announcementReview(item){
 heading('Проверьте публикацию','Черновик сохранён. Сообщение ещё не отправлено.');
 const layout=el('div',undefined,'control-announcement-layout'),summary=el('section',undefined,'card control-publish-summary');add(app,layout);add(layout,summary,announcementPreview(item));
 add(summary,el('h2',item.title),el('p',item.body,'control-preview-body'));
 const rows=[['Получатели',item.audience==='all'?'Все подтверждённые аккаунты':'Только выбранные аккаунты'],['Количество получателей',String(item.recipient_count)],['Формат',ANNOUNCEMENT_FORMATS.find(format=>format[0]===item.presentation)?.[1]||item.presentation],['Начало показа',announcementDate(item.starts_at)],['Завершение показа',announcementDate(item.expires_at)],['Ссылка',item.link||'Без ссылки']];
 if(item.audience!=='all')rows.splice(2,0,['ID аккаунтов',(item.user_ids||[]).join('\n')]);
 const details=el('dl');for(const [label,value]of rows)add(details,el('dt',label),el('dd',value));summary.append(details);
 const f=el('form',undefined,'control-publish-form');summary.append(f);const reason=field(f,'reason','Причина для журнала аудита');reason.value=item.reason||'';reason.maxLength=500;
 let confirmation=null;if(item.audience==='all'){const phrase='ВСЕМ '+item.recipient_count;f.append(el('p','Это сообщение увидят все подтверждённые аккаунты ('+item.recipient_count+'). Проверьте текст, формат и время.','notice'));confirmation=field(f,'confirmation','Введите '+phrase);confirmation.autocomplete='off';confirmation.addEventListener('input',()=>{publish.disabled=confirmation.value!==phrase;});}
 const feedback=el('p');feedback.setAttribute('role','status');const publish=el('button','Опубликовать');publish.type='submit';publish.disabled=Boolean(confirmation);add(f,feedback,publish);
 const back=el('button','Назад к черновикам','secondary');back.type='button';back.addEventListener('click',()=>staffAnnouncements().catch(error=>{feedback.textContent=error.message;}));f.append(back);
 f.addEventListener('submit',async event=>{event.preventDefault();if(!f.reportValidity()||confirmation&&confirmation.value!=='ВСЕМ '+item.recipient_count)return;publish.disabled=true;try{const current=await api('announcements/preview',{title:item.title,body:item.body,presentation:item.presentation,audience:item.audience,user_ids:item.user_ids||[],starts_at:item.starts_at,expires_at:item.expires_at,link:item.link,reason:reason.value.trim()});if(current.recipient_count!==item.recipient_count){await announcementReview({...item,recipient_count:current.recipient_count,reason:reason.value.trim()});notice('Количество получателей изменилось. Проверьте и подтвердите обновлённую аудиторию.');return;}const result=await api('announcements/publish',{id:item.id,revision:item.revision,reason:reason.value.trim()});heading('Опубликовано','Сообщение будет доступно выбранным получателям в указанное время.');app.append(panel(result.title,'Получателей: '+result.recipient_count));action('К уведомлениям',staffAnnouncements);}catch(error){feedback.className='error';feedback.textContent=error.message;}finally{publish.disabled=Boolean(confirmation&&confirmation.value!=='ВСЕМ '+item.recipient_count);}});
}
function announcementCancel(item){heading('Остановить показ?',item.title);form('Сообщение останется в истории получателей.',[['reason','Причина для журнала аудита','text']],'Подтвердить остановку',async body=>{await api('announcements/cancel',{id:item.id,revision:item.revision,reason:body.reason});await staffAnnouncements();});action('Назад к черновикам',staffAnnouncements);}


async function staffRecordRecovery(before=''){
 const result=await api('record-recovery'+(before?'?before='+encodeURIComponent(before):''));if(!Array.isArray(result.requests))throw new Error('Не удалось загрузить запросы.');
 heading('Запросы восстановления','Содержимое удалённых записей скрыто. Одобрение разрешает владельцу выполнить восстановление самостоятельно.');
 const status=el('p','','control-recovery-status');status.setAttribute('role','status');app.append(status);const filters=el('div',undefined,'actions control-recovery-filters'),list=el('div',undefined,'control-recovery-list');let filter='pending';
 const states={pending:'Ожидает проверки',approved:'Одобрен',rejected:'Отклонён',cancelled:'Отозван',completed:'Восстановлен'},kinds={note:'Заметка',task:'Задача',event:'Событие',account:'Счёт',transaction:'Операция',budget:'Бюджет',transfer:'Перевод',shopping:'Список покупок',request:'Денежный запрос'};
 const pendingButton=el('button','Ожидают','secondary'),allButton=el('button','Все запросы','secondary');for(const b of [pendingButton,allButton])b.type='button';add(filters,pendingButton,allButton);add(app,filters,list);
 function draw(){list.replaceChildren();pendingButton.setAttribute('aria-pressed',String(filter==='pending'));allButton.setAttribute('aria-pressed',String(filter==='all'));const visible=result.requests.filter(item=>filter==='all'||item.state==='pending');if(!visible.length)list.append(el('p',result.next_before?'В этой части списка нет ожидающих запросов.':'Запросов по этим условиям пока нет.','notice'));
  for(const item of visible){const card=el('section',undefined,'card control-recovery-card'),expired=item.expires_at*1000<=Date.now();add(card,el('p',(states[item.state]||'Запрос')+(expired&&item.state!=='completed'?' · срок завершён':''),'small'),el('h2',kinds[item.kind]||'Запись'));
   const metadata=el('dl');for(const [label,value]of [['ID запроса',item.id],['ID аккаунта',item.user_id],['ID пространства',item.workspace_id],['ID записи',item.record_id],['Создан',announcementDate(item.created_at)],['Действует до',announcementDate(item.expires_at)]])add(metadata,el('dt',label),el('dd',String(value)));card.append(metadata);
   if(item.state==='pending'&&!expired){const open=el('button','Рассмотреть запрос','secondary');open.type='button';open.addEventListener('click',()=>{open.hidden=true;const f=el('form',undefined,'control-recovery-review');f.append(el('p','Согласие относится к выбранной версии записи. Сотрудник не получает содержимое и не восстанавливает запись от имени владельца.','small'));const reason=field(f,'reason','Причина для журнала аудита');reason.maxLength=500;const feedback=el('p');feedback.setAttribute('role','status');const submit=el('button','Одобрить запрос');submit.type='submit';add(f,feedback,submit);card.append(f);reason.focus({preventScroll:true});f.addEventListener('submit',async event=>{event.preventDefault();if(!f.reportValidity())return;submit.disabled=true;try{const approved=await api('record-recovery/approve',{request_id:item.id,revision:item.revision,consent_hash:item.consent_hash,reason:reason.value.trim()});Object.assign(item,approved.request);status.textContent='Запрос одобрен. Восстановление выполнит владелец аккаунта.';draw();}catch(error){feedback.className='error';feedback.textContent=error.message;}finally{submit.disabled=false;}});});card.append(open);}
   list.append(card);
  }
 }
 pendingButton.addEventListener('click',()=>{filter='pending';draw();});allButton.addEventListener('click',()=>{filter='all';draw();});draw();if(result.next_before)action('Следующая страница',()=>staffRecordRecovery(result.next_before));
}

async function staffFlags(){const flags=await api('flags');heading('Настройки интерфейса','Только предусмотренные UI-флаги. Защиту, MFA и проверку TLS здесь отключить нельзя.');for(const [name,value]of Object.entries(flags))app.append(panel(name,(value.enabled?'Включён':'Выключен')+' · охват '+value.rollout+'% · версия '+value.revision));const f=form('Предварительный просмотр',[['rollout','Охват: 0–100%','number'],['reason','Причина изменения','text']],'Показать изменения',async b=>{const name=f.elements.flag.value;const prior=flags[name]||{enabled:false,rollout:0,revision:0};const proposal=await api('flags/preview',{name,enabled:f.elements.enabled.checked,rollout:Number(b.rollout),revision:prior.revision,reason:b.reason});heading('Проверьте изменение');app.append(panel(name,'Было: '+(prior.enabled?'включён':'выключен')+', '+prior.rollout+'%. Будет: '+(proposal.preview.enabled?'включён':'выключен')+', '+proposal.preview.rollout+'%.'));notice('Изменение затронет соответствующий процент аккаунтов. Предложение действует 10 минут.');action('Подтвердить применение',async()=>{await api('flags/commit',{proposal_id:proposal.proposal_id,digest:proposal.digest});await staffFlags();});action('Отменить',staffFlags);});const select=el('select');select.name='flag';select.setAttribute('aria-label','Настройка');for(const [name,title]of [['compact_onboarding','Компактное знакомство'],['chart_styles','Варианты диаграмм'],['support_entry','Вход в поддержку']]){const option=el('option',title);option.value=name;select.append(option);}f.prepend(select);const label=el('label','Включить');const enabled=el('input');enabled.name='enabled';enabled.type='checkbox';label.append(enabled);f.insertBefore(label,f.querySelector('button'));f.elements.rollout.min='0';f.elements.rollout.max='100';f.elements.rollout.value='0';}

async function customerMfa(){const status=await api('mfa');heading('Двухфакторная защита',status.enabled?'Включена. Для отключения нужны пароль и второй фактор.':'Добавьте второй фактор к паролю аккаунта. Восстановление почты не отключает эту защиту.');if(status.enabled){form('Отключить защиту',[['password','Текущий пароль','password'],['code','Код аутентификатора или восстановления','text']],'Отключить и выйти',async b=>{await api('mfa/disable',b);login();});}else{form('Подключить аутентификатор',[['password','Текущий пароль','password']],'Продолжить',async b=>{const enrollment=await api('mfa/begin',b);heading('Добавьте ключ в аутентификатор','Сохраните ключ в своём приложении-аутентификаторе. Не передавайте его поддержке.');const secret=el('textarea');secret.readOnly=true;secret.value=enrollment.totp_secret;secret.setAttribute('aria-label','Секрет настройки MFA');app.append(secret);form('Подтвердить второй фактор',[['code','Текущий шестизначный код','text']],'Включить защиту',async value=>{const result=await api('mfa/enable',{password:b.password,enrollment:enrollment.enrollment,code:value.code});heading('Сохраните коды восстановления','Каждый код действует один раз вместе с паролем. Храните их офлайн. Все прежние сессии отозваны. После сохранения войдите с новым кодом аутентификатора.');const codes=el('textarea');codes.readOnly=true;codes.value=result.recovery_codes.join('\n');codes.setAttribute('aria-label','Одноразовые коды восстановления');app.append(codes);action('Коды сохранены. Вернуться ко входу',async()=>login());});});}}

function metricCard(key,value){const labels={accounts:'Аккаунты',users:'Аккаунты',new_24h:'Новые за сутки',active_24h:'Активные за сутки',mail_pending:'Очередь писем',support_pending:'Обращения',load_1m:'Нагрузка CPU',disk_free_bytes:'Свободное место',api_latency_ms:'Задержка API',sync_errors:'Ошибки синхронизации',backup_last_success:'Резервная копия'};let text='Нет измерений';if(value!==null){if(key==='disk_free_bytes')text=(value/1073741824).toLocaleString('ru-RU',{maximumFractionDigits:1})+' ГБ';else if(key==='backup_last_success')text=new Date(value*1000).toLocaleString();else text=value.toLocaleString('ru-RU',{maximumFractionDigits:key==='load_1m'?2:0})+(key==='api_latency_ms'?' мс':'');}return add(el('section',undefined,'card metric-card'),el('h2',labels[key]||key),el('div',text,value===null?'metric-unavailable':'metric-value'));}
function controlOverview(session){
 const section=el('section',undefined,'control-overview-links');section.setAttribute('aria-label','Разделы Control');
 for(const [permission,title,description,path]of [['users.read','Пользователи','Аккаунты, устройства, доступ и ограничения.','users'],['applications.manage','Заявки на тест','Приглашения и решения по заявкам.','applications'],['staff.manage','Команда','Роли сотрудников и защищённые приглашения.','staff'],['support.read','Поддержка','Обращения пользователей и ответы команды.','support'],['announcements.manage','Уведомления','Черновики сообщений, аудитория и время показа.','announcements'],['records.recover','Восстановление записей','Запросы владельцев без доступа к содержимому.','record-recovery'],['audit.read','Аудит','Журнал действий с причинами и изменениями.','audit'],['flags.manage','Настройки интерфейса','Разрешённые настройки и предварительная проверка.','flags']]){
  if(!session.permissions.includes(permission))continue;const card=el('button',undefined,'secondary control-overview-link');card.type='button';add(card,el('strong',title),el('span',description));card.addEventListener('click',()=>{const select=controlNavigation?.querySelector('select');if(select){select.value=path;select.dispatchEvent(new Event('change'));}});section.append(card);
 }
 return section;
}
function staffRecovery(id,email){
 heading('Отправить письмо восстановления',email);notice('Письмо придёт владельцу аккаунта. Пароль и коды остаются недоступны сотруднику; защита MFA сохраняется.');
 const f=form('Подтверждение запроса',[['reason','Причина для журнала аудита','text']],'Отправить письмо',async body=>{await api('user/recovery',{user_id:id,reason:body.reason});heading('Письмо восстановления запрошено','Запрос поставлен в очередь. Дальнейшие действия выполняет владелец аккаунта.');action('К аккаунту',()=>staffUser(id));});f.elements.reason.maxLength=500;action('Отменить',()=>staffUser(id));
}

function makeControlNavigation(session,container){container.replaceChildren();const select=el('select');select.setAttribute('aria-label','Раздел Control');const routes=[['dashboard.read','Обзор','dashboard'],['users.read','Пользователи','users'],['applications.manage','Заявки на тест','applications'],['staff.manage','Команда','staff'],['support.read','Поддержка','support'],['audit.read','Аудит','audit'],['flags.manage','Настройки интерфейса','flags'],['announcements.manage','Уведомления','announcements'],['records.recover','Восстановление записей','record-recovery']];for(const [permission,title,path]of routes)if(session.permissions.includes(permission)){const option=el('option',title);option.value=path;select.append(option);}if(!session.permissions.includes('dashboard.read')){const choose=el('option','Выберите раздел');choose.value='';choose.disabled=true;choose.selected=true;select.prepend(choose);}container.append(select);select.addEventListener('change',async()=>{try{const path=select.value;if(path==='dashboard'){await dashboard();return;}if(path==='users'){await staffUsers();return;}if(path==='applications'){await staffApplications();return;}if(path==='staff'){await staffTeam();return;}if(path==='support'){await support();return;}if(path==='flags'){await staffFlags();return;}if(path==='announcements'){await staffAnnouncements();return;}if(path==='record-recovery'){await staffRecordRecovery();return;}heading('Журнал аудита');const result=await api('audit');for(const event of result.events){const card=panel(event.action,new Date(event.created_at*1000).toLocaleString());card.append(el('p',event.reason));const details=el('details');details.append(el('summary','Изменения'));details.append(el('pre',JSON.stringify({before:JSON.parse(event.before_value),after:JSON.parse(event.after_value)},null,2)));card.append(details);app.append(card);}}catch(e){notice(e.message);}});action('Выйти',async()=>{await api('logout',{});csrf='';login();},container);return container;}


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
 preview.setAttribute('aria-label', 'Пример интерфейса ULADIM');
 const rail = el('div', undefined, 'preview-rail');
 rail.setAttribute('aria-hidden', 'true');
 rail.append(el('strong', 'ULADIM'));
 const views = [
  ['today', 'Сегодня'], ['tasks', 'Задачи'], ['calendar', 'Календарь'],
  ['notes', 'Заметки'], ['money', 'Финансы'], ['account', 'Семья']
 ];
 for (const [icon, label] of views) {
  rail.append(add(el('div', undefined, 'preview-view'), homeIcon(icon), el('span', label)));
 }

 const desk = el('div', undefined, 'preview-workspace');
 const top = add(el('div', undefined, 'preview-top'),
  add(el('div'), el('h2', 'Сегодня'), el('p', 'Четверг, 12 ноября')),
  el('span', 'Пример интерфейса', 'preview-label'));

 const tasks = el('div', undefined, 'preview-tasks');
 const progress = el('span', '2 из 3');
 progress.setAttribute('aria-label', 'Выполнено 2 из 3 задач');
 tasks.append(add(el('div', undefined, 'preview-task-heading'), el('h3', 'Задачи на сегодня'), progress));
 const list = el('ul', undefined, 'preview-task-list');
 for (const [done, label] of [[true, 'Ответить на письма'], [true, 'Оплатить интернет'], [false, 'Подготовить план на неделю']]) {
  const row = el('li', undefined, 'preview-task');
  const mark = el('span', undefined, 'preview-check' + (done ? ' checked' : ''));
  mark.setAttribute('role', 'img');
  mark.setAttribute('aria-label', done ? 'Выполнено' : 'Открыто');
  list.append(add(row, mark, el(done ? 's' : 'span', label)));
 }
 tasks.append(list);

 const time = el('time', '18:30');
 time.dateTime = '18:30';
 const event = add(el('div', undefined, 'preview-event'), homeIcon('calendar'), time, el('strong', 'Встреча с семьёй'));
 const finance = add(el('div', undefined, 'preview-finance'), el('h3', 'Финансы за ноябрь'));
 const totals = el('dl', undefined, 'preview-totals');
 for (const [label, amount] of [['Доход', '150 000 ₽'], ['Расход', '3 520 ₽']]) {
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
 const title=add(el('h1'),el('span','Важное —'),' ',el('span','в одном месте.'));
 add(copy,el('p','ULADIM · Личное и семейное пространство','hero-eyebrow'),title,
  el('p','Задачи, заметки, календарь и финансы. Соберите повседневные дела в одном спокойном пространстве.','hero-description'));
 const actions=el('div',undefined,'hero-actions');
 actions.append(startLink(config));copy.append(actions);
 copy.append(el('p',config.entry==='signed-in'?'Ваш аккаунт уже открыт в этом браузере.':'Сейчас все возможности доступны бесплатно.','hero-caption'));
 app.append(add(hero,copy,todayPreview()));

 const overview=el('section',undefined,'welcome-overview');
 overview.setAttribute('aria-label','Возможности ULADIM');
 for(const [symbol,title,description]of [
  ['calendar','Планируйте день','Задачи, заметки и события рядом.'],
  ['money','Ведите финансы','Счета, операции и бюджеты без суеты.'],
  ['account','Делайте вместе','Личное пространство и общие семейные дела.']
 ]){
  const item=el('div',undefined,'welcome-capability');
  add(item,homeIcon(symbol),add(el('div'),el('h2',title),el('p',description)));
  overview.append(item);
 }
 app.append(overview);
 const learn=el('nav',undefined,'welcome-resources');learn.setAttribute('aria-label','Узнать больше');
 for(const [label,path]of [['Возможности','/docs'],['Как установить','/download'],['Тарифы','/plans'],['Вопросы и ответы','/faq'],['Поддержка','/support']]){
  const entry=el('a',label);entry.href=path;learn.append(entry);
 }
 app.append(learn);
}
function applicationCards(full) {
 const grid=el('div',undefined,'application-grid');
 const web=panel('Телефон, планшет и компьютер','ULADIM работает в браузере на iPhone, iPad, Android, Windows, macOS и Linux. На телефоне или планшете его можно добавить на домашний экран.');
 add(web,link('Открыть веб-приложение','/app'),link('Как установить',full?'#installation':'/download#installation',true));
 const android=panel('Приложение для Android','Отдельный Android-клиент. Опубликованные сборки и сведения о версиях доступны в GitHub Releases.');
 android.append(link('Сборки Android','https://github.com/pro100umarchikgamer-lgtm/lifeos/releases',true));
 if(!full)android.append(link('Об Android-приложении','/download#android',true));
 android.id='android';
 return add(grid,web,android);
}
function applicationPage() {
 heading('Приложения ULADIM','Работайте в браузере или добавьте ULADIM на домашний экран.');
 app.append(applicationCards(true));
 installGuide(app);
 const target=document.getElementById(location.hash.slice(1));
 if(target)requestAnimationFrame(()=>target.scrollIntoView());
}
async function planComparison(target){
 const data=await api('plans');const section=el('section',undefined,'plan-comparison help-plans');
 add(section,el('h2','Планируйте в своём ритме'),el('p','Все текущие возможности доступны бесплатно.','access-free-note'),el('p','Задачи, заметки, календарь, финансы, импорт и семейное пространство. Начните без карты и обязательств.'));
 const grid=el('div',undefined,'access-plan-grid');
 for(const [tier,label,title,text,items]of [
  ['Free','Можно начать сейчас','Важное под рукой','Всё, что уже работает в ULADIM, доступно бесплатно.',['Задачи, заметки и календарь','Финансовый учёт и бюджеты','Импорт записей и выписок','Личное и семейное пространство']],
  ['Plus','Бесплатный доступ к текущим функциям','Больше места для вашего ритма','Будущий вариант доступа. Окончательные условия ещё готовятся.',['Текущие функции остаются доступны бесплатно','Дополнительные возможности — после анонса','Без оформления подписки сегодня']],
  ['Premium','Появится позже','Помощь с искусственным интеллектом','Будущий уровень с ИИ. Сейчас эти возможности недоступны.',['ИИ-функции пока недоступны','Срок запуска и цена не объявлены','Подключить этот уровень пока нельзя']]
 ]){
  if(!data.tiers[tier])continue;
  const card=el('article',undefined,'card access-plan-card');card.dataset.tier=tier;
  if(tier==='Premium')card.setAttribute('aria-label','Premium: недоступен, появится позже');
  add(card,el('p',label,'access-plan-label'),el('h3',tier),el('strong',title),el('p',text));const list=el('ul');for(const item of items)list.append(el('li',item));card.append(list);
  if(tier==='Free')card.append(link('Начать бесплатно','/app'));
  else card.append(el('span',tier==='Plus'?'Продажи ещё не открыты':'Сейчас недоступен','help-plan-state'));
  grid.append(card);
 }
 section.append(grid);
 const note=el('aside',undefined,'help-callout');note.append(el('strong','Сначала понятные условия — затем ваш выбор'),el('p','Если платные возможности появятся, заранее укажем цену, состав, продление, отмену и возвраты. Сегодня покупки и автоматические списания отключены.'));section.append(note);
 const details=el('details',undefined,'access-plan-details');details.append(el('summary','Что доступно сейчас'));
 const labels={personal_core:'Задачи, заметки, календарь и финансы',family_sync:'Семейное пространство',custom_charts:'Настройка диаграмм',extended_personalization:'Темы и палитры',statement_import:'Импорт выписок',advanced_planning:'Расширенное планирование'};
 const features=el('ul');for(const [key,label]of Object.entries(labels))if(data.tiers.Free?.features.includes(key))features.append(el('li',label+' — бесплатно'));details.append(features);section.append(details);target.append(section);
 const help=el('p');help.append(el('span','Есть вопросы? '));const faq=el('a','Ответы о доступе и оплате');faq.href='/faq#plans';help.append(faq);target.append(help);
}
function installGuide(target){
 const section=el('section',undefined,'install-guide');
 section.id='installation';
 add(section,el('h2','Установка на домашний экран'),el('p','Откройте веб-приложение и выберите инструкцию для своего устройства.'));
 for(const [title,body]of [['iPhone и iPad','Откройте /app в Safari. Нажмите «Поделиться» → «На экран Домой». Запускайте ULADIM с появившегося значка.'],['Android','Откройте /app в Chrome. В меню браузера выберите «Установить приложение» или «Добавить на главный экран».'],['Компьютер','В поддерживаемом браузере откройте /app и используйте кнопку установки рядом с адресной строкой. Можно работать и в обычной вкладке.']]){const d=el('details');add(d,el('summary',title),el('p',body));section.append(d);}target.append(section);
}

async function earlyAccess(){
  const config=await api('config');if(config.registration_open){heading('Прежние заявки','Обычная регистрация открыта. Приглашение больше не требуется; прежние заявки сохранены.');app.append(link('Начать бесплатно','/app?action=signup'));form('Проверить прежнюю заявку',[['email','Электронная почта','email']],'Получить код подтверждения',async b=>{await earlyApi('recover',{email:b.email});confirmEarly(b.email);});return;}
  heading('Ваше место в ULADIM','Оставьте заявку на закрытый тест. Мы приглашаем участников постепенно. Аккаунт и подписка при подаче заявки не создаются.');
  const f=form('Заявка на участие',[['email','Электронная почта','email']],'Получить код подтверждения',async b=>{if(!consent.checked)throw new Error('Подтвердите согласие с политикой обработки данных.');await earlyApi('apply',{...b,consent_version:'2026-11-08',website:trap.value});confirmEarly(b.email);});
  f.elements.email.autocomplete='email';f.elements.email.maxLength=254;
  const row=el('label',undefined,'consent');const consent=el('input');consent.type='checkbox';consent.required=true;const label=el('span','Согласен с обработкой email для заявки, её статуса и приглашения. ');const policy=el('a','Политика конфиденциальности');policy.href='/privacy';add(label,policy);add(row,consent,label);f.insertBefore(row,f.querySelector('button'));
  const trap=el('input');trap.name='website';trap.tabIndex=-1;trap.autocomplete='off';trap.className='honeypot';trap.setAttribute('aria-hidden','true');f.append(trap);
  action('Уже есть код? Проверить статус заявки',()=>{heading('Подтверждение заявки');form('Почта заявки',[['email','Электронная почта','email']],'Продолжить',b=>confirmEarly(b.email));});
  notice('Код действует 15 минут. Повторная заявка не даёт приоритета. После подтверждения можно отменить участие.');
}
function confirmEarly(email){
  heading('Проверьте почту','Введите код из письма ULADIM. Если письма нет, проверьте папку «Спам»; повторная отправка доступна через 5 минут.');
  const f=form('Подтвердить '+email,[['code','Код подтверждения','text']],'Подтвердить email',async b=>{const result=await earlyApi('confirm',{email,code:b.code.trim()});earlyStatus(result.management_token,result.state);});f.elements.code.autocomplete='one-time-code';f.elements.code.maxLength=43;
  action('Запросить другое письмо',earlyAccess);
}
function earlyStatus(token,state){
  const labels={pending:['Заявка в очереди','Адрес подтверждён. Когда появится место, мы отправим приглашение на почту.'],approved:['Вы приглашены','Приглашение отправлено на подтверждённый email. Оно действует 7 дней.'],rejected:['Набор пока ограничен','Сейчас мы не можем включить вас в тест. Аккаунт не создан.'],cancelled:['Заявка отменена','Приглашение, если оно было, больше не действует.']};
  const [title,description]=labels[state]||['Заявка','Подтвердите почту.'];heading(title,description);
  if(state!=='cancelled'){action('Обновить статус',async()=>{const result=await earlyApi('status',{management_token:token});earlyStatus(token,result.state);});action('Отменить заявку',async()=>{const result=await earlyApi('cancel',{management_token:token});earlyStatus(token,result.state);});}
  if(state==='approved')app.append(link('Создать аккаунт по приглашению','/account'));
  notice('Доступ к статусу хранится только в памяти этой страницы. После её закрытия подтвердите почту новым кодом.');
}
async function staffApplications(state='pending',before=''){
  heading('Заявки на закрытый тест','Подтверждённая заявка не является аккаунтом. Одобрение отправляет приглашение на 7 дней.');
  const filters=el('div',undefined,'actions');app.append(filters);for(const [key,label]of [['pending','Ожидают'],['approved','Приглашены'],['rejected','Отклонены'],['cancelled','Отменены']])action(label,()=>staffApplications(key),filters);
  const result=await api('applications?state='+encodeURIComponent(state)+(before?'&before='+encodeURIComponent(before):''));
  if(!result.applications.length)notice('Заявок в этой категории пока нет.');
  for(const item of result.applications){const card=panel(item.email,'Почта подтверждена: '+(item.verified_at?new Date(item.verified_at*1000).toLocaleString():'нет'));app.append(card);if(state==='pending')for(const [decision,label]of [['approved','Пригласить'],['rejected','Отклонить']])action(label,()=>{heading(label+': '+item.email);form('Решение по заявке',[['reason','Причина для журнала аудита','text']],'Подтвердить',async b=>{await api('applications/decide',{...b,id:item.id,revision:item.revision,decision});await staffApplications(state);});},card);}
  if(result.next)action('Следующая страница',()=>staffApplications(state,result.next));
}

// Scrub private views before the browser stores a history snapshot.
window.addEventListener('pagehide',()=>{viewEpoch++;csrf='';controlNavigation=null;app.replaceChildren();});
window.addEventListener('pageshow',event=>{if(!event.persisted)return;app.replaceChildren();if(staff)dashboard().catch(()=>login());else publicPage().catch(error=>{heading('Не удалось загрузить');notice(error.message);});});

// Public legal documents and help share the factual configuration below.
function legalPage(path){publicExperience.legal(path);}

function importGuide(host){
 const guide=el('section',undefined,'import-guide');
 guide.id='import';
 guide.append(el('h2','Перенос данных в ULADIM'));
 const steps=el('ol');
 for(const [title,body] of [
  ['Выберите пространство','Войдите в веб-приложение. В переключателе вверху выберите личное или доступное семейное пространство. Откройте «Профиль → Импорт и синхронизация».'],
  ['Откройте экспорт','Выберите календари, заметки или задачи. Можно выбрать несколько файлов за раз. Браузер распознаёт поддерживаемые форматы и показывает, что нашёл.'],
  ['Проверьте и сохраните','Проверьте названия, даты и предупреждения. Снимите отметку с ненужных записей и нажмите «Импортировать». Откройте соответствующий раздел в том же пространстве.'],
 ]){
  steps.append(add(el('li'),el('strong',title),el('p',body)));
 }
 guide.append(steps);
 for(const [title,body] of [
  ['Apple Notes и обычные файлы','На iPad откройте заметку, нажмите «Поделиться → Экспортировать как Markdown» и сохраните файл в «Файлы». В ULADIM выберите этот файл в разделе заметок. TXT и Markdown переносятся как редактируемый текст. PDF, HTML и вложения пока не поддерживаются.'],
  ['Google Keep','Запросите экспорт Google Keep в Google Takeout. Выберите скачанный ZIP с папкой Keep или отдельные JSON-файлы заметок. Текст и чек-листы сохраняются как редактируемый текст. Метки, закрепление, архивный статус, даты и вложения пока не переносятся. Заметки из корзины пропускаются.'],
  ['Календарь','Выберите файл .ics из прежнего календаря. Импортируются названия, начало, часовой пояс и поддерживаемые повторения. Проверьте предупреждения о длительности, описаниях и исключениях до сохранения. Файл .ics даёт разовую копию. Для обновлений с Google Calendar потребуется отдельное подключение, которое пока готовится.'],
  ['Задачи и планировщики','Совместимый JSON переносит название и состояние выполнения. Если в файле есть время, описание, подзадачи или другие поля, ULADIM предупредит, что они пока не перенесутся. Поддержка официального экспорта Structured ещё проверяется.'],
 ]) guide.append(panel(title,body));
 guide.append(link('Открыть ULADIM','/app'),link('Вопросы об импорте','/faq#import',true));
 host.append(guide);
 if(location.hash==='#import')requestAnimationFrame(()=>guide.scrollIntoView());
}

function importFaq(host){
 heading('Частые вопросы','Вход, перенос данных и работа с записями на разных устройствах.');
 const faq=el('section',undefined,'import-faq');
 faq.id='import';
 for(const [question,answer] of [
  ['Где открыть импорт?','В веб-приложении откройте «Профиль → Импорт и синхронизация». На телефоне профиль находится в меню «Ещё».'],
  ['Что будет при повторной загрузке?','ULADIM показывает найденные совпадения в предпросмотре. Если существующая запись отличается, её текущая версия сохраняется. Для обновления внешнего календаря потребуется отдельное подключение.'],
  ['Изменятся ли исходные записи?','Исходные файлы и записи в других приложениях остаются у вас. Файлы читаются в браузере. После подтверждения сервер получает только выбранные записи для указанного пространства.'],
  ['Где найти результат?','Откройте «Заметки», «Задачи» или «Календарь» в пространстве, куда выполнили импорт. На другом устройстве войдите в веб-версию под тем же аккаунтом и выберите это же пространство. Возможности Android зависят от версии клиента.'],
  ['Почему некоторые события пропущены?','Проверьте предупреждение в предпросмотре. События с неподдерживаемым правилом или исключением пропускаются, чтобы календарь не показал неверное расписание. Исходный файл можно открыть в прежнем календаре.'],
  ['Нужен ли интернет?','Для сохранения через веб-приложение и просмотра записей на другом устройстве нужен интернет. Локальные функции Android работают независимо от облачного аккаунта.'],
 ]) faq.append(add(el('details'),el('summary',question),el('p',answer)));
 faq.append(link('Пошаговое руководство','/docs#import'));
 host.append(faq);
 if(location.hash==='#import')requestAnimationFrame(()=>faq.scrollIntoView());
}

function focusLoginStory(create,lang){
 const copy={
  ru:['Меньше суеты.','Больше ясности.','Важное — в одном месте. Задачи, планы и финансы в вашем ритме.','Задачи и заметки','События и календарь','Личные и семейные финансы','В браузере на телефоне, планшете и компьютере.'],
  en:['Less to juggle.','More clarity.','Keep what matters together. Tasks, plans and finances at your pace.','Tasks and notes','Events and calendar','Personal and family finances','In your browser on phone, tablet and desktop.'],
  'uz-Latn':['Kamroq tashvish.','Ko‘proq aniqlik.','Muhim ishlar bir joyda. Vazifalar, rejalar va moliya o‘z maromingizda.','Vazifalar va qaydlar','Tadbirlar va taqvim','Shaxsiy va oilaviy moliya','Telefon, planshet va kompyuter brauzerida.'],
  'uz-Cyrl':['Камроқ ташвиш.','Кўпроқ аниқлик.','Муҳим ишлар бир жойда. Вазифалар, режалар ва молия ўз маромингизда.','Вазифалар ва қайдлар','Тадбирлар ва тақвим','Шахсий ва оилавий молия','Телефон, планшет ва компьютер браузерида.']
 }[lang]||['Less to juggle.','More clarity.','Keep what matters together. Tasks, plans and finances at your pace.','Tasks and notes','Events and calendar','Personal and family finances','In your browser on phone, tablet and desktop.'];
 const aside=create('aside',undefined,'focus-login-story');
 const heading=create('h2');heading.append(create('span',copy[0]),create('span',copy[1]));
 const list=create('ul');for(const text of copy.slice(3,6))list.append(create('li',text));
 aside.append(create('div','ULADIM · '+(lang==='ru'?'ФОКУС':'FOCUS'),'focus-story-label'),heading,create('p',copy[2]),list,create('p',copy[6],'focus-story-footnote'));
 return aside;
}

// Public facts have one reviewable source. Blank operator facts keep documents
// in draft; an API public_legal object can supply the same keys at deployment.
// Do not infer legal identity, residency, retention or age rules from branding.
const PUBLIC_RELEASE_FACTS=Object.freeze({
 version:'2026-11-13',updated:'13 ноября 2026 года',published:false,
 operatorName:'Usmonov U',operatorCountry:'Узбекистан',operatorPostalAddress:null,supportEmail:'support@getuladim.space',supportEmailReady:false,
 processingRegion:null,processingVerified:false,privacyLifecycleReady:false,retentionVerified:false,agePolicyEnforced:false,
 minimumAgePolicy:'Самостоятельный аккаунт предназначен для пользователей от 18 лет. До появления подтверждаемого письменного согласия законного представителя не создавайте аккаунты несовершеннолетних и не добавляйте их персональные данные. Семейная роль сама по себе не подтверждает согласие родителя или опекуна.',
 legalBasis:'Необходимые данные аккаунта и ваши записи обрабатываются для предоставления запрошенных вами функций и исполнения условий использования. Отдельное согласие запрашивается там, где его требует закон. Необходимая обработка также допускается для исполнения законных обязанностей и защиты прав пользователей в пределах законодательства Узбекистана. Отзыв согласия не отменяет обработку, для которой сохраняется самостоятельное законное основание.',
 securityRetention:'Сведения о действиях, необходимых для защиты сервиса, могут сохраняться в виде служебного номера аккаунта, вида действия и времени — без почты, средств входа и содержимого ваших записей. Для этих сведений срок автоматического удаления пока не установлен. Текстовые пояснения сотрудников хранятся отдельно в защищённом виде: до 90 дней или до удаления связанного аккаунта, если оно наступит раньше. Обращения в поддержку не включаются в такой журнал.',
 backupRetention:null,correspondenceRetention:null,plannedBackupDays:7,supportProviderRetentionDays:30,
 deletionGraceHours:24,deletionPolicy:'После завершения удаления стираются данные входа, почта, связь с Google, устройства и сеансы, обращения внутри приложения, а также все созданные вами личные и общие записи, включая их содержимое, доступное для восстановления. Личные записи других участников сохраняются: их суммы, даты, валюты и описания не переписываются. Общие итоги могут измениться, потому что ваши записи больше не участвуют в расчётах. Для отображения операций других участников может остаться только отметка об удалённом счёте и его валюта, без вашего имени и исходного содержимого. Служебный номер удалённого аккаунта и дата удаления сохраняются для предотвращения возврата данных при восстановлении.',
 android:{version:'0.3.1',build:312001,minAndroid:'Android 7.0',bytes:77458893,
  url:'https://github.com/pro100umarchikgamer-lgtm/lifeos/releases/download/uladim-native-84b0bdf2c6d5/ULADIM.apk',
  sha256:'66d123cef79f85b7b2665bdcad0e6309db4a694e9a5076ed871450154c762872',
  release:'https://github.com/pro100umarchikgamer-lgtm/lifeos/releases/tag/uladim-native-84b0bdf2c6d5'}
});
const publicExperience=(()=>{
 let facts={...PUBLIC_RELEASE_FACTS};
 const node=(tag,text,cls)=>el(tag,text,cls);
 const a=(text,href,cls)=>{const n=node('a',text,cls);n.href=href;return n;};
 const block=(title,...paragraphs)=>{const n=node('section',undefined,'help-prose');n.append(node('h2',title));for(const text of paragraphs)if(text)n.append(node('p',text));return n;};
 const inline=(text,href)=>a(text,href,'help-inline-link');
 const required=['operatorName','operatorCountry','operatorPostalAddress','supportEmail','processingRegion','minimumAgePolicy','legalBasis','securityRetention','backupRetention','correspondenceRetention','deletionPolicy'];
 const ready=()=>facts.published===true&&required.every(key=>typeof facts[key]==='string'&&facts[key].trim())&&Boolean(contact())&&facts.processingVerified===true&&facts.privacyLifecycleReady===true&&facts.retentionVerified===true&&facts.agePolicyEnforced===true;
 const contactAddress=()=>typeof facts.supportEmail==='string'&&/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(facts.supportEmail)?facts.supportEmail:null;
 const contact=()=>facts.supportEmailReady===true?contactAddress():null;
 function configure(value){if(value&&typeof value==='object'){for(const key of Object.keys(PUBLIC_RELEASE_FACTS))if(key!=='android'&&Object.hasOwn(value,key))facts[key]=value[key];}}
 function intro(kicker,title,description){
  document.title=title+' · ULADIM';app.classList.add('help-center');
  app.replaceChildren(node('div',kicker,'help-kicker'),node('h1',title),node('p',description,'help-lead'));
 }
 function related(items=[['Вопросы и ответы','/faq'],['Поддержка','/support']]){
  const nav=node('nav',undefined,'help-related');nav.setAttribute('aria-label','По теме');
  for(const [label,href]of items)nav.append(a(label,href));app.append(nav);
 }
 function contactLink(parent,label='Написать в поддержку'){
  const email=contact();if(email)parent.append(link(label,'mailto:'+email,true));
  else parent.append(node('p',contactAddress()?'Почтовая поддержка '+contactAddress()+' готовится к запуску. Пока отправьте обращение из своего аккаунта.':'Публичный адрес поддержки будет указан после подтверждения сведений об операторе. Пока обращение можно отправить из своего аккаунта.','help-muted'));
 }
 function draft(){
  if(ready())return;
  const n=node('aside',undefined,'help-draft');n.setAttribute('aria-label','Статус документа');
  n.append(node('strong','Редакция готовится к публикации'),node('p','Ниже приведён проект правил. Условия размещения данных, хранения резервных копий и доступность почтовой поддержки ещё подтверждаются. Окончательная редакция пока не опубликована.'));app.append(n);
 }
 function reader(sections){
  const layout=node('div',undefined,'help-reader'),toc=node('nav',undefined,'help-toc'),article=node('article',undefined,'help-document');
  toc.setAttribute('aria-label','Содержание документа');toc.append(node('p','На этой странице','help-kicker'));const list=node('ol');
  for(const [id,title,paragraphs]of sections){list.append(add(node('li'),a(title,'#'+id)));const section=block(title,...paragraphs);section.id=id;article.append(section);}
  toc.append(list);layout.append(toc,article);app.append(layout);
 }
 const safety='Не отправляйте пароли, одноразовые коды, полные банковские реквизиты, выписки или документы. Достаточно описать действие и сообщение на экране.';
 function legal(path){
  const privacy=path==='/privacy';
  intro('ДАННЫЕ И ПРАВИЛА',privacy?'Конфиденциальность':'Условия использования',privacy?'Какие данные нужны ULADIM, зачем они используются и как ими управлять.':'Понятные правила работы с аккаунтом, личными и общими записями.');
  const meta=node('div',undefined,'help-document-meta');meta.append(node('span','Обновлено '+facts.updated),node('span','Версия '+facts.version));
  const print=node('button','Распечатать','secondary');print.type='button';print.addEventListener('click',()=>window.print());meta.append(print);app.append(meta);draft();
  const highlights=node('section',undefined,'help-highlights');highlights.setAttribute('aria-label','Главное');
  for(const [title,text]of privacy?[
   ['Без рекламной аналитики','ULADIM не использует рекламные трекеры и не продаёт ваши данные.'],
   ['Данные по делу','Аккаунт и ваши записи нужны для выбранных вами функций.'],
   ['Контроль у вас','Управляйте доступом, устройствами и удалением аккаунта.']
  ]:[['Сейчас бесплатно','Подписка и банковская карта для текущих функций не нужны.'],['Ваши записи — ваши','Добавляйте данные, которыми вправе пользоваться и делиться.'],['Финансы для учёта','Приложение не проводит платежи и банковские переводы.']])highlights.append(add(node('div'),node('strong',title),node('p',text)));
  app.append(highlights);
  const operator=facts.operatorName?`Оператор сервиса: ${facts.operatorName}. ${facts.operatorCountry?'Страна: '+facts.operatorCountry+'.':''} ${facts.operatorPostalAddress?'Почтовый адрес: '+facts.operatorPostalAddress+'.':''}`:'Наименование и страна оператора будут добавлены в окончательную редакцию.';
  const email=contact();
  const sections=privacy?[
   ['operator','Кто отвечает за данные',[operator,email?'Вопросы о данных можно направить по адресу '+email+'.':contactAddress()?'Адрес для вопросов о данных: '+contactAddress()+'. Приём почты готовится к запуску. Пока действующий пользователь может создать обращение в своём аккаунте.':'Публичный адрес для вопросов о данных ещё не подтверждён. Действующий пользователь может создать обращение в разделе поддержки своего аккаунта.']],
   ['data','Какие данные используются',[
    'Для облачного аккаунта нужны адрес электронной почты, подтверждение адреса и сведения о выбранном способе входа. При входе по паролю сохраняется его защищённая проверочная запись, а не открытый пароль. Для безопасности используются сведения о сеансах и подключённых устройствах.',
    'Когда вы создаёте или синхронизируете записи, сервис обрабатывает их содержимое: задачи, заметки, события, счета, финансовые операции, переводы, бюджеты и другие выбранные вами данные. Не добавляйте сведения о других людях без достаточного основания.',
    'В общих пространствах обрабатываются состав участников, их роли, назначения и общие записи. Финансовая запись может содержать введённое вами имя контрагента, назначение или комментарий. Такие сведения также требуют бережного обращения.',
    'Сервис не предназначен для хранения биометрических и генетических материалов, медицинских документов и иных избыточных чувствительных сведений. Не добавляйте такие материалы в заметки, общие записи и обращения в поддержку.',
    'Если вы пишете в поддержку, обрабатываются тема обращения и сообщения, которые вы сами отправили. '+safety]],
   ['purpose','Зачем это нужно',[
    'Данные аккаунта нужны для входа, восстановления доступа и связи по вопросам безопасности. Содержимое записей используется для выбранных вами функций: хранения, планирования, отображения и синхронизации между устройствами и участниками пространства.',
    'Служебные письма связаны с вашим действием или безопасностью аккаунта. Рекламная рассылка и реклама в приложении не используются. ULADIM не подключает рекламную аналитику, межсайтовое отслеживание и продажу персональных данных.',
    facts.legalBasis||'Правовые основания обработки и особенности осуществления ваших прав будут указаны после подтверждения страны и статуса оператора.']],
   ['sharing','Кто может видеть записи',[
    'Личные и общие пространства разделены. Другие участники получают доступ к общим данным в пределах своей роли и настроек записи. Проверьте пространство и доступ перед сохранением личной информации.',
    'Сотрудники поддержки получают сообщения, которые вы отправили в обращении. Обычная панель поддержки не предоставляет им просмотр личных задач, заметок и финансов. Для эксплуатации сервиса доступ к инфраструктуре имеют уполномоченные лица в пределах своих обязанностей.',
    'Данные могут передаваться по законному требованию в случаях и объёме, предусмотренных применимым правом. Мы не обещаем абсолютную недоступность данных при обстоятельствах, когда закон требует их раскрытия.']],
   ['providers','Сервисы, которые помогают работе',[
    'Для размещения сервиса используется инфраструктура Hostinger. Служебные письма отправляются через Resend. Эти поставщики обрабатывают данные, необходимые для своей услуги. Почтовая переписка с поддержкой хранится отдельно от обращений внутри приложения.',
    facts.correspondenceRetention||'Стандартный срок хранения писем у поставщика почтовой поддержки — '+facts.supportProviderRetentionDays+' дней. Удаление аккаунта само по себе не удаляет отправленные отдельно письма и копии у почтовых поставщиков. Порядок очистки этой переписки будет указан после подтверждения работы почтовой поддержки.',
    'Вход через Google используется только по вашему выбору. Запрашиваются подтверждение личности и адрес электронной почты. Доступ к вашим контактам, Google Drive, заметкам и календарям этот вход не предоставляет. Подключение Google само по себе не импортирует записи.',
    facts.processingRegion?'Место обработки и международная передача: '+facts.processingRegion:'Регион размещения данных, условия международной передачи и сведения о поставщиках будут уточнены в окончательной редакции.']],
   ['device','Что остаётся на устройстве',[
    'Браузер использует необходимый файл cookie для сохранения входа. На устройстве также сохраняются выбранные язык, тема и другие настройки интерфейса. Файлы интерфейса могут сохраняться для его загрузки. Рекламные cookie не используются.',
    'Локальные записи Android хранятся на устройстве. Сам вход в аккаунт не означает автоматическую загрузку всех локальных данных. Облачная обработка начинается для записей, которые вы создаёте в веб-приложении или явно синхронизируете.',
    'Файлы импорта обрабатываются на устройстве. После проверки и подтверждения в облако отправляются выбранные записи. Этот инструмент не загружает исходный файл выписки целиком.']],
   ['retention','Сроки хранения и удаление',[
    'Данные действующего аккаунта используются, пока нужны для предоставления выбранных вами функций. Удалить отдельные записи и запросить удаление аккаунта можно в приложении.',
    `Запрос удаления аккаунта можно отменить в течение ${facts.deletionGraceHours} часов, до указанного времени. После этого вход блокируется и начинается удаление; завершение может занять время. Удаление облачного аккаунта не стирает сохранённые на ваших устройствах копии.`,
    facts.deletionPolicy||'Точный объём удаления личных данных, порядок обращения с общими записями и действия при исключительных обстоятельствах будут зафиксированы после проверки обновлённого процесса удаления.',
    facts.backupRetention?'Резервные копии: '+facts.backupRetention:'Срок хранения резервных копий и порядок исключения удалённых данных при восстановлении ещё уточняются. До подтверждения этих условий мы не обещаем мгновенное исчезновение данных из всех копий.',
    facts.securityRetention?'Данные безопасности: '+facts.securityRetention:'Состав и сроки хранения необходимых сведений безопасности будут указаны отдельно. Они не используются для рекламного профилирования.']],
   ['rights','Как управлять своими данными',[
    'В профиле можно изменить доступные сведения аккаунта, проверить устройства, отозвать доступ, настроить защиту и запросить удаление. Экспортируйте нужные записи и проверьте созданный файл перед удалением.',
    'Если нужно получить сведения об обработке, исправить данные, сообщить об ошибке или обратиться по поводу прав другого человека, используйте поддержку. Для защиты аккаунта может потребоваться подтвердить, что запрос относится к вам. Не передавайте пароль или одноразовый код сотруднику поддержки.',
    'Право на обращение в компетентный орган и другие предусмотренные законом права сохраняются. Срок ответа и применимые процедуры зависят от подтверждённой юрисдикции оператора.']],
   ['children','Семейные пространства и возраст',[facts.minimumAgePolicy||'Возрастные условия и порядок участия несовершеннолетних должны быть утверждены оператором до окончательной публикации. Наличие детской роли в семейном пространстве само по себе не заменяет согласие или участие законного представителя, если оно требуется законом.','Участник, добавляющий данные другого человека, должен иметь право на такое действие. Не размещайте в общих записях избыточные сведения о детях и других членах семьи.']],
   ['changes','Изменения политики',['Дата и версия указаны в начале страницы. При изменении состава обработки или существенных условий новая редакция должна описывать эти изменения понятным языком. Согласие запрашивается отдельно там, где оно требуется законом.']]
  ]:[
   ['operator','О сервисе и операторе',[operator,'ULADIM помогает вести задачи, заметки, календарь, личный финансовый учёт и общие семейные дела. Текущие функции предоставляются бесплатно.',ready()?'Настоящая редакция описывает условия использования сервиса. Дата и версия указаны в начале страницы.':'Окончательная публичная редакция условий будет действовать после заполнения и подтверждения сведений оператора.']],
   ['account','Аккаунт и безопасность',['Указывайте доступную вам электронную почту и подтверждайте её. Берегите пароль, коды подтверждения и резервные коды. Не передавайте аккаунт другому человеку. Если устройство потеряно, отзовите его доступ из профиля.','Используйте только аккаунты и пространства, к которым у вас есть право доступа. Не пытайтесь обходить защиту, читать чужие записи, мешать работе сервиса или распространять через него незаконный и вредоносный контент.']],
   ['records','Ваши записи и общие пространства',['Вы сохраняете права на собственное содержимое. Размещая запись, вы разрешаете обработку, необходимую для выбранных вами функций и настроек доступа. Это не передаёт сервису право продавать ваши записи.','Перед добавлением данных другого человека убедитесь, что вправе это сделать. Выбирайте пространство и участников осознанно. Изменение общих записей может повлиять на других участников; проверяйте последствия перед подтверждением.']],
   ['availability','Сохранение, синхронизация и доступность',['Для сохранения и просмотра облачных записей нужно соединение. Локальные функции Android могут работать отдельно от облака. Если соединение пропало во время сохранения, проверьте состояние записи перед повторным вводом.','Технические работы и сбои могут временно ограничивать доступ. Для важных записей сохраняйте собственную копию. Возможность восстановления зависит от доступных данных и срока хранения; поддержка не обещает восстановить любую удалённую запись.']],
   ['finance','Финансовый учёт',['ULADIM предназначен для записи и анализа введённых вами данных. Создание перевода в приложении не переводит деньги, не подключает банковский счёт и не выполняет платёж. Приложение не оказывает банковские, кредитные, брокерские или инвестиционные услуги.','Проверяйте исходные суммы, валюты и импорт перед сохранением. Финансовые результаты зависят от полноты и правильности введённых записей. Суммы в разных валютах не следует складывать без выбранного вами способа пересчёта.']],
   ['plans','Бесплатный доступ и будущие подписки',['Все текущие функции доступны бесплатно. Банковская карта и оформление подписки не требуются. Отображаемый уровень доступа сам по себе не означает покупку или согласие на списания.','Plus готовится как будущий вариант доступа. Его окончательные функции, цена, срок и условия продления пока не опубликованы. Возможности с искусственным интеллектом относятся к более поздним планам и сейчас недоступны.','До появления платной услуги её условия должны отдельно сообщать полную цену, период, правила продления, отмены, восстановления покупки и возврата. Новые платные условия не создают согласие на оплату автоматически.']],
   ['refunds','Отмена и возвраты',['Сейчас реальные покупки и списания в ULADIM отключены, поэтому платная подписка здесь не оформляется. Если вы заметили незнакомое списание с похожим названием, проверьте получателя и обратитесь в банк или площадку, где оно было совершено.','Если платные услуги будут запущены, способ управления и возврата будет зависеть от места покупки и применимого закона. Для каждого способа оплаты понадобятся опубликованные правила и доступная поддержка. Эти условия не ограничивают обязательные права потребителя.']],
   ['ending','Прекращение доступа и удаление',['Вы можете перестать пользоваться сервисом и запросить удаление аккаунта. Облачное удаление и очистка данных на вашем устройстве выполняются отдельно. Перед удалением сохраните нужные записи и проверьте общие пространства.','Доступ может быть ограничен для защиты пользователей и сервиса при нарушении правил или выявлении угрозы. Причина и доступный способ обращения должны сообщаться в пределах, допустимых законом и требованиями безопасности. Порядок удаления описан на отдельной странице.']],
   ['age','Семья и возраст',[facts.minimumAgePolicy||'Условия участия несовершеннолетних и законного представительства будут указаны после утверждения оператором. Не следует считать, что семейная роль автоматически подтверждает право использовать сервис в любом возрасте.']],
   ['law','Ответственность и обращения',['Обязательные права, предоставленные вам применимым законом, сохраняются. Эти условия не исключают ответственность, которую нельзя исключить по закону.',ready()?'Споры рассматриваются в порядке, предусмотренном применимым законом, с сохранением обязательных прав потребителя. Сведения об операторе и контакт для обращения указаны выше. Для начала можно описать вопрос в поддержке.':'Применяется законодательство Республики Узбекистан с сохранением обязательных прав, которые предоставляет вам применимый закон. Сначала можно направить обращение оператору. Подсудность и порядок рассмотрения спора определяются законом; эти условия не отменяют право обратиться в компетентный орган или суд.']],
   ['changes','Обновления условий',['Дата и версия находятся в начале страницы. Существенные изменения публикуются в новой редакции. Появление новых платных возможностей требует отдельного понятного предложения и вашего согласия там, где оно необходимо.']]
  ];
  reader(sections);related([[privacy?'Условия использования':'Конфиденциальность',privacy?'/terms':'/privacy'],['Удаление аккаунта','/delete-account'],['Поддержка','/support']]);openHash();
 }
 const groups=[
  ['start','Начало работы','От первой записи до удобного дня',[
   ['today','С чего начать?','Откройте ULADIM и добавьте одну задачу или заметку. Выберите личное пространство. После этого настройте календарь и финансовые счета — в том порядке, который удобен вам.','Открыть приложение','/app'],
   ['tasks','Как вести задачи?','Добавьте понятное название и дату, если она нужна. Завершённые задачи отмечайте выполненными. Для общих дел сначала выберите семейное пространство и проверьте исполнителя.','Руководство','/docs#first-record'],
   ['notes','Где сохранять идеи и списки?','Используйте заметки для текста, идей и списков. Перед сохранением проверьте личное или общее пространство. Перенести текст из другого приложения можно через импорт.','О переносе заметок','/faq#import'],
   ['calendar','Как планировать события?','Укажите начало события и часовой пояс. Для повторяющегося события проверьте правило повторения и ближайшие даты. Уведомления настраиваются отдельно на каждом устройстве.','Об уведомлениях','/faq#notifications']
  ]],
  ['devices','Устройства и перенос','Установка, синхронизация и файлы',[
   ['installation','Как установить ULADIM?','На Android доступен отдельный APK. На iPhone, iPad и компьютере открывайте веб-приложение в браузере; его можно добавить на домашний экран. Отдельная версия для iOS пока не выпущена.','Приложения и установка','/download'],
   ['sync','Почему записи отличаются на устройствах?','Проверьте, что вошли в один аккаунт и выбрали одно пространство. Для облачной синхронизации нужно соединение. Сам вход в Android не переносит все локальные записи автоматически: используйте доступные средства импорта и синхронизации.','Как перенести данные','/docs#import'],
   ['import','Как перенести записи из другого приложения?','В веб-приложении откройте «Профиль → Импорт и синхронизация». Выберите тип данных и файл, проверьте предпросмотр и подтвердите только нужные записи. Заметки: TXT, Markdown и экспорт Google Keep. Календарь: ICS. Вложения и неподдерживаемые правила могут не перенестись — проверьте предупреждения.','Пошаговый перенос','/docs#import'],
   ['import-original','Изменит ли импорт исходные файлы?','Исходные файлы и записи в других приложениях остаются у вас. Файл читается на устройстве; после подтверждения в облако передаются выбранные записи. При повторном импорте проверьте совпадения в предпросмотре.','Руководство по импорту','/docs#import'],
   ['notifications','Почему не пришло напоминание?','Проверьте дату, время и часовой пояс события, разрешение уведомлений и настройки самого устройства. На Android ограничения батареи могут задерживать напоминания. В браузере разрешите уведомления именно для ULADIM. Включайте только те напоминания, которые вам нужны.','Помощь с устройством','/support']
  ]],
  ['money-family','Финансы и семья','Личный учёт и общие дела',[
   ['finances','Можно ли переводить деньги через ULADIM?','ULADIM ведёт учёт введённых вами сумм. Запись перевода перемещает сумму между счетами в вашем учёте; деньги в банке она не переводит. Проверяйте валюту и исходные данные, особенно после импорта.','О финансовом учёте','/terms#finance'],
   ['family','Кто видит записи семьи?','Доступ зависит от выбранного пространства, роли участника и настроек записи. Личную заметку сохраняйте в личном пространстве. Перед добавлением в общую запись сведений о другом человеке убедитесь, что вправе ими делиться.','Как устроен доступ','/privacy#sharing'],
   ['family-leave','Что проверить перед уходом из семьи?','Сохраните нужные личные копии и проверьте общие дела. Владельцу может потребоваться передать управление другому взрослому участнику или явно завершить работу семейного пространства. Внимательно прочитайте последствия в окне подтверждения.','Об удалении аккаунта','/delete-account']
  ]],
  ['account-group','Аккаунт и защита','Вход, восстановление и приватность',[
   ['account','Нужен ли аккаунт?','Аккаунт нужен для облачных записей и общих пространств. Локальные функции Android могут использоваться отдельно. Для входа используйте свой подтверждённый адрес почты или подключённый Google.','Открыть аккаунт','/account'],
   ['security','Как защитить аккаунт?','Выберите уникальный пароль и включите доступную двухфакторную защиту. Сохраните резервные коды в безопасном месте. В профиле проверьте устройства и отзовите потерянные. Никому не сообщайте коды и пароль, в том числе в поддержке.','Политика конфиденциальности','/privacy'],
   ['recovery','Как восстановить доступ?','На странице входа выберите восстановление пароля и укажите почту аккаунта. Проверьте входящие и папку «Спам». Если использовали Google, попробуйте тот же Google-аккаунт. Если вход недоступен или доступ ограничен, обратитесь в поддержку.','Войти или восстановить','/account'],
   ['privacy','Есть ли реклама и сбор аналитики?','Рекламных трекеров и рекламной аналитики нет. Сервис обрабатывает необходимые данные аккаунта, записи, которые вы сохраняете, и сведения для безопасности. Подробности о поставщиках, доступе и сроках приведены в политике.','Какие данные используются','/privacy#data'],
   ['deletion','Как удалить аккаунт и данные?','Откройте удаление аккаунта в профиле. Сначала сохраните нужное и проверьте общие пространства. Запрос можно отменить в течение 24 часов до указанного времени. Затем вход блокируется и начинается удаление; завершение может занять время. Все созданные вами записи, в том числе общие, удаляются. Копии на устройствах очищаются отдельно.','Открыть удаление аккаунта','/app?settings=deletion'],
   ['delete-staff-account','Как удалить аккаунт, если я сотрудник сервиса?','Сначала передайте рабочие обязанности и завершите служебный доступ через уполномоченного владельца сервиса. Для единственного владельца потребуется сохранить возможность управления сервисом после передачи. Эта страница не выдаёт новые права и не выполняет передачу автоматически. Затем вернитесь к обычному удалению аккаунта.','Обратиться в поддержку','/support']
  ]],
  ['access','Доступ и поддержка','Бесплатные функции и помощь',[
   ['plans','Нужно ли платить за ULADIM?','Сейчас все доступные функции бесплатны. Карта и подписка не нужны. Plus готовится на будущее; цены и окончательные различия ещё не опубликованы. Возможности с искусственным интеллектом сейчас недоступны.','Тарифы','/plans'],
   ['refund','Как отменить подписку или вернуть оплату?','Сейчас покупки отключены и подписка в ULADIM не оформляется. Если платные услуги появятся, условия цены, продления, отмены и возврата будут опубликованы до оплаты. Незнакомое списание проверьте у банка или площадки покупки.','Условия использования','/terms#refunds'],
   ['support','Как получить помощь?','Опишите, что хотели сделать, на каком шаге возникла проблема и какой текст появился на экране. Укажите устройство и версию приложения. Скройте личные данные на снимке экрана. Пароли, коды и банковские документы не нужны.','Связаться с поддержкой','/support']
  ]]
 ];
 function openHash(){
  let id;try{id=decodeURIComponent(location.hash.slice(1));}catch{return;}if(!id)return;const target=document.getElementById(id);if(!target)return;
  if(target.tagName==='DETAILS')target.open=true;
  requestAnimationFrame(()=>{target.scrollIntoView({block:'start'});});
 }
 function faq(){
  intro('ЦЕНТР ПОМОЩИ','Найдём ответ','Начало работы, перенос записей, семья и приватность — всё в одном месте.');
  const search=node('div',undefined,'help-search');const label=node('label','О чём хотите узнать?');label.htmlFor='help-search';const input=node('input');input.id='help-search';input.type='search';input.placeholder='Например: импорт, уведомления, удаление';input.autocomplete='off';
  const count=node('p','','help-result-count');count.setAttribute('role','status');count.setAttribute('aria-live','polite');add(search,label,input,count);app.append(search);
  const layout=node('div',undefined,'help-reader'),nav=node('nav',undefined,'help-toc'),content=node('div',undefined,'help-faq-groups');nav.setAttribute('aria-label','Темы помощи');nav.append(node('p','Выберите тему','help-kicker'));
  const entries=[];
  for(const [id,title,subtitle,questions]of groups){
   nav.append(a(title,'#'+id));const section=node('section',undefined,'help-faq-group');section.id=id;section.append(node('h2',title),node('p',subtitle,'help-muted'));
   for(const [anchor,q,answer,label,href]of questions){const details=node('details',undefined,'help-question');details.id=anchor;const body=node('div',undefined,'help-answer');body.append(node('p',answer),inline(label,href));details.append(node('summary',q),body);section.append(details);entries.push({details,section,text:(title+' '+q+' '+answer).toLocaleLowerCase('ru')});}
   content.append(section);
  }
  const empty=node('section',undefined,'help-empty');empty.hidden=true;empty.append(node('h2','Пока не нашли подходящий ответ'),node('p','Попробуйте другое слово или напишите нам — подскажем, с чего начать.'),inline('Получить помощь','/support'));content.append(empty);layout.append(nav,content);app.append(layout);
  function filter(){const query=input.value.trim().toLocaleLowerCase('ru');const words=query.split(/\s+/).filter(Boolean);let visible=0;
   for(const entry of entries){const match=words.every(word=>entry.text.includes(word));entry.details.hidden=!match;if(match)visible++;if(query&&match)entry.details.open=true;else if(!query)entry.details.open=entry.details.id===location.hash.slice(1);}
   for(const section of content.querySelectorAll('.help-faq-group'))section.hidden=!entries.some(entry=>entry.section===section&&!entry.details.hidden);
   empty.hidden=visible>0;count.textContent=query?'Найдено ответов: '+visible:'Ответы по темам: '+entries.length;
  }
  input.addEventListener('input',filter);nav.addEventListener('click',()=>{if(input.value){input.value='';filter();}});
  window.addEventListener('hashchange',openHash);filter();openHash();related([['Руководство','/docs'],['Установка','/download'],['Задать вопрос','/support']]);
 }
 function support(){
  intro('МЫ РЯДОМ','Поможем разобраться','Вопрос о записи, входе или своих данных — начните с удобного способа связи.');
  const grid=node('div',undefined,'help-support-grid');
  const own=block('Есть доступ к аккаунту','Отправьте обращение из профиля: там сохранятся ваш вопрос и ответ. Выберите подходящую тему — так будет проще разобраться.');own.append(link('Открыть аккаунт','/account'));grid.append(own);
  const no=block('Не получается войти?','Попробуйте восстановить пароль или войти тем же Google-аккаунтом. Для вопроса об ограничении доступа или своих данных не передавайте средства входа.');no.append(inline('Помощь со входом','/faq#recovery'));contactLink(no);grid.append(no);app.append(grid);
  const how=block('Что поможет быстрее найти решение','Опишите ожидаемый результат, действие перед ошибкой и сообщение на экране. Добавьте модель устройства, браузер и версию приложения, если знаете их.','На снимке экрана закройте имена, адреса, суммы и другие личные сведения, которые не относятся к вопросу.',safety);app.append(how);
  related([['Вопросы и ответы','/faq'],['Запрос о данных','/privacy#rights'],['Удаление аккаунта','/delete-account']]);
 }
 function deletion(){
  intro('ВАШ АККАУНТ','Удаление аккаунта','Проверьте последствия, сохраните нужное и подтвердите решение.');
  const callout=node('aside',undefined,'help-callout');callout.append(node('strong','Есть время передумать'),node('p',`Запрос можно отменить в течение ${facts.deletionGraceHours} часов до указанного времени. Затем вход блокируется и начинается удаление; завершение может занять время.`));app.append(callout);
  const steps=node('ol',undefined,'help-steps');for(const [title,text]of [
   ['Сохраните нужные записи','Экспортируйте данные, которые хотите оставить, и убедитесь, что созданный файл открывается.'],
   ['Проверьте общие пространства','Если управляете семьёй, передайте управление другому взрослому участнику или явно закройте семейное пространство. При закрытии участники потеряют облачный доступ к этому пространству. Сначала прочитайте последствия; записи других участников не становятся вашими и не передаются вам.'],
   ['Откройте удаление в профиле','Войдите в аккаунт, откройте раздел аккаунта и приватности и выберите удаление. Подтвердите, что действие выполняете вы, и прочитайте итоговое предупреждение.'],
   ['Дождитесь окончания срока отмены','Если передумали, вернитесь в тот же раздел до окончания 24 часов и отмените запрос. После окончания 24 часов вход блокируется и начинается удаление. Завершение может занять время; окончание срока отмены не означает, что данные уже стёрты.']
  ])steps.append(add(node('li'),node('h2',title),node('p',text)));app.append(steps,link('Открыть удаление аккаунта','/app?settings=deletion'));
  reader([
   ['removed','Что будет удалено',[facts.deletionPolicy||'Удаление предназначено для прекращения облачного аккаунта и удаления связанных с ним личных данных. Точный перечень и порядок для общих записей уточняются в проверяемом процессе удаления; окончательная политика ещё не опубликована.']],
   ['separate-mail','Письма в поддержку',[facts.correspondenceRetention||'Обращения внутри приложения удаляются вместе с аккаунтом. Письма, которые вы отправляли отдельно по электронной почте, и копии у почтовых поставщиков обрабатываются отдельно. Стандартный срок хранения писем у поставщика поддержки — '+facts.supportProviderRetentionDays+' дней; работа почтового канала и порядок очистки ещё подтверждаются.']],
   ['local-copy','Что проверить на устройствах',['Удаление облачного аккаунта не очищает автоматически локальную базу Android, сделанные вами экспорты и копии на других устройствах. Если хотите удалить и их, отдельно очистите данные приложения и собственные файлы после сохранения нужного. Не удаляйте приложение ради обычного обновления.']],
   ['backups','Резервные копии',[facts.backupRetention||'Подтверждённый срок хранения резервных копий и порядок исключения удалённых данных при восстановлении будут указаны в окончательной политике. Мгновенное стирание всех резервных копий пока не заявляется.']],
   ['no-access','Если вход недоступен',['Попробуйте восстановить доступ. Если это невозможно, обратитесь по вопросу удаления через доступный контакт поддержки. Для защиты ваших данных потребуется подтвердить принадлежность аккаунта. Пароль и одноразовый код сообщать поддержке не нужно.']]
  ]);contactLink(app,'Обратиться по вопросу удаления');related([['Восстановление доступа','/faq#recovery'],['Конфиденциальность','/privacy#retention'],['Поддержка','/support']]);openHash();
 }
 function download(){
  intro('ULADIM НА ВАШИХ УСТРОЙСТВАХ','Ближе к вашему дню','В браузере на телефоне и компьютере. Отдельное приложение — для Android.');
  const grid=node('div',undefined,'help-download-grid'),web=block('Открыть в браузере','На iPhone, iPad, Android, Windows, macOS и Linux. Можно пользоваться во вкладке или добавить значок на домашний экран.');web.append(link('Открыть ULADIM','/app'),inline('Добавить на домашний экран','#installation'));grid.append(web);
  const android=facts.android,card=block('Приложение для Android','Доступная сборка для прямой установки. Скачивайте APK только по официальной ссылке ниже.');card.id='android';
  card.append(node('p',`Версия ${android.version} · сборка ${android.build} · ${(android.bytes/1000000).toLocaleString('ru',{maximumFractionDigits:1})} МБ · ${android.minAndroid} и новее`,'help-download-meta'),link('Скачать APK для Android',android.url),inline('Сведения об этой сборке',android.release));grid.append(card);app.append(grid);
  const update=block('Обновление без потери записей','Установите новую официальную версию поверх уже установленной. Не удаляйте приложение и не очищайте его данные ради обновления. Если Android предлагает удалить прежнюю версию, остановитесь и обратитесь в поддержку.','Перед обновлением важных локальных данных сделайте собственную резервную копию. Установка APK может потребовать временно разрешить установку из выбранного браузера или файлового приложения; после установки разрешение можно отключить.');app.append(update);
  const hash=node('details',undefined,'help-question');hash.append(node('summary','Как проверить скачанный файл?'));const body=node('div',undefined,'help-answer');body.append(node('p','Для доступной сборки контрольная сумма SHA-256:'),node('code',android.sha256,'help-digest'),node('p','Контрольная сумма помогает убедиться, что файл совпадает с опубликованным. Если значения отличаются, не устанавливайте файл и сообщите в поддержку.'));hash.append(body);app.append(hash);
  installGuide(app);related([['Помощь с установкой','/faq#installation'],['Поддержка','/support']]);openHash();
 }
 return {configure,legal,faq,support,deletion,download};
})();
