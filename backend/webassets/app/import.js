'use strict';
// Files and previews live only in this dialog. Worker lifetime is bounded.
function statementWorker(request){return new Promise((resolve,reject)=>{
 const worker=new Worker('/app/assets/statement-worker.js');
 const timer=setTimeout(()=>{worker.terminate();reject({code:'import_limit'});},10000);
 const finish=()=>{clearTimeout(timer);worker.terminate();};
 worker.onmessage=event=>{finish();try{const value=JSON.parse(event.data);value.error?reject({code:value.error}):resolve(value);}catch{reject({code:'import_format'});}};
 worker.onerror=()=>{finish();reject({code:'import_format'});};
 worker.postMessage(JSON.stringify(request));
});}
function statementKey(v,account){return JSON.stringify([account,v.kind,v.amount,v.currency,v.date,(v.label||'').trim()]);}
function storedStatementKey(record){
 const v=record.data;
 return statementKey({kind:v.kind,amount:v.amount_minor,currency:v.currency,date:v.date,label:v.label},v.account_id);
}
async function statementHash(value){
 const bytes=await crypto.subtle.digest('SHA-256',typeof value==='string'?new TextEncoder().encode(value):value);
 return [...new Uint8Array(bytes)].map(byte=>byte.toString(16).padStart(2,'0')).join('');
}
async function statementID(value){
 const hex=await statementHash(value);
 return hex.slice(0,8)+'-'+hex.slice(8,12)+'-5'+hex.slice(13,16)+'-a'+hex.slice(17,20)+'-'+hex.slice(20,32);
}
function statementCopy(key){return STATEMENT_COPY[state.lang]?.[key]||STATEMENT_COPY.en[key]||t(key);}
function importStatement() {
 const workspace=state.space,user=state.session.user_id,epoch=privateEpoch;
 let accounts=records('account'), source=null, parsed=null, preview=[], pending=null, page=0;
 let running=false, closed=false, modified=false, generation=0;
 const copy=statementCopy;
 const ensureContext=()=>{if(closed||privateEpoch!==epoch||state.space!==workspace||state.session?.user_id!==user)throw {code:'view_changed'};};
 const d=dialog(copy('title'),container=>{
  container.classList.add('statement-dialog');
  const need=E('section',undefined,'statement-account-needed');
  need.append(E('p',copy('need_account')),button(copy('create_account'),openAccount));
  const controls=E('fieldset',undefined,'statement-controls');
  const account=select(controls,'import-account',t('family_account_select'),[],'');
  const file=input(controls,'statement-file',t('choose_file'),'file','',false);
  // A native, unfiltered picker lets iPadOS file providers supply local documents.
  // The parser checks file contents independently.
  const help=E('p',copy('help'),'small');help.id=file.id+'-help';file.setAttribute('aria-describedby',help.id);controls.append(help);
  const sheetControls=E('div');controls.append(sheetControls);
  const advanced=E('details',undefined,'statement-advanced');
  advanced.append(E('summary',copy('advanced')));controls.append(advanced);
  const encoding=select(advanced,'encoding',t('encoding'),[['auto',copy('auto')],['utf8','UTF-8'],['utf16','UTF-16 LE'],['utf-16be','UTF-16 BE'],['cp1251','Windows-1251'],['windows-1252','Windows-1252']],'auto');
  const delimiter=select(advanced,'delimiter',t('web_delimiter'),[['auto',copy('auto')],[';', ';'],[',',','],['\t','Tab'],['|','|']],'auto');
  const mapping=E('div',undefined,'statement-mapping');advanced.append(mapping);
  const status=E('p',undefined,'import-status');status.setAttribute('role','status');
  const totals=E('div',undefined,'statement-totals');
  const results=E('div',undefined,'import-results');
  const actions=E('div',undefined,'actions statement-actions');
  const commit=E('button',t('import_confirm'));commit.type='button';commit.disabled=true;
  commit.addEventListener('click',()=>commitRows().catch(report));
  actions.append(commit);append(container,need,controls,status,totals,results,actions);
  const mappingKeys=[['date',t('date')],['amount',t('amount')],['description',t('description')],['currency',t('currency')],
   ['bankID',copy('bank_id')],['directionColumn',copy('direction_field')],['credit',t('income')],['debit',t('expense')]];
  const fields={};
  function syncAccounts(selected) {
   account.replaceChildren();
   for(const a of accounts){const option=E('option',a.data.name+' · '+a.data.currency);option.value=a.id;account.append(option);}
   if(accounts.some(a=>a.id===selected))account.value=selected;
   need.hidden=accounts.length>0;controls.hidden=!accounts.length;actions.hidden=!accounts.length;
  }
  syncAccounts(accounts[0]?.id);
  function openAccount() {
   if(running||pending)return;
   const before=new Set(accounts.map(a=>a.id)), selected=account.value;
   editRecord('account',null,{onSaved:()=>{
    ensureContext();accounts=records('account');
    syncAccounts(selected||accounts.find(a=>!before.has(a.id))?.id);
    if(parsed)reidentify().catch(showError);else file.focus();
   }});
  }
  const defaultAccount=()=>accounts.find(a=>a.id===account.value);
  function destination(currency){
   if(defaultAccount()?.data.currency===currency)return defaultAccount();
   const matching=accounts.filter(a=>a.data.currency===currency);
   return matching.length===1?matching[0]:null;
  }
  function showError(error){if(!closed)status.textContent=copy(error.code||'import_format');}
  function updateControls(){
   controls.disabled=running||!!pending;results.inert=running||!!pending;commit.disabled=running||!(pending||preview.some(row=>row.selected));
   const close=container.querySelector('.dialog-head button');if(close)close.disabled=running;
  }
  async function readFile(){
   if(pending||!source)return;
   const turn=++generation;
   preview=[];parsed=null;mapping.replaceChildren();sheetControls.replaceChildren();results.replaceChildren();totals.replaceChildren();
   running=true;updateControls();status.textContent=copy('reading');
   try{
    if(source.size>5*1024*1024)throw {code:'import_limit'};
    const bytes=new Uint8Array(await source.arrayBuffer());
    const fingerprint=await statementHash(bytes);
    ensureContext();
    const signature=new TextDecoder().decode(bytes.subarray(0,8));
    if(signature.startsWith('%PDF-')){
     const {extractStatementPdf}=await import('/app/assets/statement-pdf.js');
     const extraction=await extractStatementPdf(bytes);
     parsed=ULADIMStatement.table(extraction.rows,'PDF');
     parsed.needsReview=true;
    }else if(signature.startsWith('%PDF'))throw {code:'import_pdf_layout'};
    else if(bytes[0]===208&&bytes[1]===207&&bytes[2]===17&&bytes[3]===224)throw {code:'import_xls_legacy'};
    else if(bytes[0]===80&&bytes[1]===75&&bytes[2]===3&&bytes[3]===4){
     const {extractStatementXlsx}=await import('/app/assets/statement-xlsx.js');
     const extraction=await extractStatementXlsx(bytes);
     if(extraction.sheets.length>1){
      const sheet=select(sheetControls,'statement-sheet',copy('sheet'),[['',copy('choose_sheet')],...extraction.sheets.map((item,index)=>[index,item.name])],'');
      status.textContent=copy('choose_sheet');
      sheet.addEventListener('change',async()=>{
       if(running||pending)return;
       preview=[];parsed=null;mapping.replaceChildren();results.replaceChildren();totals.replaceChildren();
       if(sheet.value===''){status.textContent=copy('choose_sheet');updateControls();return;}
       try{
        parsed=ULADIMStatement.table(extraction.sheets[Number(sheet.value)].rows,'XLSX');
        parsed.fingerprint=fingerprint+':'+sheet.value;
        buildMapping();await review();
       }catch(error){showError(error);updateControls();}
      });
      return;
     }
     parsed=ULADIMStatement.table(extraction.rows,'XLSX');
    }else parsed=ULADIMStatement.read(bytes,{encoding:encoding.value,delimiter:delimiter.value});
    if(turn!==generation)return;ensureContext();parsed.fingerprint=fingerprint;buildMapping();
    await buildPreview();
   }catch(error){
    if(turn===generation){showError(error);if(['import_mapping_required','import_encoding_required','import_delimiter_ambiguous'].includes(error.code))advanced.open=true;}
   }finally{if(turn===generation){running=false;updateControls();}}
  }
  function buildMapping(){
   const detected=parsed.detection;
   fields.header=select(mapping,'header',t('header_row'),parsed.rows.slice(0,20).map((r,i)=>[i,(i+1)+' · '+r.join(' / ').slice(0,100)]),detected.header);
   const columns=()=>[[-1,copy('no_column')],...parsed.rows[Number(fields.header.value)].map((label,i)=>[i,(i+1)+' · '+label.slice(0,60)])];
   for(const [key,label] of mappingKeys)fields[key]=select(mapping,key,label,columns(),detected[key]??-1);
   fields.header.addEventListener('change',()=>{
    for(const [key] of mappingKeys){
     fields[key].replaceChildren(...columns().map(([value,label])=>{const option=E('option',label);option.value=value;return option;}));
     fields[key].value='-1';
    }
   });
   fields.dateFormat=select(mapping,'dateFormat',t('date_format'),[['auto',copy('auto')],['iso','YYYY-MM-DD'],['dmy','DD.MM.YYYY / DD/MM/YYYY'],['mdy','MM/DD/YYYY'],['excel',t('excel_date')]],detected.dateFormat);
   fields.decimal=select(mapping,'decimal',t('decimal_separator'),[['auto',copy('auto')],['.','1,234.56'],[',','1.234,56']],detected.decimal);
   fields.direction=select(mapping,'direction',t('amount_direction'),[['signed','+ '+t('income')+' / − '+t('expense')],['income',t('income')],['expense',t('expense')]],'signed');
   mapping.append(button(t('import_preview'),review,'secondary'));
  }
  async function review(){
   if(!parsed||running||pending)return;
   running=true;updateControls();
   try{await buildPreview();}
   catch(error){preview=[];results.replaceChildren();totals.replaceChildren();showError(error);}
   finally{running=false;updateControls();}
  }
  function existingTransactions(){return new Map(records('transaction').map(record=>[record.id,storedStatementKey(record)]));}
  async function identify(){
   const known=existingTransactions(),existing=new Set(known.values()),bankIDs=new Map();
   for(const row of preview){
    if(!row.value)continue;
    const value=row.value;
    const target=accounts.find(a=>a.id===row.targetID&&a.data.currency===value.currency)||destination(value.currency);
    row.targetID=target?.id||'';
    row.imported=false;row.repeated=false;row.duplicate=false;row.selected=false;row.id=null;
    if(!target)continue;
    const key=statementKey(value,target.id);
    const bankKey=value.bankID?JSON.stringify([target.id,value.bankID]):null;
    if(bankKey){
     const keys=bankIDs.get(bankKey)||new Set();
     row.repeated=keys.has(key);
     keys.add(key);bankIDs.set(bankKey,keys);
    }
    row.key=key;
    row.bankKey=bankKey;
   }
   for(let i=0;i<preview.length;i+=200){
    await Promise.all(preview.slice(i,i+200).filter(row=>row.targetID&&row.value).map(async row=>{
     const identity=row.bankKey?['uladim-statement-bank-v1',row.bankKey]:['uladim-statement-file-v2',parsed.fingerprint,row.targetID,row.line];
     row.id=await statementID(JSON.stringify([user,workspace,...identity]));
     const bankCollision=row.bankKey&&(bankIDs.get(row.bankKey).size>1||known.has(row.id)&&known.get(row.id)!==row.key);
     if(row.bankKey&&known.get(row.id)!==row.key){
      const alternate=await statementID(JSON.stringify([user,workspace,'uladim-statement-bank-collision-v1',row.bankKey,row.key]));
      if(bankCollision||known.get(alternate)===row.key)row.id=alternate;
     }
     row.imported=known.get(row.id)===row.key;
     row.duplicate=!!(bankCollision||existing.has(row.key))&&!row.imported;
     row.selectionKey=JSON.stringify([row.key,row.id,row.duplicate]);
     const preference=row.selectionPreference?.key===row.selectionKey?row.selectionPreference.checked:undefined;
     row.selected=!row.error&&!row.imported&&!row.repeated&&(preference??(!row.duplicate&&!parsed.needsReview));
    }));
    ensureContext();
   }
  }
  async function reidentify(){
   running=true;updateControls();
   try{await identify();draw();}finally{running=false;updateControls();}
  }
  async function buildPreview(){
   ensureContext();
   const numbers=['header',...mappingKeys.map(([key])=>key)];
   const settings=Object.fromEntries(Object.entries(fields).map(([key,field])=>[key,numbers.includes(key)?Number(field.value):field.value]));
   settings.defaultCurrency=defaultAccount()?.data.currency;
   preview=ULADIMStatement.preview(parsed,settings);
   await identify();page=0;draw();
  }
  function rowStatus(row){
   if(row.saved)return copy('saved');
   if(row.error)return copy(row.error);
   if(row.imported)return t('already_imported');
   if(row.repeated)return copy('repeated_id');
   if(!row.targetID)return copy('missing_currency_account');
   if(row.duplicate)return t('import_duplicate');
   if(parsed.needsReview&&!row.selected)return copy('pdf_review');
   return copy('ready');
  }
  function summary(){
   totals.replaceChildren();
   const counts={selected:0,skipped:0,review:0,saved:0};
   const byCurrency=new Map();
   for(const row of preview){
    if(row.saved)counts.saved++;
    else if(row.selected){
     counts.selected++;
     const v=row.value,group=byCurrency.get(v.currency)||{income:0n,expense:0n};
     group[v.kind]+=BigInt(v.amount);byCurrency.set(v.currency,group);
    }else if(row.imported)counts.skipped++;
    else if(row.error||row.repeated||!row.targetID||row.duplicate||parsed.needsReview)counts.review++;
    else counts.skipped++;
   }
   if(!preview.length)return;
   const overview=E('p',Object.entries(counts).filter(([key,value])=>value>0||key==='selected').map(([key,value])=>
    value+' '+copy(key==='review'?'needs_review':key)).join(' · '));
   totals.append(overview);
   for(const [currency,group] of byCurrency){
    const line=E('p',undefined,'statement-currency');
    line.append(E('strong',currency),E('span','+ '+money(group.income,currency),'income'),E('span','− '+money(group.expense,currency),'expense'));totals.append(line);
   }
  }
  function draw(){
   results.replaceChildren();status.textContent=preview.length?parsed.format+' · '+preview.length+' '+copy('rows'):copy('no_rows');
   if(!preview.length){summary();updateControls();return;}
   if(preview.some(row=>row.value&&!row.targetID))results.append(button(copy('create_account'),openAccount,'secondary'));
   const table=E('table');table.setAttribute('role','table');const head=E('thead'),header=E('tr');
   const columnLabels=[copy('include'),t('date'),t('description'),t('amount'),t('family_kind_transaction'),t('family_account_select'),copy('status')];
   for(const label of columnLabels){
    const th=E('th',label);th.scope='col';header.append(th);
   }
   head.append(header);const body=E('tbody');table.append(head,body);
   for(const item of preview.slice(page*50,(page+1)*50)){
    const row=E('tr'),v=item.value,original=item.original;
    const cell=E('td'),check=E('input');check.type='checkbox';check.checked=!!item.selected;
    check.disabled=!!(item.error||item.imported||item.repeated||!item.targetID||pending);
    check.setAttribute('aria-label',copy('include')+' · '+item.line);
    check.addEventListener('change',()=>{item.selectionPreference={key:item.selectionKey,checked:check.checked};item.selected=check.checked;summary();updateControls();statusCell.firstChild.textContent=rowStatus(item);});
    cell.append(check);
    const statusCell=E('td');statusCell.append(E('span',rowStatus(item)));
    const accountCell=E('td');
    const matching=v?accounts.filter(a=>a.data.currency===v.currency):[];
    if(matching.length>1&&!item.imported&&!pending){
     const choices=[['',t('family_none')],...matching.map(a=>[a.id,a.data.name])];
     const picker=select(accountCell,'row-account-'+item.line,t('family_account_select')+' · '+item.line,choices,item.targetID);
     picker.addEventListener('change',async()=>{item.targetID=picker.value;try{await reidentify();}catch(error){showError(error);}});
    }else accountCell.textContent=accounts.find(a=>a.id===item.targetID)?.data.name||'—';
    if(item.error&&!['import_transfer_review','import_save_conflict','import_save_rejected'].includes(item.error))statusCell.append(button(copy('edit_row'),()=>editRow(item),'secondary'));
    row.append(cell,E('td',v?.date||original.date||'—'),E('td',v?.label||original.label||'—'),
     E('td',v?money(v.amount,v.currency):original.amount||'—'),E('td',v?t(v.kind):'—'),accountCell,statusCell);
    body.append(row);
   }
   const scroll=E('div',undefined,'import-table');scroll.tabIndex=0;scroll.setAttribute('role','region');scroll.setAttribute('aria-label',t('import_preview'));scroll.append(table);results.append(scroll);
   if(preview.length>50){
    const pager=E('div',undefined,'actions');
    const prev=button('←',()=>{page--;draw();}),next=button('→',()=>{page++;draw();});
    prev.setAttribute('aria-label',t('web_previous'));next.setAttribute('aria-label',t('web_next'));
    prev.disabled=page===0;next.disabled=(page+1)*50>=preview.length;
    pager.append(prev,E('span',(page+1)+' / '+Math.ceil(preview.length/50)),next);results.append(pager);
   }
   summary();updateControls();
  }
  function editRow(item){
   const rowDialog=dialog(copy('edit_row')+' · '+item.line,host=>form(host,'',f=>{
    const original=item.original;
    return {date:input(f,'date',t('date'),'text',original.date),amount:input(f,'amount',t('amount'),'text',original.amount),
     currency:input(f,'currency',t('currency'),'text',original.currency),label:input(f,'label',t('description'),'text',original.label,false),
     direction:select(f,'direction',t('family_kind_transaction'),[['',copy('auto')],['income',t('income')],['expense',t('expense')]],item.value?.kind||original.kind||'')};
   },async v=>{
    const row=[v.date.value,v.amount.value,v.label.value,v.currency.value,item.original.bankID,v.direction.value];
    const single=ULADIMStatement.table([['Date','Amount','Description','Currency','Transaction ID','Direction'],row],'CSV');
    const normalized=ULADIMStatement.preview(single,{...single.detection,defaultCurrency:defaultAccount()?.data.currency})[0];
    if(!normalized?.value)throw {code:normalized?.error||'import_format'};
    Object.assign(item,{value:normalized.value,original:normalized.original,error:null});
    await reidentify();rowDialog.close();
   }));
  }
  async function commitRows(){
   ensureContext();if(running)return;
   running=true;updateControls();
   try{
    if(!pending){
     await refresh();ensureContext();
     const current=existingTransactions();
     const keys=new Set(current.values());
     const child=currentSpace()?.role==='child';
     pending=[];
     for(const row of preview.filter(item=>item.selected)){
      if(current.has(row.id)){
       row.imported=current.get(row.id)===row.key;
       row.selected=false;
       if(!row.imported)row.error='import_save_conflict';
       continue;
      }
      if(!row.duplicate&&keys.has(row.key)){row.duplicate=true;row.selected=false;row.selectionPreference=null;continue;}
      const value=row.value;
      pending.push({row,operation:{id:crypto.randomUUID(),action:'record.put',record_id:row.id,revision:0,kind:'transaction',
       visibility:child?'shared':'private',audience:child?[currentSpace().profile_id]:[],
       data:{kind:value.kind,amount_minor:value.amount,currency:value.currency,date:value.date,label:value.label,account_id:row.targetID}}});
     }
    }
    // Keep operation IDs intact when the server may have committed before the response was lost.
    while(pending.length){
     ensureContext();const batch=pending.slice(0,100);
     const result=await call('sync',{workspace_id:workspace,operations:batch.map(item=>item.operation)});ensureContext();
     if(!Array.isArray(result.results)||result.results.length!==batch.length)throw {code:'offline',uncertain:true};
     let reconcile=false;
     result.results.forEach((item,i)=>{
      const row=batch[i].row;
      row.selected=false;
      if(item.status==='accepted'){row.saved=true;row.imported=true;modified=true;}
      else if(item.status==='conflict'||item.error==='revision_conflict'){row.error='import_save_conflict';reconcile=true;}
      else row.error='import_save_rejected';
     });
     pending.splice(0,batch.length);
     if(reconcile){
      await refresh();ensureContext();
      const visible=existingTransactions();
      for(const {row} of batch)if(row.error==='import_save_conflict'&&visible.get(row.id)===row.key){row.error=null;row.imported=true;}
     }
    }
    pending=null;commit.textContent=t('import_confirm');
    await refresh();ensureContext();draw();status.textContent=copy('finished');
   }catch(error){
    if(closed)return;
    if(error.code==='unauthorized'||error.code==='workspace_forbidden'){report(error);return;}
    if(pending?.length&&error.uncertain){commit.textContent=t('retry');status.textContent=errorText(error);summary();}
    else{pending=null;commit.textContent=t('import_confirm');draw();status.textContent=errorText(error);}
   }finally{running=false;updateControls();}
  }
  file.addEventListener('change',()=>{if(file.files?.[0]){source=file.files[0];readFile();}});
  for(const field of [encoding,delimiter])field.addEventListener('change',readFile);
  account.addEventListener('change',()=>{for(const row of preview)row.targetID='';review();});
  dCleanup(()=>{
   const outstanding=!!pending?.length;
   closed=true;source=null;parsed=null;preview=[];pending=null;
   if(privateEpoch!==epoch||state.space!==workspace)return;
   if(outstanding)refresh().then(()=>{if(privateEpoch===epoch)render();}).catch(report);
   else if(modified)render();
  });
  function dCleanup(cleanup){
   container.addEventListener('cancel',event=>{if(running)event.preventDefault();});
   container.addEventListener('close',cleanup);
  }
 });
 return d;
}

