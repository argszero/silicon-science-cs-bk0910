#!/usr/bin/env bash
# Issue #86 one-command reproduction (committed package).
#
#   bash reproduce.sh                  # bootstraps .venv from requirements.txt
#   REPRO_PYTHON=/path/to/python bash reproduce.sh   # use an existing torch venv
#
# Runs all four experiment stages (~13 min single-thread CPU) into repro_out/
# and validates them against the committed reference data (data dirs pm_out/,
# r2_out/, r3_out/, trace_out3/) plus structural claims. Expected final line:
#   VALIDATE: ALL CHECKS PASSED   (30 checks)
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"

if [ -z "${REPRO_PYTHON:-}" ]; then
  if [ ! -x "$HERE/.venv/bin/python" ]; then
    echo "== bootstrap .venv =="
    python3 -m venv "$HERE/.venv"
    "$HERE/.venv/bin/pip" install --quiet -r "$HERE/requirements.txt"
  fi
  PY="$HERE/.venv/bin/python"
else
  PY="$REPRO_PYTHON"
fi
echo "== python: $PY =="
cd "$HERE"
"$PY" reproduce.py repro_out
"$PY" validate.py repro_out
echo "== reproduction + validation complete (repro_out/, logs in repro_out.log) =="
