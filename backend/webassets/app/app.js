'use strict';
const root=document.querySelector('#root'),alerts=document.querySelector('#alerts');
const state={session:null,csrf:'',spaces:[],space:null,roster:null,records:[],financeFilters:{},taskQuery:'',taskStatus:'all',calendarDay:localDate(),lastRead:0,syncState:'idle',syncSpace:null,syncCursor:0,syncEpoch:'',tab:'today',settingsTab:'',lang:'ru',theme:'system',palette:'violet',chart:'bar',generation:0,busy:false,googleEnabled:false};
let calendarMode='month';
let packs={},alertTimer,navObserver,privateEpoch=0,redrawFinance=null,backgroundDirty=false;
const sessionEvents=typeof BroadcastChannel==='function'?new BroadcastChannel('uladim-session'):null;
sessionEvents?.addEventListener('message',event=>{if(event.data==='signed-out'){clearNoteDrafts();clearTaskActions();clearIdentity();login();}});
const pendingDeletes=new Map();
const quickTasks=new Map();
const taskChanges=new Map();
try{const saved=JSON.parse(localStorage.getItem('uladim-interface')||'{}');for(const key of ['lang','theme','palette','chart'])if(typeof saved[key]==='string')state[key]=saved[key];}catch{}
// Persist only interface preferences. Accounts, spaces, records and tokens stay in memory.
function preferences(){try{localStorage.setItem('uladim-interface',JSON.stringify({lang:state.lang,theme:state.theme,palette:state.palette,chart:state.chart}));}catch{}applyTheme();}
function applyTheme(){document.body.dataset.design=new URLSearchParams(location.search).get('design')==='legacy'?'':'clarity';document.body.dataset.theme=state.theme;document.body.dataset.palette=state.palette;document.documentElement.lang=state.lang;}

const WEB_COPY={
 ru:{web_calendar:'Календарь',family_kind_event:'Событие',web_upcoming:'Ближайшие 7 дней',web_no_events:'Событий пока нет. Добавьте время для важного.',web_all_tasks:'Все задачи',web_task_search:'Поиск задач',web_task_status:'Статус задачи',web_all:'Все',web_no_results:'Ничего не найдено',web_event_start:'Начало события',web_timezone:'Часовой пояс',web_all_day:'Весь день',web_repeat:'Повторение',web_interval:'Интервал повторения',web_until:'Повторять до',web_repeat_none:'Не повторять',web_repeat_daily:'Ежедневно',web_repeat_weekly:'Еженедельно',web_repeat_monthly:'Ежемесячно',web_repeat_yearly:'Ежегодно',web_deleted_pending:'Запись будет удалена',web_delete_failed:'Удаление не подтверждено. Обновите данные перед повтором.',web_previous:'Предыдущий месяц',web_next:'Следующий месяц',web_month:'Месяц',web_agenda:'Повестка',web_partial_short:'частичный перевод',web_locale_coverage:'Новые экраны переведены на русский, английский и два варианта узбекского. Для остальных языков новые подписи показаны на английском.',web_conflict:'Запись изменена на другом устройстве. Скопируйте свои правки и загрузите серверную версию.',web_uncertain:'Сервер мог сохранить запись. Повторите запрос этой кнопкой — повтор не создаст копию.',web_server_error:'Сервис временно недоступен. Попробуйте позже.',web_view_changed:'Пространство или сессия изменились. Откройте запись заново.',web_currency_mismatch:'Валюта должна совпадать со счётом. При переводе в одной валюте суммы должны быть одинаковыми.',web_transfer_accounts:'Для перевода нужны два разных счёта.',web_install_button:'Установить ULADIM',web_loading:'Загрузка пространства…',web_quick_task:'Что нужно сделать?',web_add_task:'Добавить задачу',web_online_status:'Синхронизация через ваш аккаунт',web_day:'Выбранный день',web_cancel:'Отменить'},
 en:{web_calendar:'Calendar',family_kind_event:'Event',web_upcoming:'Next 7 days',web_no_events:'No events yet. Make time for what matters.',web_all_tasks:'All tasks',web_task_search:'Search tasks',web_task_status:'Task status',web_all:'All',web_no_results:'No results',web_event_start:'Event start',web_timezone:'Time zone',web_all_day:'All day',web_repeat:'Repeat',web_interval:'Repeat interval',web_until:'Repeat until',web_repeat_none:'Never',web_repeat_daily:'Daily',web_repeat_weekly:'Weekly',web_repeat_monthly:'Monthly',web_repeat_yearly:'Yearly',web_deleted_pending:'Record will be deleted',web_delete_failed:'Deletion not confirmed. Refresh before retrying.',web_previous:'Previous month',web_next:'Next month',web_month:'Month',web_agenda:'Agenda',web_partial_short:'partial translation',web_locale_coverage:'New screens are translated into Russian, English and both Uzbek scripts. Other languages use English for new labels.',web_conflict:'This record changed on another device. Copy your edits, then load the server version.',web_uncertain:'The server may have saved this record. Retry with this button; it reuses the operation to avoid duplicates.',web_server_error:'Service temporarily unavailable. Try again later.',web_view_changed:'Workspace or session changed. Reopen the record.',web_currency_mismatch:'Currency must match the account. Same-currency transfers must have equal amounts.',web_transfer_accounts:'Transfers require two different accounts.',web_install_button:'Install ULADIM',web_loading:'Loading workspace…',web_quick_task:'What needs to be done?',web_add_task:'Add task',web_online_status:'Synced through your account',web_day:'Selected day',web_cancel:'Undo'},
 'uz-Latn':{web_calendar:'Taqvim',family_kind_event:'Tadbir',web_upcoming:'Keyingi 7 kun',web_no_events:'Hozircha tadbirlar yo‘q. Muhim ishlar uchun vaqt ajrating.',web_all_tasks:'Barcha vazifalar',web_task_search:'Vazifalarni qidirish',web_task_status:'Vazifa holati',web_all:'Barchasi',web_no_results:'Hech narsa topilmadi',web_event_start:'Tadbir boshlanishi',web_timezone:'Vaqt mintaqasi',web_all_day:'Kun bo‘yi',web_repeat:'Takrorlash',web_interval:'Takrorlash oralig‘i',web_until:'Shu sanagacha takrorlash',web_repeat_none:'Takrorlanmasin',web_repeat_daily:'Har kuni',web_repeat_weekly:'Har hafta',web_repeat_monthly:'Har oy',web_repeat_yearly:'Har yil',web_deleted_pending:'Yozuv o‘chiriladi',web_delete_failed:'O‘chirish tasdiqlanmadi. Qayta urinishdan oldin yangilang.',web_previous:'Oldingi oy',web_next:'Keyingi oy',web_month:'Oy',web_agenda:'Kun tartibi',web_partial_short:'qisman tarjima',web_locale_coverage:'Yangi ekranlar rus, ingliz va o‘zbek tilining ikkala yozuvida tarjima qilingan. Qolgan tillarda yangi yozuvlar inglizcha.',web_conflict:'Yozuv boshqa qurilmada o‘zgargan. Tahrirlaringizni nusxalang va server nusxasini yuklang.',web_uncertain:'Server yozuvni saqlagan bo‘lishi mumkin. Shu tugma bilan takrorlang — nusxa yaratilmaydi.',web_server_error:'Xizmat vaqtincha mavjud emas. Keyinroq urinib ko‘ring.',web_view_changed:'Makon yoki seans o‘zgargan. Yozuvni qayta oching.',web_currency_mismatch:'Valyuta hisob bilan mos bo‘lsin. Bir xil valyutadagi o‘tkazma summalari teng bo‘lishi kerak.',web_transfer_accounts:'O‘tkazma uchun ikki xil hisob kerak.',web_install_button:'ULADIM o‘rnatish',web_loading:'Makon yuklanmoqda…',web_quick_task:'Nima qilish kerak?',web_add_task:'Vazifa qo‘shish',web_online_status:'Hisobingiz orqali sinxronlanadi',web_day:'Tanlangan kun',web_cancel:'Bekor qilish'},
 'uz-Cyrl':{web_calendar:'Тақвим',family_kind_event:'Тадбир',web_upcoming:'Кейинги 7 кун',web_no_events:'Ҳозирча тадбирлар йўқ. Муҳим ишлар учун вақт ажратинг.',web_all_tasks:'Барча вазифалар',web_task_search:'Вазифаларни қидириш',web_task_status:'Вазифа ҳолати',web_all:'Барчаси',web_no_results:'Ҳеч нарса топилмади',web_event_start:'Тадбир бошланиши',web_timezone:'Вақт минтақаси',web_all_day:'Кун бўйи',web_repeat:'Такрорлаш',web_interval:'Такрорлаш оралиғи',web_until:'Шу санагача такрорлаш',web_repeat_none:'Такрорланмасин',web_repeat_daily:'Ҳар куни',web_repeat_weekly:'Ҳар ҳафта',web_repeat_monthly:'Ҳар ой',web_repeat_yearly:'Ҳар йил',web_deleted_pending:'Ёзув ўчирилади',web_delete_failed:'Ўчириш тасдиқланмади. Қайта уринишдан олдин янгиланг.',web_previous:'Олдинги ой',web_next:'Кейинги ой',web_month:'Ой',web_agenda:'Кун тартиби',web_partial_short:'қисман таржима',web_locale_coverage:'Янги экранлар рус, инглиз ва ўзбек тилининг иккала ёзувида таржима қилинган. Қолган тилларда янги ёзувлар инглизча.',web_conflict:'Ёзув бошқа қурилмада ўзгарган. Таҳрирларингизни нусхаланг ва сервер нусхасини юкланг.',web_uncertain:'Сервер ёзувни сақлаган бўлиши мумкин. Шу тугма билан такрорланг — нусха яратилмайди.',web_server_error:'Хизмат вақтинча мавжуд эмас. Кейинроқ уриниб кўринг.',web_view_changed:'Макон ёки сеанс ўзгарган. Ёзувни қайта очинг.',web_currency_mismatch:'Валюта ҳисоб билан мос бўлсин. Бир хил валютадаги ўтказма суммалари тенг бўлиши керак.',web_transfer_accounts:'Ўтказма учун икки хил ҳисоб керак.',web_install_button:'ULADIM ўрнатиш',web_loading:'Макон юкланмоқда…',web_quick_task:'Нима қилиш керак?',web_add_task:'Вазифа қўшиш',web_online_status:'Ҳисобингиз орқали синхронланади',web_day:'Танланган кун',web_cancel:'Бекор қилиш'}
};
let deferredInstall=null;
for(const [locale,message] of Object.entries({
 ru:'Изменения сохранены. Повторите обновление списка.',
 en:'Your changes were saved. Retry loading the list.',
 'uz-Latn':'O‘zgarishlar saqlandi. Ro‘yxatni qayta yuklang.',
 'uz-Cyrl':'Ўзгаришлар сақланди. Рўйхатни қайта юкланг.'
})) WEB_COPY[locale].web_saved_refresh=message;
for(const [locale,message] of Object.entries({ru:'Итого',en:'Net','uz-Latn':'Jami','uz-Cyrl':'Жами'}))WEB_COPY[locale].web_today_net=message;
for(const [locale,copy] of Object.entries({
 ru:['Расписание','{done} из {total}'],en:['Schedule','{done} of {total}'],
 'uz-Latn':['Kun tartibi','{total} tadan {done} ta'],'uz-Cyrl':['Кун тартиби','{total} тадан {done} та']
})){
 WEB_COPY[locale].web_today_schedule=copy[0];
 WEB_COPY[locale].web_today_progress=copy[1];
}
for(const [locale,[retry,create,pending]] of Object.entries({
 ru:['Сохранение не подтверждено','Повторить создание','Действие сохранено только до перезагрузки.'],
 en:['Save unconfirmed','Retry creating task','This action is only available until reload.'],
 'uz-Latn':['Saqlash tasdiqlanmadi','Yaratishni takrorlash','Harakat sahifa qayta yuklanguncha saqlanadi.'],
 'uz-Cyrl':['Сақлаш тасдиқланмади','Яратишни такрорлаш','Ҳаракат саҳифа қайта юклангунча сақланади.']
})){
 Object.assign(WEB_COPY[locale],{web_task_unconfirmed:retry,web_task_retry_create:create,web_task_tab_only:pending});
}
for(const [locale,message] of Object.entries({ru:'Импорт и синхронизация',en:'Import and sync','uz-Latn':'Import va sinxronlash','uz-Cyrl':'Импорт ва синхронлаш'}))WEB_COPY[locale].web_personal_import=message;
for(const [locale,labels] of Object.entries({
 ru:['Дополнительные параметры','Операции','Бюджеты'],
 en:['Additional options','Transactions','Budgets'],
 'uz-Latn':['Qo‘shimcha sozlamalar','Operatsiyalar','Budjetlar'],
 'uz-Cyrl':['Қўшимча созламалар','Операциялар','Бюджетлар']
})){
 const [web_event_options,web_finance_transactions,web_finance_budgets]=labels;
 Object.assign(WEB_COPY[locale],{web_event_options,web_finance_transactions,web_finance_budgets});
}
window.addEventListener('beforeinstallprompt',e=>{e.preventDefault();deferredInstall=e;});
function dateString(d){return [d.getFullYear(),String(d.getMonth()+1).padStart(2,'0'),String(d.getDate()).padStart(2,'0')].join('-');}
function eventRow(o,agenda=false){
 const row=E('div',undefined,'row event-row'),caption=E('div',undefined,'text');
 const title=E('h3',o.record.data.title),when=o.allDay?t('web_all_day'):o.time;
 if(agenda){
  const time=E(o.allDay?'span':'time',when,'calendar-event-time');
  if(!o.allDay)time.dateTime=new Date(o.at).toISOString();
  append(caption,time,title);
 }else{
  const date=new Intl.DateTimeFormat(state.lang,{day:'numeric',month:'long'}).format(new Date(o.day+'T12:00:00'));
  append(caption,title,E('p',date+' · '+when,'small'));
 }
 return append(row,caption,iconButton('more',t('edit')+' · '+o.record.data.title,()=>editRecord('event',o.record)));
}
const CALENDAR_COPY={
 ru:['Неделя','День','Предыдущая неделя','Следующая неделя','Предыдущий день','Следующий день'],
 en:['Week','Day','Previous week','Next week','Previous day','Next day'],
 'uz-Latn':['Hafta','Kun','Oldingi hafta','Keyingi hafta','Oldingi kun','Keyingi kun'],
 'uz-Cyrl':['Ҳафта','Кун','Олдинги ҳафта','Кейинги ҳафта','Олдинги кун','Кейинги кун']
};
function offsetDate(date,days){
 const shifted=new Date(date.getTime());
 shifted.setDate(shifted.getDate()+days);
 return shifted;
}
function calendar(m){
 const addEvent=()=>editRecord('event',null,{eventDay:state.calendarDay});
 const copy={
  ru:['Планы и встречи','Ваши планы и встречи в одном месте.','Новое событие','Добавить событие'],
  en:['Plans and gatherings','Your plans and gatherings, all in one place.','New event','Add event'],
  'uz-Latn':['Rejalar va uchrashuvlar','Rejalaringiz va uchrashuvlaringiz bir joyda.','Yangi tadbir','Tadbir qo‘shish'],
  'uz-Cyrl':['Режалар ва учрашувлар','Режаларингиз ва учрашувларингиз бир жойда.','Янги тадбир','Тадбир қўшиш']
 }[state.lang]||['Plans and gatherings','Your plans and gatherings, all in one place.','New event','Add event'];
 title(m,'web_calendar');
 m.classList.add('calendar-page');
 const intro=m.querySelector('.intro'),introText=intro.firstElementChild;
 introText.prepend(E('div',copy[0],'eyebrow'));
 introText.append(E('p',copy[1],'workspace-description'));
 intro.append(addButton(copy[2],addEvent));
 const date=new Date(state.calendarDay+'T12:00:00'),year=date.getFullYear(),month=date.getMonth();
 const [weekLabel,dayLabel,previousWeek,nextWeek,previousDay,nextDay]=CALENDAR_COPY[state.lang]||CALENDAR_COPY.en;
 const weekStart=offsetDate(date,-((date.getDay()+6)%7));
 const from=calendarMode==='month'?new Date(year,month,1):calendarMode==='week'?weekStart:date;
 const to=calendarMode==='month'?new Date(year,month+1,1):offsetDate(from,calendarMode==='week'?7:1);
 const modes=E('div',undefined,'calendar-modes');
 modes.setAttribute('role','group');modes.setAttribute('aria-label',t('web_calendar'));
 for(const [key,label] of [['month',t('web_month')],['week',weekLabel],['day',dayLabel]]){
  const control=button(label,()=>{
   calendarMode=key;render();
   root.querySelector('.calendar-modes [aria-pressed=true]')?.focus({preventScroll:true});
  },'secondary');
  control.setAttribute('aria-pressed',String(calendarMode===key));modes.append(control);
 }
 const layout=E('div',undefined,'calendar-layout'),monthPanel=card(),agenda=card();
 layout.dataset.mode=calendarMode;
 monthPanel.classList.add('calendar-month');
 agenda.classList.add('calendar-agenda');
 if(calendarMode==='day')layout.classList.add('calendar-day-layout');
 append(layout,monthPanel,agenda);
 m.append(layout);
 const showDate=(next,focus)=>{
  state.calendarDay=next;
  render();
  root.querySelector(focus)?.focus({preventScroll:true});
 };
 const toolbar=E('div',undefined,'calendar-toolbar');
 const move=(delta,selector)=>showDate(dateString(calendarMode==='month'?new Date(year,month+delta,1):offsetDate(date,delta*(calendarMode==='week'?7:1))),selector);
 const previous=iconButton('back',calendarMode==='month'?t('web_previous'):calendarMode==='week'?previousWeek:previousDay,()=>move(-1,'.calendar-previous'));
 previous.classList.add('calendar-previous');
 const next=iconButton('forward',calendarMode==='month'?t('web_next'):calendarMode==='week'?nextWeek:nextDay,()=>move(1,'.calendar-next'));
 next.classList.add('calendar-next');
 const period=calendarMode==='month'?date.toLocaleDateString(state.lang,{month:'long',year:'numeric'}):
  calendarMode==='week'?new Intl.DateTimeFormat(state.lang,{day:'numeric',month:'long'}).formatRange(from,offsetDate(to,-1)):
  date.toLocaleDateString(state.lang,{day:'numeric',month:'long'});
 const periodNavigation=E('div',undefined,'calendar-period');
 append(periodNavigation,previous,E('h2',period),next);
 const returnToday=button(t('today'),()=>showDate(localDate(),'.calendar-date[aria-pressed=true]'),'secondary calendar-today');
 periodNavigation.append(returnToday);
 append(toolbar,periodNavigation,modes);
 const grid=E('div',undefined,'calendar-grid');
 append(monthPanel,toolbar,grid);
 if(calendarMode!=='day')for(let i=0;i<7;i++){
  const weekday=new Date(2026,10,2+i);
  const day=E('span',weekday.toLocaleDateString(state.lang,{weekday:'short'}),'weekday');
  day.title=weekday.toLocaleDateString(state.lang,{weekday:'long'});
  grid.append(day);
 }
 const all=ULADIMDomain.occurrences(records('event'),dateString(from),dateString(to)),byDay=new Map();
 for(const o of all){
  if(!byDay.has(o.day))byDay.set(o.day,[]);
  byDay.get(o.day).push(o);
 }
 if(calendarMode==='month'){
  const offset=(from.getDay()+6)%7;
  for(let i=offset;i>0;i--)grid.append(E('span',String(offsetDate(from,-i).getDate()),'calendar-offset'));
 }
 const today=localDate();
 if(calendarMode!=='day')for(let d=from;d<to;d=offsetDate(d,1)){
  const key=dateString(d),items=byDay.get(key)||[];
  const b=button('',()=>showDate(key,'.calendar-date[aria-pressed=true]'),'calendar-date');
  b.append(E('span',String(d.getDate()),'calendar-date-number'));
  b.setAttribute('aria-label',d.toLocaleDateString(state.lang,{day:'numeric',month:'long'})+(items.length?' · '+items.map(o=>o.record.data.title).join(', '):''));
  b.setAttribute('aria-pressed',String(key===state.calendarDay));
  if(key===today){b.classList.add('is-today');b.setAttribute('aria-current','date');}
  if(items.length){
   const dots=E('span',undefined,'calendar-event-dots');dots.setAttribute('aria-hidden','true');
   for(const o of items.slice(0,3)){const dot=E('span');dot.dataset.visibility=o.record.visibility;dots.append(dot);}
   b.append(dots);
   const preview=E('span',items[0].record.data.title,'calendar-date-preview');preview.setAttribute('aria-hidden','true');b.append(preview);
  }
  grid.append(b);
 }
 if(calendarMode==='month'){
  const remaining=(7-((to.getDay()+6)%7))%7;
  for(let i=0;i<remaining;i++)grid.append(E('span',String(offsetDate(to,i).getDate()),'calendar-offset'));
 }
 if(all.length&&calendarMode!=='day'){
  const legend=E('div',undefined,'calendar-legend');
  for(const visibility of ['private','shared'])if(all.some(o=>o.record.visibility===visibility)){
   const item=E('span',t('family_'+visibility));item.dataset.visibility=visibility;legend.append(item);
  }
  monthPanel.append(legend);
 }
 const agendaHead=E('div',undefined,'calendar-agenda-head');
 const dateHeading=E('h2',undefined,'calendar-agenda-date');
 dateHeading.setAttribute('aria-label',date.toLocaleDateString(state.lang,{weekday:'long',day:'numeric',month:'long'}));
 append(dateHeading,E('strong',date.toLocaleDateString(state.lang,{day:'numeric'}),'calendar-day-number'),E('span',new Intl.DateTimeFormat(state.lang,{day:'numeric',month:'long'}).formatToParts(date).find(part=>part.type==='month')?.value||date.toLocaleDateString(state.lang,{month:'long'})));
 append(agendaHead,E('div',date.toLocaleDateString(state.lang,{weekday:'long'}),'calendar-day-weekday'),dateHeading);
 agenda.append(agendaHead);
 const selected=byDay.get(state.calendarDay)||[];
 if(selected.length){
  const events=E('div',undefined,'calendar-events');
  for(const o of selected){const row=eventRow(o,true);row.dataset.visibility=o.record.visibility;events.append(row);}
  agenda.append(events);
 }else agenda.append(emptyPanel('calendar',t('web_no_events')));
 const add=addButton(copy[3],addEvent);add.classList.add('calendar-add-event');agenda.append(add);
 const picker=E('div',undefined,'calendar-picker');
 const field=input(picker,'calendar-day',t('web_day'),'date',state.calendarDay);
 field.addEventListener('change',()=>{if(field.value)showDate(field.value,'[name=calendar-day]');});
 agenda.append(picker);
}
function queueDelete(r,workspace){
 if(!navigator.onLine){toast(t('web_online'));return;}
 const epoch=privateEpoch,job={timer:null},notification=E('div',undefined,'toast undo');
 append(notification,E('span',t('web_deleted_pending')),button(t('web_cancel'),()=>{clearTimeout(job.timer);pendingDeletes.delete(r.id);notification.remove();render();}));alerts.append(notification);
 pendingDeletes.set(r.id,job);render();
 job.timer=setTimeout(async()=>{notification.remove();if(epoch!==privateEpoch){pendingDeletes.delete(r.id);return;}try{await saveOperation({id:crypto.randomUUID(),action:'record.delete',record_id:r.id,revision:r.revision},workspace);pendingDeletes.delete(r.id);await refresh();render();}catch(error){pendingDeletes.delete(r.id);if(state.session){render();report(error);toast(t('web_delete_failed'));}}},4000);
}

