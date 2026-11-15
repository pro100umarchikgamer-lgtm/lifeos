'use strict';
// New-password fields only. Existing credentials are never rechecked on sign-in.
(function(root){
 const common=new Set(['password','password1','password123','qwerty','qwerty1','qwerty123','letmein','welcome','welcome1','1234567','12345678','123456789','пароль','пароль123','uladim','uladim123','lifeos','lifeos123','abcdefg','abcdefgh','qwertyuiop','iloveyou','welcome123','letmein1','admin','admin123','test','test123','testing','123456a','sunshine','football','monkey','monkey123','dragon','dragon123','princess','a1b2c3d4']);
 const characters=value=>Array.from(value);
 function repeated(value){
  const chars=characters(value);
  for(let width=1;width<=chars.length/2;width++)if(chars.length%width===0&&chars.join('')===chars.slice(0,width).join('').repeat(chars.length/width))return true;
  return false;
 }
 function simpleRun(value){
  const chars=characters(value);if(chars.length<2)return false;
  const steps=new Set(chars.slice(1).map((char,i)=>char.codePointAt(0)-chars[i].codePointAt(0)));
  return new Set(chars).size===1||steps.size===1&&(steps.has(1)||steps.has(-1))||['qwertyuiop','asdfghjkl','zxcvbnm'].some(row=>row.includes(value)||characters(row).reverse().join('').includes(value));
 }
 function validate(password){
  if(typeof password!=='string'||characters(password).length<8||characters(password).length>256)return 'password_length';
  const value=password.toLowerCase().trim(),letters=new Set(value.match(/\p{L}/gu)||[]);
  if(!letters.size||!(/\p{Nd}/u.test(value)||characters(password.trim()).length>=16&&letters.size>=3))return 'password_weak';
  const plain=(value.match(/[\p{L}\p{Nd}]/gu)||[]).join(''),stem=plain.replace(/\p{Nd}+$/u,'');
  const runs=plain.match(/\p{L}+|\p{Nd}+/gu)||[];
  if(new Set(characters(value)).size<3||common.has(plain)||common.has(stem)||repeated(value)||repeated(plain)||stem!==plain&&repeated(stem)||runs.every(simpleRun))return 'password_weak';
  return null;
 }
 const copy=globalThis.UladimI18n.copy("grp_aa2b8a8de0af",{
  ru:{hint:'От 8 символов: буквы и цифры. Или длинная фраза от 16 символов. Избегайте повторов и простых последовательностей.',length:'Используйте от 8 до 256 символов.',weak:'Выберите менее предсказуемый пароль: буквы и цифры или длинную фразу без простых повторов.'},
  en:{hint:'Use 8 or more characters with letters and numbers, or a passphrase of at least 16 characters. Avoid repeats and simple sequences.',length:'Use between 8 and 256 characters.',weak:'Choose a less predictable password: letters and numbers, or a long phrase without simple repeats.'},
  'uz-Latn':{hint:'Kamida 8 belgi: harflar va raqamlar. Yoki kamida 16 belgili uzun ibora. Takrorlar va sodda ketma-ketliklardan qoching.',length:'8 dan 256 tagacha belgi kiriting.',weak:'Harflar va raqamlardan yoki sodda takrorlarsiz uzun iboradan foydalaning.'},
  'uz-Cyrl':{hint:'Камида 8 белги: ҳарфлар ва рақамлар. Ёки камида 16 белгили узун ибора. Такрорлар ва содда кетма-кетликлардан қочинг.',length:'8 дан 256 тагача белги киритинг.',weak:'Ҳарфлар ва рақамлардан ёки содда такрорларсиз узун иборадан фойдаланинг.'}
 });
 function attach(input,language){
  if(!input||input.dataset.passwordGuidanceAttached)return input;
  input.dataset.passwordGuidanceAttached='true';input.autocomplete='new-password';input.spellcheck=false;input.setAttribute('autocapitalize','off');
  const lang=typeof language==='function'?language:()=>language||'en';
  const text=()=>copy[lang()]||copy.en;
  const hint=document.createElement('p');hint.className='small password-guidance';hint.dataset.passwordGuidance='true';hint.id='password-guidance-'+crypto.randomUUID();hint.textContent=text().hint;
  input.after(hint);input.setAttribute('aria-describedby',[input.getAttribute('aria-describedby'),hint.id].filter(Boolean).join(' '));
  const check=()=>{const error=input.value?validate(input.value):null;input.setCustomValidity(error?text()[error==='password_length'?'length':'weak']:'');if(input.value)input.setAttribute('aria-invalid',String(Boolean(error)));else input.removeAttribute('aria-invalid');};
  input.addEventListener('input',check);input.addEventListener('invalid',check);check();return input;
 }
 root.UladimPassword={validate,attach,copy};
})(globalThis);
