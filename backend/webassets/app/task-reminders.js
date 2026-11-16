/* Persisted task metadata. Transport/session authority is supplied by the app. */
(() => {
 'use strict';
 const COPY=globalThis.UladimI18n.copy("grp_070389c59d02",{
  ru:{legend:'Дата и напоминание',date:'Дата задачи',time:'Время (необязательно)',reminder:'Напомнить об этой задаче',clear:'Без даты',zone:'Часовой пояс',help:'В выбранное время; без времени — в 09:00. Включите уведомления этого браузера в настройках профиля. Приоритет берётся из ваших настроек; звук и доставка зависят от браузера и ОС.',readOnly:'Расписание этой задачи доступно только для просмотра.'},
  en:{legend:'Date and reminder',date:'Task date',time:'Time (optional)',reminder:'Remind me about this task',clear:'No date',zone:'Time zone',help:'At the selected time, or 09:00 without a time. Enable notifications for this browser in profile settings. Your notification priority applies; sound and delivery depend on the browser and OS.',readOnly:'You can view this task schedule but cannot edit it.'},
  'uz-Latn':{legend:'Sana va eslatma',date:'Vazifa sanasi',time:'Vaqt (ixtiyoriy)',reminder:'Bu vazifa haqida eslatish',clear:'Sanasiz',zone:'Vaqt mintaqasi',help:'Tanlangan vaqtda, vaqt bo‘lmasa — 09:00 da. Profil sozlamalarida ushbu brauzer bildirishnomalarini yoqing. Ustuvorlik sozlamalaringiz qo‘llanadi; ovoz va yetkazish brauzer va tizimga bog‘liq.',readOnly:'Bu vazifa jadvalini faqat ko‘rishingiz mumkin.'},
  'uz-Cyrl':{legend:'Сана ва эслатма',date:'Вазифа санаси',time:'Вақт (ихтиёрий)',reminder:'Бу вазифа ҳақида эслатиш',clear:'Санасиз',zone:'Вақт минтақаси',help:'Танланган вақтда, вақт бўлмаса — 09:00 да. Профил созламаларида ушбу браузер билдиришномаларини ёқинг. Устуворлик созламаларингиз қўлланади; овоз ва етказиш браузер ва тизимга боғлиқ.',readOnly:'Бу вазифа жадвалини фақат кўришингиз мумкин.'}
 });
 const FLOW=globalThis.UladimI18n.copy("grp_32b117742186",{
  ru:{loading:'Загрузка даты задачи…',loadFailed:'Не удалось загрузить дату задачи. Сохранённая дата не изменена.',reload:'Загрузить сохранённую дату',savedFailed:'Задача сохранена. Сохранение даты и напоминания пока не подтверждено.',conflict:'Дата изменена в другом сеансе. Загрузите сохранённую дату перед повторным изменением.',completed:'Задача завершена. Отключите напоминание, чтобы сохранить дату.'},
  en:{loading:'Loading task date…',loadFailed:'Could not load the task date. Its saved date has not changed.',reload:'Load saved date',savedFailed:'Task saved. Its date and reminder have not been confirmed yet.',conflict:'The date changed in another session. Load the saved date before editing it again.',completed:'This task is complete. Turn off its reminder to save the date.'},
  'uz-Latn':{loading:'Vazifa sanasi yuklanmoqda…',loadFailed:'Vazifa sanasini yuklab bo‘lmadi. Saqlangan sana o‘zgarmadi.',reload:'Saqlangan sanani yuklash',savedFailed:'Vazifa saqlandi. Sana va eslatma hali tasdiqlanmadi.',conflict:'Sana boshqa seansda o‘zgartirildi. Qayta tahrirlashdan oldin saqlangan sanani yuklang.',completed:'Vazifa bajarilgan. Sanani saqlash uchun eslatmani o‘chiring.'},
  'uz-Cyrl':{loading:'Вазифа санаси юкланмоқда…',loadFailed:'Вазифа санасини юклаб бўлмади. Сақланган сана ўзгармади.',reload:'Сақланган санани юклаш',savedFailed:'Вазифа сақланди. Сана ва эслатма ҳали тасдиқланмади.',conflict:'Сана бошқа сеансда ўзгартирилди. Қайта таҳрирлашдан олдин сақланган санани юкланг.',completed:'Вазифа бажарилган. Санани сақлаш учун эслатмани ўчиринг.'}
 });
 function matches(a,b){
  if(Boolean(a?.reminder)!==Boolean(b?.reminder))return false;
  if(!a?.schedule||!b?.schedule)return !a?.schedule&&!b?.schedule;
  return ['localStart','timezone','allDay','repeat','interval','until'].every(key=>a.schedule[key]===b.schedule[key]);
 }
 let sequence=0;
 const element=(tag,text)=>{const node=document.createElement(tag);if(text!==undefined)node.textContent=text;return node;};
 const path=(workspace,task)=>'task-reminders?workspace='+encodeURIComponent(workspace)+(task?'&task_id='+encodeURIComponent(task):'');
 function mount(container,{initial={},lang='en',timezone,wrapDate=field=>field,onChange=()=>{}}={}){
  const c=COPY[lang]||COPY.en,prefix='task-schedule-'+(++sequence),section=element('fieldset');section.className='task-schedule-fields';section.style.minInlineSize='0';
  section.append(element('legend',c.legend));
  const control=(name,caption,type)=>{const label=element('label',caption),field=element('input');field.type=type;field.id=prefix+'-'+name;field.name='task_schedule_'+name;field.style.maxWidth='100%';field.style.boxSizing='border-box';label.htmlFor=field.id;section.append(label,field);wrapDate(field);return field;};
  const date=control('date',c.date,'date'),time=control('time',c.time,'time');date.min='1900-01-01';date.max='2200-12-31';
  const reminderLabel=element('label'),reminder=element('input');reminder.type='checkbox';reminder.id=prefix+'-reminder';reminder.name='task_schedule_reminder';reminderLabel.htmlFor=reminder.id;reminderLabel.style.display='flex';reminderLabel.style.alignItems='center';reminderLabel.style.gap='10px';reminderLabel.append(reminder,element('span',c.reminder));section.append(reminderLabel);
  const clear=element('button',c.clear);clear.type='button';clear.className='text-button';section.append(clear);
  const zone=initial.schedule?.timezone||timezone||Intl.DateTimeFormat().resolvedOptions().timeZone||'UTC';
  const zoneText=element('p',c.zone+': '+zone);zoneText.className='small';section.append(zoneText);
  const help=element('p',initial.can_edit===false?c.readOnly:c.help);help.id=prefix+'-help';help.className='small';reminder.setAttribute('aria-describedby',help.id);
  const helpDetails=element('details');helpDetails.className='task-schedule-help';
  helpDetails.append(element('summary',(globalThis.UladimI18n.copy("grp_cede9efcef0f",{ru:'Как приходят напоминания',en:'How reminders arrive','uz-Latn':'Eslatmalar qanday keladi','uz-Cyrl':'Эслатмалар қандай келади'}))[lang]||'How reminders arrive'),help);section.append(helpDetails);
  const original=initial.schedule?{...initial.schedule}:null;let busy=false;
  if(original){date.value=original.localStart.slice(0,10);time.value=original.allDay?'':original.localStart.slice(11,16);}
  reminder.checked=Boolean(initial.reminder);
  function state(){const locked=busy||initial.can_edit===false,hasDate=Boolean(date.value),timeRoot=time.dateField||time;date.disabled=locked;time.disabled=locked||!hasDate;reminder.disabled=locked||!hasDate;clear.disabled=locked||!hasDate;if(!hasDate)reminder.checked=false;timeRoot.hidden=!hasDate;timeRoot.previousElementSibling.hidden=!hasDate;for(const node of [reminderLabel,clear,zoneText,helpDetails])node.hidden=!hasDate;}
  function value(){
   if(!date.value)return {schedule:null,reminder:false};
   if(!date.checkValidity()||!time.checkValidity()){section.closest('form')?.reportValidity();throw Object.assign(new Error('invalid_schedule'),{code:'invalid_schedule'});}
   const until=original?.until&&original.until>=date.value?original.until:null;
   return {schedule:{localStart:date.value+'T'+(time.value||'09:00')+':00',timezone:zone,allDay:!time.value,
    repeat:original?.repeat||'none',interval:original?.interval||1,until},reminder:reminder.checked};
  }
  function changed(){state();onChange();}
  date.addEventListener('change',changed);time.addEventListener('change',changed);reminder.addEventListener('change',changed);
  clear.addEventListener('click',()=>{date.value='';time.value='';reminder.checked=false;changed();});
  state();container.append(section);
  return {element:section,date,time,reminder,value,setBusy(value){busy=Boolean(value);state();},dispose(){section.remove();}};
 }
 window.UladimTaskReminders={
  list:(api,workspace)=>api(path(workspace)),
  get:(api,workspace,task)=>api(path(workspace,task)),
  save:(api,{workspace_id,task_id,revision,schedule,reminder})=>api('task-reminders',{workspace_id,task_id,revision,schedule,reminder}),
  mount,matches,copy:(lang='en')=>({...((COPY[lang])||COPY.en),...((FLOW[lang])||FLOW.en)}),
 };
})();