const CLARITY_COPY={
 ru:{web_more:'Ещё',web_transfer_pending:'Ожидает подтверждения до',web_family_transfer:'Передача семейного пространства',web_back_settings:'К настройкам',web_account_data:'Данные аккаунта',web_confirm_delete:'Введите DELETE',web_current_session:'Текущий сеанс',web_last_active:'Последняя активность',web_revoked_on:'Доступ отозван',web_no_sessions:'Нет активных сеансов',web_active_sessions:'Активные сеансы',web_revoked_sessions:'Завершённые сеансы',web_revoke_current_hint:'Вы выйдете из аккаунта в этом браузере.',web_revoke_device_hint:'На выбранном устройстве потребуется войти снова.',web_add_operation:'Добавить операцию',web_history:'История операций',web_filters:'Фильтры',web_analysis:'Аналитика',web_finance_summary:'Сводка',web_all_operations:'Все операции',web_open_task_form:'Задача с деталями'},
 en:{web_more:'More',web_transfer_pending:'Awaiting confirmation until',web_family_transfer:'Family workspace transfer',web_back_settings:'Back to settings',web_account_data:'Account data',web_confirm_delete:'Type DELETE',web_current_session:'Current session',web_last_active:'Last active',web_revoked_on:'Access revoked',web_no_sessions:'No active sessions',web_active_sessions:'Active sessions',web_revoked_sessions:'Ended sessions',web_revoke_current_hint:'You will be signed out in this browser.',web_revoke_device_hint:'This device will need to sign in again.',web_add_operation:'Add transaction',web_history:'Transaction history',web_filters:'Filters',web_analysis:'Analysis',web_finance_summary:'Summary',web_all_operations:'All transactions',web_open_task_form:'Task with details'},
 'uz-Latn':{web_more:'Yana',web_transfer_pending:'Tasdiqlash muddati',web_family_transfer:'Oilaviy makonni topshirish',web_back_settings:'Sozlamalarga qaytish',web_account_data:'Hisob ma’lumotlari',web_confirm_delete:'DELETE yozing',web_current_session:'Joriy seans',web_last_active:'So‘nggi faollik',web_revoked_on:'Ruxsat bekor qilindi',web_no_sessions:'Faol seanslar yo‘q',web_active_sessions:'Faol seanslar',web_revoked_sessions:'Yakunlangan seanslar',web_revoke_current_hint:'Bu brauzerda hisobdan chiqasiz.',web_revoke_device_hint:'Bu qurilmada qayta kirish kerak bo‘ladi.',web_add_operation:'Operatsiya qo‘shish',web_history:'Operatsiyalar tarixi',web_filters:'Filtrlar',web_analysis:'Tahlil',web_finance_summary:'Umumiy holat',web_all_operations:'Barcha operatsiyalar',web_open_task_form:'Tafsilotli vazifa'},
 'uz-Cyrl':{web_more:'Яна',web_transfer_pending:'Тасдиқлаш муддати',web_family_transfer:'Оилавий маконни топшириш',web_back_settings:'Созламаларга қайтиш',web_account_data:'Ҳисоб маълумотлари',web_confirm_delete:'DELETE ёзинг',web_current_session:'Жорий сеанс',web_last_active:'Сўнгги фаоллик',web_revoked_on:'Рухсат бекор қилинди',web_no_sessions:'Фаол сеанслар йўқ',web_active_sessions:'Фаол сеанслар',web_revoked_sessions:'Якунланган сеанслар',web_revoke_current_hint:'Бу браузерда ҳисобдан чиқасиз.',web_revoke_device_hint:'Бу қурилмада қайта кириш керак бўлади.',web_add_operation:'Операция қўшиш',web_history:'Операциялар тарихи',web_filters:'Фильтрлар',web_analysis:'Таҳлил',web_finance_summary:'Умумий ҳолат',web_all_operations:'Барча операциялар',web_open_task_form:'Тафсилотли вазифа'}
};
const WORKSPACE_COPY={
 ru:{web_security_devices:'Защита и устройства',web_google_status_loading:'Проверяем связь с Google…',web_google_status_error:'Не удалось получить статус Google',web_password_change_hint:'После смены пароля нужно будет войти снова.',web_mfa_enable:'Настроить двухфакторную защиту'},
 en:{web_security_devices:'Security and devices',web_google_status_loading:'Checking Google connection…',web_google_status_error:'Could not load Google status',web_password_change_hint:'You’ll need to sign in again after changing your password.',web_mfa_enable:'Set up two-factor authentication'},
 'uz-Latn':{web_security_devices:'Himoya va qurilmalar',web_google_status_loading:'Google ulanishi tekshirilmoqda…',web_google_status_error:'Google holatini olib bo‘lmadi',web_password_change_hint:'Parolni almashtirgach, qayta kirishingiz kerak.',web_mfa_enable:'Ikki bosqichli himoyani sozlash'},
 'uz-Cyrl':{web_security_devices:'Ҳимоя ва қурилмалар',web_google_status_loading:'Google уланиши текширилмоқда…',web_google_status_error:'Google ҳолатини олиб бўлмади',web_password_change_hint:'Паролни алмаштиргач, қайта киришингиз керак.',web_mfa_enable:'Икки босқичли ҳимояни созлаш'}
};
const t=k=>WORKSPACE_COPY[state.lang]?.[k]||WORKSPACE_COPY.en[k]||CLARITY_COPY[state.lang]?.[k]||WEB_COPY[state.lang]?.[k]||WEB_COPY.en[k]||packs[state.lang]?.strings[k]||CLARITY_COPY.en[k]||packs.ru?.strings[k]||k;
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
const ICON_PATHS={calendar:['M8 2v4M16 2v4M3 10h18','M5 4h14a2 2 0 0 1 2 2v14H3V6a2 2 0 0 1 2-2','M8 14h2M14 14h2M8 18h2'],today:['M8 2v4M16 2v4M3 10h18','M5 4h14a2 2 0 0 1 2 2v14H3V6a2 2 0 0 1 2-2','m8 15 2 2 5-5'],tasks:['m3 6 1 1 2-2M10 6h11m-18 6 1 1 2-2M10 12h11m-18 6 1 1 2-2M10 18h11'],notes:['M5 3h14v18H5zM8 8h8M8 12h8M8 16h5'],money:['M4 20V10m6 10V4m6 16v-8m5 8H2'],account:['M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0M4 21v-2a8 8 0 0 1 16 0v2'],close:['m6 6 12 12M6 18 18 6'],forward:['m9 6 6 6-6 6'],back:['m15 6-6 6 6 6'],more:['M5 12h.01M12 12h.01M19 12h.01'],add:['M12 5v14M5 12h14']};
ICON_PATHS.bell=['M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4'];
ICON_PATHS.appearance=['M20.5 13a8.5 8.5 0 0 1-9.5-9.5A8.5 8.5 0 1 0 20.5 13'];
function icon(name){const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');for(const [key,value]of Object.entries({viewBox:'0 0 24 24',fill:'none',stroke:'currentColor','stroke-width':'1.7','stroke-linecap':'round','stroke-linejoin':'round','aria-hidden':'true',focusable:'false',class:'ui-icon'}))svg.setAttribute(key,value);for(const path of ICON_PATHS[name]||[]){const node=document.createElementNS(svg.namespaceURI,'path');node.setAttribute('d',path);svg.append(node);}return svg;}
function iconButton(name,label,run){const b=button('',run,'icon');b.setAttribute('aria-label',label);b.title=label;b.append(icon(name));return b;}
function addButton(label,run){const b=button(label,run,'');b.prepend(icon('add'));return b;}
function anchor(text,path){const a=E('a',text,'button');a.href=path;return a;}
let activeCurrencyPicker=null,currencyPickerDismissReady=false;
const CURRENCY_FALLBACK=['AED','AFN','ALL','AMD','ARS','AUD','AZN','BAM','BDT','BGN','BHD','BND','BOB','BRL','BWP','BYN','CAD','CHF','CLP','CNY','COP','CRC','CZK','DKK','DZD','EGP','EUR','GBP','GEL','GHS','HKD','HUF','IDR','ILS','INR','IQD','ISK','JOD','JPY','KES','KGS','KHR','KRW','KWD','KZT','LAK','LBP','LKR','MAD','MDL','MKD','MNT','MOP','MUR','MXN','MYR','NGN','NOK','NPR','NZD','OMR','PEN','PHP','PKR','PLN','PYG','QAR','RON','RSD','RUB','SAR','SEK','SGD','THB','TJS','TMT','TND','TRY','TWD','TZS','UAH','UGX','USD','UYU','UZS','VND','XAF','XOF','ZAR'];
function currencyInput(n){
 const labels={ru:['Выбрать валюту','Валюты','Валюта не найдена'],en:['Choose currency','Currencies','No currency found'],'uz-Latn':['Valyutani tanlash','Valyutalar','Valyuta topilmadi'],'uz-Cyrl':['Валютани танлаш','Валюталар','Валюта топилмади']}[state.lang]||['Choose currency','Currencies','No currency found'];
 const field=E('div',undefined,'currency-picker'),toggle=E('button',undefined,'currency-picker-toggle'),list=E('div',undefined,'currency-picker-list');
 n.replaceWith(field);field.append(n,toggle,list);n.currencyField=field;
 n.maxLength=64;n.pattern='[A-Za-z]{3}';n.autocomplete='off';n.spellcheck=false;n.autocapitalize='characters';
 n.setAttribute('role','combobox');n.setAttribute('aria-autocomplete','list');n.setAttribute('aria-haspopup','listbox');n.setAttribute('aria-expanded','false');
 list.id=n.id+'-currencies';list.hidden=true;list.setAttribute('role','listbox');list.setAttribute('aria-label',labels[1]);n.setAttribute('aria-controls',list.id);
 toggle.type='button';toggle.tabIndex=-1;toggle.setAttribute('aria-label',labels[0]);toggle.setAttribute('aria-controls',list.id);toggle.setAttribute('aria-expanded','false');toggle.append(E('span','⌄'));toggle.firstChild.setAttribute('aria-hidden','true');
 let codes;
 try{codes=Intl.supportedValuesOf('currency');}catch{codes=CURRENCY_FALLBACK;}
 const common=['RUB','USD','EUR','UZS','KZT','GBP','CNY','AED'];
 codes=[...new Set([...common,...codes])].sort((a,b)=>{
  const ai=common.indexOf(a),bi=common.indexOf(b);return (ai<0?100:ai)-(bi<0?100:bi)||a.localeCompare(b);
 });
 let localNames,englishNames;
 try{localNames=new Intl.DisplayNames([state.lang],{type:'currency'});}catch{}
 try{englishNames=new Intl.DisplayNames(['en'],{type:'currency'});}catch{}
 const normalize=value=>value.normalize('NFKD').replace(/\p{M}/gu,'').toLocaleLowerCase(state.lang).trim();
 const choices=codes.map(code=>({code,name:localNames?.of(code)||code,search:normalize(code+' '+(localNames?.of(code)||'')+' '+(englishNames?.of(code)||''))}));
 let shown=[],active=-1,opened=false,choosing=false,userQuery=false,committed=n.value;
 const usable=()=>n.isConnected&&!n.readOnly&&!n.matches(':disabled');
 const control={field,close};
 function place(){
  if(!opened||!usable()){close();return;}
  const box=n.getBoundingClientRect(),dialog=n.closest('dialog')?.getBoundingClientRect(),viewport=window.visualViewport;
  const top=Math.max(dialog?.top||0,viewport?.offsetTop||0)+12;
  const bottom=Math.min(dialog?.bottom||innerHeight,(viewport?.offsetTop||0)+(viewport?.height||innerHeight))-12;
  const below=bottom-box.bottom,above=box.top-top,up=below<Math.min(220,list.scrollHeight)&&above>below;
  list.classList.toggle('opens-above',up);list.style.maxHeight=Math.min(220,Math.max(48,up?above:below))+'px';
 }
 function close(restore=false){
  if(restore)n.value=committed;
  opened=false;list.hidden=true;active=-1;n.setAttribute('aria-expanded','false');toggle.setAttribute('aria-expanded','false');n.removeAttribute('aria-activedescendant');
  window.removeEventListener('resize',place);window.removeEventListener('scroll',place,true);window.visualViewport?.removeEventListener('resize',place);
  if(activeCurrencyPicker===control)activeCurrencyPicker=null;
 }
 function mark(index){
  active=index;
  for(const [i,option]of [...list.querySelectorAll('[role=option]')].entries()){
   const selected=i===active;option.setAttribute('aria-selected',String(selected));option.classList.toggle('is-active',selected);
  }
  const option=list.querySelectorAll('[role=option]')[active];
  if(!option){n.removeAttribute('aria-activedescendant');return;}
  n.setAttribute('aria-activedescendant',option.id);
  if(option.offsetTop<list.scrollTop)list.scrollTop=option.offsetTop;
  else if(option.offsetTop+option.offsetHeight>list.scrollTop+list.clientHeight)list.scrollTop=option.offsetTop+option.offsetHeight-list.clientHeight;
 }
 function choose(code){
  if(!usable())return;
  choosing=true;n.value=committed=code;userQuery=false;
  n.dispatchEvent(new Event('input',{bubbles:true}));n.dispatchEvent(new Event('change',{bubbles:true}));choosing=false;
  close();n.focus({preventScroll:true});
 }
 function open(query='',all=false){
  if(!usable())return;
  if(activeCurrencyPicker&&activeCurrencyPicker!==control)activeCurrencyPicker.close();
  const needle=normalize(query);shown=choices.filter(choice=>choice.search.includes(needle)).slice(0,all?choices.length:8);
  list.replaceChildren();active=-1;
  for(const [i,choice]of shown.entries()){
   const option=E('button',undefined,'currency-picker-option');option.type='button';option.tabIndex=-1;option.id=list.id+'-'+i;option.setAttribute('role','option');option.setAttribute('aria-selected','false');
   option.append(E('strong',choice.code),E('span',choice.name));
   option.addEventListener('pointerdown',event=>event.preventDefault());option.addEventListener('click',()=>choose(choice.code));list.append(option);
  }
  if(!shown.length)list.append(E('p',labels[2],'currency-picker-empty'));
  opened=true;list.hidden=false;activeCurrencyPicker=control;n.setAttribute('aria-expanded','true');toggle.setAttribute('aria-expanded','true');n.removeAttribute('aria-activedescendant');
  place();window.addEventListener('resize',place);window.addEventListener('scroll',place,true);window.visualViewport?.addEventListener('resize',place);
 }
 n.addEventListener('focus',()=>{if(!opened){committed=n.value;userQuery=false;}});
 n.addEventListener('input',()=>{if(!choosing){userQuery=true;open(n.value);}});
 n.addEventListener('change',()=>{if(/^[a-z]{3}$/i.test(n.value)){n.value=n.value.toUpperCase();committed=n.value;}});
 n.addEventListener('keydown',event=>{
  if(!usable()||event.isComposing)return;
  if(['ArrowDown','ArrowUp'].includes(event.key)){
   event.preventDefault();if(!opened)open(userQuery?n.value:'',true);
   if(shown.length)mark(active<0?(event.key==='ArrowDown'?0:shown.length-1):(active+(event.key==='ArrowDown'?1:-1)+shown.length)%shown.length);
  }else if(event.key==='Enter'&&opened){event.preventDefault();if(active>=0)choose(shown[active].code);else if(shown.length===1)choose(shown[0].code);}
  else if(event.key==='Escape'&&opened){event.preventDefault();event.stopPropagation();close(true);}
 });
 toggle.addEventListener('click',()=>{if(!usable()){close();return;}if(opened){close();n.focus({preventScroll:true});}else{const query=userQuery?n.value:'';n.focus({preventScroll:true});open(query,true);}});
 field.addEventListener('focusout',event=>{if(!field.contains(event.relatedTarget))close();});
 new MutationObserver(()=>{toggle.disabled=n.readOnly||n.disabled;if(!usable())close();}).observe(n,{attributes:true,attributeFilter:['readonly','disabled']});
 if(!currencyPickerDismissReady){
  currencyPickerDismissReady=true;
  document.addEventListener('pointerdown',event=>{if(activeCurrencyPicker&&!activeCurrencyPicker.field.contains(event.target))activeCurrencyPicker.close();},true);
  document.addEventListener('close',()=>activeCurrencyPicker?.close(),true);
 }
 return n;
}
function input(container,name,label,type='text',value='',required=true){const id='input-'+name+'-'+crypto.randomUUID();const l=E('label',label);l.htmlFor=id;const n=E(type==='textarea'?'textarea':'input');n.name=name;n.id=id;if(type!=='textarea')n.type=type;if(type==='email')n.autocomplete='email';if(type==='password')n.autocomplete=['new','next','new-password'].includes(name)?'new-password':'current-password';if(type==='textarea')n.maxLength=20000;if(['name','label'].includes(name))n.maxLength=2000;if(['amount','received'].includes(name))n.inputMode='decimal';if(name==='code'){n.autocomplete='one-time-code';n.spellcheck=false;}n.value=value??'';n.required=required&&type!=='checkbox';append(container,l,n);if(name==='currency')currencyInput(n);return n;}
function select(container,name,label,choices,value){const id='select-'+name+'-'+crypto.randomUUID();const l=E('label',label);l.htmlFor=id;const s=E('select');s.name=name;s.id=id;for(const [v,label]of choices){const o=E('option',label);o.value=v;s.append(o);}s.value=value;append(container,l,s);return s;}
function card(title,body){const c=E('section',undefined,'card');if(title)c.append(E('h2',title));if(body)c.append(E('p',body));return c;}
function form(container,title,build,submit,submitLabel=t('save')){
 const f=E('form');f.noValidate=true;if(title)f.append(E('h2',title));
 const fields=E('fieldset'),values=build(fields)||{},initiallyDisabled=fields.disabled;
 const status=E('p',undefined,'error');status.setAttribute('role','status');
 const b=E('button',submitLabel);b.type='submit';append(f,fields,status,b);
 let pending=false;
 const fieldError=(field,message)=>{
  if(!field)return;
  const id=field.id+'-error';let hint=document.getElementById(id);
  if(!hint){hint=E('p',undefined,'field-error');hint.id=id;(field.currencyField||field).after(hint);}
  hint.textContent=message;field.setAttribute('aria-invalid','true');
  field.setAttribute('aria-describedby',[...new Set([...(field.getAttribute('aria-describedby')||'').split(' ').filter(Boolean),id])].join(' '));
  const options=field.closest('details');if(options)options.open=true;
 };
 f.addEventListener('input',event=>{
  const field=event.target;if(!field.id)return;
  field.removeAttribute('aria-invalid');const id=field.id+'-error';document.getElementById(id)?.remove();
  const descriptions=(field.getAttribute('aria-describedby')||'').split(' ').filter(value=>value&&value!==id);if(descriptions.length)field.setAttribute('aria-describedby',descriptions.join(' '));else field.removeAttribute('aria-describedby');
 });
 f.addEventListener('submit',async event=>{
  event.preventDefault();if(pending)return;
  const invalid=[...f.elements].find(field=>!field.disabled&&typeof field.checkValidity==='function'&&!field.checkValidity());
  if(invalid){fieldError(invalid,invalid.validationMessage);invalid.focus({preventScroll:true});invalid.scrollIntoView({block:'nearest'});return;}
  pending=true;b.disabled=true;status.textContent='';
  try{await submit(values);status.textContent=t('account_done');}
  catch(error){
   const retry=error.uncertain||error.refreshOnly;
   fields.disabled=initiallyDisabled||!!retry;
   b.textContent=retry?t('retry'):submitLabel;
   status.textContent=error.displayMessage||(error.refreshOnly?t('web_saved_refresh'):error.uncertain?t('web_uncertain'):errorText(error));
   const field=['invalid_amount','amount_precision'].includes(error.code)?values.amount:['invalid_currency','currency_mismatch'].includes(error.code)?values.currency:error.code==='invalid_date'?values.date||values.end||values.start:null;
   if(field){fieldError(field,status.textContent);field.focus({preventScroll:true});}
   if(error.code==='unauthorized')report(error);
  }finally{b.disabled=false;pending=false;}
 });
 container.append(f);return f;
}
function dialogClose(d){
 const close=iconButton('close',t('close'),()=>d.close());
 close.classList.add('dialog-close');
 return close;
}
function dialogHeading(d,title){
 title.id='dialog-'+crypto.randomUUID();
 title.tabIndex=-1;
 title.autofocus=true;
 const head=E('div',undefined,'dialog-head');
 append(head,title,dialogClose(d));
 d.setAttribute('aria-labelledby',title.id);
 return head;
}
function dialog(title,build){
 const d=E('dialog');
 d.dataset.workspace=state.space||'';
 const heading=E('h2',title);
 d.append(dialogHeading(d,heading));
 build(d);
 document.body.append(d);
 d.addEventListener('close',()=>d.remove());
 d.showModal();
 heading.focus({preventScroll:true});
 return d;
}
function replaceDialog(d,...nodes){
 const heading=nodes.find(n=>n.tagName==='H2')||E('h2','ULADIM');
 const existing=nodes.find(n=>n.tagName==='BUTTON'&&n.textContent===t('close'));
 const head=dialogHeading(d,heading);
 if(existing){
  existing.className='icon dialog-close';
  existing.setAttribute('aria-label',t('close'));
  existing.replaceChildren(icon('close'));
  head.lastChild.replaceWith(existing);
 }
 d.replaceChildren(head,...nodes.filter(n=>n!==heading&&n!==existing));
 heading.focus({preventScroll:true});
}

const SESSION_COPY={
 ru:{title:'Выйти из аккаунта?',hint:'Сеанс завершится только в этом браузере. Ваши записи останутся в аккаунте.',stay:'Остаться в ULADIM',cancel:'Отменить',done:'Вы вышли из аккаунта',googleDisconnect:'Отключить Google',googleHint:'После отключения потребуется войти с паролем. Другие данные аккаунта сохранятся.'},
 en:{title:'Sign out of your account?',hint:'This ends the session in this browser. Your records stay in your account.',stay:'Stay in ULADIM',cancel:'Cancel',done:'You have signed out',googleDisconnect:'Disconnect Google',googleHint:'You will need to sign in with your password afterwards. Your account data will be kept.'},
 'uz-Latn':{title:'Hisobdan chiqasizmi?',hint:'Faqat shu brauzerdagi seans tugaydi. Yozuvlaringiz hisobingizda qoladi.',stay:'ULADIMda qolish',cancel:'Bekor qilish',done:'Hisobdan chiqdingiz',googleDisconnect:'Google ulanishini uzish',googleHint:'Keyin parol bilan kirishingiz kerak. Hisob ma’lumotlari saqlanadi.'},
 'uz-Cyrl':{title:'Ҳисобдан чиқасизми?',hint:'Фақат шу браузердаги сеанс тугайди. Ёзувларингиз ҳисобингизда қолади.',stay:'ULADIMда қолиш',cancel:'Бекор қилиш',done:'Ҳисобдан чиқдингиз',googleDisconnect:'Google уланишини узиш',googleHint:'Кейин парол билан киришингиз керак. Ҳисоб маълумотлари сақланади.'}
};
const sessionCopy=key=>(SESSION_COPY[state.lang]||SESSION_COPY.en)[key];
function settingsInline(title,build,trigger){
 const host=root.querySelector('.settings-content');if(!host)return;
 host.querySelectorAll('.settings-inline-panel').forEach(panel=>panel.close());
 const panel=card();panel.classList.add('settings-inline-panel');
 panel.close=()=>{panel.remove();trigger?.setAttribute('aria-expanded','false');if(trigger?.isConnected)trigger.focus({preventScroll:true});};
 panel.append(E('h3',title));
 if(trigger){trigger.setAttribute('aria-expanded','true');trigger.after(panel);}else host.append(panel);
 build(panel);
 const cancel=button(sessionCopy('cancel'),()=>panel.close(),'text-button inline-cancel');panel.append(cancel);
 panel.querySelector('input')?.focus({preventScroll:true});panel.scrollIntoView({block:'nearest',behavior:'auto'});
 return panel;
}
async function finishSignOut(){
 try{await call('logout',{});}catch(error){error.displayMessage={ru:'Не удалось подтвердить выход. Проверьте подключение и повторите.',en:'Could not confirm sign-out. Check your connection and retry.','uz-Latn':'Chiqish tasdiqlanmadi. Ulanishni tekshiring va takrorlang.','uz-Cyrl':'Чиқиш тасдиқланмади. Уланишни текширинг ва такрорланг.'}[state.lang]||'Could not confirm sign-out. Check your connection and retry.';throw error;}
 clearNoteDrafts();clearTaskActions();clearIdentity();sessionEvents?.postMessage('signed-out');login();
 const status=E('p',sessionCopy('done'),'signout-success');status.setAttribute('role','status');root.querySelector('.auth-form-panel')?.prepend(status);
}
function signoutPage(host){
 const panel=card(sessionCopy('title'),sessionCopy('hint'));panel.classList.add('signout-panel');
 panel.append(E('p',state.session.email,'account-email'));
 form(panel,'',()=>({}),finishSignOut,t('family_logout'));
 panel.append(button(sessionCopy('stay'),()=>openSettings(''),'secondary'));
 host.append(panel);
}

function clearIdentity(){redrawFinance=null;backgroundDirty=false;refreshTail=Promise.resolve();privateEpoch++;state.generation++;for(const job of pendingDeletes.values())clearTimeout(job.timer);pendingDeletes.clear();quickTasks.clear();taskChanges.clear();alerts.replaceChildren();Object.assign(state,{session:null,csrf:'',space:null,spaces:[],roster:null,records:[],financeFilters:{},taskQuery:'',taskStatus:'all',settingsTab:'',referenceSection:'',lastRead:0,syncState:'idle',syncSpace:null,syncCursor:0,syncEpoch:'',tab:'today',busy:false});document.querySelectorAll('dialog').forEach(d=>{d.close();d.remove();});}
function money(value,currency){return ULADIMMoney.format(value,currency,state.lang);}
function moneyParts(value,currency,prefix=''){
 const full=prefix+money(value,currency);
 return {full,number:full.slice(0,-currency.length-1),currency};
}
function setMoneyElement(node,value,currency,prefix=''){
 const parts=moneyParts(value,currency,prefix);node.classList.add('money-display');node.setAttribute('aria-label',parts.full);
 node.replaceChildren(E('span',parts.number,'money-number'),document.createTextNode(' '),E('span',parts.currency,'money-currency'));return node;
}
function moneyElement(value,currency,cls='',prefix='',tag='strong'){
 return setMoneyElement(E(tag,undefined,cls),value,currency,prefix);
}
function displayDate(date){return new Date(date+'T12:00:00').toLocaleDateString(state.lang,{year:'numeric',month:'short',day:'numeric'});}
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
let refreshTail=Promise.resolve();
const SYNC_COPY={
 ru:['Обновление…','Не удалось обновить','Обновлено','Нет сети','Сменить тему'],
 en:['Refreshing…','Refresh failed','Updated','Offline','Switch theme'],
 'uz-Latn':['Yangilanmoqda…','Yangilanmadi','Yangilandi','Tarmoq yo‘q','Mavzuni almashtirish'],
 'uz-Cyrl':['Янгиланмоқда…','Янгиланмади','Янгиланди','Тармоқ йўқ','Мавзуни алмаштириш']
};
function updateSyncStatus(){
 const node=root.querySelector('.workspace-sync');if(!node)return;
 const copy=SYNC_COPY[state.lang]||SYNC_COPY.en;
 const index=!navigator.onLine?3:state.syncState==='loading'?0:state.syncState==='error'?1:2;
 node.textContent=copy[index]+(index===2&&state.lastRead?' · '+new Date(state.lastRead).toLocaleTimeString(state.lang,{hour:'2-digit',minute:'2-digit'}):'');
 node.dataset.status=index===1?'error':index===3?'offline':'read';
}
function refresh(){const epoch=privateEpoch;const run=async()=>{if(epoch!==privateEpoch)return;state.busy=true;state.syncState='loading';updateSyncStatus();try{const result=await call('spaces');state.spaces=result.spaces;if(!state.spaces.some(s=>s.id===state.space))state.space=state.spaces[0]?.id||null;await readSpace();if(epoch===privateEpoch&&(!state.space||state.syncSpace===state.space)){state.lastRead=Date.now();state.syncState='read';}}catch(error){if(epoch===privateEpoch)state.syncState='error';throw error;}finally{if(epoch===privateEpoch){state.busy=false;updateSyncStatus();}}};const pending=refreshTail.then(run,run);refreshTail=pending.catch(()=>{});return pending;}
async function start(){state.session=await call('session');state.csrf=state.session.csrf;await refresh();await consumeNotificationLink();render();refreshNotificationTimezone();}
function login(){
 delete document.body.dataset.referenceLayout;
 root.replaceChildren();
 const m=E('main',undefined,'login focus-login');
 const brand=E('a','ULADIM','brand focus-login-brand');
 brand.href='/';
 append(m,brand,E('h1',t('family_login')));
 root.append(m);
 form(m,'',f=>{
  const email=input(f,'email',t('family_email'),'email');
  email.autocomplete='username';
  return {email,password:input(f,'password',t('web_password'),'password')};
 },async v=>{
  let r;
  try { r=await call('login',{email:v.email.value,password:v.password.value}); }
  finally { v.password.value=''; }
  if(r.mfa_required){mfaStep(r.challenge);return;}
  state.csrf=r.csrf;
  await start();
 },t('family_login'));
 if(state.googleEnabled){
  const divider=E('div',(SIGNUP_COPY[state.lang]||SIGNUP_COPY.en).or,'focus-login-divider');
  divider.setAttribute('aria-hidden','true');
  append(m,divider,button(t('account_google_sign_in'),()=>beginGoogle(),'focus-login-google'));
 }
 const actions=E('div',undefined,'focus-login-links');
 append(actions,button(t('family_register'),signup),button(t('family_recovery'),recover));
 m.append(actions);
 const locale=E('div',undefined,'focus-login-language');
 language(locale);
 m.append(locale);
 const panel=E('div',undefined,'auth-form-panel');
 panel.append(...m.childNodes);
 m.append(focusLoginStory(E,state.lang),panel);
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


async function beginGoogle(invitation){
 const result=await call('google/start',invitation?{invitation}:{});
 location.assign(result.authorization_url);
}
async function googleReturn(){
 history.replaceState(null,'','/app');
 const result=await call('google/complete',{});
 if(result.error){login();const message=E('p',errorText({code:result.error}));message.setAttribute('role','alert');root.querySelector('main').append(message);return;}
 if(result.mfa_required){mfaStep(result.challenge);return;}
 if(result.linked){state.tab='account';state.settingsTab='security';}
 await start();if(result.linked)toast(t('account_done'));
}
function mfaStep(challenge){
 root.replaceChildren();const m=E('main',undefined,'login');append(m,E('a','ULADIM','brand'),E('h1',t('account_mfa')),E('p',t('web_mfa_hint')));root.append(m);
 form(m,'',f=>({code:input(f,'code',t('family_code'))}),async v=>{let r;try{r=await call('login/mfa',{challenge,code:v.code.value.trim()});}catch(error){if(error.code==='invalid_credentials')error.code='mfa_invalid';throw error;}finally{v.code.value='';}challenge='';state.csrf=r.csrf;await start();},t('family_login'));
 m.append(button(t('cancel'),()=>{challenge='';login();}));m.querySelector('input').focus();
}

function language(container){const s=select(container,'language',t('language'),Object.entries(packs).map(([k,v])=>[k,v.name+(WEB_COPY[k]?'':' · '+t('web_partial_short'))]),state.lang);s.addEventListener('change',()=>{state.lang=s.value;preferences();if(state.session)render();else login();});}
document.addEventListener('pointerdown',event=>{
 const menu=root.querySelector('.nav-more[open]');
 if(menu&&!menu.contains(event.target))menu.open=false;
});
const REFERENCE_COPY={
 ru:['Планирование','Финансы','Пространство','Обзор финансов','Семья и участники','Добро пожаловать','Задачи к выполнению','Расходы за месяц','Ближайшее событие','Моё пространство','Последние операции','Счета','Лаванда','Баланс счетов'],
 en:['Planning','Finances','Workspace','Financial overview','Family and members','Welcome back','Tasks to do','Monthly expenses','Next event','My workspace','Recent transactions','Accounts','Lavender','Account balances'],
 'uz-Latn':['Rejalashtirish','Moliya','Makon','Moliya sharhi','Oila va a’zolar','Xush kelibsiz','Bajariladigan vazifalar','Oylik xarajatlar','Keyingi tadbir','Mening makonim','Oxirgi operatsiyalar','Hisoblar','Lavanda','Hisoblar balansi'],
 'uz-Cyrl':['Режалаштириш','Молия','Макон','Молия шарҳи','Оила ва аъзолар','Хуш келибсиз','Бажариладиган вазифалар','Ойлик харажатлар','Кейинги тадбир','Менинг маконим','Охирги операциялар','Ҳисоблар','Лаванда','Ҳисоблар баланси']
};
function referenceCopy(index){return (REFERENCE_COPY[state.lang]||REFERENCE_COPY.en)[index];}
function referenceNavigate(tab,section=''){
 state.referenceSection=section;state.tab=tab;
 if(tab==='account')state.settingsTab=section;
 render();window.scrollTo(0,0);
 const heading=root.querySelector('main h1');if(heading){heading.tabIndex=-1;heading.dataset.focusTarget='true';heading.focus({preventScroll:true});}
}
function shell(){
 const previousMenu=root.querySelector('.nav-more');
 const keepMenu=previousMenu?.open&&previousMenu.dataset.tab===state.tab;
 navObserver?.disconnect();root.replaceChildren();document.body.dataset.referenceLayout='b12';
 const header=E('header'),nav=E('nav',undefined,'nav reference-sidebar');nav.setAttribute('aria-label','ULADIM');
 const brand=E('a','ULADIM','brand');brand.href='/app';nav.append(brand);
 const spaces=select(E('div'),'workspace','',state.spaces.map(s=>[s.id,s.name]),state.space);spaces.setAttribute('aria-label',t('family_account'));spaces.className='workspace';spaces.title=currentSpace()?.name||t('family_account');spaces.addEventListener('change',async()=>{document.querySelectorAll('dialog').forEach(d=>d.close());state.generation++;state.lastRead=0;state.syncState='loading';state.space=spaces.value;state.records=[];state.syncSpace=null;state.syncCursor=0;state.syncEpoch='';state.roster=null;render();try{await refresh();render();}catch(e){report(e);}});
 const workspaceCard=E('div',undefined,'reference-workspace');
 append(workspaceCard,E('span',(currentSpace()?.name||'U').slice(0,1).toLocaleUpperCase(state.lang),'reference-avatar'),spaces);nav.append(workspaceCard);
 const secondary=E('details',undefined,'nav-more');secondary.dataset.tab=state.tab;secondary.open=Boolean(keepMenu);
 const summary=E('summary');append(summary,icon('more'),E('span',t('web_more')));secondary.append(summary);
 const menu=E('div',undefined,'nav-menu');secondary.append(menu);
 secondary.addEventListener('keydown',event=>{if(event.key==='Escape'&&secondary.open){event.preventDefault();secondary.open=false;summary.focus();}});
 const makeItem=(tab,label,symbol,section='')=>{
  const item=button('',()=>referenceNavigate(tab,section),'reference-nav-item');item.dataset.tab=tab;item.dataset.section=section;
  append(item,icon(symbol),E('span',label));
  const activeSection=tab==='money'?(state.referenceSection==='report'?'accounts':state.referenceSection||''):tab==='account'?(state.settingsTab==='family'?'family':''):'';
  if(state.tab===tab&&activeSection===section)item.setAttribute('aria-current','page');
  if(tab==='tasks'){const count=records('task').filter(r=>!r.data.completed).length;if(count)item.append(E('span',String(count),'reference-nav-count'));}
  return item;
 };
 const planning=E('div',undefined,'reference-nav-group');planning.append(E('p',referenceCopy(0),'reference-nav-label'));
 for(const [tab,label,symbol]of [['today','today','today'],['tasks','widget_tasks','tasks'],['calendar','web_calendar','calendar'],['notes','widget_notes','notes']])planning.append(makeItem(tab,t(label),symbol));
 const finances=E('div',undefined,'reference-nav-group reference-finance-group');finances.append(E('p',referenceCopy(1),'reference-nav-label'));
 finances.append(makeItem('money',referenceCopy(3),'money'),makeItem('money',referenceCopy(11),'money','accounts'),makeItem('money',t('web_finance_transactions'),'money','ledger'),makeItem('money',t('web_finance_budgets'),'money','budgets'));
 const importItem=button(statementCopy('title'),importStatement,'reference-nav-item');importItem.prepend(icon('notes'));finances.append(importItem);
 const spaceGroup=E('div',undefined,'reference-nav-group reference-space-group');spaceGroup.append(E('p',referenceCopy(2),'reference-nav-label'),makeItem('account',referenceCopy(4),'account','family'));
 append(nav,planning,finances,spaceGroup);
 // Existing destinations stay reachable in the compact phone menu.
 menu.append(makeItem('notes',t('widget_notes'),'notes'),makeItem('account',t('profile'),'account'),makeItem('account',referenceCopy(4),'account','family'));
 const profile=()=>referenceNavigate('account');
 const footer=E('div',undefined,'reference-sidebar-footer');
 const status=E('span',undefined,'workspace-sync');status.setAttribute('role','status');footer.append(status);
 footer.append(button(t('account_support'),()=>referenceNavigate('account','support'),'text-button reference-help'));
 const identity=button('',profile,'reference-identity');identity.setAttribute('aria-label',t('profile'));append(identity,E('span',(state.session.email||'U').slice(0,1).toLocaleUpperCase(state.lang),'reference-avatar'),E('span',state.session.email||t('profile')));footer.append(identity,button(t('family_logout'),()=>openSettings('signout'),'text-button reference-signout'));nav.append(footer,secondary);
 const compactMoney=makeItem('money',t('finances'),'money');compactMoney.classList.add('reference-compact-money');nav.append(compactMoney);
 const compactProfile=makeItem('account',t('profile'),'account');compactProfile.classList.add('reference-compact-profile');nav.append(compactProfile);
 const pageLabels={today:'today',tasks:'widget_tasks',calendar:'web_calendar',notes:'widget_notes',money:'finances',account:'profile'};
 const crumbs=E('div',undefined,'reference-breadcrumb');append(crumbs,E('span',currentSpace()?.name||referenceCopy(9)),icon('forward'),E('strong',t(pageLabels[state.tab]||'today')));
 const tools=E('div',undefined,'header-tools');
 const date=button(new Date().toLocaleDateString(state.lang,{day:'numeric',month:'long',year:'numeric'}),()=>{state.calendarDay=localDate();referenceNavigate('calendar');},'secondary reference-date');date.prepend(icon('calendar'));
 const toolLabels={ru:['Тема','Профиль'],en:['Theme','Profile'],'uz-Latn':['Mavzu','Profil'],'uz-Cyrl':['Мавзу','Профил']}[state.lang]||['Theme','Profile'];
 const theme=button('',()=>{const dark=state.theme==='dark'||(state.theme==='system'&&matchMedia('(prefers-color-scheme:dark)').matches);state.theme=dark?'light':'dark';preferences();redrawFinance?.();},'icon header-theme');theme.append(icon('appearance'),E('span',toolLabels[0],'header-tool-label'));theme.setAttribute('aria-label',(SYNC_COPY[state.lang]||SYNC_COPY.en)[4]);
 const profileButton=button('',profile,'icon header-profile');profileButton.append(E('span',(state.session.email||'U').slice(0,1).toLocaleUpperCase(state.lang),'reference-avatar'),E('span',toolLabels[1],'header-tool-label'));profileButton.setAttribute('aria-label',t('profile'));
 append(tools,date,theme,profileButton);append(header,crumbs,tools);
 root.append(header,nav);
 if(!navigator.onLine){const n=E('div',t('web_online'));n.id='network';root.append(n);}
 const m=E('main');m.id='content';root.append(m);updateSyncStatus();
 let frame=0;
 const measure=()=>{frame=0;if(!nav.isConnected)return;document.body.style.setProperty('--nav-height',nav.getBoundingClientRect().height+'px');document.body.style.setProperty('--app-header-height',header.getBoundingClientRect().height+'px');document.body.style.setProperty('--header-controls-width',tools.getBoundingClientRect().width+'px');};
 measure();navObserver=new ResizeObserver(()=>{if(!frame)frame=requestAnimationFrame(measure);});navObserver.observe(nav);navObserver.observe(header);navObserver.observe(tools);return m;
}
function title(m,label,add){const intro=E('div',undefined,'intro');const a=E('div');if(label==='today')a.append(E('div',new Date().toLocaleDateString(state.lang,{day:'numeric',month:'long',weekday:'long'}),'eyebrow'));a.append(E('h1',t(label)));intro.append(a);if(add)intro.append(addButton(t('add'),add));m.append(intro);}
function render(){redrawFinance=null;if(!state.session){login();return;}const view=[state.tab,state.settingsTab||'',state.referenceSection||''].join('/'),previous=root.querySelector('main')?.dataset.view;const m=shell();m.dataset.view=view;if(previous!==view)m.classList.add('view-enter');backgroundDirty=false;if(state.tab==='account'){account(m);return;}if(!state.space){onboarding(m);return;}
 if(state.tab==='today')today(m);else if(state.tab==='tasks')listTasks(m);else if(state.tab==='calendar')calendar(m);else if(state.tab==='notes')listNotes(m);else if(state.tab==='money')finance(m);
}
function openTabSection(tab,selector){
 state.referenceSection=tab==='money'?({'#finance-ledger':'ledger','#finance-accounts':'accounts','#finance-budgets':'budgets','#finance-analysis':'analysis'}[selector]||''):'';
 state.tab=tab;
 render();
 if(tab==='money'){
  window.scrollTo(0,0);
  const heading=root.querySelector('main h1');if(heading){heading.tabIndex=-1;heading.dataset.focusTarget='true';heading.focus({preventScroll:true});}
  return;
 }
 const section=root.querySelector(selector);
 if(!section)return;
 section.tabIndex=-1;section.dataset.focusTarget='true';
 section.focus({preventScroll:true});
 section.scrollIntoView({block:'start'});
}
function taskActionKey(slot){
 const account=state.session?.user_id;
 return account&&state.space?'uladim-task-action:'+account+':'+state.space+':'+slot:'';
}
function readTaskAction(key){
 if(!key)return null;
 try{
  const action=JSON.parse(sessionStorage.getItem(key)||'null'),op=action?.operation;
  if(op?.action==='record.put'&&op.kind==='task'&&typeof op.id==='string'&&typeof op.record_id==='string'&&typeof op.data?.title==='string')return action;
 }catch{}
 return null;
}
function storeTaskAction(key,operation,accepted=false,conflict=false){
 if(!key)return false;
 try{
  if(operation)sessionStorage.setItem(key,JSON.stringify({operation,accepted,conflict}));
  else sessionStorage.removeItem(key);
  return true;
 }catch{return false;}
}
function clearTaskActions(){
 const account=state.session?.user_id;
 if(!account)return;
 const prefix='uladim-task-action:'+account+':';
 try{
  for(let i=sessionStorage.length-1;i>=0;i--){
   const key=sessionStorage.key(i);
   if(key?.startsWith(prefix))sessionStorage.removeItem(key);
  }
 }catch{}
}
function pendingTaskMessage(accepted){return t(accepted?'web_saved_refresh':'web_task_unconfirmed');}
function onboarding(m){
 m.classList.add('onboarding');const c=card();c.classList.add('setup-panel');c.append(icon('today'),E('h1',t('welcome_title')),E('p',t('web_onboarding')),addButton(t('web_personal_create'),()=>createSpace('personal')));const alternative=E('div',undefined,'setup-alternative');alternative.append(button(t('family_accept'),acceptInvite,'text-button'));append(m,c,alternative);
}
function referenceSummaryTile(container,kind,label,value,symbol,run,detail=''){
 const item=button('',run,'reference-summary-tile');item.dataset.summary=kind;
 append(item,icon(symbol),E('span',label,'reference-tile-label'));
 if(Array.isArray(value)){
  const amounts=E('span',undefined,'reference-tile-currencies');
  for(const entry of value){
   const full=money(entry.amount,entry.currency),row=E('span',undefined,'summary-currency-row');row.dataset.currency=entry.currency;row.setAttribute('aria-label',full);
   append(row,E('span',entry.currency,'summary-currency-code'),E('strong',full.slice(0,-entry.currency.length-1),'summary-currency-amount'));amounts.append(row);
  }
  item.append(amounts);
 }else item.append(E('strong',value));
 if(detail)item.append(E('span',detail,'reference-tile-detail'));
 container.append(item);return item;
}
function today(m){
 title(m,'today');m.classList.add('today-page');m.querySelector('.intro').append(addButton(t('web_add_task'),()=>editRecord('task')));
 const tasks=records('task'),open=tasks.filter(r=>!r.data.completed),done=tasks.length-open.length;
 const day=localDate(),end=new Date(day+'T12:00:00');end.setDate(end.getDate()+8);
 const occurrences=ULADIMDomain.occurrences(records('event'),day,dateString(end));
 const dayEvents=occurrences.filter(o=>o.day===day),upcoming=occurrences.filter(o=>o.day!==day);
 const tiles=E('div',undefined,'reference-summary');
 const tile=(kind,label,value,symbol,run,detail='')=>referenceSummaryTile(tiles,kind,label,value,symbol,run,detail);
 tile('tasks',referenceCopy(6),String(open.length),'tasks',()=>referenceNavigate('tasks'),t('web_today_progress').replace('{done}',done).replace('{total}',tasks.length));
 const monthly=records('transaction').filter(r=>r.data.date.slice(0,7)===day.slice(0,7)),currencies=[...new Set([...monthly,...records('account')].map(r=>r.data.currency))];
 const expenses=currencies.map(currency=>({currency,amount:financeTotals(monthly,currency).expense}));
 tile('expenses',referenceCopy(7),expenses.length?expenses:'—','money',()=>referenceNavigate('money'),new Date(day+'T12:00:00').toLocaleDateString(state.lang,{month:'long'}));
 const next=occurrences.find(o=>o.day>day||o.allDay||o.at>=Date.now());
 tile('event',referenceCopy(8),next?.record.data.title||'—','calendar',()=>referenceNavigate('calendar'),next?next.day+' · '+(next.allDay?t('web_all_day'):next.time):t('web_no_events'));
 tile('workspace',referenceCopy(9),currentSpace()?.name||referenceCopy(9),'account',()=>referenceNavigate('account','family'),t(currentSpace()?.kind==='family'?'family_account':'family_private'));
 m.append(tiles);
 const grid=E('div',undefined,'today-grid');
 const side=E('div',undefined,'today-side');
 m.append(grid);
 const a=card(t('open_tasks'));
 a.classList.add('today-tasks');
 const progress=E('progress');progress.max=tasks.length||1;progress.value=done;
 progress.setAttribute('aria-label',t('completed')+' '+done+' / '+tasks.length);
 const taskHead=E('div',undefined,'today-task-head');
 const count=t('web_today_progress').replace('{done}',done).replace('{total}',tasks.length);
 append(taskHead,a.firstElementChild,E('span',count,'small'));
 a.prepend(append(E('div',undefined,'today-progress'),taskHead,progress));
 const quick=E('form',undefined,'quick-capture'),field=E('input');
 field.name='quick-task';field.placeholder=t('web_quick_task');field.setAttribute('aria-label',t('web_quick_task'));
 field.maxLength=2000;field.required=true;field.enterKeyHint='done';
 const submit=E('button',undefined,'primary icon');submit.type='submit';
 const feedback=E('p',undefined,'quick-capture-status');feedback.setAttribute('role','status');
 append(quick,field,submit);append(a,quick,feedback);
 const workspace=state.space,epoch=privateEpoch,key=taskActionKey('quick');
 const saved=readTaskAction(key);
 const pendingCreate=readTaskAction(taskActionKey('create'));
 quick.hidden=!!pendingCreate&&!saved;
 if(quick.hidden)a.insertBefore(button(t('web_task_retry_create'),()=>editRecord('task'),'secondary'),feedback);
 const draft=quickTasks.get(workspace)||{title:saved?.operation.data.title||'',operation:saved?.operation||null,
  accepted:!!saved?.accepted,busy:false,message:saved?pendingTaskMessage(saved.accepted):''};
 quickTasks.set(workspace,draft);
 field.value=draft.title;
 field.addEventListener('input',()=>{draft.title=field.value;draft.message='';updateQuick();});
 function updateQuick(){
  submit.disabled=draft.busy;
  field.readOnly=!!draft.operation;
  submit.setAttribute('aria-label',t(draft.operation&&!draft.busy?'retry':'web_add_task'));
  submit.replaceChildren(draft.operation&&!draft.busy?document.createTextNode('↻'):icon('add'));
  feedback.hidden=!draft.message;feedback.textContent=draft.message;
 }
 updateQuick();
 quick.addEventListener('submit',async e=>{
  e.preventDefault();
  if(draft.busy||state.space!==workspace||privateEpoch!==epoch)return;
  const title=field.value.trim();
  if(!title){draft.message=errorText({code:'invalid_input'});updateQuick();return;}
  const space=currentSpace();
  draft.operation??={id:crypto.randomUUID(),action:'record.put',record_id:crypto.randomUUID(),
   revision:0,kind:'task',visibility:space?.role==='child'?'shared':'private',
   audience:space?.role==='child'?[space.profile_id]:[],
   data:{title,completed:0,assignment:'any',assignees:[],review:0}};
  const durable=storeTaskAction(key,draft.operation,draft.accepted);
  draft.title=field.value;draft.message='';draft.busy=true;updateQuick();
  try{
   if(!draft.accepted){
    await saveOperation(draft.operation,workspace);
    if(privateEpoch!==epoch)return;
    draft.accepted=true;storeTaskAction(key,draft.operation,true);
   }
   if(state.space===workspace)await refresh();
   if(privateEpoch!==epoch)return;
   storeTaskAction(key,null);
   quickTasks.delete(workspace);
   if(state.space===workspace&&['today','tasks'].includes(state.tab))render();
  }catch(error){
   if(privateEpoch!==epoch)return;
   if(!draft.accepted&&!error.uncertain&&error.code!=='unauthorized'){
    draft.operation=null;storeTaskAction(key,null);
   }
   if(error.code==='unauthorized')report(error);
   else draft.message=draft.operation?(durable?pendingTaskMessage(draft.accepted):t('web_task_tab_only')):errorText(error);
  }finally{
   draft.busy=false;
   if(privateEpoch===epoch&&state.space===workspace&&state.tab==='today'){
    if(quick.isConnected)updateQuick();
    else if(quickTasks.get(workspace)===draft)render();
   }
  }
 });
 for(const [index,r]of open.slice(0,6).entries()){const row=taskRow(r);if(index>=3)row.classList.add('today-task-secondary');a.append(row);}if(!open.length)a.append(emptyPanel('tasks',t('empty_tasks')));
 const taskActions=E('div',undefined,'task-actions');
 taskActions.append(button(t('web_all_tasks'),()=>openTabSection('tasks','main h1'),'text-button'));
 if(!pendingCreate&&!draft.operation)taskActions.append(button(t('web_open_task_form'),()=>editRecord('task'),'text-button'));
 const primary=E('div',undefined,'today-primary');
 a.append(taskActions);primary.append(a);append(grid,primary,side);
 const shortcuts=E('nav',undefined,'today-secondary-actions');shortcuts.setAttribute('aria-label',t('today'));
 const calendarShortcut=button(t('web_calendar'),()=>referenceNavigate('calendar'),'secondary');calendarShortcut.prepend(icon('calendar'));
 const workspaceShortcut=button(referenceCopy(4),()=>referenceNavigate('account','family'),'secondary');workspaceShortcut.prepend(icon('account'));
 append(shortcuts,calendarShortcut,workspaceShortcut);grid.append(shortcuts);

 const finance=card(t('finances'));
 finance.classList.add('today-finance');
 const financeHead=E('div',undefined,'today-finance-head');
 const history=button(t('web_history'),()=>openTabSection('money','#finance-ledger'),'text-button');
 append(financeHead,finance.firstElementChild,history);
 finance.append(financeHead);
 const balanceBlock=E('div',undefined,'reference-balance');finance.append(balanceBlock);
 const reportCurrency=currencies[0];
 for(const currency of currencies){
  const accounts=records('account').filter(r=>r.data.currency===currency);
  if(!accounts.length)continue;
  const sum=accounts.reduce((total,account)=>total+balance(account),0n);
  const line=E('div');append(line,E('span',referenceCopy(13),'small'),moneyElement(sum,currency));balanceBlock.append(line);
 }
 if(!balanceBlock.children.length)balanceBlock.append(E('p',t('empty_money'),'empty'));
 const financeCanvas=E('canvas',undefined,'reference-finance-chart');financeCanvas.width=720;financeCanvas.height=320;
 financeCanvas.setAttribute('aria-label',t('income')+' · '+t('expense'));financeCanvas.setAttribute('role','img');
 if(reportCurrency&&monthly.some(r=>r.data.currency===reportCurrency)){
  finance.append(financeCanvas);
  redrawFinance=()=>drawChart(financeCanvas,reportCurrency,monthly,'smooth');requestAnimationFrame(redrawFinance);
  const totals=financeTotals(monthly,reportCurrency),legend=E('div',undefined,'reference-finance-legend');
  for(const kind of ['income','expense']){const line=E('span',undefined,kind);append(line,document.createTextNode(t(kind)+' · '),moneyElement(totals[kind],reportCurrency,'','','span'));legend.append(line);}finance.append(legend);
 }else finance.append(E('p',t('empty_money'),'empty'));

 finance.append(button(t('web_add_operation'),()=>editRecord('transaction'),'text-button today-add-operation'));
 side.append(finance);

 if(dayEvents.length){
  const schedule=card(t('web_today_schedule'));
  schedule.classList.add('today-schedule');
  const timeline=E('ol',undefined,'today-timeline');
  for(const [index,o]of dayEvents.entries()){
   const item=E('li');if(index>=3)item.classList.add('today-event-secondary');
   const time=o.allDay?E('span',t('web_all_day')):E('time',o.time);
   if(!o.allDay)time.dateTime=new Date(o.at).toISOString();
   append(item,time,button(o.record.data.title,()=>editRecord('event',o.record),'text-button'));
   timeline.append(item);
  }
  schedule.append(timeline);
  if(dayEvents.length>3){const more=button(t('web_calendar')+' · '+dayEvents.length,()=>{state.calendarDay=day;calendarMode='day';referenceNavigate('calendar');},'text-button today-schedule-more');schedule.append(more);}
  side.append(schedule);
 }
 const agenda=card(t('web_upcoming'));
 agenda.classList.add('today-agenda');
 const week=E('div',undefined,'today-week');
 const currentDay=new Date(day+'T12:00:00');
 const monday=offsetDate(currentDay,-((currentDay.getDay()+6)%7));
 for(let i=0;i<7;i++){
  const date=offsetDate(monday,i),key=dateString(date);
  const control=button(undefined,()=>{
   state.calendarDay=key;calendarMode='day';openTabSection('calendar','.calendar-agenda');
  },'secondary');
  const weekday=date.toLocaleDateString(state.lang,{weekday:'short'});
  append(control,E('span',weekday,'today-weekday'),E('strong',String(date.getDate())));
  control.setAttribute('aria-label',date.toLocaleDateString(state.lang,{weekday:'long',day:'numeric',month:'long'}));
  if(key===day)control.setAttribute('aria-current','date');
  week.append(control);
 }
 agenda.append(week);
 for(const o of upcoming.slice(0,3))agenda.append(eventRow(o));
 if(!upcoming.length)agenda.append(E('p',t('web_no_events'),'empty'));
 const agendaActions=E('div',undefined,'task-actions');
 append(agendaActions,button(t('web_calendar'),()=>{state.tab='calendar';render();},'text-button'),
  addButton(t('family_kind_event'),()=>editRecord('event')));
 agenda.append(agendaActions);
 side.append(agenda);

 const latest=card(referenceCopy(10));latest.classList.add('today-transactions');
 for(const r of records('transaction').sort((a,b)=>b.data.date.localeCompare(a.data.date)||b.seq-a.seq).slice(0,4)){
  const row=button('',()=>editRecord('transaction',r),'reference-transaction');
  const copy=E('span',undefined,'reference-transaction-copy');append(copy,E('strong',r.data.label||t(r.data.kind)),E('small',r.data.date));
  append(row,icon('money'),copy,moneyElement(BigInt(r.data.amount_minor),r.data.currency,r.data.kind,r.data.kind==='income'?'+':'−'));latest.append(row);
 }
 if(!records('transaction').length)latest.append(E('p',t('empty_money'),'empty'));
 latest.append(button(t('web_all_operations'),()=>openTabSection('money','#finance-ledger'),'text-button'));primary.append(latest);
 const notes=card(t('recent_notes'));
 notes.classList.add('today-notes');
 const recent=records('note').sort((a,b)=>b.seq-a.seq).slice(0,2);
 for(const r of recent){
  const lines=r.data.body.split('\n'),label=lines[0].slice(0,110)||t('family_kind_note');
  const note=button('',()=>editRecord('note',r),'note-link');note.setAttribute('aria-label',label);
  const text=E('span',undefined,'today-note-text');text.append(E('strong',label));
  const excerpt=lines.slice(1).join(' ').trim();if(excerpt)text.append(E('span',excerpt.slice(0,110),'note-excerpt'));
  append(note,icon('notes'),text);notes.append(note);
 }
 if(!recent.length)notes.append(E('p',t('empty_notes'),'empty'));
 notes.append(button(t('family_kind_note'),()=>editRecord('note'),'text-button'));
 grid.append(notes);

}
function taskRow(r){
 const row=E('div',undefined,'row task-row'),check=E('input'),label=E('span',r.data.title,'text');
 const target=append(E('label',undefined,'task-check-target'),check);
 const workspace=state.space,epoch=privateEpoch,key=workspace+':'+r.id;
 const storageKey=taskActionKey('toggle:'+r.id),saved=readTaskAction(storageKey);
 if(saved&&!taskChanges.has(key)){
  taskChanges.set(key,{operation:saved.operation,phase:saved.conflict?'conflict':saved.accepted?'saved':'write',
   busy:false,message:saved.conflict?errorText({code:'conflict'}):pendingTaskMessage(saved.accepted)});
 }
 check.type='checkbox';check.setAttribute('aria-label',r.data.title);
 const edit=iconButton('more',t('edit')+' · '+r.data.title,()=>editRecord('task',r));
 const status=E('div',undefined,'task-change-status'),message=E('span');
 message.setAttribute('role','status');
 const retry=button(t('retry'),()=>complete(),'secondary');
 append(status,message,retry);
 function update(){
  const change=taskChanges.get(key);
  check.checked=Boolean(change?.phase==='saved'?change.operation.data.completed:r.data.completed);
  label.classList.toggle('done',check.checked);
  check.disabled=!r.editable||!!change;edit.disabled=!!change;
  row.setAttribute('aria-busy',String(!!change?.busy));
  status.hidden=!change?.message;message.textContent=change?.message||'';
  retry.disabled=!!change?.busy;
 }
 async function complete(){
  const change=taskChanges.get(key);
  if(!change||change.busy||workspace!==state.space||epoch!==privateEpoch)return;
  let failed=false;
  change.busy=true;update();
  try{
   if(change.phase==='write'){
    await saveOperation(change.operation,workspace);
    if(epoch!==privateEpoch)return;
    change.phase='saved';storeTaskAction(storageKey,change.operation,true);
   }
   if(epoch!==privateEpoch)return;
   if(workspace===state.space)await refresh();
   if(epoch!==privateEpoch)return;
   storeTaskAction(storageKey,null);
   taskChanges.delete(key);
   if(workspace===state.space&&['today','tasks'].includes(state.tab))render();
  }catch(error){
   if(epoch!==privateEpoch)return;
   failed=true;
   if(error.code==='conflict'||error.code==='revision_conflict'){
    change.phase='conflict';storeTaskAction(storageKey,change.operation,false,true);
   }
   if(change.phase==='saved')change.message=pendingTaskMessage(true);
   else if(change.phase==='conflict')change.message=errorText({code:'conflict'});
   else if(error.uncertain)change.message=t(change.durable===false?'web_task_tab_only':'web_task_unconfirmed');
   else taskChanges.delete(key);
   if(!taskChanges.has(key)||['unauthorized','workspace_forbidden','service_restricted'].includes(error.code)){
    if(error.code!=='unauthorized')storeTaskAction(storageKey,null);
    taskChanges.delete(key);report(error);
   }
  }finally{
   change.busy=false;
   if(epoch===privateEpoch&&workspace===state.space&&['today','tasks'].includes(state.tab)){
    if(row.isConnected)update();
    else if(failed)render();
   }
  }
 }
 check.addEventListener('change',()=>{
  const completed=check.checked?1:0;
  check.checked=!!r.data.completed;
  if(r.data.assignees.length){editRecord('task',r);return;}
  const operation={id:crypto.randomUUID(),action:'record.put',record_id:r.id,revision:r.revision,
   kind:r.kind,visibility:r.visibility,audience:r.audience,data:{...r.data,completed}};
  const durable=storeTaskAction(storageKey,operation);
  taskChanges.set(key,{operation,phase:'write',busy:false,message:'',durable});
  return complete();
 });
 append(row,target,label,edit,status);update();return row;
}
function listTasks(m){
 const retryCreate=readTaskAction(taskActionKey('create'));
 const retryQuick=readTaskAction(taskActionKey('quick'));
 m.classList.add('tasks-page');
 title(m,'widget_tasks',retryCreate||retryQuick?null:()=>editRecord('task'));
 if(retryCreate||retryQuick)m.querySelector('.intro').append(button(t('web_task_retry_create'),()=>{
  if(retryCreate)editRecord('task');
  else{
   openTabSection('today','.today-tasks h2');
   root.querySelector('.quick-capture button')?.focus({preventScroll:true});
  }
 },'secondary'));
 const filters=E('div',undefined,'task-filters'),queryBox=E('div'),statusBox=E('div');append(filters,queryBox,statusBox);m.append(filters);
 const query=input(queryBox,'task-search',t('web_task_search'),'search',state.taskQuery,false);
 const status=select(statusBox,'task-status',t('web_task_status'),[['all',t('web_all')],['open',t('open_tasks')],['done',t('completed')]],state.taskStatus);
 const c=E('div',undefined,'task-list');m.append(c);
 const draw=()=>{
  state.taskQuery=query.value;state.taskStatus=status.value;c.replaceChildren();
  const available=records('task'),rows=ULADIMDomain.tasks(available,query.value,status.value);
  if(!rows.length){c.append(emptyPanel('tasks',t(available.length?'web_no_results':'empty_tasks')));return;}
  for(const [name,completed] of [['open_tasks',false],['completed',true]]){
   const groupRows=rows.filter(r=>Boolean(r.data.completed)===completed);
   if(!groupRows.length)continue;
   const group=E(completed&&status.value!=='done'?'details':'section',undefined,'task-group');
   const heading=E('h2',t(name));heading.id='tasks-'+name;
   group.setAttribute('aria-labelledby',heading.id);
   group.append(append(E(group.tagName==='DETAILS'?'summary':'div',undefined,'task-group-head'),heading,E('span',String(groupRows.length),'task-group-count')));
   for(const record of groupRows)group.append(taskRow(record));
   c.append(group);
  }
 };
 query.addEventListener('input',draw);status.addEventListener('change',draw);draw();
}
function emptyPanel(symbol,message){
 const panel=E('div',undefined,'workspace-empty');
 return append(panel,icon(symbol),E('p',message));
}
const NOTE_DRAFT_COPY={
 ru:['Продолжить черновик','Черновик хранится в этой вкладке.','Браузер не смог сохранить черновик в этой вкладке.'],
 en:['Continue draft','The draft is stored in this tab.','The browser could not store the draft in this tab.'],
 'uz-Latn':['Qoralamani davom ettirish','Qoralama shu varaqda saqlanadi.','Brauzer qoralamani shu varaqda saqlay olmadi.'],
 'uz-Cyrl':['Қораламани давом эттириш','Қоралама шу варақда сақланади.','Браузер қораламани шу варақда сақлай олмади.']
};
const NOTE_SEARCH_COPY={ru:'Поиск заметок',en:'Search notes','uz-Latn':'Qaydlarni qidirish','uz-Cyrl':'Қайдларни қидириш'};
const TRANSACTION_TITLE={ru:'Операция',en:'Transaction','uz-Latn':'Operatsiya','uz-Cyrl':'Операция'};
const BUDGET_EMPTY_COPY={ru:'Добавьте бюджет, чтобы следить за лимитом.',en:'Add a budget to track a spending limit.',
 'uz-Latn':'Xarajat chegarasini kuzatish uchun byudjet qo‘shing.','uz-Cyrl':'Харажат чегарасини кузатиш учун бюджет қўшинг.'};
const noteDraftPrefix=()=>state.session?.user_id?'uladim-note-draft:'+state.session.user_id+':':'';
function noteDraftKey(record){
 const prefix=noteDraftPrefix();
 return prefix&&state.space?prefix+state.space+':'+(record?.id||'new'):'';
}
function readNoteDraft(key){
 if(!key)return null;
 try{
  const draft=JSON.parse(sessionStorage.getItem(key)||'null');
  if(typeof draft?.body==='string'&&['private','shared'].includes(draft.visibility)&&Number.isInteger(draft.revision))return draft;
 }catch{}
 return null;
}
function writeNoteDraft(key,draft){
 if(!key)return false;
 try{
  if(draft)sessionStorage.setItem(key,JSON.stringify(draft));
  else sessionStorage.removeItem(key);
  return true;
 }catch{return false;}
}
function clearNoteDrafts(){
 const prefix=noteDraftPrefix();
 if(!prefix)return;
 try{
  for(let i=sessionStorage.length-1;i>=0;i--){
   const key=sessionStorage.key(i);
   if(key?.startsWith(prefix))sessionStorage.removeItem(key);
  }
 }catch{}
}
function listNotes(m){
 const copy={
  ru:['Ваши идеи','Важное, к чему хочется вернуться.','Новая заметка','Все заметки'],
  en:['Your ideas','Keep what you want to come back to.','New note','All notes'],
  'uz-Latn':['Fikrlaringiz','Qaytishni istagan muhim narsalaringiz.','Yangi qayd','Barcha qaydlar'],
  'uz-Cyrl':['Фикрларингиз','Қайтишни истаган муҳим нарсаларингиз.','Янги қайд','Барча қайдлар']
 }[state.lang]||['Your ideas','Keep what you want to come back to.','New note','All notes'];
 title(m,'widget_notes');
 m.classList.add('notes-page');
 const intro=m.querySelector('.intro'),introText=intro.firstElementChild;
 introText.prepend(E('div',copy[0],'eyebrow'));
 introText.append(E('p',copy[1],'workspace-description'));
 intro.append(addButton(copy[2],()=>editRecord('note')));
 const toolbar=E('div',undefined,'notes-toolbar');
 const libraryHeading=E('div',undefined,'notes-library-heading');
 const count=E('span',undefined,'notes-count');
 append(libraryHeading,E('h2',copy[3]),count);
 const searchField=E('div',undefined,'notes-search');
 const search=input(searchField,'search',NOTE_SEARCH_COPY[state.lang]||NOTE_SEARCH_COPY.en,'search','',false);
 search.placeholder=NOTE_SEARCH_COPY[state.lang]||NOTE_SEARCH_COPY.en;
 const searchIcon=icon(''),searchPath=document.createElementNS(searchIcon.namespaceURI,'path');
 searchPath.setAttribute('d','M17.5 10.5a7 7 0 1 1-14 0 7 7 0 0 1 14 0Zm-2 5 5 5');
 searchIcon.append(searchPath);searchField.append(searchIcon);
 append(toolbar,libraryHeading,searchField);
 const library=E('div',undefined,'notes-library');
 const [resumeDraft]=NOTE_DRAFT_COPY[state.lang]||NOTE_DRAFT_COPY.en;
 if(readNoteDraft(noteDraftKey(null))){const resume=button(resumeDraft,()=>editRecord('note'),'secondary');resume.classList.add('notes-resume');toolbar.append(resume);}
 append(m,toolbar,library);
 const draw=()=>{
  library.replaceChildren();
  const needle=search.value.trim().toLocaleLowerCase(state.lang),available=records('note');
  const rows=available.filter(r=>r.data.body.toLocaleLowerCase(state.lang).includes(needle)).sort((a,b)=>b.seq-a.seq);
  count.textContent=String(rows.length);
  for(const r of rows){
   const c=E('article',undefined,'card note-card');
   const head=E('div',undefined,'note-card-header');
   append(head,icon('notes'),E('span',t('family_'+r.visibility),'note-visibility'));
   const content=E('div',undefined,'note-card-content');
   const firstLine=r.data.body.split('\n')[0];
   const preview=(firstLine.length>100?r.data.body.slice(100):r.data.body.slice(firstLine.length)).trimStart();
   content.append(E('h2',firstLine.slice(0,100)||t('family_kind_note')));
   if(preview)content.append(E('p',preview.slice(0,280),'note note-preview'));
   const footer=E('div',undefined,'note-card-footer');
   const edit=button(readNoteDraft(noteDraftKey(r))?resumeDraft:t('edit'),()=>editRecord('note',r),'text-button');
   edit.append(icon('forward'));
   footer.append(edit);
   append(c,head,content,footer);
   library.append(c);
  }
  if(!rows.length)library.append(emptyPanel('notes',t(available.length?'web_no_results':'empty_notes')));
 };
 search.addEventListener('input',draw);
 draw();
}
async function saveOperation(operation,workspace=state.space){
 const result=await call('sync',{workspace_id:workspace,operations:[operation]});
 const item=result.results?.[0];
 if(item?.id!==operation.id)throw {code:'server_error',uncertain:true};
 if(item.status!=='accepted')throw {code:item.status==='conflict'?'conflict':item.error};
 return item;
}
function transactionAccountKey(workspace=state.space){
 const user=state.session?.user_id;
 return user&&workspace?'uladim-transaction-account:'+user+':'+workspace:'';
}
function defaultTransactionAccount(key,accounts){
 let saved='';
 try{if(key)saved=sessionStorage.getItem(key)||'';}catch{}
 return accounts.find(account=>account.id===saved)||accounts[0]||null;
}
function rememberTransactionAccount(key,account){
 if(!key)return;
 try{
  if(account)sessionStorage.setItem(key,account);
  else sessionStorage.removeItem(key);
 }catch{}
}
function transactionCategoryChoices(){
 const ids=['','food','transport','shopping','housing','health','leisure','education','transfers','other'];
 const names={
  ru:['Без категории','Питание','Транспорт','Покупки','Дом и счета','Здоровье','Отдых','Образование','Переводы','Другое'],
  en:['Uncategorized','Food','Transport','Shopping','Home and bills','Health','Leisure','Education','Transfers','Other'],
  'uz-Latn':['Toifasiz','Oziq-ovqat','Transport','Xaridlar','Uy va hisoblar','Salomatlik','Dam olish','Ta’lim','O‘tkazmalar','Boshqa'],
  'uz-Cyrl':['Тоифасиз','Озиқ-овқат','Транспорт','Харидлар','Уй ва ҳисоблар','Саломатлик','Дам олиш','Таълим','Ўтказмалар','Бошқа']
 };
 return ids.map((id,index)=>[id,(names[state.lang]||names.en)[index]]);
}
const BUDGET_EDITOR_COPY={
 ru:{options:'Дополнительно',recurring:'Лимит обновляется каждый период. Дату окончания указывать не нужно.',custom:'Укажите начало и конец своего периода.',since:'Начало действия',participants:'Участники'},
 en:{options:'More options',recurring:'The limit renews each period. No end date is needed.',custom:'Choose the start and end of your period.',since:'Starts on',participants:'Participants'},
 az:{options:'Əlavə seçimlər',recurring:'Limit hər dövrdə yenilənir. Bitmə tarixi lazım deyil.',custom:'Dövrün başlanğıcını və sonunu seçin.',since:'Başlanğıc',participants:'İştirakçılar'},
 de:{options:'Weitere Optionen',recurring:'Das Limit erneuert sich in jedem Zeitraum. Ein Enddatum ist nicht nötig.',custom:'Wähle Beginn und Ende deines Zeitraums.',since:'Beginn',participants:'Teilnehmende'},
 es:{options:'Más opciones',recurring:'El límite se renueva en cada período. No se necesita fecha de fin.',custom:'Elige el inicio y el fin de tu período.',since:'Empieza el',participants:'Participantes'},
 fr:{options:'Plus d’options',recurring:'Le plafond se renouvelle à chaque période. Aucune date de fin n’est nécessaire.',custom:'Choisissez le début et la fin de votre période.',since:'Début',participants:'Participants'},
 hy:{options:'Լրացուցիչ ընտրանքներ',recurring:'Սահմանաչափը թարմացվում է յուրաքանչյուր ժամանակահատվածում։ Ավարտի ամսաթիվ պետք չէ։',custom:'Ընտրեք ժամանակահատվածի սկիզբն ու ավարտը։',since:'Սկիզբ',participants:'Մասնակիցներ'},
 it:{options:'Altre opzioni',recurring:'Il limite si rinnova a ogni periodo. Non serve una data di fine.',custom:'Scegli l’inizio e la fine del periodo.',since:'Inizio',participants:'Partecipanti'},
 ka:{options:'დამატებითი პარამეტრები',recurring:'ლიმიტი ყოველ პერიოდში განახლდება. დასრულების თარიღი საჭირო არ არის.',custom:'აირჩიეთ პერიოდის დასაწყისი და დასასრული.',since:'დაწყება',participants:'მონაწილეები'},
 kk:{options:'Қосымша параметрлер',recurring:'Лимит әр кезеңде жаңартылады. Аяқталу күнін көрсету қажет емес.',custom:'Кезеңнің басталуы мен аяқталуын таңдаңыз.',since:'Басталуы',participants:'Қатысушылар'},
 ky:{options:'Кошумча параметрлер',recurring:'Чек ар бир мезгилде жаңыланат. Аяктоо күнүн көрсөтүү зарыл эмес.',custom:'Мезгилдин башталышын жана аякташын тандаңыз.',since:'Башталышы',participants:'Катышуучулар'},
 pt:{options:'Mais opções',recurring:'O limite é renovado em cada período. Não é necessária uma data final.',custom:'Escolha o início e o fim do período.',since:'Início',participants:'Participantes'},
 tg:{options:'Имконоти иловагӣ',recurring:'Ҳад дар ҳар давра нав мешавад. Санаи анҷом лозим нест.',custom:'Оғоз ва анҷоми давраро интихоб кунед.',since:'Оғоз',participants:'Иштирокчиён'},
 uk:{options:'Додатково',recurring:'Ліміт оновлюється кожного періоду. Дату завершення вказувати не потрібно.',custom:'Вкажіть початок і кінець свого періоду.',since:'Початок дії',participants:'Учасники'},
 'uz-Latn':{options:'Qo‘shimcha',recurring:'Limit har davrda yangilanadi. Tugash sanasi kerak emas.',custom:'Davrning boshlanishi va tugashini tanlang.',since:'Boshlanishi',participants:'Ishtirokchilar'},
 'uz-Cyrl':{options:'Қўшимча',recurring:'Лимит ҳар даврда янгиланади. Тугаш санаси керак эмас.',custom:'Даврнинг бошланиши ва тугашини танланг.',since:'Бошланиши',participants:'Иштирокчилар'}
};
function budgetEditorStart(period,at=localDate()){
 const date=new Date(at+'T12:00:00Z');
 if(period==='month')date.setUTCDate(1);
 else if(period==='year')date.setUTCMonth(0,1);
 else if(period==='week')date.setUTCDate(date.getUTCDate()-(date.getUTCDay()+6)%7);
 return date.toISOString().slice(0,10);
}
function editRecord(kind,r=null,{eventDay=localDate(),onSaved}={}){
 const workspace=state.space,epoch=privateEpoch,taskKey=kind==='task'&&!r?taskActionKey('create'):'';
 const accountKey=kind==='transaction'?transactionAccountKey(workspace):'';
 const pendingTask=readTaskAction(taskKey);
 const d=dialog(kind==='transaction'?(TRANSACTION_TITLE[state.lang]||TRANSACTION_TITLE.en):t('family_kind_'+kind),container=>{
 container.classList.add('record-editor',kind+'-editor');
 const draftKey=kind==='note'&&(!r||r.editable)?noteDraftKey(r):'';
 const draft=readNoteDraft(draftKey);
 const [ ,localDraft,failedDraft]=NOTE_DRAFT_COPY[state.lang]||NOTE_DRAFT_COPY.en;
 let operation=draft?.operation||pendingTask?.operation||null,accepted=Boolean(draft?.accepted||pendingTask?.accepted);
 const fields={};
 const draftRevision=draft?.revision??r?.revision??0;
 const draftNotice=draftKey?E('p',undefined,'small note-draft-status'):null;
 if(draftNotice)draftNotice.setAttribute('role','status');
 const keepDraft=()=>{
  if(!draftKey)return;
  if(!r&&!operation&&!fields.body.value){
   draftNotice.textContent=writeNoteDraft(draftKey,null)?'':failedDraft;
   return;
  }
  const value={body:fields.body.value,visibility:fields.visibility.value,revision:draftRevision,operation,accepted};
  draftNotice.textContent=writeNoteDraft(draftKey,value)?localDraft:failedDraft;
 };
 const editor=form(container,'',f=>{
  const data=r?.data||{};const disabled=r&&!r.editable;
  const pair=(className,...controls)=>{
   const row=E('div',undefined,'finance-field-pair '+className);
   for(const control of controls){const field=control.currencyField||control;row.append(append(E('div'),field.previousElementSibling,field));}
   return row;
  };
  if(['task','event','account','budget'].includes(kind))fields.name=input(f,'name',t(kind==='task'?'task_title':'name'),'text',pendingTask?.operation.data.title||data.title||data.name||'');
  if(kind==='task')fields.name.placeholder=({ru:'Например, купить продукты',en:'For example, buy groceries','uz-Latn':'Masalan, oziq-ovqat xarid qilish','uz-Cyrl':'Масалан, озиқ-овқат харид қилиш'})[state.lang]||'For example, buy groceries';
  if(kind==='event'){
   const schedule=data.schedule||{};
   fields.localStart=input(f,'localStart',t('web_event_start'),'datetime-local',schedule.localStart?.slice(0,16)||eventDay+'T09:00');
   const allDay=E('div',undefined,'event-all-day');
   fields.allDay=input(allDay,'allDay',t('web_all_day'),'checkbox');fields.allDay.checked=!!schedule.allDay;
   allDay.prepend(fields.allDay);
   const options=E('details',undefined,'event-options');
   options.append(E('summary',t('web_event_options')));
   fields.timezone=input(options,'timezone',t('web_timezone'),'text',schedule.timezone||Intl.DateTimeFormat().resolvedOptions().timeZone||'device');
   fields.repeat=select(options,'repeat',t('web_repeat'),['none','daily','weekly','monthly','yearly'].map(k=>[k,t('web_repeat_'+k)]),schedule.repeat||'none');
   const recurrence=E('div',undefined,'event-repeat-options');
   fields.interval=input(recurrence,'interval',t('web_interval'),'number',schedule.interval||1);fields.interval.min=1;fields.interval.max=365;fields.interval.step=1;
   fields.until=input(recurrence,'until',t('web_until'),'date',schedule.until||'',false);
   const updateRecurrence=()=>{
    recurrence.hidden=fields.repeat.value==='none';
    fields.interval.disabled=fields.until.disabled=recurrence.hidden;
   };
   updateRecurrence();
   fields.repeat.addEventListener('change',updateRecurrence);
   options.addEventListener('invalid',()=>{options.open=true;},true);
   options.append(recurrence);
   append(f,allDay,options);
  }
  if(kind==='note')fields.body=input(f,'body',t('note_text'),'textarea',draft?.body??data.body??'');
  if(kind==='task'){
   fields.completed=input(f,'completed',t('completed'),'checkbox');fields.completed.checked=!!(pendingTask?.operation.data.completed??data.completed);fields.completed.disabled=!!data.assignees?.length;
   const status=E('div',undefined,'task-editor-status'),statusLabel=fields.completed.previousElementSibling;append(status,fields.completed,statusLabel);f.append(status);
   if(data.assignees?.length){f.append(E('p',t('family_review_pending')));for(const pid of data.assignees){const profile=state.roster.profiles.find(p=>p.id===pid);f.append(button(t('complete')+' · '+(profile?.name||pid),async()=>{await saveOperation({id:crypto.randomUUID(),action:'task.complete',record_id:r.id,revision:r.revision,profile_id:pid,completed:true});d.close();await refresh();render();}));}}
  }
  if(['account','transaction'].includes(kind))fields.currency=input(f,'currency',t('currency'),'text',data.currency||'RUB');
  if(['account','transaction','transfer'].includes(kind)){
   fields.amount=input(f,'amount',t(kind==='account'?'opening_balance':'amount'),'text',!r?'':decimalInput(data.opening_minor??data.amount_minor??data.limit_minor??data.sent_minor??0,data.currency||records('account').find(a=>a.id===data.from_id)?.data.currency||'RUB'),kind!=='account');
   fields.amount.placeholder=decimalInput(0,fields.currency?.value||records('account').find(a=>a.id===data.from_id)?.data.currency||'RUB');
   fields.currency?.addEventListener('change',()=>{try{fields.amount.placeholder=decimalInput(0,fields.currency.value);}catch{/* Currency search text is validated when a code is chosen or saved. */}});
  }
  if(kind==='transaction'){
   fields.direction=select(f,'direction',t('family_kind_transaction'),[['expense',t('expense')],['income',t('income')]],data.kind||'expense');
   fields.date=input(f,'date',t('family_date'),'date',data.date||localDate());fields.label=input(f,'label',t('family_name'),'text',data.label||'',false);
   fields.category=select(f,'category',({ru:'Категория',en:'Category','uz-Latn':'Toifa','uz-Cyrl':'Тоифа'}[state.lang]||'Category'),transactionCategoryChoices(),data.category||'');
   const categoryLabel=fields.category.previousElementSibling;
   const categoryVisibility=()=>{fields.category.hidden=false;categoryLabel.hidden=false;};
   categoryVisibility();fields.direction.addEventListener('change',categoryVisibility);
   const accounts=records('account'),selected=r?data.account_id:defaultTransactionAccount(accountKey,accounts)?.id;
   fields.account=select(f,'account',t('family_account_select'),[['',t('family_none')],...accounts.map(a=>[a.id,a.data.name+' · '+a.data.currency])],selected||'');
   const accountCurrency=()=>{
    const account=accounts.find(a=>a.id===fields.account.value);
    if(account){
     fields.currency.value=account.data.currency;
     if(!r)fields.amount.placeholder=decimalInput(0,account.data.currency);
    }
   };
   if(!r)accountCurrency();
   fields.account.addEventListener('change',accountCurrency);
   append(f,pair('transaction-context',fields.direction,fields.account),
    pair('transaction-value',fields.amount,fields.currency),fields.date.previousElementSibling,fields.date,
    fields.label.previousElementSibling,fields.label,categoryLabel,fields.category);
  }
  if(kind==='budget'){
   const copy=BUDGET_EDITOR_COPY[state.lang]||BUDGET_EDITOR_COPY.en;
   const currency=data.currency||defaultTransactionAccount(transactionAccountKey(workspace),records('account'))?.data.currency||'RUB';
   fields.amount=input(f,'amount',t('budget_limit'),'text',r?decimalInput(data.limit_minor,currency):'');
   fields.amount.placeholder=decimalInput(0,currency);
   fields.currency=input(f,'currency',t('currency'),'text',currency);
   fields.currency.spellcheck=false;
   fields.currency.addEventListener('input',()=>{
    try{fields.amount.placeholder=decimalInput(0,fields.currency.value.trim().toUpperCase());}catch{}
   });
   f.append(pair('budget-value',fields.amount,fields.currency));
   fields.period=select(f,'period',t('family_period'),['week','month','year','custom'].map(k=>[k,t('family_'+k)]),data.period||'month');
   fields.start=input(f,'start',t('web_period_start'),'date',data.start_on||budgetEditorStart(fields.period.value));
   fields.end=input(f,'end',t('web_period_end'),'date',data.end_on||'',false);
   const dates=pair('budget-dates',fields.start,fields.end);
   const summary=E('section',undefined,'budget-period-summary'),periodTitle=E('strong'),periodDates=E('p'),periodHint=E('p',undefined,'small');
   summary.setAttribute('aria-live','polite');append(summary,periodTitle,periodDates,periodHint);
   const options=E('details',undefined,'budget-options');options.append(E('summary',copy.options));
   fields.rollover=select(options,'rollover',t('family_rollover'),['none','positive','negative','both'].map(k=>[k,t('family_roll_'+k)]),data.rollover||'none');
   if(data.start_on)options.append(E('p',copy.since+' · '+displayDate(data.start_on),'small budget-original-start'));
   if(data.participants?.length)options.append(E('p',copy.participants+' · '+data.participants.map(id=>state.roster.profiles.find(p=>p.id===id)?.name||id).join(', '),'small'));
   options.addEventListener('invalid',()=>{options.open=true;},true);
   const showPeriod=()=>{
    const custom=fields.period.value==='custom';
    dates.hidden=!custom;fields.start.disabled=fields.end.disabled=!custom;
    fields.start.required=fields.end.required=custom;
    fields.end.min=fields.start.value;
    periodTitle.textContent=t('family_'+fields.period.value);
    if(custom){
     periodDates.textContent=fields.start.value&&fields.end.value?displayDate(fields.start.value)+' — '+displayDate(fields.end.value):'';
    }else{
     const current=financeBudgetPeriod({period:fields.period.value,start_on:fields.start.value,end_on:null});
     periodDates.textContent=displayDate(current.start)+' — '+displayDate(current.end);
    }
    periodDates.hidden=!periodDates.textContent;
    periodHint.textContent=custom?copy.custom:copy.recurring;
   };
   fields.period.addEventListener('change',()=>{
    fields.start.value=data.period===fields.period.value?data.start_on:budgetEditorStart(fields.period.value);
    showPeriod();
   });
   fields.start.addEventListener('input',showPeriod);fields.end.addEventListener('input',showPeriod);
   append(f,dates,summary,options);showPeriod();
  }
  if(kind==='transfer'){if(records('account').length<2)f.append(E('p',t('web_transfer_accounts'),'error'));const accounts=records('account').map(a=>[a.id,a.data.name+' · '+a.data.currency]);fields.from=select(f,'from',t('family_from'),accounts,data.from_id||accounts[0]?.[0]);fields.to=select(f,'to',t('family_to'),accounts,data.to_id||accounts[1]?.[0]);fields.received=input(f,'received',t('received_amount'),'text',r?decimalInput(data.received_minor||0,records('account').find(a=>a.id===data.to_id)?.data.currency||'RUB'):'');fields.received.placeholder=decimalInput(0,records('account').find(a=>a.id===fields.to.value)?.data.currency||'RUB');fields.to.addEventListener('change',()=>{fields.received.placeholder=decimalInput(0,records('account').find(a=>a.id===fields.to.value)?.data.currency||'RUB');});fields.from.addEventListener('change',()=>{fields.amount.placeholder=decimalInput(0,records('account').find(a=>a.id===fields.from.value)?.data.currency||'RUB');});fields.date=input(f,'date',t('family_date'),'date',data.date||localDate());}
  let accessOptions=kind==='event'?f.querySelector('.event-options'):kind==='budget'?f.querySelector('.budget-options'):null;
  if(!accessOptions){accessOptions=E('details',undefined,'record-options');accessOptions.append(E('summary',t('family_visibility')));f.append(accessOptions);}
  fields.visibility=select(accessOptions,'visibility',t('family_visibility'),[['private',t('family_private')],['shared',t('family_shared')]],r?.visibility||(currentSpace()?.role==='child'?'shared':'private'));
  if(pendingTask)fields.visibility.value=pendingTask.operation.visibility;
  if(accessOptions.classList.contains('record-options')){
   const summary=accessOptions.querySelector('summary');
   const showAccess=()=>{summary.textContent=t('family_visibility')+' · '+t('family_'+fields.visibility.value);};
   showAccess();fields.visibility.addEventListener('change',showAccess);
  }
  if(draftNotice){
   if(draft){fields.visibility.value=draft.visibility;draftNotice.textContent=localDraft;}
   fields.body.addEventListener('input',keepDraft);
   fields.visibility.addEventListener('change',keepDraft);
   f.append(draftNotice);
  }
  if(disabled)f.disabled=true;return fields;
 },async v=>{
  if(workspace!==state.space||epoch!==privateEpoch)throw {code:'view_changed'};
  if(!operation){let data={...r?.data};
   if(kind==='note')data={body:v.body.value};
   if(kind==='event'){
    const repeat=v.repeat.value;
    const schedule={localStart:v.localStart.value.length===16?v.localStart.value+':00':v.localStart.value,timezone:v.timezone.value.trim(),allDay:v.allDay.checked,repeat,interval:repeat==='none'?1:Number(v.interval.value),until:repeat==='none'?null:v.until.value||null};
    const revealOptions=()=>{container.querySelector('.event-options').open=true;};
    if(schedule.until&&schedule.until<schedule.localStart.slice(0,10)){revealOptions();throw {code:'invalid_date'};}
    const year=Number(schedule.localStart.slice(0,4));
    if(!Number.isInteger(schedule.interval)||schedule.interval<1||schedule.interval>365){revealOptions();throw {code:'invalid_schedule'};}
    if(year<1900||year>2200)throw {code:'invalid_schedule'};
    try{ULADIMDomain.occurrences([{id:'validate',data:{schedule}}],schedule.localStart.slice(0,10),dateString(new Date(Date.parse(schedule.localStart+'Z')+172800000)));}
    catch{revealOptions();throw {code:'invalid_schedule'};}
    data={title:v.name.value,schedule};
   }
   if(kind==='task')data={title:v.name.value,completed:v.completed.checked?1:0,assignment:r?.data.assignment||'any',assignees:r?.data.assignees||[],review:r?.data.review||0};
   if(kind==='account')data={name:v.name.value,currency:v.currency.value.trim().toUpperCase(),opening_minor:minor(v.amount.value||'0',true,v.currency.value)};
   if(kind==='transaction')data={kind:v.direction.value,amount_minor:minor(v.amount.value,false,v.currency?.value||records('account').find(a=>a.id===v.from?.value)?.data.currency||'RUB'),currency:v.currency.value.trim().toUpperCase(),date:v.date.value,label:v.label.value,account_id:v.account.value||null,category:v.category.value||null};
   if(kind==='budget')data={name:v.name.value,currency:v.currency.value.trim().toUpperCase(),limit_minor:minor(v.amount.value,false,v.currency.value.trim().toUpperCase()),period:v.period.value,start_on:v.start.value,end_on:v.period.value==='custom'?v.end.value||null:r?.data.end_on||null,rollover:v.rollover.value,participants:r?.data.participants||[]};
   if(kind==='transfer')data={from_id:v.from.value,to_id:v.to.value,sent_minor:minor(v.amount.value,false,v.currency?.value||records('account').find(a=>a.id===v.from?.value)?.data.currency||'RUB'),received_minor:minor(v.received.value,false,records('account').find(a=>a.id===v.to.value)?.data.currency||'RUB'),date:v.date.value};
   ULADIMDomain.validateFinance(kind,data,records('account'));
   operation={id:crypto.randomUUID(),action:'record.put',record_id:r?.id||crypto.randomUUID(),revision:draftRevision,kind,visibility:v.visibility.value,audience:r?.audience||(currentSpace()?.role==='child'?[currentSpace().profile_id]:[]),data};
  }
  if(!accepted){
   keepDraft();
   const durable=!taskKey||storeTaskAction(taskKey,operation);
   try{
    await saveOperation(operation,workspace);
    if(epoch!==privateEpoch)return;
    accepted=true;keepDraft();
    if(kind==='transaction')rememberTransactionAccount(accountKey,operation.data.account_id);
    if(taskKey)storeTaskAction(taskKey,operation,true);
   }catch(error){
    if(epoch!==privateEpoch)return;
    if(!error.uncertain&&(error.code!=='unauthorized'||!taskKey)){
     operation=null;keepDraft();
     if(taskKey)storeTaskAction(taskKey,null);
    }
    if(taskKey&&error.uncertain)error.displayMessage=t(durable?'web_task_unconfirmed':'web_task_tab_only');
    throw error;
   }
  }
  try{await refresh();}catch(error){throw {...error,refreshOnly:true};}
  if(epoch!==privateEpoch)return;
  if(draftKey)writeNoteDraft(draftKey,null);
  if(taskKey)storeTaskAction(taskKey,null);
  d.close();render();onSaved?.();
 });
 if(operation){
  editor.querySelector('fieldset').disabled=true;
  editor.querySelector('button[type=submit]').textContent=t('retry');
  editor.querySelector('.error').textContent=pendingTask?pendingTaskMessage(accepted):t(accepted?'web_saved_refresh':'web_uncertain');
 }
 const secondary=E('div',undefined,'editor-secondary-actions');
 secondary.append(button(({ru:'Отмена',en:'Cancel','uz-Latn':'Bekor qilish','uz-Cyrl':'Бекор қилиш'})[state.lang]||'Cancel',()=>d.close(),'secondary editor-cancel'));
 if(r){const more=E('details',undefined,'editor-more');more.append(E('summary',({ru:'Другие действия',en:'More actions','uz-Latn':'Boshqa amallar','uz-Cyrl':'Бошқа амаллар'})[state.lang]||'More actions'));more.append(button(t('family_use_server'),async()=>{
  await refresh();
  if(draftKey)writeNoteDraft(draftKey,null);
  d.close();render();
 },'secondary'));
 if(r.editable)more.append(button(t('delete'),()=>{d.close();queueDelete(r,workspace);},'danger'));secondary.append(more);}
 container.append(secondary);
 });
 if(taskKey)d.addEventListener('close',()=>{
  if(epoch===privateEpoch&&workspace===state.space&&['today','tasks'].includes(state.tab)&&readTaskAction(taskKey))render();
 });
}
function summaries(container){
 const month=localDate().slice(0,7);
 const transactions=records('transaction').filter(r=>r.data.date.slice(0,7)===month);
 const currencies=[...new Set([...transactions,...records('account')].map(r=>r.data.currency))];
 const period=new Intl.DateTimeFormat(state.lang,{month:'long',year:'numeric'}).format(new Date(month+'-01T12:00:00'));
 container.append(E('p',period,'finance-summary-period small'));
 if(!currencies.length){container.append(E('p',t('empty_money'),'empty'));return;}
 for(const currency of currencies){
  const {income,expense}=financeTotals(transactions,currency);
  const row=E('div',undefined,'today-money-row');
  for(const [kind,amount] of [['income',income],['expense',expense],['total',income-expense]]){
   const cell=E('div',undefined,kind);
   append(cell,E('span',t(kind==='total'?'web_today_net':kind),'small'),moneyElement(amount,currency));
   row.append(cell);
  }
  container.append(row);
 }
}

function balance(a){let result=BigInt(a.data.opening_minor);for(const r of records('transaction').filter(r=>r.data.account_id===a.id))result+=(r.data.kind==='income'?1n:-1n)*BigInt(r.data.amount_minor);for(const r of records('transfer')){if(r.data.from_id===a.id)result-=BigInt(r.data.sent_minor);if(r.data.to_id===a.id)result+=BigInt(r.data.received_minor);}return result;}
function financeBudgetPeriod(data,at=localDate()){
 const first=new Date(data.start_on+'T00:00:00Z'),now=new Date(at+'T00:00:00Z'),day=86400000;
 let start=new Date(first),end;
 if(now>=first){
  if(data.period==='month')start=new Date(Date.UTC(now.getUTCFullYear(),now.getUTCMonth(),1));
  else if(data.period==='year')start=new Date(Date.UTC(now.getUTCFullYear(),0,1));
  else{
   const span=data.period==='custom'?Math.floor((Date.parse(data.end_on+'T00:00:00Z')-first)/day)+1:7;
   start=new Date(+first+Math.floor((now-first)/day/span)*span*day);
  }
  if(start<first)start=new Date(first);
 }
 if(data.period==='month')end=new Date(Date.UTC(start.getUTCFullYear(),start.getUTCMonth()+1,0));
 else if(data.period==='year')end=new Date(Date.UTC(start.getUTCFullYear(),11,31));
 else end=new Date(+start+(data.period==='custom'?Math.floor((Date.parse(data.end_on+'T00:00:00Z')-first)/day):6)*day);
 return {start:start.toISOString().slice(0,10),end:end.toISOString().slice(0,10)};
}
function renderFinanceBudgets(m){
 const copy={
  ru:{spent:'Потрачено за период',available:'Доступно на период',remaining:'Осталось',over:'Превышение',carry:'Перенос остатка',future:'Начнётся',limit:'Лимит периода'},
  en:{spent:'Spent this period',available:'Available this period',remaining:'Remaining',over:'Over budget',carry:'Rollover',future:'Starts',limit:'Period limit'},
  'uz-Latn':{spent:'Davr xarajatlari',available:'Davr uchun mavjud',remaining:'Qoldiq',over:'Oshib ketgan',carry:'Qoldiqni o‘tkazish',future:'Boshlanadi',limit:'Davr limiti'},
  'uz-Cyrl':{spent:'Давр харажатлари',available:'Давр учун мавжуд',remaining:'Қолдиқ',over:'Ошиб кетган',carry:'Қолдиқни ўтказиш',future:'Бошланади',limit:'Давр лимити'}
 }[state.lang]||{spent:'Spent this period',available:'Available this period',remaining:'Remaining',over:'Over budget',carry:'Rollover',future:'Starts',limit:'Period limit'};
 const budgets=E('section',undefined,'finance-budgets finance-budget-grid');budgets.id='finance-budgets';
 const budgetRecords=records('budget'),views=new Map();
 for(const r of budgetRecords){
  const data=r.data,row=card(),head=E('div',undefined,'finance-budget-head'),text=E('div'),period=financeBudgetPeriod(data);
  row.classList.add('finance-budget-card');row.dataset.budget=r.id;
  append(text,E('h2',data.name),E('p',displayDate(period.start)+' — '+displayDate(period.end),'small'));
  append(head,text,iconButton('more',t('edit')+' · '+data.name,()=>editRecord('budget',r)));row.append(head);
  const remaining=E('strong','—'),balanceLine=E('div',undefined,'finance-budget-remaining');
  append(balanceLine,E('span',copy.remaining,'small'),remaining);row.append(balanceLine);
  const progress=E('progress');progress.max=10000;progress.value=0;progress.setAttribute('aria-label',copy.spent);row.append(progress);
  const metrics=E('dl',undefined,'budget-metrics'),spent=E('dd','—'),available=E('dd','—');
  append(metrics,append(E('div'),E('dt',copy.spent),spent),append(E('div'),E('dt',copy.available),available));row.append(metrics);
  const conditions=E('p',undefined,'small finance-budget-conditions');append(conditions,document.createTextNode(copy.limit+': '),moneyElement(data.limit_minor,data.currency,'','','span'),document.createTextNode(' · '+t('family_'+data.period)));
  if(data.rollover!=='none')conditions.append(E('span',' · '+copy.carry+': '+t('family_roll_'+data.rollover)));
  if(localDate()<data.start_on)conditions.append(E('span',' · '+copy.future+' '+displayDate(data.start_on)));
  row.append(conditions);budgets.append(row);views.set(r.id,{remaining,spent,available,progress,balanceLine});
 }
 if(!budgetRecords.length){const empty=card();empty.append(emptyPanel('money',BUDGET_EMPTY_COPY[state.lang]||BUDGET_EMPTY_COPY.en));budgets.append(empty);return budgets;}
 const epoch=privateEpoch;
 // Both remainder and spending come from the existing shared Dart engine. The
 // ephemeral no-carry view isolates this period's spending without changing data.
 const noCarry=budgetRecords.map(r=>({...r,id:r.id+':current-period',data:{...r.data,rollover:'none'}}));
 statementWorker({action:'budgets',at:localDate(),records:records('transaction'),budgets:[...budgetRecords,...noCarry]}).then(result=>{
  if(epoch!==privateEpoch||!m.isConnected)return;
  for(const r of budgetRecords){
   const view=views.get(r.id),remaining=BigInt(result.remaining[r.id]),limit=BigInt(r.data.limit_minor),spent=limit-BigInt(result.remaining[r.id+':current-period']),allowance=remaining+spent;
   setMoneyElement(view.remaining,remaining,r.data.currency);setMoneyElement(view.spent,spent,r.data.currency);setMoneyElement(view.available,allowance,r.data.currency);
   view.balanceLine.classList.toggle('expense',remaining<0n);
   view.balanceLine.firstChild.textContent=remaining<0n?copy.over:copy.remaining;
   if(remaining<0n)setMoneyElement(view.remaining,-remaining,r.data.currency);
   view.progress.value=allowance>0n?Number((spent>allowance?allowance:spent)*10000n/allowance):spent>0n?10000:0;
   view.progress.setAttribute('aria-valuetext',copy.spent+': '+money(spent,r.data.currency)+'; '+copy.remaining+': '+money(remaining,r.data.currency));
  }
 }).catch(error=>{if(m.isConnected)budgets.append(E('p',errorText(error),'error'));});
 return budgets;
}
function financeExpenseGroups(rows,currency,kind='expense'){
 const labels=new Map(transactionCategoryChoices()),totals=new Map();
 for(const row of rows){
  if(row.kind!=='transaction'||row.data.kind!==kind||row.data.currency!==currency)continue;
  const category=labels.has(row.data.category)?row.data.category:'';
  totals.set(category,(totals.get(category)||0n)+BigInt(row.data.amount_minor));
 }
 const colors={food:'#7966c4',transport:'#3b83ac',shopping:'#b77a42',housing:'#438d79',health:'#b2668d',leisure:'#a68b35',education:'#7388bf',transfers:'#aa7160',other:'#668d87','':'#8992a0'};
 return [...totals.entries()].map(([id,amount])=>({id,label:labels.get(id),amount,color:colors[id]})).sort((a,b)=>a.amount===b.amount?a.label.localeCompare(b.label,state.lang):a.amount>b.amount?-1:1);
}
function drawExpenseCategories(canvas,currency,groups){
 const ctx=canvas.getContext('2d');ctx.clearRect(0,0,720,320);if(!currency)return;
 const style=getComputedStyle(document.body),sum=groups.reduce((total,group)=>total+group.amount,0n);
 const ratio=value=>sum?Number(value*1000000n/sum)/1000000:0;
 let angle=-Math.PI/2;
 ctx.lineWidth=40;ctx.lineCap='butt';
 if(!sum){ctx.strokeStyle=style.getPropertyValue('--ux-border')||style.getPropertyValue('--line');ctx.beginPath();ctx.arc(360,155,102,0,Math.PI*2);ctx.stroke();}
 for(const group of groups){
  if(group.amount===0n)continue;
  const sweep=ratio(group.amount)*Math.PI*2,gap=groups.length>1?Math.min(.025,sweep/4):0;
  ctx.strokeStyle=group.color;ctx.beginPath();ctx.arc(360,155,102,angle+gap/2,angle+sweep-gap/2);ctx.stroke();angle+=sweep;
 }
 const scale=720/Math.max(canvas.clientWidth||720,240);
 ctx.textAlign='center';ctx.fillStyle=style.getPropertyValue('--ux-muted')||style.getPropertyValue('--muted');ctx.font=(12*scale)+'px system-ui';ctx.fillText(t('expense'),360,146,170);
 const parts=moneyParts(sum,currency);ctx.fillStyle=style.getPropertyValue('--ux-ink')||style.getPropertyValue('--ink');ctx.font='600 '+(20*scale)+'px system-ui';ctx.fillText(parts.number,360,170,174);ctx.font=(12*scale)+'px system-ui';ctx.fillText(parts.currency,360,195,174);ctx.textAlign='left';
 canvas.setAttribute('aria-label',t('expense')+': '+money(sum,currency)+(groups.length?'; '+groups.map(group=>group.label+': '+money(group.amount,currency)).join('; '):''));
}
function finance(m){
 const copy={
  ru:{overview:'Обзор финансов',history:'Вся история',balance:'Баланс счетов',recent:'Последние операции',report:'Отчёт по счёту',back:'Все счета',open:'Открыть отчёт',separate:'Суммы показаны отдельно по валютам.',noAccount:'Счёт больше недоступен',period:'Период отчёта'},
  en:{overview:'Financial overview',history:'All time',balance:'Account balances',recent:'Recent transactions',report:'Account report',back:'All accounts',open:'Open report',separate:'Amounts are shown separately by currency.',noAccount:'Account is no longer available',period:'Report period'},
  'uz-Latn':{overview:'Moliya sharhi',history:'Barcha vaqt',balance:'Hisoblar balansi',recent:'Oxirgi operatsiyalar',report:'Hisob bo‘yicha hisobot',back:'Barcha hisoblar',open:'Hisobotni ochish',separate:'Summalar valyuta bo‘yicha alohida ko‘rsatilgan.',noAccount:'Hisob endi mavjud emas',period:'Hisobot davri'},
  'uz-Cyrl':{overview:'Молия шарҳи',history:'Барча вақт',balance:'Ҳисоблар баланси',recent:'Охирги операциялар',report:'Ҳисоб бўйича ҳисобот',back:'Барча ҳисоблар',open:'Ҳисоботни очиш',separate:'Суммалар валюта бўйича алоҳида кўрсатилган.',noAccount:'Ҳисоб энди мавжуд эмас',period:'Ҳисобот даври'}
 }[state.lang]||{overview:'Financial overview',history:'All time',balance:'Account balances',recent:'Recent transactions',report:'Account report',back:'All accounts',open:'Open report',separate:'Amounts are shown separately by currency.',noAccount:'Account is no longer available',period:'Report period'};
 const categoriesTitle=({ru:'По категориям',en:'By category','uz-Latn':'Toifalar bo‘yicha','uz-Cyrl':'Тоифалар бўйича'})[state.lang]||'By category';
 const categoriesHint=({ru:'Нажмите категорию, чтобы увидеть операции.',en:'Choose a category to see its transactions.','uz-Latn':'Operatsiyalarni ko‘rish uchun toifani tanlang.','uz-Cyrl':'Операцияларни кўриш учун тоифани танланг.'})[state.lang]||'Choose a category to see its transactions.';
 const view=['accounts','budgets','ledger','analysis','report'].includes(state.referenceSection)?state.referenceSection:'overview';
 const accountRecords=records('account'),reportAccount=view==='report'?accountRecords.find(a=>a.id===state.financeFilters.account):null;
 title(m,'finances');m.classList.add('finance-page');m.dataset.financeView=view;
 const heading=m.querySelector('.intro h1');heading.textContent=reportAccount?reportAccount.data.name:({overview:copy.overview,accounts:t('web_accounts'),budgets:t('web_finance_budgets'),ledger:t('web_finance_transactions'),analysis:t('web_analysis'),report:copy.report}[view]);
 const toolbar=E('div',undefined,'finance-toolbar');
 if(view==='accounts')append(toolbar,addButton(t('family_kind_account'),()=>editRecord('account')),button(t('family_kind_transfer'),()=>editRecord('transfer'),'secondary'));
 else if(view==='budgets')toolbar.append(addButton(t('family_kind_budget'),()=>editRecord('budget')));
 else append(toolbar,addButton(t('web_add_operation'),()=>editRecord('transaction')),button(statementCopy('title'),importStatement,'secondary finance-import-shortcut'));
 m.querySelector('.intro').append(toolbar);
 const sections=E('nav',undefined,'finance-navigation');sections.setAttribute('aria-label',t('finances'));
 for(const [id,label] of [['',copy.overview],['ledger',t('web_finance_transactions')],['accounts',t('web_accounts')],['budgets',t('web_finance_budgets')]]){
  const item=button(label,()=>referenceNavigate('money',id),'secondary finance-view-tab');item.dataset.section=id;
  if((view==='overview'&&id==='')||view===id||(view==='report'&&id==='accounts'))item.setAttribute('aria-current','page');
  sections.append(item);
 }
 m.append(sections);
 if(view==='report'){
  const back=button(copy.back,()=>referenceNavigate('money','accounts'),'text-button finance-report-back');back.prepend(icon('back'));m.append(back);
  if(!reportAccount){m.append(emptyPanel('money',copy.noAccount));return;}
 }
 const summary=E('section',undefined,'finance-overview');summary.setAttribute('aria-label',t('web_finance_summary'));
 const scope=E('p',undefined,'finance-summary-period small');
 const metricGrid=E('div',undefined,'finance-metric-grid');append(summary,scope,metricGrid);
 const filterPanel=E('details',undefined,'finance-filter-panel');
 const filterLabel=E('summary',t('web_filters')),filters=E('div',undefined,'finance-filters');append(filterPanel,filterLabel,filters);
 const group=(name,label,type='search')=>{const wrap=E('div');filters.append(wrap);return input(wrap,name,label,type,state.financeFilters[name]||'',false);};
 const search=group('finance-search',t('search')),from=group('finance-from',t('web_period_start'),'date'),to=group('finance-to',t('web_period_end'),'date');
 const filterWrap=E('div');filters.append(filterWrap);
 const accountFilter=select(filterWrap,'finance-account',t('web_accounts'),[['',t('web_all_accounts')],...accountRecords.map(a=>[a.id,a.data.name+' · '+a.data.currency])],state.financeFilters.account||'');
 if(view==='report'){accountFilter.value=reportAccount.id;accountFilter.disabled=true;}
 const rows=()=>records('transaction').filter(r=>(!accountFilter.value||r.data.account_id===accountFilter.value)&&(!from.value||r.data.date>=from.value)&&(!to.value||r.data.date<=to.value)&&(!search.value||(r.data.label+' '+r.data.date).toLocaleLowerCase(state.lang).includes(search.value.toLocaleLowerCase(state.lang))));
 const grid=E('div',undefined,'finance-grid finance-content');m.append(grid);
 const ledger=card(view==='overview'?copy.recent:t('web_history'));ledger.classList.add('ledger');ledger.id='finance-ledger';
 const ledgerRows=E('div',undefined,'ledger-rows');ledger.append(ledgerRows);
 let ledgerLimit=25,ledgerFilterKey='';
 const pagination=E('div',undefined,'ledger-pagination'),pageStatus=E('p',undefined,'small');pageStatus.setAttribute('role','status');
 const showMore=button('',()=>{ledgerLimit+=25;draw();},'secondary');append(pagination,pageStatus,showMore);ledger.append(pagination);pagination.hidden=view==='overview';
 if(view==='overview')ledger.append(button(t('web_all_operations'),()=>referenceNavigate('money','ledger'),'text-button finance-ledger-all'));
 const accounts=card();accounts.classList.add('finance-accounts');accounts.id='finance-accounts';
 for(const a of accountRecords){
  const row=E('div',undefined,'account-balance');
  const report=button('',()=>{state.financeFilters={...state.financeFilters,account:a.id};referenceNavigate('money','report');},'secondary finance-account-report');
  const name=append(E('span',undefined,'account-name'),icon('money'),E('strong',a.data.name,'text'));
  append(report,name,moneyElement(balance(a),a.data.currency,'finance-account-amount'),E('span',copy.open,'small finance-account-link'));
  append(row,report,iconButton('more',t('edit')+' · '+a.data.name,()=>editRecord('account',a)));accounts.append(row);
 }
 if(!accountRecords.length)accounts.append(emptyPanel('money',t('empty_money')));
 const chart=card(t('web_analysis'));chart.classList.add('finance-analysis');chart.id='finance-analysis';
 const chartControls=E('div',undefined,'chart-controls'),chartCurrency=E('div'),chartMode=E('div');chart.append(append(chartControls,chartCurrency,chartMode));
 const currencies=[...new Set([...records('transaction'),...accountRecords].map(r=>r.data.currency))];
 const currency=select(chartCurrency,'chart-currency',t('currency'),currencies.map(c=>[c,c]),reportAccount?.data.currency||currencies[0]);
 const mode=select(chartMode,'chart-mode',t('web_chart_type'),[['categories',categoriesTitle],['bar',t('web_bar')],['line',t('web_line')],['smooth',t('web_smooth')],['donut',t('web_donut')],['compact',t('web_compact')]],state.financeChartMode||'categories');
 const breakdownWrap=E('div',undefined,'finance-breakdown-control');
 const breakdownKind=select(breakdownWrap,'breakdown-kind',categoriesTitle,[['expense',t('expense')],['income',t('income')]],state.financeBreakdownKind||'expense');
 chart.insertBefore(breakdownWrap,chartControls);
 const chartOptions=E('details',undefined,'finance-chart-options');chartOptions.append(E('summary',t('web_chart_type')));chart.insertBefore(chartOptions,chartControls);chartOptions.append(chartControls);
 breakdownWrap.append(chartCurrency);chartCurrency.classList.add('finance-chart-currency');chartCurrency.hidden=currencies.length<2;
 breakdownWrap.classList.toggle('has-currencies',currencies.length>1);
 let drilldown=false,categoryFilter=null;
 const clearDrill=button(({ru:'Все категории',en:'All categories','uz-Latn':'Barcha toifalar','uz-Cyrl':'Барча тоифалар'})[state.lang]||'All categories',()=>{categoryFilter=null;drilldown=false;draw();},'text-button finance-clear-drill');
 clearDrill.hidden=true;ledger.insertBefore(clearDrill,ledgerRows);
 const drill=(kind,category=null)=>{breakdownKind.value=kind;mode.value='categories';drilldown=true;categoryFilter=category;ledgerLimit=25;draw();};
 currency.disabled=mode.disabled=!currencies.length;
 if(reportAccount)currency.disabled=true;
 const legend=E('div',undefined,'chart-legend');chart.append(legend);
 const canvas=E('canvas');canvas.width=720;canvas.height=320;canvas.setAttribute('role','img');chart.append(canvas);
 const categoryVisual=E('div',undefined,'finance-category-visual'),categoryRing=E('div',undefined,'finance-category-ring'),categoryTotal=E('div',undefined,'finance-category-total');
 categoryRing.setAttribute('aria-hidden','true');append(categoryVisual,categoryRing,categoryTotal);chart.insertBefore(categoryVisual,legend);
 const categoryLargeTotal=E('div',undefined,'finance-category-large-total');categoryLargeTotal.hidden=true;chart.insertBefore(categoryLargeTotal,legend);
 const categoryHint=E('p',categoriesHint,'small finance-category-hint');chart.append(categoryHint);
 const budgets=view==='budgets'?renderFinanceBudgets(m):null;
 if(['overview','ledger','analysis','report'].includes(view)){
  grid.before(filterPanel,summary);
  if(view==='ledger')grid.append(ledger);
  else if(view==='analysis')grid.append(chart);
  else append(grid,chart,ledger);
 }else if(view==='accounts')grid.append(accounts);
 else grid.append(budgets);
 function draw(){
  state.financeFilters={'finance-search':search.value,'finance-from':from.value,'finance-to':to.value,account:accountFilter.value};
  const selectedAccount=accountRecords.find(account=>account.id===accountFilter.value);
  if(selectedAccount)currency.value=selectedAccount.data.currency;
  currency.disabled=Boolean(selectedAccount)||!currencies.length;
  const active=Object.values(state.financeFilters).filter(Boolean).length,filtered=rows();
  filterLabel.textContent=t('web_filters')+(active?' · '+active:'');
  const activeScope=[from.value?t('web_period_start')+' '+displayDate(from.value):'',to.value?t('web_period_end')+' '+displayDate(to.value):'',accountFilter.value?accountFilter.selectedOptions[0]?.textContent:'',search.value?'“'+search.value+'”':''].filter(Boolean);
  scope.textContent=(activeScope.join(' · ')||copy.history)+' · '+copy.separate;filterLabel.title=activeScope.join(' · ');
  metricGrid.replaceChildren();
  const balanceByCurrency=new Map();
  for(const a of accountRecords.filter(a=>!accountFilter.value||a.id===accountFilter.value))balanceByCurrency.set(a.data.currency,(balanceByCurrency.get(a.data.currency)||0n)+balance(a));
  for(const [kind,label] of [['balance',copy.balance],['income',t('income')],['expense',t('expense')]]){
   const tile=button('',()=>kind==='balance'?referenceNavigate('money','accounts'):drill(kind),'card finance-metric '+kind);tile.append(E('span',label,'small'));
   const values=kind==='balance'?[...balanceByCurrency.entries()]:currencies.filter(code=>!accountFilter.value||accountRecords.find(a=>a.id===accountFilter.value)?.data.currency===code).map(code=>[code,financeTotals(filtered,code)[kind]]);
   for(const [code,amount]of values)tile.append(moneyElement(amount,code));
   if(!values.length)tile.append(E('strong','—'));
   tile.append(E('span',({ru:'Подробнее',en:'View details','uz-Latn':'Batafsil','uz-Cyrl':'Батафсил'})[state.lang]||'View details','finance-metric-link'));
   metricGrid.append(tile);
  }
  const values=financeTotals(filtered,currency.value),categories=mode.value==='categories';legend.replaceChildren();
  legend.classList.toggle('chart-category-legend',categories);categoryHint.hidden=!categories;chart.classList.toggle('finance-category-analysis',categories);
  if(categories&&currency.value){
   const groups=financeExpenseGroups(filtered,currency.value,breakdownKind.value),sum=groups.reduce((total,group)=>total+group.amount,0n);
   for(const group of groups){
    const item=button('',()=>drill(breakdownKind.value,group.id),'chart-category-row'),label=E('span'),swatch=E('span',undefined,'chart-category-swatch');
    item.setAttribute('aria-pressed',String(drilldown&&categoryFilter===group.id));
    swatch.style.backgroundColor=group.color;swatch.setAttribute('aria-hidden','true');
    append(label,swatch,E('span',group.label));
    const part=sum?Number(group.amount*1000000n/sum)/1000000:0;
    const percent=part>0&&part<.001?'<'+new Intl.NumberFormat(state.lang,{style:'percent',maximumFractionDigits:1}).format(.001):new Intl.NumberFormat(state.lang,{style:'percent',maximumFractionDigits:1}).format(part);
    append(item,label,moneyElement(group.amount,currency.value),E('small',percent));legend.append(item);
   }
   if(!groups.length)legend.append(emptyPanel('money',t('empty_money')));
   let cursor=0;const stops=[];for(const group of groups){const start=cursor;cursor+=sum?Number(group.amount*1000000n/sum)/10000:0;stops.push(group.color+' '+start+'% '+cursor+'%');}
   categoryRing.style.background=sum?'conic-gradient('+stops.join(',')+')':'var(--ux-border)';
   const outsideTotal=moneyParts(sum,currency.value).number.length>13;
   categoryTotal.replaceChildren(E('span',t(breakdownKind.value),'small'),outsideTotal?E('span',currency.value,'small'):moneyElement(sum,currency.value));
   categoryLargeTotal.hidden=!outsideTotal;categoryLargeTotal.replaceChildren();if(outsideTotal)categoryLargeTotal.append(moneyElement(sum,currency.value));
  }else if(currency.value){
   for(const kind of ['income','expense']){const item=E('div',undefined,'chart-legend-row '+kind);append(item,E('span',t(kind)),moneyElement(values[kind],currency.value));legend.append(item);}
  }else legend.append(emptyPanel('money',t('empty_money')));
  state.financeChartMode=mode.value;if(!categories){state.chart=mode.value;preferences();}
  state.financeBreakdownKind=breakdownKind.value;categoryVisual.hidden=!categories||!currency.value;categoryLargeTotal.hidden=!categories||!currency.value||moneyParts(financeTotals(filtered,currency.value)[breakdownKind.value],currency.value).number.length<=13;breakdownKind.hidden=!categories;
  canvas.hidden=categories||mode.value==='compact'||!currency.value;if(chart.isConnected&&!categories)drawChart(canvas,currency.value,filtered,mode.value);
  const transfers=records('transfer').filter(r=>(!accountFilter.value||[r.data.from_id,r.data.to_id].includes(accountFilter.value))&&(!from.value||r.data.date>=from.value)&&(!to.value||r.data.date<=to.value)&&(!search.value||(t('family_kind_transfer')+' '+r.data.date).toLocaleLowerCase(state.lang).includes(search.value.toLocaleLowerCase(state.lang))));
  const categoryIds=new Set(transactionCategoryChoices().map(([id])=>id));
  const drillRows=drilldown?filtered.filter(r=>r.data.kind===breakdownKind.value&&r.data.currency===currency.value&&(categoryFilter===null||(categoryIds.has(r.data.category)?r.data.category:'')===categoryFilter)):filtered;
  const entries=[...drillRows,...(drilldown?[]:transfers)].sort((a,b)=>b.data.date.localeCompare(a.data.date)||(b.seq||0)-(a.seq||0)||b.id.localeCompare(a.id));
  clearDrill.hidden=!drilldown;pagination.hidden=view==='overview'&&!drilldown;
  const ledgerHeading=ledger.querySelector('h2');ledgerHeading.textContent=drilldown?t(breakdownKind.value)+(categoryFilter===null?'':' · '+new Map(transactionCategoryChoices()).get(categoryFilter)):view==='overview'?copy.recent:t('web_history');
  const allOperations=ledger.querySelector('.finance-ledger-all');if(allOperations)allOperations.hidden=drilldown;
  const accountsById=new Map(accountRecords.map(account=>[account.id,account.data]));ledgerRows.replaceChildren();
  const filterKey=JSON.stringify(state.financeFilters);if(filterKey!==ledgerFilterKey){ledgerLimit=25;ledgerFilterKey=filterKey;}
  const displayed=entries.slice(0,view==='overview'&&!drilldown?5:ledgerLimit);
  for(const [index,entry]of displayed.entries()){
   const data=entry.data,isTransfer=entry.kind==='transfer',kind=isTransfer?'transfer':data.kind;
   const row=E('div',undefined,'row ledger-row'),text=E('div',undefined,'text'),label=isTransfer?t('family_kind_transfer'):data.label||t(kind);
   const account=isTransfer?[accountsById.get(data.from_id)?.name,accountsById.get(data.to_id)?.name].filter(Boolean).join(' → '):accountsById.get(data.account_id)?.name;
   append(text,E('h3',label),E('p',[displayDate(data.date),account].filter(Boolean).join(' · '),'small'));
   const receiving=isTransfer&&accountFilter.value===data.to_id,transferCurrency=accountsById.get(receiving?data.to_id:data.from_id)?.currency;
   const amount=isTransfer?(transferCurrency?money(receiving?data.received_minor:data.sent_minor,transferCurrency):''):(kind==='expense'?'− ':'+ ')+money(data.amount_minor,data.currency);
   const amountCode=isTransfer?transferCurrency:data.currency;
   const amountNode=amountCode?moneyElement(isTransfer?(receiving?data.received_minor:data.sent_minor):data.amount_minor,amountCode,kind,isTransfer?'':kind==='expense'?'− ':'+ '):E('strong',amount,kind);
   append(row,text,amountNode,iconButton('more',t('edit')+' · '+label,()=>editRecord(entry.kind,entry)));
   ledgerRows.append(row);
  }
  const paginationCopy={ru:['Показано','из','Показать ещё'],en:['Showing','of','Show more'],'uz-Latn':['Ko‘rsatilgan','jami','Yana ko‘rsatish'],'uz-Cyrl':['Кўрсатилган','жами','Яна кўрсатиш']}[state.lang]||['Showing','of','Show more'];
  pageStatus.textContent=paginationCopy[0]+' '+displayed.length+' '+paginationCopy[1]+' '+entries.length;
  showMore.hidden=displayed.length>=entries.length;showMore.textContent=paginationCopy[2]+' '+Math.min(25,entries.length-displayed.length);
  if(!entries.length)ledgerRows.append(E('p',t(active?'web_no_results':'empty_money'),'empty'));
 }
 redrawFinance=draw;
 for(const field of [search,from,to,accountFilter,currency,mode,breakdownKind])field.addEventListener(field===search?'input':'change',()=>{if(field===breakdownKind){categoryFilter=null;if(drilldown)ledgerLimit=25;}draw();});
 requestAnimationFrame(draw);
}
function financeTotals(rows,currency){let income=0n,expense=0n;for(const r of rows.filter(r=>r.data.currency===currency)){if(r.data.kind==='income')income+=BigInt(r.data.amount_minor);else expense+=BigInt(r.data.amount_minor);}return {income,expense};}
function drawChart(canvas,currency,rows=records('transaction'),chartStyle=state.chart){
 const ctx=canvas.getContext('2d');ctx.clearRect(0,0,720,320);if(!currency)return;
 const {income,expense}=financeTotals(rows,currency),style=getComputedStyle(document.body),colors=[style.getPropertyValue('--income'),style.getPropertyValue('--expense')],values=[income,expense],sum=income+expense,max=income>expense?income:expense;
 canvas.setAttribute('aria-label',t('income')+': '+money(income,currency)+'; '+t('expense')+': '+money(expense,currency));
 ctx.font=(14*720/Math.max(canvas.clientWidth||720,240))+'px system-ui';ctx.fillStyle=style.getPropertyValue('--muted');if(!sum){ctx.fillText(t('empty_money'),24,150);return;}
 const ratio=(v,m=max)=>Number(v*1000000n/m)/1000000;
 if(chartStyle==='donut'){let angle=-Math.PI/2;values.forEach((v,i)=>{if(!v)return;ctx.beginPath();ctx.strokeStyle=colors[i];ctx.lineWidth=42;ctx.arc(360,155,100,angle,angle+ratio(v,sum)*Math.PI*2);ctx.stroke();angle+=ratio(v,sum)*Math.PI*2;});return;}
 if(['line','smooth'].includes(chartStyle)){
  const days=new Map();for(const r of rows.filter(r=>r.data.currency===currency)){if(!days.has(r.data.date))days.set(r.data.date,[0n,0n]);days.get(r.data.date)[r.data.kind==='income'?0:1]+=BigInt(r.data.amount_minor);}
  const dates=[...days.keys()].sort();const start=Date.parse(dates[0]),end=Date.parse(dates.at(-1));
  for(let k=0;k<2;k++){let running=0n;const points=dates.map(date=>{running+=days.get(date)[k];return [40+(end===start?0:(Date.parse(date)-start)/(end-start)*640),270-ratio(running)*225];});ctx.strokeStyle=colors[k];ctx.lineWidth=3;ctx.beginPath();points.forEach(([x,y],i)=>{if(!i)ctx.moveTo(x,y);else if(chartStyle==='smooth'){const [px,py]=points[i-1],mid=(px+x)/2;ctx.bezierCurveTo(mid,py,mid,y,x,y);}else ctx.lineTo(x,y);});ctx.stroke();for(const [x,y]of points){ctx.fillStyle=colors[k];ctx.beginPath();ctx.arc(x,y,3,0,Math.PI*2);ctx.fill();}}
  ctx.fillStyle=style.getPropertyValue('--muted');ctx.fillText(dates[0],40,304);ctx.textAlign='right';ctx.fillText(dates.at(-1),680,304);ctx.textAlign='left';return;
 }
 values.forEach((v,i)=>{ctx.fillStyle=colors[i];ctx.fillText(t(i?'expense':'income'),24,48+i*135);ctx.fillRect(24,64+i*135,ratio(v)*650,44);ctx.fillStyle=style.getPropertyValue('--ink');ctx.fillText(money(v,currency),24,132+i*135);});
}
function createSpace(kind){let operation;const d=dialog(t(kind==='family'?'family_create':'web_personal_create'),container=>form(container,'',f=>({name:input(f,'name',t('name'))}),async v=>{operation=operation||{id:crypto.randomUUID(),workspace_id:crypto.randomUUID(),action:'workspace.create',kind,name:v.name.value};try{await call('family',operation);}catch(e){if(!e.uncertain)operation=null;throw e;}state.space=operation.workspace_id;d.close();await refresh();render();}));}
function acceptInvite(){
 let operation,accepted=false;
 const d=dialog(t('family_accept'),container=>form(container,'',f=>({invitation:input(f,'invitation',t('family_invitation'))}),async v=>{
  operation??={id:crypto.randomUUID(),invitation:v.invitation.value};
  if(!accepted){try{await call('invitations/accept',operation);accepted=true;}catch(error){if(!error.uncertain)operation=null;throw error;}}
  try{await refresh();}catch(error){throw {...error,refreshOnly:true};}
  d.close();render();
 }));
}
function familyPanel(m){
 const copy={
  ru:['Вместе проще','Личные планы и общие дела — в своих пространствах.','Активно','Личное пространство','Семейное пространство','Создать пространство','Ваши личные планы и заметки','Общие задачи, бюджет и календарь','Участники пространства','Участников','Владелец'],
  en:['Better together','Personal plans and shared activities, in your own spaces.','Active','Personal workspace','Family workspace','Create workspace','Your personal plans and notes','Shared tasks, budget and calendar','Workspace members','Members','Owner'],
  'uz-Latn':['Birga osonroq','Shaxsiy rejalar va umumiy ishlar — o‘z makonlaringizda.','Faol','Shaxsiy makon','Oilaviy makon','Makon yaratish','Shaxsiy rejalaringiz va qaydlaringiz','Umumiy vazifalar, budjet va taqvim','Makon a’zolari','A’zolar','Egasi'],
  'uz-Cyrl':['Бирга осонроқ','Шахсий режалар ва умумий ишлар — ўз маконларингизда.','Фаол','Шахсий макон','Оилавий макон','Макон яратиш','Шахсий режаларингиз ва қайдларингиз','Умумий вазифалар, бюджет ва тақвим','Макон аъзолари','Аъзолар','Эгаси']
 }[state.lang]||['Better together','Personal plans and shared activities, in your own spaces.','Active','Personal workspace','Family workspace','Create workspace','Your personal plans and notes','Shared tasks, budget and calendar','Workspace members','Members','Owner'];
 const page=m.closest('main'),intro=page?.querySelector('.intro');
 page?.classList.add('reference-family-page');
 const breadcrumb=root.querySelector('.reference-breadcrumb strong');if(breadcrumb)breadcrumb.textContent=referenceCopy(4);
 if(intro){const heading=intro.querySelector('h1');heading.textContent=referenceCopy(4);heading.before(E('div',copy[0],'eyebrow'));heading.after(E('p',copy[1],'reference-account-description'));}
 const c=card();c.classList.add('family-panel','reference-family-panel');
 const spaces=E('div',undefined,'reference-space-grid');
 for(const workspace of state.spaces){
  const active=workspace.id===state.space;
  const choice=button('',()=>{
   if(active)return;
   const picker=root.querySelector('select[name=workspace]');
   if(picker){picker.value=workspace.id;picker.dispatchEvent(new Event('change',{bubbles:true}));}
  },'reference-space-card');
  choice.dataset.workspace=workspace.id;choice.setAttribute('aria-pressed',String(active));
  const top=E('span',undefined,'reference-space-card-top');
  append(top,E('span',(workspace.name||'U').slice(0,1).toLocaleUpperCase(state.lang),'reference-avatar'));
  if(active)top.append(E('span','✓ '+copy[2],'reference-space-active'));
  append(choice,top,E('strong',workspace.name,'reference-space-name'),E('span',workspace.kind==='family'?copy[4]:copy[3],'reference-space-kind'));
  if(active&&state.roster?.space?.id===workspace.id)choice.append(E('span',copy[9]+': '+state.roster.members.length,'reference-space-member-count'));
  const detail=E('span',workspace.kind==='family'?copy[7]:copy[6],'reference-space-detail');detail.prepend(icon(workspace.kind==='family'?'account':'notes'));choice.append(detail);spaces.append(choice);
 }
 const create=button('',()=>createSpace('family'),'reference-space-card reference-space-create');
 append(create,icon('add'),E('strong',copy[5]),E('span',t('family_create'),'reference-space-kind'));spaces.append(create);
 c.append(spaces);
 const actions=E('div',undefined,'family-workspace-actions');
 append(actions,button(t('web_personal_create'),()=>createSpace('personal'),'text-button'),
  button(t('family_accept'),acceptInvite,'text-button'));
 append(c,actions);m.append(c);
 if(!state.roster)return;
 const {space,members,profiles}=state.roster;
 const roster=card(copy[8]);roster.classList.add('family-roster','reference-family-roster');
 if(space.name)roster.append(E('p',space.name,'reference-roster-space'));
 for(const member of members){
  const self=member.user_id===state.session.user_id;
  const row=E('div',undefined,'row reference-family-member'),avatar=E('span',undefined,'reference-avatar');
  if(self)avatar.textContent=(state.session.email||'U').slice(0,1).toLocaleUpperCase(state.lang);else avatar.append(icon('account'));
  const role=member.role==='owner'?copy[10]:t('family_'+member.role);
  const identity=append(E('div',undefined,'reference-member-copy'),E('strong',self?state.session.email:member.user_id),E('span',(self?t('family_you')+' · ':'')+role));
  append(row,avatar,identity,E('span',role,'reference-member-role'));
  roster.append(row);
 }
 c.append(roster);
 if(space.kind==='family'&&['parent','owner'].includes(space.role)){
  const invite=button(t('family_invite'),()=>dialog(t('family_invite'),container=>{let operation;form(container,'',f=>({email:input(f,'email',t('family_invite_email'),'email'),role:select(f,'role',t('family_role'),['adult','parent','child'].map(k=>[k,t('family_'+k)]),'adult'),profile:select(f,'profile',t('family_child'),[['',t('family_none')],...profiles.map(p=>[p.id,p.name])],'')}),async v=>{operation=operation||{id:crypto.randomUUID(),workspace_id:space.id,action:'invite.create',email:v.email.value,role:v.role.value,profile_id:v.role.value==='child'?v.profile.value:null};const invite=await call('family',operation);replaceDialog(container,E('h2',t('family_invite')),E('p',t('family_invite_hint')),E('pre',invite.invitation),button(t('close'),()=>container.close()));});}),'reference-family-invite');
  invite.prepend(icon('add'));(intro||actions).append(invite);
  actions.append(button(t('family_child_add'),()=>{const d=dialog(t('family_child_add'),container=>form(container,'',f=>({name:input(f,'name',t('name'))}),async v=>{await call('family',{id:crypto.randomUUID(),workspace_id:space.id,action:'child.save',profile_id:crypto.randomUUID(),revision:0,name:v.name.value,permissions:['view_shared','complete_tasks']});d.close();await refresh();render();}));},'text-button'));
 }
}
const NOTIFICATION_COPY={
 ru:{title:'Уведомления',intro:'Напоминания календаря на этом устройстве, даже когда ULADIM закрыт.',off:'Выключены на этом устройстве',on:'Включены на этом устройстве',enable:'Включить уведомления',disable:'Выключить на устройстве',test:'Проверить доставку',loading:'Проверяем настройки…',unavailable:'Этот браузер не поддерживает фоновые уведомления. Откройте ULADIM в актуальном браузере.',install:'На iPhone и iPad уведомления работают в установленном приложении с iOS 16.4 или новее. В Safari нажмите «Поделиться» → «На экран Домой», затем откройте ULADIM с экрана Домой.',denied:'Уведомления запрещены в настройках браузера. Разрешите их для ULADIM и вернитесь сюда.',update:'Чтобы подключить уведомления, закройте остальные окна ULADIM и откройте приложение снова: обновление ещё устанавливается.',permission:'Разрешение не получено. Можно включить уведомления позже.',options:'Параметры напоминаний',lead:'До начала события',minutes:'мин',priority:'Приоритет доставки',high:'Высокий',normal:'Обычный',save:'Сохранить параметры',saved:'Параметры сохранены',schedule:'События со временем — заранее; события на весь день — в 09:00 по часовому поясу этого устройства.',privacy:'Текст уведомлений не раскрывает названия событий. Звук и показ на экране определяет система устройства. Высокий приоритет не обходит режим «Не беспокоить».',delivery:'Последняя проверка доставки',queued:'Уведомление в очереди',sending:'Отправляем в push-сервис…',accepted:'Push-сервис принял уведомление. Ждём ответа устройства.',displayed:'Передано системе устройства. Проверьте экран и настройки звука.',suppressed:'Показ пропущен: сеанс недоступен или устройство не разрешило уведомление.',failed:'Доставка не подтверждена. Проверьте соединение и разрешения устройства.',cancelled:'Отправка отменена',pending:'Ответ устройства пока не получен. Можно вернуться сюда позже.',error:'Не удалось обновить настройки уведомлений. Проверьте соединение и повторите.',cooldown:'Повторная проверка доступна через минуту.',retry:'Повторить',enabledHelp:'Только этот браузер или установленное веб-приложение. Другие устройства настраиваются отдельно.',disablePartial:'Не удалось подтвердить отключение на сервере. Повторите отключение.',testHelp:'Проверка отправит одно уведомление. Подтверждение системы не означает, что баннер был виден.'},
 en:{title:'Notifications',intro:'Calendar reminders on this device, even when ULADIM is closed.',off:'Off on this device',on:'On on this device',enable:'Enable notifications',disable:'Turn off on this device',test:'Check delivery',loading:'Checking settings…',unavailable:'This browser does not support background notifications. Open ULADIM in an up-to-date browser.',install:'On iPhone and iPad, notifications require the installed app and iOS 16.4 or later. In Safari, choose Share → Add to Home Screen, then open ULADIM from your Home Screen.',denied:'Notifications are blocked in browser settings. Allow them for ULADIM and return here.',update:'Close the other ULADIM windows and reopen the app to enable notifications: an update is still installing.',permission:'Permission was not granted. You can enable notifications later.',options:'Reminder settings',lead:'Before an event',minutes:'min',priority:'Delivery priority',high:'High',normal:'Normal',save:'Save settings',saved:'Settings saved',schedule:'Timed events arrive in advance; all-day events at 09:00 in this device’s time zone.',privacy:'Notification text does not reveal event titles. Your device controls sound and banners. High priority does not override Do Not Disturb.',delivery:'Latest delivery check',queued:'Notification queued',sending:'Sending to the push service…',accepted:'The push service accepted the notification. Waiting for the device.',displayed:'Passed to the device system. Check your screen and sound settings.',suppressed:'Display skipped: the session was unavailable or the device did not allow notifications.',failed:'Delivery was not confirmed. Check your connection and device permissions.',cancelled:'Sending cancelled',pending:'The device has not responded yet. You can return here later.',error:'Could not update notification settings. Check your connection and retry.',cooldown:'Another check is available in one minute.',retry:'Retry',enabledHelp:'Applies to this browser or installed web app only. Set up other devices separately.',disablePartial:'The server did not confirm disabling notifications. Try turning them off again.',testHelp:'This sends one notification. System confirmation does not mean the banner was visible.'},
 'uz-Latn':{title:'Bildirishnomalar',intro:'ULADIM yopiq bo‘lsa ham, ushbu qurilmada taqvim eslatmalari.',off:'Bu qurilmada o‘chirilgan',on:'Bu qurilmada yoqilgan',enable:'Bildirishnomalarni yoqish',disable:'Bu qurilmada o‘chirish',test:'Yetkazishni tekshirish',loading:'Sozlamalar tekshirilmoqda…',unavailable:'Bu brauzer fon bildirishnomalarini qo‘llamaydi. ULADIMni yangilangan brauzerda oching.',install:'iPhone va iPadda bildirishnomalar o‘rnatilgan ilovada, iOS 16.4 yoki yangiroq tizimda ishlaydi. Safarida Ulashish → Bosh ekranga qo‘shish tugmasini bosing va ULADIMni bosh ekrandan oching.',denied:'Brauzer sozlamalarida bildirishnomalar taqiqlangan. ULADIM uchun ruxsat bering va bu yerga qayting.',update:'Yangilanish hali o‘rnatilmoqda. ULADIMning boshqa oynalarini yoping va ilovani qayta oching.',permission:'Ruxsat berilmadi. Bildirishnomalarni keyinroq yoqishingiz mumkin.',options:'Eslatma sozlamalari',lead:'Tadbirdan oldin',minutes:'daq',priority:'Yetkazish ustuvorligi',high:'Yuqori',normal:'Oddiy',save:'Sozlamalarni saqlash',saved:'Sozlamalar saqlandi',schedule:'Vaqti belgilangan tadbirlar oldindan, kun bo‘yi tadbirlar esa qurilma vaqt mintaqasida 09:00 da eslatiladi.',privacy:'Bildirishnomada tadbir nomi ko‘rsatilmaydi. Ovoz va bannerlarni qurilma boshqaradi. Yuqori ustuvorlik «Bezovta qilmang» rejimini chetlab o‘tmaydi.',delivery:'So‘nggi yetkazish tekshiruvi',queued:'Bildirishnoma navbatda',sending:'Push xizmatiga yuborilmoqda…',accepted:'Push xizmati qabul qildi. Qurilma javobi kutilmoqda.',displayed:'Qurilma tizimiga uzatildi. Ekran va ovoz sozlamalarini tekshiring.',suppressed:'Ko‘rsatish o‘tkazib yuborildi: seans mavjud emas yoki qurilma ruxsat bermadi.',failed:'Yetkazish tasdiqlanmadi. Ulanish va qurilma ruxsatlarini tekshiring.',cancelled:'Yuborish bekor qilindi',pending:'Qurilma hali javob bermadi. Keyinroq qaytishingiz mumkin.',error:'Bildirishnoma sozlamalarini yangilab bo‘lmadi. Ulanishni tekshirib qayta urinib ko‘ring.',cooldown:'Bir daqiqadan so‘ng qayta tekshirish mumkin.',retry:'Qayta urinish',enabledHelp:'Faqat shu brauzer yoki o‘rnatilgan veb-ilova uchun. Boshqa qurilmalar alohida sozlanadi.',disablePartial:'Server o‘chirishni tasdiqlamadi. Qayta o‘chirib ko‘ring.',testHelp:'Tekshiruv bitta bildirishnoma yuboradi. Tizim tasdig‘i banner ko‘ringanini anglatmaydi.'},
 'uz-Cyrl':{title:'Билдиришномалар',intro:'ULADIM ёпиқ бўлса ҳам, ушбу қурилмада тақвим эслатмалари.',off:'Бу қурилмада ўчирилган',on:'Бу қурилмада ёқилган',enable:'Билдиришномаларни ёқиш',disable:'Бу қурилмада ўчириш',test:'Етказишни текшириш',loading:'Созламалар текширилмоқда…',unavailable:'Бу браузер фон билдиришномаларини қўлламайди. ULADIMни янгиланган браузерда очинг.',install:'iPhone ва iPadда билдиришномалар ўрнатилган иловада, iOS 16.4 ёки янгироқ тизимда ишлайди. Safariда Улашиш → Бош экранга қўшиш тугмасини босинг ва ULADIMни бош экрандан очинг.',denied:'Браузер созламаларида билдиришномалар тақиқланган. ULADIM учун рухсат беринг ва бу ерга қайтинг.',update:'Янгиланиш ҳали ўрнатилмоқда. ULADIMнинг бошқа ойналарини ёпинг ва иловани қайта очинг.',permission:'Рухсат берилмади. Билдиришномаларни кейинроқ ёқишингиз мумкин.',options:'Эслатма созламалари',lead:'Тадбирдан олдин',minutes:'дақ',priority:'Етказиш устуворлиги',high:'Юқори',normal:'Оддий',save:'Созламаларни сақлаш',saved:'Созламалар сақланди',schedule:'Вақти белгиланган тадбирлар олдиндан, кун бўйи тадбирлар эса қурилма вақт минтақасида 09:00 да эслатилади.',privacy:'Билдиришномада тадбир номи кўрсатилмайди. Овоз ва баннерларни қурилма бошқаради. Юқори устуворлик «Безовта қилманг» режимини четлаб ўтмайди.',delivery:'Сўнгги етказиш текшируви',queued:'Билдиришнома навбатда',sending:'Push хизматига юборилмоқда…',accepted:'Push хизмати қабул қилди. Қурилма жавоби кутилмоқда.',displayed:'Қурилма тизимига узатилди. Экран ва овоз созламаларини текширинг.',suppressed:'Кўрсатиш ўтказиб юборилди: сеанс мавжуд эмас ёки қурилма рухсат бермади.',failed:'Етказиш тасдиқланмади. Уланиш ва қурилма рухсатларини текширинг.',cancelled:'Юбориш бекор қилинди',pending:'Қурилма ҳали жавоб бермади. Кейинроқ қайтишингиз мумкин.',error:'Билдиришнома созламаларини янгилаб бўлмади. Уланишни текшириб қайта уриниб кўринг.',cooldown:'Бир дақиқадан сўнг қайта текшириш мумкин.',retry:'Қайта уриниш',enabledHelp:'Фақат шу браузер ёки ўрнатилган веб-илова учун. Бошқа қурилмалар алоҳида созланади.',disablePartial:'Сервер ўчиришни тасдиқламади. Қайта ўчириб кўринг.',testHelp:'Текширув битта билдиришнома юборади. Тизим тасдиғи баннер кўринганини англатмайди.'}
};
for(const [locale,copy]of Object.entries(NOTIFICATION_COPY))WORKSPACE_COPY[locale].web_notifications=copy.title;
function notificationSupport(){
 const ios=/iP(ad|hone|od)/.test(navigator.userAgent)||(navigator.platform==='MacIntel'&&navigator.maxTouchPoints>1);
 if(ios&&!navigator.standalone&&!matchMedia('(display-mode: standalone)').matches)return 'install';
 return window.isSecureContext===true&&'Notification'in window&&'serviceWorker'in navigator&&'PushManager'in window?'supported':'unavailable';
}
function notificationTimeout(promise,ms){return new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(new Error('notification_timeout')),ms);promise.then(value=>{clearTimeout(timer);resolve(value);},error=>{clearTimeout(timer);reject(error);});});}
async function notificationWorker(){
 await navigator.serviceWorker.register('/app/sw.js',{scope:'/app'});
 const registration=await notificationTimeout(navigator.serviceWorker.ready,12000);
 const supported=await new Promise(resolve=>{
  const channel=new MessageChannel(),timer=setTimeout(()=>{channel.port1.close();resolve(false);},2000);
  channel.port1.onmessage=event=>{clearTimeout(timer);channel.port1.close();resolve(event.data?.supported===true&&event.data.version===1);};
  if(!registration.active){clearTimeout(timer);resolve(false);return;}
  registration.active.postMessage({type:'uladim-notifications-capabilities'},[channel.port2]);
 });
 return {registration,supported};
}
function notificationKey(value){const text=atob(value.replace(/-/g,'+').replace(/_/g,'/'));return Uint8Array.from(text,c=>c.charCodeAt(0));}
function notificationSettings(subscription,settings){return {subscription:subscription.toJSON(),lead_minutes:settings.lead_minutes||15,priority:settings.priority||'high',timezone:Intl.DateTimeFormat().resolvedOptions().timeZone||'UTC'};}
async function refreshNotificationTimezone(){
 const epoch=privateEpoch;if(!state.session||notificationSupport()!=='supported'||Notification.permission!=='granted')return;
 try{
  const settings=await call('notifications');if(epoch!==privateEpoch||!settings.enabled)return;
  const worker=await notificationWorker();if(epoch!==privateEpoch||!worker.supported)return;
  const subscription=await worker.registration.pushManager.getSubscription();
  if(subscription&&epoch===privateEpoch&&state.session)await call('notifications/subscribe',notificationSettings(subscription,settings));
 }catch{} // Existing opt-in only; startup must never show a permission dialog.
}
async function notificationPage(content){
 const copy=NOTIFICATION_COPY[state.lang]||NOTIFICATION_COPY.en,epoch=privateEpoch;
 const active=()=>epoch===privateEpoch&&content.isConnected&&state.tab==='account'&&state.settingsTab==='notifications';
 const panel=card(copy.title);panel.classList.add('notification-panel');content.append(panel);
 append(panel,E('p',copy.intro,'notification-intro'));
 const status=E('p',copy.loading,'notification-status');status.setAttribute('role','status');panel.append(status);
 const support=notificationSupport();
 if(support!=='supported'){status.textContent=copy[support];status.dataset.state='attention';return;}
 const controls=E('div',undefined,'notification-actions'),feedback=E('p','','notification-feedback');feedback.setAttribute('role','status');
 const delivery=E('section',undefined,'notification-delivery');delivery.setAttribute('aria-live','polite');
 append(panel,controls,feedback,E('p',copy.enabledHelp,'small'),delivery);
 const details=E('details',undefined,'notification-options');details.append(E('summary',copy.options));
 const fields=E('div',undefined,'notification-option-fields');
 const lead=select(fields,'notification-lead',copy.lead,[5,15,30,60].map(n=>[String(n),n+' '+copy.minutes]),'15');
 const priority=select(fields,'notification-priority',copy.priority,[['high',copy.high],['normal',copy.normal]],'high');
 const save=button(copy.save,()=>execute(async()=>{settings=await call('notifications/subscribe',notificationSettings(subscription,{lead_minutes:Number(lead.value),priority:priority.value}));feedback.textContent=copy.saved;await draw();}),'secondary');
 fields.append(save);append(details,fields,E('p',copy.schedule,'small'));append(panel,details,E('p',copy.privacy,'small notification-privacy'));
 let settings=null,worker=null,subscription=null,busy=false;
 const failure=error=>{if(!active())return;feedback.textContent=['rate_limited','notification_test_rate_limited','notification_test_cooldown'].includes(error.code)?copy.cooldown:copy.error;if(error.code==='unauthorized')report(error);};
 async function execute(run){if(busy||!active())return;busy=true;panel.setAttribute('aria-busy','true');controls.querySelectorAll('button').forEach(b=>b.disabled=true);save.disabled=true;try{await run();}catch(error){failure(error);}finally{busy=false;if(active()){panel.removeAttribute('aria-busy');await draw();}}}
 function showDelivery(value,pending=false){delivery.replaceChildren();if(!value)return;append(delivery,E('h3',copy.delivery),E('p',copy[value.state]||copy.pending));if(pending)delivery.append(E('p',copy.pending,'small'));}
 async function draw(){
  if(!active())return;
  const permission=Notification.permission,on=Boolean(settings?.enabled&&subscription&&permission==='granted');
  status.textContent=permission==='denied'?copy.denied:!worker?.supported?copy.update:on?copy.on:copy.off;status.dataset.state=on?'enabled':'attention';
  controls.replaceChildren();save.disabled=!on||busy;lead.disabled=priority.disabled=busy;
  if(on){
   controls.append(button(copy.test,()=>execute(async()=>{
    const test=await call('notifications/test',{});showDelivery({state:test.state});
    for(let attempt=0;attempt<15&&active();attempt++){
     await new Promise(resolve=>setTimeout(resolve,2000));if(!active())return;
     settings=await call('notifications');const last=settings.last_delivery;
     if(last?.id===test.delivery_id){showDelivery(last);if(['displayed','suppressed','failed','cancelled'].includes(last.state))return;}
    }
    if(active())showDelivery(settings?.last_delivery,true);
   }),'primary'));
   controls.append(button(copy.disable,()=>execute(async()=>{
    const results=await Promise.allSettled([call('notifications/unsubscribe',{}),subscription.unsubscribe()]);
    if(results[1].status==='fulfilled'&&results[1].value)subscription=null;
    if(results[0].status==='rejected'){feedback.textContent=copy.disablePartial;return;}
    settings=results[0].value;subscription=await worker.registration.pushManager.getSubscription();feedback.textContent='';
   }),'secondary'));
  }else{
   const enable=button(copy.enable,()=>{
    // requestPermission must run synchronously inside this explicit click.
    const permissionResult=Notification.permission==='default'?Notification.requestPermission():Promise.resolve(Notification.permission);
    return execute(async()=>{
     const permission=await permissionResult;if(!active())return;
     if(permission!=='granted'){feedback.textContent=copy.permission;return;}
     const prepared=await call('notifications/prepare');if(!active())return;
     subscription=await worker.registration.pushManager.getSubscription();
     if(subscription&&settings?.last_delivery?.error_code==='subscription_gone'){
      // A provider can expire an endpoint before the browser removes it.
      // Explicit reconnection must obtain a fresh subscription instead of
      // registering the same dead endpoint again and repeating a 410 loop.
      if(!await subscription.unsubscribe())throw new Error('notification_reconnect');
      subscription=null;
     }
     subscription=subscription||await worker.registration.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:notificationKey(prepared.application_server_key)});
     if(!active())return;
     settings=await call('notifications/subscribe',notificationSettings(subscription,{lead_minutes:Number(lead.value),priority:priority.value}));feedback.textContent='';
    });
   },'primary');enable.disabled=permission==='denied'||!worker?.supported||busy;controls.append(enable);
   // Revocation may have removed the local subscription while the server still
   // has opt-in state. Keep a way to turn that server registration off.
   if(settings?.enabled)controls.append(button(copy.disable,()=>execute(async()=>{settings=await call('notifications/unsubscribe',{});}),'secondary'));
  }
  if(on)controls.append(E('p',copy.testHelp,'small notification-test-help'));
 }
 try{
  settings=await call('notifications');if(!active())return;
  lead.value=String(settings.lead_minutes||15);priority.value=settings.priority||'high';showDelivery(settings.last_delivery);
  worker=await notificationWorker();if(!active())return;subscription=await worker.registration.pushManager.getSubscription();await draw();
 }catch(error){if(!active())return;status.textContent=copy.error;failure(error);controls.append(button(copy.retry,()=>openSettings('notifications'),'secondary'));}
}
async function consumeNotificationLink(){
 const url=new URL(location.href);if(url.searchParams.get('notification')!=='calendar')return;
 const workspace=url.searchParams.get('workspace'),day=url.searchParams.get('day');
 for(const key of ['notification','workspace','day'])url.searchParams.delete(key);history.replaceState(null,'',url.pathname+url.search+url.hash);
 if(!state.spaces.some(space=>space.id===workspace)||!/^\d{4}-\d{2}-\d{2}$/.test(day||''))return;
 const date=new Date(day+'T12:00:00Z');if(!Number.isFinite(date.getTime())||date.toISOString().slice(0,10)!==day||date.getUTCFullYear()<1900||date.getUTCFullYear()>2200)return;
 if(state.space!==workspace){state.space=workspace;state.records=[];state.syncSpace=null;state.syncCursor=0;state.syncEpoch='';state.roster=null;await refresh();}
 state.tab='calendar';state.calendarDay=day;
}

