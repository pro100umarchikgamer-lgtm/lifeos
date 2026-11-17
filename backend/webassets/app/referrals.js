'use strict';
// Customer rendering deliberately consumes only counts and opted-in short names.
(function(root){
 const KEY='uladim-pending-invitation',CODE=/^[A-Za-z0-9_-]{43}$/;
 const copies=globalThis.UladimI18n.copy("grp_7d5054fbbe9b",{
  ru:{title:'Пригласить друзей',intro:'Поделитесь ULADIM с теми, кому он может пригодиться.',count:'Присоединились по вашему приглашению',link:'Ваша ссылка',create:'Создать ссылку',copy:'Скопировать',copied:'Ссылка скопирована.',selected:'Ссылка выделена. Скопируйте её.',people:'Приглашённые друзья',empty:'Пока никто не присоединился.',more:'Показать ещё',member:'Участник',loading:'Загружаем приглашения…',error:'Не удалось загрузить приглашения. Попробуйте ещё раз.',retry:'Повторить',verify:'Подтвердите почту, чтобы пользоваться приглашениями.',aliasTitle:'Как вас видит пригласивший',aliasHint:'Можно указать имя и первую букву фамилии, например «Умар U.». Контакты, активность и покупки ему недоступны.',first:'Имя',initial:'Первая буква фамилии',save:'Показывать это имя',hide:'Не показывать имя',saved:'Имя сохранено.',pending:'Вас пригласили в ULADIM',pendingHint:'После принятия приглашения друг увидит только выбранное вами короткое имя. Остальные данные аккаунта останутся закрыты.',accept:'Принять приглашение',decline:'Не сейчас',accepted:'Приглашение принято.',self:'Это ваша собственная ссылка.',claimed:'Для этого аккаунта уже принято другое приглашение.',invalid:'Ссылка приглашения недействительна.',failed:'Не удалось сохранить. Проверьте подключение и повторите.'},
  en:{title:'Invite friends',intro:'Share ULADIM with people who may find it useful.',count:'Joined through your invitation',link:'Your link',create:'Create invite link',copy:'Copy',copied:'Link copied.',selected:'Link selected. Copy it.',people:'Invited friends',empty:'No one has joined yet.',more:'Show more',member:'Member',loading:'Loading invitations…',error:'Could not load invitations. Try again.',retry:'Retry',verify:'Verify your email to use invitations.',aliasTitle:'Your name for the inviter',aliasHint:'You may share a first name and surname initial, such as “Umar U.” Your contacts, activity and purchases remain private.',first:'First name',initial:'Surname initial',save:'Show this name',hide:'Keep my name private',saved:'Name saved.',pending:'You have an invitation to ULADIM',pendingHint:'After you accept, your friend will see only the short name you choose. Your other account information stays private.',accept:'Accept invitation',decline:'Not now',accepted:'Invitation accepted.',self:'This is your own link.',claimed:'This account has already accepted another invitation.',invalid:'This invitation is not valid.',failed:'Could not save. Check your connection and retry.'}
 });
 function configureCopies(packs){
  const names={title:'title',intro:'intro',count:'count',link:'link',create:'create',copy:'copy',copied:'copied',people:'people',empty:'empty',more:'more',member:'member',loading:'loading',error:'load_error',retry:'retry',verify:'verify',aliasTitle:'alias_title',aliasHint:'alias_hint',first:'first',initial:'initial',save:'show_name',hide:'hide_name',saved:'name_saved',pending:'claim_title',pendingHint:'claim_hint',accept:'claim_action',accepted:'claim_done',self:'self',claimed:'already_attributed',invalid:'invalid_invitation',failed:'action_error'};
  for(const [lang,pack]of Object.entries(packs||{})){const next={...copies.en,...copies[lang]};for(const [key,name]of Object.entries(names)){const value=pack.strings?.['referrals_'+name];if(typeof value==='string'&&value)next[key]=value;}copies[lang]=next;}
 }
 function text(lang){return copies[lang]||copies.en;}
 function el(tag,value,cls){const n=document.createElement(tag);if(value!==undefined)n.textContent=value;if(cls)n.className=cls;return n;}
 function action(label,run,cls='secondary'){const b=el('button',label,cls);b.type='button';b.addEventListener('click',async()=>{b.disabled=true;try{await run();}finally{if(b.isConnected)b.disabled=false;}});return b;}
 function box(title){const c=el('section',undefined,'card referral-card');if(title)c.append(el('h2',title));return c;}
 function pending(){try{const x=JSON.parse(sessionStorage.getItem(KEY)||'null');if(CODE.test(x?.code||'')&&Number.isFinite(x.at)&&Date.now()-x.at<7*86400000&&x.at<=Date.now()+300000)return x.code;sessionStorage.removeItem(KEY);}catch{}return null;}
 function forget(){try{sessionStorage.removeItem(KEY);}catch{}}
 function captureInvite(){
  try{const url=new URL(location.href),values=url.searchParams.getAll('ref');if(!values.length)return;url.searchParams.delete('ref');history.replaceState(null,'',url.pathname+url.search+url.hash);if(values.length===1&&CODE.test(values[0]))sessionStorage.setItem(KEY,JSON.stringify({code:values[0],at:Date.now()}));}catch{}
 }
 function failure(error,c){return ({referral_self:c.self,referral_already_attributed:c.claimed,referral_invalid:c.invalid})[error?.code]||c.failed;}
 function invitation(container,{request,session,lang='ru',done=()=>{}}){
  const code=pending();if(!code||!session?.verified)return null;
  const c=text(lang),card=box(c.pending),status=el('p','','referral-status');status.setAttribute('role','status');
  card.classList.add('referral-pending');card.append(el('p',c.pendingHint));
  card.append(action(c.accept,async()=>{try{await request('referrals/claim',{code});forget();status.textContent=c.accepted;done();if(card.isConnected)card.remove();}catch(e){status.textContent=failure(e,c);}}),action(c.decline,()=>{forget();card.remove();}));card.append(status);container.append(card);return card;
 }
 async function customer(container,{request,session,lang='ru'}){
  const c=text(lang);container.classList.add('referral-section');container.replaceChildren();
  if(!session?.verified){container.append(el('p',c.verify));return;}
  invitation(container,{request,session,lang,done:()=>customer(container,{request,session,lang})});
  const loading=el('p',c.loading,'small');container.append(loading);
  let result;
  try{result=await request('referrals');}catch(e){if(container.isConnected){loading.textContent=c.error;container.append(action(c.retry,()=>customer(container,{request,session,lang})));}return;}
  if(!container.isConnected)return;loading.remove();
  const summary=box(c.title);summary.append(el('p',c.intro,'small'),el('p',c.count,'referral-count-label'),el('strong',Number(result.confirmed_count||0).toLocaleString(lang),'referral-count'));container.append(summary);
  const status=el('p','','referral-status');status.setAttribute('role','status');
  if(result.invite){
   const label=el('label',c.link),link=el('input');link.type='url';link.readOnly=true;link.value=result.invite.url;link.id='referral-link-'+crypto.randomUUID();label.htmlFor=link.id;
   summary.append(label,link,action(c.copy,async()=>{try{await navigator.clipboard.writeText(link.value);status.textContent=c.copied;}catch{link.focus();link.select();status.textContent=c.selected;}}));
  }else summary.append(action(c.create,async()=>{try{await request('referrals/code',{});await customer(container,{request,session,lang});}catch(e){status.textContent=failure(e,c);}}));
  summary.append(status);
  const friends=box(c.people),list=el('ul',undefined,'referral-people');friends.append(list);container.append(friends);
  const addPeople=people=>{for(const person of people||[]){const name=person.display_name==='Участник'?c.member:person.display_name;list.append(el('li',name));}};
  addPeople(result.people);if(!list.children.length)friends.append(el('p',c.empty,'small'));
  let offset=result.next_offset;
  if(offset!==null&&offset!==undefined){const more=action(c.more,async()=>{try{const next=await request('referrals?offset='+encodeURIComponent(offset));if(!container.isConnected)return;addPeople(next.people);offset=next.next_offset;if(offset===null)more.remove();}catch(e){status.textContent=c.error;}});friends.append(more);}
  const alias=box(c.aliasTitle),form=el('form'),firstLabel=el('label',c.first),initialLabel=el('label',c.initial),first=el('input'),initial=el('input');
  first.name='referral-first-name';first.maxLength=32;first.placeholder=lang==='ru'?'Умар':'Umar';initial.name='referral-surname-initial';initial.maxLength=2;initial.placeholder='U';
  first.id='referral-first-'+crypto.randomUUID();initial.id='referral-initial-'+crypto.randomUUID();firstLabel.htmlFor=first.id;initialLabel.htmlFor=initial.id;
  const save=el('button',c.save),message=el('p','','referral-status');save.type='submit';message.setAttribute('role','status');
  form.append(firstLabel,first,initialLabel,initial,save);alias.append(el('p',c.aliasHint,'small'),form,action(c.hide,async()=>{try{await request('referrals/alias',{first_name:'',surname_initial:''});first.value='';initial.value='';message.textContent=c.saved;}catch(e){message.textContent=c.failed;}}),message);container.append(alias);
  form.addEventListener('submit',async event=>{event.preventDefault();save.disabled=true;try{const value=await request('referrals/alias',{first_name:first.value.trim(),surname_initial:initial.value.trim()});message.textContent=c.saved+' '+(value.display_name==='Участник'?c.member:value.display_name);}catch(e){message.textContent=c.failed;}finally{save.disabled=false;}});
 }
 async function admin(container,{request,onUser=()=>{}}){
  container.classList.add('referral-section','referral-admin');container.replaceChildren(el('h2',globalThis.UladimI18n.text("literal_b0b0c93a7c1e",{},"Приглашения")));
  const filters=el('form',undefined,'referral-filters'),activity=el('select'),converted=el('select'),referrer=el('input');referrer.placeholder=globalThis.UladimI18n.text("literal_83baadd31cff",{},"ID пригласившего");referrer.setAttribute('aria-label',globalThis.UladimI18n.text("literal_83baadd31cff",{},"ID пригласившего"));activity.setAttribute('aria-label',globalThis.UladimI18n.text("literal_85f08e3bc2dd",{},"Активность"));converted.setAttribute('aria-label',globalThis.UladimI18n.text("literal_46d1c79ab062",{},"Покупка"));
  for(const [value,label]of [['',globalThis.UladimI18n.text("literal_6bf0706f8452",{},"Любая активность")],['active',globalThis.UladimI18n.text("literal_eeac62450940",{},"Активны за 30 дней")],['inactive',globalThis.UladimI18n.text("literal_ab27f70fa04d",{},"Без активности за 30 дней")]]){const o=el('option',label);o.value=value;activity.append(o);}
  for(const [value,label]of [['',globalThis.UladimI18n.text("literal_fae4bdc8cee3",{},"Все приглашённые")],['yes',globalThis.UladimI18n.text("literal_8536a1486760",{},"Есть подтверждение покупки")],['no',globalThis.UladimI18n.text("literal_e11a360f6492",{},"Без подтверждения покупки")]]){const o=el('option',label);o.value=value;converted.append(o);}
  const submit=el('button',globalThis.UladimI18n.text("literal_e15f960d93eb",{},"Применить"));submit.type='submit';filters.append(referrer,activity,converted,submit);container.append(filters);
  const results=el('section',undefined,'referral-results'),status=el('p','','referral-status');status.setAttribute('role','status');container.append(status,results);
  let next=null;
  const load=async(more=false)=>{
   submit.disabled=true;status.textContent=globalThis.UladimI18n.text("literal_fd96ae95bde0",{},"Загружаем приглашения…");
   try{
    const q=new URLSearchParams();if(referrer.value.trim())q.set('referrer',referrer.value.trim());if(activity.value)q.set('activity',activity.value);if(converted.value)q.set('converted',converted.value);if(more&&next)q.set('before',next);
    const value=await request('referrals'+(q.size?'?'+q:''));if(!container.isConnected)return;
    if(!more){results.replaceChildren();const totals=el('div',undefined,'referral-admin-counts');for(const [key,label]of [['confirmed',globalThis.UladimI18n.text("literal_5bbe71aea517",{},"Приглашены")],['active',globalThis.UladimI18n.text("literal_44b19be1a46a",{},"Активны")],['inactive',globalThis.UladimI18n.text("literal_3b756579f196",{},"Без активности")],['purchase_converted',globalThis.UladimI18n.text("literal_2153a4abdef0",{},"Подтверждения покупки")]]){const card=box(label);card.append(el('strong',Number(value.counts[key]||0).toLocaleString('ru-RU'),'referral-count'));totals.append(card);}results.append(totals,el('p',globalThis.UladimI18n.text("literal_66b3fdf5b917",{"arg0":(value.activity_window_days)},"Активность определяется по входам за последние {arg0} дней. Платные продажи и бонусы сейчас отключены."),'small'));if(value.purchase_conversion_available!==true)results.append(el('p',globalThis.UladimI18n.text("literal_4be7eecfce1c",{},"Подсчёт реальных оплат будет доступен после подключения подтверждений магазинов."),'small'));}
    let list=results.querySelector('.referral-edges');if(!list){list=el('div',undefined,'referral-edges');results.append(list);}
    for(const edge of value.edges||[]){const row=box(),pair=el('div',undefined,'referral-edge-people');pair.append(action(globalThis.UladimI18n.text("literal_4c3876db8620",{},"Пригласивший · ")+edge.referrer_id,()=>onUser(edge.referrer_id)),el('span','→'),action(globalThis.UladimI18n.text("literal_68bb072898c8",{},"Приглашённый · ")+edge.invitee_id,()=>onUser(edge.invitee_id)));row.append(pair,el('p',new Date(edge.confirmed_at*1000).toLocaleString('ru-RU'),'small'),el('p',(edge.activity==='active'?globalThis.UladimI18n.text("literal_a87a4b39c304",{},"Активен"):globalThis.UladimI18n.text("literal_3b756579f196",{},"Без активности"))+' · '+(edge.purchase_converted?globalThis.UladimI18n.text("literal_8536a1486760",{},"Есть подтверждение покупки"):globalThis.UladimI18n.text("literal_e11a360f6492",{},"Без подтверждения покупки")),'small'));list.append(row);}
    if(!list.children.length)list.append(el('p',globalThis.UladimI18n.text("literal_62700680a897",{},"Приглашений по этим условиям пока нет."),'small'));
    results.querySelector('.referral-more')?.remove();next=value.next_before;if(next){const button=action(globalThis.UladimI18n.text("literal_c6826c783794",{},"Показать ещё"),()=>load(true));button.classList.add('referral-more');results.append(button);}status.textContent='';
   }catch(e){status.textContent=e?.message||globalThis.UladimI18n.text("literal_255d42a275f5",{},"Не удалось загрузить статистику. Повторите попытку.");}finally{submit.disabled=false;}
  };
  filters.addEventListener('submit',event=>{event.preventDefault();load();});await load();
 }
 root.UladimReferrals={configureCopies,captureInvite,pending,forget,invitation,customer,admin};
})(globalThis);
