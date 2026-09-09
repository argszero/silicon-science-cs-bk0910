#!/usr/bin/env python3
"""Issue #96 canonical runner — When Prefetching Flips (deterministic, stdlib only).

Single algebraic mean-field model of a core + shared DRAM bus + prefetcher(ac,cv) with
two harm channels (bandwidth coupling, cache pollution pi).  All panels P0-P6 produce the
numbers reported in manuscript.md.  No randomness, no wall-clock fields: the artifact is
byte-identical across machines.
"""
import json, math, os

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------- model core ----------
def solve_two(m0, P, s, cv, ac, pi, tol=1e-12):
    """Fixed-point elapsed cycles E for demand misses + prefetcher.

    m = m0*(1 + pi*useless_per_demand)  (pollution inflates future misses)
    useless_per_demand = cv*(1-ac)/ac
    r = m*((1-cv) + cv/ac)             (bus request rate: uncovered + all prefetches)
    E = 1 + (1-cv)*m*(P + s*u/(1-u))   (uncovered fills stall P + queueing)
    u*E = r*s                           (utilization closure)
    """
    if ac <= 0:
        return None
    useless_per_demand = cv * (1.0 - ac) / ac if ac < 1.0 and cv > 0 else 0.0
    m = m0 * (1.0 + pi * useless_per_demand)
    if cv == 0.0:
        r = m
    else:
        r = m * ((1.0 - cv) + cv / ac)
    def E_of_u(u):
        if u >= 1.0:
            return float('inf')
        return 1.0 + (1.0 - cv) * m * (P + s * u / (1.0 - u))
    def g(u):
        return u * E_of_u(u) - r * s
    lo, hi = 0.0, 1.0 - 1e-10
    for _ in range(300):
        mid = 0.5 * (lo + hi)
        if g(mid) > 0:
            hi = mid
        else:
            lo = mid
        if hi - lo < tol:
            break
    u = 0.5 * (lo + hi)
    E = E_of_u(u)
    Q = s * u / (1.0 - u)
    return E, u, Q, m

def decoupled_E(m0, P, s, cv, ac):
    """Demand fills prioritized: E uses demand-only utilization; prefetch rides leftover."""
    if cv == 0.0:
        sol = solve_two(m0, P, s, 0.0, 1.0, 0.0)
        return sol[0]
    r = m0 * ((1.0 - cv) + cv / ac)
    def E_d(u_d):
        if u_d >= 1.0:
            return float('inf')
        return 1.0 + (1.0 - cv) * m0 * (P + s * u_d / (1.0 - u_d))
    def gd(u):
        return u * E_d(u) - m0 * s
    lo, hi = 0.0, 1.0 - 1e-10
    for _ in range(300):
        mid = 0.5 * (lo + hi)
        if gd(mid) > 0:
            hi = mid
        else:
            lo = mid
        if hi - lo < 1e-12:
            break
    u_d = 0.5 * (lo + hi)
    return E_d(u_d)

def speedup(E0, E):
    return E0 / E if E and E != float('inf') else 0.0

def ac_star_over_acs(speeds, acs):
    """First ac (ascending) with speedup >= 1; linear interpolation."""
    prev_ac, prev_sp = None, None
    for ac, sp in zip(acs, speeds):
        if sp >= 1.0 and prev_sp is not None and prev_sp < 1.0:
            frac = (1.0 - prev_sp) / (sp - prev_sp)
            return prev_ac + frac * (ac - prev_ac)
        prev_ac, prev_sp = ac, sp
    return None

def field(m0, P, s, pi, acs, cvs):
    E0 = solve_two(m0, P, s, 0.0, 1.0, 0.0)[0]
    cells, harm = {}, 0
    ac_stars = {}
    for cv in cvs:
        speeds = []
        for ac in acs:
            sol = solve_two(m0, P, s, cv, ac, pi)
            E = sol[0] if sol else float('inf')
            sp = speedup(E0, E)
            cells[f'{cv}_{ac}'] = round(sp, 6)
            if sp < 1.0:
                harm += 1
            speeds.append(sp)
        ac_stars[str(cv)] = ac_star_over_acs(speeds, acs)
    return E0, cells, harm, ac_stars

