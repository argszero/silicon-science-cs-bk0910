#!/usr/bin/env python3
"""Issue #89 — core figures from expected_output.json.

fig1_steering_laws.png : 3-panel; per family, recall (with Wilson CI band)
   vs the family's control quantity — the paper's central mechanism figure.
fig2_monitor_info.png  : family-A 2D map — recall vs entropy H for the two
   monitor-information conditions (top-R informed vs random-R).
"""
import json
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, 'expected_output.json')
OUT = os.path.join(HERE, 'figures')
os.makedirs(OUT, exist_ok=True)

with open(DATA) as f:
    d = json.load(f)

# ---- fig1: three steering laws ----
fig, axes = plt.subplots(1, 3, figsize=(13, 4))

# A: recall vs entropy H (partial-discrete, topR)
fa = d['family_A_partial_discrete']
Hs = [fa[k]['H'] for k in sorted(fa, key=lambda k: fa[k]['H'])]
rs = [fa[k]['topR']['recall'] for k in sorted(fa, key=lambda k: fa[k]['H'])]
los = [fa[k]['topR']['ci_lo'] for k in sorted(fa, key=lambda k: fa[k]['H'])]
his = [fa[k]['topR']['ci_hi'] for k in sorted(fa, key=lambda k: fa[k]['H'])]
ax = axes[0]
ax.plot(Hs, rs, 'o-', color='#1f77b4', lw=2)
ax.fill_between(Hs, los, his, color='#1f77b4', alpha=0.2)
ax.axhline(0.10, color='grey', ls='--', lw=1, label='detector FPR')
ax.set_xlabel('attack entropy H (bits)')
ax.set_ylabel('recall on attacks')
ax.set_title('(a) partial-discrete\n(coverage-limited: informed R=4 rules)')
ax.legend(fontsize=8)
ax.set_ylim(-0.02, 1.05)

# B: recall vs q (full control)
fb = d['family_B_full']
qs = [float(k) for k in sorted(fb, key=float)]
rs = [fb[k]['recall'] if fb[k]['n'] else float('nan') for k in sorted(fb, key=float)]
los = [fb[k]['ci_lo'] if fb[k]['n'] else float('nan') for k in sorted(fb, key=float)]
his = [fb[k]['ci_hi'] if fb[k]['n'] else float('nan') for k in sorted(fb, key=float)]
ax = axes[1]
ax.plot(qs, rs, 's-', color='#d62728', lw=2)
ax.fill_between(qs, los, his, color='#d62728', alpha=0.2)
ax.axhline(0.10, color='grey', ls='--', lw=1, label='detector FPR')
ax.set_xlabel('rewrite fraction q (full control)')
ax.set_ylabel('recall on controlled subset')
ax.set_title('(b) full control\n(unbounded: recall = FPR floor)')
ax.legend(fontsize=8)
ax.set_ylim(-0.02, 1.05)

# C: recall vs eps (partial-continuous) + FP availability arm
fc = d['family_C_partial_continuous']
es = [float(k) for k in sorted(fc, key=float)]
rs = [fc[k]['recall'] for k in sorted(fc, key=float)]
los = [fc[k]['ci_lo'] for k in sorted(fc, key=float)]
his = [fc[k]['ci_hi'] for k in sorted(fc, key=float)]
ax = axes[2]
ax.plot(es, rs, '^-', color='#2ca02c', lw=2, label='recall on attacks')
ax.fill_between(es, los, his, color='#2ca02c', alpha=0.2)
if all('fp' in fc[k] for k in fc):
    frs = [fc[k]['fp']['rate'] for k in sorted(fc, key=float)]
    flos = [fc[k]['fp']['ci_lo'] for k in sorted(fc, key=float)]
    fhis = [fc[k]['fp']['ci_hi'] for k in sorted(fc, key=float)]
    ax.plot(es, frs, 's--', color='#ff7f0e', lw=2, label='FP on benign (availability)')
    ax.fill_between(es, flos, fhis, color='#ff7f0e', alpha=0.15)
ax.set_xlabel('L2 perturbation budget eps')
ax.set_ylabel('rate')
ax.set_title('(c) partial-continuous\n(budget-limited: crossover eps*)')
ax.set_ylim(-0.02, 1.05)
ax.legend(fontsize=8, loc='center left')

fig.suptitle('Steering laws of detector-based defenses by attacker channel-control type '
             '(one shared detection task, detector FPR 0.10)', fontsize=11)
fig.tight_layout(rect=(0, 0, 1, 0.94))
fig.savefig(os.path.join(OUT, 'fig1_steering_laws.png'), dpi=160)
print('fig1 written')

# ---- fig2: family-A monitor-information map ----
fig2, ax2 = plt.subplots(1, 1, figsize=(6.5, 4.6))
Hs = [fa[k]['H'] for k in sorted(fa, key=lambda k: fa[k]['H'])]
for mode, color, marker in (('topR', '#1f77b4', 'o'), ('randomR', '#ff7f0e', 's')):
    rs = [fa[k][mode]['recall'] for k in sorted(fa, key=lambda k: fa[k]['H'])]
    los = [fa[k][mode]['ci_lo'] for k in sorted(fa, key=lambda k: fa[k]['H'])]
    his = [fa[k][mode]['ci_hi'] for k in sorted(fa, key=lambda k: fa[k]['H'])]
    ax2.plot(Hs, rs, marker + '-', color=color, lw=2, label='informed (top-R)' if mode == 'topR' else 'uninformed (random-R)')
    ax2.fill_between(Hs, los, his, color=color, alpha=0.2)
ax2.axhline(0.10, color='grey', ls='--', lw=1, label='detector FPR')
ax2.axhline(4 / 32, color='grey', ls=':', lw=1)
ax2.text(5.0, 4 / 32 + 0.015, 'R/K = 0.125 (chance)', fontsize=8, ha='right')
ax2.set_xlabel('attack entropy H (bits)')
ax2.set_ylabel('recall on attacks')
ax2.set_title('Partial-discrete family: monitor information determines\nwhether the entropy-coverage bound is reached')
ax2.legend(fontsize=9)
ax2.set_ylim(-0.02, 1.05)
fig2.tight_layout()
fig2.savefig(os.path.join(OUT, 'fig2_monitor_info.png'), dpi=160)
print('fig2 written')
