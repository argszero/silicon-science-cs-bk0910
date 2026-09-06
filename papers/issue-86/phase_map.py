#!/usr/bin/env python3
"""Issue #86 phase-map runner: (learning-rate x weight-decay) grid, plain SGD,
MLP+LayerNorm toy, concurrent measurement of every mechanism's named trigger.

Per run records: loss trajectory, scale-invariant weight norms (sampled),
lambda_max (power iteration, sampled), gradient norm (sampled), spike events
(hysteresis detector). Outputs one jsonl per run into OUTDIR.
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
hessian_lambda_max = sf.hessian_lambda_max

OUTDIR = sys.argv[1] if len(sys.argv) > 1 else '/tmp/pm_out'
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


def detect_spikes(loss, enter=0.5, exit_margin=0.1):
    """Hysteresis: spike = rise above (running_min+enter) that falls back below
    (running_min+exit_margin). Returns list of (start,end)."""
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


def run(lr, wd, seed, steps=20000, batch=128, lam_every=400, sample_every=25):
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

    loss_s = []
    step_s = []
    w1_s = []
    w3_s = []
    grad_s = []
    lam_s = []
    lam_steps = []
    t0 = time.time()
    for step in range(steps):
        perm = torch.randperm(n)[:batch]
        opt.zero_grad()
        loss = loss_fn(model(Xtr[perm]), ytr[perm])
        loss.backward()
        gnorm = math.sqrt(sum(torch.sum(p.grad ** 2).item()
                              for p in model.parameters() if p.grad is not None))
        opt.step()
        if step % sample_every == 0:
            loss_s.append(loss.item())
            step_s.append(step)
            grad_s.append(gnorm)
            with torch.no_grad():
                w1_s.append(model.fc1.weight.norm().item())
                w3_s.append(model.fc3.weight.norm().item())
        if step % lam_every == 0 and step > 0:
            perm2 = torch.randperm(n)[:128]
            try:
                lam = hessian_lambda_max(model, loss_fn, Xtr[perm2], ytr[perm2], iters=15)
                lam_s.append(lam)
                lam_steps.append(step)
            except Exception:
                lam_s.append(float('nan'))
                lam_steps.append(step)
    events = detect_spikes([loss for loss in loss_s], enter=0.5)
    # reindex events from sample-indices to steps
    events_steps = [(step_s[s], step_s[e] if e < len(step_s) else steps - 1) for s, e in events]
    model.eval()
    with torch.no_grad():
        acc = (model(Xte).argmax(1) == yte).float().mean().item()
    rec = {
        'lr': lr, 'wd': wd, 'seed': seed, 'steps': steps,
        'n_spikes': len(events_steps),
        'events': events_steps[:60],
        'test_acc': acc,
        'wall_s': round(time.time() - t0, 1),
        'step': step_s, 'loss': loss_s, 'w1norm': w1_s, 'w3norm': w3_s,
        'gradnorm': grad_s, 'lam_steps': lam_steps, 'lam': lam_s,
        'loss_min': min(loss_s), 'loss_last': loss_s[-1],
        'w1_first': w1_s[0], 'w1_last': w1_s[-1],
    }
    return rec


def main():
    lrs = [0.02, 0.05, 0.1, 0.2]
    wds = [0.0, 3e-3, 1e-2, 3e-2, 1e-1]
    seeds = [0, 1, 2]
    total = len(lrs) * len(wds) * len(seeds)
    done = 0
    for lr in lrs:
        for wd in wds:
            for seed in seeds:
                r = run(lr, wd, seed)
                fname = os.path.join(OUTDIR, 'pm_lr{}_wd{}_s{}.json'.format(
                    str(lr).replace('.', 'p'), str(wd).replace('.', 'p'), seed))
                with open(fname, 'w') as f:
                    json.dump(r, f)
                done += 1
                print('[{}/{}] lr={} wd={} seed={} spikes={} acc={:.3f} w1 {:.2f}->{:.3f} lam_max={:.0f} wall={}s'.format(
                    done, total, lr, wd, seed, r['n_spikes'], r['test_acc'],
                    r['w1_first'], r['w1_last'],
                    max([v for v in r['lam'] if isinstance(v, float) and v == v]) if any(
                        isinstance(v, float) and v == v for v in r['lam']) else float('nan'),
                    r['wall_s']), flush=True)
    print('wrote', total, 'runs to', OUTDIR)


if __name__ == '__main__':
    main()
