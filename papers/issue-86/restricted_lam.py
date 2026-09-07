#!/usr/bin/env python3
"""Issue #86 round 3:
(A) Restricted-lambda test: FULL-Hessian lambda_max vs TRAINABLE-SUBSPACE
    lambda_max for control vs freeze=hid vs freeze=out on the money cell.
    Question: does freeze=hid stay stable because the trainable-subspace
    (effective) sharpness is below 2/eta even though full-Hessian lambda > 2/eta?
(B) Per-step lambda (lam_every=20) on the control money cell over 0..1500 to
    resolve the trigger dynamics at the first spike.
"""
import json
import math
import os
import sys
import time

import numpy as np
import torch
import torch.nn as nn
from importlib.machinery import SourceFileLoader

sf = SourceFileLoader('sf', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'spike_feas.py')).load_module()
MLPLN = sf.MLPLN
OUTDIR = sys.argv[1] if len(sys.argv) > 1 else '/tmp/r3_out'
os.makedirs(OUTDIR, exist_ok=True)


def make_data(n_train=4000, n_test=1000, n_class=20, dim=64, seed=0):
    g = np.random.RandomState(seed)
    centers = g.randn(n_class, dim) * 2.0
    n = n_train + n_test
    xs, ys = [], []
    for _ in range(n):
        c = g.randint(n_class)
        xs.append(centers[c] + g.randn(dim) * 1.0)
        ys.append(c)
    xs = np.array(xs, dtype=np.float32)
    ys = np.array(ys, dtype=np.int64)
    return xs[:n_train], ys[:n_train], xs[n_train:], ys[n_train:]


def hessian_lam(model, loss_fn, xb, yb, subset=None, iters=15):
    """Top-eigenvalue of Hessian restricted to `subset` (or all params if None)."""
    params = list(model.parameters())
    if subset is None:
        subset = params
    v = []
    for p in params:
        if any(p is q for q in subset):
            v.append(torch.randn_like(p))
        else:
            v.append(torch.zeros_like(p))
    vnorm = math.sqrt(sum(torch.sum(torch.pow(vi, 2)).item() for vi in v))
    if vnorm < 1e-12:
        return 0.0
    for vi in v:
        vi.div_(vnorm)
    lam = 0.0
    for _ in range(iters):
        model.zero_grad()
        loss = loss_fn(model(xb), yb)
        grads = torch.autograd.grad(loss, params, create_graph=True)
        Hv = torch.autograd.grad(grads, params, grad_outputs=v, retain_graph=False)
        num = sum(torch.sum(hi * vi).item() for hi, vi in zip(Hv, v))
        den = sum(torch.sum(vi * vi).item() for vi in v)
        lam = num / max(den, 1e-12)
        nv = [hi.detach().clone() for hi in Hv]
        nnorm = math.sqrt(sum(torch.sum(torch.pow(hi, 2)).item() for hi in nv))
        if nnorm > 1e-12:
            for hi in nv:
                hi.div_(nnorm)
        v = nv
        del grads, Hv
    return lam


def detect_spikes(loss, enter=0.5, exit_margin=0.1):
    events = []
    run_min = 1e9
    in_spike = False
    start = -1
    for i, lv in enumerate(loss):
        if lv < run_min:
            run_min = lv
        if not in_spike:
            if lv > run_min + enter:
                in_spike = True
                start = i
        else:
            if lv < run_min + exit_margin:
                in_spike = False
                events.append((start, i))
    return events


