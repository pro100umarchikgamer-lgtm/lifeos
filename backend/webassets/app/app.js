'use strict';
const root=document.querySelector('#root'),alerts=document.querySelector('#alerts');
const state={session:null,csrf:'',spaces:[],space:null,roster:null,records:[],financeFilters:{},taskQuery:'',taskStatus:'all',calendarDay:localDate(),syncSpace:null,syncCursor:0,syncEpoch:'',tab:'today',lang:'ru',theme:'system',palette:'forest',chart:'bar',generation:0,busy:false,googleEnabled:false};
let packs={},alertTimer,navObserver,privateEpoch=0;
const pendingDeletes=new Map();
try{const saved=JSON.parse(localStorage.getItem('uladim-interface')||'{}');for(const key of ['lang','theme','palette','chart'])if(typeof saved[key]==='string')state[key]=saved[key];}catch{}
// Persist only interface preferences. Accounts, spaces, records and tokens stay in memory.
function preferences(){try{localStorage.setItem('uladim-interface',JSON.stringify({lang:state.lang,theme:state.theme,palette:state.palette,chart:state.chart}));}catch{}applyTheme();}
function applyTheme(){document.body.dataset.design=new URLSearchParams(location.search).get('design')==='legacy'?'':'clarity';document.body.dataset.theme=state.theme;document.body.dataset.palette=state.palette;document.documentElement.lang=state.lang;}

const WEB_COPY={
 ru:{web_calendar:'Календарь',family_kind_event:'Событие',web_upcoming:'Ближайшие 7 дней',web_no_events:'Событий пока нет. Добавьте время для важного.',web_all_tasks:'Все задачи',web_task_search:'Поиск задач',web_task_status:'Статус задачи',web_all:'Все',web_no_results:'Ничего не найдено',web_event_start:'Начало события',web_timezone:'Часовой пояс IANA или device',web_all_day:'Весь день',web_repeat:'Повторение',web_interval:'Интервал повторения',web_until:'Повторять до',web_repeat_none:'Не повторять',web_repeat_daily:'Ежедневно',web_repeat_weekly:'Еженедельно',web_repeat_monthly:'Ежемесячно',web_repeat_yearly:'Ежегодно',web_deleted_pending:'Запись будет удалена',web_delete_failed:'Удаление не подтверждено. Обновите данные перед повтором.',web_previous:'Предыдущий месяц',web_next:'Следующий месяц',web_month:'Месяц',web_agenda:'Повестка',web_partial_short:'частичный перевод',web_locale_coverage:'Новые экраны переведены на русский, английский и два варианта узбекского. Для остальных языков новые подписи показаны на английском.',web_conflict:'Запись изменена на другом устройстве. Скопируйте свои правки и загрузите серверную версию.',web_uncertain:'Сервер мог сохранить запись. Повторите запрос этой кнопкой — повтор не создаст копию.',web_server_error:'Сервис временно недоступен. Попробуйте позже.',web_view_changed:'Пространство или сессия изменились. Откройте запись заново.',web_currency_mismatch:'Валюта должна совпадать со счётом. При переводе в одной валюте суммы должны быть одинаковыми.',web_transfer_accounts:'Для перевода нужны два разных счёта.',web_install_button:'Установить ULADIM',web_loading:'Загрузка пространства…',web_quick_task:'Что нужно сделать?',web_add_task:'Добавить задачу',web_online_status:'Синхронизация через ваш аккаунт',web_day:'Выбранный день',web_cancel:'Отменить'},
 en:{web_calendar:'Calendar',family_kind_event:'Event',web_upcoming:'Next 7 days',web_no_events:'No events yet. Make time for what matters.',web_all_tasks:'All tasks',web_task_search:'Search tasks',web_task_status:'Task status',web_all:'All',web_no_results:'No results',web_event_start:'Event start',web_timezone:'IANA timezone or device',web_all_day:'All day',web_repeat:'Repeat',web_interval:'Repeat interval',web_until:'Repeat until',web_repeat_none:'Never',web_repeat_daily:'Daily',web_repeat_weekly:'Weekly',web_repeat_monthly:'Monthly',web_repeat_yearly:'Yearly',web_deleted_pending:'Record will be deleted',web_delete_failed:'Deletion not confirmed. Refresh before retrying.',web_previous:'Previous month',web_next:'Next month',web_month:'Month',web_agenda:'Agenda',web_partial_short:'partial translation',web_locale_coverage:'New screens are translated into Russian, English and both Uzbek scripts. Other languages use English for new labels.',web_conflict:'This record changed on another device. Copy your edits, then load the server version.',web_uncertain:'The server may have saved this record. Retry with this button; it reuses the operation to avoid duplicates.',web_server_error:'Service temporarily unavailable. Try again later.',web_view_changed:'Workspace or session changed. Reopen the record.',web_currency_mismatch:'Currency must match the account. Same-currency transfers must have equal amounts.',web_transfer_accounts:'Transfers require two different accounts.',web_install_button:'Install ULADIM',web_loading:'Loading workspace…',web_quick_task:'What needs to be done?',web_add_task:'Add task',web_online_status:'Synced through your account',web_day:'Selected day',web_cancel:'Undo'},
 'uz-Latn':{web_calendar:'Taqvim',family_kind_event:'Tadbir',web_upcoming:'Keyingi 7 kun',web_no_events:'Hozircha tadbirlar yo‘q. Muhim ishlar uchun vaqt ajrating.',web_all_tasks:'Barcha vazifalar',web_task_search:'Vazifalarni qidirish',web_task_status:'Vazifa holati',web_all:'Barchasi',web_no_results:'Hech narsa topilmadi',web_event_start:'Tadbir boshlanishi',web_timezone:'IANA vaqt mintaqasi yoki device',web_all_day:'Kun bo‘yi',web_repeat:'Takrorlash',web_interval:'Takrorlash oralig‘i',web_until:'Shu sanagacha takrorlash',web_repeat_none:'Takrorlanmasin',web_repeat_daily:'Har kuni',web_repeat_weekly:'Har hafta',web_repeat_monthly:'Har oy',web_repeat_yearly:'Har yil',web_deleted_pending:'Yozuv o‘chiriladi',web_delete_failed:'O‘chirish tasdiqlanmadi. Qayta urinishdan oldin yangilang.',web_previous:'Oldingi oy',web_next:'Keyingi oy',web_month:'Oy',web_agenda:'Kun tartibi',web_partial_short:'qisman tarjima',web_locale_coverage:'Yangi ekranlar rus, ingliz va o‘zbek tilining ikkala yozuvida tarjima qilingan. Qolgan tillarda yangi yozuvlar inglizcha.',web_conflict:'Yozuv boshqa qurilmada o‘zgargan. Tahrirlaringizni nusxalang va server nusxasini yuklang.',web_uncertain:'Server yozuvni saqlagan bo‘lishi mumkin. Shu tugma bilan takrorlang — nusxa yaratilmaydi.',web_server_error:'Xizmat vaqtincha mavjud emas. Keyinroq urinib ko‘ring.',web_view_changed:'Makon yoki seans o‘zgargan. Yozuvni qayta oching.',web_currency_mismatch:'Valyuta hisob bilan mos bo‘lsin. Bir xil valyutadagi o‘tkazma summalari teng bo‘lishi kerak.',web_transfer_accounts:'O‘tkazma uchun ikki xil hisob kerak.',web_install_button:'ULADIM o‘rnatish',web_loading:'Makon yuklanmoqda…',web_quick_task:'Nima qilish kerak?',web_add_task:'Vazifa qo‘shish',web_online_status:'Hisobingiz orqali sinxronlanadi',web_day:'Tanlangan kun',web_cancel:'Bekor qilish'},
 'uz-Cyrl':{web_calendar:'Тақвим',family_kind_event:'Тадбир',web_upcoming:'Кейинги 7 кун',web_no_events:'Ҳозирча тадбирлар йўқ. Муҳим ишлар учун вақт ажратинг.',web_all_tasks:'Барча вазифалар',web_task_search:'Вазифаларни қидириш',web_task_status:'Вазифа ҳолати',web_all:'Барчаси',web_no_results:'Ҳеч нарса топилмади',web_event_start:'Тадбир бошланиши',web_timezone:'IANA вақт минтақаси ёки device',web_all_day:'Кун бўйи',web_repeat:'Такрорлаш',web_interval:'Такрорлаш оралиғи',web_until:'Шу санагача такрорлаш',web_repeat_none:'Такрорланмасин',web_repeat_daily:'Ҳар куни',web_repeat_weekly:'Ҳар ҳафта',web_repeat_monthly:'Ҳар ой',web_repeat_yearly:'Ҳар йил',web_deleted_pending:'Ёзув ўчирилади',web_delete_failed:'Ўчириш тасдиқланмади. Қайта уринишдан олдин янгиланг.',web_previous:'Олдинги ой',web_next:'Кейинги ой',web_month:'Ой',web_agenda:'Кун тартиби',web_partial_short:'қисман таржима',web_locale_coverage:'Янги экранлар рус, инглиз ва ўзбек тилининг иккала ёзувида таржима қилинган. Қолган тилларда янги ёзувлар инглизча.',web_conflict:'Ёзув бошқа қурилмада ўзгарган. Таҳрирларингизни нусхаланг ва сервер нусхасини юкланг.',web_uncertain:'Сервер ёзувни сақлаган бўлиши мумкин. Шу тугма билан такрорланг — нусха яратилмайди.',web_server_error:'Хизмат вақтинча мавжуд эмас. Кейинроқ уриниб кўринг.',web_view_changed:'Макон ёки сеанс ўзгарган. Ёзувни қайта очинг.',web_currency_mismatch:'Валюта ҳисоб билан мос бўлсин. Бир хил валютадаги ўтказма суммалари тенг бўлиши керак.',web_transfer_accounts:'Ўтказма учун икки хил ҳисоб керак.',web_install_button:'ULADIM ўрнатиш',web_loading:'Макон юкланмоқда…',web_quick_task:'Нима қилиш керак?',web_add_task:'Вазифа қўшиш',web_online_status:'Ҳисобингиз орқали синхронланади',web_day:'Танланган кун',web_cancel:'Бекор қилиш'}
};
let deferredInstall=null;
window.addEventListener('beforeinstallprompt',e=>{e.preventDefault();deferredInstall=e;});
function dateString(d){return [d.getFullYear(),String(d.getMonth()+1).padStart(2,'0'),String(d.getDate()).padStart(2,'0')].join('-');}
function eventRow(o){const row=E('div',undefined,'row event-row'),caption=E('div',undefined,'text');append(caption,E('h3',o.record.data.title),E('p',o.day+' · '+(o.allDay?t('web_all_day'):o.time)+' · '+o.zone,'small'));append(row,caption,iconButton('more',t('edit')+' · '+o.record.data.title,()=>editRecord('event',o.record)));return row;}
function calendar(m){
 title(m,'web_calendar',()=>editRecord('event'));
 const date=new Date(state.calendarDay+'T12:00:00'),year=date.getFullYear(),month=date.getMonth(),from=new Date(year,month,1),to=new Date(year,month+1,1);
 const toolbar=E('div',undefined,'calendar-toolbar');
 const move=delta=>{state.calendarDay=dateString(new Date(year,month+delta,1));render();};
 append(toolbar,button('‹',()=>move(-1)),E('h2',date.toLocaleDateString(state.lang,{month:'long',year:'numeric'})),button('›',()=>move(1)));
 toolbar.firstChild.setAttribute('aria-label',t('web_previous'));toolbar.lastChild.setAttribute('aria-label',t('web_next'));m.append(toolbar);
 const layout=E('div',undefined,'calendar-layout'),monthGrid=card(),agenda=card(t('web_agenda'));append(layout,monthGrid,agenda);m.append(layout);
 const grid=E('div',undefined,'calendar-grid');monthGrid.append(grid);
 for(let i=0;i<7;i++)grid.append(E('span',new Date(2026,10,2+i).toLocaleDateString(state.lang,{weekday:'short'}),'weekday'));
 const all=ULADIMDomain.occurrences(records('event'),dateString(from),dateString(to)),byDay=new Map();for(const o of all){if(!byDay.has(o.day))byDay.set(o.day,[]);byDay.get(o.day).push(o);}
 for(let i=0;i<(from.getDay()+6)%7;i++)grid.append(E('span'));
 for(let day=1;day<to.getDate()+32;day++){const d=new Date(year,month,day);if(d.getMonth()!==month)break;const key=dateString(d),items=byDay.get(key)||[],b=button(String(day),()=>{state.calendarDay=key;render();},'calendar-date');b.setAttribute('aria-label',d.toLocaleDateString(state.lang,{day:'numeric',month:'long'})+(items.length?' · '+items.map(o=>o.record.data.title).join(', '):''));b.setAttribute('aria-pressed',String(key===state.calendarDay));if(key===localDate())b.classList.add('is-today');if(items.length)b.append(E('span',String(items.length),'event-count'));grid.append(b);}
 const picker=input(agenda,'calendar-day',t('web_day'),'date',state.calendarDay);picker.addEventListener('change',()=>{if(picker.value){state.calendarDay=picker.value;render();}});
 const selected=byDay.get(state.calendarDay)||[];for(const o of selected)agenda.append(eventRow(o));if(!selected.length)agenda.append(E('p',t('web_no_events'),'empty'));
}
function queueDelete(r,workspace){
 if(!navigator.onLine){toast(t('web_online'));return;}
 const epoch=privateEpoch,job={timer:null},notification=E('div',undefined,'toast undo');
 append(notification,E('span',t('web_deleted_pending')),button(t('web_cancel'),()=>{clearTimeout(job.timer);pendingDeletes.delete(r.id);notification.remove();render();}));alerts.append(notification);
 pendingDeletes.set(r.id,job);render();
 job.timer=setTimeout(async()=>{notification.remove();if(epoch!==privateEpoch){pendingDeletes.delete(r.id);return;}try{await saveOperation({id:crypto.randomUUID(),action:'record.delete',record_id:r.id,revision:r.revision},workspace);pendingDeletes.delete(r.id);await refresh();render();}catch(error){pendingDeletes.delete(r.id);if(state.session){render();report(error);toast(t('web_delete_failed'));}}},4000);
}

