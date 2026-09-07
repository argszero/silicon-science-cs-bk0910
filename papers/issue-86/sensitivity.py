#!/usr/bin/env python3
"""Issue #86 sensitivity analysis.

1. How fragile is each REFUTATION?
   P1 (weight-norm sufficiency): 30 clean runs collapsed norms >=50% yet never
   spiked. How many of those would need to spike to make collapse "sufficient"?
   P2 (EoS sufficiency): 15 clean runs crossed 2/eta (any sample) yet never
   spiked; plus freeze=hid s1 excursion to 66 w/ 0 spikes. Flip-count: how many
   of the 15 clean-crossing runs would need to spike for the naive rule to hold?
2. Wilson CIs on spike rates per phase-map cell and freeze arms.
3. Boundary-cell binomial CIs (6 seeds each).
"""
import glob
import json
import math
import os
import sys

PM = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pm_out')
R2 = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'r2_out', 'r2_results.jsonl')


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def load_pm():
    rows = {}
    for f in glob.glob(os.path.join(PM, 'pm_*.json')):
        r = json.load(open(f))
        rows[(r['lr'], r['wd'], r['seed'])] = r
    return rows


def first_ge(xs, steps, thresh):
    for v, s in zip(xs, steps):
        if isinstance(v, float) and v == v and v >= thresh:
            return s
    return None


def first_below(vals, steps, frac):
    base = vals[0]
    for v, s in zip(vals, steps):
        if v < frac * base:
            return s
    return None


def main():
    rows = load_pm()
    print('== 1. Refutation fragility (flip counts) ==')
    # P1: clean runs that collapsed norm >=50%
    collapsed_clean = 0
    spiked_after_collapse = 0
    for (lr, wd, s), r in rows.items():
        if wd == 0.0:
            continue
        nc = first_below(r['w1norm'], r['step'], 0.5)
        if nc is None:
            continue
        if r['n_spikes'] > 0:
            first_sp = r['events'][0][0]
            if first_sp >= nc:
                spiked_after_collapse += 1
        else:
            collapsed_clean += 1
    print('P1: runs with norm-collapse and spikes-after-collapse:', spiked_after_collapse,
          '| clean collapsed runs:', collapsed_clean,
          '| collapse-before-spike accord: {}/{}'.format(spiked_after_collapse,
                                                         spiked_after_collapse + collapsed_clean))
    n_collapsed = spiked_after_collapse + collapsed_clean
    lo, hi = wilson(spiked_after_collapse, n_collapsed)
    print('   P1 accord rate {:.1f}% CI[{:.1f},{:.1f}] (would need {} clean runs to spike to reach 50%)'.format(
        100.0 * spiked_after_collapse / n_collapsed, 100 * lo, 100 * hi, n_collapsed - 2 * spiked_after_collapse))
    # P2: clean runs that crossed 2/eta (any lam sample)
    crossed_clean = 0
    spiked_with_cross = 0
    for (lr, wd, s), r in rows.items():
        if wd == 0.0:
            continue
        thresh = 2.0 / lr
        lc = first_ge(r['lam'], r['lam_steps'], thresh)
        if lc is None:
            continue
        if r['n_spikes'] > 0:
            spiked_with_cross += 1
        else:
            crossed_clean += 1
    print('P2: spiked-with-cross:', spiked_with_cross, '| clean-crossed:', crossed_clean)
    n_cross = spiked_with_cross + crossed_clean
    lo, hi = wilson(spiked_with_cross, n_cross)
    print('   P2 accord rate {:.1f}% CI[{:.1f},{:.1f}] (would need {} clean runs to spike to reach 50%)'.format(
        100.0 * spiked_with_cross / n_cross, 100 * lo, 100 * hi, max(0, n_cross - 2 * spiked_with_cross)))
    # freeze=hid counterexample strength
    print('   freeze=hid s1: lambda excursion to 66 (>2/eta x6.6) with 0 spikes - binary causal counterexample')

    print()
    print('== 2. Cell spike-rate CIs (per lr x wd, n=3) ==')
    lrs = sorted(set(k[0] for k in rows))
    wds = sorted(set(k[1] for k in rows if k[1] > 0))
    print('lr\\wd   ' + ''.join('{:>12}'.format('{:.2g}'.format(w)) for w in [0.0] + wds))
    for lr in lrs:
        line = '{:.2f}  '.format(lr)
        for wd in [0.0] + wds:
            runs = [rows[(lr, wd, s)] for s in [0, 1, 2]]
            sp = sum(1 for r in runs if r['n_spikes'] > 0)
            lo, hi = wilson(sp, 3)
            line += '{:>12}'.format('{:.0f}%[{:.0f},{:.0f}]'.format(100 * sp / 3, 100 * lo, 100 * hi))
        print(line)

    print()
    print('== 3. Freeze-arm rates (r2: n=5 per arm, post-branch events) ==')
    r2 = [json.loads(l) for l in open(R2)]
    for arm in ['none', 'hid', 'out']:
        runs = [r for r in r2 if r['freeze'] == arm and r['exp'] == 'freeze']
        sp = sum(1 for r in runs if any(s >= 300 for (s, e) in r['events']))
        n = len(runs)
        lo, hi = wilson(sp, n)
        print('freeze={:4s}: {}/{} spiked post-branch rate {:.0f}% CI[{:.0f},{:.0f}]'.format(
            arm, sp, n, 100 * sp / n if n else 0, 100 * lo, 100 * hi))
    fp = [r for r in r2 if r['exp'] == 'fp64' and r['lr'] == 0.2]
    print('fp64 lr=0.2 wd=0.1: {}/2 spiked (fp32 control 2/2)'.format(sum(1 for r in fp if r['n_spikes'] > 0)))

    print()
    print('== 4. Boundary cells: 6-seed spike-presence (pm seeds 0-2 + deep seeds 3-5) ==')
    deep = {}
    for r in r2:
        if r['exp'] == 'deep':
            deep[(r['lr'], r['wd'], r['seed'])] = r['n_spikes']
    for (lr, wd) in [(0.05, 0.03), (0.1, 0.01)]:
        counts = [rows[(lr, wd, s)]['n_spikes'] for s in [0, 1, 2]]
        counts += [deep[(lr, wd, s)] for s in [3, 4, 5]]
        k = sum(1 for c in counts if c > 0)
        lo, hi = wilson(k, 6)
        print('lr={} wd={}: seeds {} -> {}/6 spiked rate {:.0f}% CI[{:.0f}%,{:.0f}%]'.format(
            lr, wd, counts, k, 100.0 * k / 6, 100 * lo, 100 * hi))


if __name__ == '__main__':
    main()
