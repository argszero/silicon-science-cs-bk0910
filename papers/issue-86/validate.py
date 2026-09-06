#!/usr/bin/env python3
"""Issue #86 validate.py: verify a reproduce.py run against the manuscript's
committed numbers (two-tier, mirroring the journal house style).

Tier A (assert; any failure -> exit 1): structural claims that must hold of the
regenerated data alone — spike-region geometry, freeze-arm outcomes, fp64
persistence, boundary 6-seed rates, restricted-sharpness refutation, and the
trace bit-identical-branch protocol.
Tier B (report + assert-with-tolerance): comparison against the committed
outputs that produced the manuscript (same-machine determinism was verified, so
counts must match exactly and phase-map table means within 0.15).

Usage: <venv python> validate.py [repro_out_dir]
"""
import glob
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPRO = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'repro_out')
COMM = HERE  # committed outputs live next to the scripts (pm_out/, r2_out/, ...)

fails = []


def check(cond, msg):
    status = 'PASS' if cond else 'FAIL'
    print('[%s] %s' % (status, msg))
    if not cond:
        fails.append(msg)
    return cond


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def load_pm(d):
    rows = {}
    for f in glob.glob(os.path.join(d, 'pm_*.json')):
        r = json.load(open(f))
        rows[(r['lr'], r['wd'], r['seed'])] = r
    return rows


def load_jsonl(f):
    return [json.loads(l) for l in open(f) if l.strip()]


LRS = [0.02, 0.05, 0.1, 0.2]
WDS = [0.0, 3e-3, 1e-2, 3e-2, 1e-1]


