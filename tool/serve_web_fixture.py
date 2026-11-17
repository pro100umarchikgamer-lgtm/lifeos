"""Loopback-only preview. Synthetic account/data; never a staging production DB."""
import time
from tool.check_web_platform import fixture
# Use the same fixture at a stable port for Lighthouse. The fixture itself binds
# port 0; a local forwarding WSGI app avoids adding any production code path.
from wsgiref.simple_server import make_server
from urllib.request import urlopen, Request
from urllib.error import HTTPError

def main():
    with fixture() as (origin,_,__,___):
        def forward(env,start):
            data=env['wsgi.input'].read(int(env.get('CONTENT_LENGTH') or 0)) if env['REQUEST_METHOD']=='POST' else None
            headers={k[5:].replace('_','-').title():v for k,v in env.items() if k.startswith('HTTP_') and k!='HTTP_HOST'}
            if data is not None:headers['Content-Type']=env.get('CONTENT_TYPE','application/json')
            request=Request(origin+env['PATH_INFO']+('?' + env['QUERY_STRING'] if env.get('QUERY_STRING') else ''),data=data,headers=headers)
            # Same-origin security is preserved at the fixture's own origin.
            if 'Origin' in headers:request.add_header('Origin',origin)
            try:response=urlopen(request)
            except HTTPError as e:response=e
            start(str(response.status)+' Fixture',[(k,v) for k,v in response.headers.items() if k.lower() not in ('transfer-encoding','connection','content-length')])
            return [response.read()]
        with make_server('127.0.0.1',8765,forward) as server:
            print('Synthetic ULADIM preview: http://localhost:8765/app',flush=True)
            server.serve_forever()
if __name__=='__main__':main()
