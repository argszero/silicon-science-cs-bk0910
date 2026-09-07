#!/usr/bin/env python3
"""Issue #86 figure generation (R203): fig1 phase-map, fig2 freeze arms,
fig3 excursion traces. Reads committed outputs (pm_out, r2, r3) + trace_out3
(dense traces, bit-identical freeze-branch protocol). Outputs 3 PNGs.

Runs with /usr/bin/python3 (matplotlib available). Number anchors asserted
against the manuscript draft so figures and text cannot drift apart.
"""
import glob
import json
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'figures')  # committed figures live at issue root
os.makedirs(OUT, exist_ok=True)

LRS = [0.02, 0.05, 0.1, 0.2]
WDS = [0.0, 0.003, 0.01, 0.03, 0.1]

# ---------------- load data ----------------
pm = {}
for f in glob.glob(os.path.join(HERE, 'pm_out', 'pm_*.json')):
    d = json.load(open(f))
    pm[(d['lr'], d['wd'], d['seed'])] = d

r2 = [json.loads(l) for l in open(os.path.join(HERE, 'r2_out', 'r2_results.jsonl'))]
r3 = [json.loads(l) for l in open(os.path.join(HERE, 'r3_out', 'r3_results.jsonl'))]

traces = {}
for f in glob.glob(os.path.join(HERE, 'trace_out3', 'trace_*.json')):
    d = json.load(open(f))
    traces[(d['freeze'], d['seed'])] = d

# ---------------- fig 1: phase-map heatmap ----------------
mean_spikes = np.zeros((len(LRS), len(WDS)))
for i, lr in enumerate(LRS):
    for j, wd in enumerate(WDS):
        mean_spikes[i, j] = np.mean([pm[(lr, wd, s)]['n_spikes'] for s in (0, 1, 2)])

# assert manuscript Table 1
T1 = [[0, 0, 0, 0, 0], [0, 0, 0, 0.3, 4.0], [0, 0, 1.0, 9.3, 13.0], [0, 0, 10.3, 30.7, 67.7]]
for i in range(4):
    for j in range(5):
        assert abs(mean_spikes[i, j] - T1[i][j]) < 0.15, 'Table-1 mismatch %s' % (i, j)

fig, ax = plt.subplots(figsize=(6.2, 4.4))
im = ax.imshow(mean_spikes, cmap='YlOrRd', aspect='auto')
for i in range(4):
    for j in range(5):
        v = mean_spikes[i, j]
        txt = '%.0f' % v if v >= 10 else ('%.1f' % v if v != 0 else '0')
        ax.text(j, i, txt, ha='center', va='center',
                color='white' if v > 25 else 'black', fontsize=10)
ax.set_xticks(range(5))
ax.set_xticklabels(['0', '3e-3', '1e-2', '3e-2', '1e-1'])
ax.set_yticks(range(4))
ax.set_yticklabels(['0.02', '0.05', '0.1', '0.2'])
ax.set_xlabel('weight decay')
ax.set_ylabel('learning rate $\\eta$')
ax.set_title('Mean loss-spike events per run (20k steps, 3 seeds)')
# mark money cell
ax.add_patch(plt.Rectangle((4.5 - 0.5, 3 - 0.5), 1, 1, fill=False,
                           edgecolor='blue', linewidth=2.5))
fig.colorbar(im, ax=ax, label='mean spike events', shrink=0.9)
fig.tight_layout()
fig.savefig(os.path.join(OUT, 'fig1_phase_map.png'), dpi=160)
plt.close(fig)
print('fig1 written; matrix\n', mean_spikes)

# ---------------- fig 2: freeze-arm outcome bars ----------------
arms = [('none', 'control'), ('hid', 'freeze hidden (fc1+fc2)'), ('out', 'freeze readout (fc3)')]
fr_runs = {a: [r for r in r2 if r['freeze'] == a and r['exp'] == 'freeze'] for a, _ in arms}
def post_branch(r):
    return any(s >= 300 for (s, e) in r['events'])
spiked = {a: sum(1 for r in fr_runs[a] if post_branch(r)) for a, _ in arms}
n_arm = {a: len(fr_runs[a]) for a, _ in arms}
assert (spiked['none'], spiked['hid'], spiked['out']) == (5, 0, 5), spiked

# r3 post-branch (steps > 300) full-lambda means per arm+seed
lam_post = {}
for d in r3:
    if d['freeze'] == 'none':
        arm = 'none'
    else:
        arm = d['freeze']
    steps = np.array(d['lam_steps'])
    lam_post[(arm, d['seed'])] = np.mean(np.array(d['lam_full'])[steps > 300])
# assert manuscript values: freeze=hid s1 25.2
assert abs(lam_post[('hid', 1)] - 25.2) < 0.3, lam_post[('hid', 1)]

