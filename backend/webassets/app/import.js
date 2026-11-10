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
function statementKey(v,account){return JSON.stringify([account,v.kind,v.amount,v.currency,v.date,v.label.trim()]);}
async function statementID(value){const bytes=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(value));const hex=[...new Uint8Array(bytes)].map(b=>b.toString(16).padStart(2,'0')).join('');return hex.slice(0,8)+'-'+hex.slice(8,12)+'-5'+hex.slice(13,16)+'-a'+hex.slice(17,20)+'-'+hex.slice(20,32);}
function importStatement(){
 let table=null,preview=[],page=0,pending=null,position=0,running=false,closed=false,modified=false;
 const workspace=state.space,user=state.session.user_id,epoch=privateEpoch;
 const accounts=records('account');
 if(!accounts.length){editRecord('account');return;}
 const d=dialog(t('import_file'),container=>{
  container.classList.add('statement-dialog');
  const info=E('p',t('web_import_help'),'small');container.append(info);
  const controls=E('fieldset');container.append(controls);
  const account=select(controls,'import-account',t('family_account_select'),accounts.map(a=>[a.id,a.data.name+' · '+a.data.currency]),accounts[0].id);
  const file=input(controls,'statement-file',t('choose_file'),'file','',false);file.accept='.csv,.tsv,.txt,.json,.ofx,.qif';
  const advanced=E('details'),advancedTitle=E('summary',t('ux_import_advanced'));advanced.append(advancedTitle);controls.append(advanced);
  const encoding=select(advanced,'encoding',t('encoding'),[['auto',t('system')],['utf8','UTF-8'],['utf16','UTF-16'],['cp1251','Windows-1251']],'auto');
  const delimiter=select(advanced,'delimiter',t('web_delimiter'),[['auto',t('system')],[';', ';'],[',',','],['\t','Tab']],'auto');
  const mapping=E('div');controls.append(mapping);
  const status=E('p',undefined,'import-status');status.setAttribute('role','status');container.append(status);
  const results=E('div',undefined,'import-results');container.append(results);
  const actions=E('div',undefined,'actions');container.append(actions);
  const commit=E('button',t('import_confirm'));commit.type='button';commit.addEventListener('click',()=>commitRows().catch(report));commit.disabled=true;actions.append(commit);
  const currency=()=>accounts.find(a=>a.id===account.value).data.currency;
  const ensureContext=()=>{if(closed||privateEpoch!==epoch||state.space!==workspace||state.session?.user_id!==user)throw {code:'view_changed'};};
  let fields={};
  async function parseFile(){
   if(running||pending)return;table=null;preview=[];results.replaceChildren();mapping.replaceChildren();commit.disabled=true;const source=file.files?.[0];if(!source)return;
   if(source.size>5*1024*1024){status.textContent=t('import_limit');return;}
   const extension=source.name.split('.').pop().toLowerCase();if(!['csv','tsv','txt','json','ofx','qif'].includes(extension)){status.textContent=t('web_import_help');return;}
   running=true;controls.disabled=true;status.textContent=t('import_step_1');
   try{
    const bytes=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onerror=()=>reject({code:'import_format'});reader.onload=()=>resolve(String(reader.result).split(',')[1]);reader.readAsDataURL(source);});
    const value=await statementWorker({action:'parse',bytes,extension,encoding:encoding.value,delimiter:delimiter.value,currency:currency()});ensureContext();table=value.rows;
    const detected=value.detection||{header:0,date:-1,amount:-1,description:-1,currency:-1,dateFormat:'iso',decimal:'.'};
    fields.header=select(mapping,'header',t('header_row'),table.slice(0,20).map((row,i)=>[i,String(i+1)+' · '+row.join(' / ').slice(0,100)]),detected.header);
    const columns=table[detected.header].map((label,i)=>[i,String(i+1)+' · '+label.slice(0,60)]);
    for(const [key,label,optional] of [['date','date',false],['amount','amount',false],['description','description',true],['currency','currency',true]])fields[key]=select(mapping,key,t(label),[[-1,t('family_none')],...columns],detected[key]);
    fields.header.addEventListener('change',()=>{const choices=table[Number(fields.header.value)];for(const key of ['date','amount','description','currency']){const selected=fields[key].value;fields[key].replaceChildren();for(const [index,label]of [[-1,t('family_none')],...choices.map((label,i)=>[i,String(i+1)+' · '+label.slice(0,60)])]){const option=E('option',label);option.value=index;fields[key].append(option);}fields[key].value=Number(selected)<choices.length?selected:'-1';}});
    fields.dateFormat=select(mapping,'dateFormat',t('date_format'),[['iso','YYYY-MM-DD'],['dmy','DD.MM.YYYY'],['mdy','MM/DD/YYYY'],['excel',t('excel_date')]],detected.dateFormat);
    fields.decimal=select(mapping,'decimal',t('decimal_separator'),[['.','1,234.56'],[',','1.234,56']],detected.decimal);
    fields.direction=select(mapping,'direction',t('amount_direction'),[['signed','+ '+t('income')+' / − '+t('expense')],['income',t('income')],['expense',t('expense')]],'signed');
    mapping.append(button(t('import_preview'),review));status.textContent=t('import_step_1');
   }catch(error){if(!closed)status.textContent=errorText(error);}finally{running=false;controls.disabled=false;}
  }
  file.addEventListener('change',parseFile);
  for(const field of [encoding,delimiter])field.addEventListener('change',parseFile);
  account.addEventListener('change',()=>{preview=[];results.replaceChildren();commit.disabled=true;});
  mapping.addEventListener('change',()=>{preview=[];results.replaceChildren();commit.disabled=true;});
  async function review(){
   if(!table||running||pending)return;running=true;controls.disabled=true;commit.disabled=true;
   try{
    const m=Object.fromEntries(Object.entries(fields).map(([k,v])=>[k,['header','date','amount','description','currency'].includes(k)?Number(v.value):v.value]));
    m.defaultCurrency=currency();const result=await statementWorker({action:'normalize',rows:table,mapping:m});ensureContext();
    const existing=new Map();for(const r of records('transaction')){const key=statementKey({kind:r.data.kind,amount:r.data.amount_minor,currency:r.data.currency,date:r.data.date,label:r.data.label},r.data.account_id);existing.set(key,(existing.get(key)||0)+1);}
    const occurrence=new Map();preview=[];
    for(let i=0;i<result.preview.length;i++){
     const item=result.preview[i];if(item.error){preview.push({...item,index:i,selected:false});continue;}
     const v=item.value,key=statementKey(v,account.value),n=occurrence.get(key)||0;occurrence.set(key,n+1);
     const id=await statementID(JSON.stringify(['uladim-statement-v1',user,workspace,key,n]));
     const imported=state.records.some(r=>r.id===id),duplicate=n<(existing.get(key)||0)||n>0;
     preview.push({...item,index:i,id,imported,duplicate,selected:!imported&&!duplicate&&v.currency===currency(),mismatch:v.currency!==currency()});
    }
    page=0;draw();
   }catch(error){status.textContent=errorText(error);}finally{running=false;controls.disabled=false;}
  }
  function draw(){
   results.replaceChildren();status.textContent=t('import_step_2')+' · '+preview.filter(r=>r.selected).length+' / '+preview.length;
   const tableEl=E('table');const head=E('thead'),tr=E('tr');for(const key of ['import_confirm','date','description','amount','family_kind_transaction'])tr.append(E('th',t(key)));head.append(tr);tableEl.append(head);const body=E('tbody');tableEl.append(body);
   for(const item of preview.slice(page*100,(page+1)*100)){
    const row=E('tr');body.append(row);const cell=E('td');row.append(cell);const check=E('input');check.type='checkbox';check.checked=item.selected;check.disabled=!!(item.error||item.imported||item.mismatch||pending);check.setAttribute('aria-label',t('import_confirm')+' · '+(item.index+1));cell.append(check);
    check.addEventListener('change',()=>{item.selected=check.checked;status.textContent=t('import_step_2')+' · '+preview.filter(r=>r.selected).length+' / '+preview.length;commit.disabled=!preview.some(r=>r.selected);});
    if(item.error){const reason=E('td',t(item.error));reason.colSpan=4;row.append(reason);continue;}
    const v=item.value;row.append(E('td',v.date),E('td',v.label),E('td',money(v.amount,v.currency)),E('td',t(v.kind)));
    if(item.imported||item.duplicate||item.mismatch){const note=E('p',t(item.imported?'already_imported':item.mismatch?'family_error_currency_mismatch':'import_duplicate'),'small');row.children[2].append(note);}
   }
   const scroll=E('div',undefined,'import-table');scroll.tabIndex=0;scroll.setAttribute('role','region');scroll.setAttribute('aria-label',t('import_preview'));scroll.append(tableEl);results.append(scroll);
   const pages=E('div',undefined,'actions');const prev=button('←',()=>{page--;draw();}),next=button('→',()=>{page++;draw();});prev.setAttribute('aria-label',t('web_previous'));next.setAttribute('aria-label',t('web_next'));prev.disabled=page===0;next.disabled=(page+1)*100>=preview.length;pages.append(prev,E('span',(page+1)+' / '+Math.ceil(preview.length/100)),next);results.append(pages);
   commit.disabled=!preview.some(r=>r.selected);
  }
  async function commitRows(){
   ensureContext();if(running)return;running=true;controls.disabled=true;commit.disabled=true;
   try{
    if(!pending){await refresh();ensureContext();pending=preview.filter(r=>r.selected).map(row=>({row,operation:{id:crypto.randomUUID(),action:'record.put',record_id:row.id,revision:0,kind:'transaction',visibility:currentSpace()?.role==='child'?'shared':'private',audience:currentSpace()?.role==='child'?[currentSpace().profile_id]:[],data:{kind:row.value.kind,amount_minor:row.value.amount,currency:row.value.currency,date:row.value.date,label:row.value.label,account_id:account.value}}}));position=0;}
    // Reuse exactly the same operation and record IDs after a lost response.
    while(position<pending.length){ensureContext();const batch=pending.slice(position,position+100);
     const result=await call('sync',{workspace_id:workspace,operations:batch.map(item=>item.operation)});ensureContext();
     let failure=null;result.results.forEach((item,i)=>{const row=batch[i].row;if(item.status==='accepted'){row.accepted=true;row.selected=false;row.imported=true;modified=true;}else failure=failure||{code:item.error||'conflict'};});
     while(position<pending.length&&pending[position].row.accepted)position++;status.textContent=t('import_batch')+' · '+pending.filter(item=>item.row.accepted).length+' / '+pending.length;if(failure)throw failure;
    }
    pending=null;await refresh();ensureContext();draw();status.textContent=t('account_done')+' · '+position;commit.disabled=true;
   }catch(error){status.textContent=t('import_batch')+' · '+(pending?.filter(item=>item.row.accepted).length||0)+' / '+(pending?.length||0)+' · '+errorText(error);commit.textContent=t('retry');}
   finally{running=false;controls.disabled=!!pending;commit.disabled=pending?false:!preview.some(r=>r.selected);}
  }
 });
 d.addEventListener('cancel',event=>{if(running)event.preventDefault();});
 d.addEventListener('close',()=>{const outstanding=!!pending;closed=true;table=null;preview=[];pending=null;if(privateEpoch!==epoch||state.space!==workspace)return;if(outstanding)refresh().then(()=>{if(privateEpoch===epoch)render();}).catch(report);else if(modified)render();});
}
