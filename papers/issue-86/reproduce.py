#!/usr/bin/env python3
"""Issue #86 reproduce.py: regenerate every experiment behind the manuscript.

Runs the four canonical experiment scripts into a fresh output tree:
  phase_map.py     -> 60 phase-map runs (4 lr x 5 wd x 3 seeds, 20k steps)
  freeze_fp64.py   -> r2_results.jsonl (16 runs: freeze arms 6 + fp64 4 + deep 6)
  restricted_lam.py-> r3_results.jsonl (7 runs)
  trace_runs.py    -> 4 trace_*.json runs (fig3)

Stages are resumable: a stage whose output dir already contains the expected
file/row counts is skipped (crash-safe — a half-written stage reruns).

Usage: <venv python> reproduce.py [outbase]
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
OUTBASE = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'repro_out')
PY = sys.executable

STAGES = [
    ('phase_map.py', 'pm', 60, None, None),
    ('freeze_fp64.py', 'r2', 1, 16, 'r2_results.jsonl'),
    ('restricted_lam.py', 'r3', 1, 7, 'r3_results.jsonl'),
    ('trace_runs.py', 'trace', 4, None, None),
]


def stage_done(outdir, expect_files, expect_rows, rowfile):
    if not os.path.isdir(outdir):
        return False
    files = os.listdir(outdir)
    if len(files) != expect_files:
        return False
    if expect_rows is not None:
        try:
            with open(os.path.join(outdir, rowfile)) as f:
                n = sum(1 for line in f if line.strip())
            return n == expect_rows
        except OSError:
            return False
    return True


def main():
    os.makedirs(OUTBASE, exist_ok=True)
    print('reproduce.py: outbase %s, python %s' % (OUTBASE, PY), flush=True)
    t_start = time.time()
    for script, sub, expect_files, expect_rows, rowfile in STAGES:
        outdir = os.path.join(OUTBASE, sub)
        if stage_done(outdir, expect_files, expect_rows, rowfile):
            print('--- %s: already complete, skipping (resume)' % script, flush=True)
            continue
        os.makedirs(outdir, exist_ok=True)
        t0 = time.time()
        print('--- running %s -> %s' % (script, outdir), flush=True)
        r = subprocess.run([PY, os.path.join(HERE, script), outdir])
        if r.returncode != 0:
            sys.exit('ERROR: %s failed with rc=%d' % (script, r.returncode))
        if not stage_done(outdir, expect_files, expect_rows, rowfile):
            sys.exit('ERROR: %s outputs incomplete (files=%d want=%d rows=%s)' % (
                script, len(os.listdir(outdir)), expect_files, expect_rows))
        print('--- %s OK in %.0fs' % (script, time.time() - t0), flush=True)
    print('ALL STAGES COMPLETE in %.0fs -> %s' % (time.time() - t_start, OUTBASE), flush=True)


if __name__ == '__main__':
    main()
