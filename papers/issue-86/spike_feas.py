#!/usr/bin/env python3
"""Feasibility spike: do toy MLP+LayerNorm nets show reproducible loss spikes
under weight decay, and does spike onset track the weight-norm-criticality chain
(norm collapse -> sharpness/lambda_max rise) vs a pure EoS threshold?

Run with the issue-79 venv python (torch CPU). Outputs JSON lines + csv to argv[1].
"""
import json
import math
import sys
import time

import numpy as np
import torch
import torch.nn as nn

OUT = sys.argv[1] if len(sys.argv) > 1 else '/tmp/spike_out.jsonl'

torch.manual_seed(0)
np.random.seed(0)


def make_data(n_train=4000, n_test=1000, n_class=20, dim=64, seed=0):
    g = np.random.RandomState(seed)
    centers = g.randn(n_class, dim) * 2.0
    xs = []
    ys = []
    for _ in range(n_train + n_test):
        c = g.randint(n_class)
        x = centers[c] + g.randn(dim) * 1.0
        xs.append(x)
        ys.append(c)
    xs = np.array(xs, dtype=np.float32)
    ys = np.array(ys, dtype=np.int64)
    return xs[:n_train], ys[:n_train], xs[n_train:], ys[n_train:]


class MLPLN(nn.Module):
    def __init__(self, dim=64, hid=256, n_class=20):
        super().__init__()
        self.fc1 = nn.Linear(dim, hid, bias=True)
        self.ln1 = nn.LayerNorm(hid)
        self.fc2 = nn.Linear(hid, hid, bias=True)
        self.ln2 = nn.LayerNorm(hid)
        self.fc3 = nn.Linear(hid, n_class, bias=True)

    def forward(self, x):
        h = torch.relu(self.ln1(self.fc1(x)))
        h = torch.relu(self.ln2(self.fc2(h)))
        return self.fc3(h)


def hessian_lambda_max(model, loss_fn, xb, yb, iters=25):
    """Power iteration top-eigenvalue of Hessian w.r.t. all params (RAdam-free)."""
    params = [p for p in model.parameters() if p.requires_grad]
    # random init vector
    v = []
    for p in params:
        v.append(torch.randn_like(p))
    vnorm = math.sqrt(sum(torch.sum(torch.pow(vi, 2)).item() for vi in v))
    for vi in v:
        vi.div_(vnorm)
    lam = 0.0
    for _ in range(iters):
        model.zero_grad()
        out = model(xb)
        loss = loss_fn(out, yb)
        grads = torch.autograd.grad(loss, params, create_graph=True)
        Hv = torch.autograd.grad(grads, params, grad_outputs=v, retain_graph=False)
        # normalize
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


def run(wd, lr, steps, seed, dtype=torch.float32, lam_every=400, tag=''):
    torch.manual_seed(seed)
    np.random.seed(seed)
    Xtr, ytr, Xte, yte = make_data(seed=seed)
    Xtr = torch.from_numpy(Xtr)
    ytr = torch.from_numpy(ytr)
    Xte = torch.from_numpy(Xte)
    yte = torch.from_numpy(yte)
    model = MLPLN()
    model = model.to(dtype)
    loss_fn = nn.CrossEntropyLoss()
    opt = torch.optim.SGD(model.parameters(), lr=lr, weight_decay=wd, momentum=0.0)
    n = Xtr.shape[0]
    batch = 128
    rec = {'wd': wd, 'lr': lr, 'seed': seed, 'dtype': str(dtype).split('.')[-1],
           'loss': [], 'w1norm': [], 'w3norm': [], 'lam': [], 'gradnorm': [], 'step': []}
    spike_thresh = 0.3
    prev_min = 1e9
    spikes = 0
    first_spike_step = -1
    t0 = time.time()
    for step in range(steps):
        idx = torch.randperm(n)[:batch]
        xb = Xtr[idx].to(dtype)
        yb = ytr[idx]
        model.train()
        opt.zero_grad()
        out = model(xb)
        loss = loss_fn(out, yb)
        loss.backward()
        gnorm = math.sqrt(sum(torch.sum(p.grad ** 2).item() for p in model.parameters() if p.grad is not None))
        opt.step()
        lv = loss.item()
        rec['loss'].append(lv)
        rec['gradnorm'].append(gnorm)
        rec['step'].append(step)
        with torch.no_grad():
            rec['w1norm'].append(model.fc1.weight.norm().item())
            rec['w3norm'].append(model.fc3.weight.norm().item())
        if lv < prev_min:
            prev_min = lv
        elif lv > prev_min + spike_thresh:
            spikes += 1
            if first_spike_step < 0:
                first_spike_step = step
            prev_min = lv
        if lam_every and step % lam_every == 0 and step > 0:
            with torch.no_grad():
                xb2 = Xtr[torch.randperm(n)[:256]].to(dtype)
                yb2 = ytr[:256] if len(ytr) > 0 else ytr
                # align: use same random subset ordering safely
                perm = torch.randperm(n)[:256]
                xb2 = Xtr[perm].to(dtype)
                yb2 = ytr[perm]
            try:
                lam = hessian_lambda_max(model, loss_fn, xb2, yb2, iters=15)
                rec['lam'].append((step, lam))
            except Exception as e:
                rec['lam'].append((step, float('nan')))
    rec['spikes'] = spikes
    rec['first_spike_step'] = first_spike_step
    rec['wall_s'] = round(time.time() - t0, 1)
    # test acc
    model.eval()
    with torch.no_grad():
        out = model(Xte.to(dtype))
        acc = (out.argmax(1) == yte).float().mean().item()
    rec['test_acc'] = acc
    return rec


def main():
    results = []
    for wd in [0.0, 1e-3, 1e-2, 3e-2]:
        for seed in [0, 1, 2]:
            r = run(wd, lr=0.05, steps=3500, seed=seed, dtype=torch.float32)
            results.append(r)
            print(json.dumps({k: r[k] for k in ['wd', 'seed', 'spikes', 'first_spike_step', 'test_acc', 'wall_s']}), flush=True)
    # fp64 discriminator on the strongest-decay cell
    for seed in [0]:
        r = run(1e-2, lr=0.05, steps=3500, seed=seed, dtype=torch.float64)
        results.append(r)
        print('FP64', json.dumps({k: r[k] for k in ['wd', 'seed', 'spikes', 'first_spike_step', 'test_acc', 'wall_s']}), flush=True)
    with open(OUT, 'w') as f:
        for r in results:
            f.write(json.dumps(r) + '\n')
    print('wrote', OUT, len(results), 'runs')


if __name__ == '__main__':
    main()