function openSettings(section){
 state.tab='account';
 state.settingsTab=section;
 render();
 const back=root.querySelector('.settings-back');
 const target=section?(back?.getClientRects().length?back:root.querySelector('.settings-content h2')):root.querySelector('.settings-navigation button');
 if(target){if(target.tagName==='H2')target.tabIndex=-1;target.focus({preventScroll:true});}
 window.scrollTo({top:0,behavior:'instant'});
}
async function renderAccountPlan(content){
 const [ent,catalog]=await Promise.all([call('entitlements'),call('plans')]);
 if(!content.isConnected||state.tab!=='account'||state.settingsTab!=='plan')return;
 const copy={
  ru:{free:'«Пока всё доступно бесплатно»',current:'Ваш уровень доступа',intro:'Пользуйтесь всеми текущими возможностями. Оформлять подписку и вводить платёжные данные не нужно.',future:'Будущий тариф',included:'Сейчас включено',note:'Plus и Premium — подготовленная линейка на будущее. Цены и различия ещё не утверждены; продажи отключены.',titles:['Для личного ритма','Для своих привычек','Для совместных планов'],descriptions:['Задачи, заметки, календарь и финансы в одном месте.','Больше внимания настройкам, диаграммам и личному пространству.','Личные и семейные дела в отдельных пространствах.'],features:{personal_core:'Задачи, заметки, календарь и финансы',family_sync:'Семейное пространство и синхронизация',custom_charts:'Настройка диаграмм',extended_personalization:'Темы и палитры'}},
  en:{free:'“Everything is free for now”',current:'Your access level',intro:'Use all current features. No subscription or payment details are needed.',future:'Future plan',included:'Included now',note:'Plus and Premium are prepared for the future. Prices and differences have not been approved; sales are disabled.',titles:['For your daily rhythm','For your own way of working','For plans together'],descriptions:['Tasks, notes, calendar and finances together.','A focus on settings, charts and your personal workspace.','Personal and family activities in separate workspaces.'],features:{personal_core:'Tasks, notes, calendar and finances',family_sync:'Family workspace and sync',custom_charts:'Chart settings',extended_personalization:'Themes and palettes'}},
  'uz-Latn':{free:'«Hozircha barcha imkoniyatlar bepul»',current:'Kirish darajangiz',intro:'Barcha mavjud imkoniyatlardan foydalaning. Obuna yoki to‘lov ma’lumotlari kerak emas.',future:'Kelajakdagi tarif',included:'Hozir mavjud',note:'Plus va Premium kelajak uchun tayyorlangan. Narxlar va farqlar hali tasdiqlanmagan; savdo o‘chirilgan.',titles:['Kundalik maromingiz uchun','O‘zingizga mos ishlash uchun','Birgalikdagi rejalar uchun'],descriptions:['Vazifalar, qaydlar, taqvim va moliya bir joyda.','Sozlamalar, diagrammalar va shaxsiy makonga e’tibor.','Shaxsiy va oilaviy ishlar alohida makonlarda.'],features:{personal_core:'Vazifalar, qaydlar, taqvim va moliya',family_sync:'Oilaviy makon va sinxronlash',custom_charts:'Diagramma sozlamalari',extended_personalization:'Mavzular va ranglar'}},
  'uz-Cyrl':{free:'«Ҳозирча барча имкониятлар бепул»',current:'Кириш даражангиз',intro:'Барча мавжуд имкониятлардан фойдаланинг. Обуна ёки тўлов маълумотлари керак эмас.',future:'Келажакдаги тариф',included:'Ҳозир мавжуд',note:'Plus ва Premium келажак учун тайёрланган. Нархлар ва фарқлар ҳали тасдиқланмаган; савдо ўчирилган.',titles:['Кундалик маромингиз учун','Ўзингизга мос ишлаш учун','Биргаликдаги режалар учун'],descriptions:['Вазифалар, қайдлар, тақвим ва молия бир жойда.','Созламалар, диаграммалар ва шахсий маконга эътибор.','Шахсий ва оилавий ишлар алоҳида маконларда.'],features:{personal_core:'Вазифалар, қайдлар, тақвим ва молия',family_sync:'Оилавий макон ва синхронлаш',custom_charts:'Диаграмма созламалари',extended_personalization:'Мавзулар ва ранглар'}}
 };
 const c=copy[state.lang]||copy.en;
 const access=card(t('account_access'));access.classList.add('access-plan-status');
 append(access,E('p',c.current,'small'),E('strong',ent.tier,'access-plan-tier'),E('p',c.free,'access-free-note'),E('p',c.intro));
 const included=E('ul',undefined,'access-included-features');for(const [feature,label]of Object.entries(c.features))if(ent.features?.[feature])included.append(E('li',label));access.append(included);content.append(access);
 const grid=E('div',undefined,'access-plan-grid');
 ['Free','Plus','Premium'].forEach((tier,index)=>{
  const plan=catalog.tiers?.[tier];if(!plan)return;
  const item=E('section',undefined,'card access-plan-card');item.dataset.tier=tier;
  append(item,E('p',index===0?c.included:c.future,'access-plan-label'),E('h3',tier+' · '+c.titles[index]),E('p',c.descriptions[index]));
  grid.append(item);
 });
 append(content,grid,E('p',c.note,'small access-plan-boundary'));
}
async function account(m){
 const section=state.settingsTab||'profile';
 const pageTitle={notifications:'web_notifications',security:'account_privacy',devices:'account_devices','personal-import':'web_personal_import'};
 title(m,pageTitle[section]||'account_manage');m.classList.add('settings-page');
 m.dataset.settingsDetail=String(Boolean(state.settingsTab));
 const layout=E('div',undefined,'settings-layout'),navigation=E('nav',undefined,'settings-navigation'),content=E('section',undefined,'settings-content');
 content.dataset.section=section;
 navigation.setAttribute('aria-label',t('account_manage'));
 const back=button(t('web_back_settings'),()=>openSettings(''),'settings-back text-button');
 back.prepend(icon('back'));append(layout,navigation,content);append(m,back,layout);
 const sections=[['profile','profile'],['appearance','theme'],['security','account_privacy'],['devices','account_devices'],['notifications','web_notifications'],['family','family_account'],['personal-import','web_personal_import'],['plan','account_access'],['support','account_support']];
 for(const [key,label] of sections){
  const item=settingsRow(t(label),()=>openSettings(key),'settings-item');
  item.dataset.section=key;
  if(section===key)item.setAttribute('aria-current','page');
  navigation.append(item);
 }
 if(section==='profile'){
  const copy={
   ru:['Ваш аккаунт','Управляйте своим аккаунтом и предпочтениями.','Личные данные','Подтверждена','Не подтверждена','Выйти из аккаунта','Завершить текущий сеанс на этом устройстве'],
   en:['Your account','Manage your account and preferences.','Personal details','Verified','Not verified','Sign out of your account','End the current session on this device'],
   'uz-Latn':['Hisobingiz','Hisobingiz va sozlamalaringizni boshqaring.','Shaxsiy ma’lumotlar','Tasdiqlangan','Tasdiqlanmagan','Hisobdan chiqish','Ushbu qurilmadagi joriy seansni tugatish'],
   'uz-Cyrl':['Ҳисобингиз','Ҳисобингиз ва созламаларингизни бошқаринг.','Шахсий маълумотлар','Тасдиқланган','Тасдиқланмаган','Ҳисобдан чиқиш','Ушбу қурилмадаги жорий сеансни тугатиш']
  }[state.lang]||['Your account','Manage your account and preferences.','Personal details','Verified','Not verified','Sign out of your account','End the current session on this device'];
  m.classList.add('reference-profile-page');
  const heading=m.querySelector('.intro h1');heading.textContent=t('profile');heading.before(E('div',copy[0],'eyebrow'));heading.after(E('p',copy[1],'reference-account-description'));
  const c=card(t('profile'));c.classList.add('profile-summary');
  c.querySelector('h2').textContent=copy[2];
  const email=E('dd',state.session.email,'account-email');
  const identity=append(E('div',undefined,'reference-profile-identity'),E('span',(state.session.email||'U').slice(0,1).toLocaleUpperCase(state.lang),'reference-avatar'),append(E('dl',undefined,'profile-identity'),E('dt',t('family_email')),email));
  const verified=E('span',copy[state.session.verified?3:4],'reference-profile-verified');verified.dataset.verified=String(Boolean(state.session.verified));identity.append(verified);
  const options=E('div',undefined,'reference-profile-options');
  for(const [key,label,symbol]of [['appearance','theme','appearance'],['security','account_privacy','account'],['devices','account_devices','calendar'],['notifications','web_notifications','bell'],['family','family_account','account'],['personal-import','web_personal_import','notes'],['plan','account_access','money'],['support','account_support','notes']]){
   const action=settingsRow(t(label),()=>openSettings(key),'reference-profile-option'+(['appearance','security','devices'].includes(key)?'':' reference-profile-extra'));action.dataset.settingsSection=key;action.prepend(icon(symbol));options.append(action);
  }
  const logout=button(t('family_logout'),()=>openSettings('signout'),'text-button profile-logout');
  logout.append(icon('forward'));
  const signout=card();signout.classList.add('reference-profile-signout');
  append(signout,append(E('div'),E('h2',copy[5]),E('p',copy[6])),logout);
  append(c,identity,options);append(content,c,signout);
  if(['owner','staff'].includes(new URLSearchParams(location.search).get('setup')))content.append(button('ULADIM Control',enrollStaff));
 }
 if(section==='appearance'){const settings=card(t('theme'));settings.classList.add('settings-grid');content.append(settings);language(settings);const theme=select(settings,'theme',t('theme'),['system','light','dark'].map(k=>[k,t(k)]),state.theme);theme.addEventListener('change',()=>{state.theme=theme.value;preferences();});const palette=select(settings,'palette',t('palette'),[['violet',referenceCopy(12)],['forest',t('appearance_emerald')],['ocean',t('appearance_sky')],['pistachio',t('appearance_pistachio')]],state.palette);palette.addEventListener('change',()=>{state.palette=palette.value;preferences();});const install=E('details',undefined,'installation-help');append(install,E('summary','iPhone / iPad · PWA'),E('p',t('web_install')));settings.append(install,E('p',t('web_online'),'small'),E('p',t('web_locale_coverage'),'small'));if(deferredInstall)settings.append(button(t('web_install_button'),async()=>{await deferredInstall.prompt();deferredInstall=null;}));}
 if(section==='signout')signoutPage(content);
 if(section==='notifications')await notificationPage(content);
 if(section==='personal-import')await personalImportCenter(content).catch(report);
 if(section==='security')privacy(content);
 if(section==='devices')await devices(content).catch(error=>{if(error.code==='unauthorized'){report(error);return;}if(content.isConnected){content.replaceChildren(E('h2',t('account_devices')),E('p',errorText(error),'error'),button(t('retry'),()=>openSettings('devices'),'secondary'));}});
 if(section==='family'){familyPanel(content);familyPermissions(content);}
 try{if(section==='family')await incomingOwnership(content);if(section==='plan')await renderAccountPlan(content);if(section==='support')await support(content);}catch(e){report(e);}
}
function enrollStaff(){dialog('ULADIM Control',container=>{const owner=new URLSearchParams(location.search).get('setup')==='owner';const d=container;form(container,t('account_manage'),f=>({password:input(f,'password',t('family_password'),'password'),invitation:input(f,'invitation',t('family_invitation'))}),async v=>{const result=await call('staff/enrollment',{owner,password:v.password.value,invitation:v.invitation.value});replaceDialog(container,E('h2',t('account_mfa')),E('p',t('account_mfa_setup')),E('pre',result.totp_secret));form(container,'',f=>({code:input(f,'code',t('family_code'))}),async code=>{const r=await call('staff/confirm',{owner,enrollment:result.enrollment,code:code.code.value});replaceDialog(container,E('h2',t('account_mfa_recovery')),E('pre',r.recovery_codes.join('\n')),button(t('close'),()=>d.close()));});});});}
let activeSupportThread=null;
function supportCopy(){
 const all={
  ru:{category:'Тип обращения',back:'Все обращения',you:'Вы',empty:'Обращений пока нет',hint:'Опишите проблему или отправьте жалобу. Не прикладывайте пароли, коды и банковские выписки.',categories:[['other','Другой вопрос'],['bug','Ошибка в приложении'],['complaint','Жалоба'],['account','Аккаунт и вход'],['sync','Синхронизация'],['billing','Тарифы и доступ'],['privacy','Приватность'],['deletion','Удаление аккаунта']]},
  en:{category:'Request type',back:'All requests',you:'You',empty:'No requests yet',hint:'Describe a problem or send a complaint. Do not include passwords, codes or bank statements.',categories:[['other','Other question'],['bug','App problem'],['complaint','Complaint'],['account','Account and sign-in'],['sync','Sync'],['billing','Plans and access'],['privacy','Privacy'],['deletion','Account deletion']]},
  'uz-Latn':{category:'Murojaat turi',back:'Barcha murojaatlar',you:'Siz',empty:'Hali murojaatlar yo‘q',hint:'Muammoni tasvirlang yoki shikoyat yuboring. Parollar, kodlar yoki bank ko‘chirmalarini qo‘shmang.',categories:[['other','Boshqa savol'],['bug','Ilovadagi xato'],['complaint','Shikoyat'],['account','Hisob va kirish'],['sync','Sinxronlash'],['billing','Tariflar va kirish'],['privacy','Maxfiylik'],['deletion','Hisobni o‘chirish']]},
  'uz-Cyrl':{category:'Мурожаат тури',back:'Барча мурожаатлар',you:'Сиз',empty:'Ҳали мурожаатлар йўқ',hint:'Муаммони тасвирланг ёки шикоят юборинг. Пароллар, кодлар ёки банк кўчирмаларини қўшманг.',categories:[['other','Бошқа савол'],['bug','Иловадаги хато'],['complaint','Шикоят'],['account','Ҳисоб ва кириш'],['sync','Синхронлаш'],['billing','Тарифлар ва кириш'],['privacy','Махфийлик'],['deletion','Ҳисобни ўчириш']]}
 };return all[state.lang]||all.en;
}
async function support(m){
 if(activeSupportThread?.epoch===privateEpoch)return openThread(activeSupportThread.id,m);
 activeSupportThread=null;
 const result=await call('support');if(!m.isConnected||state.tab!=='account'||state.settingsTab!=='support')return;
 const copy=supportCopy(),c=card(t('account_support'));m.append(c);c.append(E('p',copy.hint,'small'));
 if(!result.tickets?.length)c.append(E('p',copy.empty,'small'));
 for(const ticket of result.tickets||[])c.append(button(ticket.subject,()=>openThread(ticket.id),'secondary support-ticket-link'));
 form(c,'',f=>{
  const category=select(f,'category',copy.category,copy.categories,'other');
  const subject=input(f,'subject',t('account_subject')),message=input(f,'message',t('account_message'),'textarea');subject.maxLength=160;message.maxLength=8000;
  return {category,subject,message};
 },async v=>{await call('support',{category:v.category.value,subject:v.subject.value,message:v.message.value});toast(t('account_done'));render();},t('account_send'));
}
async function openThread(id,content){
 const target=content||root.querySelector('.settings-content[data-section="support"]');
 const result=await call('thread?id='+encodeURIComponent(id));
 if(!target?.isConnected||state.tab!=='account'||state.settingsTab!=='support')return;
 activeSupportThread={id,epoch:privateEpoch};
 const copy=supportCopy(),thread=card(result.ticket.subject);thread.classList.add('support-thread');
 target.replaceChildren(button(copy.back,()=>{activeSupportThread=null;render();},'text-button support-back'),thread);
 for(const message of result.messages){
  const item=E('article',undefined,'support-message');item.dataset.staff=String(Boolean(message.is_staff));
  append(item,E('strong',message.is_staff?t('account_support'):copy.you),E('p',message.body));thread.append(item);
 }
 form(thread,'',f=>{const message=input(f,'message',t('account_message'),'textarea');message.maxLength=8000;return {message};},async v=>{await call('support/reply',{ticket_id:id,message:v.message.value,state:'open'});await openThread(id);},t('account_send'));
}
function backgroundView(){return JSON.stringify([state.space,state.spaces,state.roster,state.syncCursor,state.syncEpoch]);}
function editingView(){const active=document.activeElement;return Boolean(document.querySelector('dialog[open],.settings-inline-panel,.device-revoke-inline')||active?.matches('input,textarea,select,[contenteditable=true]')||state.tab==='account');}
function flushBackground(){if(backgroundDirty&&state.session&&!editingView()){const y=scrollY;render();window.scrollTo({top:y,behavior:'instant'});}}
async function backgroundRefresh(){
 if(!state.session||state.busy||document.querySelector('dialog[open]'))return;
 const before=backgroundView(),epoch=privateEpoch;
 await refresh();
 if(epoch!==privateEpoch||!state.session)return;
 if(before!==backgroundView())backgroundDirty=true;
 flushBackground();
}
window.addEventListener('online',()=>backgroundRefresh().catch(report));
window.addEventListener('offline',()=>{updateSyncStatus();toast(t('web_online'));});
window.addEventListener('pagehide',()=>{clearIdentity();root.replaceChildren();alerts.replaceChildren();});
window.addEventListener('pageshow',e=>{if(e.persisted)start().catch(error=>{if(error.code==='unauthorized'){clearIdentity();login();}else report(error);});});
document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible')backgroundRefresh().catch(report);});
document.addEventListener('focusout',()=>requestAnimationFrame(flushBackground));
setInterval(()=>{if(document.visibilityState==='visible'&&navigator.onLine)backgroundRefresh().catch(report);},30000);
(async()=>{try{packs=await (await fetch('/app/assets/locales.json',{cache:'no-store'})).json();if(!packs[state.lang])state.lang='ru';applyTheme();const config=await call('config');state.googleEnabled=Boolean(config.google_enabled);try{if(new URLSearchParams(location.search).get('google')==='return')await googleReturn();else await start();}catch(error){if(error.code==='unauthorized'){login();if(new URLSearchParams(location.search).get('action')==='signup')await signup();}else{login();report(error);}}if('serviceWorker'in navigator)navigator.serviceWorker.register('/app/sw.js',{scope:'/app'}).catch(()=>{});}catch{root.textContent='ULADIM · '+t('retry');}})();

