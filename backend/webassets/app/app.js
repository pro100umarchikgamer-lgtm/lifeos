'use strict';
const root=document.querySelector('#root'),alerts=document.querySelector('#alerts');
const state={session:null,csrf:'',spaces:[],space:null,roster:null,records:[],financeFilters:{},taskQuery:'',taskStatus:'all',calendarDay:localDate(),syncSpace:null,syncCursor:0,syncEpoch:'',tab:'today',settingsTab:'',lang:'ru',theme:'system',palette:'forest',chart:'bar',generation:0,busy:false,googleEnabled:false};
let calendarMode='month';
let packs={},alertTimer,navObserver,privateEpoch=0,redrawFinance=null;
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
function eventRow(o){const row=E('div',undefined,'row event-row'),caption=E('div',undefined,'text');append(caption,E('h3',o.record.data.title),E('p',new Intl.DateTimeFormat(state.lang,{day:'numeric',month:'long'}).format(new Date(o.day+'T12:00:00'))+' · '+(o.allDay?t('web_all_day'):o.time),'small'));append(row,caption,iconButton('more',t('edit')+' · '+o.record.data.title,()=>editRecord('event',o.record)));return row;}
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
 title(m,'web_calendar',addEvent);
 m.classList.add('calendar-page');
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
 m.append(modes);
 const layout=E('div',undefined,'calendar-layout'),monthPanel=card(),agenda=card();
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
 append(toolbar,previous,E('h2',period),next);
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
 if(calendarMode==='month')for(let i=0;i<(from.getDay()+6)%7;i++)grid.append(E('span',undefined,'calendar-offset'));
 const today=localDate();
 if(calendarMode!=='day')for(let d=from;d<to;d=offsetDate(d,1)){
  const key=dateString(d),items=byDay.get(key)||[];
  const b=button(String(d.getDate()),()=>showDate(key,'.calendar-date[aria-pressed=true]'),'calendar-date');
  b.setAttribute('aria-label',d.toLocaleDateString(state.lang,{day:'numeric',month:'long'})+(items.length?' · '+items.map(o=>o.record.data.title).join(', '):''));
  b.setAttribute('aria-pressed',String(key===state.calendarDay));
  if(key===today){b.classList.add('is-today');b.setAttribute('aria-current','date');}
  if(items.length){const count=E('span',String(items.length),'event-count');count.setAttribute('aria-hidden','true');b.append(count);}
  grid.append(b);
 }
 const dateHeading=E('h2',date.toLocaleDateString(state.lang,{weekday:'long',day:'numeric',month:'long'}),'calendar-agenda-date');
 const agendaHead=E('div',undefined,'calendar-agenda-head');
 append(agendaHead,dateHeading,addButton(t('family_kind_event'),addEvent));
 agenda.append(agendaHead);
 const selected=byDay.get(state.calendarDay)||[];
 for(const o of selected)agenda.append(eventRow(o));
 if(!selected.length)agenda.append(E('p',t('web_no_events'),'empty'));
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
function icon(name){const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');for(const [key,value]of Object.entries({viewBox:'0 0 24 24',fill:'none',stroke:'currentColor','stroke-width':'1.7','stroke-linecap':'round','stroke-linejoin':'round','aria-hidden':'true',focusable:'false',class:'ui-icon'}))svg.setAttribute(key,value);for(const path of ICON_PATHS[name]||[]){const node=document.createElementNS(svg.namespaceURI,'path');node.setAttribute('d',path);svg.append(node);}return svg;}
function iconButton(name,label,run){const b=button('',run,'icon');b.setAttribute('aria-label',label);b.title=label;b.append(icon(name));return b;}
function addButton(label,run){const b=button(label,run,'');b.prepend(icon('add'));return b;}
function anchor(text,path){const a=E('a',text,'button');a.href=path;return a;}
function input(container,name,label,type='text',value='',required=true){const id='input-'+name+'-'+crypto.randomUUID();const l=E('label',label);l.htmlFor=id;const n=E(type==='textarea'?'textarea':'input');n.name=name;n.id=id;if(type!=='textarea')n.type=type;if(type==='email')n.autocomplete='email';if(type==='password')n.autocomplete=['new','next','new-password'].includes(name)?'new-password':'current-password';if(type==='textarea')n.maxLength=20000;if(['name','label'].includes(name))n.maxLength=2000;if(name==='currency'){n.maxLength=3;n.autocapitalize='characters';}if(['amount','received'].includes(name))n.inputMode='decimal';if(name==='code'){n.autocomplete='one-time-code';n.spellcheck=false;}n.value=value??'';n.required=required&&type!=='checkbox';append(container,l,n);return n;}
function select(container,name,label,choices,value){const id='select-'+name+'-'+crypto.randomUUID();const l=E('label',label);l.htmlFor=id;const s=E('select');s.name=name;s.id=id;for(const [v,label]of choices){const o=E('option',label);o.value=v;s.append(o);}s.value=value;append(container,l,s);return s;}
function card(title,body){const c=E('section',undefined,'card');if(title)c.append(E('h2',title));if(body)c.append(E('p',body));return c;}
function form(container,title,build,submit,submitLabel=t('save')){
 const f=E('form');if(title)f.append(E('h2',title));
 const fields=E('fieldset'),values=build(fields)||{},initiallyDisabled=fields.disabled;
 const status=E('p',undefined,'error');status.setAttribute('role','status');
 const b=E('button',submitLabel);b.type='submit';append(f,fields,status,b);
 let pending=false;
 f.addEventListener('submit',async event=>{
  event.preventDefault();if(pending)return;
  pending=true;b.disabled=true;status.textContent='';
  try{await submit(values);status.textContent=t('account_done');}
  catch(error){
   const retry=error.uncertain||error.refreshOnly;
   fields.disabled=initiallyDisabled||!!retry;
   b.textContent=retry?t('retry'):submitLabel;
   status.textContent=error.displayMessage||(error.refreshOnly?t('web_saved_refresh'):error.uncertain?t('web_uncertain'):errorText(error));
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

function clearIdentity(){redrawFinance=null;refreshTail=Promise.resolve();privateEpoch++;state.generation++;for(const job of pendingDeletes.values())clearTimeout(job.timer);pendingDeletes.clear();quickTasks.clear();taskChanges.clear();alerts.replaceChildren();Object.assign(state,{session:null,csrf:'',space:null,spaces:[],roster:null,records:[],financeFilters:{},taskQuery:'',taskStatus:'all',settingsTab:'',syncSpace:null,syncCursor:0,syncEpoch:'',tab:'today',busy:false});document.querySelectorAll('dialog').forEach(d=>{d.close();d.remove();});}
function money(value,currency){return ULADIMMoney.format(value,currency,state.lang);}
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
function refresh(){const epoch=privateEpoch;const run=async()=>{if(epoch!==privateEpoch)return;state.busy=true;try{const result=await call('spaces');state.spaces=result.spaces;if(!state.spaces.some(s=>s.id===state.space))state.space=state.spaces[0]?.id||null;await readSpace();}finally{if(epoch===privateEpoch)state.busy=false;}};const pending=refreshTail.then(run,run);refreshTail=pending.catch(()=>{});return pending;}
async function start(){state.session=await call('session');state.csrf=state.session.csrf;await refresh();render();}
function login(){
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
document.addEventListener('pointerdown',event=>{
 const menu=root.querySelector('.nav-more[open]');
 if(menu&&!menu.contains(event.target))menu.open=false;
});
function shell(){
 const previousMenu=root.querySelector('.nav-more');
 const keepMenu=previousMenu?.open&&previousMenu.dataset.tab===state.tab;
 navObserver?.disconnect();root.replaceChildren();const header=E('header');const brand=E('a','ULADIM','brand');brand.href='/app';brand.append(E('small',t('ux3_settings_body')));header.append(brand);
 const spaces=select(E('div'),'workspace','',state.spaces.map(s=>[s.id,s.name]),state.space);spaces.setAttribute('aria-label',t('family_account'));spaces.className='workspace';spaces.title=currentSpace()?.name||t('family_account');spaces.addEventListener('change',async()=>{document.querySelectorAll('dialog').forEach(d=>d.close());state.space=spaces.value;state.records=[];state.syncSpace=null;state.syncCursor=0;state.syncEpoch='';state.roster=null;render();try{await readSpace();render();}catch(e){report(e);}});if(state.spaces.length)header.append(spaces);root.append(header);
 if(!navigator.onLine){const n=E('div',t('web_online'));n.id='network';root.append(n);}
 const m=E('main');m.id='content';root.append(m);const nav=E('nav',undefined,'nav');nav.setAttribute('aria-label','ULADIM');
 const secondary=E('details',undefined,'nav-more');
 secondary.dataset.tab=state.tab;secondary.open=Boolean(keepMenu);
 const summary=E('summary');append(summary,icon('more'),E('span',t('web_more')));secondary.append(summary);
 const menu=E('div',undefined,'nav-menu');secondary.append(menu);
 secondary.addEventListener('keydown',event=>{if(event.key==='Escape'&&secondary.open){event.preventDefault();secondary.open=false;summary.focus();}});
 for(const [key,label] of [['today','today'],['tasks','widget_tasks'],['calendar','web_calendar'],['notes','widget_notes'],['money','finances'],['account','profile']]){
  const navigate=()=>{
   secondary.open=false;
   if(key==='account')state.settingsTab='';
   state.tab=key;render();
   window.scrollTo(0,0);
   const heading=root.querySelector('main h1');
   if(heading){heading.tabIndex=-1;heading.focus({preventScroll:true});}
  };
  const navItem=()=>{
   const b=button('',navigate);
   append(b,icon(key),E('span',t(label)));
   if(state.tab===key)b.setAttribute('aria-current','page');
   return b;
  };
  const item=navItem();
  if(['notes','account'].includes(key)){
   item.classList.add('nav-secondary');
   menu.append(navItem());
  }
  nav.append(item);
 }
 if(['notes','account'].includes(state.tab)){summary.classList.add('active');summary.setAttribute('aria-current','page');}
 nav.append(secondary);root.append(nav);
 let measureFrame=0;
 const measureChrome=()=>{
  measureFrame=0;
  if(!nav.isConnected||!header.isConnected)return;
  const heights=[['--nav-height',nav.getBoundingClientRect().height],['--app-header-height',header.getBoundingClientRect().height]];
  for(const [name,height] of heights){
   const value=height+'px';
   if(document.body.style.getPropertyValue(name)!==value)document.body.style.setProperty(name,value);
  }
 };
 measureChrome();
 // Changing a CSS variable can resize the observed chrome. Do the write outside observer delivery.
 navObserver=new ResizeObserver(()=>{if(!measureFrame)measureFrame=requestAnimationFrame(measureChrome);});
 navObserver.observe(nav);navObserver.observe(header);return m;
}
function title(m,label,add){const intro=E('div',undefined,'intro');const a=E('div');if(label==='today')a.append(E('div',new Date().toLocaleDateString(state.lang,{day:'numeric',month:'long',weekday:'long'}),'eyebrow'));a.append(E('h1',t(label)));intro.append(a);if(add)intro.append(addButton(t('add'),add));m.append(intro);}
function render(){redrawFinance=null;if(!state.session){login();return;}const m=shell();if(state.tab==='account'){account(m);return;}if(!state.space){onboarding(m);return;}
 if(state.tab==='today')today(m);else if(state.tab==='tasks')listTasks(m);else if(state.tab==='calendar')calendar(m);else if(state.tab==='notes')listNotes(m);else if(state.tab==='money')finance(m);
}
function openTabSection(tab,selector){
 state.tab=tab;
 render();
 const section=root.querySelector(selector);
 if(!section)return;
 section.tabIndex=-1;
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
function today(m){
 title(m,'today');m.classList.add('today-page');
 const tasks=records('task'),open=tasks.filter(r=>!r.data.completed),done=tasks.length-open.length;
 const day=localDate(),end=new Date(day+'T12:00:00');end.setDate(end.getDate()+8);
 const occurrences=ULADIMDomain.occurrences(records('event'),day,dateString(end));
 const dayEvents=occurrences.filter(o=>o.day===day),upcoming=occurrences.filter(o=>o.day!==day);
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
 for(const r of open.slice(0,6))a.append(taskRow(r));if(!open.length)a.append(emptyPanel('tasks',t('empty_tasks')));
 const taskActions=E('div',undefined,'task-actions');
 taskActions.append(button(t('web_all_tasks'),()=>openTabSection('tasks','main h1'),'text-button'));
 if(!pendingCreate&&!draft.operation)taskActions.append(button(t('web_open_task_form'),()=>editRecord('task'),'text-button'));
 a.append(taskActions);append(grid,a,side);

 const finance=card(t('finances'));
 finance.classList.add('today-finance');
 const financeHead=E('div',undefined,'today-finance-head');
 const history=button(t('web_history'),()=>openTabSection('money','#finance-ledger'),'text-button');
 append(financeHead,finance.firstElementChild,history);
 finance.append(financeHead);
 summaries(finance);
 finance.append(button(t('web_add_operation'),()=>editRecord('transaction'),'text-button today-add-operation'));
 side.append(finance);

 if(dayEvents.length){
  const schedule=card(t('web_today_schedule'));
  schedule.classList.add('today-schedule');
  const timeline=E('ol',undefined,'today-timeline');
  for(const o of dayEvents){
   const item=E('li');
   const time=o.allDay?E('span',t('web_all_day')):E('time',o.time);
   if(!o.allDay)time.dateTime=new Date(o.at).toISOString();
   append(item,time,button(o.record.data.title,()=>editRecord('event',o.record),'text-button'));
   timeline.append(item);
  }
  schedule.append(timeline);side.append(schedule);
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

 const notes=card(t('recent_notes'));
 notes.classList.add('today-notes');
 const recent=records('note').sort((a,b)=>b.seq-a.seq).slice(0,2);
 for(const r of recent)notes.append(button(r.data.body.split('\n')[0].slice(0,110)||t('family_kind_note'),()=>editRecord('note',r),'note-link'));
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
   const group=E('section',undefined,'task-group');
   const heading=E('h2',t(name));heading.id='tasks-'+name;
   group.setAttribute('aria-labelledby',heading.id);
   group.append(append(E('div',undefined,'task-group-head'),heading,E('span',String(groupRows.length),'task-group-count')));
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
 title(m,'widget_notes',()=>editRecord('note'));
 m.classList.add('notes-page');
 const toolbar=E('div',undefined,'notes-toolbar');
 const search=input(toolbar,'search',t('search'),'search','',false);
 const library=E('div',undefined,'notes-library');
 const [resumeDraft]=NOTE_DRAFT_COPY[state.lang]||NOTE_DRAFT_COPY.en;
 if(readNoteDraft(noteDraftKey(null)))toolbar.append(button(resumeDraft,()=>editRecord('note'),'secondary'));
 append(m,toolbar,library);
 const draw=()=>{
  library.replaceChildren();
  const needle=search.value.trim().toLocaleLowerCase(state.lang),available=records('note');
  const rows=available.filter(r=>r.data.body.toLocaleLowerCase(state.lang).includes(needle)).sort((a,b)=>b.seq-a.seq);
  for(const r of rows){
   const c=E('article',undefined,'card note-card');
   const firstLine=r.data.body.split('\n')[0];
   const preview=(firstLine.length>100?r.data.body.slice(100):r.data.body.slice(firstLine.length)).trimStart();
   c.append(E('h2',firstLine.slice(0,100)||t('family_kind_note')));
   if(preview)c.append(E('p',preview.slice(0,280),'note note-preview'));
   c.append(button(readNoteDraft(noteDraftKey(r))?resumeDraft:t('edit'),()=>editRecord('note',r),'text-button'));
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
function editRecord(kind,r=null,{eventDay=localDate(),onSaved}={}){
 const workspace=state.space,epoch=privateEpoch,taskKey=kind==='task'&&!r?taskActionKey('create'):'';
 const pendingTask=readTaskAction(taskKey);
 const d=dialog(t('family_kind_'+kind),container=>{
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
  if(['task','event','account','budget'].includes(kind))fields.name=input(f,'name',t(kind==='task'?'task_title':'name'),'text',pendingTask?.operation.data.title||data.title||data.name||'');
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
  fields.visibility=select(kind==='event'?f.querySelector('.event-options'):f,'visibility',t('family_visibility'),[['private',t('family_private')],['shared',t('family_shared')]],r?.visibility||(currentSpace()?.role==='child'?'shared':'private'));
  if(pendingTask)fields.visibility.value=pendingTask.operation.visibility;
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
   if(kind==='account')data={name:v.name.value,currency:v.currency.value.trim().toUpperCase(),opening_minor:minor(v.amount.value,true,v.currency.value)};
   if(kind==='transaction')data={kind:v.direction.value,amount_minor:minor(v.amount.value,false,v.currency?.value||records('account').find(a=>a.id===v.from?.value)?.data.currency||'RUB'),currency:v.currency.value.trim().toUpperCase(),date:v.date.value,label:v.label.value,account_id:v.account.value||null};
   if(kind==='budget')data={name:v.name.value,currency:v.currency.value.trim().toUpperCase(),limit_minor:minor(v.amount.value,false,v.currency?.value||records('account').find(a=>a.id===v.from?.value)?.data.currency||'RUB'),period:v.period.value,start_on:v.start.value,end_on:v.end.value||null,rollover:v.rollover.value,participants:r?.data.participants||[]};
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
 if(r)container.append(button(t('family_use_server'),async()=>{
  await refresh();
  if(draftKey)writeNoteDraft(draftKey,null);
  d.close();render();
 }));
 if(r?.editable)container.append(button(t('delete'),()=>{d.close();queueDelete(r,workspace);},'danger'));
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
   append(cell,E('span',t(kind==='total'?'web_today_net':kind),'small'),E('strong',money(amount,currency)));
   row.append(cell);
  }
  container.append(row);
 }
}

function balance(a){let result=BigInt(a.data.opening_minor);for(const r of records('transaction').filter(r=>r.data.account_id===a.id))result+=(r.data.kind==='income'?1n:-1n)*BigInt(r.data.amount_minor);for(const r of records('transfer')){if(r.data.from_id===a.id)result-=BigInt(r.data.sent_minor);if(r.data.to_id===a.id)result+=BigInt(r.data.received_minor);}return result;}
function finance(m){
 title(m,'finances');m.classList.add('finance-page');
 const toolbar=E('div',undefined,'finance-toolbar');
 append(toolbar,addButton(t('web_add_operation'),()=>editRecord('transaction')),button(t('family_kind_transfer'),()=>editRecord('transfer'),'text-button'),button(statementCopy('title'),importStatement,'secondary'));
 m.querySelector('.intro').append(toolbar);
 const sections=E('nav',undefined,'finance-navigation');
 sections.setAttribute('aria-label',t('finances'));
 for(const [id,label] of [['ledger','web_finance_transactions'],['accounts','web_accounts'],['budgets','web_finance_budgets'],['analysis','web_analysis']]){
  const link=E('a',t(label));
  link.href='#finance-'+id;
  sections.append(link);
 }
 const grid=E('div',undefined,'finance-grid');
 const activity=E('div',undefined,'finance-activity'),details=E('aside',undefined,'finance-details');
 append(grid,activity,details);m.append(grid);
 const summary=card(t('web_finance_summary'));
 summary.classList.add('finance-overview');details.append(summary);
 const ledger=card(t('web_history'));ledger.classList.add('ledger');append(activity,ledger,sections);
 ledger.id='finance-ledger';ledger.tabIndex=-1;
 const filterPanel=E('details',undefined,'finance-filter-panel');
 const filterLabel=E('summary',t('web_filters'));
 const filters=E('div',undefined,'finance-filters');
 append(filterPanel,filterLabel,filters);ledger.append(filterPanel);
 const ledgerRows=E('div',undefined,'ledger-rows');ledger.append(ledgerRows);
 const group=(name,label,type='search')=>{const wrap=E('div');filters.append(wrap);return input(wrap,name,label,type,state.financeFilters[name]||'',false);};
 const search=group('finance-search',t('search')),from=group('finance-from',t('web_period_start'),'date'),to=group('finance-to',t('web_period_end'),'date');
 const wrap=E('div');filters.append(wrap);const accountFilter=select(wrap,'finance-account',t('web_accounts'),[['',t('web_all_accounts')],...records('account').map(a=>[a.id,a.data.name+' · '+a.data.currency])],state.financeFilters.account||'');
 const rows=()=>records('transaction').filter(r=>(!accountFilter.value||r.data.account_id===accountFilter.value)&&(!from.value||r.data.date>=from.value)&&(!to.value||r.data.date<=to.value)&&(!search.value||(r.data.label+' '+r.data.date).toLocaleLowerCase(state.lang).includes(search.value.toLocaleLowerCase(state.lang))));
 const accounts=card(t('web_accounts'));accounts.classList.add('finance-accounts');details.append(accounts);
 accounts.id='finance-accounts';accounts.tabIndex=-1;
 for(const a of records('account')){const row=E('div',undefined,'account-balance');append(row,E('span',a.data.name,'text'),E('strong',money(balance(a),a.data.currency)),iconButton('more',t('edit')+' · '+a.data.name,()=>editRecord('account',a)));accounts.append(row);}if(!records('account').length)accounts.append(E('p',t('empty_money')));accounts.append(addButton(t('family_kind_account'),()=>editRecord('account')));
 const chart=card(t('web_analysis'));chart.classList.add('finance-analysis');details.append(chart);const chartControls=E('div',undefined,'chart-controls');chart.append(chartControls);
 chart.id='finance-analysis';chart.tabIndex=-1;
 const currencies=[...new Set([...records('transaction'),...records('account')].map(r=>r.data.currency))];const currency=select(chartControls,'chart-currency',t('currency'),currencies.map(c=>[c,c]),currencies[0]);const mode=select(chartControls,'chart-mode',t('web_chart_type'),[['bar',t('web_bar')],['line',t('web_line')],['smooth',t('web_smooth')],['donut',t('web_donut')],['compact',t('web_compact')]],state.chart);
 const legend=E('div',undefined,'chart-legend');chart.append(legend);const canvas=E('canvas');canvas.width=720;canvas.height=320;canvas.setAttribute('role','img');chart.append(canvas);
 const budgets=card(t('family_kind_budget'));budgets.classList.add('finance-budgets');details.insertBefore(budgets,chart);
 budgets.id='finance-budgets';budgets.tabIndex=-1;
 const budgetLabels=new Map();for(const r of records('budget')){const row=E('div',undefined,'budget-line'),text=E('div'),amount=E('p',money(r.data.limit_minor,r.data.currency),'small');append(text,E('h3',r.data.name),amount);budgetLabels.set(r.id,amount);append(row,text,iconButton('more',t('edit')+' · '+r.data.name,()=>editRecord('budget',r)));budgets.append(row);}
 if(budgetLabels.size){const epoch=privateEpoch;statementWorker({action:'budgets',at:localDate(),records:records('transaction'),budgets:records('budget')}).then(result=>{if(epoch!==privateEpoch||!m.isConnected)return;for(const r of records('budget'))budgetLabels.get(r.id).textContent=t('remaining')+': '+money(result.remaining[r.id],r.data.currency)+' · '+t('budget_limit')+': '+money(r.data.limit_minor,r.data.currency);}).catch(error=>{if(m.isConnected)budgets.append(E('p',errorText(error),'error'));});}
 budgets.append(addButton(t('family_kind_budget'),()=>editRecord('budget')));
 function draw(){
  state.financeFilters={'finance-search':search.value,'finance-from':from.value,'finance-to':to.value,account:accountFilter.value};const active=Object.values(state.financeFilters).filter(Boolean).length;
  filterLabel.textContent=t('web_filters')+(active?' · '+active:'');
  filterLabel.title=[from.value,to.value,accountFilter.value?accountFilter.selectedOptions[0]?.textContent:''].filter(Boolean).join(' · ');
  const filtered=rows();summary.replaceChildren(E('h2',t('web_finance_summary')));
  const activeScope=[from.value? t('web_period_start')+' '+displayDate(from.value):'',to.value? t('web_period_end')+' '+displayDate(to.value):'',accountFilter.value?accountFilter.selectedOptions[0]?.textContent:''].filter(Boolean);
  if(activeScope.length)summary.append(E('p',activeScope.join(' · '),'small finance-scope'));
  for(const code of currencies){const values=financeTotals(filtered,code),row=E('div',undefined,'finance-total');append(row,E('span',code,'currency-code'),E('div',undefined,'income'),E('div',undefined,'expense'));row.children[1].append(E('span',t('income'),'small'),E('strong',money(values.income,code)));row.children[2].append(E('span',t('expense'),'small'),E('strong',money(values.expense,code)));summary.append(row);}if(!currencies.length)summary.append(E('p',t('empty_money')));summary.append(E('p',t('web_totals'),'small'));
  const values=financeTotals(filtered,currency.value);legend.replaceChildren();if(currency.value){legend.append(E('span',t('income')+' · '+money(values.income,currency.value),'income'),E('span',t('expense')+' · '+money(values.expense,currency.value),'expense'));}
  state.chart=mode.value;preferences();canvas.hidden=mode.value==='compact'||!currency.value;drawChart(canvas,currency.value,filtered);
  const transfers=records('transfer').filter(r=>(!accountFilter.value||[r.data.from_id,r.data.to_id].includes(accountFilter.value))&&(!from.value||r.data.date>=from.value)&&(!to.value||r.data.date<=to.value)&&(!search.value||(t('family_kind_transfer')+' '+r.data.date).toLocaleLowerCase(state.lang).includes(search.value.toLocaleLowerCase(state.lang))));
  const entries=[...filtered,...transfers].sort((a,b)=>b.data.date.localeCompare(a.data.date));
  const accountsById=new Map(records('account').map(account=>[account.id,account.data]));
  ledgerRows.replaceChildren();
  const older=E('details',undefined,'ledger-older');
  older.append(E('summary',t('web_all_operations')+' · '+entries.length));
  for(const [index,entry] of entries.entries()){
   const data=entry.data,isTransfer=entry.kind==='transfer',kind=isTransfer?'transfer':data.kind;
   const row=E('div',undefined,'row ledger-row'),text=E('div',undefined,'text');
   const label=isTransfer?t('family_kind_transfer'):data.label||t(kind);
   const account=isTransfer?[accountsById.get(data.from_id)?.name,accountsById.get(data.to_id)?.name].filter(Boolean).join(' → '):accountsById.get(data.account_id)?.name;
   append(text,E('h3',label),E('p',[displayDate(data.date),account].filter(Boolean).join(' · '),'small'));
   const receiving=isTransfer&&accountFilter.value===data.to_id;
   const transferCurrency=accountsById.get(receiving?data.to_id:data.from_id)?.currency;
   const amount=isTransfer?(transferCurrency?money(receiving?data.received_minor:data.sent_minor,transferCurrency):''):(kind==='expense'?'− ':'+ ')+money(data.amount_minor,data.currency);
   append(row,text,E('strong',amount,kind),iconButton('more',t('edit')+' · '+label,()=>editRecord(entry.kind,entry)));
   (index<6?ledgerRows:older).append(row);
  }
  if(entries.length>6)ledgerRows.append(older);
  if(!entries.length)ledgerRows.append(E('p',t(active?'web_no_results':'empty_money'),'empty'));
 }
 redrawFinance=draw;
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
function acceptInvite(){
 let operation,accepted=false;
 const d=dialog(t('family_accept'),container=>form(container,'',f=>({invitation:input(f,'invitation',t('family_invitation'))}),async v=>{
  operation??={id:crypto.randomUUID(),invitation:v.invitation.value};
  if(!accepted){try{await call('invitations/accept',operation);accepted=true;}catch(error){if(!error.uncertain)operation=null;throw error;}}
  try{await refresh();}catch(error){throw {...error,refreshOnly:true};}
  d.close();render();
 }));
}
function familyPanel(m){const c=card(t('family_account'));m.append(c);c.append(button(t('family_create'),()=>createSpace('family')),button(t('family_owner'),()=>createSpace('personal')),button(t('family_accept'),acceptInvite));if(!state.roster)return;const {space,members,profiles}=state.roster;for(const member of members){const row=E('div',undefined,'row');append(row,E('span',member.user_id===state.session.user_id?t('family_you'):member.user_id,'text'),E('span',t('family_'+member.role),'pill'));c.append(row);}if(space.kind==='family'&&['parent','owner'].includes(space.role))c.append(button(t('family_invite'),()=>dialog(t('family_invite'),container=>{let operation;form(container,'',f=>({email:input(f,'email',t('family_invite_email'),'email'),role:select(f,'role',t('family_role'),['adult','parent','child'].map(k=>[k,t('family_'+k)]),'adult'),profile:select(f,'profile',t('family_child'),[['',t('family_none')],...profiles.map(p=>[p.id,p.name])],'')}),async v=>{operation=operation||{id:crypto.randomUUID(),workspace_id:space.id,action:'invite.create',email:v.email.value,role:v.role.value,profile_id:v.role.value==='child'?v.profile.value:null};const invite=await call('family',operation);replaceDialog(container,E('h2',t('family_invite')),E('p',t('family_invite_hint')),E('pre',invite.invitation),button(t('close'),()=>container.close()));});})),button(t('family_child_add'),()=>{const d=dialog(t('family_child_add'),container=>form(container,'',f=>({name:input(f,'name',t('name'))}),async v=>{await call('family',{id:crypto.randomUUID(),workspace_id:space.id,action:'child.save',profile_id:crypto.randomUUID(),revision:0,name:v.name.value,permissions:['view_shared','complete_tasks']});d.close();await refresh();render();}));}));}
function openSettings(section){
 state.settingsTab=section;
 render();
 const back=root.querySelector('.settings-back');
 const target=section?(back?.getClientRects().length?back:root.querySelector('.settings-content h2')):root.querySelector('.settings-navigation button');
 if(target){if(target.tagName==='H2')target.tabIndex=-1;target.focus();}
}
async function account(m){
 const section=state.settingsTab||'profile';
 title(m,section==='personal-import'?'web_personal_import':'account_manage');m.classList.add('settings-page');
 m.dataset.settingsDetail=String(Boolean(state.settingsTab));
 const layout=E('div',undefined,'settings-layout'),navigation=E('nav',undefined,'settings-navigation'),content=E('section',undefined,'settings-content');
 navigation.setAttribute('aria-label',t('account_manage'));
 const back=button(t('web_back_settings'),()=>openSettings(''),'settings-back text-button');
 back.prepend(icon('back'));append(layout,navigation,content);append(m,back,layout);
 const sections=[['profile','profile'],['appearance','theme'],['security','account_privacy'],['family','family_account'],['personal-import','web_personal_import'],['plan','account_access'],['support','account_support']];
 for(const [key,label] of sections){
  const item=settingsRow(t(label),()=>openSettings(key),'settings-item');
  item.dataset.section=key;
  if(section===key)item.setAttribute('aria-current','page');
  navigation.append(item);
 }
 if(section==='profile'){const c=card(t('profile'));append(c,E('p',state.session.email,'account-email'),settingsRow(t('account_privacy'),()=>openSettings('security')),button(t('family_logout'),async()=>{await call('logout',{});clearNoteDrafts();clearTaskActions();clearIdentity();login();},'text-button'));content.append(c);if(['owner','staff'].includes(new URLSearchParams(location.search).get('setup')))content.append(button('ULADIM Control',enrollStaff));}
 if(section==='appearance'){const settings=card(t('theme'));settings.classList.add('settings-grid');content.append(settings);language(settings);const theme=select(settings,'theme',t('theme'),['system','light','dark'].map(k=>[k,t(k)]),state.theme);theme.addEventListener('change',()=>{state.theme=theme.value;preferences();});const palette=select(settings,'palette',t('palette'),[['forest',t('appearance_emerald')],['ocean',t('appearance_sky')],['pistachio',t('appearance_pistachio')]],state.palette);palette.addEventListener('change',()=>{state.palette=palette.value;preferences();});const install=E('details',undefined,'installation-help');append(install,E('summary','iPhone / iPad · PWA'),E('p',t('web_install')));settings.append(install,E('p',t('web_online'),'small'),E('p',t('web_locale_coverage'),'small'));if(deferredInstall)settings.append(button(t('web_install_button'),async()=>{await deferredInstall.prompt();deferredInstall=null;}));}
 if(section==='personal-import')await personalImportCenter(content).catch(report);
 if(section==='security')privacy(content);
 if(section==='family'){familyPanel(content);familyPermissions(content);}
 try{if(section==='family')await incomingOwnership(content);if(section==='plan'){const ent=await call('entitlements');if(state.tab!=='account'||state.settingsTab!==section)return;const plans=card(t('account_access'));append(plans,E('div',ent.tier,'stat'),E('p',t('account_no_payment')));content.append(plans);}if(section==='support')await support(content);}catch(e){report(e);}
}
function enrollStaff(){dialog('ULADIM Control',container=>{const owner=new URLSearchParams(location.search).get('setup')==='owner';const d=container;form(container,t('account_manage'),f=>({password:input(f,'password',t('family_password'),'password'),invitation:input(f,'invitation',t('family_invitation'))}),async v=>{const result=await call('staff/enrollment',{owner,password:v.password.value,invitation:v.invitation.value});replaceDialog(container,E('h2',t('account_mfa')),E('p',t('account_mfa_setup')),E('pre',result.totp_secret));form(container,'',f=>({code:input(f,'code',t('family_code'))}),async code=>{const r=await call('staff/confirm',{owner,enrollment:result.enrollment,code:code.code.value});replaceDialog(container,E('h2',t('account_mfa_recovery')),E('pre',r.recovery_codes.join('\n')),button(t('close'),()=>d.close()));});});});}
async function support(m){const result=await call('support');if(state.tab!=='account')return;const c=card(t('account_support'));m.append(c);for(const ticket of result.tickets||[])c.append(button(ticket.subject,()=>openThread(ticket.id)));form(c,'',f=>({subject:input(f,'subject',t('account_subject')),message:input(f,'message',t('account_message'),'textarea')}),async v=>{await call('support',{category:'other',subject:v.subject.value,message:v.message.value});toast(t('account_done'));render();},t('account_send'));}
async function openThread(id){const result=await call('thread?id='+encodeURIComponent(id));dialog(result.ticket.subject,d=>{for(const message of result.messages)d.append(E('p',message.body,'note'));form(d,'',f=>({message:input(f,'message',t('account_message'),'textarea')}),async v=>{await call('support/reply',{ticket_id:id,message:v.message.value,state:'open'});d.close();await openThread(id);},t('account_send'));});}
window.addEventListener('online',()=>{if(state.session)refresh().then(render).catch(report);});window.addEventListener('offline',()=>{if(state.session&&!document.querySelector('dialog'))render();toast(t('web_online'));});window.addEventListener('pagehide',()=>{clearIdentity();root.replaceChildren();document.querySelector('#alerts').replaceChildren();});window.addEventListener('pageshow',e=>{if(e.persisted)start().catch(error=>{clearIdentity();login();if(error.code!=='unauthorized')toast(errorText(error));});});
document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible'&&state.session&&!document.querySelector('dialog'))refresh().then(render).catch(report);});
setInterval(()=>{if(state.session&&document.visibilityState==='visible'&&!document.querySelector('dialog')&&navigator.onLine)refresh().then(render).catch(report);},30000);
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
 const group=label=>{
  const section=E('section',undefined,'settings-group');
  section.append(E('h2',t(label)));
  m.append(section);
  return section;
 };
 const methods=group('account_google_methods');
 const google=settingsRow('Google',googleMethods);
 const googleStatus=E('span',t('web_google_status_loading'),'settings-row-status');
 google.setAttribute('aria-label','Google');
 googleStatus.id='google-status';
 google.setAttribute('aria-describedby',googleStatus.id);
 const googleLabel=E('span',undefined,'settings-row-copy');
 append(googleLabel,E('span','Google'),googleStatus);
 google.firstChild.replaceWith(googleLabel);
 append(methods,google,settingsRow(t('family_password_change'),changePassword),
  settingsRow(t('account_email_change'),changeEmail));
 const protection=group('web_security_devices');
 append(protection,settingsRow(t('account_mfa'),customerMfa),settingsRow(t('account_devices'),devices));
 const data=group('web_account_data');
 data.append(settingsRow(t('account_delete'),deletion,'danger-text'));
 call('google').then(status=>{
  if(googleStatus.isConnected)googleStatus.textContent=t(status.google_linked?'account_google_linked':'account_google_unlinked');
 }).catch(()=>{
  if(googleStatus.isConnected)googleStatus.textContent=t('web_google_status_error');
 });
}
function changePassword(){
 const label=t('family_password_change');
 dialog(label,d=>{
  d.append(E('p',t('web_password_change_hint'),'small'));
  form(d,'',f=>({old:input(f,'old',t('family_old_password'),'password'),next:input(f,'new',t('family_new_password'),'password')}),async v=>{
   await call('password',{old_password:v.old.value,new_password:v.next.value});
   clearIdentity();
   login();
  },label);
 });
}
function changeEmail(){
 const label=t('account_email_change');
 dialog(label,d=>form(d,'',f=>({email:input(f,'email',t('family_email'),'email'),password:input(f,'password',t('family_old_password'),'password')}),async v=>{
  const email=v.email.value;
  await call('email',{email,password:v.password.value});
  replaceDialog(d,E('h2',t('family_verify')),E('p',email,'account-email'));
  form(d,'',f=>({code:input(f,'code',t('family_code')),password:input(f,'password',t('family_old_password'),'password')}),async v=>{
   await call('confirm-email',{code:v.code.value,password:v.password.value});clearIdentity();login();
  },t('family_verify'));
  d.querySelector('input').focus();
 },label));
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
async function googleMethods(){
 const status=await call('google'),mfa=await call('mfa');
 dialog(t('account_google_methods'),d=>{
  d.append(E('p',t(status.google_linked?'account_google_linked':'account_google_unlinked')));
  if(!status.has_password){d.append(E('p',t('account_google_password_first')),button(t('family_recovery'),recover));return;}
  if(!status.google_linked&&!status.google_web_enabled){d.append(E('p',t('family_error_google_unavailable'),'small'));return;}
  form(d,'',f=>({password:input(f,'password',t('family_old_password'),'password'),...(mfa.enabled?{code:input(f,'code',t('family_code'))}:{})}),async v=>{
   let value;try{value=await call(status.google_linked?'google/unlink':'google/link',{password:v.password.value,code:v.code?.value});}finally{v.password.value='';if(v.code)v.code.value='';}
   if(value.authorization_url){location.assign(value.authorization_url);return;}
   d.close();clearIdentity();login();
  },t(status.google_linked?'account_google_disconnect':'account_google_connect'));
 });
}
async function devices(){
 const {devices:items}=await call('devices');
 dialog(t('account_devices'),d=>{
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
    if(!device.revoked_at)row.append(button(t('account_revoke'),()=>confirmDeviceRevoke(device,d),'text-button danger-text'));
    section.append(row);
   }
   if(!entries.length)section.append(E('p',t('web_no_sessions'),'small'));
   d.append(section);
  }
  group('web_active_sessions',active);
  if(revoked.length)group('web_revoked_sessions',revoked);
 });
}
function confirmDeviceRevoke(device,list){
 dialog(t('account_revoke'),d=>{
  append(d,E('p',device.label,'device-name'),E('p',t(device.current?'web_revoke_current_hint':'web_revoke_device_hint')));
  const confirmation=form(d,'',f=>({password:input(f,'password',t('family_old_password'),'password')}),async v=>{
   try{await call('devices/revoke',{device_id:device.id,password:v.password.value});}finally{v.password.value='';}
   d.close();
   list.close();
   if(device.current){clearIdentity();login();return;}
   toast(t('account_done'));
   await devices();
  },t('account_revoke'));
  confirmation.querySelector('button[type=submit]').classList.add('danger-action');
 });
}
async function customerMfa(){
 const status=await call('mfa');
 dialog(t('account_mfa'),d=>{
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
 });
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
 const choices=[['calendars','calendarFiles','importCalendars'],['notes','noteFiles','importNotes'],['tasks','taskFiles','importTasks']];
 for(const [label,formats,action] of choices){
  const row=E('li');
  append(row,append(E('div'),E('strong',copy(label)),E('p',copy(formats),'small')),
    button(copy(action),()=>openPersonalImport(parser,copy(action)),'secondary'));
  list.append(row);
 }
 const backup=E('li');
 append(backup,append(E('div'),E('strong',copy('backups')),E('p',copy('backupStatus'),'small')));
 files.append(list,E('p',copy('structuredStatus'),'small'));
 list.append(backup);
 const sync=card(copy('sync'),copy('googleStatus'));
 append(host,files,sync,anchor(state.lang==='ru'?'Руководство по импорту':'Import guide','/docs#import'));
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