def main():
    m0, P, s = 0.01, 200.0, 40.0
    acs = [round(0.05 * k, 2) for k in range(1, 21)]
    cvs = [round(0.05 * k, 2) for k in range(1, 20)]

    # P0: anchors
    E0 = solve_two(m0, P, s, 0.0, 1.0, 0.0)[0]
    orc = solve_two(m0, P, s, 1.0, 1.0, 0.0)[0]
    col = solve_two(m0, P, s, 0.9, 0.1, 0.0)[0]
    p0 = {
        'E0_baseline': round(E0, 6), 'u0': round(solve_two(m0, P, s, 0.0, 1.0, 0.0)[1], 6),
        'oracle_E': round(orc, 6), 'oracle_speedup': round(E0 / orc, 6),
        'collapse_ac01_cv09_speedup': round(speedup(E0, col), 6),
        'collapse_u': round(solve_two(m0, P, s, 0.9, 0.1, 0.0)[1], 6),
    }

    # P1: field pi=0 (bandwidth only) — 380 cells + boundary
    E0b, cells0, harm0, stars0 = field(m0, P, s, 0.0, acs, cvs)
    p1 = {'harmful_cells': harm0, 'n_cells': len(acs) * len(cvs),
          'ac_star_by_cv': {k: (round(v, 4) if v else None) for k, v in stars0.items()}}

    # P2: coupling ablation (P3 of registration) — harm coupled vs decoupled
    harm_dec = 0
    for cv in cvs:
        for ac in acs:
            E_c = solve_two(m0, P, s, cv, ac, 0.0)[0]
            E_d = decoupled_E(m0, P, s, cv, ac)
            if speedup(E0, E_c) < 1.0 and speedup(E0, E_d) < 1.0:
                pass
            if speedup(E0, E_d) < 1.0:
                harm_dec += 1
    p2 = {'harm_coupled': harm0, 'harm_decoupled': harm_dec,
          'corner_coupled_sp': round(speedup(E0, col), 6),
          'corner_decoupled_sp': round(speedup(E0, decoupled_E(m0, P, s, 0.9, 0.1)), 6)}

    # P3: pollution sweep pi in {0, .2, .4, .6, .8, 1}
    pis = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
    p3 = {}
    for pi in pis:
        E0p, cellsp, harmp, starsp = field(m0, P, s, pi, acs, cvs)
        vals = [v for v in starsp.values() if v]
        ac_max = max(vals) if vals else None
        p3[str(pi)] = {'harmful_cells': harmp,
                       'ac_star_max': round(ac_max, 4) if ac_max else None,
                       'pi_over_1pi': round(pi / (1.0 + pi), 4)}

    # P4: sharpness — width in ac of the crossing (<= 0.05 grid res)
    p4 = {}
    for pi in [0.0, 0.5, 1.0]:
        E0p, cellsp, _, _ = field(m0, P, s, pi, acs, cvs)
        # width: ac from sp=1.25 down to crossing
        for cv in [0.5, 0.9]:
            prev_ac, prev_sp = None, None
            lo_ac = None
            star = None
            for ac in acs:
                sp = cellsp[f'{cv}_{ac}']
                if sp <= 1.25 and prev_sp is not None and prev_sp > 1.25:
                    frac = (1.25 - sp) / (prev_sp - sp)
                    lo_ac = prev_ac + frac * (ac - prev_ac)
                if sp >= 1.0 and prev_sp is not None and prev_sp < 1.0:
                    frac = (1.0 - prev_sp) / (sp - prev_sp)
                    star = prev_ac + frac * (ac - prev_ac)
                prev_ac, prev_sp = ac, sp
            p4[f'pi{pi}_cv{cv}'] = {'width': round(star - lo_ac, 4) if (star and lo_ac) else 0.05,
                                    'ac_star': round(star, 4) if star else None}

    # P5: pollution ablation — harm full vs pollution-free at high pi
    p5 = {}
    for pi in [0.5, 0.8, 1.0]:
        _, _, h_full, _ = field(m0, P, s, pi, acs, cvs)
        p5[str(pi)] = {'harm_full': h_full, 'harm_pollution_free': harm0}

    # P6: robustness — ac*(pi=0.5, cv=0.9) over P x s
    p6 = {}
    for Pp in [100, 200, 400]:
        for ss in [20, 40, 80]:
            E0r, cellsr, _, starsr = field(m0, Pp, ss, 0.5, acs, cvs)
            st = starsr.get('0.9')
            p6[f'P{Pp}_s{ss}'] = round(st, 4) if st else None

    # P7: combined two-channel law — ac* at cv=0.9 per pi (v3 grid) vs add model
    bw_term = stars0.get('0.9')  # pi=0, cv=0.9 = pure bandwidth floor
    p7 = {}
    for pi in [0.0, 0.2, 0.5, 0.8, 1.0]:
        _, cellsp, _, starsp = field(m0, P, s, pi, acs, cvs)
        st = starsp.get('0.9')
        p7[str(pi)] = {'ac_star_meas_cv09': round(st, 4) if st else None,
                       'bw_term': round(bw_term, 4),
                       'pi_term': round(pi / (1.0 + pi), 4),
                       'pred_add': round(bw_term + pi / (1.0 + pi), 4)}

    # P8: bus-pressure family — vary m (demand miss rate) at fixed s=40, pi=0
    # (folklore test: does ac* reach ~0.5 near bus saturation? -> no, saturates ~0.155)
    p8 = {}
    for ms in [0.16, 0.4, 0.64, 0.8, 0.96]:
        m_i = ms / s
        E0r, cellsr, _, starsr = field(m_i, P, s, 0.0, acs, cvs)
        vals8 = [v for v in starsr.values() if v]
        p8[f'mS{ms}'] = round(max(vals8), 4) if vals8 else None

    results = {
        'meta': {'model': 'prefetch_canonical_meanfield', 'script': 'canonical_runner.py',
                 'deterministic': True,
                 'params': {'m0': m0, 'P': P, 's': s, 'mP': m0 * P, 'mS': m0 * s}},
        'P0_anchors': p0, 'P1_field_pi0': p1, 'P2_coupling': p2,
        'P3_pollution': p3, 'P4_sharpness': p4, 'P5_ablation': p5,
        'P6_robust': p6, 'P7_combined_law': p7, 'P8_bus_pressure': p8,
    }
    out = os.path.join(HERE, 'canonical_results.json')
    json.dump(results, open(out, 'w'), indent=1)
    import hashlib
    h = hashlib.sha256(open(out, 'rb').read()).hexdigest()
    print("wrote", out)
    print("sha256", h)
    print("P0:", p0)
    print("P1 harm:", harm0, "| P2 decoupled harm:", harm_dec)
    print("P3:", {k: v['ac_star_max'] for k, v in p3.items()})
    print("P5:", p5)

if __name__ == '__main__':
    main()
