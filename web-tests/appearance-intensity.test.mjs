import {loadI18n} from './i18n-fixture.mjs';
import assert from 'node:assert/strict';
import {describe, it, mock} from 'node:test';
import {JSDOM} from 'jsdom';
import {readFileSync} from 'node:fs';
const source=readFileSync(new URL('../backend/webassets/app/appearance-intensity.js',import.meta.url),'utf8');
function fixture(){
 const dom=new JSDOM('<body><section id="settings"><fieldset class="appearance-palettes"></fieldset><aside></aside></section></body>',{runScripts:'outside-only'});
 const {window}=dom;loadI18n(window);window.eval(source);
 const E=(tag,text,classes)=>{const node=window.document.createElement(tag);if(text!==undefined)node.textContent=text;if(classes)node.className=classes;return node;};
 const append=(host,...nodes)=>{host.append(...nodes);return host;};
 const input=(host,name,label,type,value)=>{const id='test-'+name;const caption=E('label',label);caption.htmlFor=id;const field=E('input');Object.assign(field,{id,name,type,value});append(host,caption,field);return field;};
 return {window,api:window.UladimAppearance,container:window.document.querySelector('#settings'),E,append,input};
}
describe('background intensity',()=>{
 it('defaults invalid preferences and bounds finite values',()=>{
  const f=fixture();
  for(const value of [undefined,null,'invalid',NaN]){const state={appearanceIntensity:value};f.api.applyIntensity({state});assert.equal(state.appearanceIntensity, 50);}
  for(const [value,expected] of [[-1,0],[0,0],[20.8,21],[100,100],[500,100]]){
   const state={appearanceIntensity:value};f.api.applyIntensity({state});
   assert.equal(state.appearanceIntensity, expected);
   assert.equal(f.window.document.body.dataset.appearanceIntensity, String(expected));
   assert.equal(f.window.document.body.style.getPropertyValue('--appearance-tint'), (20+expected*.8)+'%');
  }
 });
 it('inserts one labelled keyboard range after palette choices, saves input and preserves palette/theme',()=>{
  const f=fixture(),state={lang:'ru',theme:'dark',palette:'rose'},save=mock.fn();
  f.api.attachIntensity({...f,state,save});f.api.attachIntensity({...f,state,save});
  assert.equal(f.container.querySelectorAll('input[type=range]').length, 1);
  const section=f.container.querySelector('.appearance-intensity'),range=section.querySelector('input');
  assert.equal(section.previousElementSibling.className, 'appearance-palettes');
  assert.equal(section.querySelector('label').htmlFor, range.id);
  assert.deepEqual([range.min,range.max,range.step,range.value], ['0','100','1','50']);
  range.value='89';range.dispatchEvent(new f.window.Event('input',{bubbles:true}));
  assert.partialDeepStrictEqual(state, {appearanceIntensity:89,palette:'rose',theme:'dark'});
  assert.equal(save.mock.callCount(), 1);assert.equal(section.querySelector('output').textContent, '89%');
 });
 it('labels Russian, English and both Uzbek scripts without exposing untranslated keys',()=>{
  for(const lang of ['ru','en','uz-Latn','uz-Cyrl']){
   const f=fixture();f.api.attachIntensity({...f,state:{lang},save:()=>{}});
   const range=f.container.querySelector('input');
   assert.ok(range.labels[0].textContent.length > 5);
   assert.equal(range.getAttribute('aria-valuetext'), '50%');
  }
 });
});