fig, ax1 = plt.subplots(figsize=(6.6, 4.4))
labels = ['control', 'freeze hidden\n(fc1+fc2)', 'freeze readout\n(fc3)']
xs = np.arange(3)
frac = [spiked[a] / n_arm[a] for a, _ in arms]
colors = ['#c44e52', '#55a868', '#4c72b0']
bars = ax1.bar(xs, frac, 0.5, color=colors, alpha=0.85)
for x, f, a in zip(xs, frac, [a for a, _ in arms]):
    ax1.text(x, f + 0.03, '%d/%d spiked\n(post-branch)' % (spiked[a], n_arm[a]), ha='center', fontsize=10)
ax1.set_ylim(0, 1.5)
ax1.set_ylabel('fraction of seeds spiking (post-branch)')
ax1.set_xticks(xs)
ax1.set_xticklabels(labels)
ax1.axhline(1.0, color='grey', ls=':', lw=0.8)

ax2 = ax1.twinx()
for x, a in zip(xs, [a for a, _ in arms]):
    means = [lam_post[(a, s)] for s in (0, 1) if (a, s) in lam_post]
    for s in (0, 1):
        if (a, s) in lam_post:
            ax2.scatter(x + 0.14, lam_post[(a, s)], marker='v', s=45,
                        color='black', alpha=0.75, zorder=5)
    ax2.scatter([], [], marker='v', s=45, color='black', label='post-branch $\\lambda_{max}$ mean (per seed, r3)')
ax2.axhline(10.0, color='blue', ls='--', lw=1.2)
ax2.text(2.35, 11.5, '$2/\\eta = 10$', color='blue', fontsize=9)
ax2.set_ylabel('mean post-branch $\\lambda_{max}$ (full Hessian)')
ax2.set_ylim(0, 40)
ax2.legend(loc='upper left', fontsize=8.5, framealpha=0.9)
ax1.set_title('Causal freeze arms on the money cell ($\\eta$=0.2, wd=0.1)')
fig.tight_layout()
fig.savefig(os.path.join(OUT, 'fig2_freeze_arms.png'), dpi=160)
plt.close(fig)
print('fig2 written; post-branch lam means:', lam_post)

# ---------------- fig 3: excursion traces (control vs freeze=hid, s0) ----------------
c = traces[('none', 0)]
h = traces[('hid', 0)]
assert c['n_spikes'] == 4 and h['n_spikes'] == 0
# bit-identical pre-branch (step <= 300), loss arrays every 20 steps
npre = sum(1 for s in c['step'] if s <= 300)
assert all(c['loss'][i] == h['loss'][i] for i in range(npre))

fig, (axa, axb) = plt.subplots(2, 1, figsize=(7.6, 5.6), sharex=True,
                               gridspec_kw={'height_ratios': [1, 1]})
axa.plot(c['step'], c['loss'], '-', color='#c44e52', lw=1.2, label='control (fc1/fc2 adapt)')
axa.plot(h['step'], h['loss'], '-', color='#55a868', lw=1.2, label='freeze=hid (branch @300)')
axa.axvline(300, color='grey', ls='--', lw=1)
axa.text(310, axa.get_ylim()[1] if False else 1.1, 'branch @ step 300', fontsize=8, color='grey')
for (w0, w1) in c['events']:
    axa.axvspan(w0, w1, color='red', alpha=0.12)
axa.set_ylabel('loss (sampled /20 steps)')
axa.set_ylim(0, 1.3)
axa.legend(loc='upper right', fontsize=8.5)
axa.set_title('Money cell $\\eta$=0.2 wd=0.1: loss and sharpness traces, seed 0')

thr = 10.0
axb.plot(c['lam_steps'], c['lam_full'], 'o-', ms=3, color='#c44e52', lw=0.8,
         label='control $\\lambda_{max}$')
axb.plot(h['lam_steps'], h['lam_full'], 'o-', ms=3, color='#55a868', lw=0.8,
         label='freeze=hid $\\lambda_{max}$')
axb.axhline(thr, color='blue', ls='--', lw=1.2)
axb.text(1200, 13, '$2/\\eta = 10$', color='blue', fontsize=9)
for (w0, w1) in c['events']:
    axb.axvspan(w0, w1, color='red', alpha=0.12)
axb.set_ylim(-20, 100)
axb.set_xlabel('training step')
axb.set_ylabel('$\\lambda_{max}$ (power iter.)')
axb.legend(loc='upper left', fontsize=8.5)
fig.tight_layout()
fig.savefig(os.path.join(OUT, 'fig3_excursion_trace.png'), dpi=160)
plt.close(fig)
print('fig3 written; control events=%s hid spikes=%d' % (c['events'], h['n_spikes']))
print('ALL FIGURES WRITTEN to', OUT)
