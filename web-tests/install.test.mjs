import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync, existsSync} from 'node:fs';
import {JSDOM} from 'jsdom';
import {loadI18n} from './i18n-fixture.mjs';

const helper=new URL('../backend/webassets/app/install.js',import.meta.url);
const source=existsSync(helper)?readFileSync(helper,'utf8'):'';
const tick=()=>new Promise(resolve=>setTimeout(resolve,0));

function setup({userAgent='',platform='',touch=0,standalone=false,control=false}={}){
 const dom=new JSDOM('<html lang="en"'+(control?' data-surface="control"':'')+'><body><main><input value="Keep my draft"><div id="first"></div><div id="second"></div></main></body></html>',{url:'https://getuladim.space/app',runScripts:'outside-only'});
 const w=dom.window;let mediaListener;
 w.matchMedia=()=>({matches:standalone,addEventListener(type,listener){mediaListener=listener;}});
 for(const [key,value]of Object.entries({userAgent,platform,maxTouchPoints:touch,standalone}))Object.defineProperty(w.navigator,key,{configurable:true,value});
 loadI18n(w);w.UladimI18n.setLanguage('en');w.eval(source);
 return {dom,w,mediaChange:matches=>mediaListener?.({matches})};
}
function mount(w,selector='#first'){
 assert.ok(w.UladimInstall,'shared installation controller is available');
 w.UladimInstall.mount(w.document.querySelector(selector));
 return w.document.querySelector(selector+' .install-affordance');
}
function offer(w,prompt,userChoice){
 const event=new w.Event('beforeinstallprompt',{cancelable:true});
 event.prompt=prompt;if(userChoice)event.userChoice=userChoice;
 w.dispatchEvent(event);return event;
}

test('a late native offer updates the existing controls without replacing or blurring a draft',()=>{
 const {dom,w}=setup();try{
  const first=mount(w),second=mount(w,'#second'),button=first.querySelector('button'),draft=w.document.querySelector('input');
  draft.focus();draft.value='Unsaved work';let calls=0;
  assert.equal(first.dataset.installState,'manual');assert.equal(first.querySelector('details').open,false);
  const event=offer(w,()=>{calls++;return Promise.resolve({outcome:'dismissed'});});
  assert.equal(event.defaultPrevented,true);assert.equal(calls,0);
  assert.equal(first.dataset.installState,'ready');assert.equal(second.dataset.installState,'ready');
  assert.equal(first.querySelector('button'),button);assert.equal(w.document.activeElement,draft);assert.equal(draft.value,'Unsaved work');
 }finally{dom.window.close();}
});

test('only an explicit click opens one native prompt, and acceptance waits for installation evidence',async()=>{
 const {dom,w}=setup();try{
  const first=mount(w),second=mount(w,'#second');let calls=0,finish;
  offer(w,()=>{calls++;return new Promise(resolve=>{finish=resolve;});});
  assert.equal(calls,0);first.querySelector('button').click();second.querySelector('button').click();
  assert.equal(calls,1);assert.equal(first.dataset.installState,'prompting');assert.equal(second.querySelector('button').disabled,true);
  finish({outcome:'accepted'});await tick();
  assert.equal(first.dataset.installState,'accepted');assert.equal(w.UladimInstall.isInstalled(),false);
  w.dispatchEvent(new w.Event('appinstalled'));
  for(const surface of [first,second]){assert.equal(surface.dataset.installState,'installed');assert.equal(surface.querySelector('button').hidden,true);}
  assert.equal(w.UladimInstall.isInstalled(),true);assert.equal(first.querySelector('a').getAttribute('href'),'/app');
 }finally{dom.window.close();}
});

test('dismissal consumes its event and manual retry cannot reuse it; a fresh offer can prompt',async()=>{
 const {dom,w}=setup();try{
  const surface=mount(w);let calls=0;
  offer(w,()=>{calls++;return Promise.resolve();},Promise.resolve({outcome:'dismissed'}));
  surface.querySelector('button').click();await tick();
  assert.equal(surface.dataset.installState,'dismissed');assert.equal(surface.querySelector('button').disabled,false);
  surface.querySelector('button').click();await tick();assert.equal(calls,1);assert.equal(surface.querySelector('details').open,true);
  offer(w,()=>{calls++;return Promise.resolve({outcome:'dismissed'});});
  assert.equal(surface.dataset.installState,'ready');surface.querySelector('button').click();await tick();assert.equal(calls,2);
 }finally{dom.window.close();}
});

