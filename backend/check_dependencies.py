"""Fail a staged image before migration if its installed pins are stale."""
from importlib.metadata import version
from pathlib import Path


def verify():
    for line in Path(__file__).with_name('requirements.txt').read_text().splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        name, expected = line.split('==')
        package = name.split('[', 1)[0]
        if version(package) != expected:
            raise RuntimeError('Installed dependency differs from pin: ' + package)
        if name == 'psycopg[binary]' and version('psycopg-binary') != expected:
            raise RuntimeError('psycopg binary adapter differs from pin')


if __name__ == '__main__':
    verify()