const SIGNUP_COPY = {
 ru: {intro: 'Введите почту и придумайте пароль.', or: 'или', privacy: 'Конфиденциальность'},
 en: {intro: 'Enter your email and choose a password.', or: 'or', privacy: 'Privacy'},
 'uz-Latn': {intro: 'Email manzilingizni kiriting va parol yarating.', or: 'yoki', privacy: 'Maxfiylik'},
 'uz-Cyrl': {intro: 'Email манзилингизни киритинг ва парол яратинг.', or: 'ёки', privacy: 'Махфийлик'}
};

function authDialogBrand(container) {
 container.querySelector('.dialog-head').prepend(E('span','ULADIM','registration-brand'));
}

async function signup() {
 const config=await call('config');
 const copy=SIGNUP_COPY[state.lang]||SIGNUP_COPY.en;
 const d=dialog(t('family_register'),container=>{
  container.classList.add('registration-dialog');
  authDialogBrand(container);
  container.append(E('p',copy.intro,'registration-intro'));

  form(container,'',f=>{
   const email=input(f,'email',t('family_email'),'email');
   email.placeholder='name@example.com';
   const password=input(f,'new-password',t('family_password'),'password');
   const fields={email,password};
   if(!config.registration_open)fields.invitation=input(f,'invitation',t('family_invitation'));
   return fields;
  },async v=>{
   const email=v.email.value;
   try {
    await call('signup',{email,password:v.password.value,...(v.invitation?{invitation:v.invitation.value}:{})});
   } finally { v.password.value=''; }
   replaceDialog(container,E('h2',t('family_verify')),E('p',t('family_verify_hint'),'registration-intro'));
   authDialogBrand(container);
   form(container,'',f=>({code:input(f,'code',t('family_code'))}),async fields=>{
    await call('confirm-signup',{email,code:fields.code.value.trim()});
    fields.code.value='';
    d.close();
    login();
    toast(t('account_done'));
   },t('family_verify'));
   container.append(button(t('ux3_resend_verification'),async()=>{
    await call('resend-signup',{email});
    toast(t('family_verify_hint'));
   },'registration-secondary'));
  },t('family_register'));

  if(config.google_enabled){
   const divider=E('div',copy.or,'registration-divider');
   divider.setAttribute('aria-hidden','true');
   const google=button(t('account_google_sign_in'),()=>beginGoogle(container.querySelector('[name=invitation]')?.value),'registration-secondary');
   append(container,divider,google);
  }
  const privacy=E('a',copy.privacy);
  privacy.href='/privacy';
  container.append(append(E('p',undefined,'registration-legal'),privacy));
 });
}

