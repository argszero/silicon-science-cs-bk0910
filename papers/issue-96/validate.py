#!/usr/bin/env python3
"""Issue #96 validator — structural + semantic checks on canonical_results.json.

Tier A: structural invariants / anchor cells (ground truth by construction).
Tier B: mechanism checks tied to the evidence spine (v3 regression values).
No wall-clock fields anywhere in the artifact; fully deterministic.
"""
import hashlib, json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXPECTED_SHA = '576c55115a8d13f593183db81c23139fce3180bb0a28c73e33ba26209ea41d9f'

def main():
    path = os.path.join(HERE, 'canonical_results.json')
    d = json.load(open(path))
    checks, fails = [], []

    def check(name, cond, detail=''):
        checks.append(name)
        if not cond:
            fails.append((name, detail))

    # --- sha determinism lock ---
    raw = open(path, 'rb').read()
    h = hashlib.sha256(raw).hexdigest()
    check('sha256 deterministic artifact', h == EXPECTED_SHA, f'got {h}')

    # --- panel presence ---
    for panel in ('P0_anchors', 'P1_field_pi0', 'P2_coupling', 'P3_pollution',
                  'P4_sharpness', 'P5_ablation', 'P6_robust', 'P7_combined_law',
                  'P8_bus_pressure'):
        check(f'panel {panel} present', panel in d)

    p0, p1, p2 = d['P0_anchors'], d['P1_field_pi0'], d['P2_coupling']
    p3, p4, p5, p6, p7, p8 = (d['P3_pollution'], d['P4_sharpness'], d['P5_ablation'],
                              d['P6_robust'], d['P7_combined_law'], d['P8_bus_pressure'])

    # --- Tier A: anchors ---
    E0 = p0['E0_baseline']
    check('A1 baseline E0 in canonical region (2.5, 3.6)', 2.5 < E0 < 3.6, str(E0))
    check('A1b baseline utilization u0 in (0.10, 0.16)', 0.10 < p0['u0'] < 0.16)
    check('A2 oracle E == 1.0 (all stalls removed)', p0['oracle_E'] == 1.0)
    check('A2b oracle speedup == E0', abs(p0['oracle_speedup'] - E0) < 1e-6)
    check('A3 added-bytes collapse: ac=0.1 cv=0.9 speedup < 1', p0['collapse_ac01_cv09_speedup'] < 1.0)
    check('A3b collapse utilization < 1 (no hard saturation)', p0['collapse_u'] < 1.0)

    # --- Tier A: P1 field ---
    check('A4 field is 380 cells (19 ac x 20 cv)', p1['n_cells'] == 380)
    check('A5 harmful cells == 22 at pi=0 (bandwidth only)', p1['harmful_cells'] == 22)
    stars = p1['ac_star_by_cv']
    none_low = [stars[k] is None for k in sorted(stars, key=float) if float(k) < 0.2]
    defined_high = [stars[k] is not None for k in sorted(stars, key=float) if float(k) >= 0.2]
    check('A6 ac* undefined below cv=0.2 (never harmful)', all(none_low), str(stars))
    check('A6b ac* defined for all cv >= 0.2', len(defined_high) == 16 and all(defined_high))
    acs = [stars[k] for k in sorted(stars, key=float) if stars[k] is not None]
    check('A6c ac* monotone nondecreasing in cv', all(b >= a - 1e-9 for a, b in zip(acs, acs[1:])))
    check('A7 ac*(cv=0.5) ~ 0.0878', abs(stars['0.5'] - 0.0878) < 1e-3, str(stars['0.5']))
    check('A7b ac*(cv=0.9) ~ 0.1221 (=v3 bandwidth term)', abs(stars['0.9'] - 0.1221) < 1e-3)
    check('A7c ac* max ~ 0.1264 at cv=0.95', abs(stars['0.95'] - 0.1264) < 1e-3)

    # --- Tier B: P2 coupling ablation ---
    check('B1 decoupled service removes ALL harm (22 -> 0)', p2['harm_decoupled'] == 0 and p2['harm_coupled'] == 22)
    check('B2 corner flip: coupled 0.827 -> decoupled 2.509 (x3.0)',
          p2['corner_coupled_sp'] < 1.0 and p2['corner_decoupled_sp'] > 2.0)

    # --- Tier B: P3 pollution ---
    harms = [p3[k]['harmful_cells'] for k in ('0.0', '0.2', '0.4', '0.6', '0.8', '1.0')]
    check('B3 harm strictly increasing in pi (22,60,87,109,129,142)',
          harms == [22, 60, 87, 109, 129, 142], str(harms))
    for k, tol in (('0.4', 0.05), ('0.6', 0.03), ('0.8', 0.02), ('1.0', 0.02)):
        v = p3[k]
        check(f'B4 pi={k}: ac*max tracks pi/(1+pi) within {tol}',
              abs(v['ac_star_max'] - v['pi_over_1pi']) < tol, f"meas {v['ac_star_max']} law {v['pi_over_1pi']}")
    check('B5 bandwidth floor: ac*max ~0.1264 at pi=0', abs(p3['0.0']['ac_star_max'] - 0.1264) < 1e-3)
    check('B5b folklore limit reproduced at pi=1: ac*max ~0.505', abs(p3['1.0']['ac_star_max'] - 0.505) < 0.01)

    # --- Tier B: P4 sharpness ---
    for k, v in p4.items():
        check(f'B6 sharpness {k}: width <= 0.0501 (grid-res sharp)', v['width'] <= 0.0501, str(v['width']))
        check(f'B6b {k}: ac* defined', v['ac_star'] is not None)

    # --- Tier B: P5 pollution ablation ---
    for k in ('0.5', '0.8', '1.0'):
        v = p5[k]
        check(f'B7 pi={k}: pollution-free harm == 22 (bandwidth floor)', v['harm_pollution_free'] == 22)
        check(f'B7b pi={k}: pollution marginal (full > floor)', v['harm_full'] > v['harm_pollution_free'])

    # --- Tier B: P6 robustness ---
    for s in (20, 40, 80):
        vals = [p6[f'P{P}_s{s}'] for P in (100, 200, 400)]
        check(f'B8 P-sensitivity s={s}: ac* falls as P rises', vals[0] > vals[1] > vals[2], str(vals))
    for P in (100, 200, 400):
        vals = [p6[f'P{P}_s{s}'] for s in (20, 40, 80)]
        check(f'B8b s-sensitivity P={P}: ac* rises as s rises', vals[0] < vals[1] < vals[2], str(vals))
    check('B9 robustness magnitudes in (0.10, 0.60)', all(0.10 < v < 0.60 for v in p6.values()))

    # --- Tier B: P7 combined law (sub-additivity regression vs v3) ---
    ref = {'0.0': 0.1221, '0.2': 0.2098, '0.5': 0.2771, '0.8': 0.3239, '1.0': 0.3497}
    for k, rv in ref.items():
        v = p7[k]
        check(f'B10 pi={k}: ac*(cv=0.9) matches v3 spine ({rv})',
              abs(v['ac_star_meas_cv09'] - rv) < 1e-3, str(v['ac_star_meas_cv09']))
    for k in ('0.2', '0.5', '0.8', '1.0'):
        v = p7[k]
        check(f'B11 pi={k}: combined law SUB-ADDITIVE (channels interact)',
              v['ac_star_meas_cv09'] < v['pred_add'])

    # --- Tier B: P8 bus-pressure family (folklore test, m-sweep at fixed s=40) ---
    ref8 = {'mS0.16': 0.085, 'mS0.4': 0.126, 'mS0.64': 0.144, 'mS0.8': 0.150, 'mS0.96': 0.155}
    vals8 = [p8[k] for k in ref8]
    check('B12 bus-pressure family matches v1 spine (0.085..0.155)',
          all(abs(p8[k] - v) <= 0.003 for k, v in ref8.items()), str(p8))
    check('B12b ac*max nondecreasing in bus pressure m*s',
          all(b >= a - 1e-9 for a, b in zip(vals8, vals8[1:])))
    check('B12c folklore NOT reproduced at any pressure: ac*max < 0.20 at m*s=0.96',
          p8['mS0.96'] < 0.20 and p8['mS0.96'] > 0.10)

    print(f'validate: {len(checks)} checks, {len(fails)} failures')
    if fails:
        for name, detail in fails:
            print(f'  FAIL {name}: {detail}')
        sys.exit(1)
    print('ALL CHECKS PASS')
    return 0

if __name__ == '__main__':
    sys.exit(main())
