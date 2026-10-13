#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose ps
free=$(df -P . | awk 'NR==2{gsub(/%/,"",$5);print 100-$5}')
(( free >= 15 )) || { echo 'WARNING: less than 15% host disk free; inspect storage and backups. Nothing deleted.'; exit 1; }
docker compose exec -T api python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health/ready',timeout=3).read().decode()); print(urllib.request.urlopen('http://127.0.0.1:8000/metrics',timeout=3).read().decode())"