test('a rejected prompt exposes useful manual instructions and cannot leak an unhandled rejection',async()=>{
 const {dom,w}=setup();try{
  const surface=mount(w);let calls=0;
  offer(w,()=>{calls++;return Promise.reject(new Error('Browser policy'));});
  surface.querySelector('button').click();await tick();
  assert.equal(surface.dataset.installState,'error');assert.equal(surface.querySelector('details').open,true);
  assert.equal(surface.querySelector('button').disabled,false);assert.match(surface.textContent,/browser/i);
  surface.querySelector('button').click();await tick();assert.equal(calls,1);
 }finally{dom.window.close();}
});

test('installation evidence received while a prompt is open wins over its later dismissed result',async()=>{
 const {dom,w}=setup();try{
  const surface=mount(w);let finish;
  offer(w,()=>new Promise(resolve=>{finish=resolve;}));surface.querySelector('button').click();
  w.dispatchEvent(new w.Event('appinstalled'));finish({outcome:'dismissed'});await tick();
  assert.equal(surface.dataset.installState,'installed');assert.equal(surface.querySelector('button').hidden,true);
 }finally{dom.window.close();}
});

test('standalone launches and a later display-mode change show installed state without prompting',()=>{
 for(const standalone of [true,false]){
  const {dom,w,mediaChange}=setup({standalone});try{
   const surface=mount(w);if(!standalone)mediaChange(true);
   assert.equal(surface.dataset.installState,'installed');assert.equal(w.UladimInstall.isInstalled(),true);
  }finally{dom.window.close();}
 }
});

test('a public page restored from history still receives a late installation offer',async()=>{
 const {dom,w}=setup();try{
  const surface=mount(w);w.dispatchEvent(new w.Event('pagehide'));await tick();
  offer(w,()=>Promise.resolve({outcome:'dismissed'}));
  assert.equal(surface.dataset.installState,'ready');
 }finally{dom.window.close();}
});

test('manual steps distinguish iPad Chrome, touch iPad, Safari, Android and Mac',()=>{
 const cases=[
  {userAgent:'Mozilla/5.0 (iPad; CPU OS 18_0 like Mac OS X) CriOS/130 Mobile Safari/604.1',want:/Chrome.*Share.*Add to Home Screen.*Add/},
  {userAgent:'Mozilla/5.0 Macintosh CriOS/130',platform:'MacIntel',touch:5,want:/Chrome.*Share.*Add to Home Screen/},
  {userAgent:'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0) Version/18.0 Mobile Safari/604.1',want:/Share.*Add to Home Screen/},
  {userAgent:'Mozilla/5.0 (Linux; Android 14) Chrome/130',want:/browser menu.*Install app.*Add to Home screen/},
  {userAgent:'Mozilla/5.0 (Macintosh; Intel Mac OS X) Version/18.0 Safari/605.1',platform:'MacIntel',want:/Share.*Add to Dock/},
 ];
 for(const item of cases){
  const {dom,w}=setup(item);try{
   const surface=mount(w);surface.querySelector('button').click();assert.equal(surface.querySelector('details').open,true);
   assert.match(surface.querySelector('[data-install-steps]').textContent,item.want);
   assert.equal(w.document.querySelectorAll('dialog').length,0);assert.equal(w.localStorage.length,0);
  }finally{dom.window.close();}
 }
});

test('Control loads the shared asset harmlessly and does not intercept browser installation',()=>{
 const {dom,w}=setup({control:true});try{
  assert.equal(w.UladimInstall,undefined);
  const event=offer(w,()=>{throw new Error('Control must not prompt');});assert.equal(event.defaultPrevented,false);
  assert.equal(w.document.querySelectorAll('.install-affordance').length,0);
 }finally{dom.window.close();}
});
