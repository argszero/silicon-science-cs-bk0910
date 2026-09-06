#!/usr/bin/env python3
"""Issue #86 round 2 experiments:
(A) Freeze-arm causal test on money cell (lr=0.2 wd=0.1): branch from a
    bit-identical pre-spike state into three arms:
      control      - continue training (expect spikes resume)
      freeze_hid   - freeze fc1/fc2 (LayerNorm'd hidden layers, the
                     scale-invariant ones) -> spikes stop if norm-collapse
                     of hidden layers is causal for the lambda rise
      freeze_out   - freeze fc3 (readout/logits) -> spikes persist if readout
                     dynamics are not the trigger
(B) fp64 contrast on spiking cells (NFI discriminator: if spikes are
    fp-precision artifacts they vanish in float64).
(C) Boundary-cell seed deepening: seeds 3,4,5 on lr=0.05 wd=0.03 and
    lr=0.1 wd=0.01 (have 0-3 spikes/3 seeds; need n for a CI).
Outputs jsonl records.
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

OUTDIR = sys.argv[1] if len(sys.argv) > 1 else '/tmp/r2_out'
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


def train_to(model, opt, Xtr, ytr, steps, batch=128, record_every=25):
    """Train `steps` more steps, returning (loss_s, step_s). model/opt mutated."""
    n = Xtr.shape[0]
    loss_s, step_s = [], []
    for step in range(steps):
        perm = torch.randperm(n)[:batch]
        opt.zero_grad()
        loss = torch.nn.functional.cross_entropy(model(Xtr[perm]), ytr[perm])
        loss.backward()
        opt.step()
        loss_s.append(loss.item())
        step_s.append(step)
    return loss_s, step_s


def run(lr, wd, seed, steps=20000, dtype=torch.float32, freeze_at=None,
        freeze='none', lam_every=100, record_every=25):
    """freeze_at: step at which to branch and freeze; freeze in {none,hid,out}."""
    torch.manual_seed(seed)
    np.random.seed(seed)
    Xtr, ytr, Xte, yte = make_data(seed=seed)
    Xtr = torch.from_numpy(Xtr).to(dtype)
    ytr = torch.from_numpy(ytr)
    Xte = torch.from_numpy(Xte).to(dtype)
    yte = torch.from_numpy(yte)
    model = MLPLN().to(dtype)
    loss_fn = nn.CrossEntropyLoss()
    params = list(model.parameters())
    opt = torch.optim.SGD(params, lr=lr, weight_decay=wd, momentum=0.0)
    n = Xtr.shape[0]
    batch = 128
    loss_s, step_s, lamv, lam_steps = [], [], [], []
    w1v = []
    t0 = time.time()
    for step in range(steps):
        if freeze_at is not None and step == freeze_at:
            # branch: rebuild optimizer excluding frozen params
            if freeze == 'hid':
                frozen = list(model.fc1.parameters()) + list(model.fc2.parameters())
            elif freeze == 'out':
                frozen = list(model.fc3.parameters())
            else:
                frozen = []
            keep = [p for p in model.parameters() if not any(p is q for q in frozen)]
            opt = torch.optim.SGD(keep, lr=lr, weight_decay=wd, momentum=0.0)
        perm = torch.randperm(n)[:batch]
        opt.zero_grad()
        loss = loss_fn(model(Xtr[perm]), ytr[perm])
        loss.backward()
        opt.step()
        if step % record_every == 0:
            loss_s.append(loss.item())
            step_s.append(step)
            with torch.no_grad():
                w1v.append(model.fc1.weight.norm().item())
        if lam_every and step % lam_every == 0 and step > 0:
            perm2 = torch.randperm(n)[:128]
            try:
                lam = hessian_lambda_max(model, loss_fn, Xtr[perm2], ytr[perm2], iters=15)
                lamv.append(lam)
                lam_steps.append(step)
            except Exception:
                lamv.append(float('nan'))
                lam_steps.append(step)
    events = detect_spikes(loss_s)
    ev_steps = [(step_s[s], step_s[e] if e < len(step_s) else steps - 1) for s, e in events]
    model.eval()
    with torch.no_grad():
        acc = (model(Xte).argmax(1) == yte).float().mean().item()
    return {
        'exp': 'freeze' if freeze_at is not None else ('fp64' if dtype == torch.float64 else 'deep'),
        'freeze': freeze, 'lr': lr, 'wd': wd, 'seed': seed,
        'n_spikes': len(ev_steps), 'events': ev_steps[:30],
        'test_acc': acc, 'loss_min': min(loss_s), 'loss_last': loss_s[-1],
        'w1_first': w1v[0], 'w1_last': w1v[-1],
        'lam': lamv, 'lam_steps': lam_steps,
        'wall_s': round(time.time() - t0, 1),
    }


def main():
    results = []
    # (A) freeze arms on money cell, branch at step 300 (pre-spike; first spike ~300-600)
    for seed in [0, 1]:
        for frz in ['none', 'hid', 'out']:
            r = run(0.2, 0.1, seed, steps=6000, freeze_at=300, freeze=frz)
            results.append(r)
            print('A lr=0.2 wd=0.1 s={} freeze={} spikes={} first={} acc={:.3f} wall={}s'.format(
                seed, frz, r['n_spikes'], r['events'][0][0] if r['events'] else None,
                r['test_acc'], r['wall_s']), flush=True)
    # (B) fp64 on two spiking cells
    for lr, wd in [(0.2, 0.1), (0.1, 0.03)]:
        for seed in [0, 1]:
            r = run(lr, wd, seed, steps=6000, dtype=torch.float64)
            results.append(r)
            print('B fp64 lr={} wd={} s={} spikes={} first={} acc={:.3f} wall={}s'.format(
                lr, wd, seed, r['n_spikes'], r['events'][0][0] if r['events'] else None,
                r['test_acc'], r['wall_s']), flush=True)
    # (C) boundary deep seeds 3,4,5
    for lr, wd in [(0.05, 0.03), (0.1, 0.01)]:
        for seed in [3, 4, 5]:
            r = run(lr, wd, seed, steps=20000)
            results.append(r)
            print('C deep lr={} wd={} s={} spikes={} first={} acc={:.3f} wall={}s'.format(
                lr, wd, seed, r['n_spikes'], r['events'][0][0] if r['events'] else None,
                r['test_acc'], r['wall_s']), flush=True)
    with open(os.path.join(OUTDIR, 'r2_results.jsonl'), 'w') as f:
        for r in results:
            f.write(json.dumps(r) + '\n')
    print('wrote', len(results), 'runs')


if __name__ == '__main__':
    main()