const RECOVERY_COPY = {
 ru: ['Восстановление пароля','Введите почту, которую используете в ULADIM.','Если аккаунт существует, код придёт на эту почту.','Отправить код','Сохранить пароль','Вернуться ко входу'],
 en: ['Reset your password','Enter the email you use for ULADIM.','If an account exists, a code will be sent to this email.','Send code','Save password','Back to sign in'],
 'uz-Latn': ['Parolni tiklash','ULADIM uchun ishlatadigan email manzilingizni kiriting.','Hisob mavjud bo‘lsa, shu manzilga kod yuboriladi.','Kodni yuborish','Parolni saqlash','Kirishga qaytish'],
 'uz-Cyrl': ['Паролни тиклаш','ULADIM учун ишлатадиган email манзилингизни киритинг.','Ҳисоб мавжуд бўлса, шу манзилга код юборилади.','Кодни юбориш','Паролни сақлаш','Киришга қайтиш']
};

function recover(){
 const [title,intro,sent,send,save,back]=RECOVERY_COPY[state.lang]||RECOVERY_COPY.en;
 const d=dialog(title,container=>{
  container.classList.add('registration-dialog','recovery-dialog');
  authDialogBrand(container);
  container.append(E('p',intro,'registration-intro'));
  const backToLogin=()=>container.append(button(back,()=>container.close(),'recovery-back'));
  form(container,'',f=>({email:input(f,'email',t('family_email'),'email')}),async v=>{
   const email=v.email.value;
   await call('recovery',{email});
   replaceDialog(container,E('h2',title),E('p',sent,'registration-intro'));
   authDialogBrand(container);
   form(container,'',f=>({
    code:input(f,'code',t('family_code')),
    password:input(f,'new-password',t('family_new_password'),'password')
   }),async fields=>{
    await call('reset',{email,code:fields.code.value,password:fields.password.value});
    d.close();
    login();
    toast(t('account_done'));
   },save);
   backToLogin();
  },send);
  backToLogin();
 });
}

