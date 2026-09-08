#!/usr/bin/env python3
"""Issue #91 — shared plan-regret task core (v0 + R222 additions), scratch copy."""
import math
import random

SEEDS = [0, 1, 2, 3, 4, 5, 6, 7]
EPS_LEVELS = [0.01, 0.03, 0.1, 0.3, 1.0]
S_MIN = 1e-4
N_QUERIES = 2000

def log_uniform_s(rng, n, lo=S_MIN, hi=1.0):
    return [math.exp(rng.uniform(math.log(lo), math.log(hi))) for _ in range(n)]

def est_selectivity(rng, s, eps):
    w = math.log(1.0 + eps)
    return s * math.exp(rng.uniform(-w, w))

def argmin_costs(costs):
    m = min(range(len(costs)), key=lambda i: costs[i])
    return m

def regret_of(sel_strategy, true_strategy, costs_at_s):
    c_sel = costs_at_s[sel_strategy]
    c_orc = costs_at_s[true_strategy]
    if c_orc <= 0:
        return 0.0
    return (c_sel - c_orc) / c_orc

def run_cell(family, eps, seed, n=N_QUERIES):
    rng = random.Random(seed * 101 + int(eps * 1000))
    out = []
    for s in log_uniform_s(rng, n):
        c_true = family.costs(s)
        s_hat = est_selectivity(rng, s, eps)
        c_est = family.costs(s_hat)
        chosen = argmin_costs(c_est)
        oracle = argmin_costs(c_true)
        r = regret_of(chosen, oracle, c_true)
        out.append((s, r))
    return out

def dw_of(s, boundaries, eps):
    w = math.log(1.0 + eps)
    if not boundaries:
        return float('inf')
    return min(abs(math.log(s / b)) for b in boundaries) / w

def support_stats(rows, boundaries, eps):
    total = sum(r for _, r in rows)
    mass_in = sum(r for s, r in rows if dw_of(s, boundaries, eps) <= 1.0)
    flip_dws = [dw_of(s, boundaries, eps) for s, r in rows if r > 0]
    return (mass_in / total if total > 0 else 1.0,
            max(flip_dws) if flip_dws else 0.0)

def near_rows(rows, boundaries, eps, cut=1.0):
    return [r for s, r in rows if dw_of(s, boundaries, eps) < cut]

def random_planner_regret(family, seed, n=N_QUERIES):
    rng = random.Random(seed * 101 + 777777)
    s_list = log_uniform_s(rng, n)
    m = len(family.costs(s_list[0]))
    tot = 0.0
    for s in s_list:
        c = family.costs(s)
        o = argmin_costs(c)
        tot += regret_of(rng.randrange(m), o, c)
    return tot / n

def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0

def flip_rate(rows):
    pos = [r for _, r in rows if r > 0]
    return len(pos) / len(rows) if rows else 0.0
