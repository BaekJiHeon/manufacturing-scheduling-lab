#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -f runtime/python_path.txt ]] || [[ ! -x "$(cat runtime/python_path.txt)" ]]; then
  bash scripts/setup_python.sh
fi
training_cache="$(mktemp -d /tmp/manufacturing-training-cache.XXXXXX)"
UV_CACHE_DIR="$training_cache" UV_LINK_MODE=copy uv pip install --python "$(cat runtime/python_path.txt)" -r requirements.training.lock.txt
