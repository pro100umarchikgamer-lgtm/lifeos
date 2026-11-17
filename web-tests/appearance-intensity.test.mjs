import {loadI18n} from './i18n-fixture.mjs';
import {describe,it,expect,vi} from 'vitest';
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
  for(const value of [undefined,null,'invalid',NaN]){const state={appearanceIntensity:value};f.api.applyIntensity({state});expect(state.appearanceIntensity).toBe(50);}
  for(const [value,expected] of [[-1,0],[0,0],[20.8,21],[100,100],[500,100]]){
   const state={appearanceIntensity:value};f.api.applyIntensity({state});
   expect(state.appearanceIntensity).toBe(expected);
   expect(f.window.document.body.dataset.appearanceIntensity).toBe(String(expected));
   expect(f.window.document.body.style.getPropertyValue('--appearance-tint')).toBe((20+expected*.8)+'%');
  }
 });
 it('inserts one labelled keyboard range after palette choices, saves input and preserves palette/theme',()=>{
  const f=fixture(),state={lang:'ru',theme:'dark',palette:'rose'},save=vi.fn();
  f.api.attachIntensity({...f,state,save});f.api.attachIntensity({...f,state,save});
  expect(f.container.querySelectorAll('input[type=range]')).toHaveLength(1);
  const section=f.container.querySelector('.appearance-intensity'),range=section.querySelector('input');
  expect(section.previousElementSibling.className).toBe('appearance-palettes');
  expect(section.querySelector('label').htmlFor).toBe(range.id);
  expect([range.min,range.max,range.step,range.value]).toEqual(['0','100','1','50']);
  range.value='89';range.dispatchEvent(new f.window.Event('input',{bubbles:true}));
  expect(state).toMatchObject({appearanceIntensity:89,palette:'rose',theme:'dark'});
  expect(save).toHaveBeenCalledTimes(1);expect(section.querySelector('output').textContent).toBe('89%');
 });
 it('labels Russian, English and both Uzbek scripts without exposing untranslated keys',()=>{
  for(const lang of ['ru','en','uz-Latn','uz-Cyrl']){
   const f=fixture();f.api.attachIntensity({...f,state:{lang},save:()=>{}});
   const range=f.container.querySelector('input');
   expect(range.labels[0].textContent.length).toBeGreaterThan(5);
   expect(range.getAttribute('aria-valuetext')).toBe('50%');
  }
 });
});
