"""Bounded HTTPS checks on ULADIM only; no accepted signup/application or mail."""
import argparse,hashlib,json,re,subprocess,time,urllib.request,urllib.error
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('--revision',default='c2309d6612ad60eda124622a031f443dcc5c0f3b');parser.add_argument('--output',default='web_evidence/live-acceptance-20261109.json');args=parser.parse_args()
assert re.fullmatch('[a-f0-9]{40}',args.revision)
SITE='https://getuladim.space';R=args.revision;cases=[]
def save_progress(result):
 destination=Path(args.output);destination.parent.mkdir(parents=True,exist_ok=True);destination.write_text(json.dumps({'result':result,'revision':R,'cases':cases},indent=2)+'\n')
def check(path,status=200,method='GET',host=SITE,body=None,headers=None):
 h={'User-Agent':'ULADIM-release-acceptance/20261109',**(headers or {})}
 if body is not None:h['Content-Type']='application/json'
 request=urllib.request.Request(host+path,data=json.dumps(body).encode() if body is not None else None,headers=h,method=method)
 try:r=urllib.request.urlopen(request,timeout=20)
 except urllib.error.HTTPError as e:r=e
 except urllib.error.URLError as e:
  cases.append({'url':host+path,'method':method,'expected_status':status,'actual_status':None,'passed':False,'transport_error':type(e.reason).__name__});save_progress('incomplete');raise
 with r:
  data=r.read();ok=r.status==status
  cases.append({'url':host+path,'method':method,'expected_status':status,'actual_status':r.status,'passed':ok})
  save_progress('in_progress' if ok else 'failed')
  assert ok,cases[-1]
  if len(cases)%10==0:print('HTTPS_PROGRESS',len(cases),flush=True)
  if '/account/api/' in path and not path.endswith('/plans'):assert r.headers.get('Cache-Control')=='no-store'
  if method=='HEAD':assert not data
  time.sleep(.05)
  return data,r.headers
for path in ('/','/app','/early-access','/account','/plans','/support','/privacy','/terms','/faq','/docs','/status','/delete-account','/download'):check(path)
for path in ('/','/app','/early-access','/account'):check(path,method='HEAD')
for f in ('app.js','app.css','locales.json','manifest.webmanifest','offline.html','offline.js','icon-192.png'):
 data,_=check('/app/assets/'+f)
 expected=subprocess.check_output(['git','show',R+':backend/webassets/app/'+f])
 assert hashlib.sha256(data).digest()==hashlib.sha256(expected).digest(),f
check('/app/sw.js')
for action in ('session','spaces','sync','roster','devices','mfa','deletion','support','thread','entitlements'):check('/account/api/'+action,401)
check('/control/api/login',404,'POST',body={})
check('/early-access/api/apply',403,'POST',body={})
data,_=check('/account/api/signup',403,'POST',body={'email':'unauthorized-acceptance@example.test','password':'synthetic-closed-test-password'},headers={'Origin':SITE})
assert json.loads(data)['error']=='registration_closed'
for host in ('https://api.getuladim.space','https://control.getuladim.space'):check('/',503,host=host)
for host in (SITE,'https://api.getuladim.space','https://control.getuladim.space'):
 for path in ('/metrics','/health/ready'):check(path,404,host=host)
check('/account/api/session',401,headers={'Cookie':'__Host-uladim_account='+'A'*43})
_,cors_headers=check('/account/api/signup',405,'OPTIONS',headers={'Origin':'https://attacker.example.test','Access-Control-Request-Method':'POST'});assert 'Access-Control-Allow-Origin' not in cors_headers
data,_=check('/account/api/plans');assert json.loads(data)['sales_enabled'] is False
result={'at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'revision_verified_by_asset_hash':R,'result':'passed','passed':len(cases),'total':len(cases),'scope':'Read-only/denied synthetic requests; no accepted application/account or outgoing email; no authenticated owner or physical-device test','cases':cases}
destination=Path(args.output);destination.parent.mkdir(parents=True,exist_ok=True);destination.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'result':result['result'],'passed':len(cases)}))