function settingsRow(label, run, variant=''){
 const row=button(label,run,'settings-row '+variant);
 row.append(icon('forward'));
 return row;
}
function privacy(m){
 m.classList.add('security-panel');
 const group=label=>{
  const section=E('section',undefined,'settings-group');
  section.append(E('h2',t(label)));
  m.append(section);
  return section;
 };
 const methods=group('account_google_methods');
 const google=settingsRow('Google',()=>googleMethods(google));
 const googleStatus=E('span',t('web_google_status_loading'),'settings-row-status');
 google.setAttribute('aria-label','Google');
 googleStatus.id='google-status';
 google.setAttribute('aria-describedby',googleStatus.id);
 const googleLabel=E('span',undefined,'settings-row-copy');
 append(googleLabel,E('span','Google'),googleStatus);
 google.firstChild.replaceWith(googleLabel);
 const password=settingsRow(t('family_password_change'),()=>changePassword(password));
 const email=settingsRow(t('account_email_change'),()=>changeEmail(email));
 append(methods,google,password,email);
 const protection=group('web_security_devices');
 const mfa=settingsRow(t('account_mfa'),()=>customerMfa(mfa));
 append(protection,mfa,settingsRow(t('account_devices'),()=>openSettings('devices')));
 const data=group('web_account_data');
 data.append(settingsRow(t('account_delete'),deletion,'danger-text'));
 call('google').then(status=>{
  if(googleStatus.isConnected)googleStatus.textContent=t(status.google_linked?'account_google_linked':'account_google_unlinked');
 }).catch(()=>{
  if(googleStatus.isConnected)googleStatus.textContent=t('web_google_status_error');
 });
}
function changePassword(trigger){
 const label=t('family_password_change');
 settingsInline(label,d=>{
  d.append(E('p',t('web_password_change_hint'),'small'));
  form(d,'',f=>({old:input(f,'old',t('family_old_password'),'password'),next:input(f,'new',t('family_new_password'),'password')}),async v=>{
   try{await call('password',{old_password:v.old.value,new_password:v.next.value});}finally{v.old.value='';v.next.value='';}
   clearIdentity();
   login();
  },label);
 },trigger);
}
function changeEmail(trigger){
 const label=t('account_email_change');
 settingsInline(label,d=>form(d,'',f=>({email:input(f,'email',t('family_email'),'email'),password:input(f,'password',t('family_old_password'),'password')}),async v=>{
  const email=v.email.value;
  await call('email',{email,password:v.password.value});
  replaceDialog(d,E('h2',t('family_verify')),E('p',email,'account-email'));
  form(d,'',f=>({code:input(f,'code',t('family_code')),password:input(f,'password',t('family_old_password'),'password')}),async v=>{
   await call('confirm-email',{code:v.code.value,password:v.password.value});clearIdentity();login();
  },t('family_verify'));
  d.querySelector('input').focus();
 },label),trigger);
}
async function incomingOwnership(content){
 const {incoming_transfers:transfers}=await call('deletion');
 if(!content.isConnected||!transfers?.length)return;
 const section=E('section',undefined,'settings-group');
 section.append(E('h2',t('web_family_transfer')));
 for(const transfer of transfers){
  const label=t('account_accept_transfer')+' · '+transfer.name;
  section.append(settingsRow(label,()=>dialog(label,d=>{
   form(d,'',f=>({password:input(f,'password',t('family_old_password'),'password')}),async v=>{
    try{await call('accept-transfer',{transfer_id:transfer.id,password:v.password.value});}finally{v.password.value='';}
    d.close();await refresh();render();
   },t('account_accept_transfer'));
  })));
 }
 content.prepend(section);
}
async function deletion(){
 const status=await call('deletion');
 dialog(t('account_delete'),d=>{
  d.append(E('p',t('account_delete_notice')));
  if(status.ownership_transfer_required.length){
   for(const family of status.ownership_transfer_required){
    if(family.pending_until){
     d.append(E('p',family.name+' · '+t('web_transfer_pending')+' '+new Date(family.pending_until*1000).toLocaleString(state.lang),'small'));
     continue;
    }
    if(family.eligible_parent_id)form(d,t('account_transfer')+' · '+family.name,f=>({password:input(f,'password',t('family_old_password'),'password')}),async v=>{
     try{await call('transfer',{workspace_id:family.id,user_id:family.eligible_parent_id,password:v.password.value});}finally{v.password.value='';}
     d.close();await deletion();
    },t('account_transfer'));
   }
  }else if(status.request?.state==='pending'){
   form(d,'',f=>({password:input(f,'password',t('family_old_password'),'password')}),async v=>{
    await call('cancel-deletion',{password:v.password.value});d.close();await deletion();
   },t('account_cancel_delete'));
  }else{
   const request=form(d,'',f=>({password:input(f,'password',t('family_old_password'),'password'),confirmation:input(f,'confirmation',t('web_confirm_delete'))}),async v=>{
    await call('deletion',{password:v.password.value,confirmation:v.confirmation.value});d.close();await deletion();
   },t('account_delete'));
   request.querySelector('button[type=submit]').classList.add('danger-action');
  }
 });
}
async function googleMethods(trigger){
 const status=await call('google'),mfa=await call('mfa');
 if(!trigger?.isConnected)return;
 settingsInline(t('account_google_methods'),d=>{
  d.append(E('p',t(status.google_linked?'account_google_linked':'account_google_unlinked')));
  if(!status.has_password){d.append(E('p',t('account_google_password_first')),button(t('family_recovery'),recover));return;}
  if(!status.google_linked&&!status.google_web_enabled){d.append(E('p',t('family_error_google_unavailable'),'small'));return;}
  if(status.google_linked)d.append(E('p',sessionCopy('googleHint'),'small'));
  form(d,'',f=>({password:input(f,'password',t('family_old_password'),'password'),...(mfa.enabled?{code:input(f,'code',t('family_code'))}:{})}),async v=>{
   let value;try{value=await call(status.google_linked?'google/unlink':'google/link',{password:v.password.value,code:v.code?.value});}finally{v.password.value='';if(v.code)v.code.value='';}
   if(value.authorization_url){location.assign(value.authorization_url);return;}
   d.close();clearIdentity();login();
  },status.google_linked?sessionCopy('googleDisconnect'):t('account_google_connect'));
 },trigger);
}
async function devices(host){
 if(!host){openSettings('devices');return;}
 const epoch=privateEpoch;
 const loading=E('p',t('web_loading'),'small');host.append(loading);
 const {devices:items}=await call('devices');
 if(!host.isConnected||epoch!==privateEpoch)return;
 loading.remove();
 const d=host;
 d.classList.add('devices-panel');
 d.append(E('h2',t('account_devices')));
  d.classList.add('devices-dialog');
  const active=items.filter(device=>!device.revoked_at);
  const revoked=items.filter(device=>device.revoked_at);
  const deviceDate=value=>new Intl.DateTimeFormat(state.lang,{dateStyle:'medium',timeStyle:'short'}).format(value*1000);
  function group(label,entries){
   const section=E('section',undefined,'device-group');
   section.append(E('h3',t(label)));
   for(const device of entries){
    const row=E('div',undefined,'device-row'),description=E('div',undefined,'device-description');
    append(description,E('strong',device.label));
    if(device.current)description.append(E('span',t('web_current_session'),'device-status'));
    description.append(E('p',t(device.revoked_at?'web_revoked_on':'web_last_active')+' · '+deviceDate(device.revoked_at||device.last_seen_at),'small'));
    row.append(description);
    if(!device.revoked_at){const revoke=button(t('account_revoke'),()=>confirmDeviceRevoke(device,d,revoke),'text-button danger-text');row.append(revoke);}
    section.append(row);
   }
   if(!entries.length)section.append(E('p',t('web_no_sessions'),'small'));
   d.append(section);
  }
  group('web_active_sessions',active);
  if(revoked.length)group('web_revoked_sessions',revoked);
}
function confirmDeviceRevoke(device,list,trigger){
 const row=trigger?.closest('.device-row');if(!row)return;
 row.querySelector('.device-revoke-inline')?.remove();
 const d=E('div',undefined,'device-revoke-inline');row.append(d);
 trigger.hidden=true;
 const close=()=>{d.remove();trigger.hidden=false;trigger.focus({preventScroll:true});};
  append(d,E('p',t(device.current?'web_revoke_current_hint':'web_revoke_device_hint')));
  const confirmation=form(d,'',f=>({password:input(f,'password',t('family_old_password'),'password')}),async v=>{
   try{await call('devices/revoke',{device_id:device.id,password:v.password.value});}finally{v.password.value='';}
   d.remove();
   if(device.current){clearIdentity();login();return;}
   toast(t('account_done'));
   if(list.isConnected)await openSettings('devices');
  },t('account_revoke'));
  confirmation.querySelector('button[type=submit]').classList.add('danger-action');
  d.append(button(sessionCopy('cancel'),close,'text-button'));
  d.querySelector('input').focus({preventScroll:true});
}
async function customerMfa(trigger){
 const status=await call('mfa');
 if(!trigger?.isConnected)return;
 settingsInline(t('account_mfa'),d=>{
  if(status.enabled){
   const disable=form(d,'',f=>({password:input(f,'password',t('family_old_password'),'password'),code:input(f,'code',t('family_code'))}),async v=>{
    await call('mfa/disable',{password:v.password.value,code:v.code.value});
    d.close();clearIdentity();login();toast(t('account_done'));
   },t('account_mfa_disable'));
   disable.querySelector('button[type=submit]').classList.add('danger-action');
   return;
  }
  form(d,'',f=>({password:input(f,'password',t('family_old_password'),'password')}),async v=>{
   const r=await call('mfa/begin',{password:v.password.value});
   replaceDialog(d,E('h2',t('account_mfa')),E('p',t('account_mfa_setup')),E('pre',r.totp_secret));
   form(d,'',f=>({password:input(f,'password',t('family_old_password'),'password'),code:input(f,'code',t('family_code'))}),async fields=>{
    const value=await call('mfa/enable',{password:fields.password.value,enrollment:r.enrollment,code:fields.code.value});
    replaceDialog(d,E('h2',t('account_mfa_recovery')),E('pre',value.recovery_codes.join('\n')),button(t('close'),()=>{d.close();clearIdentity();login();}));
   },t('web_mfa_enable'));
  },t('web_mfa_enable'));
 },trigger);
}

