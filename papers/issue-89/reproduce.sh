#!/usr/bin/env bash
# Issue #89 — one-command reproduction.
# Runs the canonical experiment (deterministic) and validates two-tier.
set -e
cd "$(dirname "$0")"
PY="${REPRO_PYTHON:-python3}"
echo "== reproduce.sh: using $PY =="
$PY reproduce.py
echo "REPRODUCE: ALL STAGES PASSED"
