'use strict';
// Only decorative page and soft backgrounds consume these variables. Text,
// surfaces, controls and palette accents keep their existing contrast colors.
(() => {
 const copy=globalThis.UladimI18n.copy("grp_52ab76597086",{
  ru:['Насыщенность фона','Сдержанно','Ярче'],
  en:['Background intensity','Less color','More color'],
  'uz-Latn':['Fon rangining to‘yinganligi','Sokinroq','Yorqinroq'],
  'uz-Cyrl':['Фон рангининг тўйинганлиги','Сокинроқ','Ёрқинроқ']
 });
 function applyIntensity({state}){
  const raw=state.appearanceIntensity;
  const numeric=typeof raw==='number'?raw:NaN;
  const value=Number.isFinite(numeric)?Math.min(100,Math.max(0,Math.round(numeric))):50;
  state.appearanceIntensity=value;
  document.body.dataset.appearanceIntensity=String(value);
  document.body.style.setProperty('--appearance-intensity',String(value));
  document.body.style.setProperty('--appearance-tint',(20+value*.8)+'%');
  return value;
 }
 function attachIntensity({container,state,save,E,append,input}){
  const value=applyIntensity({state});
  const existing=container.querySelector('.appearance-intensity');
  if(existing)return existing;
  const [title,low,high]=copy[state.lang]||copy.en;
  const section=E('section',undefined,'appearance-intensity');
  const field=input(section,'appearance-intensity',title,'range',String(value),false);
  field.min='0';field.max='100';field.step='1';
  const output=E('output',value+'%','appearance-intensity-value');
  output.setAttribute('for',field.id);
  field.setAttribute('aria-valuetext',value+'%');
  const ends=E('div',undefined,'appearance-intensity-ends');
  append(ends,E('span',low),E('span',high));append(section,output,ends);
  field.addEventListener('input',()=>{
   state.appearanceIntensity=Number(field.value);
   const current=applyIntensity({state});
   output.textContent=current+'%';field.setAttribute('aria-valuetext',current+'%');
   save();
  });
  const palettes=container.querySelector('.appearance-palettes');
  if(palettes)palettes.insertAdjacentElement('afterend',section);else container.append(section);
  return section;
 }
 globalThis.UladimAppearance=Object.freeze({attachIntensity,applyIntensity});
})();
