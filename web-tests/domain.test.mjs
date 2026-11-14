import { describe, it, expect } from 'vitest';
import '../backend/webassets/app/domain.js';
import '../backend/webassets/app/money.js';
const D=globalThis.ULADIMDomain;
const event=(localStart,repeat='none',timezone='device')=>({id:'e',data:{title:'Event',schedule:{localStart,timezone,allDay:false,repeat,interval:1,until:null}}});
describe('calendar shared schedule contract',()=>{
 it('clamps month ends like the Android calendar',()=>{
  const rows=D.occurrences([event('2026-01-31T09:00:00','monthly')],'2026-02-01','2026-04-01','UTC');
  expect(rows.map(x=>x.day)).toEqual(['2026-02-28','2026-03-31']);
 });
 it('displays named timezone events on the viewer civil day',()=>{
  expect(D.occurrences([event('2026-11-10T23:30:00','none','America/New_York')],'2026-11-11','2026-11-12','Asia/Tashkent')[0].day).toBe('2026-11-11');
 });
 it('respects inclusive recurrence end and interval',()=>{
  const e=event('2026-11-01T09:00:00','daily');e.data.schedule.interval=2;e.data.schedule.until='2026-11-05';
  expect(D.occurrences([e],'2026-11-01','2026-11-10','UTC').map(x=>x.day)).toEqual(['2026-11-01','2026-11-03','2026-11-05']);
 });
 it('uses device timezone and keeps all-day dates civil',()=>{
  const e=event('2026-11-10T00:00:00','none','Pacific/Kiritimati');e.data.schedule.allDay=true;
  expect(D.occurrences([e],'2026-11-10','2026-11-11','America/Los_Angeles')[0].day).toBe('2026-11-10');
 });
 it('rejects invalid timezone and malformed dates without hanging',()=>{
  expect(()=>D.occurrences([event('bad')],'2026-01-01','2026-02-01','UTC')).toThrow();
  expect(()=>D.occurrences([event('2026-01-05T09:00:00','none','Not/AZone')],'2026-01-01','2026-02-01','UTC')).toThrow();
 });
});
describe('server schedule bounds',()=>{
 it('rejects out-of-contract years and recurrence intervals',()=>{
  for(const [start,interval] of [['1899-01-01T09:00:00',1],['2201-01-01T09:00:00',1],['2026-01-01T09:00:00',366],['2026-01-01T09:00:00',1.5]]){
   const e=event(start);e.data.schedule.interval=interval;
   expect(()=>D.occurrences([e],'2026-01-01','2026-02-01','UTC')).toThrow('invalid_schedule');
  }
 });
});
describe('DST parity with Android',()=>{
 it('chooses earlier instant in an overlap',()=>{expect(new Date(D.wallTime('2026-10-25T02:30:00','Europe/Berlin')).toISOString()).toBe('2026-10-25T00:30:00.000Z');});
 it('shifts a half-hour gap by its actual length',()=>{expect(new Date(D.wallTime('2026-10-04T02:15:00','Australia/Lord_Howe')).toISOString()).toBe('2026-10-03T15:45:00.000Z');});
});
describe('task filters and money form validation',()=>{
 it('filters completion and searches case insensitively',()=>{
  const rows=[{data:{title:'Привет Умар',completed:0}},{data:{title:'Привет',completed:1}}];
  expect(D.tasks(rows,'ПРИВЕТ','open')).toHaveLength(1);
 });
 it('rejects mismatched transaction currency and same-account transfers',()=>{
  const a=[{id:'rub',data:{currency:'RUB'}},{id:'usd',data:{currency:'USD'}}];
  expect(()=>D.validateFinance('transaction',{account_id:'rub',currency:'USD'},a)).toThrow();
  expect(()=>D.validateFinance('transfer',{from_id:'rub',to_id:'rub',sent_minor:100,received_minor:100},a)).toThrow();
 });
 it('enforces equal units for same currency and explicit amounts for FX',()=>{
  const a=[{id:'a',data:{currency:'RUB'}},{id:'b',data:{currency:'RUB'}},{id:'c',data:{currency:'USD'}}];
  expect(()=>D.validateFinance('transfer',{from_id:'a',to_id:'b',sent_minor:100,received_minor:90},a)).toThrow();
  expect(()=>D.validateFinance('transfer',{from_id:'a',to_id:'c',sent_minor:100,received_minor:90},a)).not.toThrow();
 });
 it('preserves maximum minor-unit precision and three-digit currencies',()=>{
  expect(ULADIMMoney.parse('9999999999999,99','RUB')).toBe(999999999999999);
  expect(ULADIMMoney.parse('1.123','KWD')).toBe(1123);
  expect(()=>ULADIMMoney.parse('1.1','JPY')).toThrow();
 });
});
