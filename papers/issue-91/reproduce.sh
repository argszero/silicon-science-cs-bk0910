#!/usr/bin/env bash
# Issue #91 — one-command reproduction (R225)
#   bash reproduce.sh
# Runs the canonical study end-to-end and validates it.
# Expected outcome: canonical runner emits canonical_results.json; validator
# reports 7/7 checks passed.  Deterministic (fixed seeds 0..7, pure stdlib);
# canonical_results.json must be byte-identical across runs.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo "==> canonical_runner.py (3 families x 7 boundaries x 5 eps x 8 seeds)"
python3 canonical_runner.py > canonical_run.log
tail -1 canonical_run.log

echo "==> validate_v0.py (two-tier: structural + value checks)"
python3 validate_v0.py | tee canonical_validate.log
if ! grep -q "7/7 checks passed" canonical_validate.log; then
  echo "FAIL: validator did not report 7/7" >&2
  exit 1
fi

echo "==> residual_analysis.py (per-cell window counts + 95% CIs on H/(w/12))"
python3 residual_analysis.py > residual_run.log 2>&1 || { echo "FAIL: residual analysis" >&2; exit 1; }
tail -1 residual_run.log

echo "==> checksum"
shasum -a 256 canonical_results.json

echo "ALL GREEN: canonical run + validate 7/7 + residual analysis (see canonical_run.log / canonical_validate.log / residual_run.log)"
