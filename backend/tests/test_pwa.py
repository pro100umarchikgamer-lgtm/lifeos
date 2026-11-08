import io
import json
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch
from cryptography.fernet import Fernet
from backend.config import Settings
from backend.production import Application
from backend.service import Backend
from backend.http_server import dispatch


class PWAHTTPTests(unittest.TestCase):
    def setUp(self):
        folder=tempfile.TemporaryDirectory(); self.addCleanup(folder.cleanup)
        self.mail={}; self.backend=Backend(Path(folder.name)/'web.db',deliver=lambda e,c:self.mail.update({e:c}))
        self.prepare_pwa()

    def prepare_pwa(self):
        self.password='synthetic-pwa-password'
        android=self.backend.register('web@example.test',self.password)
        actor=self.backend.authenticate(android['token']); self.backend.verify(actor,self.mail[actor['email']])
        self.actor=self.backend.authenticate(android['token']); self.android=android['token']
        self.wid=str(uuid.uuid4())
        self.backend.family(self.actor,{'id':str(uuid.uuid4()),'workspace_id':self.wid,'action':'workspace.create','kind':'personal','name':'Shared protocol'})
        settings=Settings.load({'DATABASE_URL':'postgresql://example/db','EMAIL_QUEUE_KEY':Fernet.generate_key().decode(),'RATE_LIMIT_KEY':'x'*48,'SMTP_HOST':'127.0.0.1','SMTP_TLS':'none','EMAIL_FROM':'test@example.test'})
        self.app=Application(self.backend,settings)
        status,headers,value=self.request('/account/api/login',{'email':self.actor['email'],'password':self.password})
        self.assertEqual(status,200); self.cookie=headers['Set-Cookie'].split(';')[0]; self.csrf=value['csrf']

    def request(self,path,body=None,cookie=None,csrf=None,origin='https://getuladim.space',host='getuladim.space'):
        path,_,query=path.partition('?'); data=json.dumps(body).encode() if body is not None else b''
        env={'HTTP_HOST':host,'REQUEST_METHOD':'POST' if body is not None else 'GET','PATH_INFO':path,'QUERY_STRING':query,'REMOTE_ADDR':'172.30.30.2','HTTP_X_FORWARDED_PROTO':'https','HTTP_USER_AGENT':'fixture','HTTP_COOKIE':getattr(self,'cookie','') if cookie is None else cookie,'HTTP_X_CSRF_TOKEN':getattr(self,'csrf','') if csrf is None else csrf,'HTTP_ORIGIN':origin,'CONTENT_TYPE':'application/json','CONTENT_LENGTH':str(len(data)),'wsgi.input':io.BytesIO(data)}
        response=[]
        with patch.object(self.app,'limit'):raw=b''.join(self.app(env,lambda s,h:response.append((int(s.split()[0]),dict(h)))))
        status,headers=response[0]
        return status,headers,json.loads(raw) if headers['Content-Type'].startswith('application/json') else raw

    def test_web_and_android_use_same_records_and_conflict_protocol(self):
        for kind,data in [('task',{'title':'Study','completed':0,'assignment':'any','assignees':[],'review':0}),('note',{'body':'Same note'}),('transaction',{'kind':'expense','amount_minor':1250,'currency':'RUB','date':'2026-11-08','label':'Lunch','account_id':None})]:
            op={'id':str(uuid.uuid4()),'action':'record.put','record_id':str(uuid.uuid4()),'revision':0,'kind':kind,'visibility':'private','audience':[],'data':data}
            status,_,result=self.request('/account/api/sync',{'workspace_id':self.wid,'operations':[op]})
            self.assertEqual(status,200); self.assertEqual(result['results'][0]['status'],'accepted')
            self.assertEqual(self.request('/account/api/sync',{'workspace_id':self.wid,'operations':[op]})[2],result)
        android=dispatch(self.backend,'GET','/v1/sync/pull?workspace='+self.wid,{},'Bearer '+self.android)
        self.assertEqual({r['kind'] for r in android['records']},{'task','note','transaction'})
        note=next(r for r in android['records'] if r['kind']=='note')
        op={'id':str(uuid.uuid4()),'action':'record.put','record_id':note['id'],'revision':note['revision'],'kind':'note','visibility':'private','audience':[],'data':{'body':'Edited through Android protocol'}}
        dispatch(self.backend,'POST','/v1/sync/push',{'workspace_id':self.wid,'operations':[op]},'Bearer '+self.android)
        result=self.request('/account/api/sync?workspace='+self.wid)[2]
        self.assertEqual(next(r for r in result['records'] if r['kind']=='note')['data']['body'],op['data']['body'])
        conflict=self.request('/account/api/sync',{'workspace_id':self.wid,'operations':[dict(op,id=str(uuid.uuid4()))]})[2]
        self.assertEqual(conflict['results'][0]['status'],'conflict')

    def test_session_csrf_host_and_space_boundaries(self):
        operation={'workspace_id':self.wid,'operations':[]}
        self.assertEqual(self.request('/account/api/spaces',cookie='')[0],401)
        self.assertEqual(self.request('/account/api/sync',operation,csrf='wrong')[0],403)
        self.assertEqual(self.request('/account/api/sync',operation,origin='https://evil.invalid')[0],403)
        self.assertEqual(self.request('/account/api/sync?workspace='+str(uuid.uuid4()))[0],403)
        self.assertEqual(self.request('/account/api/spaces',host='control.getuladim.space')[0],404)
        self.assertEqual(self.request('/account/api/logout',{})[0],200)
        self.assertEqual(self.request('/account/api/spaces')[0],401)

    def test_pwa_routes_manifest_no_store_and_traversal(self):
        status,headers,html=self.request('/app')
        self.assertEqual(status,200); self.assertIn(b'manifest',html); self.assertEqual(headers['Cache-Control'],'no-store')
        manifest=json.loads(self.request('/app/assets/manifest.webmanifest')[2])
        self.assertEqual(manifest['start_url'],'/app')
        self.assertEqual(self.request('/app/sw.js')[1]['Service-Worker-Allowed'],'/app')
        self.assertEqual(self.request('/app/assets/../index.html')[0],404)
        self.assertEqual(self.request('/app/assets/schema.sql')[0],404)
        self.assertEqual(self.request('/app',host='control.getuladim.space')[0],404)
        catalogs=self.request('/app/assets/locales.json')[2]
        self.assertEqual(len(catalogs),16)
        self.assertEqual({frozenset(p['strings']) for p in catalogs.values()}.__len__(),1)
