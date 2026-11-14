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
const STATEMENT_FLOW_COPY={
 ru:['Выбор файла','Проверка','Результат','Сохранено операций','Не сохранено из выбранных','Открыть историю операций','Вернуться к проверке','Сервер подтвердил запись. Повторите загрузку истории.'],
 en:['Choose file','Review','Result','Transactions saved','Selected but not saved','Open transaction history','Back to review','The server accepted the write. Retry loading history.'],
 'uz-Latn':['Fayl tanlash','Tekshirish','Natija','Saqlangan amallar','Tanlangan, ammo saqlanmagan','Amallar tarixini ochish','Tekshirishga qaytish','Server yozuvni qabul qildi. Tarixni qayta yuklang.'],
 'uz-Cyrl':['Файл танлаш','Текшириш','Натижа','Сақланган амаллар','Танланган, аммо сақланмаган','Амаллар тарихини очиш','Текширишга қайтиш','Сервер ёзувни қабул қилди. Тарихни қайта юкланг.']
};
const STATEMENT_SOURCE_COPY={
 ru:['Счета в выписке','Использовать отдельные счета','Объединить в существующий счёт','Новый счёт','Использовать счета','Создать счета и использовать','Начальный остаток новых счетов — 0. Операции сохраняются следующим шагом.','Разные валюты нельзя объединить в один счёт. Выберите отдельные счета.','Сначала подтвердите счета выписки.','Счета не подтверждены. Повторите запрос — копии не создадутся.','Не удалось подтвердить счёт. Проверьте доступ и повторите.','Найден существующий счёт','Создать','Счёт из выписки'],
 en:['Statement accounts','Use separate accounts','Combine into an existing account','New account','Use accounts','Create accounts and use them','New accounts start at 0. Save transactions in the next step.','Different currencies cannot share one account. Use separate accounts.','Confirm statement accounts first.','Accounts are not confirmed. Retry the request; it will not create copies.','The account could not be confirmed. Check access and retry.','Existing account found','Create','Statement account'],
 'uz-Latn':['Ko‘chirmadagi hisoblar','Alohida hisoblardan foydalanish','Mavjud hisobga birlashtirish','Yangi hisob','Hisoblardan foydalanish','Hisoblarni yaratish va foydalanish','Yangi hisoblar 0 dan boshlanadi. Amallarni keyingi bosqichda saqlang.','Turli valyutalarni bir hisobga birlashtirib bo‘lmaydi. Alohida hisoblarni tanlang.','Avval ko‘chirma hisoblarini tasdiqlang.','Hisoblar tasdiqlanmadi. Qayta urining; nusxalar yaratilmaydi.','Hisob tasdiqlanmadi. Ruxsatni tekshiring va qayta urining.','Mavjud hisob topildi','Yaratish','Ko‘chirma hisobi'],
 'uz-Cyrl':['Кўчирмадаги ҳисоблар','Алоҳида ҳисоблардан фойдаланиш','Мавжуд ҳисобга бирлаштириш','Янги ҳисоб','Ҳисоблардан фойдаланиш','Ҳисобларни яратиш ва фойдаланиш','Янги ҳисоблар 0 дан бошланади. Амалларни кейинги босқичда сақланг.','Турли валюталарни бир ҳисобга бирлаштириб бўлмайди. Алоҳида ҳисобларни танланг.','Аввал кўчирма ҳисобларини тасдиқланг.','Ҳисоблар тасдиқланмади. Қайта урининг; нусхалар яратилмайди.','Ҳисоб тасдиқланмади. Рухсатни текширинг ва қайта урининг.','Мавжуд ҳисоб топилди','Яратиш','Кўчирма ҳисоби']
};
function importStatement() {
 const workspace=state.space,user=state.session.user_id,epoch=privateEpoch;
 let accounts=records('account'), source=null, parsed=null, preview=[], pending=null, page=0;
 let running=false, closed=false, modified=false, generation=0, attempted=[], stage=0, correcting=null;
 let sourcePlans=[],sourceSignature='',sourceApplied=false,accountPending=null,sourceMode='separate';
 const sourceCopy=STATEMENT_SOURCE_COPY[state.lang]||STATEMENT_SOURCE_COPY.en;
 const [chooseStep,reviewStep,resultStep,savedLabel,failedLabel,historyLabel,reviewLabel,refreshLabel]=STATEMENT_FLOW_COPY[state.lang]||STATEMENT_FLOW_COPY.en;
 const copy=statementCopy;
 const ensureContext=()=>{if(closed||privateEpoch!==epoch||state.space!==workspace||state.session?.user_id!==user)throw {code:'view_changed'};};
 const d=dialog(copy('title'),container=>{
  container.classList.add('statement-dialog');
  const steps=E('ol',undefined,'statement-steps');
  for(const label of [chooseStep,reviewStep,resultStep])steps.append(E('li',label));
  const receipt=E('section',undefined,'statement-receipt');receipt.tabIndex=-1;
  const need=E('section',undefined,'statement-account-needed');
  need.append(E('p',copy('need_account')),button(copy('create_account'),openAccount));
  const controls=E('fieldset',undefined,'statement-controls');
  const account=select(controls,'import-account',t('family_account_select'),[],'');
  const sourceGroup=E('section',undefined,'statement-source-accounts');sourceGroup.hidden=true;
  const sourceChoices=E('fieldset'),sourceRows=E('div'),sourceMessage=E('p',undefined,'small');
  sourceChoices.append(E('legend',sourceCopy[0]));
  const sourceStrategy=select(sourceChoices,'statement-account-strategy',sourceCopy[0],[['separate',sourceCopy[1]],['combine',sourceCopy[2]]],'separate');
  sourceStrategy.setAttribute('aria-label',sourceCopy[0]);sourceChoices.querySelector('label').hidden=true;
  const combineAccount=select(sourceChoices,'statement-combine-account',t('family_account_select'),[],'');
  const sourceConfirm=button(sourceCopy[4],()=>confirmSourceAccounts(),'secondary');
  sourceConfirm.classList.add('statement-source-confirm');
  sourceGroup.append(sourceChoices,sourceRows,sourceMessage,sourceConfirm);
  const fileOptions=E('details',undefined,'statement-file-options');
  const fileTitle=E('summary');
  const fileTitleLabel=E('span',chooseStep);
  fileTitle.append(fileTitleLabel);fileOptions.append(fileTitle);controls.append(fileOptions);
  const file=input(fileOptions,'statement-file',t('choose_file'),'file','',false);
  // A native, unfiltered picker lets iPadOS file providers supply local documents.
  // The parser checks file contents independently.
  const help=E('p',copy('help'),'small');help.id=file.id+'-help';file.setAttribute('aria-describedby',help.id);fileOptions.append(help);
  const sheetControls=E('div');controls.append(sheetControls);
  const advanced=E('details',undefined,'statement-advanced');
  const advancedTitle=E('summary');advancedTitle.append(E('span',copy('advanced')),E('span',copy('advanced_badge'),'statement-advanced-badge'));advanced.append(advancedTitle,E('p',copy('advanced_help'),'small'));controls.append(advanced);
  const dateHelp=E('section',undefined,'statement-date-help');dateHelp.hidden=true;controls.insertBefore(dateHelp,advanced);
  const recognitionHelp=E('section',undefined,'statement-recognition-help');recognitionHelp.hidden=true;controls.insertBefore(recognitionHelp,advanced);
  const recognitionMessage=E('p',copy('recognition_help'));
  const recognitionFields=E('div',undefined,'statement-required-fields');
  recognitionHelp.append(recognitionMessage,recognitionFields,button(copy('open_advanced'),()=>{advanced.open=true;const field=fields.date?.value==='-1'?fields.date:fields.amount?.value==='-1'?fields.amount:encoding;field.focus();field.scrollIntoView({block:'center'});},'text-button'));
  const encoding=select(advanced,'encoding',t('encoding'),[['auto',copy('auto')],['utf8','UTF-8'],['utf16','UTF-16 LE'],['utf-16be','UTF-16 BE'],['cp1251','Windows-1251'],['windows-1252','Windows-1252']],'auto');
  const delimiter=select(advanced,'delimiter',t('web_delimiter'),[['auto',copy('auto')],[';', ';'],[',',','],['\t','Tab'],['|','|']],'auto');
  const mapping=E('div',undefined,'statement-mapping');advanced.append(mapping);
  const status=E('p',undefined,'import-status');status.setAttribute('role','status');
  const totals=E('div',undefined,'statement-totals');
  const results=E('div',undefined,'import-results');
  const correction=E('section',undefined,'statement-row-correction');correction.hidden=true;
  const actions=E('div',undefined,'actions statement-actions');
  const commit=E('button',t('import_confirm'));commit.type='button';commit.disabled=true;
  commit.addEventListener('click',()=>commitRows().catch(report));
  const selectReady=button(copy('select_ready'),()=>{
   for(const row of preview)if(ready(row)){row.selected=true;row.selectionPreference={key:row.selectionKey,checked:true};}
   draw();
  },'secondary');
  const clearSelection=button(copy('clear_selection'),()=>{
   for(const row of preview){row.selected=false;row.selectionPreference={key:row.selectionKey,checked:false};}
   draw();
  },'text-button');
  const bulk=E('div',undefined,'actions statement-bulk');bulk.append(selectReady,clearSelection);
  actions.append(commit);append(container,steps,need,controls,sourceGroup,status,receipt,correction,totals,bulk,results,actions);
  function setStage(next){
   stage=next;
   for(const [i,item] of [...steps.children].entries()){
    if(i===stage)item.setAttribute('aria-current','step');else item.removeAttribute('aria-current');
   }
   receipt.hidden=stage!==2;
   controls.hidden=stage===2;
   sourceGroup.hidden=stage===2||!sourcePlans.length;
   need.hidden=accounts.length>0||!!sourcePlans.length;
   fileOptions.open=stage===0;
   fileTitleLabel.textContent=source?.name||chooseStep;
   fileTitleLabel.title=source?.name||'';
   totals.hidden=results.hidden=stage===2;bulk.hidden=stage!==1||!preview.length;
   actions.hidden=stage===2;
  }
  setStage(0);
  const mappingKeys=[['date',t('date')],['amount',t('amount')],['description',t('description')],['currency',t('currency')],
   ['bankID',copy('bank_id')],['directionColumn',copy('direction_field')],['credit',t('income')],['debit',t('expense')]];
  const fields={};
  function syncAccounts(selected) {
   account.replaceChildren();
   for(const a of accounts){const option=E('option',a.data.name+' · '+a.data.currency);option.value=a.id;account.append(option);}
   if(accounts.some(a=>a.id===selected))account.value=selected;
   need.hidden=accounts.length>0;controls.hidden=stage===2;actions.hidden=stage===2;
   account.hidden=!accounts.length;
   controls.querySelector('label[for="'+account.id+'"]').hidden=account.hidden;
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
  function confirmedSourceAccount(id,currency){
   const record=state.records.find(item=>item.id===id);
   if(!record)return null;
   if(record.deleted||record.kind!=='account'||record.data.currency!==currency)throw {code:'statement_account_conflict'};
   return record;
  }
  async function prepareSourcePlans(header){
   const metadata=ULADIMStatement.sourceAccounts(parsed,header);
   const valid=preview.filter(row=>row.value);
   // Incomplete owner context must never silently send unknown rows elsewhere.
   if(!valid.length||preview.some(row=>!metadata[row.line])){
    sourcePlans=[];sourceSignature='';sourceApplied=false;drawSourceAccounts();return;
   }
   const grouped=new Map();
   for(const row of valid){
    const owner=metadata[row.line],key=JSON.stringify([owner.provider||'',owner.id,row.value.currency]);
    row.sourceAccountKey=key;
    if(!grouped.has(key))grouped.set(key,{key,owner,currency:row.value.currency});
   }
   const signature=JSON.stringify([...grouped.keys()].sort());
   const previous=new Map(sourcePlans.map(plan=>[plan.key,plan]));
   sourcePlans=await Promise.all([...grouped.values()].map(async (plan,index)=>{
    const id=await statementID(JSON.stringify([user,workspace,'uladim-statement-owner-account-v1',plan.key]));
    const existing=confirmedSourceAccount(id,plan.currency);
    const suffix=plan.owner.id.length>4?plan.owner.id.slice(-4):'';
    return {...plan,id,name:sourceCopy[13]+' '+(index+1)+' •••• '+suffix,
     targetID:previous.get(plan.key)?.targetID||(existing?id:'')};
   }));
   ensureContext();
   if(signature!==sourceSignature){sourceApplied=false;sourceMode='separate';}
   sourceSignature=signature;drawSourceAccounts();
  }
  function drawSourceAccounts(){
   sourceGroup.hidden=stage===2||!sourcePlans.length;
   need.hidden=accounts.length>0||!!sourcePlans.length;
   account.hidden=!accounts.length||!!sourcePlans.length;
   controls.querySelector('label[for="'+account.id+'"]').hidden=account.hidden;
   sourceStrategy.value=sourceMode;sourceRows.replaceChildren();
   const selected=combineAccount.value||account.value;
   const currencies=new Set(sourcePlans.map(plan=>plan.currency));
   combineAccount.replaceChildren(...accounts.filter(item=>currencies.size===1&&currencies.has(item.data.currency)).map(item=>{
    const option=E('option',item.data.name+' · '+item.data.currency);option.value=item.id;return option;
   }));
   if(accounts.some(item=>item.id===selected))combineAccount.value=selected;
   combineAccount.hidden=sourceMode!=='combine';
   sourceChoices.querySelector('label[for="'+combineAccount.id+'"]').hidden=combineAccount.hidden;
   let creating=0;
   for(const [index,plan] of sourcePlans.entries()){
    const line=E('div',undefined,'statement-source-row');
    const existing=accounts.find(item=>item.id===plan.targetID);
    const label=plan.name+' · '+plan.currency;
    if(sourceMode==='separate'){
     const choices=[['',sourceCopy[3]],...accounts.filter(item=>item.data.currency===plan.currency).map(item=>[item.id,item.data.name+' · '+item.data.currency])];
     const picker=select(line,'statement-source-'+index,label,choices,plan.targetID);
     picker.addEventListener('change',()=>{plan.targetID=picker.value;sourceApplied=false;invalidateSourceRows();drawSourceAccounts();});
     if(existing)line.append(E('span',sourceCopy[11],'small'));else creating++;
    }else line.append(E('p',label));
    sourceRows.append(line);
   }
   const mixed=new Set(sourcePlans.map(plan=>plan.currency)).size>1;
   sourceMessage.textContent=sourceMode==='combine'&&mixed?sourceCopy[7]:sourceCopy[6];
   sourceConfirm.textContent=accountPending?t('retry'):creating&&sourceMode==='separate'?sourceCopy[5]+' · '+creating:sourceCopy[4];
   sourceConfirm.hidden=sourceApplied;
   updateControls();
  }
  function invalidateSourceRows(){
   for(const row of preview){row.targetID='';row.selected=false;row.selectionPreference=null;}
   draw();
  }
  sourceStrategy.addEventListener('change',()=>{
   sourceMode=sourceStrategy.value;
   if(sourceMode==='separate')for(const plan of sourcePlans)plan.targetID=accounts.some(item=>item.id===plan.id&&item.data.currency===plan.currency)?plan.id:'';
   sourceApplied=false;invalidateSourceRows();drawSourceAccounts();
  });
  combineAccount.addEventListener('change',()=>{sourceApplied=false;invalidateSourceRows();drawSourceAccounts();});
  async function confirmSourceAccounts(){
   ensureContext();if(running||pending||!sourcePlans.length)return;
   running=true;updateControls();
   try{
    if(!accountPending){
     await refresh();ensureContext();accounts=records('account');
     if(sourceMode==='combine'){
      const currencies=new Set(sourcePlans.map(plan=>plan.currency));
      if(currencies.size!==1||!accounts.some(item=>item.id===combineAccount.value&&item.data.currency===[...currencies][0]))throw {code:'statement_account_currency'};
     }else{
      const child=currentSpace()?.role==='child';accountPending=[];
      for(const plan of sourcePlans){
       if(plan.targetID){if(!confirmedSourceAccount(plan.targetID,plan.currency))throw {code:'statement_account_conflict'};continue;}
       if(confirmedSourceAccount(plan.id,plan.currency))continue;
       accountPending.push({plan,operation:{id:crypto.randomUUID(),action:'record.put',record_id:plan.id,revision:0,kind:'account',
        visibility:child?'shared':'private',audience:child?[currentSpace().profile_id]:[],
        data:{name:plan.name,currency:plan.currency,opening_minor:0}}});
      }
     }
    }
    // Account operations are retained, including their IDs, until the complete
    // response is known. No transaction write can run before this finishes.
    while(accountPending?.length){
     const batch=accountPending.slice(0,100);
     const result=await call('sync',{workspace_id:workspace,operations:batch.map(item=>item.operation)});ensureContext();
     if(!Array.isArray(result.results)||result.results.length!==batch.length||result.results.some((item,index)=>item.id!==batch[index].operation.id))throw {code:'offline',uncertain:true};
     if(result.results.some(item=>item.status==='accepted'))modified=true;
     if(result.results.some(item=>!['accepted','conflict'].includes(item.status)&&item.error!=='revision_conflict')){
      accountPending=null;throw {code:'statement_account_rejected'};
     }
     modified=true;accountPending.splice(0,batch.length);
    }
    await refresh();ensureContext();accounts=records('account');
    for(const plan of sourcePlans){
     const target=sourceMode==='combine'?combineAccount.value:plan.targetID||plan.id;
     if(!confirmedSourceAccount(target,plan.currency))throw {code:'offline',uncertain:true};
     plan.targetID=target;
    }
    accountPending=null;sourceApplied=true;syncAccounts(account.value);
    await identify();drawSourceAccounts();draw();
   }catch(error){
    if(!error.uncertain)accountPending=null;
    sourceMessage.textContent=error.uncertain?sourceCopy[9]:error.code==='statement_account_currency'?sourceCopy[7]:sourceCopy[10];
    sourceConfirm.textContent=t('retry');
    if(['unauthorized','workspace_forbidden'].includes(error.code))report(error);
   }finally{running=false;updateControls();}
  }
  function showError(error){
   if(closed)return;
   status.textContent=error.code==='statement_account_conflict'?sourceCopy[10]:copy(error.code||'import_format');
   recognitionFields.replaceChildren();
   recognitionHelp.hidden=!['import_mapping_required','import_encoding_required','import_delimiter_ambiguous'].includes(error.code);
   recognitionMessage.textContent=copy(error.code==='import_mapping_required'?'recognition_help':error.code||'import_format');
   if(error.code==='import_mapping_required'&&parsed){
    // Ask only for unknown required fields. The full expert mapping remains folded.
    setStage(1);
    const required=['date'];
    if(fields.amountMode.value==='split'){
     if(Number(fields.debit.value)<0&&Number(fields.credit.value)<0)required.push('debit','credit');
    }else required.push('amount');
    if(fields.amountMode.value==='typed')required.push('directionColumn');
    for(const key of required){
     const field=fields[key];if(!field||Number(field.value)>=0)continue;
     const label=mappingKeys.find(([name])=>name===key)?.[1]||copy(key);
     const choices=[...field.options].map(option=>[option.value,option.textContent]);
     const picker=select(recognitionFields,'required-'+key,label,choices,field.value);
     for(const [index,option] of [...picker.options].entries())option.disabled=field.options[index].disabled;
     picker.addEventListener('change',()=>{field.value=picker.value;review();});
    }
   }
  }
  function ready(row){return !!row.value&&!row.error&&!row.imported&&!row.repeated&&!row.duplicate&&!!row.targetID&&!parsed?.needsReview;}
  function updateControls(){
   selectReady.disabled=running||!!pending||!!correcting||!preview.some(row=>ready(row)&&!row.selected);
   clearSelection.disabled=running||!!pending||!!correcting||!preview.some(row=>row.selected);
   controls.disabled=running||!!pending||!!correcting||!!accountPending;results.inert=running||!!pending||!!correcting||!!accountPending;commit.disabled=running||!!correcting||!!accountPending||(sourcePlans.length&&!sourceApplied)||!(pending||preview.some(row=>row.selected));
   sourceChoices.disabled=running||!!pending||!!correcting||!!accountPending;
   for(const field of sourceRows.querySelectorAll('select'))field.disabled=sourceChoices.disabled;
   sourceConfirm.disabled=running||!!pending||!!correcting||(sourceMode==='combine'&&(!combineAccount.value||new Set(sourcePlans.map(plan=>plan.currency)).size>1));
   const close=container.querySelector('.dialog-head button');if(close)close.disabled=running;
  }
  async function readFile(){
   if(pending||!source)return;
   const turn=++generation;
   setStage(0);attempted=[];
   clearCorrection();preview=[];parsed=null;sourcePlans=[];sourceSignature='';sourceApplied=false;sourceGroup.hidden=true;mapping.replaceChildren();dateHelp.replaceChildren();dateHelp.hidden=true;recognitionHelp.hidden=true;recognitionFields.replaceChildren();advanced.open=false;sheetControls.replaceChildren();results.replaceChildren();totals.replaceChildren();
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
    if(turn===generation)showError(error);
   }finally{if(turn===generation){running=false;updateControls();}}
  }
  function buildMapping(){
   const detected=parsed.detection;
   fields.header=select(mapping,'header',t('header_row'),parsed.rows.slice(0,20).map((r,i)=>[i,(i+1)+' · '+r.join(' / ').slice(0,100)]),detected.header);
   fields.amountMode=select(mapping,'amountMode',copy('amount_mode'),[['signed',copy('amount_signed')],['split',copy('amount_split')],['typed',copy('amount_typed')]],
    detected.credit>=0||detected.debit>=0?'split':detected.directionColumn>=0&&parsed.rows.slice(detected.header+1).some(row=>(row[detected.directionColumn]||'').trim())?'typed':'signed');
   const columns=()=>[[-1,copy('no_column')],...parsed.rows[Number(fields.header.value)].map((label,i)=>{
    const samples=parsed.rows.slice(Number(fields.header.value)+1,Number(fields.header.value)+4).map(row=>row[i]).filter(Boolean).slice(0,2);
    return [i,(i+1)+' · '+label.slice(0,40)+(samples.length?' · '+samples.map(value=>value.slice(0,24)).join(' / '):'')];
   })];
   for(const [key,label] of mappingKeys)fields[key]=select(mapping,key,label,columns(),detected[key]??-1);
   fields.header.addEventListener('change',()=>{
    for(const [key] of mappingKeys){
     fields[key].replaceChildren(...columns().map(([value,label])=>{const option=E('option',label);option.value=value;return option;}));
     fields[key].value='-1';
    }
   });
   dateHelp.replaceChildren(E('h3',copy('date_help_title')),E('p',copy('date_help_body')));
   fields.dateFormat=select(dateHelp,'dateFormat',t('date_format'),[['auto',copy('auto')],['iso','YYYY-MM-DD'],['dmy',copy('date_day_first')],['mdy',copy('date_month_first')],['excel',t('excel_date')]],detected.dateFormat);
   const dateExamples=E('p',undefined,'statement-date-examples');dateHelp.append(dateExamples);
   function showDateExample(){
    const sample=preview.find(row=>row.original?.date)?.original.date||parsed.rows[detected.header+1]?.[detected.date]||'';
    dateExamples.textContent=sample?copy('date_example')+' '+sample:'';
   }
   fields.dateFormat.addEventListener('change',showDateExample);showDateExample();
   // The same date-format control stays visible after the first choice so the user can correct it.
   dateHelp.dataset.needed='false';
   fields.decimal=select(mapping,'decimal',t('decimal_separator'),[['auto',copy('auto')],['.','1,234.56'],[',','1.234,56']],detected.decimal);
   fields.direction=select(mapping,'direction',t('amount_direction'),[['signed','+ '+t('income')+' / − '+t('expense')],['income',t('income')],['expense',t('expense')]],'signed');
   // The mode determines which amount fields apply; hidden alternatives never
   // override it. Shared recognition changes always rebuild the complete file.
   function updateMapping(){
    fields.direction.hidden=fields.amountMode.value!=='signed';mapping.querySelector('label[for="'+fields.direction.id+'"]').hidden=fields.direction.hidden;
    for(const [key] of mappingKeys){
     const field=fields[key],split=fields.amountMode.value==='split';
     const inactive=(key==='amount'&&split)||(['debit','credit'].includes(key)&&!split)||(key==='directionColumn'&&fields.amountMode.value!=='typed');
     field.hidden=inactive;mapping.querySelector('label[for="'+field.id+'"]').hidden=inactive;
     for(const option of field.options)option.disabled=!ULADIMStatement.columnCompatible(parsed,Number(option.value),key,Number(fields.header.value));
    }
   }
   updateMapping();
   for(const field of Object.values(fields))field.addEventListener('change',()=>{updateMapping();review();});
   mapping.append(button(copy('show_date_format'),()=>{dateHelp.hidden=false;dateHelp.dataset.needed='true';fields.dateFormat.focus();dateHelp.scrollIntoView({block:'center'});},'text-button'),E('p',copy('mapping_help'),'small'),button(copy('apply_mapping'),review,'secondary'));
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
   // Alternate UUIDs share a hashed bank/account prefix. This makes collisions
   // recognizable from synced records without storing the bank identifier.
   const knownGroups=new Set([...known.keys()].map(id=>id.slice(0,24)));
   for(const row of preview){
    if(!row.value)continue;
    const value=row.value;
    const sourcePlan=sourcePlans.find(plan=>plan.key===row.sourceAccountKey);
    const target=sourcePlans.length?(sourceApplied&&sourcePlan?accounts.find(a=>a.id===sourcePlan.targetID&&a.data.currency===value.currency):null):
     accounts.find(a=>a.id===row.targetID&&a.data.currency===value.currency)||destination(value.currency);
    row.targetID=target?.id||'';
    row.imported=false;row.repeated=false;row.duplicate=false;row.selected=false;row.id=null;row.bankGroup=null;
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
     let bankCollision=false;
     if(row.bankKey&&known.get(row.id)!==row.key){
      const group=(await statementID(JSON.stringify([user,workspace,'uladim-statement-bank-group-v1',row.bankKey]))).slice(0,24);
      row.bankGroup=group;
      const suffix=(await statementID(JSON.stringify([user,workspace,'uladim-statement-bank-row-v1',row.bankKey,row.key]))).slice(24);
      const alternate=group+suffix;
      bankCollision=bankIDs.get(row.bankKey).size>1||known.has(row.id)||knownGroups.has(group);
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
   try{await prepareSourcePlans(Number(fields.header.value));await identify();draw();}finally{running=false;updateControls();}
  }
  async function buildPreview(){
   ensureContext();
   const numbers=['header',...mappingKeys.map(([key])=>key)];
   const settings=Object.fromEntries(Object.entries(fields).map(([key,field])=>[key,numbers.includes(key)?Number(field.value):field.value]));
   settings.defaultCurrency=defaultAccount()?.data.currency;
   preview=ULADIMStatement.preview(parsed,settings);
   await prepareSourcePlans(settings.header);
   await identify();page=0;setStage(1);draw();
   const dateProblem=preview.some(row=>row.error==='import_date_ambiguous');
   if(dateProblem)dateHelp.dataset.needed='true';
   dateHelp.hidden=dateHelp.dataset.needed!=='true';
   dateHelp.classList.toggle('is-resolved',!dateProblem);
   const example=preview.find(row=>row.original?.date),exampleText=dateHelp.querySelector('.statement-date-examples');
   if(exampleText&&example)exampleText.textContent=copy('date_example')+' '+example.original.date+(example.value?.date?' → '+example.value.date:'');
   // A parsed table with row validation errors does not need its structure remapped.
   recognitionHelp.hidden=true;recognitionFields.replaceChildren();
  }
  function rowStatus(row){
   if(row.saved)return copy('saved');
   if(row.error)return copy(row.error);
   if(row.imported)return t('already_imported');
   if(row.repeated)return copy('repeated_id');
   if(sourcePlans.length&&!sourceApplied)return sourceCopy[8];
   if(!row.targetID)return copy('missing_currency_account');
   if(row.duplicate)return t('import_duplicate');
   if(parsed.needsReview&&!row.selected)return copy('pdf_review');
   return copy('ready');
  }
  function summary(){
   totals.replaceChildren();
   const counts={selected:0,ready:0,duplicates:0,errors:0,skipped:0,review:0,saved:0};
   const byCurrency=new Map();
   for(const row of preview){
    if(ready(row))counts.ready++;
    if(row.duplicate||row.repeated)counts.duplicates++;
    if(row.error||(!row.targetID&&row.value))counts.errors++;
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
   if(!sourcePlans.length&&preview.some(row=>row.value&&!row.targetID))results.append(button(copy('create_account'),openAccount,'secondary'));
   const table=E('table');table.setAttribute('role','table');const head=E('thead'),header=E('tr');header.setAttribute('role','row');
   const columnLabels=[copy('include'),t('date'),t('description'),t('amount'),t('family_kind_transaction'),t('family_account_select'),copy('status')];
   for(const label of columnLabels){
    const th=E('th',label);th.scope='col';th.setAttribute('role','columnheader');header.append(th);
   }
   head.append(header);const body=E('tbody');table.append(head,body);
   for(const item of preview.slice(page*50,(page+1)*50)){
    const row=E('tr'),v=item.value,original=item.original;row.setAttribute('role','row');
    const cell=E('td'),check=E('input');check.type='checkbox';check.checked=!!item.selected;
    check.disabled=!!(item.error||item.imported||item.repeated||!item.targetID||pending);
    check.setAttribute('aria-label',copy('include')+' · '+item.line);
    check.addEventListener('change',()=>{item.selectionPreference={key:item.selectionKey,checked:check.checked};item.selected=check.checked;summary();updateControls();statusCell.firstChild.textContent=rowStatus(item);});
    cell.append(check);
    const statusCell=E('td');statusCell.append(E('span',rowStatus(item)));
    const accountCell=E('td');
    const matching=v?accounts.filter(a=>a.data.currency===v.currency):[];
    if(!sourcePlans.length&&matching.length>1&&!item.imported&&!pending){
     const choices=[['',t('family_none')],...matching.map(a=>[a.id,a.data.name])];
     const picker=select(accountCell,'row-account-'+item.line,t('family_account_select')+' · '+item.line,choices,item.targetID);
     picker.addEventListener('change',async()=>{item.targetID=picker.value;try{await reidentify();}catch(error){showError(error);}});
    }else accountCell.textContent=accounts.find(a=>a.id===item.targetID)?.data.name||'—';
    if(item.error&&!['import_transfer_review','import_save_conflict','import_save_rejected'].includes(item.error))statusCell.append(button(copy('edit_row'),()=>editRow(item),'secondary'));
    row.append(cell,E('td',v?.date||original.date||'—'),E('td',v?.label||original.label||'—'),
     E('td',v?money(v.amount,v.currency):original.amount||'—'),E('td',v?t(v.kind):'—'),accountCell,statusCell);
    for(const [i,td] of [...row.cells].entries()){
     td.setAttribute('role','cell');td.dataset.label=columnLabels[i];
    }
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
   correcting=item;correction.hidden=false;correction.replaceChildren(E('h3',copy('edit_row')+' · '+item.line));updateControls();
   const editor=form(correction,'',f=>{
    const original=item.original;
    return {date:input(f,'date',t('date'),'text',original.date),amount:input(f,'amount',t('amount'),'text',original.amount),
     currency:input(f,'currency',t('currency'),'text',original.currency),label:input(f,'label',t('description'),'text',original.label,false),
     direction:select(f,'direction',t('family_kind_transaction'),[['',copy('auto')],['income',t('income')],['expense',t('expense')]],item.value?.kind||original.kind||'')};
   },async v=>{
    ensureContext();if(correcting!==item||!preview.includes(item))throw {code:'view_changed'};
    const row=[v.date.value,v.amount.value,v.label.value,v.currency.value,item.original.bankID,v.direction.value];
    const single=ULADIMStatement.table([['Date','Amount','Description','Currency','Transaction ID','Direction'],row],'CSV');
    const normalized=ULADIMStatement.preview(single,{...single.detection,defaultCurrency:defaultAccount()?.data.currency})[0];
    if(!normalized?.value)throw {code:normalized?.error||'import_format'};
    Object.assign(item,{value:normalized.value,original:normalized.original,error:null});
    clearCorrection();await reidentify();
   });
   editor.append(button(t('close'),()=>{clearCorrection();updateControls();},'text-button'));
   const first=correction.querySelector('input');first?.focus({preventScroll:true});first?.scrollIntoView({block:'center'});
  }
  function clearCorrection(){correcting=null;correction.hidden=true;correction.replaceChildren();}
  async function commitRows(){
   ensureContext();if(running||accountPending||(sourcePlans.length&&!sourceApplied))return;
   running=true;updateControls();
   try{
    if(!pending){
     await refresh();ensureContext();
     const current=existingTransactions();
     const keys=new Set(current.values());
     const groups=new Set([...current.keys()].map(id=>id.slice(0,24)));
     const child=currentSpace()?.role==='child';
     pending=[];attempted=preview.filter(item=>item.selected);
     for(const row of attempted){
      if(current.has(row.id)){
       row.imported=current.get(row.id)===row.key;
       row.selected=false;
       if(!row.imported)row.error='import_save_conflict';
       continue;
      }
      if(!row.duplicate&&(keys.has(row.key)||groups.has(row.bankGroup))){
       row.duplicate=true;row.selected=false;row.selectionPreference=null;continue;
      }
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
     if(!Array.isArray(result.results)||result.results.length!==batch.length||
        result.results.some((item,index)=>item.id!==batch[index].operation.id))throw {code:'offline',uncertain:true};
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
    await refresh();ensureContext();
    const visible=existingTransactions();
    if(attempted.some(row=>row.saved&&visible.get(row.id)!==row.key))throw {code:'server_error',refreshOnly:true};
    const saved=attempted.filter(row=>row.saved).length;
    const failed=attempted.filter(row=>!row.saved&&!row.imported).length;
    pending=null;commit.textContent=t('import_confirm');
    receipt.replaceChildren(E('h3',resultStep),E('p',savedLabel+' · '+saved));
    if(failed)receipt.append(E('p',failedLabel+' · '+failed,'error'));
    const skipped=preview.length-saved-failed;
    if(skipped)receipt.append(E('p',skipped+' '+copy('skipped'),'small'));
    receipt.append(button(historyLabel,()=>{
     modified=false;d.close();openTabSection('money','#finance-ledger');
    }),button(reviewLabel,()=>{setStage(1);draw();},'text-button'));
    setStage(2);status.textContent=saved?copy(failed||preview.some(row=>row.error||(!row.targetID&&row.value))?'partially_finished':'finished'):'';receipt.focus();
   }catch(error){
    if(closed)return;
    if(error.code==='unauthorized'||error.code==='workspace_forbidden'){report(error);return;}
    if(pending&&(error.uncertain||error.refreshOnly||pending.length===0)){
     commit.textContent=t('retry');status.textContent=pending.length?errorText(error):refreshLabel;summary();
    }
    else{pending=null;commit.textContent=t('import_confirm');draw();status.textContent=errorText(error);}
   }finally{running=false;updateControls();}
  }
  file.addEventListener('change',()=>{if(file.files?.[0]){source=file.files[0];readFile();}});
  for(const field of [encoding,delimiter])field.addEventListener('change',readFile);
  account.addEventListener('change',()=>{for(const row of preview)row.targetID='';review();});
  dCleanup(()=>{
   const outstanding=!!pending?.length||!!accountPending?.length;
   closed=true;source=null;parsed=null;preview=[];pending=null;sourcePlans=[];accountPending=null;
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
  select_ready:'Выбрать все готовые',clear_selection:'Снять выбор',duplicates:'дубликатов',errors:'с ошибками',
  amount_mode:'Как задана сумма',amount_signed:'Одна сумма со знаком + / −',amount_split:'Отдельные столбцы дохода и расхода',amount_typed:'Сумма и тип операции',
  mapping_help:'Изменения применяются ко всем строкам. В названиях столбцов показаны примеры из файла.',apply_mapping:'Проверить все строки',
  import_direction_invalid:'Проверьте тип операции: доход или расход.',
  advanced_badge:'Для опытных',advanced_help:'Расширенные настройки файла. Обычно их менять не нужно: используйте их, только если выписка распознана неверно.',recognition_help:'Неизвестное название столбца. Выберите его по примерам ниже — один выбор применится ко всей выписке.',open_advanced:'Открыть расширенные настройки',date_help_title:'Уточните формат даты',date_help_body:'Выберите порядок дня и месяца. Настройка применится ко всей выписке.',date_day_first:'День → месяц (4 мая)',date_month_first:'Месяц → день (5 апреля)',date_example:'Пример из вашей выписки:',show_date_format:'Формат даты',advanced:'Исправить распознавание',auto:'Автоматически',bank_id:'Идентификатор операции',direction_field:'Тип операции',reading:'Распознаём выписку…',
  saved:'сохранено',skipped:'пропущено',selected:'выбрано',needs_review:'требуют проверки',ready:'Готово',rows:'строк',
  include:'Включить',status:'Статус',edit_row:'Исправить строку',no_rows:'В выписке нет операций для проверки.',
  partially_finished:'Сохранена только часть строк. Проверьте ошибки и пропущенные операции.',
  finished:'Импорт завершён. Сохранённые операции доступны в истории.',
  missing_currency_account:'Выберите или создайте счёт в валюте операции.',repeated_id:'Банковский идентификатор повторяется.',
  pdf_review:'Сверьте строку с PDF и отметьте её для импорта.',
  import_mapping_required:'Выберите нераспознанный столбец ниже. Остальные настройки уже определены.',
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
  import_currency_conflict:'В выписке указаны разные валюты. Проверьте, к какой валюте относится сумма.',
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
  select_ready:'Select all ready',clear_selection:'Clear selection',duplicates:'duplicates',errors:'with errors',
  amount_mode:'Amount format',amount_signed:'One signed amount + / −',amount_split:'Separate income and expense columns',amount_typed:'Amount and transaction type',
  mapping_help:'Changes apply to every row. Column choices include examples from the file.',apply_mapping:'Check all rows',
  import_direction_invalid:'Check the transaction type: income or expense.',
  advanced_badge:'Advanced',advanced_help:'Advanced file settings. Usually no changes are needed; use these only if the statement was read incorrectly.',recognition_help:'This column name is unfamiliar. Choose it using the examples below; your choice applies to the whole statement.',open_advanced:'Open advanced settings',date_help_title:'Confirm the date format',date_help_body:'Choose the day and month order once for the whole statement.',date_day_first:'Day first (4 May)',date_month_first:'Month first (5 April)',date_example:'Example from your statement:',show_date_format:'Date format',advanced:'Correct recognition',auto:'Automatic',bank_id:'Transaction ID',direction_field:'Transaction type',reading:'Reading statement…',
  saved:'saved',skipped:'skipped',selected:'selected',needs_review:'need review',ready:'Ready',rows:'rows',
  include:'Include',status:'Status',edit_row:'Correct row',no_rows:'There are no transactions to review in this statement.',
  partially_finished:'Only part of the statement was saved. Review errors and skipped transactions.',
  finished:'Import finished. Saved transactions are available in history.',
  missing_currency_account:'Choose or create an account in the transaction currency.',repeated_id:'The bank transaction ID appears more than once.',
  pdf_review:'Compare this row with the PDF, then select it for import.',
  import_mapping_required:'Choose the unrecognized column below. The other settings are already detected.',
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
  import_currency_conflict:'The statement lists different currencies. Check which currency belongs to the amount.',
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
