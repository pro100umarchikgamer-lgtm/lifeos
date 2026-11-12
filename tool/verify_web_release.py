"""Compare public release assets with this source using normal TLS verification."""
import argparse
import hashlib
from pathlib import Path
from urllib.request import Request, urlopen

ASSETS = {
    '/app/assets/auth-texture.webp': 'backend/webassets/app/auth-texture.webp',
    '/app/assets/app.js': 'backend/webassets/app/app.js',
    '/app/assets/import.js': 'backend/webassets/app/import.js',
    '/app/assets/statement-formats.js': 'backend/webassets/app/statement-formats.js',
    '/app/sw.js': 'backend/webassets/app/sw.js',
    '/assets/design.css': 'backend/webassets/design.css',
    '/assets/web.js': 'backend/webassets/web.js',
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--origin', default='https://getuladim.space')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    failed = []
    for url, source in ASSETS.items():
        expected = hashlib.sha256((root / source).read_bytes()).hexdigest()
        request = Request(args.origin.rstrip('/') + url, headers={'Cache-Control': 'no-cache'})
        with urlopen(request, timeout=20) as response:
            actual = hashlib.sha256(response.read()).hexdigest()
        if actual != expected:
            failed.append(url)
        print(('MATCH' if actual == expected else 'MISMATCH'), url, actual)
    if failed:
        raise SystemExit('Release assets differ: ' + ', '.join(failed))
    print('WEB_RELEASE_ASSETS_VERIFIED')


if __name__ == '__main__':
    main()
