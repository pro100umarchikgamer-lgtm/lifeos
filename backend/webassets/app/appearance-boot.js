'use strict';
// Runs before styles. This single nonprivate preference key is the only disk read.
(() => {
 const palettes={violet:['#6956bd','#c1b1ff'],forest:['#286550','#a8d9bf'],ocean:['#32688f','#a8d3ef'],pistachio:['#526b38','#c7dfa9'],rose:['#9c4e67','#edb5c7'],sand:['#816233','#e4ca99']};
 const system=globalThis.matchMedia?.('(prefers-color-scheme:dark)');let current={};
 const mix=(base,tint,amount)=>'#'+[1,3,5].map(i=>Math.round(parseInt(base.slice(i,i+2),16)*(1-amount)+parseInt(tint.slice(i,i+2),16)*amount).toString(16).padStart(2,'0')).join('');
 function apply(prefs={}){
  const mode=['light','dark','system'].includes(prefs.theme)?prefs.theme:'system',dark=mode==='dark'||mode==='system'&&Boolean(system?.matches),palette=Object.hasOwn(palettes,prefs.palette)?prefs.palette:'violet';
  const value=Number.isFinite(prefs.appearanceIntensity)?Math.min(100,Math.max(0,Math.round(prefs.appearanceIntensity))):50,amount=value/100,tint=palettes[palette][dark?1:0];
  current={theme:mode,palette,appearanceIntensity:value};
  const colors={page:mix(dark?'#171717':'#f6f6f6',tint,amount*(dark?.18:.22)),surface:mix(dark?'#242424':'#ffffff',tint,amount*(dark?.14:.12)),input:mix(dark?'#292929':'#ffffff',tint,amount*(dark?.08:.07)),soft:mix(dark?'#303030':'#f1f1f1',tint,amount*(dark?.20:.10))},html=document.documentElement;
  html.dataset.bootTheme=dark?'dark':'light';html.dataset.bootPalette=palette;html.dataset.bootIntensity=String(value);html.style.colorScheme=dark?'dark':'light';html.style.backgroundColor=colors.page;html.style.color=dark?'#f2f0f8':'#25242d';
  html.style.setProperty('--boot-page',colors.page);html.style.setProperty('--boot-ink',dark?'#f2f0f8':'#25242d');
  for(const [key,color]of Object.entries(colors))html.style.setProperty('--appearance-'+key+'-color',color);
  return colors;
 }
 globalThis.UladimAppearanceBoot=Object.freeze({apply});
 let saved={};try{saved=JSON.parse(localStorage.getItem('uladim-interface')||'{}')||{};}catch{}
 apply(saved);
 system?.addEventListener?.('change',()=>{if(current.theme==='system')apply(current);});
})();
