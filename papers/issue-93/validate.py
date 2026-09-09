#!/usr/bin/env python3
"""
Issue #93 validator (R238).
Two tiers:
  Tier A — structural checks on canonical_results.json (laws the paper claims).
  Tier B — reproduction determinism: re-run marker cells + byte-identity of the
           canonical artifact (sha256 must equal the committed reference).
Usage: run after canonical_runner.py (reproduce.sh does both).
"""
import hashlib, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REF_SHA = '9be610e44217351dbf023aea6ac20f0a78d22b13b9591d47f24c7dbbc3f49a3a'

def load():
    with open(os.path.join(HERE, 'canonical_results.json')) as f:
        return json.load(f)

def check(name, cond, detail=''):
    status = 'PASS' if cond else 'FAIL'
    print('  [%s] %s %s' % (status, name, detail))
    if not cond:
        sys.exit('VALIDATION FAILED at: %s' % name)

def main():
    r = load()
    print('== Tier A: structural law checks ==')
    ol = r['P0_openloop']
    for k, v in ol.items():
        check('openloop %s rel_err < 5%%' % k, v['rel_err'] < 0.05, '(rel=%.4f)' % v['rel_err'])
    for k in ('classic_only', 'l4s_only'):
        u = r['P1_single'][k]['util']
        check('single %s util in [0.94, 1.06]' % k, abs(u - 1.0) < 0.06, '(util=%.4f)' % u)
    p2 = r['P2_regimes']
    d_low = p2['Nc10_g0']['d_l_ms']; d_mid = p2['Nc20_g0']['d_l_ms']
    check('coexist low-N_c uncoupled < 6 ms', d_low < 6.0, '(%.2f ms)' % d_low)
    check('fragile mid-N_c uncoupled > 8 ms', d_mid > 8.0, '(%.2f ms)' % d_mid)
    for nc in (20, 40, 80):
        dc = p2['Nc%d_g1' % nc]['d_l_ms']
        check('coupling isolates N_c=%d (< 6 ms)' % nc, dc < 6.0, '(%.2f ms)' % dc)
    for k, v in r['P6_plateau'].items():
        err = abs(v['d_meas'] - v['pred']) / v['d_meas'] * 100.0
        check('plateau law %s err < 5%%' % k, err < 5.0, '(%.2f%%)' % err)
    ab = r['P5_ablation']['Nc40']
    ratio = ab['d_shared_ms'] / ab['d_own_ms']
    check('P3 ablation ratio > 4 at N_c=40', ratio > 4.0, '(x%.1f)' % ratio)
    f0 = r['P4_field']['0']; f1 = r['P4_field']['1']
    m0 = max(max(row) for row in f0['delay_ms'])
    m1 = max(max(row) for row in f1['delay_ms'])
    check('uncoupled field reaches classic-scale (> 14 ms)', m0 > 14.0, '(max %.2f)' % m0)
    check('coupled field fully isolated (< 5 ms)', m1 < 5.0, '(max %.2f)' % m1)
    for k, v in r['P9_robust'].items():
        if k.startswith('dt'):
            check('dt convergence %s < 0.01%%' % k, v['pct_change'] < 0.01, '(%.4f%%)' % v['pct_change'])
        else:
            check('IC unique attractor %s < 1%%' % k, v['spread_pct'] < 1.0, '(%.3f%%)' % v['spread_pct'])
    tc = r['P7_Tc_boundary']
    check('boundary T_C-independent', abs(tc['Nc_star_TC15'] - tc['Nc_star_TC30']) < 0.05,
          '(%s vs %s)' % (round(tc['Nc_star_TC15'], 3), round(tc['Nc_star_TC30'], 3)))
    bu = r['P8_buffer_boundary']
    vals = [bu['Bh1'], bu['Bh5'], bu['Bh10']]
    check('boundary buffer-independent', all(abs(v - vals[1]) < 0.05 for v in vals),
          '(%s)' % [round(v, 3) for v in vals])

    print('== Tier B: reproduction determinism ==')
    h = hashlib.sha256(open(os.path.join(HERE, 'canonical_results.json'), 'rb').read()).hexdigest()
    check('canonical_results.json sha256 == committed', h == REF_SHA, '(%.12s...)' % h)
    sys.path.insert(0, HERE)
    import canonical_runner as CR
    markers = [
        ('openloop classic p=1e-3', CR.check_openloop()['classic_p1e-3']['W_meas'],
         ol['classic_p1e-3']['W_meas'], 1e-9),
        ('P2 Nc20_g0 d_l_ms', CR.run(20, 20, g=0.0)['d_l_ms'], p2['Nc20_g0']['d_l_ms'], 1e-9),
        ('P4 field Nl20 Nc20 g0 (rounded 4dp)', CR.run(20, 20, g=0.0)['d_l_ms'],
         f0['delay_ms'][2][6], 5e-5),
    ]
    for name, fresh, committed, tol in markers:
        check('marker re-run %s matches committed' % name, abs(fresh - committed) < tol,
              '(fresh=%.8f committed=%.8f)' % (fresh, committed))
    print('ALL TIER-A + TIER-B CHECKS PASS')
    print('VALIDATE OK')

if __name__ == '__main__':
    main()
