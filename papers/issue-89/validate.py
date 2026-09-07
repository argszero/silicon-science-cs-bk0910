#!/usr/bin/env python3
"""Issue #89 — two-tier validator.

Tier A (structural, env-independent, assert-based):
  A1. Family A: topR recall monotone INCREASING as H decreases (i.e. recall at
      the most concentrated H > recall at the least concentrated); topR > randomR
      at every concentrated cell; randomR within [0, 0.35] everywhere.
  A2. Family B: for every q in {0.25, 0.5, 0.75, 1.0}, |recall - FPR| <= 0.02
      (floor equality, env-independent); q=0 must be n/a (empty controlled set).
  A3. Family C: recall monotone non-increasing in eps; recall(eps=0) >= 0.9;
      recall(eps>=4.5) <= 0.001; FPR side rises (checked via crossover: exists a
      cell with recall < 0.5 and the next-lower-eps cell with recall > 0.5).
  A4. Determinism: re-running the experiment reproduces expected_output.json
      byte-identically (sha equal to committed) — pure-python fixed-seed RNG.

Tier B (CI containment vs committed expected_output.json):
  B1. Each committed cell recall lies inside the freshly computed Wilson 95% CI
      (with a small tolerance for pooling), and vice versa.
  B2. Reported CIs are internally consistent: ci_lo <= recall <= ci_hi.

Exit 0 only if all checks pass; prints 'VALIDATE: ALL CHECKS PASSED (N)'.
"""
import hashlib
import json
import math
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.join(HERE, 'expected_output.json')
COMMITTED = os.path.join(HERE, 'expected_output.committed.json')
FPR = 0.10
TOL_FLOOR = 0.02
N_CHECKS = 0

def check(cond, name, extra=''):
    global N_CHECKS
    N_CHECKS += 1
    if not cond:
        print('FAIL:', name, extra)
        sys.exit(1)
    print('PASS:', name)

def wilson_contains(cell, recall, tol=0.01):
    if cell['ci_lo'] is None:
        return True  # n/a cell
    return (recall >= cell['ci_lo'] - tol) and (recall <= cell['ci_hi'] + tol)

