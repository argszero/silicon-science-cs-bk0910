#!/bin/bash
# Issue #96 one-command reproduction: canonical run -> validate -> determinism sha.
# Requires: python3 (stdlib only). Deterministic byte-identical artifact.
set -euo pipefail
cd "$(dirname "$0")"

echo "== [1/3] canonical run =="
python3 canonical_runner.py | tee canonical_run.log

echo "== [2/3] validate =="
python3 validate.py

echo "== [3/3] determinism sha =="
SHA=$(shasum -a 256 canonical_results.json | awk '{print $1}')
echo "sha256 canonical_results.json = $SHA"

echo "== REPRODUCE ALL GREEN =="
