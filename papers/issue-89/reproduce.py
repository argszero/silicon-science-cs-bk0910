#!/usr/bin/env python3
"""Issue #89 — one-command reproduction (stage 1 of reproduce.sh).

Runs the canonical experiment (deterministic, fixed seeds) and writes
expected_output.json in the canonical/ directory. validate.py (stage 2)
compares the fresh output against the committed reference and checks the
structural laws.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CANON = HERE  # reproduce.py lives alongside canonical_exp.py

def main():
    print('== Issue #89 reproduction: stage 1 (canonical experiment) ==')
    r = subprocess.run([sys.executable, os.path.join(CANON, 'canonical_exp.py')],
                       cwd=CANON)
    if r.returncode != 0:
        print('stage 1 FAILED')
        sys.exit(1)
    print('stage 1 OK: expected_output.json regenerated (deterministic)')
    print('== stage 2 (two-tier validation) ==')
    r2 = subprocess.run([sys.executable, os.path.join(HERE, 'validate.py')],
                        cwd=HERE)
    if r2.returncode != 0:
        print('stage 2 FAILED')
        sys.exit(1)
    print('REPRODUCE: ALL STAGES PASSED')

if __name__ == '__main__':
    main()
