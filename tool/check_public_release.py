"""Credential-free HTTPS acceptance; preserves proxy settings and does not send mail.

Run from the repository root. This complements the VPS monitor's direct DNS/TLS
checks, which cannot run through a DNS-isolating workstation proxy.
"""
import concurrent.futures
import hashlib
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SITE = 'https://getuladim.space'
CASES = []


def add(path, expected=200, *, host=SITE, body=None, origin=None, asset=None):
    CASES.append((host, path, expected, body, origin, asset))


for path in ('/', '/early-access', '/account', '/plans', '/privacy', '/terms',
             '/status', '/support', '/app', '/app/'):
    add(path)
for name in ('app.js', 'app.css', 'locales.json', 'manifest.webmanifest',
             'offline.html', 'offline.js', 'icon-192.png', 'icon-512.png',
             'apple-touch-icon.png'):
    add('/app/assets/' + name, asset='backend/webassets/app/' + name)
add('/app/sw.js', asset='backend/webassets/app/sw.js')
for name in ('web.js', 'web.css'):
    add('/assets/' + name, asset='backend/webassets/' + name)
for path in ('/metrics', '/health/ready', '/control/api/applications',
             '/app/assets/config.py'):
    add(path, 404)
for path in ('/account/api/session', '/account/api/spaces',
             '/account/api/sync', '/account/api/entitlements'):
    add(path, 401)
add('/account/api/signup', 403, body={
    'email': 'no-invitation@example.invalid', 'password': 'synthetic-gate-check'}, origin=SITE)
add('/account/api/staff/enrollment', 401, body={'owner': True}, origin=SITE)
for action in ('status', 'cancel'):
    add('/early-access/api/' + action, 401,
        body={'management_token': 'x' * 43}, origin=SITE)
add('/early-access/api/apply', 403, body={}, origin='https://example.invalid')
for host in ('https://api.getuladim.space', 'https://control.getuladim.space'):
    add('/', 503, host=host)
    add('/control/api/login', 503, host=host, body={})
    add('/v1/auth/register', 503, host=host, body={})
    add('/metrics', 404, host=host)
    add('/health/ready', 404, host=host)


def check(case):
    host, path, expected, body, origin, asset = case
    headers = {'User-Agent': 'ULADIM-release-acceptance/1'}
    if body is not None:
        headers['Content-Type'] = 'application/json'
    if origin:
        headers['Origin'] = origin
    request = urllib.request.Request(host + path,
        data=json.dumps(body).encode() if body is not None else None, headers=headers)
    started = time.monotonic()
    result = {'url': host + path, 'method': request.get_method(), 'expected': expected}
    try:
        try:
            response = urllib.request.urlopen(request, timeout=30)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            data = response.read()
            result['status'] = response.status
            assert response.status == expected, f'HTTP {response.status}, expected {expected}'
            assert response.headers.get('Set-Cookie') is None, 'unexpected cookie'
            assert response.headers.get('X-Content-Type-Options') == 'nosniff', 'missing nosniff'
            # Caddy's private-route 404s have no HTML and do not use app headers.
            if host == SITE and path not in ('/metrics', '/health/ready', '/control/api/applications'):
                assert "frame-ancestors 'none'" in response.headers.get('Content-Security-Policy', ''), 'missing frame protection'
            if ('/api/' in path and expected != 404) or expected == 503:
                assert response.headers.get('Cache-Control') == 'no-store', 'missing no-store'
            if expected == 503:
                assert response.headers.get('Retry-After') == '3600'
            if asset:
                digest = hashlib.sha256(data).hexdigest()
                assert digest == hashlib.sha256(Path(asset).read_bytes()).hexdigest(), 'asset differs from reviewed source'
                result['sha256'] = digest
            if path == '/app/sw.js':
                assert response.headers.get('Service-Worker-Allowed') == '/app'
            if path.endswith('/manifest.webmanifest'):
                manifest = json.loads(data)
                assert manifest['start_url'] == '/app' and manifest['display'] == 'standalone'
            if path.endswith('/locales.json'):
                assert len(json.loads(data)) == 16
            result['passed'] = True
    except Exception as error:
        result.update(passed=False, failure=str(error))
    result['seconds'] = round(time.monotonic() - started, 3)
    return result


def main():
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(check, CASES))
    report = {'at': datetime.now(timezone.utc).isoformat(),
              'scope': 'Real HTTPS, no accounts, credentials, accepted applications or outgoing mail; proxy TLS trust, no direct DNS/certificate inspection',
              'passed': sum(r['passed'] for r in results), 'total': len(results), 'checks': results}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report['passed'] == report['total'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
