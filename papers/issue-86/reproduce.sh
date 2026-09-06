#!/usr/bin/env bash
# Issue #86 one-command reproduction (committed package, revision v1.1).
#
#   bash reproduce.sh                  # bootstraps .venv from requirements.txt
#   REPRO_PYTHON=/path/to/python bash reproduce.sh   # use an existing torch venv
#
# Runs all four experiment stages (~13-22 min single-thread CPU) into repro_out/
# and validates them with validate.py (two-tier, environment-tolerant):
#   Tier A = structural claims that hold in ANY environment (region geometry,
#   r2 freeze arms, fp64, effective-sharpness refutation, trace protocol,
#   boundary rare-event bound).
#   Tier B = banded comparisons against the committed reference data (clean
#   cells stay clean; spiking cells keep presence; heavy-cell means within a
#   band; P1/P2 accord rates inside the committed Wilson CIs).
# Exact per-run spike counts are environment-chaotic (see manuscript §5) and
# are NOT asserted. Expected final line:
#   VALIDATE: ALL CHECKS PASSED   (24 checks)
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
echo "== reproduction + validation complete (repro_out/) =="
