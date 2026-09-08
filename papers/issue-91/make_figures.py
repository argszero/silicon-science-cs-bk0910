#!/usr/bin/env python3
"""Issue #91 — core figures from canonical_results.json (R225).

fig1_flip_profile.png : pooled flip rate vs d/w buckets + theory (1-dw)/2
                        (universal window geometry, Lemma 2)
fig2_p2_law.png       : per-boundary H = meanR*C/(Vp*s*) vs w/12 parity, 35 pts
                        (flip-margin height law, Lemma 3) + residual panel
fig3_p3_shift.png     : Family C s*(M) log-log with 1/M law + miscalibration
                        band (Lemma 4)
"""
import json
import math
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
FIGD = os.path.join(HERE, 'figures')
os.makedirs(FIGD, exist_ok=True)
with open(os.path.join(HERE, 'canonical_results.json')) as f:
    res = json.load(f)

# ---- fig1: flip-profile collapse -----------------------------------------
fig, ax = plt.subplots(figsize=(5.6, 4.2))
prof = res['flip_profile']
xs = [p['dw_mid'] for p in prof]
ys = [p['flip_rate'] for p in prof]
ths = [p['theory'] for p in prof]
ax.plot([0, 1], [0.5, 0.0], 'k--', lw=1.4, label='theory (1−dw)/2')
ax.plot(xs, ys, 'o-', ms=5, color='#1f77b4', lw=1.2,
        label='pooled, 7 boundaries × 5 ε')
worst = max(abs(y - t) for y, t in zip(ys, ths))
ax.set_xlabel('log-distance to nearest crossing $d/w$ (units of error half-width)')
ax.set_ylabel('P(plan flips)')
ax.set_title('Universal fragility-window geometry\nworst |err| = %.4f' % worst)
ax.set_xlim(-0.03, 1.03)
ax.legend(loc='upper right', fontsize=8)
fig.tight_layout()
fig.savefig(os.path.join(FIGD, 'fig1_flip_profile.png'), dpi=150)

# ---- fig2: P2 parity H vs w/12 --------------------------------------------
rows = res['p2_per_boundary']
labels = sorted(set(r['boundary'] for r in rows))
colors = plt.cm.tab10([i % 10 for i in range(len(labels))])
lmap = dict(zip(labels, colors))
fig, (a1, a2) = plt.subplots(1, 2, figsize=(9.5, 4.0))
w12 = sorted(set(r['w12'] for r in rows))
for r in rows:
    a1.plot([r['w12']], [r['H']], 'o', ms=5, color=lmap[r['boundary']], alpha=0.85)
mx = max(w12) * 1.15
a1.plot([0, mx], [0, mx], 'k--', lw=1)
a1.set_xscale('log'); a1.set_yscale('log')
a1.set_xlabel('predicted w/12')
a1.set_ylabel('measured H = meanR·C/(V′·s*)')
a1.set_title('P2 zero-parameter law (7 boundaries × 5 ε)')
for lab in labels:
    a1.plot([], [], 'o', color=lmap[lab], label=lab, ms=5)
a1.legend(fontsize=6.5, loc='lower right', ncol=2)
# residual panel: ratio vs eps
allw = sorted(set(r['eps'] for r in rows))
for r in rows:
    a2.plot([r['eps']], [r['ratio']], 'o', ms=5, color=lmap[r['boundary']], alpha=0.85)
a2.axhspan(0.9, 1.1, color='gray', alpha=0.15)
a2.axhline(1.0, color='k', lw=0.8, ls=':')
a2.set_xscale('log')
a2.set_xlabel('ε (error level)')
a2.set_ylabel('H / (w/12)')
a2.set_title('residual vs ε (O(w) corrections at large ε)')
fig.tight_layout()
fig.savefig(os.path.join(FIGD, 'fig2_p2_law.png'), dpi=150)

# ---- fig3: P3 crossover shift + miscalibration band ----------------------
fig, (a1, a2) = plt.subplots(1, 2, figsize=(9.5, 4.0))
sh = res['p3']['shift_law']
Ms = [s['M'] for s in sh]
ss = [s['s_star_analytic'] for s in sh]
a1.loglog(Ms, ss, 'o-', color='#d62728', ms=6)
a1.set_xlabel('per-match multiplier M')
a1.set_ylabel('crossover s*(M)')
a1.set_title('P3: crossover shift s*(M) = (N−P)/(M·N) ∝ 1/M')
mb = res['p3']['miscal_band']
a1.text(0.05, 0.9, 'slope −1 (1/M law)', transform=a1.transAxes, fontsize=9)
a2.axvspan(mb['s_true'], mb['s_cal'], color='#ff7f0e', alpha=0.35)
a2.set_xscale('log')
a2.set_xlim(1e-4, 1)
a2.set_ylim(0, 1.1)
a2.set_yticks([])
a2.set_xlabel('selectivity s (log scale)')
a2.set_title('Miscalibration band: calibrate M′=10, true M=100\n'
             'band = 1.00 decades = 25% of log range')
# oracle-correct regions annotated
a2.text(mb['s_true'] * 0.5, 0.6, 'index correct', ha='center', fontsize=8)
a2.text(mb['s_cal'] * 4.5, 0.6, 'scan correct', ha='center', fontsize=8)
a2.annotate('systematically wrong\nplan for every query here',
            xy=(math.sqrt(mb['s_true'] * mb['s_cal']), 0.5),
            xytext=(math.sqrt(mb['s_true'] * mb['s_cal']) * 0.35, 0.85),
            fontsize=7.5, ha='center',
            arrowprops=dict(arrowstyle='->', lw=0.8))
fig.tight_layout()
fig.savefig(os.path.join(FIGD, 'fig3_p3_shift.png'), dpi=150)

print('wrote:')
for fn in sorted(os.listdir(FIGD)):
    p = os.path.join(FIGD, fn)
    print('  %s (%d bytes)' % (fn, os.path.getsize(p)))
