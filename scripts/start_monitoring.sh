#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# PostgreSQL is disposable tmpfs on this FAT32 host. Rebuild from project artifacts.
docker compose stop grafana
docker compose up -d --wait postgres prometheus
bash scripts/python.sh - <<'PY'
from pathlib import Path
from scripts.ingest_run import ingest
for p in sorted(Path('results/phase1_cpsat').glob('*/metadata.json')):
    if (p.parent/'metrics.csv').exists():ingest(p.parent)
PY
bash scripts/python.sh scripts/restore_extended.py
if [[ "$(docker compose exec -T postgres psql -U demo -d grafana -tAc "SELECT to_regclass('public.migration_log') IS NULL")" == t ]]; then
  snapshot=postgres/grafana_before_tmpfs.sql
  if [[ -f postgres/grafana_latest.sql ]]; then snapshot=postgres/grafana_latest.sql; fi
  if [[ -f "$snapshot" ]]; then
    docker compose exec -T postgres psql -U demo -d grafana -v ON_ERROR_STOP=1 < "$snapshot"
  fi
  # A clean clone has no local login/session backup; Grafana initializes itself.
fi
docker compose up -d grafana
bash scripts/python.sh scripts/start_resource_exporter.py
