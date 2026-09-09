#!/usr/bin/env python3
"""Issue #98 validator — When Does Proactive Beat Reactive?

Cross-checks canonical_results.json against (i) its own structural invariants and
(ii) closed-form laws recomputed from the meta params (b, A, W, L, phi, R, m).
Pure arithmetic + stdlib only; deterministic; no wall-clock fields.

Usage:  python3 validate.py [path/to/canonical_results.json]
Exit code 0 iff every check passes (prints VALIDATE n/n ALL PASS).
"""
import hashlib, json, math, os, sys

EXPECTED_SHA = 'bdd4498e069518931b2990a6d446b1e114ea9cc1190396d5457ecb43b128c985'
HERE = os.path.dirname(os.path.abspath(__file__))
PATH = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'canonical_results.json')

failures = []
checks = 0

def check(cond, name, detail=''):
    global checks
    checks += 1
    if cond:
        print(f'  ok  {name}' + (f'  [{detail}]' if detail else ''))
    else:
        print(f'FAIL  {name}' + (f'  [{detail}]' if detail else ''))
        failures.append(name)

def approx(a, b, tol=1e-6):
    return a is not None and b is not None and abs(a - b) <= tol

# ---------------- closed-form law (fallback arm), recomputed from params -------
def cf_boundary(phi, W, L, R):
    """proactive-FB <= reactive iff rho >= rho*:
    rho* = -[(1-phi)W - phi L] / [phi L (1-R) - (1-phi)W]"""
    num = -((1 - phi) * W - phi * L)
    den = phi * L * (1 - R) - (1 - phi) * W
    return (num / den) if den != 0 else None

# ---------------- load + integrity -------------------------------------------------
raw = open(PATH, 'rb').read()
sha = hashlib.sha256(raw).hexdigest()
check(sha == EXPECTED_SHA, 'artifact sha256 == committed', sha[:12])
d = json.loads(raw)

meta = d['meta']
check(meta.get('model') == 'proactive_vs_reactive_canonical', 'meta.model')
check(meta.get('deterministic') is True, 'meta.deterministic')
p = meta['params']
B, A, W, P, L, T = p['b'], p['A'], p['W'], p['P'], p['L'], p['T']
check((B, A, W, P, L, T) == (100.0, 20.0, 20, 100, 10, 40000), 'meta.params canonical cell')
check(approx(p['f'], L / W), 'meta f = L/W', f"f={p['f']}")
check(approx(p['wall_m'], (B + A) / B), 'meta wall_m = (b+A)/b', f"wall_m={p['wall_m']}")

# ---------------- P0 anchors -----------------------------------------------------------
p0 = d['P0_anchors']
none_c, oracle_c, reac_c, pro_c = p0['none'], p0['oracle'], p0['reactive'], p0['proactive']
S = none_c['sum_d']
check(none_c['resource'] == 0, 'A1a none: resource == 0')
check(approx(none_c['violation'], S), 'A1b none: violation == sum_d', f"{none_c['violation']} vs {S}")
check(approx(oracle_c['resource'], S), 'A2a oracle: resource == sum_d')
check(oracle_c['violation'] == 0, 'A2b oracle: violation == 0 (lower bound)')
check(approx(reac_c['resource'], oracle_c['resource']), 'A2c reactive resource == oracle resource (shift invariance)',
      f"{reac_c['resource']} vs {oracle_c['resource']}")
n_present = oracle_c['n_present']
check(approx(reac_c['violation'], A * L * n_present), 'A2d reactive violation == A*L*n_present (onset gap)',
      f"{reac_c['violation']} vs {A * L * n_present}")
check(p0['proactive_rho1_equals_oracle'] is True, 'A3 proactive(rho=1) == oracle EXACTLY')
check(approx(pro_c['resource'], oracle_c['resource']) and pro_c['violation'] == 0 and approx(pro_c['cost'], oracle_c['cost']),
      'A3b proactive(rho=1) resource/viol/cost match oracle')
check(pro_c['cost'] <= reac_c['cost'], 'A4 ordering: proactive(rho=1) cost <= reactive cost')
check(approx(none_c['cost'], oracle_c['cost'], 1e-3), 'A4b R=1 accounting: none cost == oracle cost == sum_d',
      f"none {none_c['cost']} oracle {oracle_c['cost']}")
