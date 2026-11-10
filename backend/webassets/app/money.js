'use strict';
// Identical minor-unit conventions to lib/domain/models.dart (Android).
globalThis.ULADIMMoney=Object.freeze({
 digits(currency){const c=String(currency).trim().toUpperCase();if(!/^[A-Z]{3}$/.test(c))throw {code:'invalid_currency'};return ['JPY','KRW','VND','CLP','ISK','PYG','UGX','XAF','XOF'].includes(c)?0:['BHD','JOD','KWD','OMR','TND','IQD','LYD'].includes(c)?3:2;},
 decimal(value,currency){const digits=this.digits(currency),v=BigInt(value),a=v<0n?-v:v,s=a.toString().padStart(digits+1,'0');return(v<0n?'-':'')+(digits?s.slice(0,-digits)+'.'+s.slice(-digits):s);},
 format(value,currency,locale){const text=this.decimal(value,currency),[whole,fraction]=text.split('.');const separator=new Intl.NumberFormat(locale).formatToParts(1.1).find(p=>p.type==='decimal')?.value||'.';return (text.startsWith('-')?'-':'')+BigInt(whole.replace('-','')).toLocaleString(locale)+(fraction!==undefined?separator+fraction:'')+' '+currency;},
 parse(value,currency,signed=false){const digits=this.digits(currency),clean=value.trim().replace(/[ \u00a0]/g,'').replace(',','.');const match=new RegExp('^'+(signed?'-?':'')+'(\\d+)(?:\\.(\\d+))?$').exec(clean);if(!match)throw {code:'invalid_amount'};const fraction=match[2]||'';if(fraction.length>digits)throw {code:'amount_precision'};const amount=BigInt(match[1]+fraction.padEnd(digits,'0'))*(clean.startsWith('-')?-1n:1n);if(amount>999999999999999n||amount< -999999999999999n||(!signed&&amount<=0n))throw {code:'invalid_amount'};return Number(amount);}
});
