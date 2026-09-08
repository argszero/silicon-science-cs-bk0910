#!/usr/bin/env python3
"""Issue #91 — canonical consolidated runner (R224).

Runs the full 3-family study deterministically and emits canonical_results.json:
  - per-boundary P2 table: H vs w/12 law across 7 boundaries x 5 eps
  - cross-family flip-profile collapse (flip rate vs d/w on top of (1-dw)/2)
  - P3 crossover-shift law for Family C (s*(M) ~ 1/M) + miscalibration band

Deterministic: fixed seeds 0..7, 2000 queries/cell, pure stdlib. Output JSON is
the byte-identical artifact a validator checks.
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import toy_regret_core as core

# --------------------------------------------------------------------------
# Families (single source of truth; A/B/C as in smokes)
# --------------------------------------------------------------------------
N_C = 10_000      # family C rows
P_C = 10          # family C probe cost
M_SWEEP = [1, 10, 100, 1000]

class FamilyA:
    name = 'A_filtered_ANN_3strategy'
    @staticmethod
    def costs(s):
        return [10.0 + 1000.0 * s, 60.0 + 100.0 * s * s, 500.0 - 400.0 * s]
    @staticmethod
    def boundaries():
        return [(10.0 - math.sqrt(98.0)) / 2.0, -2.0 + math.sqrt(8.4)]
    PAIRS = [(0, 1), (1, 2)]   # boundary b_k crosses strategies (pairs[k])

class FamilyB:
    name = 'B_joinorder_pairwise'
    @staticmethod
    def costs(s):
        return [60.0 + 100.0 * s, 10.0 + 200.0 * s]
    @staticmethod
    def boundaries():
        return [0.50]
    PAIRS = [(0, 1)]

def make_familyC(M):
    return type('FamilyC', (), {
        'name': 'C_index_vs_scan_M%d' % M,
        'M': M,
        'costs': staticmethod(lambda s, M=M: [N_C, P_C + M * s * N_C]),
        'boundaries': staticmethod(lambda M=M: [(N_C - P_C) / (M * N_C)]),
        'PAIRS': [(0, 1)],
    })

ALL_BOUNDARIES = []   # (label, family, boundary_index, s*, strategy_pair)
def register(label, family, bi, i, j):
    ALL_BOUNDARIES.append((label, family, bi, i, j))

register('A-s1', FamilyA, 0, 0, 1)
register('A-s2', FamilyA, 1, 1, 2)
register('B', FamilyB, 0, 0, 1)
for M in M_SWEEP:
    fam = make_familyC(M)
    register('C-M%d' % M, fam, 0, 0, 1)

# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def slope_at(family, b, i, j, h_rel=1e-3):
    h = b * h_rel
    dci = (family.costs(b + h)[i] - family.costs(b - h)[i]) / (2 * h)
    dcj = (family.costs(b + h)[j] - family.costs(b - h)[j]) / (2 * h)
    return abs(dci - dcj)

def window_regret(family, bi, eps, seeds=core.SEEDS):
    """Unconditional mean regret over queries whose nearest boundary is bi's
    crossing with d<w (far-field queries excluded: regret 0 there anyway)."""
    bs = family.boundaries()
    b = bs[bi]
    reg_sum = 0.0
    n_win = 0
    flips = 0
    n_query = 0
    for seed in seeds:
        for s, r in core.run_cell(family, eps, seed):
            n_query += 1
            dws = [abs(math.log(s / bb)) / math.log(1.0 + eps) for bb in bs]
            k = min(range(len(dws)), key=lambda i: dws[i])
            if k == bi and dws[k] < 1.0:   # query's OWN window is this boundary's
                n_win += 1
                reg_sum += r
                if r > 0:
                    flips += 1
    return {'window_mean': reg_sum / n_win if n_win else 0.0,
            'n_window': n_win, 'flips': flips,
            'n_query': n_query, 'flip_rate_window': flips / n_win if n_win else 0.0}

# --------------------------------------------------------------------------
# P2: per-boundary H vs w/12
# --------------------------------------------------------------------------
def p2_table():
    rows = []
    for label, family, bi, i, j in ALL_BOUNDARIES:
        b = family.boundaries()[bi]
        C_b = family.costs(b)[i]          # crossing-pair cost (equal for j)
        Vp = slope_at(family, b, i, j)
        for eps in core.EPS_LEVELS:
            w = math.log(1.0 + eps)
            st = window_regret(family, bi, eps)
            H = st['window_mean'] * C_b / (Vp * b) if Vp * b > 0 else 0.0
            pred = w / 12.0
            rows.append({
                'boundary': label, 's_star': b, 'Vp': Vp, 'C_pair': C_b,
                'geom': Vp * b / C_b, 'eps': eps,
                'window_mean_regret': st['window_mean'],
                'n_window': st['n_window'], 'flips': st['flips'],
                'H': H, 'w12': pred, 'ratio': H / pred if pred > 0 else None,
            })
    return rows

# --------------------------------------------------------------------------
# cross-family flip-profile collapse: flip rate in d/w buckets vs (1-dw)/2
# --------------------------------------------------------------------------
def flip_profile():
    """For every FAMILY (each counted once) and eps, mean flip rate per d/w
    bucket (width 0.1); aggregate -> empirical (1-dw)/2 test. NOTE: iterate
    unique families — boundaries of one family share query streams; iterating
    boundaries would double-count multi-boundary families (A)."""
    seen = set()
    families = []
    for label, family, bi, i, j in ALL_BOUNDARIES:
        nm = family.name
        if nm not in seen:
            seen.add(nm)
            families.append(family)
    buckets = {}
    for family in families:
        for eps in core.EPS_LEVELS:
            for seed in core.SEEDS:
                for s, r in core.run_cell(family, eps, seed):
                    dws = [abs(math.log(s / bb)) / math.log(1.0 + eps)
                           for bb in family.boundaries()]
                    dw = min(dws)
                    if dw >= 1.0:
                        continue
                    k = math.floor(dw / 0.1) * 0.1
                    buckets.setdefault(k, {'flip': 0, 'n': 0})
                    buckets[k]['n'] += 1
                    if r > 0:
                        buckets[k]['flip'] += 1
    prof = []
    for k in sorted(buckets):
        mid = k + 0.05
        rate = buckets[k]['flip'] / buckets[k]['n']
        prof.append({'dw_mid': mid, 'flip_rate': rate,
                     'theory': max(0.0, (1.0 - mid) / 2.0),
                     'n': buckets[k]['n']})
    return prof

# --------------------------------------------------------------------------
# P3: crossover shift law for Family C
# --------------------------------------------------------------------------
def p3_table():
    out = []
    for M in M_SWEEP:
        fam = make_familyC(M)
        b_an = fam.boundaries()[0]
        # empirical planner-switch boundary from expected-cost equality (same analytic)
        out.append({'M': M, 's_star_analytic': b_an,
                    'law': '1/M', 's_star_pred': (N_C - P_C) / (M * N_C)})
    # miscalibration band: calibrated M'=10, true M=100
    b_cal = (N_C - P_C) / (10 * N_C)
    b_tru = (N_C - P_C) / (100 * N_C)
    lo, hi = min(b_cal, b_tru), max(b_cal, b_tru)
    log_frac = (math.log(hi) - math.log(lo)) / (math.log(1.0) - math.log(core.S_MIN))
    return {'shift_law': out, 'miscal_band': {
        'calibrated_M': 10, 'true_M': 100,
        's_cal': b_cal, 's_true': b_tru,
        'band_lo': lo, 'band_hi': hi,
        'log_range_fraction': log_frac,
        'decades': math.log10(hi / lo)}}

# --------------------------------------------------------------------------
def main():
    res = {
        'meta': {'issue': 91, 'round': 'R224-canonical-v1',
                 'seeds': core.SEEDS, 'eps_levels': core.EPS_LEVELS,
                 'n_queries_per_cell': core.N_QUERIES, 's_min': core.S_MIN,
                 'familyC': {'N': N_C, 'P': P_C, 'M_sweep': M_SWEEP}},
        'p2_per_boundary': p2_table(),
        'flip_profile': flip_profile(),
        'p3': p3_table(),
    }
    out_p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         'canonical_results.json')
    with open(out_p, 'w') as f:
        json.dump(res, f, indent=1, sort_keys=True)
    print('wrote', out_p)

    # ---- human table ------------------------------------------------------
    print('\n=== P2 per-boundary law: H = window_mean*C/(Vp*s*) vs w/12 ===')
    print('%-7s %-9s %-9s %-9s | %-6s %-10s %-8s %-7s' %
          ('bound', 's*', 'Vp', 'C_pair', 'eps', 'win_mean', 'H', 'ratio'))
    med = []
    for r in res['p2_per_boundary']:
        med.append(r['ratio'])
        print('%-7s %-9.5f %-9.1f %-9.1f | %-6.2f %-10.6f %-8.4f %-7.3f' %
              (r['boundary'], r['s_star'], r['Vp'], r['C_pair'], r['eps'],
               r['window_mean_regret'], r['H'], r['ratio']))
    medv = sorted(x for x in med if x is not None)
    print('\nratio median=%.3f  p10=%.3f  p90=%.3f  (theory: all ~1.0)'
          % (medv[len(medv)//2], medv[len(medv)//10], medv[9*len(medv)//10]))

    print('\n=== cross-family flip-profile collapse (flip rate vs d/w) ===')
    print('%-8s %-10s %-10s %-8s' % ('dw_mid', 'flip_rate', '(1-dw)/2', 'n'))
    for p in res['flip_profile']:
        print('%-8.2f %-10.4f %-10.4f %-8d' %
              (p['dw_mid'], p['flip_rate'], p['theory'], p['n']))

    print('\n=== P3 crossover shift ===')
    for s in res['p3']['shift_law']:
        print('  M=%-5d s*=%.6f (1/M law)' % (s['M'], s['s_star_pred']))
    mb = res['p3']['miscal_band']
    print('  miscalibration band (M\'=%d, M=%d): s in (%.5f, %.5f) = %.2f decades = %.1f%% of log range'
          % (mb['calibrated_M'], mb['true_M'], mb['band_lo'], mb['band_hi'],
             mb['decades'], 100 * mb['log_range_fraction']))

if __name__ == '__main__':
    main()