check(approx(reac_c['cost'], oracle_c['cost'] + reac_c['violation'], 1e-3),
      'A4c R=1 accounting: reactive cost == oracle cost + violations',
      f"reactive {reac_c['cost']} vs {oracle_c['cost'] + reac_c['violation']}")

# ---------------- P1 closed form vs sim --------------------------------------------------
p1 = d['P1_closed_form']
PHIS1 = [0.1, 0.25, 0.5]
RS1 = [0.2, 0.5, 1.0, 2.0, 5.0, 10.0]
for phi in PHIS1:
    row = p1[str(phi)]
    prev = None
    for R in RS1:
        cell = row[str(R)]
        cf_rec = cf_boundary(phi, W, L, R)
        cf_stored_round = round(cell['cf'], 4) if cell['cf'] is not None else None
        cf_rec_round = round(cf_rec, 4) if cf_rec is not None else None
        check(cf_stored_round == cf_rec_round, f'P1 phi={phi} R={R}: closed-form recompute',
              f"stored {cell['cf']} recomputed {cf_rec_round}")
        check(cell['sim'] is not None, f'P1 phi={phi} R={R}: sim boundary exists')
        if cell['sim'] is not None and cf_rec is not None:
            check(abs(cell['sim'] - cf_rec) <= 0.02 + 1e-9,
                  f'P1 phi={phi} R={R}: |sim - cf| <= grid 0.01',
                  f"sim {cell['sim']} cf {round(cf_rec, 4)}")
        if prev is not None:
            check(cell['sim'] is None or prev >= cell['sim'] or approx(prev, cell['sim'], 1e-9),
                  f'P1 phi={phi}: rho* nonincreasing in R ({R})')
        prev = cell['sim']
    # cross-phi: rho* nonincreasing in phi at every R (burst density raises proactive value)
for R in RS1:
    vals = [p1[str(phi)][str(R)]['sim'] for phi in PHIS1]
    check(all(v is None or v2 is None or v >= v2 for v, v2 in zip(vals, vals[1:])),
          f'P1 R={R}: rho* nonincreasing in phi', str(vals))

# ---------------- P2 canonical surface ----------------------------------------------------
p2 = d['P2_surface']
MS = [1.0, 1.05, 1.1, 1.15, 1.2]
PHIS2 = [0.1, 0.25, 0.5]
for m_m in MS:
    check(str(m_m) in p2, f'P2 m={m_m} present')
for R in RS1:
    for phi in PHIS2:
        # monotone in R
        col = [p2[str(m_m)][str(phi)][str(R)] for m_m in MS]
        # monotone in m (rho* rises with margin until the wall)
        sub = [c for c in col[:-1] if c is not None]
        check(all(sub[i] <= sub[i + 1] + 1e-9 for i in range(len(sub) - 1)),
              f'P2 R={R} phi={phi}: rho* nondecreasing in m (violation-shield)', str(col))
        check(col[-1] is None, f'P2 R={R} phi={phi}: m=1.2 wall -> None')
        for c in col[:-1]:
            check(c is not None, f'P2 R={R} phi={phi}: m<1.2 not walled')
for m_m in MS[:-1]:
    for R in RS1:
        vals = [p2[str(m_m)][str(phi)][str(R)] for phi in PHIS2]
        check(all(v2 is None or v is None or v >= v2 for v, v2 in zip(vals, vals[1:])),
              f'P2 m={m_m} R={R}: rho* nonincreasing in phi', str(vals))
    for phi in PHIS2:
        vals = [p2[str(m_m)][str(phi)][str(R)] for R in RS1]
        check(all(v2 is None or v is None or v >= v2 for v, v2 in zip(vals, vals[1:])),
              f'P2 m={m_m} phi={phi}: rho* nonincreasing in R', str(vals))

# ---------------- P3 margin wall ------------------------------------------------------------
p3 = d['P3_margin_wall']
check(approx(p3['wall_m'], (B + A) / B), 'P3 wall_m = 1.2', str(p3['wall_m']))
WALLED = [1.2, 1.21, 1.25, 1.43]
BELOW = [1.0, 1.1, 1.19]
for m_m in WALLED:
    v = p3[str(m_m)]['reactive_viol']
    check(v == 0, f'P3 m={m_m} (>= wall): reactive zero violations', f"viol={v}")
for m_m in BELOW:
    v = p3[str(m_m)]['reactive_viol']
    check(v > 0, f'P3 m={m_m} (< wall): reactive violations remain', f"viol={v}")
