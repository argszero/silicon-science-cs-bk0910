#!/usr/bin/env python3
"""Issue #91 revision analysis (R230): noise-vs-bias split of the H/(w/12)
residuals. Uses the deterministic machinery (toy_regret_core + families from
canonical_runner) to compute per-(boundary, eps) PER-SEED window means, giving
an across-seed SE and 95% CI on the window mean regret and hence on H. This
answers reviewer Q1: how much of the eps=.01 ratio spread (0.30-1.62) is
sampling noise (wide CI) vs systematic bias.
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import toy_regret_core as core
import canonical_runner as canon   # families + ALL_BOUNDARIES + helpers

def slope_at(family, b, i, j, h_rel=1e-3):
    h = b * h_rel
    dci = (family.costs(b + h)[i] - family.costs(b - h)[i]) / (2 * h)
    dcj = (family.costs(b + h)[j] - family.costs(b - h)[j]) / (2 * h)
    return abs(dci - dcj)

def per_seed_window_means(family, bi, eps, seeds=core.SEEDS):
    """List of (per-seed window mean regret, per-seed n_window)."""
    out = []
    bs = family.boundaries()
    for seed in seeds:
        reg_sum = 0.0
        n_win = 0
        for s, r in core.run_cell(family, eps, seed):
            dws = [abs(math.log(s / bb)) / math.log(1.0 + eps) for bb in bs]
            k = min(range(len(dws)), key=lambda i: dws[i])
            if k == bi and dws[k] < 1.0:
                n_win += 1
                reg_sum += r
        out.append((reg_sum / n_win if n_win else 0.0, n_win))
    return out

def t95(n):
    return 2.365 if n >= 3 else float('inf')   # t_{0.975, n-1}, n=8 -> 2.306; use 2.365 for 7 df safety

def main():
    rows = []
    for label, family, bi, i, j in canon.ALL_BOUNDARIES:
        b = family.boundaries()[bi]
        C_b = family.costs(b)[i]
        Vp = slope_at(family, b, i, j)
        for eps in core.EPS_LEVELS:
            w = math.log(1.0 + eps)
            ps = per_seed_window_means(family, bi, eps)
            means = [m for m, _ in ps]
            ns = [n for _, n in ps]
            k = len(means)
            mean = sum(means) / k
            var = sum((m - mean) ** 2 for m in means) / (k - 1) if k > 1 else 0.0
            se = math.sqrt(var / k) if k > 1 else 0.0
            # CI on mean regret (t with k-1 df; k=8 -> use 2.306)
            tval = 2.306
            lo = mean - tval * se
            hi = mean + tval * se
            # H = mean*C/(Vp*b); ratios with CI
            Hm = mean * C_b / (Vp * b)
            Hlo = lo * C_b / (Vp * b)
            Hhi = hi * C_b / (Vp * b)
            pred = w / 12.0
            rows.append({
                'boundary': label, 'eps': eps, 'w': w,
                'window_mean': mean, 'se': se, 'ci_lo': lo, 'ci_hi': hi,
                'n_window_total': sum(ns), 'n_window_min': min(ns),
                'n_window_per_seed': ns,
                'H': Hm, 'H_ci': (Hlo, Hhi),
                'ratio': Hm / pred, 'ratio_ci': (Hlo / pred, Hhi / pred),
            })

    print('%-8s %-5s %-8s %-8s %-10s %-10s %-10s | %-9s %-10s' %
          ('bound', 'eps', 'mean', 'se', 'ci_lo', 'ci_hi', 'n_win', 'ratio', 'ratio CI'))
    print('-' * 100)
    for r in rows:
        print('%-8s %-5.2f %-8.5f %-8.5f %-10.5f %-10.5f %-10d | %-9.3f [%.2f, %.2f]' %
              (r['boundary'], r['eps'], r['window_mean'], r['se'], r['ci_lo'],
               r['ci_hi'], r['n_window_total'], r['ratio'],
               r['ratio_ci'][0], r['ratio_ci'][1]))

    # eps=.01 noise-vs-bias summary
    print('\neps=0.01 column: ratio spread decomposition')
    print('%-8s %-8s %-10s %-12s %-10s %-14s' %
          ('bound', 'ratio', 'ratio_lo', 'ratio_hi', 'n_win', 'noise-dominated?'))
    for r in rows:
        if abs(r['eps'] - 0.01) < 1e-9:
            span = r['ratio_ci'][1] - r['ratio_ci'][0]
            dom = 'yes (CI spans >1.0x)' if span > 1.0 else 'partial'
            print('%-8s %-8.3f %-10.2f %-12.2f %-10d %-14s' %
                  (r['boundary'], r['ratio'], r['ratio_ci'][0], r['ratio_ci'][1],
                   r['n_window_total'], dom))

    # store
    with open('residual_analysis.json', 'w') as f:
        json.dump(rows, f, indent=1)
    print('\nwrote residual_analysis.json')

if __name__ == '__main__':
    main()
