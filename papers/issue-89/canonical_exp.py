#!/usr/bin/env python3
"""Issue #89 — canonical full-factorial experiment.

Three detector-control families on ONE shared detection task; 5 control
levels x 8 seeds x 3 families; per-cell pooled Wilson 95% CI over seeds;
family-A monitor-information lever (informed top-R vs random-R) -> 2D map.

Deterministic (fixed seeds). Emits expected-output JSON that a future
validate.py can check against.

Metric everywhere: recall on the attacker-controlled subset at detector
FPR 0.10 (except where noted), pooled across seeds as one binomial.

Steering-law predictions (registered P1-P3):
  A partial-discrete: recall = top-R coverage C(R,H), falls with H
     (control quantity = entropy H; attacker concentrates -> detector better,
      i.e. recall rises as H falls). Monitor-info lever: random-R << top-R.
  B full: recall on rewritten subset = FPR floor, independent of H and q>0.
  C partial-continuous: recall falls with budget eps; crossover eps* near 3.
"""
import json
import math
import random

FPR = 0.10
SEEDS = [0, 1, 2, 3, 4, 5, 6, 7]
D = 8
K = 32
N_PER_SEED = 20000
RULES = 4
MU_MAG = 10.0
R_BALL = 5.0

A_ALPHAS = [0.0, 0.7, 1.4, 2.1, 2.8]
B_QS = [0.0, 0.25, 0.5, 0.75, 1.0]
C_EPS = [0.0, 1.5, 3.0, 4.5, 6.0]

def zipf_weights(alpha, K=K):
    if alpha == 0:
        return [1.0 / K] * K
    denom = sum(1.0 / (k ** alpha) for k in range(1, K + 1))
    return [(1.0 / (k ** alpha)) / denom for k in range(1, K + 1)]

def entropy(w):
    return -sum(p * math.log2(p) for p in w if p > 0)

def gauss(rng, dim=D):
    return [rng.gauss(0.0, 1.0) for _ in range(dim)]

def norm2(v):
    return math.sqrt(sum(x * x for x in v))

def wilson(k, n, z=1.96):
    """Wilson 95% score interval for a binomial proportion."""
    if n == 0:
        return (None, None, None)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (p, max(0.0, centre - half), min(1.0, centre + half))

def sample_discrete(rng, w):
    u = rng.random()
    acc = 0.0
    for j, pr in enumerate(w):
        acc += pr
        if u <= acc:
            return j
    return len(w) - 1

def family_a_cell(alpha, rules_mode, n_seed=N_PER_SEED):
    """partial-discrete: recall of rule set on attacks; rules_mode in
    {'top', 'random'} for the monitor-information lever."""
    w = zipf_weights(alpha)
    H = entropy(w)
    if rules_mode == 'top':
        order = set(sorted(range(K), key=lambda j: -w[j])[:RULES])
    else:
        order = None
    k_tot = 0
    n_tot = 0
    for seed in SEEDS:
        rng = random.Random(seed * 131 + alpha * 1000)
        if order is None:
            rset = set(rng.sample(range(K), RULES))
        else:
            rset = order
        for _ in range(n_seed):
            p = sample_discrete(rng, w)
            n_tot += 1
            if p in rset:
                k_tot += 1
    p, lo, hi = wilson(k_tot, n_tot)
    return {'H': round(H, 3), 'recall': p, 'ci_lo': lo, 'ci_hi': hi,
            'k': k_tot, 'n': n_tot}

def family_b_cell(q, alpha=2.0):
    """full: recall on the rewritten (attacker-controlled) harmful subset."""
    w = zipf_weights(alpha)
    k_tot = 0
    n_tot = 0
    for seed in SEEDS:
        rng = random.Random(seed * 17 + int(q * 1000))
        benign_norm = sorted(norm2(gauss(rng)) for _ in range(20000))
        tau = benign_norm[int((1.0 - FPR) * len(benign_norm))]
        for _ in range(N_PER_SEED):
            if rng.random() < 0.5:
                continue
            sample_discrete(rng, w)   # keep RNG stream comparable
            if rng.random() < q:
                r = gauss(rng)         # attacker-controlled surface
                n_tot += 1
                if norm2(r) > tau:
                    k_tot += 1
    p, lo, hi = wilson(k_tot, n_tot)
    return {'recall': p, 'ci_lo': lo, 'ci_hi': hi, 'k': k_tot, 'n': n_tot}

