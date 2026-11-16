'use strict';
// One app-owned menu, with a native value carrier for existing forms and APIs.
(() => {
 let opened=null;
 const el=(tag,classes)=>{const node=document.createElement(tag);if(classes)node.className=classes;return node;};
 const dismiss=()=>opened?.close();
 document.addEventListener('pointerdown',event=>{if(opened&&!opened.wrapper.contains(event.target))dismiss();},true);
 document.addEventListener('close',dismiss,true);
 document.addEventListener('keydown',event=>{if(event.key==='Escape'&&opened){event.preventDefault();event.stopPropagation();opened.close(true);}},true);
 window.addEventListener('resize',dismiss);
 window.addEventListener('pagehide',dismiss);
 document.addEventListener('scroll',event=>{if(opened&&!opened.list.contains(event.target))opened.position();},true);
 new MutationObserver(()=>{if(opened&&!opened.wrapper.isConnected)dismiss();}).observe(document.documentElement,{childList:true,subtree:true});
 function enhance(select,label=''){
  if(select.choiceField)return select.choiceField;
  const labels=[...select.labels||[]],wrapper=el('div','cw-choice field-menu'),trigger=el('button','secondary cw-choice-trigger field-menu-trigger'),list=el('div','cw-choice-list field-menu-list');
  const id='field-menu-'+crypto.randomUUID();trigger.type='button';trigger.id=id+'-trigger';trigger.setAttribute('aria-label',label||select.getAttribute('aria-label')||select.name);trigger.setAttribute('aria-haspopup','listbox');trigger.setAttribute('aria-controls',id);trigger.setAttribute('aria-expanded','false');
  list.id=id;list.setAttribute('role','listbox');list.setAttribute('aria-label',trigger.getAttribute('aria-label'));list.tabIndex=-1;list.hidden=true;
  select.hidden=false;select.classList.add('field-menu-carrier');select.tabIndex=-1;select.setAttribute('aria-hidden','true');select.removeAttribute('aria-label');
  select.parentNode?.insertBefore(wrapper,select);wrapper.append(select,trigger,list);select.choiceField=wrapper;
  for(const caption of labels)caption.htmlFor=trigger.id;
  let index=-1,typeahead='',typeTimer;
  const options=()=>[...select.options].filter(option=>!option.disabled&&!option.parentElement?.disabled);
  const blocked=()=>select.matches(':disabled')||Boolean(select.closest('[inert]'));
  function close(focus=false){
   if(opened?.wrapper===wrapper)opened=null;
   try{if(list.matches(':popover-open'))list.hidePopover();}catch{}
   list.hidden=true;wrapper.removeAttribute('data-open');trigger.setAttribute('aria-expanded','false');clearTimeout(typeTimer);typeahead='';
   if(focus&&trigger.isConnected&&!blocked())trigger.focus({preventScroll:true});
  }
  function refresh(){
   trigger.textContent=select.selectedOptions[0]?.textContent||label;trigger.disabled=blocked();
   const invalid=select.getAttribute('aria-invalid');if(invalid)trigger.setAttribute('aria-invalid',invalid);else trigger.removeAttribute('aria-invalid');
   const description=select.getAttribute('aria-describedby');if(description)trigger.setAttribute('aria-describedby',description);else trigger.removeAttribute('aria-describedby');
   if(trigger.disabled)close();
   list.replaceChildren();options().forEach((option,i)=>{const item=el('div','cw-choice-option field-menu-option');item.textContent=option.textContent;item.id=id+'-'+i;item.setAttribute('role','option');item.setAttribute('aria-label',option.textContent);item.setAttribute('aria-selected',String(option.selected));item.dataset.index=String(i);list.append(item);});
  }
  function active(i){const choices=options();if(!choices.length)return;index=(i+choices.length)%choices.length;for(const item of list.children)item.classList.toggle('is-active',Number(item.dataset.index)===index);list.setAttribute('aria-activedescendant',id+'-'+index);list.children[index]?.scrollIntoView?.({block:'nearest'});}
  function position(){
   const rect=trigger.getBoundingClientRect(),below=innerHeight-rect.bottom-10,above=rect.top-10,up=below<170&&above>below,width=Math.max(1,Math.min(rect.width,innerWidth-24));
   if(rect.bottom<0||rect.top>innerHeight){close();return;}
   wrapper.dataset.above=String(up);list.style.width=width+'px';list.style.maxHeight=Math.max(64,Math.min(280,up?above:below))+'px';list.style.left=Math.min(Math.max(12,rect.left),innerWidth-width-12)+'px';list.style.top=(up?Math.max(10,rect.top-6):rect.bottom+6)+'px';list.style.transform=up?'translateY(-100%)':'none';
  }
  function open(){
   if(blocked()||!wrapper.isConnected)return;dismiss();refresh();opened={wrapper,list,close,position};list.hidden=false;wrapper.dataset.open='true';trigger.setAttribute('aria-expanded','true');position();
   if(typeof list.showPopover==='function'){list.setAttribute('popover','manual');try{list.showPopover();}catch{list.removeAttribute('popover');}}
   active(Math.max(0,options().findIndex(option=>option.selected)));list.focus({preventScroll:true});
  }
  function choose(){const option=options()[index];if(!option||blocked())return;select.value=option.value;select.dispatchEvent(new Event('input',{bubbles:true}));select.dispatchEvent(new Event('change',{bubbles:true}));close(true);}
  trigger.addEventListener('click',()=>list.hidden?open():close(true));
  trigger.addEventListener('keydown',event=>{if(['ArrowDown','ArrowUp','Enter',' '].includes(event.key)){event.preventDefault();open();if(event.key==='ArrowUp')active(options().length-1);}});
  list.addEventListener('click',event=>{const item=event.target.closest('[role=option]');if(item&&list.contains(item)){index=Number(item.dataset.index);choose();}});
  list.addEventListener('keydown',event=>{
   if(['ArrowDown','ArrowUp','Home','End','Enter',' ','Escape','Tab'].includes(event.key)){
    if(event.key!=='Tab')event.preventDefault();if(event.key==='ArrowDown')active(index+1);if(event.key==='ArrowUp')active(index-1);if(event.key==='Home')active(0);if(event.key==='End')active(options().length-1);if(['Enter',' '].includes(event.key))choose();if(event.key==='Escape')close(true);if(event.key==='Tab'){close(true);}
   }else if(event.key.length===1&&!event.ctrlKey&&!event.metaKey){typeahead+=event.key.toLocaleLowerCase();clearTimeout(typeTimer);typeTimer=setTimeout(()=>{typeahead='';},650);const next=options().findIndex(option=>option.textContent.toLocaleLowerCase().startsWith(typeahead));if(next>=0)active(next);}
  });
  wrapper.addEventListener('focusout',event=>{if(!wrapper.contains(event.relatedTarget))close();});
  select.addEventListener('change',refresh);
  select.addEventListener('invalid',()=>{select.closest('details')?.setAttribute('open','');trigger.focus();});
  for(const key of ['value','selectedIndex','disabled']){
   const property=Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,key);
   if(property?.get&&property?.set)Object.defineProperty(select,key,{get(){return property.get.call(this);},set(value){property.set.call(this,value);refresh();},configurable:true});
  }
  const observer=new MutationObserver(refresh);observer.observe(select,{attributes:true,childList:true,subtree:true,characterData:true});
  for(let parent=wrapper.parentElement;parent;parent=parent.parentElement)if(parent.tagName==='FIELDSET'||parent.hasAttribute('inert'))observer.observe(parent,{attributes:true,attributeFilter:['disabled','inert']});
  select.form?.addEventListener('reset',()=>queueMicrotask(refresh));
  refresh();return wrapper;
 }
 globalThis.UladimFieldMenu=Object.freeze({enhance,close:dismiss});
})();
