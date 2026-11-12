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
const errors={unauthorized:'Войдите в аккаунт.',invalid_credentials:'Проверьте почту и пароль.',staff_auth_invalid:'Проверьте данные входа и новый код MFA.',rate_limited:'Слишком много попыток. Подождите перед повтором.',staff_forbidden:'Для этого действия нет разрешения.',csrf_invalid:'Обновите страницу и повторите действие.',verify_email:'Сначала подтвердите почту в приложении.',registration_closed:'Регистрация пока доступна только приглашённым тестировщикам.'};
async function api(path,body){const epoch=viewEpoch;const response=await fetch(prefix+path,{method:body?'POST':'GET',credentials:'same-origin',headers:body?{'Content-Type':'application/json','X-CSRF-Token':csrf}:{},body:body?JSON.stringify(body):undefined});const value=await response.json();if(epoch!==viewEpoch)throw new Error('Обновите страницу и повторите действие.');if(!response.ok){const error=new Error(authPacks[authLanguage]?.strings['family_error_'+value.error]||tr('family_error_invalid_input'));error.code=value.error;throw error;}return value;}
function heading(title,description){app.replaceChildren(el('div',staff?'ULADIM Control':'ULADIM','eyebrow'),el('h1',title));if(description)app.append(el('p',description));if(staff&&controlNavigation)app.append(controlNavigation);}
function notice(text){app.append(el('div',text,'notice'));}
function panel(title,body){return add(el('section',undefined,'card'),el('h2',title),el('p',body));}
function field(form,name,label,type='text'){const id='field-'+name;const l=el('label',label);l.htmlFor=id;const input=el(name==='message'?'textarea':'input');input.id=id;input.name=name;if(name!=='message')input.type=type;input.required=true;if(type==='password')input.autocomplete='current-password';form.append(l,input);return input;}
function form(title,fields,submit,run){const f=el('form',undefined,'panel');f.append(el('h2',title));const inputs={};for(const [name,label,type]of fields)inputs[name]=field(f,name,label,type);const message=el('p');message.setAttribute('role','status');const button=el('button',submit);button.type='submit';f.append(message,button);f.addEventListener('submit',async e=>{e.preventDefault();button.disabled=true;message.textContent='';try{await run(Object.fromEntries(Object.entries(inputs).map(([k,v])=>[k,v.value])));message.textContent=tr('account_done');}catch(error){message.className='error';message.textContent=error.message;}finally{button.disabled=false;}});app.append(f);return f;}
function login(){
 if(staff)controlNavigation=null;document.body.dataset.auth='true';app.classList.add('auth');heading(staff?'ULADIM Control':tr('family_login'));
 const f=form('',[['email',tr('family_email'),'email'],['password',tr('web_password'),'password']],tr('family_login'),async b=>{
 let r;try{r=await api('login',b);}finally{f.elements.password.value='';b.password='';}
 if(r.mfa_required){loginMfa(r.challenge);return;}csrf=r.csrf;app.classList.remove('auth');await dashboard();
 });f.elements.email.autocomplete='username';
 if(!staff&&googleEnabled)action(tr('account_google_sign_in'),async()=>{const value=await api('google/start',{});location.assign(value.authorization_url);});
 if(!staff){action(tr('family_register'),registration);action(tr('family_recovery'),recovery);}authLanguages();
}
function loginMfa(challenge){
 heading(tr('account_mfa'),tr('web_mfa_hint'));
 const f=form('',[['code',tr('family_code'),'text']],tr('family_login'),async b=>{let r;try{r=await api('login/mfa',{challenge,code:b.code.trim()});}catch(e){if(e.code==='invalid_credentials')e.message=tr('web_mfa_hint');throw e;}finally{f.elements.code.value='';b.code='';}challenge='';csrf=r.csrf;app.classList.remove('auth');await dashboard();});
 f.elements.code.autocomplete='one-time-code';f.elements.code.spellcheck=false;f.elements.code.focus();action(tr('cancel'),()=>{challenge='';login();});
}