function familyPermissions(m){
 const roster=state.roster;if(!roster||roster.space.kind!=='family'||!['parent','owner'].includes(roster.space.role))return;
 const c=card(t('family_role'));m.append(c);
 for(const profile of roster.profiles)c.append(button(profile.name+' · '+t('edit'),()=>childProfile(profile)));
 for(const member of roster.members.filter(x=>['adult','child'].includes(x.role))){const row=E('div',undefined,'row');append(row,E('span',member.user_id,'text'),button(t('account_revoke'),()=>dialog(t('family_remove'),d=>d.append(button(t('account_revoke'),async()=>{await call('family',{id:crypto.randomUUID(),action:'member.remove',workspace_id:roster.space.id,user_id:member.user_id,revision:member.revision});d.close();await refresh();render();})))));c.append(row);}
 for(const invite of roster.invitations||[])c.append(button(invite.email+' · '+t('account_revoke'),()=>dialog(t('family_invite_revoke'),d=>d.append(button(t('account_revoke'),async()=>{await call('family',{id:crypto.randomUUID(),action:'invite.revoke',workspace_id:roster.space.id,invitation_id:invite.id});d.close();await refresh();render();})))));
}
function childProfile(profile){const d=dialog(t('family_child'),container=>form(container,'',f=>{const fields={name:input(f,'name',t('name'),'text',profile.name)};for(const key of ['view_budget','record_spending','edit_own','request_money','view_shared','create_tasks','complete_tasks']){fields[key]=input(f,key,t('family_permission_'+key),'checkbox','',false);fields[key].checked=profile.permissions.includes(key);}return fields;},async v=>{const permissions=Object.keys(v).filter(k=>k!=='name'&&v[k].checked);await call('family',{id:crypto.randomUUID(),workspace_id:state.space,action:'child.save',profile_id:profile.id,revision:profile.revision,name:v.name.value,permissions});d.close();await refresh();render();}));}