def main():
    print('validate.py: committed base %s, repro dir %s' % (COMM, REPRO))
    pm = load_pm(os.path.join(REPRO, 'pm'))
    pm_comm = load_pm(os.path.join(COMM, 'pm_out'))
    if len(pm) != 60:
        check(False, 'phase-map file count 60 (got %d)' % len(pm))
        return
    # ---- Tier A: spike-region geometry ----
    presence = {}
    for (lr, wd, s), r in pm.items():
        presence.setdefault((lr, wd), 0)
        if r['n_spikes'] > 0:
            presence[(lr, wd)] += 1
    ok_geo = True
    for lr in LRS:
        for wd in WDS:
            if wd == 0.0 and presence.get((lr, wd), 0) != 0:
                ok_geo = False
            if lr == 0.02 and presence.get((lr, wd), 0) != 0:
                ok_geo = False
    check(ok_geo, 'spike-region geometry: wd=0 column and lr=0.02 row all clean')
    check(presence.get((0.2, 0.1)) == 3, 'money cell (0.2,0.1) spikes 3/3')
    check(presence.get((0.05, 0.03)) == 1 and presence.get((0.1, 0.01)) == 1,
          'boundary cells 1/3 each from pm (deep seeds -> 1/6 below)')

    # ---- Tier A: freeze arms / fp64 / deep (r2) ----
    r2 = load_jsonl(os.path.join(REPRO, 'r2', 'r2_results.jsonl'))
    check(len(r2) == 16, 'r2 has 16 runs')
    for arm, expect in [('none', 2), ('hid', 0), ('out', 2)]:
        runs = [r for r in r2 if r['freeze'] == arm and r['exp'] == 'freeze']
        sp = sum(1 for r in runs if r['n_spikes'] > 0)
        check(sp == expect, 'freeze=%s spiked %d/2 (expect %d/2)' % (arm, sp, expect))
    fp = [r for r in r2 if r['exp'] == 'fp64' and r['lr'] == 0.2]
    check(sum(1 for r in fp if r['n_spikes'] > 0) == 2,
          'fp64 on money cell 2/2 spiked (NFI refuted)')
    deep = {(r['lr'], r['wd'], r['seed']): r for r in r2 if r['exp'] == 'deep'}
    for (lr, wd) in [(0.05, 0.03), (0.1, 0.01)]:
        k6 = sum(1 for s in range(6)
                 if ((lr, wd, s) in pm and pm[(lr, wd, s)]['n_spikes'] > 0) or
                 ((lr, wd, s) in deep and deep[(lr, wd, s)]['n_spikes'] > 0))
        lo, hi = wilson(k6, 6)
        check(k6 == 1, 'boundary lr=%s wd=%s: 6-seed presence %d/6 CI[%.0f,%.0f]' % (
            lr, wd, k6, 100 * lo, 100 * hi))

    # ---- Tier A: restricted sharpness (r3) ----
    r3 = load_jsonl(os.path.join(REPRO, 'r3', 'r3_results.jsonl'))
    check(len(r3) == 7, 'r3 has 7 runs')
    hid_s1 = [r for r in r3 if r['freeze'] == 'hid' and r['seed'] == 1][0]
    steps = hid_s1['lam_steps']
    m = [i for i in range(len(steps)) if steps[i] > 300]
    mf = sum(hid_s1['lam_full'][i] for i in m) / len(m)
    mr = sum(hid_s1['lam_rest'][i] for i in m) / len(m)
    check(abs(mf - 25.2) < 0.5, 'freeze=hid s1 post-branch full-lam mean %.1f ~ 25.2' % mf)
    check(abs(mf - mr) < 1.0, 'freeze=hid s1 trainable-lam %.1f == full %.1f (effective-sharpness refuted)' % (mr, mf))
    check(hid_s1['n_spikes'] == 0, 'freeze=hid s1 zero spikes')
    ok_full_rest = True
    for r in r3:
        steps3 = r['lam_steps']
        m3 = [i for i in range(len(steps3)) if steps3[i] > 300]
        if not m3:
            continue
        mf3 = sum(r['lam_full'][i] for i in m3) / len(m3)
        mr3 = sum(r['lam_rest'][i] for i in m3) / len(m3)
        ok_full_rest &= abs(mf3 - mr3) <= 2.5
        if r['freeze'] == 'hid':
            check(mr3 > 10, 'freeze=hid s%d trainable-subspace mean lam %.1f > 2/eta=10 (effective-sharpness refuted)' % (r['seed'], mr3))
    check(ok_full_rest, 'r3 all arms: post-branch trainable-lam mean within 2.5 of full')

    # ---- Tier A: trace bit-identical protocol (trace_out3 equivalent) ----
    tr = {}
    for f in glob.glob(os.path.join(REPRO, 'trace', 'trace_*.json')):
        d = json.load(open(f))
        tr[(d['freeze'], d['seed'])] = d
    check(len(tr) == 4, 'trace has 4 runs')
    for seed in [0, 1]:
        c, h = tr[('none', seed)], tr[('hid', seed)]
        npre = sum(1 for s in c['step'] if s <= 300)
        ident = all(c['loss'][i] == h['loss'][i] for i in range(npre))
        check(ident, 'trace seed %d: pre-300 loss bit-identical control vs freeze=hid' % seed)
    c0 = tr[('none', 0)]
    post300 = sum(1 for (w0, w1) in c0['events'] if w0 > 300)
    check(post300 >= 3, 'trace control s0: >=3 post-branch spikes (got %d)' % post300)
    h0 = tr[('hid', 0)]
    check(h0['n_spikes'] == 0, 'trace freeze=hid s0: zero spikes')
    hsteps = [s for s in h0['lam_steps'] if s > 300]
    hl = [v for s, v in zip(h0['lam_steps'], h0['lam_full']) if s > 300]
    check(sum(hl) / len(hl) > 10, 'trace freeze=hid s0 post-300 lam mean %.1f > 2/eta=10' % (sum(hl) / len(hl)))

    # ---- Tier B: repro vs committed (same-machine determinism: exact) ----
    print('--- Tier B: repro vs committed manuscript data ---')
    n_match = 0
    for (lr, wd, s), r in pm.items():
        if pm_comm[(lr, wd, s)]['n_spikes'] == r['n_spikes']:
            n_match += 1
    check(n_match == 60, 'phase-map n_spikes matches committed in all 60 runs (%d/60)' % n_match)
    # P1 accord (collapse->spike) and P2 accord (cross->spike) recomputed on repro
    n_coll = n_clean_coll = n_cross = n_clean_cross = 0
    for (lr, wd, s), r in pm.items():
        if wd == 0.0:
            continue
        w1 = r['w1norm']
        base = w1[0]
        nc = next((st for st, v in zip(r['step'], w1) if v < 0.5 * base), None)
        if nc is not None:
            if r['n_spikes'] > 0 and r['events'][0][0] >= nc:
                n_coll += 1
            elif r['n_spikes'] == 0:
                n_clean_coll += 1
        thresh = 2.0 / lr
        lc = next((st for st, v in zip(r['lam_steps'], r['lam'])
                   if isinstance(v, float) and v == v and v >= thresh), None)
        if lc is not None:
            if r['n_spikes'] > 0:
                n_cross += 1
            else:
                n_clean_cross += 1
    p1 = n_coll + n_clean_coll
    p2 = n_cross + n_clean_cross
    lo1, hi1 = wilson(n_coll, p1)
    lo2, hi2 = wilson(n_cross, p2)
    print('   P1 collapse->spike accord %d/%d = %.1f%% CI[%.1f,%.1f]' % (n_coll, p1, 100 * n_coll / p1, 100 * lo1, 100 * hi1))
    print('   P2 cross->spike accord  %d/%d = %.1f%% CI[%.1f,%.1f]' % (n_cross, p2, 100 * n_cross / p2, 100 * lo2, 100 * hi2))
    check(p1 == 48 and n_coll == 18, 'P1 accord 18/48 reproduced (got %d/%d)' % (n_coll, p1))
    check(p2 == 33 and n_cross == 18, 'P2 accord 18/33 reproduced (got %d/%d)' % (n_cross, p2))
    # phase-map table means within tolerance
    ok_tab = True
    for lr in LRS:
        for wd in WDS:
            mv = sum(pm[(lr, wd, s)]['n_spikes'] for s in (0, 1, 2)) / 3.0
            cv = sum(pm_comm[(lr, wd, s)]['n_spikes'] for s in (0, 1, 2)) / 3.0
            if abs(mv - cv) > 0.15:
                ok_tab = False
                print('   table mismatch lr=%s wd=%s repro=%.2f comm=%.2f' % (lr, wd, mv, cv))
    check(ok_tab, 'phase-map table means within 0.15 of committed (Table 1)')
    # r2/r3 row-by-row n_spikes
    r2c = load_jsonl(os.path.join(COMM, 'r2_out', 'r2_results.jsonl'))
    r2m = all(a['n_spikes'] == b['n_spikes'] and a['freeze'] == b['freeze'] and a['seed'] == b['seed']
              for a, b in zip(sorted(r2, key=lambda x: (x['exp'], x['freeze'], x['seed'])),
                              sorted(r2c, key=lambda x: (x['exp'], x['freeze'], x['seed']))))
    check(r2m, 'r2 freeze/fp64/deep n_spikes match committed')
    r3c = load_jsonl(os.path.join(COMM, 'r3_out', 'r3_results.jsonl'))
    r3m = all(a['n_spikes'] == b['n_spikes'] for a, b in zip(r3, r3c))
    check(r3m, 'r3 n_spikes match committed')

    print()
    if fails:
        print('VALIDATE: %d FAILURES' % len(fails))
        for f in fails:
            print('  -', f)
        sys.exit(1)
    print('VALIDATE: ALL CHECKS PASSED')


if __name__ == '__main__':
    main()
