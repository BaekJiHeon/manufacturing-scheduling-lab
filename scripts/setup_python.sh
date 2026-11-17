#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p runtime logs
# Dependencies are disposable. Research data and results never leave this root.
volume_root="$(python3 - <<'PY2'
import os
from pathlib import Path
p=Path.cwd()
while not os.path.ismount(p):p=p.parent
print(p)
PY2
)"
if [[ "$(uname)" == Darwin ]] && diskutil info "$volume_root" 2>/dev/null | grep -q 'FAT32'; then
  envroot="$(mktemp -d /tmp/manufacturing-rl-python.XXXXXX)"
  echo "FAT32: using disposable dependency environment $envroot"
else
  envroot="$PWD/.python-runtime"
fi
uv venv --python "${MANUFACTURING_PYTHON_VERSION:-3.11}" "$envroot/venv"
UV_CACHE_DIR="$envroot/cache" UV_LINK_MODE=copy uv pip install --python "$envroot/venv/bin/python" -r requirements.lock.txt
printf '%s\n' "$envroot/venv/bin/python" > runtime/python_path.txt
