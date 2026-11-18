import assert from 'node:assert/strict';
import {describe, it} from 'node:test';
import {JSDOM} from 'jsdom';
import {existsSync,readFileSync} from 'node:fs';
const path=new URL('../backend/webassets/app/appearance-boot.js',import.meta.url);
function boot(saved,dark){const dom=new JSDOM('<html><head></head><body></body></html>',{url:'https://example.test/app',runScripts:'outside-only'}),w=dom.window;const media={matches:dark,addEventListener(_type,callback){this.changed=callback;}};w.matchMedia=()=>media;w.bootSystem=media;w.localStorage.setItem('uladim-interface',JSON.stringify(saved));if(existsSync(path))w.eval(readFileSync(path,'utf8'));return w;}
describe('early appearance boot',()=>{
 it('updates page and card colors when system mode changes and preserves explicit light mode',()=>{const w=boot({theme:'system',appearanceIntensity:100},false),initial=w.document.documentElement.style.getPropertyValue('--appearance-surface-color');w.bootSystem.matches=true;w.bootSystem.changed();assert.equal(w.document.documentElement.dataset.bootTheme, 'dark');assert.notEqual(w.document.documentElement.style.getPropertyValue('--appearance-surface-color'), initial);w.UladimAppearanceBoot.apply({theme:'light',appearanceIntensity:100});w.bootSystem.changed();assert.equal(w.document.documentElement.dataset.bootTheme, 'light');});
 it('paints a saved light theme before app startup even when the system is dark',()=>{const w=boot({theme:'light',palette:'rose',appearanceIntensity:100},true);assert.equal(w.document.documentElement.dataset.bootTheme, 'light');assert.equal(w.document.documentElement.style.colorScheme, 'light');assert.match(w.document.documentElement.style.getPropertyValue('--boot-page'), /^#[\da-f]{6}$/);});
 it('resolves system mode, bounds invalid preferences and reads only nonprivate interface preferences',()=>{const w=boot({theme:'system',palette:'invalid',appearanceIntensity:-1},true);assert.equal(w.document.documentElement.dataset.bootTheme, 'dark');assert.equal(w.document.documentElement.dataset.bootPalette, 'violet');assert.equal(w.document.documentElement.dataset.bootIntensity, '0');assert.equal(w.localStorage.length, 1);});
});
