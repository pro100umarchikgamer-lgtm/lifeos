'use strict';
const CACHE='uladim-interface-v50-refined-experience';
const FILES=['/app/assets/domain.js','/app/assets/auth-texture.webp','/assets/design.css','/app/assets/money.js','/app/assets/statement-formats.js','/app/assets/import.js','/app/assets/personal-import.js','/app/assets/statement-xlsx.js','/app/assets/statement-worker.js','/app/assets/app.js','/app/assets/app.css','/app/assets/locales.json','/app/assets/offline.html','/app/assets/offline.js','/app/assets/icon-192.png','/app/assets/icon-512.png','/app/assets/apple-touch-icon.png'];
self.addEventListener('install',event=>event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(FILES))));
self.addEventListener('activate',event=>event.waitUntil(caches.keys().then(keys=>Promise.all([...keys.filter(key=>key.startsWith('uladim-interface-')&&key!==CACHE).map(key=>caches.delete(key)),self.clients.claim()]))));
self.addEventListener('fetch',event=>{
  const request=event.request,url=new URL(request.url);
  if(request.method!=='GET'||url.origin!==self.location.origin)return;
  // An exact allowlist: account, sync, support and Control responses never enter CacheStorage.
  if(FILES.includes(url.pathname)&&!url.search){
    event.respondWith(fetch(request).catch(()=>caches.match(url.pathname)));return;
  }
  if(request.mode==='navigate'&&(url.pathname==='/app'||url.pathname==='/app/'))event.respondWith(fetch(request).catch(()=>caches.match('/app/assets/offline.html')));
});
