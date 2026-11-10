"""Compile the authoritative Android domain parser into a bounded browser worker."""
import os
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent

def main():
    dart = os.environ.get('DART', 'dart')
    with tempfile.TemporaryDirectory(prefix='uladim-statement-') as temporary:
        work = Path(temporary)
        shutil.copytree(ROOT / 'lib/domain', work / 'domain')
        shutil.copy(ROOT / 'tool/statement_worker.dart', work / 'worker.dart')
        (work / 'pubspec.yaml').write_text("name: uladim_statement_worker\nenvironment:\n  sdk: '>=3.10.0 <4.0.0'\ndependencies:\n  cryptography: 2.7.0\n")
        lock = ROOT / 'tool/statement_worker.pubspec.lock'
        if lock.exists(): shutil.copy(lock, work / 'pubspec.lock')
        subprocess.run([dart, 'pub', 'get', *(['--enforce-lockfile'] if lock.exists() else [])], cwd=work, check=True)
        shutil.copy(work / 'pubspec.lock', lock)
        subprocess.run([dart, 'compile', 'js', '-O2', '--no-source-maps', '-o',
                        str(ROOT / 'backend/webassets/app/statement-worker.js'), 'worker.dart'], cwd=work, check=True)
        (ROOT / 'backend/webassets/app/statement-worker.js.deps').unlink(missing_ok=True)
        sources = ['tool/statement_worker.dart', 'tool/statement_worker.pubspec.lock',
                   *['lib/domain/' + name + '.dart' for name in ('statement_import','statement_detection','models','calendar_models','offline_models','finance_engine')],
                   'backend/webassets/app/statement-worker.js']
        hashes = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in sources}
        (ROOT / 'tool/statement-worker-build.json').write_text(json.dumps({
            'sdk': subprocess.check_output([dart, '--version'], text=True).strip(),
            'sha256': hashes}, indent=2) + '\n')

if __name__ == '__main__': main()
