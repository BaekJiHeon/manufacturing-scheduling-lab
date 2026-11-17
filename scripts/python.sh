#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd "$(dirname "$0")/.." && pwd)"
if [[ -n "${MANUFACTURING_PYTHON:-}" ]]; then
  python_bin="$MANUFACTURING_PYTHON"
elif [[ -f "$project_root/runtime/python_path.txt" ]]; then
  python_bin="$(cat "$project_root/runtime/python_path.txt")"
else
  python_bin="$project_root/.venv/bin/python"
fi
if [[ ! -x "$python_bin" ]]; then
  echo 'Python runtime missing. Run: bash scripts/setup_python.sh' >&2
  exit 1
fi
export MPLCONFIGDIR="$project_root/.cache/matplotlib"
exec "$python_bin" "$@"
