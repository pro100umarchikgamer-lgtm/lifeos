#!/usr/bin/env python3
"""Verify real HTTPS and closed-test application intake. No credentials or accounts are used."""
import hashlib
import json
from pathlib import Path
import socket
import ssl
import sys
import urllib.error
import urllib.request

SITE = 'getuladim.space'
API = 'api.getuladim.space'
CONTROL = 'control.getuladim.space'
IP = '187.126.10.198'
records = []

def request(host, path='/', expected=200, method='GET'):
    data = b'{}' if method == 'POST' else None
    req = urllib.request.Request('https://' + host + path, data=data, method=method,
                                 headers={'Content-Type': 'application/json'} if data else {})
    try:
        response = urllib.request.urlopen(req, timeout=20)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        body = response.read()
        assert response.status == expected, (host, path, response.status)
        assert response.headers.get('Set-Cookie') is None, (host, path, 'unexpected cookie')
        if expected == 503:
            assert response.headers.get('Retry-After') == '3600'
            assert response.headers.get('Cache-Control') == 'no-store'
        records.append({'host': host, 'path': path, 'method': method, 'status': response.status})
        return body, response.headers

for host in (SITE, API, CONTROL):
    addresses = sorted({x[4][0] for x in socket.getaddrinfo(host, 443, socket.AF_INET)})
    assert addresses == [IP], (host, addresses)
    context = ssl.create_default_context()
    with socket.create_connection((host, 443), timeout=15) as raw:
        with context.wrap_socket(raw, server_hostname=host) as tls:
            cert = tls.getpeercert()
            records.append({'host': host, 'tls': tls.version(), 'expires': cert['notAfter']})

body, headers = request(SITE)
assert b'data-surface="site"' in body
assert 'ULADIM'.encode() in body
assert "frame-ancestors 'none'" in headers['Content-Security-Policy']
assert headers['X-Content-Type-Options'] == 'nosniff'
for filename in ('web.js', 'web.css'):
    payload, _ = request(SITE, '/assets/' + filename)
    original = Path('backend/webassets', filename).read_bytes()
    assert hashlib.sha256(payload).digest() == hashlib.sha256(original).digest(), filename
for path in ('/privacy', '/terms', '/status', '/support', '/early-access', '/docs', '/plans', '/account'):
    request(SITE, path)
request(SITE, '/early-access/api/apply', 403, 'POST')
request(SITE, '/account/api/signup', 403, 'POST')
request(SITE, '/control/api/login', 404, 'POST')
for host in (API, CONTROL):
    request(host, expected=503)
    request(host, '/v1/auth/register', 503, 'POST')
    request(host, '/account/api/register', 503, 'POST')
    request(host, '/control/api/login', 503, 'POST')
    request(host, '/sync/push', 503, 'POST')
for host in (SITE, API, CONTROL):
    request(host, '/metrics', 404)
    request(host, '/health/ready', 404)
with urllib.request.urlopen('http://' + SITE, timeout=20) as response:
    assert response.url == 'https://' + SITE + '/'
print('HTTPS_EDGE_ACCEPTANCE_OK', len(records), 'checks') if '--quiet' in sys.argv else print(json.dumps({'result': 'HTTPS_EDGE_ACCEPTANCE_OK', 'checks': records}, indent=2))

