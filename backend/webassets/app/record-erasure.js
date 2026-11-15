'use strict';
// Only a current owner's explicit consent can request irreversible erasure.
// Neither record bodies nor operation receipts are persisted in the browser.
window.UladimRecordErasure = {
 attach(panel,{record,language,request,E,append,button,isCurrent,onErased}) {
  const copies=globalThis.UladimI18n.copy("grp_05f057598d55",{
   ru:{open:'Удалить навсегда',intro:'Запись будет удалена без возможности возврата.',review:'Проверить удаление',loading:'Проверяем запись…',consent:'Удалить именно эту запись навсегда',submit:'Удалить запись навсегда',retry:'Проверить и продолжить',cancel:'Отмена',done:'Запись удалена навсегда.',unavailable:'Удаление сейчас недоступно. Попробуйте позже.',linked:'Сначала удалите связанные операции из корзины.',stale:'Запись изменилась. Обновите корзину и проверьте её заново.',uncertain:'Удаление пока не подтверждено. Нажмите «Проверить и продолжить».',error:'Не удалось проверить удаление. Проверьте подключение и повторите.'},
   en:{open:'Delete permanently',intro:'This record will be deleted and cannot be restored.',review:'Review deletion',loading:'Checking the record…',consent:'Permanently delete this exact record',submit:'Delete record permanently',retry:'Check and continue',cancel:'Cancel',done:'Record permanently deleted.',unavailable:'Deletion is unavailable right now. Try again later.',linked:'First permanently delete the linked transactions from Trash.',stale:'The record changed. Refresh Trash and review it again.',uncertain:'Deletion is not confirmed yet. Choose “Check and continue”.',error:'Could not check deletion. Check your connection and try again.'},
   'uz-Latn':{open:'Butunlay o‘chirish',intro:'Yozuv butunlay o‘chiriladi va uni tiklab bo‘lmaydi.',review:'O‘chirishni tekshirish',loading:'Yozuv tekshirilmoqda…',consent:'Aynan shu yozuvni butunlay o‘chirish',submit:'Yozuvni butunlay o‘chirish',retry:'Tekshirish va davom etish',cancel:'Bekor qilish',done:'Yozuv butunlay o‘chirildi.',unavailable:'Hozir o‘chirish imkoni yo‘q. Keyinroq urinib ko‘ring.',linked:'Avval bog‘liq operatsiyalarni savatdan butunlay o‘chiring.',stale:'Yozuv o‘zgardi. Savatni yangilang va uni qayta tekshiring.',uncertain:'O‘chirish hali tasdiqlanmadi. «Tekshirish va davom etish»ni bosing.',error:'O‘chirishni tekshirib bo‘lmadi. Ulanishni tekshirib, qayta urinib ko‘ring.'},
   'uz-Cyrl':{open:'Бутунлай ўчириш',intro:'Ёзув бутунлай ўчирилади ва уни тиклаб бўлмайди.',review:'Ўчиришни текшириш',loading:'Ёзув текширилмоқда…',consent:'Айнан шу ёзувни бутунлай ўчириш',submit:'Ёзувни бутунлай ўчириш',retry:'Текшириш ва давом этиш',cancel:'Бекор қилиш',done:'Ёзув бутунлай ўчирилди.',unavailable:'Ҳозир ўчириш имкони йўқ. Кейинроқ уриниб кўринг.',linked:'Аввал боғлиқ операцияларни саватдан бутунлай ўчиринг.',stale:'Ёзув ўзгарди. Саватни янгиланг ва уни қайта текширинг.',uncertain:'Ўчириш ҳали тасдиқланмади. «Текшириш ва давом этиш»ни босинг.',error:'Ўчиришни текшириб бўлмади. Уланишни текшириб, қайта уриниб кўринг.'}
  });
  const copy=()=>copies[language()]||copies.en;
  const details=E('details',undefined,'record-erasure'),summary=E('summary',copy().open),body=E('div',undefined,'record-erasure-body');
  append(details,summary,body);panel.append(details);
  let busy=false,prepared=null,operation=null,uncertain=false,finished=false;
  const valid=()=>!finished&&isCurrent()&&details.isConnected;
  function problem(error){
   const c=copy();
   if(error?.code==='record_erasure_linked')return c.linked;
   if(['not_found','record_erasure_stale','record_forbidden','workspace_forbidden','verify_email','service_restricted'].includes(error?.code))return c.stale;
   if(error?.code==='record_erasure_unavailable')return uncertain?c.uncertain:c.unavailable;
   return uncertain?c.uncertain:c.error;
  }
  async function complete(){
   finished=true;details.open=true;body.replaceChildren(E('p',copy().done));
   summary.textContent=copy().done;
   await onErased?.(record.id,copy().done);
  }
  function idle(message=''){
   body.replaceChildren(E('p',copy().intro));
   if(message){const note=E('p',message,'record-erasure-status');note.setAttribute('role','status');body.append(note);}
   body.append(button(uncertain?copy().retry:copy().review,review,'secondary'));
  }
  function consent(){
   body.replaceChildren(E('p',copy().intro));
   const form=E('form'),label=E('label',undefined,'record-erasure-consent'),check=E('input');check.type='checkbox';
   append(label,check,E('span',copy().consent));
   const submit=E('button',copy().submit,'danger'),cancel=button(copy().cancel,()=>{prepared=null;check.checked=false;details.open=false;idle();},'text-button');
   submit.type='submit';submit.disabled=true;
   check.addEventListener('change',()=>{submit.disabled=!check.checked||busy;});
   append(form,label,submit,cancel);body.append(form);
   form.addEventListener('submit',async event=>{
    event.preventDefault();if(!valid()||busy||!check.checked||!prepared)return;
    busy=true;form.inert=true;submit.disabled=true;
    if(!operation)operation=prepared.pending_operation_id||crypto.randomUUID();
    try{
     const result=await request('recovery/purge',{operation_id:operation,record_id:record.id,revision:prepared.record.revision,consent_hash:prepared.record.consent_hash});
     if(!valid())return;
     if(result?.id!==operation||result?.record_id!==record.id||result?.status!=='accepted'||result?.erased!==true)throw {code:'server_error'};
     await complete();
    }catch(error){if(valid()){uncertain=true;idle(problem(error));}}
    finally{busy=false;}
   });
  }
  async function review(){
   if(!valid()||busy)return;busy=true;
   body.replaceChildren(E('p',copy().loading));body.setAttribute('aria-busy','true');
   try{
    const result=await request('recovery/purge-preview?record='+encodeURIComponent(record.id));
    if(!valid())return;
    if(result?.erased===true&&result.record_id===record.id){await complete();return;}
    if(result?.record?.id!==record.id||result.record.owner_id!==record.owner_id||result.record.workspace_id!==record.workspace_id||(result.record.deleted!==true&&result.record.deleted!==1)||result.record.revision!==record.revision||result.record.consent_hash!==record.consent_hash||!Number.isSafeInteger(result.record.revision)||typeof result.record.consent_hash!=='string'||!/^[a-f0-9]{64}$/.test(result.record.consent_hash))throw {code:'record_erasure_stale'};
    if(result.permanent_delete_available!==true){idle(uncertain?copy().uncertain:copy().unavailable);return;}
    if(result.pending_operation_id!==null&&result.pending_operation_id!==undefined&&!/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/i.test(result.pending_operation_id))throw {code:'server_error'};
    if(operation&&result.pending_operation_id&&operation!==result.pending_operation_id)throw {code:'record_erasure_stale'};
    prepared=result;consent();
   }catch(error){if(valid())idle(problem(error));}
   finally{busy=false;body.removeAttribute('aria-busy');}
  }
  idle();
  return {clear(){finished=true;prepared=null;operation=null;details.remove();}};
 }
};