if(window.visualViewport){const fit=()=>{document.body.style.setProperty('--visible-height',visualViewport.height+'px');document.querySelector('dialog input:focus,dialog textarea:focus')?.scrollIntoView({block:'nearest'});};visualViewport.addEventListener('resize',fit);fit();}

// Repaint canvas pixels when system colors change; keep open dialog drafts intact.
window.matchMedia?.('(prefers-color-scheme: dark)')?.addEventListener('change',()=>redrawFinance?.());

async function personalImportCenter(host){
 const parser=await import('/app/assets/personal-import.js');
 if(!host.isConnected)return;
 const copy=key=>parser.importCopy(key,state.lang);
 const files=card(copy('oneTime'),copy('local'));
 files.classList.add('personal-import-center');
 const list=E('ul',undefined,'personal-import-sources');
 const choices=[['calendar','calendars','calendarFiles','importCalendars'],['notes','notes','noteFiles','importNotes'],['tasks','tasks','taskFiles','importTasks']];
 for(const [symbol,label,formats,action] of choices){
  const row=E('li');
  const labelBlock=append(E('div',undefined,'personal-import-source'),icon(symbol),
   append(E('div'),E('strong',copy(label)),E('p',copy(formats),'small')));
  append(row,labelBlock,
    button(copy(action),()=>openPersonalImport(parser,copy(action)),'secondary'));
  list.append(row);
 }
 files.append(list,E('p',copy('structuredStatus'),'small'));
 const backup=card(copy('backups'),copy('backupStatus'));
 const sync=card(copy('sync'),copy('googleStatus'));
 backup.classList.add('personal-import-status-card');sync.classList.add('personal-import-status-card');
 const guide=anchor(state.lang==='ru'?'Руководство по импорту':'Import guide','/docs#import');guide.classList.add('personal-import-guide-link');
 append(host,files,backup,sync,guide);
}

function openPersonalImport(parser,titleText){
 const workspace=state.space,user=state.session.user_id,epoch=privateEpoch;
 const copy=key=>parser.importCopy(key,state.lang);
 if(!workspace||currentSpace()?.role==='child'){toast(copy(workspace?'child':'noSpace'));return;}
 let busy=false,saving=false,pending=null,saved=0,failed=0,rows=[];
 const sameContext=()=>privateEpoch===epoch&&state.space===workspace&&state.session?.user_id===user;
 const d=dialog(titleText,host=>{
  host.classList.add('personal-import-dialog');
  host.append(E('p',copy('local'),'small'));
  const file=E('input');
  file.type='file';
  file.multiple=true;
  host.append(append(E('label',undefined,'personal-import-picker'),E('span',copy('pick')),file));
  const status=E('p',undefined,'personal-import-status');
  status.setAttribute('role','status');
  const review=E('div');
  const list=E('ul',undefined,'personal-import-preview');
  const save=E('button',copy('save'));
  save.type='button';
  save.hidden=true;
  append(host,status,review,list,append(E('div',undefined,'actions'),save));
  const selected=()=>rows.filter(row=>row.status==='ready'&&row.selected);
  const active=()=>sameContext()&&host.isConnected&&host.open;
  const close=host.querySelector('.dialog-close');
  const update=()=>{
   file.disabled=busy||Boolean(pending);
   save.disabled=busy||!(pending||selected().length);
   if(close)close.disabled=saving;
  };
  host.addEventListener('cancel',event=>{if(saving)event.preventDefault();});

  function showRows(){
   list.replaceChildren();
   const found=[['event','calendars'],['note','notes'],['task','tasks']]
    .map(([kind,label])=>copy(label)+': '+rows.filter(row=>row.kind===kind).length);
   const existing=rows.filter(row=>row.status==='duplicate'||row.status==='conflict').length;
   const skipped=rows.filter(row=>row.issue).length;
   review.replaceChildren(E('h3',copy('review')),E('p',found.join(' · '),'small'),
     E('p',copy('duplicate')+': '+existing+' · '+copy('skipped')+': '+skipped,'small'));
   for(const row of rows){
    const item=E('li');
    if(row.issue){item.append(E('p',copy(row.issue),'small'));list.append(item);continue;}
    const label=row.kind==='note'?row.data.body.split('\n')[0].slice(0,110):row.data.title;
    if(row.status==='ready'){
     const choice=E('input');choice.type='checkbox';choice.checked=row.selected;
     choice.addEventListener('change',()=>{row.selected=choice.checked;update();});
     item.append(append(E('label'),choice,E('span',label)));
    }else item.append(E('strong',label));
    if(row.kind==='event'){
     const schedule=row.data.schedule;
     item.append(E('p',schedule.localStart.slice(0,schedule.allDay?10:16).replace('T',' ')+
       ' · '+(schedule.allDay?t('web_all_day'):schedule.timezone),'small'));
    }
    if(row.status!=='ready')item.append(E('p',copy(row.status),'small'));
    for(const issue of row.issues)item.append(E('p',copy(issue),'small'));
    list.append(item);
   }
   save.hidden=!rows.some(row=>row.status==='ready');
  }

  file.addEventListener('change',async()=>{
   if(!active()||busy||pending)return;
   const files=[...file.files];
   busy=true;rows=[];saved=0;failed=0;save.textContent=copy('save');
   review.replaceChildren();list.replaceChildren();status.textContent=copy('checking');update();
   try{
    const parsed=await parser.previewPersonalFiles(files);
    await refresh();
    if(!active())return;
    rows=await parser.identifyPersonalRows(parsed,[user,workspace],state.records,statementID);
    if(!active())return;
    for(const row of rows)row.selected=row.status==='ready';
    status.textContent='';showRows();
   }catch(error){
    if(active())status.textContent=errorText(error);
   }finally{
    file.value='';busy=false;update();
   }
  });

  save.addEventListener('click',async()=>{
   if(!active()||busy||!(pending||selected().length))return;
   pending??=selected().map(row=>({id:crypto.randomUUID(),action:'record.put',record_id:row.id,
     revision:0,kind:row.kind,visibility:'private',audience:[],data:row.data}));
   busy=true;saving=true;list.inert=true;update();
   try{
    while(pending.length&&active()){
     const batch=pending.slice(0,25);
     const reply=await call('sync',{workspace_id:workspace,operations:batch});
     if(!active())return;
     if(!Array.isArray(reply.results)||reply.results.length!==batch.length||
        reply.results.some((result,index)=>result.id!==batch[index].id))throw {code:'server_error',uncertain:true};
     const accepted=reply.results.filter(result=>result.status==='accepted').length;
     saved+=accepted;failed+=batch.length-accepted;
     pending.splice(0,batch.length);
    }
    if(!active())return;
    await refresh();
    if(!active())return;
    pending=null;rows=[];save.hidden=true;review.replaceChildren();list.replaceChildren();
    status.textContent=copy('saved')+': '+saved+(failed?' · '+copy('failed')+': '+failed:'');
    render();
   }catch(error){
    if(active()){
     if(['unauthorized','workspace_forbidden','service_restricted'].includes(error.code)){host.close();report(error);return;}
     const refreshOnly=pending?.length===0;
     status.textContent=refreshOnly&&saved&&!failed?t('web_saved_refresh'):error.uncertain?copy('retryHelp'):errorText(error);
     save.textContent=refreshOnly?t('retry'):copy('retry');
    }
   }finally{
    busy=false;saving=false;list.inert=Boolean(pending);update();
   }
  });
  update();
 });
 return d;
}
