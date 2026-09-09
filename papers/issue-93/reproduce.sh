#!/usr/bin/env bash
# Issue #93 one-command reproduction (deterministic; ~4-5 min, stdlib only).
set -euo pipefail
cd "$(dirname "$0")"
echo "== canonical_runner.py (regenerates canonical_results.json) =="
python3 canonical_runner.py
echo "== validate.py (structural laws + byte-identity) =="
python3 validate.py
echo "REPRODUCE ALL GREEN"
