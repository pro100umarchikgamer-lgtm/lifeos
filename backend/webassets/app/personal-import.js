import {readImportArchive} from './statement-xlsx.js';

const MAX_FILES = 50;
const MAX_BYTES = 5 * 1024 * 1024;
const MAX_RECORDS = 250;
const decode = new TextDecoder('utf-8', {fatal:true});
const invalid = () => {throw new Error('invalid_import');};
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const plain = value => typeof value === 'string' && !/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/u.test(value);

function note(body, issues = []) {
  if (!plain(body) || !body.trim() || [...body].length > 20000) invalid();
  return {kind:'note', data:{body:body.trim()}, issues};
}

function task(item) {
  if (!object(item) || !plain(item.title) || !item.title.trim() || [...item.title].length > 2000 ||
      typeof item.completed !== 'boolean') invalid();
  const issues = Object.keys(item).some(key => !['title','completed','id'].includes(key)) ? ['task_metadata'] : [];
  return {kind:'task', data:{title:item.title.trim(), completed:Number(item.completed), assignment:'any', assignees:[], review:0}, issues};
}

function keep(item) {
  const keepKeys = ['isPinned','isArchived','isTrashed','createdTimestampUsec','userEditedTimestampUsec'];
  if (!object(item) || !keepKeys.some(key => Object.hasOwn(item,key)) ||
      (typeof item.textContent !== 'string' && !Array.isArray(item.listContent) && !plain(item.title))) invalid();
  if (item.isTrashed === true) return {issue:'trashed'};
  const parts = [];
  if (item.title != null) {
    if (!plain(item.title)) invalid();
    parts.push(item.title);
  }
  if (item.textContent != null) {
    if (!plain(item.textContent)) invalid();
    parts.push(item.textContent);
  }
  if (item.listContent != null) {
    if (!Array.isArray(item.listContent) || item.listContent.length > MAX_RECORDS) invalid();
    parts.push(item.listContent.map(line => {
      if (!object(line) || !plain(line.text) || typeof line.isChecked !== 'boolean') invalid();
      return (line.isChecked ? '- [x] ' : '- [ ] ') + line.text;
    }).join('\n'));
  }
  const issues = ['keep_metadata'];
  if (item.attachments?.length) issues.push('attachments');
  return note(parts.filter(part => part.trim()).join('\n\n'), issues);
}

function json(text) {
  const root = JSON.parse(text);
  if (root?.format !== 'uladim-import' || root.version !== 1) return [keep(root)];
  if (!Array.isArray(root.records) || root.records.length > MAX_RECORDS) invalid();
  return root.records.map(item => {
    try {
      if (!object(item)) invalid();
      if (item.id !== undefined && (!plain(item.id) || !item.id.trim() || item.id.length > 500)) invalid();
      let row;
      if (item.kind === 'note') {
        row = note(item.body, Object.keys(item).some(key => !['kind','body','id'].includes(key)) ? ['note_metadata'] : []);
      } else if (item.kind === 'task') {
        const {kind, ...fields} = item;
        row = task(fields);
      } else {
        return {issue:'unsupported_record'};
      }
      if (item.id !== undefined) row.sourceKey = 'uladim-json:' + item.id;
      return row;
    } catch {
      return {issue:'invalid_record'};
    }
  });
}

function calendarDate(value, params = '') {
  const match = /^(\d{4})(\d{2})(\d{2})(?:T(\d{2})(\d{2})(\d{2})(Z)?)?$/u.exec(value);
  if (!match) invalid();
  const [,year,month,day,hour,minute,second,utc] = match;
  const date = `${year}-${month}-${day}`;
  const allDay = hour === undefined;
  const localStart = date + 'T' + (allDay ? '00:00:00' : `${hour}:${minute}:${second}`);
  const instant = new Date(localStart+'Z');
  if (Number(year)<1900 || Number(year)>2200 || !Number.isFinite(+instant) ||
      instant.toISOString().slice(0,19) !== localStart) invalid();
  const zone = /(?:^|;)TZID=("[^"]+"|[^;]+)/iu.exec(params)?.[1].replace(/^"|"$/gu,'');
  if ((utc && zone) || (allDay && zone) || (/TZID=/iu.test(params) && !zone)) invalid();
  const timezone = zone || (utc || allDay ? 'UTC' : 'device');
  if (timezone !== 'device') {
    if (!/^[A-Za-z][A-Za-z0-9_+./-]*$/u.test(timezone)) invalid();
    new Intl.DateTimeFormat('en',{timeZone:timezone});
  }
  return {localStart, timezone, allDay};
}

