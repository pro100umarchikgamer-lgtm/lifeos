'use strict';
// Only existing wrapper nodes move. Record payloads and edit permissions are
// untouched; the authenticated caller owns loading/saving this personal order.
(() => {
 const COPY=globalThis.UladimI18n.copy("grp_f5a258375dd8",{
  ru:['Порядок','Готово','↑ Выше','↓ Ниже','Поднять','Опустить','Счёт','Бюджет','Сохраняем порядок…','Порядок сохранён.','Не удалось сохранить порядок. Повторите.','Позиция'],
  en:['Order','Done','↑ Up','↓ Down','Move up','Move down','Account','Budget','Saving order…','Order saved.','Could not save the order. Try again.','Position'],
  'uz-Latn':['Tartib','Tayyor','↑ Yuqoriga','↓ Pastga','Yuqoriga ko‘chirish','Pastga ko‘chirish','Hisob','Budjet','Tartib saqlanmoqda…','Tartib saqlandi.','Tartibni saqlab bo‘lmadi. Qayta urinib ko‘ring.','O‘rin'],
  'uz-Cyrl':['Тартиб','Тайёр','↑ Юқорига','↓ Пастга','Юқорига кўчириш','Пастга кўчириш','Ҳисоб','Бюджет','Тартиб сақланмоқда…','Тартиб сақланди.','Тартибни сақлаб бўлмади. Қайта уриниб кўринг.','Ўрин']
 });
 function orderRecords(records,ids=[]){
  const ranks=new Map();
  for(const id of Array.isArray(ids)?ids:[])if(typeof id==='string'&&!ranks.has(id))ranks.set(id,ranks.size);
  return records.map((record,index)=>({record,index})).sort((a,b)=>
   (ranks.get(a.record.id)??Infinity)-(ranks.get(b.record.id)??Infinity)||a.index-b.index).map(item=>item.record);
 }
 function mountOrderControls({container,items,kind,order=[],onSave,E,lang='ru'}){
  const copy=COPY[lang]||COPY.en;
  const [orderLabel,doneLabel,upLabel,downLabel,moveUp,moveDown,account,budget,saving,saved,failed,position]=copy;
  const noun=kind==='budget'?budget:account;
  let ids=orderRecords(items,order).map(item=>item.id),active=false,pending=false,destroyed=false;
  const byID=new Map(items.map(item=>[item.id,item]));
  const toolbar=E('div',undefined,'actions layout-order-toolbar');toolbar.style.gridColumn='1 / -1';
  const toggle=E('button',orderLabel,'secondary layout-order-toggle');toggle.type='button';toggle.setAttribute('aria-pressed','false');
  const status=E('span',undefined,'small layout-order-status');status.setAttribute('role','status');
  toolbar.append(toggle,status);container.prepend(toolbar);
  const groups=new Map();
  for(const item of items){
   const controls=E('div',undefined,'actions layout-order-controls');controls.style.gridColumn='1 / -1';
   controls.setAttribute('role','group');controls.setAttribute('aria-label',orderLabel+' · '+noun+' · '+item.label);
   const up=E('button',upLabel,'secondary'),down=E('button',downLabel,'secondary');
   up.type=down.type='button';
   up.setAttribute('aria-label',moveUp+' · '+noun+' · '+item.label);
   down.setAttribute('aria-label',moveDown+' · '+noun+' · '+item.label);
   up.addEventListener('click',event=>{event.stopPropagation();move(item.id,-1,up);});
   down.addEventListener('click',event=>{event.stopPropagation();move(item.id,1,down);});
   controls.append(up,down);item.element.append(controls);groups.set(item.id,{controls,up,down});
  }
  function draw(){
   toggle.disabled=pending;toggle.textContent=active?doneLabel:orderLabel;toggle.setAttribute('aria-pressed',String(active));
   toolbar.hidden=items.length<2;
   for(const [index,id] of ids.entries()){
    const group=groups.get(id);
    group.controls.hidden=!active;group.controls.style.display=active?'flex':'none';
    group.up.disabled=pending||index===0;group.down.disabled=pending||index===ids.length-1;
   }
  }
  function place(){for(const id of ids)container.append(byID.get(id).element);}
  async function move(id,direction,source){
   if(!active||pending||destroyed)return;
   const from=ids.indexOf(id),to=from+direction;
   if(from<0||to<0||to>=ids.length)return;
   const candidate=ids.slice();[candidate[from],candidate[to]]=[candidate[to],candidate[from]];
   pending=true;status.textContent=saving;draw();
   try{
    await onSave(candidate.slice());
    if(destroyed)return;
    ids=candidate;place();
    status.textContent=saved+' '+byID.get(id).label+' · '+position+' '+(to+1)+' / '+ids.length;
   }catch{
    if(!destroyed)status.textContent=failed;
   }finally{
    if(!destroyed){pending=false;draw();if(source.isConnected)(source.disabled?toggle:source).focus({preventScroll:true});}
   }
  }
  toggle.addEventListener('click',()=>{if(pending||destroyed)return;active=!active;status.textContent='';draw();});
  place();draw();
  return {getOrder:()=>ids.slice(),destroy(){
   destroyed=true;toolbar.remove();for(const group of groups.values())group.controls.remove();
  }};
 }
 globalThis.UladimLayoutOrder=Object.freeze({orderRecords,mountOrderControls});
})();
