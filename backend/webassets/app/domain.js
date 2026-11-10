'use strict';
// Pure view logic. No persistence, credentials or alternative API contracts.
(function () {
 const dayMs=86400000;
 const civil=d=>d.toISOString().slice(0,10);
 function zonedParts(at,zone){return Object.fromEntries(new Intl.DateTimeFormat('en-CA',{timeZone:zone,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'}).formatToParts(at).filter(p=>p.type!=='literal').map(p=>[p.type,p.value]));}
 function wallTime(text,zone){
  const target=Date.parse(text+'Z');if(!Number.isFinite(target))throw new Error('invalid_schedule');
  let at=target;
  for(let i=0;i<4;i++){const p=zonedParts(new Date(at),zone),actual=Date.parse(`${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}:${p.second}Z`),delta=target-actual;if(!delta)return at;at+=delta;}
  // Nonexistent DST wall times advance to the first corresponding later time,
  // matching Android's calendar convention. Repeated times use the earlier instant.
  const candidates=[at,at-3600000,at+3600000].filter(n=>{const p=zonedParts(new Date(n),zone);return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`===text.slice(0,16);});
  return candidates.length?Math.min(...candidates):Math.max(at,at+3600000);
 }
 function occurrences(events,from,to,viewer=Intl.DateTimeFormat().resolvedOptions().timeZone){
  const result=[],lower=Date.parse(from+'T00:00:00Z'),upper=Date.parse(to+'T00:00:00Z');
  if(!Number.isFinite(lower)||!Number.isFinite(upper)||upper<=lower)throw new Error('invalid_date');
  for(const record of events){
   const s=record.data.schedule,base=new Date(s.localStart+'Z');
   if(!Number.isFinite(+base)||!['none','daily','weekly','monthly','yearly'].includes(s.repeat)||!Number.isInteger(s.interval)||s.interval<1)throw new Error('invalid_schedule');
   const zone=s.timezone==='device'?viewer:s.timezone;
   // Start near the requested view, never materialize years of occurrences.
   const days=Math.floor((lower-base)/dayMs),months=(new Date(lower).getUTCFullYear()-base.getUTCFullYear())*12+new Date(lower).getUTCMonth()-base.getUTCMonth();
   let start=s.repeat==='none'?0:s.repeat==='monthly'?Math.floor(months/s.interval)-2:s.repeat==='yearly'?Math.floor(months/(12*s.interval))-2:Math.floor(days/(s.interval*(s.repeat==='weekly'?7:1)))-2;
   start=Math.max(0,start);
   for(let n=start;n<start+5005;n++){
    let date=new Date(base);
    if(['daily','weekly'].includes(s.repeat))date.setUTCDate(base.getUTCDate()+n*s.interval*(s.repeat==='weekly'?7:1));
    if(['monthly','yearly'].includes(s.repeat)){date.setUTCDate(1);date.setUTCMonth(base.getUTCMonth()+n*s.interval*(s.repeat==='yearly'?12:1));date.setUTCDate(Math.min(base.getUTCDate(),new Date(Date.UTC(date.getUTCFullYear(),date.getUTCMonth()+1,0)).getUTCDate()));}
    const local=civil(date);if(+date>upper+2*dayMs||(s.until&&local>s.until))break;
    const stamp=local+s.localStart.slice(10),at=wallTime(stamp,zone),p=zonedParts(new Date(at),viewer),day=s.allDay?local:`${p.year}-${p.month}-${p.day}`;
    if(day>=from&&day<to)result.push({record,day,at,allDay:s.allDay,time:`${p.hour}:${p.minute}`,zone});
    if(s.repeat==='none')break;
   }
  }
  return result.sort((a,b)=>a.day.localeCompare(b.day)||Number(b.allDay)-Number(a.allDay)||a.at-b.at);
 }
 function validateFinance(kind,data,accounts){
  const fail=code=>{throw Object.assign(new Error(code),{code});},get=id=>accounts.find(a=>a.id===id);
  if(kind==='transaction'&&data.account_id&&get(data.account_id)?.data.currency!==data.currency)fail('currency_mismatch');
  if(kind==='transfer'){
   const a=get(data.from_id),b=get(data.to_id);if(!a||!b||a.id===b.id)fail('invalid_reference');
   if(a.data.currency===b.data.currency&&data.sent_minor!==data.received_minor)fail('currency_mismatch');
  }
  if(kind==='budget'&&data.period==='custom'&&(!data.end_on||data.end_on<data.start_on))fail('invalid_date');
 }
 globalThis.ULADIMDomain=Object.freeze({occurrences,wallTime,validateFinance,tasks:(rows,query='',status='all')=>rows.filter(r=>(status==='all'||Boolean(r.data.completed)===(status==='done'))&&r.data.title.toLocaleLowerCase().includes(query.toLocaleLowerCase()))});
})();
