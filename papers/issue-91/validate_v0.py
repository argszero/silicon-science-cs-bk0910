#!/usr/bin/env python3
"""Issue #91 — validator v0 (R224). Independent checks over the canonical run.

Tier A (structural, deterministic facts about the model, recomputed here from
first principles with code paths independent of canonical_runner.py):
  A1  support: regret == 0 for every query with d/w > 1 (P1 strong form)
  A2  oracle identity: argmin switches exactly at each analytic boundary
  A3  flip profile: aggregate |flip_rate - (1-dw)/2| stays < 0.05 everywhere
      (universal window geometry)
  A4  P3 crossover: oracle switch point == analytic (N-P)/(M*N) for all M
Tier B (value checks over canonical_results.json):
  B1  schema/consistency: all 7 boundaries x 5 eps rows present
  B2  P2 law: median H/(w/12) ratio in [0.7, 1.4]; p10/p90 in [0.3, 2.0]
  B3  miscalibration band: ~1.00 decade (=25.0% of the log range)
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import toy_regret_core as core

PASS, FAIL = [], []
def check(name, ok, detail=''):
    (PASS if ok else FAIL).append(name)
    print('  [%s] %s %s' % ('PASS' if ok else 'FAIL', name, detail))

# ---- families (duplicated, independent of canonical_runner) ---------------
class FamilyA:
    @staticmethod
    def costs(s):
        return [10.0 + 1000.0 * s, 60.0 + 100.0 * s * s, 500.0 - 400.0 * s]
    @staticmethod
    def boundaries():
        return [(10.0 - math.sqrt(98.0)) / 2.0, -2.0 + math.sqrt(8.4)]
class FamilyB:
    @staticmethod
    def costs(s):
        return [60.0 + 100.0 * s, 10.0 + 200.0 * s]
    @staticmethod
    def boundaries():
        return [0.50]

def mkC(M):
    class F:
        @staticmethod
        def costs(s):
            return [10000.0, 10.0 + M * s * 10000.0]
        @staticmethod
        def boundaries():
            return [(10000.0 - 10.0) / (M * 10000.0)]
    return F
OBJS = [('A', FamilyA()), ('B', FamilyB())] + [('C%d' % M, mkC(M)) for M in [1, 10, 100, 1000]]

print('Tier A — structural facts')

viol = 0
for _, fam in OBJS:
    for eps in core.EPS_LEVELS:
        for seed in core.SEEDS:
            for s, r in core.run_cell(fam, eps, seed):
                if r > 0:
                    dw = min(abs(math.log(s / b)) for b in fam.boundaries())
                    if dw > math.log(1 + eps) * (1 + 1e-9):
                        viol += 1
check('A1 support (0 out-of-band flips)', viol == 0, 'viol=%d' % viol)

# A2 oracle identity at analytic boundaries
bad = []
for label, fam in OBJS:
    for b in fam.boundaries():
        for s, want in [(b * (1 - 1e-7), None), (b * (1 + 1e-7), None)]:
            pass
        lo = core.argmin_costs(fam.costs(b * (1 - 1e-9)))
        hi = core.argmin_costs(fam.costs(b * (1 + 1e-9)))
        if lo == hi:
            bad.append((label, b, lo, hi))
check('A2 oracle flips at every analytic boundary', len(bad) == 0, str(bad[:3]))

# A3 flip profile vs (1-dw)/2 (aggregated across all families and eps)
buckets = {}
for label, fam in OBJS:
    for eps in core.EPS_LEVELS:
        for seed in core.SEEDS:
            for s, r in core.run_cell(fam, eps, seed):
                dw = min(abs(math.log(s / b)) for b in fam.boundaries()) / math.log(1 + eps)
                if dw >= 1.0:
                    continue
                k = math.floor(dw / 0.1) * 0.1
                bkt = buckets.setdefault(k, {'n': 0, 'flip': 0})
                bkt['n'] += 1
                if r > 0:
                    bkt['flip'] += 1
worst = 0.0
for k, bkt in buckets.items():
    rate = bkt['flip'] / bkt['n']
    theory = max(0.0, (1.0 - (k + 0.05)) / 2.0)
    worst = max(worst, abs(rate - theory))
check('A3 flip profile tracks (1-dw)/2 (worst |err| < 0.05)',
      worst < 0.05, 'worst=%.4f' % worst)

# A4 P3 crossover exactness
okC = True
for M in [1, 10, 100, 1000]:
    fam = mkC(M)
    b_an = fam.boundaries()[0]
    lo = core.argmin_costs(fam.costs(b_an * (1 - 1e-9)))
    hi = core.argmin_costs(fam.costs(b_an * (1 + 1e-9)))
    if not (lo == 1 and hi == 0):     # index below, scan above
        okC = False
check('A4 P3: oracle switches index<->scan exactly at s*(M)', okC)

print('Tier B — canonical_results.json value checks')
rj = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'canonical_results.json')
with open(rj) as f:
    res = json.load(f)

rows = res['p2_per_boundary']
labels = sorted(set(r['boundary'] for r in rows))
check('B1 schema: 7 boundaries x 5 eps = 35 rows',
      len(rows) == 35 and len(labels) == 7, 'rows=%d labels=%d' % (len(rows), len(labels)))

ratios = sorted(r['ratio'] for r in rows if r['ratio'] is not None)
med = ratios[len(ratios) // 2]
p10, p90 = ratios[len(ratios) // 10], ratios[9 * len(ratios) // 10]
check('B2 P2 law: median H/(w/12) in [0.7,1.4], p10/p90 in [0.3,2.0]',
      0.7 <= med <= 1.4 and 0.3 <= p10 and p90 <= 2.0,
      'med=%.3f p10=%.3f p90=%.3f' % (med, p10, p90))

mb = res['p3']['miscal_band']
check('B3 miscalibration band ~1.00 decade / 25% log range',
      abs(mb['decades'] - 1.0) < 1e-6 and abs(mb['log_range_fraction'] - 0.25) < 1e-6,
      'decades=%.4f frac=%.4f' % (mb['decades'], mb['log_range_fraction']))

print('\n%d/%d checks passed' % (len(PASS), len(PASS) + len(FAIL)))
sys.exit(0 if not FAIL else 1)
