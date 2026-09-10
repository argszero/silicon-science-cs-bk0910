#!/usr/bin/env python3
"""Issue #98 figures — When Does Proactive Beat Reactive?

Deterministic matplotlib (Agg) figures drawn from canonical_results.json
(no simulation inside; every data point is the committed artifact).

  fig1_phase_map.png  — rho*(R; phi, m): 3 panels (phi=0.1/0.25/0.5), lines per m,
                        shaded m>=wall dead zone, closed-form curves (dashed) overlaid
  fig2_boundary_law.png — boundary-law parity: sim vs closed form at m=1 across
                        phi x R (identity parity line)
  fig3_margin_wall.png — reactive/proactive cost & violation vs margin m; wall at
                        m*=(b+A)/b=1.2 (violation shield)
  fig4_aliasing.png    — K-bin action snapping residual-violation penalty (off-grid
                        amplitudes), monotone O(1/K) + continuous floor reference

Stdlib + matplotlib only. Usage: /usr/bin/python3 make_figures.py  (Agg, no display)
"""
import json, math, os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), 'figures')  # committed area: papers/issue-98/figures/
os.makedirs(OUT, exist_ok=True)
d = json.load(open(os.path.join(HERE, 'canonical_results.json')))

plt.rcParams.update({'figure.dpi': 110, 'font.size': 8.5, 'axes.grid': True,
                     'grid.alpha': 0.25, 'savefig.bbox': 'tight'})

def cf_boundary(phi, W, L, R):
    num = -((1 - phi) * W - phi * L)
    den = phi * L * (1 - R) - (1 - phi) * W
    return num / den if den != 0 else None

B, A, W, P, L = 100.0, 20.0, 20, 100, 10
WALL = 1.2

# ---------------------------------------------------------------- fig1 phase map
p2 = d['P2_surface']
RS = [0.2, 0.5, 1.0, 2.0, 5.0, 10.0]
MS_L = [1.0, 1.05, 1.1, 1.15]
fig, axes = plt.subplots(1, 3, figsize=(9.4, 3.1), sharey=True)
for ax, phi in zip(axes, [0.1, 0.25, 0.5]):
    for m_m, col in zip(MS_L, ['#1f77b4', '#2ca02c', '#ff7f0e', '#d62728']):
        ys = [p2[str(m_m)][str(phi)][str(R)] for R in RS]
        ax.plot(RS, ys, marker='o', ms=3.5, lw=1.3, color=col, label=f'm={m_m}')
        cfys = [cf_boundary(phi, W, L, R) for R in RS]
        ax.plot(RS, cfys, ls='--', lw=0.7, color=col, alpha=0.45)
    ax.axvspan(1.2, 10, color='gray', alpha=0.18)
    ax.text(10 * 0.96, 0.97, 'reactive\nnever loses\n(m≥m*)', fontsize=6.6,
            ha='right', va='top', color='0.25')
    ax.set_title(f'φ={phi}', fontsize=9)
    ax.set_xscale('log'); ax.set_xticks(RS); ax.set_xticklabels(RS, fontsize=6.4)
    ax.set_ylim(0, 1.05)
    if phi == 0.1:
        ax.set_ylabel('ρ*  (accuracy proactive needs to tie reactive)')
    ax.legend(fontsize=6, loc='upper right')
axes[0].set_xlabel('cost ratio R = violation ÷ resource', fontsize=8)
fig.suptitle('Proactive-vs-reactive phase map: boundary accuracy ρ*(R; φ, m);  '
             'proactive wins iff ρ ≥ ρ*', fontsize=10)
fig.savefig(os.path.join(OUT, 'fig1_phase_map.png'))
plt.close(fig)

# ---------------------------------------------------------------- fig2 boundary law parity
p1 = d['P1_closed_form']
fig, ax = plt.subplots(figsize=(4.3, 3.6))
for phi in [0.1, 0.25, 0.5]:
    sims, cfs = [], []
    for R in RS:
        c = p1[str(phi)][str(R)]
        if c['sim'] is not None and c['cf'] is not None:
            sims.append(c['sim']); cfs.append(c['cf'])
    ax.plot(cfs, sims, 'o', ms=4, label=f'φ={phi}')
    ax.plot(cfs, cfs, 'k-', lw=0.7, alpha=0.5)