function calendarEvent(fields, exceptions) {
  const uid = fields.get('UID')?.value;
  if (!uid || uid.length>500 || exceptions.has(uid) || ['EXDATE','RDATE','EXRULE'].some(key=>fields.has(key))) {
    return {issue:'calendar_exception'};
  }
  const summary = fields.get('SUMMARY')?.value?.replace(/\\([nN,;\\])/gu,(_,value)=>/[nN]/u.test(value)?' ':value);
  if (!plain(summary) || !summary.trim() || [...summary].length>2000) invalid();
  const start = fields.get('DTSTART');
  const schedule = {...calendarDate(start?.value,start?.params), repeat:'none', interval:1, until:null};
  const rule = fields.get('RRULE')?.value;
  if (rule !== undefined) {
    const clauses = rule.toUpperCase().split(';').map(clause=>clause.split('='));
    const parts = new Map(clauses);
    if (clauses.some(pair=>pair.length!==2) || parts.size!==clauses.length ||
        [...parts.keys()].some(key=>!['FREQ','INTERVAL','UNTIL'].includes(key))) return {issue:'calendar_rule'};
    schedule.repeat=parts.get('FREQ')?.toLowerCase();
    schedule.interval=Number(parts.get('INTERVAL') ?? 1);
    const monthDay=Number(schedule.localStart.slice(8,10));
    if (!['daily','weekly','monthly','yearly'].includes(schedule.repeat) ||
        !Number.isInteger(schedule.interval) || schedule.interval<1 || schedule.interval>365 ||
        (schedule.repeat==='monthly'&&monthDay>28) ||
        (schedule.repeat==='yearly'&&schedule.localStart.slice(5,10)==='02-29')) return {issue:'calendar_rule'};
    if (parts.has('UNTIL')) {
      const last = calendarDate(parts.get('UNTIL'));
      if (last.allDay!==schedule.allDay || (!last.allDay&&(last.timezone!=='UTC'||schedule.timezone!=='UTC'))) {
        return {issue:'calendar_rule'};
      }
      const cutoff=new Date(last.localStart+'Z');
      if (!last.allDay && last.localStart.slice(11)<schedule.localStart.slice(11)) cutoff.setUTCDate(cutoff.getUTCDate()-1);
      schedule.until=cutoff.toISOString().slice(0,10);
      if (schedule.until<schedule.localStart.slice(0,10)) return {issue:'calendar_rule'};
    }
  }
  const issues=[];
  if (['DTEND','DURATION','DESCRIPTION','LOCATION','ATTACH','VALARM'].some(key=>fields.has(key))) issues.push('calendar_metadata');
  if (schedule.timezone==='device') issues.push('floating_time');
  return {kind:'event', data:{title:summary.trim(),schedule}, sourceKey:uid, issues};
}

function ics(text) {
  const lines = text.replace(/\r\n|\r/gu,'\n').replace(/\n[ \t]/gu,'').trim().split('\n');
  if (lines[0]?.toUpperCase()!=='BEGIN:VCALENDAR' || lines.at(-1)?.toUpperCase()!=='END:VCALENDAR') invalid();
  const stack=[], events=[];
  let event;
  for (const line of lines) {
    let colon=-1,quoted=false;
    for(let index=0;index<line.length;index++){
      if(line[index]==='"') quoted=!quoted;
      else if(line[index]===':'&&!quoted){colon=index;break;}
    }
    if (colon<0) {if(line.trim())invalid();continue;}
    const [rawKey,...params]=line.slice(0,colon).split(';');
    const key=rawKey.toUpperCase(),value=line.slice(colon+1);
    if (key==='BEGIN') {
      const component=value.toUpperCase();
      if (component==='VEVENT') {
        if (stack.at(-1)!=='VCALENDAR' || events.length>=MAX_RECORDS) invalid();
        event=new Map();
      } else if (component==='VALARM' && event) event.set('VALARM',{value});
      stack.push(component);
    } else if (key==='END') {
      const component=value.toUpperCase();
      if (stack.pop()!==component) invalid();
      if (component==='VEVENT') {events.push(event);event=null;}
    } else if (event && stack.at(-1)==='VEVENT') {
      if (event.has(key) && ['UID','SUMMARY','DTSTART','RRULE','RECURRENCE-ID'].includes(key)) event.set('DUPLICATE',{value});
      event.set(key,{value,params:params.join(';')});
    }
  }
  if (stack.length || !events.length) invalid();
  const counts=new Map(), exceptions=new Set();
  for(const event of events){
    const uid=event.get('UID')?.value;
    counts.set(uid,(counts.get(uid)||0)+1);
    if(event.has('RECURRENCE-ID'))exceptions.add(uid);
  }
  return events.map(event=>{
    const uid=event.get('UID')?.value;
    if(counts.get(uid)>1 || event.has('DUPLICATE') || event.get('STATUS')?.value.toUpperCase()==='CANCELLED') return {issue:'calendar_exception'};
    try{return calendarEvent(event,exceptions);}catch{return {issue:'invalid_record'};}
  });
}

