'use strict';
/* Browser install prompts are optional and single-use. Nothing here requests
   permission, opens an OS menu, stores identity, or interrupts an active draft. */
(function(root){
 if(root.document.documentElement.dataset.surface==='control')return;
 const COPY={
  ru:{title:'ULADIM на вашем устройстве',button:'Установить ULADIM',open:'Открыть ULADIM',ready:'Открывайте ULADIM с отдельного значка.',manual:'Установка завершается через меню браузера.',prompting:'Подтвердите установку в окне браузера.',accepted:'Браузер принял запрос. Завершите установку по его подсказкам.',dismissed:'Установка отменена. Можно повторить её через меню браузера.',error:'Браузер не открыл установку. Воспользуйтесь инструкцией ниже.',installed:'ULADIM установлен на этом устройстве.',guide:'Как установить',ios:'Нажмите «Поделиться» → «На экран Домой» → «Добавить». Затем откройте ULADIM с нового значка.',ios_chrome:'В Chrome нажмите «Поделиться» рядом с адресной строкой → «На экран Домой» → «Добавить».',safari_fallback:'Если пункта «На экран Домой» нет, откройте ULADIM в Safari и нажмите «Поделиться».',android:'Откройте меню браузера → «Установить приложение» или «Добавить на главный экран» → «Установить».',mac:'В Safari нажмите «Поделиться» → «Добавить в Dock» → «Добавить».',desktop:'Нажмите значок установки рядом с адресной строкой или откройте меню браузера → «Установить ULADIM».',unavailable:'Если установка недоступна, откройте ULADIM в актуальном Chrome, Edge или Safari. Можно продолжить работу в этой вкладке.'},
  en:{title:'ULADIM on your device',button:'Install ULADIM',open:'Open ULADIM',ready:'Open ULADIM from its own icon.',manual:'Complete installation through your browser menu.',prompting:'Confirm installation in the browser window.',accepted:'The browser accepted your request. Follow its steps to finish installation.',dismissed:'Installation cancelled. You can try again through the browser menu.',error:'The browser could not open installation. Use the steps below.',installed:'ULADIM is installed on this device.',guide:'Installation steps',ios:'Tap Share → Add to Home Screen → Add. Then open ULADIM from the new icon.',ios_chrome:'In Chrome, tap Share beside the address bar → Add to Home Screen → Add.',safari_fallback:'If Add to Home Screen is missing, open ULADIM in Safari and tap Share.',android:'Open the browser menu → Install app or Add to Home screen → Install.',mac:'In Safari, open Share → Add to Dock → Add.',desktop:'Use the install icon beside the address bar or the browser menu → Install ULADIM.',unavailable:'If installation is unavailable, open ULADIM in a current Chrome, Edge or Safari browser. You can keep using this tab.'}
 };
 const mounted=new Set(),byHost=new WeakMap(),media=root.matchMedia?.('(display-mode: standalone)');
 let pending=null,phase='manual',observedInstalled=false,standalone=Boolean(media?.matches),sequence=0;
 const text=key=>{
  const locale=root.UladimI18n?.language?.()||root.document.documentElement.lang;
  const fallback=(COPY[locale]||COPY.en)[key];
  return root.UladimI18n?.text('pwa_install_'+key,{},fallback)||fallback;
 };
 const isInstalled=()=>observedInstalled||standalone||root.navigator.standalone===true;
 const element=(tag,className)=>{const node=root.document.createElement(tag);if(className)node.className=className;return node;};
 function steps(){
  const ua=root.navigator.userAgent||'',ios=/iP(ad|hone|od)/.test(ua)||(root.navigator.platform==='MacIntel'&&root.navigator.maxTouchPoints>1);
  if(ios)return [/CriOS/.test(ua)?'ios_chrome':'ios','safari_fallback'];
  if(/Android/.test(ua))return ['android','unavailable'];
  if(/Mac/.test(root.navigator.platform||ua)&&/Safari/.test(ua)&&!/Chrome|Chromium|Edg/.test(ua))return ['mac','unavailable'];
  return ['desktop','unavailable'];
 }
 function update(surface){
  const state=isInstalled()?'installed':phase;
  surface.node.dataset.installState=state;
  surface.heading.textContent=text('title');
  surface.button.textContent=text('button');surface.button.hidden=state==='installed';surface.button.disabled=state==='prompting';
  surface.button.setAttribute('aria-expanded',String(surface.details.open));
  surface.open.textContent=text('open');surface.status.textContent=text(state==='ready'?'ready':state);
  surface.summary.textContent=text('guide');surface.details.hidden=state==='installed';
  const wanted=steps();
  while(surface.steps.children.length>wanted.length)surface.steps.lastElementChild.remove();
  wanted.forEach((key,index)=>{
   let line=surface.steps.children[index];if(!line){line=element('p');surface.steps.append(line);}line.textContent=text(key);
  });
 }
 function publish(){for(const surface of mounted){if(surface.node.isConnected)update(surface);else mounted.delete(surface);}}
 function installed(){observedInstalled=true;pending=null;phase='installed';publish();}
 function reveal(surface){surface.details.open=true;surface.button.setAttribute('aria-expanded','true');}
 async function install(surface){
  if(isInstalled()||phase==='prompting')return;
  const offer=pending;
  if(!offer){reveal(surface);return;}
  pending=null;phase='prompting';publish();
  try{
   // Keep this call before the first await: the browser requires user activation.
   const result=await offer.prompt();
   const choice=offer.userChoice?await offer.userChoice:result;
   if(isInstalled())return;
   // A new browser offer can replace a consumed event while its result settles.
   phase=pending?'ready':choice?.outcome==='accepted'?'accepted':'dismissed';
  }catch{
   if(isInstalled())return;
   phase=pending?'ready':'error';reveal(surface);
  }finally{publish();}
 }
 function mount(host,{compact=false,heading=true,placement=''}={}){
  if(!host)return null;
  for(const surface of mounted)if(!surface.node.isConnected)mounted.delete(surface);
  const existing=byHost.get(host);if(existing?.node.parentNode===host){mounted.add(existing);update(existing);return existing.node;}
  const node=element('section','install-affordance'+(compact?' install-affordance-compact':''));
  if(placement)node.dataset.installPlacement=placement;
  const title=element('h2','install-affordance-title'),status=element('p','install-affordance-status');
  title.hidden=!heading;status.setAttribute('role','status');status.setAttribute('aria-live','polite');
  const actions=element('div','install-affordance-actions'),button=element('button','secondary install-affordance-button'),open=element('a','install-affordance-open');
  button.type='button';open.href='/app';
  const details=element('details','install-affordance-guide'),summary=element('summary'),lines=element('div','install-affordance-steps');
  details.id='uladim-install-'+(++sequence);button.setAttribute('aria-controls',details.id);lines.dataset.installSteps='';
  details.append(summary,lines);actions.append(button,open);node.append(title,status,actions,details);
  const surface={node,heading:title,status,button,open,details,summary,steps:lines};
  button.addEventListener('click',()=>{void install(surface);});
  details.addEventListener('toggle',()=>button.setAttribute('aria-expanded',String(details.open)));
  host.append(node);byHost.set(host,surface);mounted.add(surface);update(surface);return node;
 }
 root.addEventListener('beforeinstallprompt',event=>{
  if(isInstalled()||typeof event.prompt!=='function')return;
  event.preventDefault();pending=event;if(phase!=='prompting')phase='ready';publish();
 });
 root.addEventListener('appinstalled',installed);
 // The app clears its private DOM in its own pagehide handler. Prune after it;
 // public documents retained in the history cache keep their live controls.
 root.addEventListener('pagehide',()=>root.queueMicrotask(publish));
 if(media?.addEventListener)media.addEventListener('change',event=>{standalone=event.matches;publish();});
 else media?.addListener?.(event=>{standalone=event.matches;publish();});
 root.UladimInstall={mount,isInstalled};
})(globalThis);