def family_c_cell(eps):
    """partial-continuous: two arms under L2 budget eps over the continuous
    input channel the guard reads.

    EVASION arm (recall): harmful y ~ N(mu_H, I) is pushed AWAY from mu_H by
    the budget; it is still caught iff dist(y, mu_H) <= R_ball - eps.
    AVAILABILITY arm (fp): benign x ~ N(0, I) is pushed TOWARD mu_H by the
    budget; it is falsely flagged iff dist(x, mu_H) <= R_ball + eps.
    Both are functions of the single scalar budget eps (no pattern entropy) —
    the third, budget-parameterized steering-law shape.

    The fp arm runs in a seed-disjoint loop so the recall RNG stream is
    unchanged from earlier committed versions (recall values stay valid).
    """
    muH = [0.0] * D
    muH[0] = MU_MAG
    k_tot = 0
    n_tot = 0
    for seed in SEEDS:
        rng = random.Random(seed * 29 + int(eps * 100))
        for _ in range(N_PER_SEED):
            if rng.random() < 0.5:
                continue
            y = [muH[i] + rng.gauss(0.0, 1.0) for i in range(D)]
            n_tot += 1
            if norm2([y[i] - muH[i] for i in range(D)]) <= R_BALL - eps:
                k_tot += 1
    p, lo, hi = wilson(k_tot, n_tot)
    # availability arm (seed-disjoint stream)
    kf_tot = 0
    nf_tot = 0
    for seed in SEEDS:
        rng2 = random.Random(seed * 31 + int(eps * 1000) + 5)
        for _ in range(N_PER_SEED):
            x = gauss(rng2)
            nf_tot += 1
            if norm2([x[i] - muH[i] for i in range(D)]) <= R_BALL + eps:
                kf_tot += 1
    pf, lof, hif = wilson(kf_tot, nf_tot)
    return {'recall': p, 'ci_lo': lo, 'ci_hi': hi, 'k': k_tot, 'n': n_tot,
            'fp': {'rate': pf, 'ci_lo': lof, 'ci_hi': hif,
                   'k': kf_tot, 'n': nf_tot}}

def main():
    out = {'meta': {
        'FPR': FPR, 'seeds': SEEDS, 'n_per_seed': N_PER_SEED,
        'D': D, 'K': K, 'rules': RULES, 'mu_mag': MU_MAG, 'r_ball': R_BALL,
        'note': 'recall = fraction of attacker-controlled harmful items flagged '
                'by the detector (FPR 0.10); fp = false-positive rate on '
                'benign items under the same budget (availability arm, '
                'family C only); Wilson 95pct CI pooled over seeds'}}
    # Family A: control = alpha (entropy H); monitor info lever top vs random
    fam_a = {}
    for alpha in A_ALPHAS:
        cell_top = family_a_cell(alpha, 'top')
        cell_rnd = family_a_cell(alpha, 'random')
        fam_a[str(alpha)] = {'H': cell_top['H'],
                             'topR': cell_top, 'randomR': cell_rnd}
    out['family_A_partial_discrete'] = fam_a
    # Family B: control = q (rewrite fraction); alpha fixed 2.0
    fam_b = {}
    for q in B_QS:
        fam_b[str(q)] = family_b_cell(q)
    out['family_B_full'] = fam_b
    # Family B entropy sweep: full control (q=1.0) across the same alphas as
    # family A — tests P2's entropy-INDEPENDENCE claim with committed data.
    fam_b_ent = {}
    for alpha in A_ALPHAS:
        fam_b_ent[str(alpha)] = family_b_cell(1.0, alpha)
    out['family_B_entropy_sweep'] = fam_b_ent
    # Family C: control = eps (L2 budget)
    fam_c = {}
    for eps in C_EPS:
        fam_c[str(eps)] = family_c_cell(eps)
    out['family_C_partial_continuous'] = fam_c

    with open('expected_output.json', 'w') as f:
        json.dump(out, f, indent=1, sort_keys=True)
    # console summary
    for alpha, cell in fam_a.items():
        print('A alpha=%s H=%.2f  topR recall=%.3f CI[%.3f,%.3f]  randomR=%.3f'
              % (alpha, cell['H'], cell['topR']['recall'],
                 cell['topR']['ci_lo'], cell['topR']['ci_hi'],
                 cell['randomR']['recall']))
    for q, cell in fam_b.items():
        if cell['n'] == 0:
            print('B q=%s  n/a (no controlled items)' % q)
        else:
            print('B q=%s  recall=%.3f CI[%.3f,%.3f] (FPR floor %.2f)'
                  % (q, cell['recall'], cell['ci_lo'], cell['ci_hi'], FPR))
    print('B entropy sweep (q=1.0):')
    for alpha, cell in fam_b_ent.items():
        print('B alpha=%s  recall=%.3f CI[%.3f,%.3f] (FPR floor %.2f)'
              % (alpha, cell['recall'], cell['ci_lo'], cell['ci_hi'], FPR))
    for eps, cell in fam_c.items():
        print('C eps=%s  recall=%.3f CI[%.3f,%.3f]  fp=%.4f CI[%.4f,%.4f]'
              % (eps, cell['recall'], cell['ci_lo'], cell['ci_hi'],
                 cell['fp']['rate'], cell['fp']['ci_lo'], cell['fp']['ci_hi']))
    print('expected_output.json written')

if __name__ == '__main__':
    main()
