#!/usr/bin/env bash
# Issue #98 — one-command reproduction: "When Does Proactive Beat Reactive?"
# 1) re-run the deterministic canonical runner (P0-P7) -> canonical_results.json
# 2) assert the artifact sha256 matches the committed reference (byte-identical)
# 3) run the 279-check validator (closed forms + structural invariants)
# Exit 0 only if all three stages pass. Stdlib Python only, no network, no seeds
# to draw (runner is fully deterministic by construction).
set -euo pipefail
cd "$(dirname "$0")"

EXPECTED_SHA="bdd4498e069518931b2990a6d446b1e114ea9cc1190396d5457ecb43b128c985"

echo "== stage 1: canonical runner =="
python3 canonical_runner.py | grep -v "^wrote"

echo
echo "== stage 2: artifact byte-identity =="
SHA=$(python3 -c "import hashlib;print(hashlib.sha256(open('canonical_results.json','rb').read()).hexdigest())")
echo "sha256 $SHA"
if [ "$SHA" != "$EXPECTED_SHA" ]; then
    echo "FAIL: artifact sha differs from committed reference ($EXPECTED_SHA)"
    exit 1
fi
echo "byte-identical: ok"

echo
echo "== stage 3: validator =="
python3 validate.py

echo
echo "REPRODUCE ALL GREEN"
