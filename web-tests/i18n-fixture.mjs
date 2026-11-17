import {readFileSync} from 'node:fs';
const source=readFileSync(new URL('../backend/webassets/app/i18n.js',import.meta.url),'utf8');
export function loadI18n(window){window.eval(source);return window.UladimI18n;}