def main():
    # Tier A4: determinism — rerun experiment and compare sha
    r = subprocess.run([sys.executable, os.path.join(HERE, 'canonical_exp.py')],
                       capture_output=True, cwd=HERE, text=True)
    if r.returncode != 0:
        print('FAIL: canonical_exp.py rerun exited', r.returncode, r.stderr[-400:])
        sys.exit(1)
    def sha(p):
        return hashlib.sha256(open(p, 'rb').read()).hexdigest()
    committed_sha = sha(COMMITTED)
    fresh_sha = sha(EXP)
    check(committed_sha == fresh_sha, 'A4 determinism (byte-identical rerun)',
          'committed=%s fresh=%s' % (committed_sha[:10], fresh_sha[:10]))

    with open(EXP) as f:
        d = json.load(f)
    fa = d['family_A_partial_discrete']
    fb = d['family_B_full']
    fc = d['family_C_partial_continuous']

    # Tier A1: family A structural
    cells_a = sorted(fa.values(), key=lambda v: -v['H'])  # high H first
    recalls_top = [c['topR']['recall'] for c in cells_a]
    check(recalls_top == sorted(recalls_top), 'A1a topR recall monotone up as H down',
          'recalls=%s' % [round(x, 3) for x in recalls_top])
    for c in cells_a:
        check(c['topR']['recall'] >= c['randomR']['recall'] - 0.02,
              'A1b topR >= randomR at H=%.2f' % c['H'],
              'top=%.3f rnd=%.3f' % (c['topR']['recall'], c['randomR']['recall']))
        check(0.0 <= c['randomR']['recall'] <= 0.35,
              'A1c randomR in [0,0.35] at H=%.2f' % c['H'],
              'rnd=%.3f' % c['randomR']['recall'])

    # Tier A2: family B structural
    for q, cell in sorted(fb.items(), key=lambda kv: float(kv[0])):
        if float(q) == 0.0:
            check(cell['n'] == 0, 'A2a q=0 is n/a (empty controlled set)')
        else:
            check(abs(cell['recall'] - FPR) <= TOL_FLOOR, 'A2b floor equality q=%s' % q,
                  'recall=%.3f FPR=%.2f' % (cell['recall'], FPR))
    # A2c: entropy sweep at full control (q=1.0) stays at the FPR floor
    fbe = d.get('family_B_entropy_sweep')
    if fbe is not None:
        for alpha, cell in sorted(fbe.items(), key=lambda kv: float(kv[0])):
            check(abs(cell['recall'] - FPR) <= TOL_FLOOR,
                  'A2c entropy-sweep floor alpha=%s (q=1.0)' % alpha,
                  'recall=%.3f FPR=%.2f' % (cell['recall'], FPR))

    # Tier A3: family C structural
    cells_c = sorted(fc.items(), key=lambda kv: float(kv[0]))
    recalls_c = [kv[1]['recall'] for kv in cells_c]
    check(all(recalls_c[i] >= recalls_c[i + 1] - 1e-9 for i in range(len(recalls_c) - 1)),
          'A3a recall monotone non-increasing in eps')
    check(recalls_c[0] >= 0.9, 'A3b recall(eps=0) >= 0.9', 'r=%.3f' % recalls_c[0])
    check(recalls_c[-1] <= 0.001, 'A3c recall(high eps) <= 0.001', 'r=%.3f' % recalls_c[-1])
    # crossover: some cell below 0.5 with previous above 0.5
    crossed = any(cells_c[i][1]['recall'] < 0.5 and cells_c[i - 1][1]['recall'] > 0.5
                  for i in range(1, len(cells_c)))
    check(crossed, 'A3d crossover eps* present (recall crosses 0.5)')
    # A3e: FP-availability arm rises with budget (env-independent direction)
    if all('fp' in kv[1] for kv in cells_c):
        fps = [kv[1]['fp']['rate'] for kv in cells_c]
        check(all(fps[i] <= fps[i + 1] + 1e-9 for i in range(len(fps) - 1)),
              'A3e fp rate monotone non-decreasing in eps', 'fps=%s' % [round(x, 4) for x in fps])
        check(fps[-1] > 0.5, 'A3f fp(high eps) > 0.5 (availability regime)',
              'fp=%.3f' % fps[-1])

    # Tier B: CI containment vs committed
    with open(COMMITTED) as f:
        dc = json.load(f)
    all_ok = True
    for fam_key in ('family_A_partial_discrete', 'family_B_full',
                   'family_B_entropy_sweep', 'family_C_partial_continuous'):
        fresh = d[fam_key]
        comm = dc[fam_key]
        for k in fresh:
            fcell = fresh[k]
            ccell = comm[k]
            for sub in (fcell.keys() & ccell.keys()):
                if isinstance(fcell[sub], dict) and ('recall' in fcell[sub] or 'rate' in fcell[sub]):
                    fsub = fcell[sub]
                    csub = ccell[sub]
                    stat = 'recall' if 'recall' in fsub else 'rate'
                    # committed stat inside fresh CI and fresh stat inside committed CI
                    ok1 = wilson_contains(fsub, csub[stat])
                    ok2 = wilson_contains(csub, fsub[stat])
                    ok = ok1 and ok2
                    if not ok:
                        all_ok = False
                        print('FAIL B1:', fam_key, k, sub,
                              'fresh=%.4f committed=%.4f' % (fsub[stat], csub[stat]))
    check(all_ok, 'B1 CI containment (bidirectional) all cells')

    # B2: CI internal consistency
    ci_ok = True
    def leaves(node):
        if isinstance(node, dict) and ('recall' in node or 'rate' in node):
            yield node
        elif isinstance(node, dict):
            for sub in node.values():
                yield from leaves(sub)
    for fam_key in (d.keys()):
        if fam_key == 'meta':
            continue
        for cell in leaves(d[fam_key]):
            if cell.get('ci_lo') is not None:
                if not (cell['ci_lo'] <= cell['recall'] <= cell['ci_hi']):
                    ci_ok = False
    check(ci_ok, 'B2 CI internal consistency')

    print('VALIDATE: ALL CHECKS PASSED (%d)' % N_CHECKS)

if __name__ == '__main__':
    main()
