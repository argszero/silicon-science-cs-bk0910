#!/usr/bin/env python3
"""Issue #86 validate.py (revision v1.1): two-tier reproduction validation.

Tier A (assert; any failure -> exit 1): STRUCTURAL claims that must hold of
the regenerated data in ANY environment — spike-region geometry, r2 freeze-arm
outcomes (the causal backbone), fp64 persistence, effective-sharpness refutation
(r3 trainable-subspace lam ~ full lam), trace protocol (pre-branch bit-identity,
freeze=hid zero-spike, control >=2 post-branch spikes), boundary cells not
deterministic spiking (<=2/6 presence).

Tier B (banded, report + assert): environment-tolerant comparisons against the
committed reference data. Exact 20k-step spike counts are chaotic under
cross-machine floating-point perturbations (verified: a second environment
reproduced 42/60 counts exactly); the *claims* are not count-exact, so Tier B
enforces: clean cells stay clean (presence 0/3), spiking cells keep presence
(>=1/3 for committed >=2/3), heavy cells' means stay within a band, and the P1/P2
accord rates fall inside the committed Wilson CIs.

Usage: <venv python> validate.py [repro_out_dir]
"""
import glob
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPRO = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'repro_out')
COMM = HERE

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
    print('validate.py v1.1: committed base %s, repro dir %s' % (COMM, REPRO))
    pm = load_pm(os.path.join(REPRO, 'pm'))
    pm_comm = load_pm(os.path.join(COMM, 'pm_out'))
    if len(pm) != 60:
        check(False, 'phase-map file count 60 (got %d)' % len(pm))
        return

    presence = {}
    for (lr, wd, s), r in pm.items():
        presence.setdefault((lr, wd), 0)
        if r['n_spikes'] > 0:
            presence[(lr, wd)] += 1
    pres_c = {}
    for (lr, wd, s), r in pm_comm.items():
        pres_c.setdefault((lr, wd), 0)
        if r['n_spikes'] > 0:
            pres_c[(lr, wd)] += 1

    # ---- Tier A: region geometry (exact) ----
    ok_geo = all(presence.get((lr, wd), 0) == 0 for lr in LRS for wd in WDS
                 if pres_c.get((lr, wd), 0) == 0)
    check(ok_geo, 'TierA region geometry: all committed-clean cells (presence 0/3) are clean in repro '
                  '(wd=0 col, lr=0.02 row, low-lr/low-wd)')
    check(presence.get((0.2, 0.1)) >= 2, 'TierA money cell (0.2,0.1) spiked >=2/3 (got %d/3)' % presence.get((0.2, 0.1)))

    # ---- Tier A: r2 freeze arms (causal backbone, robust across envs) ----
    r2 = load_jsonl(os.path.join(REPRO, 'r2', 'r2_results.jsonl'))
    check(len(r2) == 25, 'TierA r2 has 25 runs (15 freeze arms x 5 seeds + 4 fp64 + 6 deep)')
    for arm, expect in [('none', 5), ('hid', 0), ('out', 5)]:
        runs = [r for r in r2 if r['freeze'] == arm and r['exp'] == 'freeze']
        # post-branch outcome (start >= 300): pre-branch events are shared bit-identically across arms
        sp = sum(1 for r in runs if any(s >= 300 for (s, e) in r['events']))
        check(len(runs) == 5 and sp == expect,
              'TierA freeze=%s spiked %d/5 post-branch (expect %d/5 — causal backbone, disjoint CIs)' % (arm, sp, expect))
    fp = [r for r in r2 if r['exp'] == 'fp64' and r['lr'] == 0.2]
    check(sum(1 for r in fp if r['n_spikes'] > 0) == 2, 'TierA fp64 on money cell 2/2 spiked (NFI refuted)')
    deep = {(r['lr'], r['wd'], r['seed']): r for r in r2 if r['exp'] == 'deep'}

    # ---- Tier A: boundary cells not deterministic spiking (env-robust bound) ----
    for (lr, wd) in [(0.05, 0.03), (0.1, 0.01)]:
        k6 = sum(1 for s in range(6)
                 if ((lr, wd, s) in pm and pm[(lr, wd, s)]['n_spikes'] > 0) or
                 ((lr, wd, s) in deep and deep[(lr, wd, s)]['n_spikes'] > 0))
        check(k6 <= 2, 'TierA boundary lr=%s wd=%s: 6-seed presence %d/6 <= 2 (rare-event cell, not deterministic)' % (lr, wd, k6))

    # ---- Tier A: r3 restricted sharpness (directional + effective-sharpness) ----
    r3 = load_jsonl(os.path.join(REPRO, 'r3', 'r3_results.jsonl'))
    check(len(r3) == 7, 'TierA r3 has 7 runs')
    ok_full_rest = True
    hid_ok = True
    hid_le_control = True
    hid_above = False
    for r in r3:
        steps3 = r['lam_steps']
        m3 = [i for i in range(len(steps3)) if steps3[i] > 300]
        if m3:
            mf3 = sum(r['lam_full'][i] for i in m3) / len(m3)
            mr3 = sum(r['lam_rest'][i] for i in m3) / len(m3)
            ok_full_rest &= abs(mf3 - mr3) <= 3.0
            if r['freeze'] == 'hid':
                hid_above |= mr3 > 10
    check(ok_full_rest, 'TierA r3 all arms: post-branch trainable-lam mean within 3.0 of full (effective-sharpness refuted)')
    check(hid_above, 'TierA r3 at least one freeze=hid arm keeps trainable-lam mean > 2/eta=10')
    ctrl = {r['seed']: r for r in r3 if r['freeze'] == 'none'}
    for r in r3:
        if r['freeze'] == 'hid' and r['seed'] in ctrl:
            hid_le_control &= r['n_spikes'] <= ctrl[r['seed']]['n_spikes']
    check(hid_le_control, 'TierA r3 freeze=hid spikes <= control spikes per seed (directional suppression)')

    # ---- Tier A: trace protocol ----
    tr = {}
    for f in glob.glob(os.path.join(REPRO, 'trace', 'trace_*.json')):
        d = json.load(open(f))
        tr[(d['freeze'], d['seed'])] = d
    check(len(tr) == 4, 'TierA trace has 4 runs')
    for seed in [0, 1]:
        c, h = tr[('none', seed)], tr[('hid', seed)]
        npre = sum(1 for s in c['step'] if s <= 300)
        ident = all(c['loss'][i] == h['loss'][i] for i in range(npre))
        check(ident, 'TierA trace seed %d: pre-300 loss bit-identical control vs freeze=hid (same-env branch protocol)' % seed)
    c0 = tr[('none', 0)]
    post300 = sum(1 for (w0, w1) in c0['events'] if w0 > 300)
    check(post300 >= 2, 'TierA trace control s0: >=2 post-branch spikes (got %d; committed 4, env2 2)' % post300)
    h0 = tr[('hid', 0)]
    check(h0['n_spikes'] == 0, 'TierA trace freeze=hid s0: zero spikes')
    hl = [v for s, v in zip(h0['lam_steps'], h0['lam_full']) if s > 300]
    check(len(hl) > 0 and sum(hl) / len(hl) > 10,
          'TierA trace freeze=hid s0 post-300 lam mean > 2/eta=10 (%.1f)' % (sum(hl) / len(hl) if hl else -1))

    # ---- Tier B: banded vs committed ----
    print('--- Tier B (banded; exact counts are env-chaotic, claims are not) ---')
    # B1: clean cells stay clean (already in geometry); spiking cells keep presence
    ok_pres = True
    for (lr, wd), pc in pres_c.items():
        pr = presence.get((lr, wd), 0)
        if pc >= 2 and pr < 1:
            ok_pres = False
            print('   presence drop: (%s,%s) committed %d/3 repro %d/3' % (lr, wd, pc, pr))
    check(ok_pres, 'TierB all committed >=2/3-presence cells spiked >=1/3 in repro')
    # B2: heavy-cell means within band |d| <= max(12, 0.5*committed)
    ok_band = True
    print('   cell means (committed -> repro):')
    for (lr, wd) in sorted(set(list(pres_c.keys()) + list(presence.keys()))):
        mc = sum(pm_comm[(lr, wd, s)]['n_spikes'] for s in (0, 1, 2)) / 3.0
        mr = sum(pm[(lr, wd, s)]['n_spikes'] for s in (0, 1, 2)) / 3.0
        flag = ''
        if pres_c[(lr, wd)] == 3 and mc >= 9:
            tol = max(12.0, 0.5 * mc)
            if abs(mc - mr) > tol:
                ok_band = False
                flag = ' <-- OUT OF BAND'
            print('   (%s, %s) %.1f -> %.1f  (tol +-%.0f)%s' % (lr, wd, mc, mr, tol, flag))
    check(ok_band, 'TierB heavy-spiking cell means within band of committed')
    # B3: P1/P2 accord rates inside committed Wilson CIs
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
    if p1:
        r1 = 100.0 * n_coll / p1
        check(25.2 <= r1 <= 51.6, 'TierB P1 accord %.1f%% (%d/%d) inside committed CI[25.2,51.6]' % (r1, n_coll, p1))
    if p2:
        r2v = 100.0 * n_cross / p2
        check(38.0 <= r2v <= 70.2, 'TierB P2 accord %.1f%% (%d/%d) inside committed CI[38.0,70.2]' % (r2v, n_cross, p2))
    # B4: reference values report
    print('   P1 accord %d/%d = %.1f%% (committed 18/48 = 37.5%%)' % (n_coll, p1, 100.0 * n_coll / p1 if p1 else -1))
    print('   P2 accord %d/%d = %.1f%% (committed 18/33 = 54.5%%)' % (n_cross, p2, 100.0 * n_cross / p2 if p2 else -1))
    print('   (reference-data values remain authoritative; Tier B enforces the claims, not count equality)')

    print()
    if fails:
        print('VALIDATE: %d FAILURES' % len(fails))
        for f in fails:
            print('  -', f)
        sys.exit(1)
    print('VALIDATE: ALL CHECKS PASSED')


if __name__ == '__main__':
    main()
