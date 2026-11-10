"""Fail CI if the shared Android parser changes without rebuilding its web worker."""
import hashlib
import json
from pathlib import Path

root=Path(__file__).resolve().parent.parent
manifest=json.loads((root/'tool/statement-worker-build.json').read_text())
for path,digest in manifest['sha256'].items():
    assert hashlib.sha256((root/path).read_bytes()).hexdigest()==digest, 'Rebuild statement worker: '+path
print('STATEMENT_BUILD_MATCHED',len(manifest['sha256']))
