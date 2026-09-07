#!/usr/bin/env python3
"""Issue #86 trace runs (R203): dense traces for fig3, mirroring r3-B protocol.

Protocol (identical to restricted_lam.run / r3-B per-step onset run):
  money cell lr=0.2 wd=0.1; loss recorded every 20 steps; lambda_max
  (full + trainable-subspace) every 20 steps via hessian_lam(iters=12);
  freeze branch @ step 300 for freeze=hid arms (opt rebuilt excluding
  fc1/fc2); 1500 steps; seeds {0,1} x arms {control, freeze=hid}.
Verification anchor: control s0 must reproduce the documented r3-B events
  [160-180],[640-660],[1380-1400] (n_spikes=3) and lam samples ~80@160,
  57@620/53@640, 86@700.
Saves one JSON per run (loss/step arrays + lam traces) into OUTDIR.
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

HERE = os.path.dirname(os.path.abspath(__file__))
OUTDIR = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'trace_out')
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


def hessian_lam(model, loss_fn, xb, yb, subset=None, iters=12):
    """Top-eigenvalue of Hessian restricted to `subset` (copied from r3)."""
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


def run_trace(lr, wd, seed, steps=1500, freeze_at=300, freeze='none',
              lam_every=20, batch=128):
    """Mirror of restricted_lam.run() + loss/step trace saving."""
    torch.manual_seed(seed)
    np.random.seed(seed)
    Xtr, ytr, Xte, yte = make_data(seed=seed)
    Xtr = torch.from_numpy(Xtr)
    ytr = torch.from_numpy(ytr)
    Xte = torch.from_numpy(Xte)
    yte = torch.from_numpy(yte)
    model = MLPLN()
    loss_fn = nn.CrossEntropyLoss()
    opt = torch.optim.SGD(model.parameters(), lr=lr, weight_decay=wd,
                          momentum=0.0)
    n = Xtr.shape[0]

    frozen = []
    if freeze == 'hid':
        frozen = list(model.fc1.parameters()) + list(model.fc2.parameters())

    loss_s, step_s = [], []
    lam_full, lam_rest, lam_steps = [], [], []
    t0 = time.time()
    for step in range(steps):
        if freeze_at is not None and step == freeze_at:
            keep = [p for p in model.parameters()
                    if not any(p is q for q in frozen)]
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
            # Full-Hessian lambda only: identical RNG consumption for every
            # arm (v-init draws randn for ALL params) so all arms share a
            # bit-identical pre-branch trajectory (true freeze-branch design).
            perm2 = torch.randperm(n)[:128]
            try:
                lf = hessian_lam(model, loss_fn, Xtr[perm2], ytr[perm2], None)
            except Exception:
                lf = float('nan')
            lam_full.append(lf)
            lam_steps.append(step)
    ev = detect_spikes(loss_s)
    ev_steps = [(step_s[s], step_s[e] if e < len(step_s) else steps - 1)
                for s, e in ev]
    model.eval()
    with torch.no_grad():
        acc = (model(Xte).argmax(1) == yte).float().mean().item()
    return {
        'lr': lr, 'wd': wd, 'seed': seed, 'freeze': freeze,
        'n_spikes': len(ev_steps), 'events': ev_steps[:20],
        'test_acc': acc, 'wall_s': round(time.time() - t0, 1),
        'step': step_s, 'loss': loss_s,
        'lam_steps': lam_steps, 'lam_full': lam_full,
    }


def main():
    for seed in [0, 1]:
        for frz in ['none', 'hid']:
            r = run_trace(0.2, 0.1, seed, freeze=frz)
            name = 'trace_%s_s%d.json' % (
                'control' if frz == 'none' else 'freezehid', seed)
            with open(os.path.join(OUTDIR, name), 'w') as f:
                json.dump(r, f)
            print('s=%d freeze=%-4s spikes=%d events=%s acc=%.3f wall=%ss' % (
                seed, frz, r['n_spikes'], r['events'][:4], r['test_acc'],
                r['wall_s']), flush=True)
    print('wrote 4 traces to', OUTDIR)


if __name__ == '__main__':
    main()
