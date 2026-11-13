'use strict';
const CACHE='uladim-interface-v51-web-notifications';
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

// Push contents never enter CacheStorage. A fresh session check also protects
// against an in-flight message after logout or switching to another account.
self.addEventListener('message',event=>{
  if(event.data?.type==='uladim-notifications-capabilities')event.ports[0]?.postMessage({supported:true,version:1});
});
const PUSH_UUID=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
function notificationDestination(value){
  if(typeof value!=='string'||value.length>512)return null;
  try{
    const url=new URL(value,self.location.origin);
    if(url.origin!==self.location.origin||!['/app','/app/'].includes(url.pathname)||url.hash||url.username||url.password)return null;
    if(!url.search)return '/app';
    if([...url.searchParams.keys()].some(key=>!['notification','workspace','day'].includes(key))||[...url.searchParams.keys()].length!==3)return null;
    const day=url.searchParams.get('day');
    if(url.searchParams.get('notification')!=='calendar'||!PUSH_UUID.test(url.searchParams.get('workspace')||'')||!/^\d{4}-\d{2}-\d{2}$/.test(day||'')||new Date(day+'T12:00:00Z').toISOString().slice(0,10)!==day)return null;
    return '/app'+url.search;
  }catch{return null;}
}
function notificationPayload(event){
  try{
    if(!event.data||event.data.arrayBuffer().byteLength>8192)return null;
    const data=event.data.json(),now=Date.now();
    if(data?.v!==1||!PUSH_UUID.test(data.delivery_id||'')||!PUSH_UUID.test(data.recipient_user_id||'')||!PUSH_UUID.test(data.subscription_id||'')||! /^[A-Za-z0-9_-]{43}$/.test(data.receipt_token||'')||data.title!=='ULADIM'||typeof data.body!=='string'||!data.body.length||data.body.length>240||!Number.isSafeInteger(data.sent_at)||now-data.sent_at>3600000||data.sent_at-now>300000||!['high','normal'].includes(data.priority))return null;
    const url=notificationDestination(data.url);
    if(!url||data.tag!=='uladim-'+data.delivery_id)return null;
    return {...data,url};
  }catch{return null;}
}
async function notificationReceipt(data,state){
  try{await fetch('/account/api/notifications/receipt',{method:'POST',credentials:'same-origin',cache:'no-store',headers:{'Content-Type':'application/json'},body:JSON.stringify({delivery_id:data.delivery_id,receipt_token:data.receipt_token,state})});}catch{}
}
async function receiveNotification(event){
  const data=notificationPayload(event);if(!data)return;
  try{
    const response=await fetch('/account/api/session',{credentials:'same-origin',cache:'no-store'});
    const session=response.ok?await response.json():null;
    if(session?.user_id!==data.recipient_user_id){await notificationReceipt(data,'suppressed');return;}
    const statusResponse=await fetch('/account/api/notifications',{credentials:'same-origin',cache:'no-store'});
    const status=statusResponse.ok?await statusResponse.json():null;
    if(!status?.enabled||status.subscription_id!==data.subscription_id){await notificationReceipt(data,'suppressed');return;}
    await self.registration.showNotification(data.title,{body:data.body,icon:'/app/assets/icon-192.png',badge:'/app/assets/icon-192.png',tag:data.tag,renotify:true,silent:false,requireInteraction:data.priority==='high',vibrate:data.priority==='high'?[200,100,200]:[100],timestamp:data.sent_at,data:{url:data.url,delivery_id:data.delivery_id}});
    // "displayed" records browser acceptance, not that a person saw a banner.
    await notificationReceipt(data,'displayed');
  }catch{await notificationReceipt(data,'suppressed');}
}
self.addEventListener('push',event=>event.waitUntil(receiveNotification(event)));
self.addEventListener('notificationclick',event=>{
  event.notification.close();
  const destination=notificationDestination(event.notification.data?.url);if(!destination)return;
  event.waitUntil((async()=>{
    const windows=await self.clients.matchAll({type:'window',includeUncontrolled:true});
    for(const client of windows){const url=new URL(client.url);if(url.origin===self.location.origin&&['/app','/app/'].includes(url.pathname)){await client.navigate(destination);await client.focus();return;}}
    await self.clients.openWindow(destination);
  })());
});
