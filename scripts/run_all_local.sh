#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export MPLCONFIGDIR="$PWD/.cache/matplotlib"
bash scripts/python.sh -m pytest -q tests/test_core.py --basetemp=runtime/pytest-tmp
bash scripts/python.sh -m src.evaluation.run_phase01 --config configs/experiments/phase1.yaml