ax.set_xlabel('closed-form ρ* (fallback arm)'); ax.set_ylabel('simulation ρ* (grid 0.01)')
ax.set_title('Boundary law parity (m=1)', fontsize=9)
ax.legend(fontsize=7); ax.set_aspect('equal')
fig.savefig(os.path.join(OUT, 'fig2_boundary_law.png'))
plt.close(fig)

# ---------------------------------------------------------------- fig3 margin wall
p3 = d['P3_margin_wall']
p6 = d['P6_resource_floor']
ms = sorted([float(k) for k in p3 if k != 'wall_m'])
rv = [p3[str(m)]['reactive_viol'] for m in ms]
rc = [p3[str(m)]['reactive_cost'] / 1e6 for m in ms]
pc = [p3[str(m)]['pro_rho05_cost'] / 1e6 for m in ms]
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.6, 3.0))
ax1.plot(ms, [v / 1000 for v in rv], 'o-', color='#d62728', lw=1.3, label='reactive violations')
ax1.axvline(WALL, color='k', ls='--', lw=0.9)
ax1.annotate('margin wall\nm* = (b+A)/b = 1.2', xy=(WALL, 18), xytext=(1.065, 15),
             fontsize=7.5, arrowprops=dict(arrowstyle='->', lw=0.7))
ax1.set_xlabel('margin m (calibrated headroom)'); ax1.set_ylabel('reactive violations (×10³)')
ax1.set_title('Margin as violation shield', fontsize=9)
ax2.plot(ms, rc, 'o-', color='#1f77b4', lw=1.3, label='reactive (calibrated)')
ax2.plot(ms, pc, 's--', color='#ff7f0e', lw=1.1, label='proactive ρ=0.5')
ax2.axvline(WALL, color='k', ls='--', lw=0.9)
ax2.set_xlabel('margin m'); ax2.set_ylabel('cost (M)')
ax2.set_title('Proactive never wins at ρ=0.5 (R=1)', fontsize=9)
ax2.legend(fontsize=7)
fig.suptitle('RLScale-Bench m=1.43 (70% target) sits beyond the wall', fontsize=9.5, y=1.04)
fig.tight_layout()
fig.savefig(os.path.join(OUT, 'fig3_margin_wall.png'))
plt.close(fig)

# ---------------------------------------------------------------- fig4 aliasing
p4 = d['P4_aliasing']
KS = [2, 4, 8, 20]
extras = [p4[str(k)]['extra_vs_cont'] / 1e3 for k in KS]
cont_v = p4['continuous']['violation'] / 1e3
fig, ax = plt.subplots(figsize=(4.3, 3.2))
ax.plot(KS, extras, 'o-', color='#2ca02c', lw=1.4, label='extra cost vs continuous (×10³)')
ax.plot(KS, [p4[str(k)]['violation'] / 1e3 for k in KS], 's--', color='#d62728', lw=1.1,
        label='residual violation (×10³)')
ax.axhline(cont_v, color='k', ls=':', lw=0.9)
ax.annotate('continuous floor', xy=(13, cont_v), fontsize=6.8, color='0.2')
ax.set_xscale('log', base=2); ax.set_xticks(KS); ax.set_xticklabels(KS)
ax.set_xlabel('action bins K (raise snapped to K levels over [0,A])')
ax.set_ylabel('×10³ (cost units)')
ax.set_title('Action aliasing: monotone penalty O(1/K)', fontsize=9)
ax.legend(fontsize=6.6)
fig.savefig(os.path.join(OUT, 'fig4_aliasing.png'))
plt.close(fig)

print('figures written to', OUT)
for f in sorted(os.listdir(OUT)):
    print('  ', f, os.path.getsize(os.path.join(OUT, f)), 'bytes')