const t=k=>WEB_COPY[state.lang]?.[k]||WEB_COPY.en[k]||packs[state.lang]?.strings[k]||packs.ru?.strings[k]||k;
const E=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
function append(e,...children){e.append(...children);return e;}
function toast(message){const n=E('div',message,'toast');alerts.append(n);setTimeout(()=>n.remove(),4000);}
function errorText(error){if(['server_error','service_unavailable'].includes(error.code))return t('web_server_error');if(error.code==='view_changed')return t('web_view_changed');if(error.code==='currency_mismatch')return t('web_currency_mismatch');if(error.code==='mfa_invalid')return t('web_mfa_hint');if(error.code==='conflict'||error.code==='revision_conflict')return t('web_conflict');if(error.code==='offline')return error.uncertain?t('web_uncertain'):t('web_online');if(['invalid_amount','invalid_currency','amount_precision'].includes(error.code))return t(error.code);if(error.code?.startsWith('import_'))return t(error.code);return packs[state.lang]?.strings['family_error_'+error.code]||t('family_error_invalid_input');}
function report(error){if(['unauthorized','staff_unauthorized'].includes(error.code)){clearIdentity();login();}else if(['workspace_forbidden','service_restricted'].includes(error.code)){state.records=[];state.syncSpace=null;state.roster=null;state.space=null;render();}toast(errorText(error));}
async function call(path,body){
 const epoch=privateEpoch;
 let response;try{response=await fetch('/account/api/'+path,{method:body===undefined?'GET':'POST',credentials:'same-origin',cache:'no-store',headers:body===undefined?{}:{'Content-Type':'application/json','X-CSRF-Token':state.csrf},body:body===undefined?undefined:JSON.stringify(body)});}catch{throw Object.assign(new Error('offline'),{code:'offline',uncertain:body!==undefined});}
 let value;try{value=await response.json();}catch{throw Object.assign(new Error('server_error'),{code:'server_error',uncertain:body!==undefined});}
 if(epoch!==privateEpoch)throw Object.assign(new Error('view_changed'),{code:'view_changed',uncertain:body!==undefined});
 if(!response.ok)throw Object.assign(new Error(value.error),{code:value.error,uncertain:body!==undefined&&response.status>=500});return value;
}
function button(text,run,cls='ghost'){const b=E('button',text,cls);b.type='button';b.addEventListener('click',async()=>{b.disabled=true;try{await run();}catch(error){report(error);}finally{b.disabled=false;}});return b;}
const ICON_PATHS={calendar:['M8 2v4M16 2v4M3 10h18','M5 4h14a2 2 0 0 1 2 2v14H3V6a2 2 0 0 1 2-2','M8 14h2M14 14h2M8 18h2'],today:['M8 2v4M16 2v4M3 10h18','M5 4h14a2 2 0 0 1 2 2v14H3V6a2 2 0 0 1 2-2','m8 15 2 2 5-5'],tasks:['m3 6 1 1 2-2M10 6h11m-18 6 1 1 2-2M10 12h11m-18 6 1 1 2-2M10 18h11'],notes:['M5 3h14v18H5zM8 8h8M8 12h8M8 16h5'],money:['M4 20V10m6 10V4m6 16v-8m5 8H2'],account:['M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0M4 21v-2a8 8 0 0 1 16 0v2'],close:['m6 6 12 12M6 18 18 6'],more:['M5 12h.01M12 12h.01M19 12h.01'],add:['M12 5v14M5 12h14']};
function icon(name){const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');for(const [key,value]of Object.entries({viewBox:'0 0 24 24',fill:'none',stroke:'currentColor','stroke-width':'1.7','stroke-linecap':'round','stroke-linejoin':'round','aria-hidden':'true',focusable:'false',class:'ui-icon'}))svg.setAttribute(key,value);for(const path of ICON_PATHS[name]||[]){const node=document.createElementNS(svg.namespaceURI,'path');node.setAttribute('d',path);svg.append(node);}return svg;}
function iconButton(name,label,run){const b=button('',run,'icon');b.setAttribute('aria-label',label);b.title=label;b.append(icon(name));return b;}
function addButton(label,run){const b=button(label,run,'');b.prepend(icon('add'));return b;}
function anchor(text,path){const a=E('a',text,'button');a.href=path;return a;}
function input(container,name,label,type='text',value='',required=true){const id='input-'+name+'-'+crypto.randomUUID();const l=E('label',label);l.htmlFor=id;const n=E(type==='textarea'?'textarea':'input');n.name=name;n.id=id;if(type!=='textarea')n.type=type;if(type==='email')n.autocomplete='email';if(type==='password')n.autocomplete=['new','next','new-password'].includes(name)?'new-password':'current-password';if(type==='textarea')n.maxLength=20000;if(['name','label'].includes(name))n.maxLength=2000;if(name==='currency'){n.maxLength=3;n.autocapitalize='characters';}if(['amount','received'].includes(name))n.inputMode='decimal';if(name==='code'){n.autocomplete='one-time-code';n.spellcheck=false;}n.value=value??'';n.required=required&&type!=='checkbox';append(container,l,n);return n;}
function select(container,name,label,choices,value){const id='select-'+name+'-'+crypto.randomUUID();const l=E('label',label);l.htmlFor=id;const s=E('select');s.name=name;s.id=id;for(const [v,label]of choices){const o=E('option',label);o.value=v;s.append(o);}s.value=value;append(container,l,s);return s;}
function card(title,body){const c=E('section',undefined,'card');if(title)c.append(E('h2',title));if(body)c.append(E('p',body));return c;}
function form(container,title,build,submit,submitLabel=t('save')){const f=E('form');if(title)f.append(E('h2',title));const fields=E('fieldset');const values=build(fields)||{};f.append(fields);const status=E('p',undefined,'error');status.setAttribute('role','status');const b=E('button',submitLabel);b.type='submit';append(f,status,b);let pending=false;f.addEventListener('submit',async event=>{event.preventDefault();if(pending)return;pending=true;b.disabled=true;status.textContent='';try{await submit(values);status.textContent=t('account_done');}catch(error){status.textContent=errorText(error);if(error.uncertain){fields.disabled=true;b.textContent=t('retry');status.textContent=t('web_uncertain');}if(error.code==='unauthorized')report(error);}finally{b.disabled=false;pending=false;}});container.append(f);return f;}
function dialog(title,build){const d=E('dialog');d.dataset.workspace=state.space||'';const h=E('div',undefined,'dialog-head');const heading=E('h2',title);heading.id='dialog-'+crypto.randomUUID();d.setAttribute('aria-labelledby',heading.id);append(h,heading,iconButton('close',t('close'),()=>d.close()));d.append(h);build(d);document.body.append(d);d.addEventListener('close',()=>d.remove());d.showModal();return d;}
function replaceDialog(d,...nodes){
 const heading=nodes.find(n=>n.tagName==='H2')||E('h2','ULADIM');heading.id='dialog-'+crypto.randomUUID();
 const existing=nodes.find(n=>n.tagName==='BUTTON'&&n.textContent===t('close'));
 const close=existing||iconButton('close',t('close'),()=>d.close());
 if(existing){close.className='icon';close.setAttribute('aria-label',t('close'));close.replaceChildren(icon('close'));}
 const head=E('div',undefined,'dialog-head');append(head,heading,close);d.setAttribute('aria-labelledby',heading.id);
 d.replaceChildren(head,...nodes.filter(n=>n!==heading&&n!==existing));
}

function clearIdentity(){privateEpoch++;state.generation++;for(const job of pendingDeletes.values())clearTimeout(job.timer);pendingDeletes.clear();Object.assign(state,{session:null,csrf:'',space:null,spaces:[],roster:null,records:[],financeFilters:{},syncSpace:null,syncCursor:0,syncEpoch:'',tab:'today',busy:false});document.querySelectorAll('dialog').forEach(d=>{d.close();d.remove();});}
function money(value,currency){return ULADIMMoney.format(value,currency,state.lang);}
function minor(value,signed=false,currency='RUB'){return ULADIMMoney.parse(value,currency,signed);}
function decimalInput(value,currency){return ULADIMMoney.decimal(value,currency);}
function localDate(){const d=new Date();return [d.getFullYear(),String(d.getMonth()+1).padStart(2,'0'),String(d.getDate()).padStart(2,'0')].join('-');}
function currentSpace(){return state.spaces.find(s=>s.id===state.space);}
function records(kind){return state.records.filter(r=>!r.deleted&&!pendingDeletes.has(r.id)&&r.kind===kind);}
async function readSpace(){
 const generation=++state.generation,wid=state.space;if(!wid){state.records=[];state.syncSpace=null;state.roster=null;return;}
 const roster=await call('roster?workspace='+encodeURIComponent(wid));const same=state.syncSpace===wid;let cursor=same?state.syncCursor:0,epoch=same?state.syncEpoch:'',all=new Map(same?state.records.map(r=>[r.id,r]):[]);
 for(let pages=0;pages<10000;pages++){
  const page=await call('sync?workspace='+encodeURIComponent(wid)+'&cursor='+cursor+'&epoch='+encodeURIComponent(epoch));
  if(generation!==state.generation)return;
  if(page.reset)all.clear();for(const r of page.records){if(r.deleted)all.delete(r.id);else all.set(r.id,r);}if(page.more&&page.cursor===cursor&&!page.reset)throw {code:'invalid_sync_response'};cursor=page.cursor;epoch=page.epoch;if(!page.more){state.records=[...all.values()];state.roster=roster;state.syncSpace=wid;state.syncCursor=page.cursor;state.syncEpoch=page.epoch;return;}
 }throw {code:'invalid_sync_response'};
}
async function refresh(){if(state.busy)return;state.busy=true;try{const result=await call('spaces');state.spaces=result.spaces;if(!state.spaces.some(s=>s.id===state.space))state.space=state.spaces[0]?.id||null;await readSpace();}finally{state.busy=false;}}
async function start(){state.session=await call('session');state.csrf=state.session.csrf;await refresh();render();}
function login(){
 root.replaceChildren();const m=E('main',undefined,'login');const brand=E('a','ULADIM','brand');brand.href='/';append(m,brand,E('h1',t('family_login')));root.append(m);
 form(m,'',f=>({email:input(f,'email',t('family_email'),'email'),password:input(f,'password',t('web_password'),'password')}),async v=>{let r;try{r=await call('login',{email:v.email.value,password:v.password.value});}finally{v.password.value='';}if(r.mfa_required){mfaStep(r.challenge);return;}state.csrf=r.csrf;await start();},t('family_login'));
 if(state.googleEnabled)m.append(button(t('account_google_sign_in'),()=>beginGoogle()));
 const actions=E('div',undefined,'actions');append(actions,button(t('family_register'),signup),button(t('family_recovery'),recover));m.append(actions);language(m);
}
async function beginGoogle(invitation){
 const result=await call('google/start',invitation?{invitation}:{});
 location.assign(result.authorization_url);
}
async function googleReturn(){
 history.replaceState(null,'','/app');
 const result=await call('google/complete',{});
 if(result.error){login();const message=E('p',errorText({code:result.error}));message.setAttribute('role','alert');root.querySelector('main').append(message);return;}
 if(result.mfa_required){mfaStep(result.challenge);return;}
 await start();if(result.linked)toast(t('account_done'));
}
function mfaStep(challenge){
 root.replaceChildren();const m=E('main',undefined,'login');append(m,E('a','ULADIM','brand'),E('h1',t('account_mfa')),E('p',t('web_mfa_hint')));root.append(m);
 form(m,'',f=>({code:input(f,'code',t('family_code'))}),async v=>{let r;try{r=await call('login/mfa',{challenge,code:v.code.value.trim()});}catch(error){if(error.code==='invalid_credentials')error.code='mfa_invalid';throw error;}finally{v.code.value='';}challenge='';state.csrf=r.csrf;await start();},t('family_login'));
 m.append(button(t('cancel'),()=>{challenge='';login();}));m.querySelector('input').focus();
}

function language(container){const s=select(container,'language',t('language'),Object.entries(packs).map(([k,v])=>[k,v.name+(WEB_COPY[k]?'':' · '+t('web_partial_short'))]),state.lang);s.addEventListener('change',()=>{state.lang=s.value;preferences();if(state.session)render();else login();});}
function shell(){
 navObserver?.disconnect();root.replaceChildren();const header=E('header');const brand=E('a','ULADIM','brand');brand.href='/app';brand.append(E('small',t('ux3_settings_body')));header.append(brand);
 const spaces=select(E('div'),'workspace','',state.spaces.map(s=>[s.id,s.name]),state.space);spaces.setAttribute('aria-label',t('family_account'));spaces.className='workspace';spaces.addEventListener('change',async()=>{document.querySelectorAll('dialog').forEach(d=>d.close());state.space=spaces.value;state.records=[];state.roster=null;render();try{await readSpace();render();}catch(e){report(e);}});if(state.spaces.length)header.append(spaces);root.append(header);
 if(!navigator.onLine){const n=E('div',t('web_online'));n.id='network';root.append(n);}
 const m=E('main');m.id='content';root.append(m);const nav=E('nav',undefined,'nav');nav.setAttribute('aria-label','ULADIM');
 for(const [key,label]of [['today','today'],['tasks','widget_tasks'],['calendar','web_calendar'],['notes','widget_notes'],['money','finances'],['account','profile']]){const b=button('',()=>{state.tab=key;render();});const symbol=E('span',undefined,'symbol');symbol.append(icon(key));append(b,symbol,E('span',t(label)));if(state.tab===key)b.setAttribute('aria-current','page');nav.append(b);}root.append(nav);navObserver=new ResizeObserver(()=>{document.body.style.setProperty('--nav-height',nav.getBoundingClientRect().height+'px');document.body.style.setProperty('--app-header-height',header.getBoundingClientRect().height+'px');});navObserver.observe(nav);navObserver.observe(header);return m;
}
function title(m,label,add){const intro=E('div',undefined,'intro');const a=E('div');append(a,E('div',new Date().toLocaleDateString(state.lang,{day:'numeric',month:'long',weekday:'long'}),'eyebrow'),E('h1',t(label)));intro.append(a);if(add)intro.append(addButton(t('add'),add));m.append(intro);}
function render(){if(!state.session){login();return;}const m=shell();if(state.tab==='account'){account(m);return;}if(!state.space){title(m,'today');m.append(card(t('welcome_title'),t('web_onboarding')),addButton(t('web_personal_create'),()=>createSpace('personal')),button(t('family_create'),()=>createSpace('family')),button(t('family_accept'),acceptInvite));return;}
 if(state.tab==='today')today(m);else if(state.tab==='tasks')listTasks(m);else if(state.tab==='calendar')calendar(m);else if(state.tab==='notes')listNotes(m);else if(state.tab==='money')finance(m);
}
function today(m){
 title(m,'today',chooseAdd);
 const actions=E('div',undefined,'actions quick-actions');
 for(const kind of ['task','transaction','note','event'])actions.append(addButton(t('family_kind_'+kind),()=>editRecord(kind)));
 m.append(actions);
 const grid=E('div',undefined,'grid today-grid');m.append(grid);
 const tasks=records('task'),open=tasks.filter(r=>!r.data.completed),a=card(t('open_tasks'));
 a.classList.add('today-tasks');a.querySelector('h2').append(E('span',String(open.length),'task-count'));
 for(const r of open.slice(0,5))a.append(taskRow(r));
 if(!open.length)a.append(E('p',t('empty_tasks'),'empty'));
 a.append(button(t('web_all_tasks'),()=>{state.tab='tasks';render();}));grid.append(a);
 const agenda=card(t('web_upcoming'));agenda.classList.add('today-agenda');
 const end=new Date(localDate()+'T12:00:00');end.setDate(end.getDate()+7);
 const occurrences=ULADIMDomain.occurrences(records('event'),localDate(),dateString(end));
 for(const o of occurrences.slice(0,4))agenda.append(eventRow(o));
 if(!occurrences.length)agenda.append(E('p',t('web_no_events')));
 agenda.append(button(t('web_calendar'),()=>{state.tab='calendar';render();}));grid.append(agenda);
 const c=card(t('finances'));c.classList.add('wide','today-finance');summaries(c);grid.append(c);
 const budgets=records('budget');if(budgets.length){const b=card(t('family_kind_budget'));for(const r of budgets.slice(0,3)){const row=E('div',undefined,'row');append(row,E('span',r.data.name,'text'),E('strong',money(r.data.limit_minor,r.data.currency)));b.append(row);}b.append(button(t('finances'),()=>{state.tab='money';render();}));grid.append(b);}
 const notes=card(t('recent_notes'));notes.classList.add('today-notes');for(const r of records('note').slice(-2).reverse())notes.append(button(r.data.body.slice(0,100),()=>editRecord('note',r),'note-link'));if(!records('note').length)notes.append(E('p',t('empty_notes')));grid.append(notes);
 m.append(button(t('family_sync'),async()=>{await refresh();render();}));
}
function chooseAdd(){dialog(t('add'),d=>{for(const kind of ['task','event','note','transaction','account','budget','transfer'])d.append(button(t('family_kind_'+kind),()=>{d.close();editRecord(kind);}));});}
function taskRow(r){const row=E('div',undefined,'row');const check=E('input');check.type='checkbox';check.checked=!!r.data.completed;check.disabled=!r.editable;check.setAttribute('aria-label',r.data.title);check.addEventListener('change',async()=>{check.disabled=true;try{if(r.data.assignees.length){editRecord('task',r);return;}await saveOperation({id:crypto.randomUUID(),action:'record.put',record_id:r.id,revision:r.revision,kind:r.kind,visibility:r.visibility,audience:r.audience,data:{...r.data,completed:check.checked?1:0}});await refresh();render();}catch(e){check.checked=!!r.data.completed;report(e);}finally{check.disabled=!r.editable;}});append(row,check,E('span',r.data.title,'text'+(r.data.completed?' done':'')),iconButton('more',t('edit')+' · '+r.data.title,()=>editRecord('task',r)));return row;}
function listTasks(m){
 title(m,'widget_tasks',()=>editRecord('task'));
 const filters=E('div',undefined,'task-filters'),queryBox=E('div'),statusBox=E('div');append(filters,queryBox,statusBox);m.append(filters);
 const query=input(queryBox,'task-search',t('web_task_search'),'search',state.taskQuery,false);
 const status=select(statusBox,'task-status',t('web_task_status'),[['all',t('web_all')],['open',t('open_tasks')],['done',t('completed')]],state.taskStatus);
 const c=card();m.append(c);
 const draw=()=>{state.taskQuery=query.value;state.taskStatus=status.value;c.replaceChildren();const rows=ULADIMDomain.tasks(records('task'),query.value,status.value);for(const r of rows.sort((a,b)=>a.data.completed-b.data.completed))c.append(taskRow(r));if(!rows.length)c.append(E('p',t('web_no_results'),'empty'));};
 query.addEventListener('input',draw);status.addEventListener('change',draw);draw();
}
function listNotes(m){title(m,'widget_notes',()=>editRecord('note'));const search=input(m,'search',t('search'),'search','',false);const grid=E('div',undefined,'grid');m.append(grid);const draw=()=>{grid.replaceChildren();const rows=records('note').filter(r=>r.data.body.toLocaleLowerCase(state.lang).includes(search.value.toLocaleLowerCase(state.lang)));for(const r of rows){const c=card();c.append(E('h2',r.data.body.split('\n')[0].slice(0,100)),E('p',r.data.body.slice(0,280),'note note-preview'),button(t('edit'),()=>editRecord('note',r)));grid.append(c);}if(!rows.length)grid.append(E('p',t('empty_notes'),'empty'));};search.addEventListener('input',draw);draw();}
async function saveOperation(operation,workspace=state.space){const result=await call('sync',{workspace_id:workspace,operations:[operation]});const item=result.results[0];if(item.status!=='accepted')throw {code:item.status==='conflict'?'conflict':item.error};return item;}
function editRecord(kind,r=null){
 const workspace=state.space;const d=dialog(t('family_kind_'+kind),container=>{
 let operation=null;const fields={};
 form(container,'',f=>{
  const data=r?.data||{};const disabled=r&&!r.editable;
  if(['task','event','account','budget'].includes(kind))fields.name=input(f,'name',t(kind==='task'?'task_title':'name'),'text',data.title||data.name||'');
  if(kind==='event'){
   const schedule=data.schedule||{};
   fields.localStart=input(f,'localStart',t('web_event_start'),'datetime-local',schedule.localStart?.slice(0,16)||localDate()+'T09:00');
   fields.timezone=input(f,'timezone',t('web_timezone'),'text',schedule.timezone||Intl.DateTimeFormat().resolvedOptions().timeZone);
   fields.allDay=input(f,'allDay',t('web_all_day'),'checkbox');fields.allDay.checked=!!schedule.allDay;
   fields.repeat=select(f,'repeat',t('web_repeat'),['none','daily','weekly','monthly','yearly'].map(k=>[k,t('web_repeat_'+k)]),schedule.repeat||'none');
   fields.interval=input(f,'interval',t('web_interval'),'number',schedule.interval||1);fields.interval.min=1;fields.interval.max=365;fields.interval.step=1;
   fields.until=input(f,'until',t('web_until'),'date',schedule.until||'',false);
  }
  if(kind==='note')fields.body=input(f,'body',t('note_text'),'textarea',data.body||'');
  if(kind==='task'){
   fields.completed=input(f,'completed',t('completed'),'checkbox');fields.completed.checked=!!data.completed;fields.completed.disabled=!!data.assignees?.length;
   if(data.assignees?.length){f.append(E('p',t('family_review_pending')));for(const pid of data.assignees){const profile=state.roster.profiles.find(p=>p.id===pid);f.append(button(t('complete')+' · '+(profile?.name||pid),async()=>{await saveOperation({id:crypto.randomUUID(),action:'task.complete',record_id:r.id,revision:r.revision,profile_id:pid,completed:true});d.close();await refresh();render();}));}}
  }
  if(['account','transaction','budget'].includes(kind))fields.currency=input(f,'currency',t('currency'),'text',data.currency||'RUB');
  if(['account','transaction','budget','transfer'].includes(kind))fields.amount=input(f,'amount',t(kind==='account'?'opening_balance':'amount'),'text',decimalInput(data.opening_minor??data.amount_minor??data.limit_minor??data.sent_minor??0,data.currency||records('account').find(a=>a.id===data.from_id)?.data.currency||'RUB'));
  if(kind==='transaction'){
   fields.direction=select(f,'direction',t('family_kind_transaction'),[['expense',t('expense')],['income',t('income')]],data.kind||'expense');
   fields.date=input(f,'date',t('family_date'),'date',data.date||localDate());fields.label=input(f,'label',t('family_name'),'text',data.label||'',false);
   fields.account=select(f,'account',t('family_account_select'),[['',t('family_none')],...records('account').map(a=>[a.id,a.data.name+' · '+a.data.currency])],data.account_id||'');fields.account.addEventListener('change',()=>{const account=records('account').find(a=>a.id===fields.account.value);if(account)fields.currency.value=account.data.currency;});
  }
  if(kind==='budget'){fields.period=select(f,'period',t('family_period'),['week','month','year','custom'].map(k=>[k,t('family_'+k)]),data.period||'month');fields.start=input(f,'start',t('family_start'),'date',data.start_on||localDate());fields.end=input(f,'end',t('family_end'),'date',data.end_on||'',false);fields.rollover=select(f,'rollover',t('family_rollover'),['none','positive','negative','both'].map(k=>[k,t('family_roll_'+k)]),data.rollover||'none');}
  if(kind==='transfer'){if(records('account').length<2)f.append(E('p',t('web_transfer_accounts'),'error'));const accounts=records('account').map(a=>[a.id,a.data.name+' · '+a.data.currency]);fields.from=select(f,'from',t('family_from'),accounts,data.from_id||accounts[0]?.[0]);fields.to=select(f,'to',t('family_to'),accounts,data.to_id||accounts[1]?.[0]);fields.received=input(f,'received',t('received_amount'),'text',decimalInput(data.received_minor||0,records('account').find(a=>a.id===data.to_id)?.data.currency||'RUB'));fields.date=input(f,'date',t('family_date'),'date',data.date||localDate());}
  fields.visibility=select(f,'visibility',t('family_visibility'),[['private',t('family_private')],['shared',t('family_shared')]],r?.visibility||(currentSpace()?.role==='child'?'shared':'private'));
  if(disabled)f.disabled=true;return fields;
 },async v=>{
  if(workspace!==state.space)throw {code:'view_changed'};
  if(!operation){let data={...r?.data};
   if(kind==='note')data={body:v.body.value};
   if(kind==='event'){const schedule={localStart:v.localStart.value.length===16?v.localStart.value+':00':v.localStart.value,timezone:v.timezone.value.trim(),allDay:v.allDay.checked,repeat:v.repeat.value,interval:Number(v.interval.value),until:v.until.value||null};if(schedule.until&&schedule.until<schedule.localStart.slice(0,10))throw {code:'invalid_date'};try{ULADIMDomain.occurrences([{id:'validate',data:{schedule}}],schedule.localStart.slice(0,10),dateString(new Date(Date.parse(schedule.localStart+'Z')+172800000)));}catch{throw {code:'invalid_schedule'};}data={title:v.name.value,schedule};}
   if(kind==='task')data={title:v.name.value,completed:v.completed.checked?1:0,assignment:r?.data.assignment||'any',assignees:r?.data.assignees||[],review:r?.data.review||0};
   if(kind==='account')data={name:v.name.value,currency:v.currency.value.trim().toUpperCase(),opening_minor:minor(v.amount.value,true,v.currency.value)};
   if(kind==='transaction')data={kind:v.direction.value,amount_minor:minor(v.amount.value,false,v.currency?.value||records('account').find(a=>a.id===v.from?.value)?.data.currency||'RUB'),currency:v.currency.value.trim().toUpperCase(),date:v.date.value,label:v.label.value,account_id:v.account.value||null};
   if(kind==='budget')data={name:v.name.value,currency:v.currency.value.trim().toUpperCase(),limit_minor:minor(v.amount.value,false,v.currency?.value||records('account').find(a=>a.id===v.from?.value)?.data.currency||'RUB'),period:v.period.value,start_on:v.start.value,end_on:v.end.value||null,rollover:v.rollover.value,participants:r?.data.participants||[]};
   if(kind==='transfer')data={from_id:v.from.value,to_id:v.to.value,sent_minor:minor(v.amount.value,false,v.currency?.value||records('account').find(a=>a.id===v.from?.value)?.data.currency||'RUB'),received_minor:minor(v.received.value,false,records('account').find(a=>a.id===v.to.value)?.data.currency||'RUB'),date:v.date.value};
   ULADIMDomain.validateFinance(kind,data,records('account'));
   operation={id:crypto.randomUUID(),action:'record.put',record_id:r?.id||crypto.randomUUID(),revision:r?.revision||0,kind,visibility:v.visibility.value,audience:r?.audience||(currentSpace()?.role==='child'?[currentSpace().profile_id]:[]),data};
  }
  try{await saveOperation(operation,workspace);}catch(error){if(!error.uncertain)operation=null;throw error;}d.close();await refresh();render();
 });
 if(r)container.append(button(t('family_use_server'),async()=>{d.close();await refresh();render();}));
 if(r?.editable)container.append(button(t('delete'),()=>{d.close();queueDelete(r,workspace);},'danger'));
 });
}
function totals(currency){let income=0n,expense=0n;for(const r of records('transaction').filter(r=>r.data.currency===currency)){if(r.data.kind==='income')income+=BigInt(r.data.amount_minor);else expense+=BigInt(r.data.amount_minor);}return {income,expense};}
function summaries(container){const currencies=[...new Set([...records('transaction'),...records('account')].map(r=>r.data.currency))];if(!currencies.length){container.append(E('p',t('empty_money')));return;}for(const currency of currencies){const {income,expense}=totals(currency);const row=E('div',undefined,'row');append(row,E('strong',currency),E('span','+ '+money(income,currency),'income'),E('span','− '+money(expense,currency),'expense'));container.append(row);}container.append(E('p',t('web_totals'),'small'));}
function balance(a){let result=BigInt(a.data.opening_minor);for(const r of records('transaction').filter(r=>r.data.account_id===a.id))result+=(r.data.kind==='income'?1n:-1n)*BigInt(r.data.amount_minor);for(const r of records('transfer')){if(r.data.from_id===a.id)result-=BigInt(r.data.sent_minor);if(r.data.to_id===a.id)result+=BigInt(r.data.received_minor);}return result;}
function finance(m){
 title(m,'finances',chooseAdd);const toolbar=E('div',undefined,'finance-toolbar');toolbar.append(button(t('import_file'),importStatement));m.append(toolbar);
 const filters=E('section',undefined,'finance-filters');m.append(filters);
 const group=(name,label,type='search')=>{const wrap=E('div');filters.append(wrap);return input(wrap,name,label,type,state.financeFilters[name]||'',false);};
 const search=group('finance-search',t('search')),from=group('finance-from',t('web_period_start'),'date'),to=group('finance-to',t('web_period_end'),'date');
 const wrap=E('div');filters.append(wrap);const accountFilter=select(wrap,'finance-account',t('web_accounts'),[['',t('web_all_accounts')],...records('account').map(a=>[a.id,a.data.name+' · '+a.data.currency])],state.financeFilters.account||'');
 const grid=E('div',undefined,'grid finance-grid');m.append(grid);
 const rows=()=>records('transaction').filter(r=>(!accountFilter.value||r.data.account_id===accountFilter.value)&&(!from.value||r.data.date>=from.value)&&(!to.value||r.data.date<=to.value)&&(!search.value||(r.data.label+' '+r.data.date).toLocaleLowerCase(state.lang).includes(search.value.toLocaleLowerCase(state.lang))));
 const summary=card(t('feature_finance'));summary.classList.add('wide','finance-overview');grid.append(summary);
 const accounts=card(t('web_accounts'));accounts.classList.add('finance-accounts');grid.append(accounts);
 for(const a of records('account')){const row=E('div',undefined,'account-balance');append(row,E('span',a.data.name,'text'),E('strong',money(balance(a),a.data.currency)),iconButton('more',t('edit')+' · '+a.data.name,()=>editRecord('account',a)));accounts.append(row);}if(!records('account').length)accounts.append(E('p',t('empty_money')));accounts.append(addButton(t('family_kind_account'),()=>editRecord('account')));
 const chart=card(t('finances'));chart.classList.add('finance-analysis');grid.append(chart);const chartControls=E('div',undefined,'chart-controls');chart.append(chartControls);
 const currencies=[...new Set([...records('transaction'),...records('account')].map(r=>r.data.currency))];const currency=select(chartControls,'chart-currency',t('currency'),currencies.map(c=>[c,c]),currencies[0]);const mode=select(chartControls,'chart-mode',t('web_chart_type'),[['bar',t('web_bar')],['line',t('web_line')],['smooth',t('web_smooth')],['donut',t('web_donut')],['compact',t('web_compact')]],state.chart);
 const legend=E('div',undefined,'chart-legend');chart.append(legend);const canvas=E('canvas');canvas.width=720;canvas.height=320;canvas.setAttribute('role','img');chart.append(canvas);
 const budgets=card(t('family_kind_budget'));budgets.classList.add('wide','finance-budgets');grid.append(budgets);
 const budgetLabels=new Map();for(const r of records('budget')){const row=E('div',undefined,'budget-line'),text=E('div'),amount=E('p',money(r.data.limit_minor,r.data.currency),'small');append(text,E('h3',r.data.name),amount);budgetLabels.set(r.id,amount);append(row,text,iconButton('more',t('edit')+' · '+r.data.name,()=>editRecord('budget',r)));budgets.append(row);}
 if(budgetLabels.size){const epoch=privateEpoch;statementWorker({action:'budgets',at:localDate(),records:records('transaction'),budgets:records('budget')}).then(result=>{if(epoch!==privateEpoch||!m.isConnected)return;for(const r of records('budget'))budgetLabels.get(r.id).textContent=t('remaining')+': '+money(result.remaining[r.id],r.data.currency)+' · '+t('budget_limit')+': '+money(r.data.limit_minor,r.data.currency);}).catch(error=>{if(m.isConnected)budgets.append(E('p',errorText(error),'error'));});}
 budgets.append(addButton(t('family_kind_budget'),()=>editRecord('budget')));
 const ledger=card(t('family_kind_transaction'));ledger.classList.add('wide','ledger');grid.append(ledger);
 function draw(){
  state.financeFilters={'finance-search':search.value,'finance-from':from.value,'finance-to':to.value,account:accountFilter.value};const filtered=rows();summary.replaceChildren(E('h2',t('feature_finance')));
  for(const code of currencies){const values=financeTotals(filtered,code),row=E('div',undefined,'finance-total');append(row,E('span',code,'currency-code'),E('div',undefined,'income'),E('div',undefined,'expense'));row.children[1].append(E('span',t('income'),'small'),E('strong',money(values.income,code)));row.children[2].append(E('span',t('expense'),'small'),E('strong',money(values.expense,code)));summary.append(row);}if(!currencies.length)summary.append(E('p',t('empty_money')));summary.append(E('p',t('web_totals'),'small'));
  const values=financeTotals(filtered,currency.value);legend.replaceChildren();if(currency.value){legend.append(E('span',t('income')+' · '+money(values.income,currency.value),'income'),E('span',t('expense')+' · '+money(values.expense,currency.value),'expense'));}
  state.chart=mode.value;preferences();canvas.hidden=mode.value==='compact'||!currency.value;drawChart(canvas,currency.value,filtered);
  ledger.replaceChildren(E('h2',t('family_kind_transaction')));for(const r of filtered.sort((a,b)=>b.data.date.localeCompare(a.data.date))){const row=E('div',undefined,'row');const text=E('div',undefined,'text');append(text,E('h3',r.data.label||t(r.data.kind)),E('p',r.data.date+(r.data.account_id?' · '+(records('account').find(a=>a.id===r.data.account_id)?.data.name||''):''),'small'));append(row,text,E('strong',(r.data.kind==='expense'?'− ':'+ ')+money(r.data.amount_minor,r.data.currency),r.data.kind),iconButton('more',t('edit')+' · '+(r.data.label||t(r.data.kind)),()=>editRecord('transaction',r)));ledger.append(row);}if(!filtered.length)ledger.append(E('p',t('empty_money'),'empty'));
  for(const r of records('transfer').filter(r=>(!accountFilter.value||[r.data.from_id,r.data.to_id].includes(accountFilter.value))&&(!from.value||r.data.date>=from.value)&&(!to.value||r.data.date<=to.value)))ledger.append(button(t('family_kind_transfer')+' · '+r.data.date,()=>editRecord('transfer',r)));
 }
 for(const field of [search,from,to,accountFilter,currency,mode])field.addEventListener(field===search?'input':'change',draw);requestAnimationFrame(draw);
}
function financeTotals(rows,currency){let income=0n,expense=0n;for(const r of rows.filter(r=>r.data.currency===currency)){if(r.data.kind==='income')income+=BigInt(r.data.amount_minor);else expense+=BigInt(r.data.amount_minor);}return {income,expense};}
function drawChart(canvas,currency,rows=records('transaction')){
 const ctx=canvas.getContext('2d');ctx.clearRect(0,0,720,320);if(!currency)return;
 const {income,expense}=financeTotals(rows,currency),style=getComputedStyle(document.body),colors=[style.getPropertyValue('--income'),style.getPropertyValue('--expense')],values=[income,expense],sum=income+expense,max=income>expense?income:expense;
 canvas.setAttribute('aria-label',t('income')+': '+money(income,currency)+'; '+t('expense')+': '+money(expense,currency));
 ctx.font=(14*720/Math.max(canvas.clientWidth||720,240))+'px system-ui';ctx.fillStyle=style.getPropertyValue('--muted');if(!sum){ctx.fillText(t('empty_money'),24,150);return;}
 const ratio=(v,m=max)=>Number(v*1000000n/m)/1000000;
 if(state.chart==='donut'){let angle=-Math.PI/2;values.forEach((v,i)=>{if(!v)return;ctx.beginPath();ctx.strokeStyle=colors[i];ctx.lineWidth=42;ctx.arc(360,155,100,angle,angle+ratio(v,sum)*Math.PI*2);ctx.stroke();angle+=ratio(v,sum)*Math.PI*2;});return;}
 if(['line','smooth'].includes(state.chart)){
  const days=new Map();for(const r of rows.filter(r=>r.data.currency===currency)){if(!days.has(r.data.date))days.set(r.data.date,[0n,0n]);days.get(r.data.date)[r.data.kind==='income'?0:1]+=BigInt(r.data.amount_minor);}
  const dates=[...days.keys()].sort();const start=Date.parse(dates[0]),end=Date.parse(dates.at(-1));
  for(let k=0;k<2;k++){let running=0n;const points=dates.map(date=>{running+=days.get(date)[k];return [40+(end===start?0:(Date.parse(date)-start)/(end-start)*640),270-ratio(running)*225];});ctx.strokeStyle=colors[k];ctx.lineWidth=3;ctx.beginPath();points.forEach(([x,y],i)=>{if(!i)ctx.moveTo(x,y);else if(state.chart==='smooth'){const [px,py]=points[i-1],mid=(px+x)/2;ctx.bezierCurveTo(mid,py,mid,y,x,y);}else ctx.lineTo(x,y);});ctx.stroke();for(const [x,y]of points){ctx.fillStyle=colors[k];ctx.beginPath();ctx.arc(x,y,3,0,Math.PI*2);ctx.fill();}}
  ctx.fillStyle=style.getPropertyValue('--muted');ctx.fillText(dates[0],40,304);ctx.textAlign='right';ctx.fillText(dates.at(-1),680,304);ctx.textAlign='left';return;
 }
 values.forEach((v,i)=>{ctx.fillStyle=colors[i];ctx.fillText(t(i?'expense':'income'),24,48+i*135);ctx.fillRect(24,64+i*135,ratio(v)*650,44);ctx.fillStyle=style.getPropertyValue('--ink');ctx.fillText(money(v,currency),24,132+i*135);});
}
function createSpace(kind){let operation;const d=dialog(t(kind==='family'?'family_create':'web_personal_create'),container=>form(container,'',f=>({name:input(f,'name',t('name'))}),async v=>{operation=operation||{id:crypto.randomUUID(),workspace_id:crypto.randomUUID(),action:'workspace.create',kind,name:v.name.value};try{await call('family',operation);}catch(e){if(!e.uncertain)operation=null;throw e;}state.space=operation.workspace_id;d.close();await refresh();render();}));}
function acceptInvite(){const d=dialog(t('family_accept'),container=>form(container,'',f=>({invitation:input(f,'invitation',t('family_invitation'))}),async v=>{await call('invitations/accept',{id:crypto.randomUUID(),invitation:v.invitation.value});d.close();await refresh();render();}));}
function familyPanel(m){const c=card(t('family_account'));m.append(c);c.append(button(t('family_create'),()=>createSpace('family')),button(t('family_owner'),()=>createSpace('personal')),button(t('family_accept'),acceptInvite));if(!state.roster)return;const {space,members,profiles}=state.roster;for(const member of members){const row=E('div',undefined,'row');append(row,E('span',member.user_id===state.session.user_id?t('family_you'):member.user_id,'text'),E('span',t('family_'+member.role),'pill'));c.append(row);}if(space.kind==='family'&&['parent','owner'].includes(space.role))c.append(button(t('family_invite'),()=>dialog(t('family_invite'),container=>{let operation;form(container,'',f=>({email:input(f,'email',t('family_invite_email'),'email'),role:select(f,'role',t('family_role'),['adult','parent','child'].map(k=>[k,t('family_'+k)]),'adult'),profile:select(f,'profile',t('family_child'),[['',t('family_none')],...profiles.map(p=>[p.id,p.name])],'')}),async v=>{operation=operation||{id:crypto.randomUUID(),workspace_id:space.id,action:'invite.create',email:v.email.value,role:v.role.value,profile_id:v.role.value==='child'?v.profile.value:null};const invite=await call('family',operation);replaceDialog(container,E('h2',t('family_invite')),E('p',t('family_invite_hint')),E('pre',invite.invitation),button(t('close'),()=>container.close()));});})),button(t('family_child_add'),()=>{const d=dialog(t('family_child_add'),container=>form(container,'',f=>({name:input(f,'name',t('name'))}),async v=>{await call('family',{id:crypto.randomUUID(),workspace_id:space.id,action:'child.save',profile_id:crypto.randomUUID(),revision:0,name:v.name.value,permissions:['view_shared','complete_tasks']});d.close();await refresh();render();}));}));}
async function account(m){title(m,'account_manage');const c=card(state.session.email);m.append(c);c.append(button(t('account_privacy'),privacy),button(t('family_logout'),async()=>{await call('logout',{});clearIdentity();login();}));const settings=card(t('theme'));settings.classList.add('settings-grid');m.append(settings);language(settings);const theme=select(settings,'theme',t('theme'),['system','light','dark'].map(k=>[k,t(k)]),state.theme);theme.addEventListener('change',()=>{state.theme=theme.value;preferences();});const palette=select(settings,'palette',t('palette'),[['forest',t('appearance_emerald')],['ocean',t('appearance_sky')],['pistachio',t('appearance_pistachio')]],state.palette);palette.addEventListener('change',()=>{state.palette=palette.value;preferences();});const install=E('details');append(install,E('summary','iPhone / iPad · PWA'),E('p',t('web_install')));settings.append(install,E('p',t('web_online'),'small'),E('p',t('web_locale_coverage'),'small'));if(deferredInstall)settings.append(button(t('web_install_button'),async()=>{await deferredInstall.prompt();deferredInstall=null;}));familyPanel(m);familyPermissions(m);if(['owner','staff'].includes(new URLSearchParams(location.search).get('setup')))m.append(button('ULADIM Control',enrollStaff));
 try{const ent=await call('entitlements');if(state.tab!=='account')return;const plans=card(t('account_access'));append(plans,E('div',ent.tier,'stat'),E('p',t('account_no_payment')));m.append(plans);await support(m);}catch(e){report(e);}}
function enrollStaff(){dialog('ULADIM Control',container=>{const owner=new URLSearchParams(location.search).get('setup')==='owner';const d=container;form(container,t('account_manage'),f=>({password:input(f,'password',t('family_password'),'password'),invitation:input(f,'invitation',t('family_invitation'))}),async v=>{const result=await call('staff/enrollment',{owner,password:v.password.value,invitation:v.invitation.value});replaceDialog(container,E('h2',t('account_mfa')),E('p',t('account_mfa_setup')),E('pre',result.totp_secret));form(container,'',f=>({code:input(f,'code',t('family_code'))}),async code=>{const r=await call('staff/confirm',{owner,enrollment:result.enrollment,code:code.code.value});replaceDialog(container,E('h2',t('account_mfa_recovery')),E('pre',r.recovery_codes.join('\n')),button(t('close'),()=>d.close()));});});});}
async function support(m){const result=await call('support');if(state.tab!=='account')return;const c=card(t('account_support'));m.append(c);for(const ticket of result.tickets||[])c.append(button(ticket.subject,()=>openThread(ticket.id)));form(c,'',f=>({subject:input(f,'subject',t('account_subject')),message:input(f,'message',t('account_message'),'textarea')}),async v=>{await call('support',{category:'other',subject:v.subject.value,message:v.message.value});toast(t('account_done'));render();},t('account_send'));}
async function openThread(id){const result=await call('thread?id='+encodeURIComponent(id));dialog(result.ticket.subject,d=>{for(const message of result.messages)d.append(E('p',message.body,'note'));form(d,'',f=>({message:input(f,'message',t('account_message'),'textarea')}),async v=>{await call('support/reply',{ticket_id:id,message:v.message.value,state:'open'});d.close();await openThread(id);},t('account_send'));});}
window.addEventListener('online',()=>{if(state.session)refresh().then(render).catch(report);});window.addEventListener('offline',()=>{if(state.session&&!document.querySelector('dialog'))render();toast(t('web_online'));});window.addEventListener('pagehide',()=>{clearIdentity();root.replaceChildren();document.querySelector('#alerts').replaceChildren();});window.addEventListener('pageshow',e=>{if(e.persisted)start().catch(error=>{clearIdentity();login();if(error.code!=='unauthorized')toast(errorText(error));});});
document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible'&&state.session&&!document.querySelector('dialog'))refresh().then(render).catch(report);});
setInterval(()=>{if(state.session&&document.visibilityState==='visible'&&!document.querySelector('dialog')&&navigator.onLine)refresh().then(render).catch(report);},30000);
(async()=>{try{packs=await (await fetch('/app/assets/locales.json',{cache:'no-store'})).json();if(!packs[state.lang])state.lang='ru';applyTheme();const config=await call('config');state.googleEnabled=Boolean(config.google_enabled);try{if(new URLSearchParams(location.search).get('google')==='return')await googleReturn();else await start();}catch(error){if(error.code==='unauthorized'){login();if(new URLSearchParams(location.search).get('action')==='signup')await signup();}else{login();report(error);}}if('serviceWorker'in navigator)navigator.serviceWorker.register('/app/sw.js',{scope:'/app'}).catch(()=>{});}catch{root.textContent='ULADIM · '+t('retry');}})();

async function signup(){
 const config=await call('config');
 const d=dialog(t('family_register'),container=>{
 form(container,'',f=>{const fields={email:input(f,'email',t('family_email'),'email'),password:input(f,'new-password',t('family_password'),'password')};if(!config.registration_open)fields.invitation=input(f,'invitation',t('family_invitation'));return fields;},async v=>{
 const email=v.email.value;try{await call('signup',{email,password:v.password.value,...(v.invitation?{invitation:v.invitation.value}:{})});}finally{v.password.value='';}
 replaceDialog(container,E('h2',t('family_verify')),E('p',t('family_verify_hint')));
 form(container,'',f=>({code:input(f,'code',t('family_code'))}),async fields=>{await call('confirm-signup',{email,code:fields.code.value.trim()});fields.code.value='';d.close();login();toast(t('account_done'));},t('family_verify'));
 container.append(button(t('ux3_resend_verification'),async()=>{await call('resend-signup',{email});toast(t('family_verify_hint'));}));
 },t('family_register'));
 if(config.google_enabled)container.append(button(t('account_google_sign_in'),()=>beginGoogle(container.querySelector('[name=invitation]')?.value)));
 const legal=E('p',undefined,'small');append(legal,anchor(t('account_privacy'),'/privacy'));container.append(legal);
 });
}

function recover(){const d=dialog(t('family_recovery'),container=>form(container,'',f=>({email:input(f,'email',t('family_email'),'email')}),async v=>{const email=v.email.value;await call('recovery',{email});replaceDialog(container,E('h2',t('family_recovery')),E('p',t('family_recovery_hint')));form(container,'',f=>({code:input(f,'code',t('family_code')),password:input(f,'new-password',t('family_new_password'),'password')}),async fields=>{await call('reset',{email,code:fields.code.value,password:fields.password.value});d.close();login();toast(t('account_done'));});}));}
async function privacy(){const status=await call('deletion');dialog(t('account_privacy'),d=>{
 d.append(button(t('account_mfa'),customerMfa),button(t('account_devices'),devices),button(t('account_google_methods'),googleMethods));
 form(d,t('family_password_change'),f=>({old:input(f,'old',t('family_old_password'),'password'),next:input(f,'new',t('family_new_password'),'password')}),async v=>{await call('password',{old_password:v.old.value,new_password:v.next.value});d.close();clearIdentity();login();});
 form(d,t('account_email_change'),f=>({email:input(f,'email',t('family_email'),'email'),password:input(f,'password',t('family_old_password'),'password')}),async v=>{await call('email',{email:v.email.value,password:v.password.value});dialog(t('family_verify'),c=>form(c,'',f=>({code:input(f,'code',t('family_code')),password:input(f,'password',t('family_old_password'),'password')}),async v=>{await call('confirm-email',{code:v.code.value,password:v.password.value});clearIdentity();login();}));});
 d.append(E('h2',t('account_delete')),E('p',t('account_delete_notice')));
 for(const transfer of status.incoming_transfers||[])form(d,t('account_accept_transfer')+' · '+transfer.name,f=>({password:input(f,'password',t('family_old_password'),'password')}),async v=>{await call('accept-transfer',{transfer_id:transfer.id,password:v.password.value});d.close();await privacy();});
 if(status.ownership_transfer_required.length){for(const family of status.ownership_transfer_required)if(family.eligible_parent_id)form(d,t('account_transfer')+' · '+family.name,f=>({password:input(f,'password',t('family_old_password'),'password')}),async v=>{await call('transfer',{workspace_id:family.id,user_id:family.eligible_parent_id,password:v.password.value});toast(t('account_done'));});}
 else if(status.request?.state==='pending')form(d,t('account_cancel_delete'),f=>({password:input(f,'password',t('family_old_password'),'password')}),async v=>{await call('cancel-deletion',{password:v.password.value});d.close();await privacy();});
 else form(d,t('account_delete'),f=>({password:input(f,'password',t('family_old_password'),'password'),confirmation:input(f,'confirmation','DELETE')}),async v=>{await call('deletion',{password:v.password.value,confirmation:v.confirmation.value});d.close();await privacy();});
 });}
async function googleMethods(){
 const status=await call('google'),mfa=await call('mfa');
 dialog(t('account_google_methods'),d=>{
  d.append(E('p',t(status.google_linked?'account_google_linked':'account_google_unlinked')));
  if(!status.has_password){d.append(E('p',t('account_google_password_first')),button(t('family_recovery'),recover));return;}
  if(!status.google_linked&&!status.google_web_enabled)return;
  form(d,'',f=>({password:input(f,'password',t('family_old_password'),'password'),...(mfa.enabled?{code:input(f,'code',t('family_code'))}:{})}),async v=>{
   let value;try{value=await call(status.google_linked?'google/unlink':'google/link',{password:v.password.value,code:v.code?.value});}finally{v.password.value='';if(v.code)v.code.value='';}
   if(value.authorization_url){location.assign(value.authorization_url);return;}
   d.close();clearIdentity();login();
  },t(status.google_linked?'account_google_disconnect':'account_google_connect'));
 });
}
async function devices(){const result=await call('devices');dialog(t('account_devices'),d=>{for(const device of result.devices){const c=card(device.label);c.append(E('p',new Date(device.last_seen_at*1000).toLocaleString(state.lang)));form(c,t('account_revoke'),f=>({password:input(f,'password',t('family_old_password'),'password')}),async v=>{await call('devices/revoke',{device_id:device.id,password:v.password.value});d.close();await start();});d.append(c);}});}
async function customerMfa(){const status=await call('mfa');dialog(t('account_mfa'),d=>{
 if(status.enabled)form(d,t('account_mfa_disable'),f=>({password:input(f,'password',t('family_old_password'),'password'),code:input(f,'code',t('family_code'))}),async v=>{await call('mfa/disable',{password:v.password.value,code:v.code.value});d.close();clearIdentity();login();toast(t('account_done'));});
 else form(d,t('account_mfa'),f=>({password:input(f,'password',t('family_old_password'),'password')}),async v=>{const r=await call('mfa/begin',{password:v.password.value});replaceDialog(d,E('h2',t('account_mfa')),E('p',t('account_mfa_setup')),E('pre',r.totp_secret));form(d,'',f=>({password:input(f,'password',t('family_old_password'),'password'),code:input(f,'code',t('family_code'))}),async fields=>{const value=await call('mfa/enable',{password:fields.password.value,enrollment:r.enrollment,code:fields.code.value});replaceDialog(d,E('h2',t('account_mfa_recovery')),E('pre',value.recovery_codes.join('\n')),button(t('close'),()=>{d.close();clearIdentity();login();}));});});
 });}

function familyPermissions(m){
 const roster=state.roster;if(!roster||roster.space.kind!=='family'||!['parent','owner'].includes(roster.space.role))return;
 const c=card(t('family_role'));m.append(c);
 for(const profile of roster.profiles)c.append(button(profile.name+' · '+t('edit'),()=>childProfile(profile)));
 for(const member of roster.members.filter(x=>['adult','child'].includes(x.role))){const row=E('div',undefined,'row');append(row,E('span',member.user_id,'text'),button(t('account_revoke'),()=>dialog(t('family_remove'),d=>d.append(button(t('account_revoke'),async()=>{await call('family',{id:crypto.randomUUID(),action:'member.remove',workspace_id:roster.space.id,user_id:member.user_id,revision:member.revision});d.close();await refresh();render();})))));c.append(row);}
 for(const invite of roster.invitations||[])c.append(button(invite.email+' · '+t('account_revoke'),()=>dialog(t('family_invite_revoke'),d=>d.append(button(t('account_revoke'),async()=>{await call('family',{id:crypto.randomUUID(),action:'invite.revoke',workspace_id:roster.space.id,invitation_id:invite.id});d.close();await refresh();render();})))));
}
function childProfile(profile){const d=dialog(t('family_child'),container=>form(container,'',f=>{const fields={name:input(f,'name',t('name'),'text',profile.name)};for(const key of ['view_budget','record_spending','edit_own','request_money','view_shared','create_tasks','complete_tasks']){fields[key]=input(f,key,t('family_permission_'+key),'checkbox','',false);fields[key].checked=profile.permissions.includes(key);}return fields;},async v=>{const permissions=Object.keys(v).filter(k=>k!=='name'&&v[k].checked);await call('family',{id:crypto.randomUUID(),workspace_id:state.space,action:'child.save',profile_id:profile.id,revision:profile.revision,name:v.name.value,permissions});d.close();await refresh();render();}));}

if(window.visualViewport){const fit=()=>{document.body.style.setProperty('--visible-height',visualViewport.height+'px');document.querySelector('dialog input:focus,dialog textarea:focus')?.scrollIntoView({block:'nearest'});};visualViewport.addEventListener('resize',fit);fit();}
