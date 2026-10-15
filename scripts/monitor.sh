#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose ps
free=$(df -P . | awk 'NR==2{gsub(/%/,"",$5);print 100-$5}')
(( free >= 15 )) || { echo 'WARNING: less than 15% host disk free; inspect storage and backups. Nothing deleted.'; exit 1; }
docker compose exec -T api python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health/ready',timeout=3).read().decode()); print(urllib.request.urlopen('http://127.0.0.1:8000/metrics',timeout=3).read().decode())"
docker compose exec -T mail python -c "import pathlib,time; assert time.time()-pathlib.Path('/tmp/lifeos-mail.heartbeat').stat().st_mtime<120, 'Mail worker heartbeat is stale'"
if [[ -n "${1:-}" ]]; then
  python3 - "$1" <<'PY'
from pathlib import Path
import sys,time
archives=[p for p in Path(sys.argv[1]).glob('*.pgdump.aesgcm') if p.is_file() and p.stat().st_size>0]
if not archives or time.time()-max(p.stat().st_mtime for p in archives)>36*3600:
    raise SystemExit('WARNING: no completed encrypted backup within 36 hours. Nothing deleted.')
print('Encrypted backup freshness: OK')
PY
fi