function action(label,run,parent=app){const button=el('button',label,'secondary');button.type='button';button.addEventListener('click',async()=>{button.disabled=true;try{await run();}catch(e){notice(e.message);}finally{button.disabled=false;}});parent.append(button);}
function showObject(value){const pre=el('pre',JSON.stringify(value,null,2));app.append(pre);}
async function support(){heading('Поддержка','Сообщайте только сведения, которыми хотите поделиться. Не отправляйте пароли, коды, банковские выписки или личные документы.');const result=await api('support');for(const ticket of result.tickets){const row=add(el('section',undefined,'card'),el('h2',ticket.subject),el('p',ticket.category+' · '+ticket.state));action('Открыть обращение',async()=>{const r=await api('thread?id='+encodeURIComponent(ticket.id));heading(ticket.subject);for(const m of r.messages)app.append(panel(m.is_staff?'Поддержка':'Вы',m.body));form('Ответить',[['message','Сообщение','text']],'Отправить',async b=>{await api(staff?'support/reply':'support/reply',{...b,ticket_id:ticket.id,state:staff?'waiting':'open'});await support();});},row);app.append(row);}if(!staff)form('Новое обращение',[['subject','Тема','text'],['message','Сообщение','text']],'Отправить',async b=>{await api('support',{...b,category:'other'});await support();});}
async function dashboard(){const session=await api('session');csrf=session.csrf;if(!staff){location.replace('/app');return;}delete document.body.dataset.auth;heading(staff?'Обзор сервиса':'Ваш ULADIM',staff?'Операционные показатели без доступа к личным записям пользователей.':session.email);const tabs=el('div',undefined,'tabs');app.append(tabs);action('Выйти',async()=>{await api('logout',{});csrf='';login();},tabs);if(staff){controlNavigation=makeControlNavigation(session,tabs);if(session.permissions.includes('dashboard.read')){const data=await api('dashboard');const grid=el('div',undefined,'grid metrics');for(const [key,value]of Object.entries(data)){if(typeof value==='number'||value===null)grid.append(metricCard(key,value));}app.append(grid);}else notice('Выберите доступный раздел.');}else{action('Поддержка',support,tabs);action('Аккаунт и приватность',accountPrivacy,tabs);const ent=await api('entitlements');const grid=el('div',undefined,'grid');grid.append(panel('Ваш доступ: '+ent.tier,ent.billing_managed_by?'Управляется через '+ent.billing_managed_by:'Платёж не оформлен. Текущий доступ не означает платную подписку.'));grid.append(panel('Данные на устройстве','Личные записи остаются в зашифрованной базе Android. Кабинет не предоставляет к ним доступ.'));app.append(grid);const devices=await api('devices');app.append(el('h2','Устройства'));for(const device of devices.devices){const row=add(el('div',undefined,'row'),el('span',device.label||'Устройство'),el('span',new Date(device.last_seen_at*1000).toLocaleString(),'badge'));if(!device.revoked_at)action('Отозвать доступ',async()=>{heading('Отозвать доступ устройства');form(device.label,[['password','Ваш пароль','password']],'Подтвердить отзыв',async b=>{await api('devices/revoke',{device_id:device.id,password:b.password});await dashboard();});},row);app.append(row);}notice('Покупки пока отключены. Free, Plus и Premium используют единый серверный каталог.');}}
function publicNavigation(path) {
 const header=document.querySelector('body > header');
 const nav=header.querySelector('nav');
 const signIn=nav.querySelector('a[href="/account"]');
 const apps=el('a','Приложения');
 apps.href='/download';
 nav.insertBefore(apps,signIn);
 nav.id='public-navigation';
 for(const entry of nav.querySelectorAll('a')) {
  if(entry.pathname===path)entry.setAttribute('aria-current','page');
 }

 const controls=el('div',undefined,'public-header-controls');
 const mobileSignIn=signIn.cloneNode(true);
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
function startLink(config) {
 return config.registration_open ? link('Начать бесплатно','/app?action=signup') : link('Открыть ULADIM','/app');
}
async function publicPage(config) {
 const path=location.pathname;
 if(path==='/account') {
  try{await dashboard();}catch(e){if(e.code==='unauthorized'||e.code==='staff_unauthorized')login();else throw e;}
  return;
 }
 document.body.classList.add('product-site');
 publicNavigation(path);
 if(path==='/'){await landing(config);return;}
 app.classList.add('product-content');
 if(['/privacy','/terms'].includes(path)){legalPage(path);return;}
 if(path==='/early-access'){await earlyAccess();return;}
 if(path==='/docs') {
  heading('Порядок в ваших делах','Записывайте задачи и идеи, планируйте события и ведите финансы в одном аккаунте. Для общих дел можно создать семейное пространство.');
  app.append(panel('Начните с одной записи','Добавьте задачу, заметку или финансовый счёт в личном пространстве. Если хотите планировать вместе с близкими, создайте семейное пространство и пригласите их.'));
  installGuide(app);
  importGuide(app);
  app.append(startLink(config));
  return;
 }
 if(path==='/faq'){importFaq(app);return;}
 if(path==='/download'){applicationPage();return;}
 if(path==='/plans') {
  heading('Free, Plus, Premium','Пользуйтесь текущими возможностями ULADIM бесплатно. Платные подписки пока недоступны.');
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
 try {
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
})();

async function registration(){
 const config=await api('config');heading(tr('family_register'));
 const fields=[['email',tr('family_email'),'email'],['password',tr('family_password'),'password']];if(!config.registration_open)fields.push(['invitation',tr('family_invitation'),'text']);
 const f=form('',fields,tr('family_register'),async b=>{const email=b.email;try{await api('signup',b);}finally{f.elements.password.value='';b.password='';}heading(tr('family_verify'),tr('family_verify_hint'));
 form('',[['code',tr('family_code'),'text']],tr('family_verify'),async code=>{await api('confirm-signup',{email,code:code.code.trim()});login();notice(tr('account_done'));});action(tr('ux3_resend_verification'),async()=>{await api('resend-signup',{email});notice(tr('family_verify_hint'));});});
 if(config.google_enabled)action(tr('account_google_sign_in'),async()=>{const result=await api('google/start',{invitation:f.elements.invitation?.value});location.assign(result.authorization_url);});
 f.elements.password.autocomplete='new-password';app.append(link(tr('account_privacy'),'/privacy',true));
}

function recovery(){heading(tr('family_recovery'));form('',[['email',tr('family_email'),'email']],tr('account_send'),async b=>{const email=b.email;await api('recovery',{email});heading(tr('family_recovery'),tr('family_recovery_hint'));const f=form('',[['code',tr('family_code'),'text'],['password',tr('family_new_password'),'password']],tr('save'),async value=>{try{await api('reset',{email,...value});}finally{f.elements.password.value='';f.elements.code.value='';value.password='';value.code='';}login();notice(tr('account_done'));});f.elements.code.autocomplete='one-time-code';f.elements.password.autocomplete='new-password';});}

async function accountPrivacy(){heading('Аккаунт и приватность');action('Двухфакторная защита',customerMfa);const status=await api('deletion');for(const transfer of status.incoming_transfers||[]){form('Принять владение: '+transfer.name,[['password','Ваш пароль','password']],'Принять владение семьёй',async b=>{await api('accept-transfer',{transfer_id:transfer.id,password:b.password});await accountPrivacy();});}form('Сменить пароль',[['old_password','Текущий пароль','password'],['new_password','Новый пароль: от 7 символов','password']],'Сменить и выйти',async b=>{await api('password',b);login();});form('Сменить почту',[['email','Новый адрес','email'],['password','Текущий пароль','password']],'Отправить код',async b=>{await api('email',b);heading('Подтвердить новую почту');form('Код из письма',[['code','Код','text']],'Подтвердить и выйти',async value=>{await api('confirm-email',{code:value.code,password:b.password});login();});});app.append(el('h2','Удаление облачного аккаунта'));notice('Запрос можно отменить в течение 24 часов. Локальная база Android и общие записи семьи сохраняются. Срок очистки резервных копий требует отдельной проверки оператором.');if(status.ownership_transfer_required.length){notice('Сначала передайте владение семейным пространством другому родителю с его подтверждением.');for(const family of status.ownership_transfer_required){if(family.eligible_parent_id)form('Передать владение: '+family.name,[['password','Ваш пароль','password']],'Запросить согласие другого родителя',async b=>{await api('transfer',{workspace_id:family.id,user_id:family.eligible_parent_id,password:b.password});notice('Запрос создан. Другой родитель может принять его в разделе приватности своего аккаунта.');});}}else if(status.request?.state==='pending'){notice('Запрос ожидает исполнения после '+new Date(status.request.due_at*1000).toLocaleString());form('Отменить запрос',[['password','Текущий пароль','password']],'Отменить удаление',async b=>{await api('cancel-deletion',b);await accountPrivacy();});}else{if(status.request?.state==='attention')notice('Для исполнения нужна отдельная проверка: общие ссылки или права изменились. Данные не удалены.');form('Подтвердить запрос удаления',[['password','Текущий пароль','password'],['confirmation','Введите DELETE для подтверждения','text']],'Запросить удаление',async b=>{await api('deletion',b);await accountPrivacy();});}}
async function staffUsers(){heading('Пользователи','Поиск только по ID или почте. Личные записи не доступны.');form('Поиск',[['search','ID или почта','text']],'Найти',async b=>{const result=await api('users?search='+encodeURIComponent(b.search));const list=el('div',undefined,'grid');for(const user of result.users){const card=panel(user.email,user.verified?'Почта подтверждена':'Почта не подтверждена');action('Открыть аккаунт',()=>staffUser(user.id),card);list.append(card);}app.append(list);});}
function selectField(form,name,label,choices){
  const caption=el('label',label);caption.htmlFor='select-'+name;
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
    selectField(f,'tier','Уровень',[['Plus','Plus'],['Premium','Premium']]);
    selectField(f,'source','Основание',[['manual','Ручная выдача'],['promo','Подарок / тест']]);
    selectField(f,'duration','Срок доступа',[['30','30 дней'],['90','90 дней'],['365','1 год'],['unlimited','Без ограничения срока']]);
    notice('Это ручная выдача доступа. Платёж и магазинная подписка не создаются.');
  }
  if(session.permissions.includes('users.moderate')){
    const services=[['account','Весь аккаунт'],['family_write','Изменения в семье'],['premium','Премиальные сервисы'],['support_write','Новые сообщения поддержки']];
    for(const [service,until]of Object.entries(ent.holds)){
      const name=services.find(row=>row[0]===service)?.[1]||service;
      const card=panel('Ограничение: '+name,'До '+accessUntil(until));app.append(card);
      action('Снять ограничение',async()=>{
        heading('Снять ограничение: '+name,'Снятие не удалит историю и другие ограничения.');
        form('Подтверждение',[['reason','Причина снятия','text']],'Подтвердить снятие',async b=>{
          await api('moderate',{user_id:id,service,until_at:0,reason:b.reason});await staffUser(id);
        });action('Отменить',async()=>staffUser(id));
      },card);
    }
    const f=form('Временное ограничение',[['reason','Обязательная причина','text']],'Ограничить на 24 часа',async b=>{
      await api('moderate',{user_id:id,service:f.elements.service.value,until_at:Math.floor(Date.now()/1000)+86400,reason:b.reason});await staffUser(id);
    });selectField(f,'service','Ограничиваемый сервис',services);
  }
}

async function staffTeam(){const result=await api('staff');const session=await api('session');heading('Команда Control','Права ограничены ролью и проверяются сервером при каждом действии. Для каждого сотрудника обязателен MFA.');for(const member of result.staff){const card=panel(member.email,member.roles.join(' · '));card.append(el('span',member.active?'Доступ активен':'Доступ отозван','badge'));app.append(card);if(!member.roles.includes('owner')&&member.id!==session.staff_id)action('Изменить права',async()=>{heading(member.email);const f=form('Права сотрудника',[['reason','Обязательная причина','text']],'Сохранить и отозвать сессии',async b=>{await api('staff/update',{staff_id:member.id,roles:[f.elements.role.value],active:f.elements.active.checked,revision:member.revision,reason:b.reason});await staffTeam();});roleSelect(f,session.roles.includes('owner'));const l=el('label','Доступ активен');const checkbox=el('input');checkbox.type='checkbox';checkbox.name='active';checkbox.checked=!!member.active;l.append(checkbox);f.insertBefore(l,f.querySelector('button'));},card);}const f=form('Пригласить сотрудника',[['email','Почта получателя','email'],['reason','Причина приглашения','text']],'Создать приглашение',async b=>{const result=await api('staff/invite',{email:b.email,roles:[f.elements.role.value],reason:b.reason});heading('Приглашение создано','Передайте код только выбранному получателю по защищённому каналу. Он должен войти в свой подтверждённый аккаунт и настроить MFA. Срок — 24 часа.');const code=el('textarea');code.readOnly=true;code.value=result.invitation;code.setAttribute('aria-label','Одноразовое приглашение');app.append(code);});roleSelect(f,session.roles.includes('owner'));}
function roleSelect(form,owner){const label=el('label','Роль');label.htmlFor='role-select';const select=el('select');select.name='role';select.id='role-select';const roles={support:'Поддержка',moderator:'Модератор',billing_manager:'Управление доступом',auditor:'Аудитор',admin:'Администратор'};for(const [value,title]of Object.entries(roles)){if(value==='admin'&&!owner)continue;const option=el('option',title);option.value=value;select.append(option);}form.insertBefore(label,form.querySelector('button'));form.insertBefore(select,form.querySelector('button'));}
async function staffFlags(){const flags=await api('flags');heading('Настройки интерфейса','Только предусмотренные UI-флаги. Защиту, MFA и проверку TLS здесь отключить нельзя.');for(const [name,value]of Object.entries(flags))app.append(panel(name,(value.enabled?'Включён':'Выключен')+' · охват '+value.rollout+'% · версия '+value.revision));const f=form('Предварительный просмотр',[['rollout','Охват: 0–100%','number'],['reason','Причина изменения','text']],'Показать изменения',async b=>{const name=f.elements.flag.value;const prior=flags[name]||{enabled:false,rollout:0,revision:0};const proposal=await api('flags/preview',{name,enabled:f.elements.enabled.checked,rollout:Number(b.rollout),revision:prior.revision,reason:b.reason});heading('Проверьте изменение');app.append(panel(name,'Было: '+(prior.enabled?'включён':'выключен')+', '+prior.rollout+'%. Будет: '+(proposal.preview.enabled?'включён':'выключен')+', '+proposal.preview.rollout+'%.'));notice('Изменение затронет соответствующий процент аккаунтов. Предложение действует 10 минут.');action('Подтвердить применение',async()=>{await api('flags/commit',{proposal_id:proposal.proposal_id,digest:proposal.digest});await staffFlags();});action('Отменить',staffFlags);});const select=el('select');select.name='flag';select.setAttribute('aria-label','Настройка');for(const [name,title]of [['compact_onboarding','Компактное знакомство'],['chart_styles','Варианты диаграмм'],['support_entry','Вход в поддержку']]){const option=el('option',title);option.value=name;select.append(option);}f.prepend(select);const label=el('label','Включить');const enabled=el('input');enabled.name='enabled';enabled.type='checkbox';label.append(enabled);f.insertBefore(label,f.querySelector('button'));f.elements.rollout.min='0';f.elements.rollout.max='100';f.elements.rollout.value='0';}

async function customerMfa(){const status=await api('mfa');heading('Двухфакторная защита',status.enabled?'Включена. Для отключения нужны пароль и второй фактор.':'Добавьте второй фактор к паролю аккаунта. Восстановление почты не отключает эту защиту.');if(status.enabled){form('Отключить защиту',[['password','Текущий пароль','password'],['code','Код аутентификатора или восстановления','text']],'Отключить и выйти',async b=>{await api('mfa/disable',b);login();});}else{form('Подключить аутентификатор',[['password','Текущий пароль','password']],'Продолжить',async b=>{const enrollment=await api('mfa/begin',b);heading('Добавьте ключ в аутентификатор','Сохраните ключ в своём приложении-аутентификаторе. Не передавайте его поддержке.');const secret=el('textarea');secret.readOnly=true;secret.value=enrollment.totp_secret;secret.setAttribute('aria-label','Секрет настройки MFA');app.append(secret);form('Подтвердить второй фактор',[['code','Текущий шестизначный код','text']],'Включить защиту',async value=>{const result=await api('mfa/enable',{password:b.password,enrollment:enrollment.enrollment,code:value.code});heading('Сохраните коды восстановления','Каждый код действует один раз вместе с паролем. Храните их офлайн. Все прежние сессии отозваны. После сохранения войдите с новым кодом аутентификатора.');const codes=el('textarea');codes.readOnly=true;codes.value=result.recovery_codes.join('\n');codes.setAttribute('aria-label','Одноразовые коды восстановления');app.append(codes);action('Коды сохранены. Вернуться ко входу',async()=>login());});});}}

function metricCard(key,value){const labels={accounts:'Аккаунты',users:'Аккаунты',new_24h:'Новые за сутки',active_24h:'Активные за сутки',mail_pending:'Очередь писем',support_pending:'Обращения',load_1m:'Нагрузка CPU',disk_free_bytes:'Свободное место',api_latency_ms:'Задержка API',sync_errors:'Ошибки синхронизации',backup_last_success:'Резервная копия'};let text='Нет измерений';if(value!==null){if(key==='disk_free_bytes')text=(value/1073741824).toLocaleString('ru-RU',{maximumFractionDigits:1})+' ГБ';else if(key==='backup_last_success')text=new Date(value*1000).toLocaleString();else text=value.toLocaleString('ru-RU',{maximumFractionDigits:key==='load_1m'?2:0})+(key==='api_latency_ms'?' мс':'');}return add(el('section',undefined,'card metric-card'),el('h2',labels[key]||key),el('div',text,value===null?'metric-unavailable':'metric-value'));}
function makeControlNavigation(session,container){container.replaceChildren();const select=el('select');select.setAttribute('aria-label','Раздел Control');const routes=[['dashboard.read','Обзор','dashboard'],['users.read','Пользователи','users'],['applications.manage','Заявки на тест','applications'],['staff.manage','Команда','staff'],['support.read','Поддержка','support'],['audit.read','Аудит','audit'],['flags.manage','Настройки интерфейса','flags']];for(const [permission,title,path]of routes)if(session.permissions.includes(permission)){const option=el('option',title);option.value=path;select.append(option);}if(!session.permissions.includes('dashboard.read')){const choose=el('option','Выберите раздел');choose.value='';choose.disabled=true;choose.selected=true;select.prepend(choose);}container.append(select);select.addEventListener('change',async()=>{try{const path=select.value;if(path==='dashboard'){await dashboard();return;}if(path==='users'){await staffUsers();return;}if(path==='applications'){await staffApplications();return;}if(path==='staff'){await staffTeam();return;}if(path==='support'){await support();return;}if(path==='flags'){await staffFlags();return;}heading('Журнал аудита');const result=await api('audit');for(const event of result.events){const card=panel(event.action,new Date(event.created_at*1000).toLocaleString());card.append(el('p',event.reason));const details=el('details');details.append(el('summary','Изменения'));details.append(el('pre',JSON.stringify({before:JSON.parse(event.before_value),after:JSON.parse(event.after_value)},null,2)));card.append(details);app.append(card);}}catch(e){notice(e.message);}});action('Выйти',async()=>{await api('logout',{});csrf='';login();},container);return container;}


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
 const hero = el('section', undefined, 'product-hero');
 const copy = el('div', undefined, 'hero-copy');
 const title = add(el('h1'), el('span', 'Уладим день.'), ' ', el('span', 'Освободим голову.'));
 add(copy, title, el('p', 'Задачи, календарь, заметки и финансы для себя и семьи.', 'hero-description'));
 const actions = el('div', undefined, 'hero-actions');
 add(actions, startLink(config), link('Возможности', '/docs', true));
 copy.append(actions);
 if (!config.registration_open) copy.append(el('p', 'Регистрация по приглашениям.', 'hero-caption'));
 app.append(add(hero, copy, todayPreview()));

 const features = add(el('section', undefined, 'product-features'), el('h2', 'Что можно делать в ULADIM'));
 const featureGrid = el('div', undefined, 'home-feature-grid');
 const capabilities = [
  ['calendar', 'Дела и календарь', 'Планируйте день, ведите задачи и не пропускайте важные события.'],
  ['notes', 'Заметки', 'Храните идеи, планы и важную информацию в одном месте.'],
  ['money', 'Финансы', 'Учитывайте доходы и расходы, ведите счета и бюджеты. Суммы видны отдельно по валютам.'],
  ['account', 'Семейное пространство', 'Планируйте дела вместе с близкими и выбирайте, какими записями поделиться.']
 ];
 for (const [icon, name, description] of capabilities) {
  const text = add(el('div'), el('h3', name), el('p', description));
  featureGrid.append(add(el('div', undefined, 'feature-row'), homeIcon(icon), text));
 }
 app.append(add(features, featureGrid));
 const platforms=el('section',undefined,'product-platforms');
 add(platforms,el('h2','ULADIM на ваших устройствах'),applicationCards(false));
 app.append(platforms);
 await planComparison(app);
 const faq=el('section',undefined,'product-faq');faq.append(el('h2','Частые вопросы'));
 for(const [question,answer]of [['Можно пользоваться без оплаты?','Да. Free доступен без покупки. Реальные платежи пока не подключены; Plus и Premium не продаются.'],['Нужен ли интернет?','Веб-версия работает прежде всего онлайн. В браузере кешируется интерфейс, а личные записи не сохраняются для полноценной работы без сети. У Android есть отдельное зашифрованное локальное хранилище.'],['Один ли аккаунт в вебе и Android?','Да. Используйте одинаковую почту. Передача записей зависит от выбранного пространства и его прав; сама авторизация не отправляет все локальные записи Android автоматически.'],['Что делать с прежним приглашением?','Откройте создание аккаунта. При открытой регистрации приглашение не требуется. Прежняя заявка сохранена: её статус и отмена доступны по ссылке «Прежние заявки».']]){const d=el('details');add(d,el('summary',question),el('p',answer));faq.append(d);}app.append(faq);
 const help=el('div',undefined,'hero-actions');add(help,link('Открыть ULADIM','/app'),link('Поддержка','/support',true),link('Прежние заявки','/early-access',true));app.append(help);
}
function applicationCards(full) {
 const grid=el('div',undefined,'application-grid');
 const web=panel('Веб-приложение','Откройте ULADIM в браузере или добавьте его на домашний экран телефона или планшета.');
 add(web,link('Открыть веб-приложение','/app'),link('Как установить',full?'#installation':'/download#installation',true));
 const android=panel('Android','Отдельное приложение для Android. Для новой сборки пока нет подтверждённой ссылки на скачивание.');
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
 const data=await api('plans');const section=el('section',undefined,'plan-comparison');add(section,el('h2','Три тарифа. Понятные условия.'),el('p','Free — без оплаты. Продажи Plus и Premium пока не подключены. Сейчас сервер предоставляет перечисленные возможности во всех трёх уровнях; будущие цены и различия ещё не утверждены.'));
 const scroll=el('div',undefined,'table-scroll');scroll.tabIndex=0;scroll.setAttribute('role','region');scroll.setAttribute('aria-label','Сравнение тарифов');const table=el('table');const head=el('thead');const row=el('tr');for(const label of ['Возможность','Free','Plus','Premium']){const th=el('th',label);th.scope='col';row.append(th);}head.append(row);table.append(head);const body=el('tbody');
 const labels={personal_core:'Задачи, заметки и финансы',family_sync:'Семейная синхронизация',custom_charts:'Настройка диаграмм',extended_personalization:'Темы и палитры'};
 for(const [key,label]of Object.entries(labels)){const row=el('tr');const th=el('th',label);th.scope='row';row.append(th);for(const tier of ['Free','Plus','Premium'])row.append(el('td',data.tiers[tier].features.includes(key)?'Доступно':'Не включено'));body.append(row);}table.append(body);scroll.append(table);section.append(scroll);target.append(section);
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

// Factual closed-test notices, reviewed against server code; operator/retention
// details must be supplied before these become final public legal documents.
function legalPage(path){
 const privacy=path==='/privacy';heading(privacy?'Конфиденциальность':'Условия использования','Предварительная редакция от 10 ноября 2026 года · закрытый тест');
 const sections=privacy?[
 ['Какие данные обрабатываются','Для аккаунта: email, хеш пароля при входе по паролю, подтверждение почты, устройства и серверные сессии. Если вы подключаете Google, сервер хранит связь аккаунта с идентификатором Google. В браузер не передаётся секрет OAuth.'],
 ['Ваши записи и семейные пространства','На сервер поступают записи, которые вы создаёте в вебе или явно синхронизируете из Android: задачи, заметки, события, счета, операции, переводы и бюджеты. Общий доступ зависит от пространства, видимости записи и прав участника, которые проверяет сервер. Сам вход не загружает на сервер все локальные записи Android.'],
 ['Что хранится в браузере','Для входа используется защищённый HttpOnly cookie сессии. В локальных настройках сохраняются язык, тема, палитра и вид диаграммы. Service Worker кеширует только файлы интерфейса из разрешённого списка. Записи, пароли и токены не сохраняются веб-клиентом в localStorage или CacheStorage. Открытые данные остаются в памяти страницы до закрытия или выхода.'],
 ['Импорт и поддержка','Файл выписки разбирается в браузере. После вашего подтверждения выбранные операции передаются на сервер; сам исходный файл не загружается этим инструментом. Сообщения, отправленные вами в поддержку, сохраняются и доступны уполномоченным сотрудникам. Не включайте пароли, коды и банковские документы в обращения.'],
 ['Инфраструктура и внешние сервисы','В текущей конфигурации предусмотрены PostgreSQL на Hostinger и Resend для служебных писем. Google участвует только при выбранном входе или подключении Google. Окончательные сведения о регионе хранения, трансграничной передаче и договорных основаниях ещё подлежат подтверждению оператором.'],
 ['Управление данными','В профиле можно управлять устройствами, доступными способами входа и запросом удаления аккаунта. Запрос удаления можно отменить в течение 24 часов. Для владельца семьи предусмотрена предварительная передача владения с подтверждением второго родителя. Удаление облачного аккаунта и локальных данных Android — разные действия.'],
 ['Что нужно уточнить до публичного запуска','Юридическое имя и контакты оператора, основания и сроки обработки, сроки очистки резервных копий, порядок запросов на доступ и исправление данных, правила для несовершеннолетних. До подтверждения этих сведений документ остаётся предварительным.']
 ]:[
 ['Статус продукта','ULADIM проходит закрытое тестирование. Доступ выдаётся по действующим серверным правилам. Этот документ описывает текущую работу продукта и ещё не является окончательной публичной офертой.'],
 ['Аккаунт и доступ','Веб и Android используют одну серверную систему аккаунтов. Доступ к личным и общим данным зависит от выбранного пространства и серверных разрешений. Берегите средства входа и отзывайте доступ потерянных устройств через профиль.'],
 ['Данные и доступность','Веб-клиенту необходимо соединение с сервером для сохранения и синхронизации. Ошибка соединения не всегда означает, что сервер не получил изменение; используйте повтор запроса в том же диалоге. Не используйте тестовый сервис как единственное место хранения незаменимых данных.'],
 ['Финансы','Финансовые записи предназначены для учёта. Суммы разных валют показываются отдельно без выдуманного обменного курса. Ввод перевода в учёте не осуществляет банковский перевод и не даёт доступ к вашему банку.'],
 ['Тарифы и покупки','Free, Plus и Premium определяются единым серверным каталогом. Реальные платежи не подключены. Отображение уровня доступа не означает покупку подписки или согласие на автоматические списания. Цены и окончательные условия платных услуг не утверждены.'],
 ['Семья и поддержка','Предоставляйте доступ к общим записям осознанно. Обращение в поддержку можно создать в профиле; не передавайте в нём средства входа и чувствительные документы. Правила для несовершеннолетних и законного представительства требуют отдельного утверждения оператором.'],
 ['Перед публичным выпуском','Необходимо утвердить сведения оператора, применимые условия, порядок прекращения доступа, разрешения споров и обращения с данными. Эти вопросы остаются открытыми; текущая редакция не заявляет их юридическую завершённость.']
 ];
 for(const [title,body]of sections)app.append(panel(title,body));
 app.append(link('Поддержка','/support',true),link(privacy?'Условия использования':'Конфиденциальность',privacy?'/terms':'/privacy',true));
}

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