for m_m in BELOW + WALLED:
    check(p3[str(m_m)]['pro_wins'] is False,
          f'P3 m={m_m}: proactive rho=0.5 never beats reactive at R=1 phi=0.25 (rho*~0.84 > 0.5)')
vs = [p3[str(m)]['reactive_viol'] for m in [1.0, 1.1, 1.19]]
check(vs[0] > vs[1] > vs[2] > 0, 'P3 margin shrinks reactive violation below wall', str(vs))

# ---------------- P4 aliasing ---------------------------------------------------------------
p4 = d['P4_aliasing']
cont = p4['continuous']
KS = ['2', '4', '8', '20']
check(cont['violation'] > 0, 'P4 continuous: residual FN-fallback violation present', str(cont['violation']))
res_c = cont['resource']
extras = {k: p4[k]['extra_vs_cont'] for k in KS}
viols = {k: p4[k]['violation'] for k in KS}
check(all(p4[k]['resource'] == res_c for k in KS), 'P4 discretization: resource unchanged (pure violation penalty at R=1)')
check(all(v > 0 for v in extras.values()) and extras['2'] > extras['4'] > extras['8'] > extras['20'],
      'P4 aliasing penalty strictly decreasing in K (more bins -> less residual)',
      str(extras))
check(viols['2'] > viols['4'] > viols['8'] > viols['20'],
      'P4 residual violation strictly decreasing in K', str(viols))
check(extras['2'] < cont['violation'] * 3, 'P4 penalty magnitude sane (< 3x continuous viol)')

# ---------------- P5 rise time ----------------------------------------------------------------
p5 = d['P5_rise']
check(p5['0']['reactive_viol'] == reac_c['violation'], 'P5 tau=0 matches P0 reactive violation',
      f"{p5['0']['reactive_viol']} vs {reac_c['violation']}")
vtau = [p5[str(t)]['reactive_viol'] for t in [0, 5, 10, 20]]
check(all(vtau[i] >= vtau[i + 1] for i in range(len(vtau) - 1)),
      'P5 reactive violation nonincreasing in rise time tau (ramps shrink lag penalty)', str(vtau))
check(vtau[-1] < vtau[0], 'P5 tau=20 strictly below tau=0', f"{vtau[0]} -> {vtau[-1]}")
ctau = [p5[str(t)]['reactive_cost'] for t in [0, 5, 10, 20]]
check(all(ctau[i] >= ctau[i + 1] for i in range(len(ctau) - 1)), 'P5 reactive cost nonincreasing in tau')

# ---------------- P6 resource floor -------------------------------------------------------------
p6 = d['P6_resource_floor']
for m_m in [1.0, 1.1, 1.2]:
    cell = p6[str(m_m)]
    check(approx(cell['reactive_res'], cell['m_times_sumd'], 1e-2),
          f'P6 m={m_m}: reactive_res == m*sum_d (shift-invariant floor)',
          f"{cell['reactive_res']} vs {cell['m_times_sumd']}")
    check(cell['equal_rho1'] is True, f'P6 m={m_m}: proactive(rho=1) attains same floor')
    # closed-form excess: m*A*(W*n_fp - L*n_fn); phi=0.25 rho=0.8 -> n_fp=60 n_fn=20
    n_fp, n_fn = 60, 20
    cf_excess = m_m * A * (W * n_fp - L * n_fn)
    check(approx(cell['rho08_excess_over_floor'], cf_excess, 1e-2),
          f'P6 m={m_m}: rho=0.8 excess == m*A*(W*n_fp - L*n_fn) closed form',
          f"{cell['rho08_excess_over_floor']} vs {cf_excess}")

# ---------------- P7 RLScale-Bench committed cell -----------------------------------------------
p7 = d['P7_rlscale_cell']
check(p7['m143_reactive_viol'] == 0, 'P7 m=1.43 (RLScale 70%% target): reactive zero violations')
check(p7['m143_proactive_viol'] == 0, 'P7 m=1.43: proactive(rho=1) also zero violations (both in wall)')
check(p7['consistent_with_RLScaleBench_finding_i'] is True, 'P7 consistency flag set')
check(len(p7['m143_prediction']) > 20, 'P7 prediction string present')

# ---------------- summary ------------------------------------------------------------------------
print()
if failures:
    print(f'VALIDATE {checks - len(failures)}/{checks} FAILED: {len(failures)} failing checks')
    for f in failures:
        print('   -', f)
    sys.exit(1)
print(f'VALIDATE {checks}/{checks} ALL PASS')