const STATEMENT_COPY={
 ru:{
  title:'Импортировать выписку',need_account:'Для импорта нужен счёт. Создайте его, чтобы связать операции с вашими финансами.',
  create_account:'Создать счёт',help:'CSV, TSV, TXT, JSON, OFX, QIF, PDF или XLSX · до 5 МБ. Выписка обрабатывается в браузере.',
  advanced:'Исправить распознавание',auto:'Автоматически',bank_id:'Идентификатор операции',direction_field:'Тип операции',reading:'Распознаём выписку…',
  saved:'сохранено',skipped:'пропущено',selected:'выбрано',needs_review:'требуют проверки',ready:'Готово',rows:'строк',
  include:'Включить',status:'Статус',edit_row:'Исправить строку',no_rows:'В выписке нет операций для проверки.',
  finished:'Импорт завершён. Сохранённые операции доступны в истории.',
  missing_currency_account:'Выберите или создайте счёт в валюте операции.',repeated_id:'Банковский идентификатор повторяется.',
  pdf_review:'Сверьте строку с PDF и отметьте её для импорта.',
  import_mapping_required:'Укажите столбцы даты и суммы в разделе «Исправить распознавание».',
  import_delimiter_ambiguous:'В файле несколько возможных разделителей. Укажите нужный.',
  import_encoding_required:'Кодировка не определена. Выберите её в разделе «Исправить распознавание».',
  import_format:'Структуру выписки не удалось распознать. Проверьте файл или экспортируйте таблицу из банка.',
  import_json_structure:'JSON должен содержать массив операций. Проверьте структуру выписки.',
  import_date_ambiguous:'Уточните порядок дня и месяца.',import_date_invalid:'Укажите существующую дату, например 2026-11-21.',
  import_number_ambiguous:'Уточните, какой знак отделяет дробную часть суммы.',
  no_column:'Не выбрано',import_unreadable_cell:'Ячейка выписки содержит формулу или неподдерживаемый тип. Проверьте строку и введите исходные значения вручную.',
  import_currency_invalid:'Проверьте код валюты, например RUB.',
  import_amount_invalid:'Проверьте сумму, знак и число знаков после разделителя.',
  import_transfer_review:'Похожая на перевод операция. Сверьте счета и добавьте её в разделе «Перевод».',
  import_row_length:'Сократите слишком длинное описание или проверьте идентификатор.',
  import_save_rejected:'Сервер отклонил строку. Проверьте счёт и права на запись.',
  import_save_conflict:'Запись изменилась на сервере. Обновите предпросмотр.',
  import_direction_conflict:'Знак суммы и вид операции противоречат друг другу. Проверьте оба значения.',
  import_pdf_encrypted:'PDF защищён паролем. Сохраните незашифрованную копию или скачайте выписку в другом формате.',
  import_pdf_scanned:'В PDF нет текстового слоя. Скачайте текстовую выписку или CSV.',
  import_pdf_layout:'В таблице PDF не удалось надёжно выделить операции. Попробуйте CSV или XLSX.',
  sheet:'Лист Excel',choose_sheet:'Выберите лист с операциями.',
  import_xlsx_browser:'Этот браузер не распаковывает XLSX. Обновите его или сохраните таблицу как CSV.',
  import_xls_legacy:'Это старый XLS или защищённая книга. Сохраните незашифрованный XLSX или CSV.',
  import_xlsx_layout:'Не удалось прочитать таблицу Excel. Проверьте лист с операциями или сохраните его как CSV.',
  import_xlsx_encrypted:'Книга Excel защищена. Используйте незашифрованную выписку.'
 },
 en:{
  title:'Import a statement',need_account:'Create an account to link statement entries to your finances.',
  create_account:'Create account',help:'CSV, TSV, TXT, JSON, OFX, QIF, PDF or XLSX · up to 5 MB. Your browser processes the statement.',
  advanced:'Correct recognition',auto:'Automatic',bank_id:'Transaction ID',direction_field:'Transaction type',reading:'Reading statement…',
  saved:'saved',skipped:'skipped',selected:'selected',needs_review:'need review',ready:'Ready',rows:'rows',
  include:'Include',status:'Status',edit_row:'Correct row',no_rows:'There are no transactions to review in this statement.',
  finished:'Import finished. Saved transactions are available in history.',
  missing_currency_account:'Choose or create an account in the transaction currency.',repeated_id:'The bank transaction ID appears more than once.',
  pdf_review:'Compare this row with the PDF, then select it for import.',
  import_mapping_required:'Choose the date and amount columns under Correct recognition.',
  import_delimiter_ambiguous:'Several separators are possible. Select the one used by the statement.',
  import_encoding_required:'The file encoding is unclear. Select it under Correct recognition.',
  import_format:'The statement structure is unclear. Check the file or export a table from your bank.',
  import_json_structure:'The JSON file must contain an array of transactions. Check the export structure.',
  import_date_ambiguous:'Confirm the order of the day and month.',import_date_invalid:'Enter a valid date such as 2026-11-21.',
  no_column:'Not selected',import_unreadable_cell:'The statement cell contains a formula or unsupported value. Check the source and correct the row manually.',
  import_number_ambiguous:'Confirm the decimal separator.',import_currency_invalid:'Check the currency code, for example USD.',
  import_amount_invalid:'Check the amount, sign, and number of decimal places.',
  import_transfer_review:'This looks like a transfer. Check both accounts and record it as a transfer.',
  import_row_length:'Shorten the description or check the bank transaction ID.',
  import_save_rejected:'The server rejected this row. Check the account and your write access.',
  import_save_conflict:'The record changed on the server. Refresh the preview.',
  import_direction_conflict:'The amount sign and transaction type disagree. Check both values.',
  import_pdf_encrypted:'This PDF is password-protected. Save an unencrypted copy or download another format.',
  import_pdf_scanned:'This PDF has no text layer. Download a text statement or CSV.',
  import_pdf_layout:'The PDF table could not be read reliably. Try CSV or XLSX.',
  sheet:'Excel sheet',choose_sheet:'Choose the sheet with transactions.',
  import_xlsx_browser:'This browser cannot unpack XLSX. Update it or save the sheet as CSV.',
  import_xls_legacy:'This is a legacy XLS or a protected workbook. Save an unencrypted XLSX or CSV.',
  import_xlsx_layout:'The Excel worksheet could not be read. Check the transaction sheet or save it as CSV.',
  import_xlsx_encrypted:'This Excel workbook is protected. Use an unencrypted statement.'
 }
};