export async function previewPersonalFiles(files) {
  if (!files.length || files.length>MAX_FILES || files.reduce((sum,file)=>sum+file.size,0)>MAX_BYTES) {
    return [{issue:'limit'}];
  }
  const rows=[];
  for (const file of files) {
    try {
      const bytes=new Uint8Array(await file.arrayBuffer());
      if (bytes[0]===0x50 && bytes[1]===0x4b) {
        const entries=readImportArchive(bytes).filter(entry=>!entry.name.endsWith('/'));
        const keepFiles=entries.filter(entry=>/(?:^|\/)Keep\/[^/]+\.json$/iu.test(entry.name));
        if (!keepFiles.length || keepFiles.length>MAX_RECORDS) invalid();
        for (const entry of keepFiles) {
          try{rows.push(keep(JSON.parse(decode.decode(await entry.read()))));}
          catch{rows.push({issue:'invalid_record'});}
        }
        if(entries.some(entry=>!keepFiles.includes(entry)&&!/\.html?$/iu.test(entry.name))) rows.push({issue:'attachments'});
      } else {
        const value=decode.decode(bytes).replace(/^\uFEFF/u,'').trim();
        if (!plain(value)) invalid();
        if (/^BEGIN:VCALENDAR(?:\r|\n)/iu.test(value)) rows.push(...ics(value));
        else if (/\.(?:md|markdown|txt)$/iu.test(file.name) && !/^%PDF-|^<!DOCTYPE html|^<html/iu.test(value)) rows.push(note(value));
        else if (/^[{\[]/u.test(value) || /\.json$/iu.test(file.name)) rows.push(...json(value));
        else rows.push({issue:'unsupported_file'});
      }
    } catch {rows.push({issue:'invalid_file'});}
    if (rows.length>MAX_RECORDS) return [{issue:'limit'}];
  }
  return rows.length?rows:[{issue:'invalid_file'}];
}

const COPY = {
  ru: {
    title:'Импорт и синхронизация', oneTime:'Разовый импорт', sync:'Синхронизация',
    pick:'Выбрать файлы', calendars:'Календари', notes:'Заметки', tasks:'Задачи', backups:'Резервные копии',
    importCalendars:'Импортировать календарь', importNotes:'Импортировать заметки', importTasks:'Импортировать задачи',
    calendarFiles:'Файлы ICS', noteFiles:'TXT, Markdown и экспорт Google Keep', taskFiles:'Совместимый JSON',
    backupStatus:'Восстановление резервных копий готовится.', googleStatus:'Подключение Google Calendar готовится.',
    structuredStatus:'Экспорт Structured ещё проверяется.',
    local:'Файлы проверяются на устройстве. После подтверждения записи сохраняются в выбранном пространстве.',
    noSpace:'Сначала выберите пространство ULADIM.', child:'Импорт доступен из взрослого аккаунта.',
    checking:'Проверяем файлы…', review:'Проверьте найденные записи', ready:'К импорту', duplicate:'Уже есть',
    conflict:'Запись уже есть и отличается. Существующая версия будет сохранена.', skipped:'Пропущено',
    save:'Импортировать', saved:'Сохранено', failed:'Требуют повторной проверки', retry:'Повторить импорт',
    retryHelp:'Ответ сервера не получен. Можно безопасно повторить сохранение.',
    invalid_file:'Файл повреждён или его формат не распознан.',
    invalid_record:'Запись не удалось прочитать.',
    unsupported_file:'Этот тип файла пока не поддерживается.',
    unsupported_record:'Такую запись пока нельзя перенести.',
    limit:'Выберите до 50 файлов общим размером до 5 МБ и не более 250 записей.',
    trashed:'Заметка в корзине пропущена.',
    attachments:'Вложения не перенесутся.',
    keep_metadata:'Закрепление, архив, метки и даты Keep не перенесутся.',
    note_metadata:'Дополнительные свойства заметки не перенесутся.',
    task_metadata:'Дополнительные поля задачи, включая даты, время и подзадачи, не перенесутся.',
    calendar_metadata:'Длительность, описание, место, напоминания и вложения события не перенесутся.',
    calendar_exception:'Событие с исключением, отменой или повторяющимся идентификатором пропущено.',
    calendar_rule:'Правило повторения нельзя перенести без изменений. Событие пропущено.',
    floating_time:'Время без часового пояса будет локальным на каждом устройстве.',
  },
  en: {
    title:'Import and sync', oneTime:'File import', sync:'Synchronization',
    pick:'Choose files', calendars:'Calendars', notes:'Notes', tasks:'Tasks', backups:'Backups',
    importCalendars:'Import calendar', importNotes:'Import notes', importTasks:'Import tasks',
    calendarFiles:'ICS files', noteFiles:'TXT, Markdown and Google Keep export', taskFiles:'Compatible JSON',
    backupStatus:'Backup restoration is in development.', googleStatus:'Google Calendar connection is in development.',
    structuredStatus:'Structured export compatibility is under review.',
    local:'Files are checked on this device. Confirm to save records to the selected workspace.',
    noSpace:'Choose a ULADIM workspace first.', child:'Import is available to adult accounts.',
    checking:'Checking files…', review:'Review the records', ready:'Ready to import', duplicate:'Already exists',
    conflict:'An existing record differs. Its current version will be kept.', skipped:'Skipped',
    save:'Import', saved:'Saved', failed:'Needs review', retry:'Retry import',
    retryHelp:'No response from the server. It is safe to retry.',
    invalid_file:'The file is damaged or its format was not recognized.', invalid_record:'The record could not be read.',
    unsupported_file:'This file type is not supported yet.', unsupported_record:'This record type is not supported yet.',
    limit:'Choose up to 50 files, 5 MB total, and at most 250 records.',
    trashed:'A trashed note was skipped.', attachments:'Attachments will not be imported.',
    keep_metadata:'Pinning, archive state, labels and dates from Keep will not be imported.',
    note_metadata:'Additional note properties will not be imported.',
    task_metadata:'Additional task fields, including dates, times and subtasks, will not be imported.',
    calendar_metadata:'Event duration, description, location, reminders and attachments will not be imported.',
    calendar_exception:'An event with an exception, cancellation or duplicate identifier was skipped.',
    calendar_rule:'This recurrence cannot be represented exactly. The event was skipped.',
    floating_time:'The event has no timezone. Its time remains local on each device.',
  }
};

export function importCopy(key, lang) {
  return (COPY[lang] || COPY.en)[key];
}

function stable(value) {
  if (Array.isArray(value)) return value.map(stable);
  if (object(value)) return Object.fromEntries(Object.keys(value).sort().map(key=>[key,stable(value[key])]));
  return value;
}

export async function identifyPersonalRows(rows, scope, records, idFor) {
  const seen=new Map(records.map(record=>[record.id,{kind:record.kind,data:record.data}]));
  for(const row of rows){
    if(row.issue)continue;
    const body=JSON.stringify(stable(row.data));
    row.id=await idFor(JSON.stringify(['personal-import-v1',...scope,row.kind,row.sourceKey??body]));
    const previous=seen.get(row.id);
    if(previous) row.status=previous.kind===row.kind&&JSON.stringify(stable(previous.data))===body?'duplicate':'conflict';
    else {
      row.status='ready';
      seen.set(row.id,{kind:row.kind,data:row.data});
    }
  }
  return rows;
}
