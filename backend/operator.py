"""Local operator commands. Secret enrollment material is written once to a 0600 file."""
import argparse
import json
import os
from pathlib import Path
from cryptography.fernet import Fernet
from .config import Settings
from .control import Control
from .postgres import PostgresBackend


def write_private(path, action):
    # Reserve output before any account mutation. Never overwrite existing material.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as output:
        value = action()
        json.dump(value, output, ensure_ascii=False)
        output.flush()
        os.fsync(output.fileno())


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    owner = sub.add_parser('bootstrap-owner')
    owner.add_argument('--email', required=True)
    owner.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    settings = Settings.load()
    backend = PostgresBackend(settings.database_url, Fernet(settings.email_queue_key.encode()))
    try:
        write_private(args.output, lambda: Control(backend).bootstrap(args.email))
        print('Enrollment written to the private output file. Store it offline; MFA is mandatory.')
    finally:
        backend.close()

if __name__ == '__main__': main()