def run(lr, wd, seed, steps, freeze_at=None, freeze='none',
        lam_every=50, batch=128):
    torch.manual_seed(seed)
    np.random.seed(seed)
    Xtr, ytr, Xte, yte = make_data(seed=seed)
    Xtr = torch.from_numpy(Xtr)
    ytr = torch.from_numpy(ytr)
    Xte = torch.from_numpy(Xte)
    yte = torch.from_numpy(yte)
    model = MLPLN()
    loss_fn = nn.CrossEntropyLoss()
    opt = torch.optim.SGD(model.parameters(), lr=lr, weight_decay=wd, momentum=0.0)
    n = Xtr.shape[0]

    frozen = []
    if freeze == 'hid':
        frozen = list(model.fc1.parameters()) + list(model.fc2.parameters())
    elif freeze == 'out':
        frozen = list(model.fc3.parameters())

    loss_s, step_s = [], []
    lam_full, lam_rest, lam_steps = [], [], []
    t0 = time.time()
    for step in range(steps):
        if freeze_at is not None and step == freeze_at:
            keep = [p for p in model.parameters() if not any(p is q for q in frozen)]
            opt = torch.optim.SGD(keep, lr=lr, weight_decay=wd, momentum=0.0)
        perm = torch.randperm(n)[:batch]
        opt.zero_grad()
        loss = loss_fn(model(Xtr[perm]), ytr[perm])
        loss.backward()
        opt.step()
        lv = loss.item()
        if step % 20 == 0:
            loss_s.append(lv)
            step_s.append(step)
        if lam_every and step % lam_every == 0 and step > 0:
            perm2 = torch.randperm(n)[:128]
            trainable = [p for p in model.parameters() if not any(p is q for q in frozen)]
            try:
                lf = hessian_lam(model, loss_fn, Xtr[perm2], ytr[perm2], None, iters=12)
            except Exception:
                lf = float('nan')
            try:
                lr2 = hessian_lam(model, loss_fn, Xtr[perm2], ytr[perm2], trainable, iters=12)
            except Exception:
                lr2 = float('nan')
            lam_full.append(lf)
            lam_rest.append(lr2)
            lam_steps.append(step)
    ev = detect_spikes(loss_s)
    ev_steps = [(step_s[s], step_s[e] if e < len(step_s) else steps - 1) for s, e in ev]
    model.eval()
    with torch.no_grad():
        acc = (model(Xte).argmax(1) == yte).float().mean().item()
    return {
        'lr': lr, 'wd': wd, 'seed': seed, 'freeze': freeze,
        'n_spikes': len(ev_steps), 'events': ev_steps[:20],
        'test_acc': acc,
        'lam_steps': lam_steps, 'lam_full': lam_full, 'lam_rest': lam_rest,
        'wall_s': round(time.time() - t0, 1),
    }


def main():
    results = []
    for seed in [0, 1]:
        for frz in ['none', 'hid', 'out']:
            r = run(0.2, 0.1, seed, steps=2500, freeze_at=300, freeze=frz, lam_every=50)
            results.append(r)
            pairs = [(s, f, rr) for s, f, rr in zip(r['lam_steps'], r['lam_full'], r['lam_rest'])]
            post = [(s, f, rr) for s, f, rr in pairs if s >= 350
                    and not (isinstance(f, float) and f != f)
                    and not (isinstance(rr, float) and rr != rr)]
            if post:
                mf = sum(x[1] for x in post) / len(post)
                mr = sum(x[2] for x in post) / len(post)
                print('A s={} freeze={:4s} spikes={:2d} acc={:.3f} | post-branch mean full-lam {:.1f} trainable-lam {:.1f} (2/eta=10)'.format(
                    seed, frz, r['n_spikes'], r['test_acc'], mf, mr), flush=True)
            else:
                print('A s={} freeze={:4s} spikes={:2d} | no post-branch lam'.format(seed, frz, r['n_spikes']), flush=True)
    for seed in [0]:
        r = run(0.2, 0.1, seed, steps=1500, freeze_at=None, freeze='none', lam_every=20)
        results.append(r)
        pairs = list(zip(r['lam_steps'], r['lam_full'], r['lam_rest']))
        print('B control per-step s={} spikes={} events={}'.format(seed, r['n_spikes'], r['events'][:5]), flush=True)
        band = [(s, f) for s, f, _ in pairs if not (isinstance(f, float) and f != f)]
        print('   lam samples around onset:', ['{:.0f}@{}'.format(f, s) for s, f in band[:40]], flush=True)
    with open(os.path.join(OUTDIR, 'r3_results.jsonl'), 'w') as f:
        for r in results:
            f.write(json.dumps(r) + '\n')
    print('wrote', len(results), 'runs')


if __name__ == '__main__':
    main()
