#!/usr/bin/env python3
"""Issue #96 figures — fig1 phase field, fig2 pollution law, fig3 mechanism ablation.

Run with /usr/bin/python3 (matplotlib 3.9.4). Reads canonical_results.json and
re-solves the 380-cell field through canonical_runner's model (same code path).
Figures are derived artifacts; the one-command core reproduction (reproduce.sh)
does not depend on them.
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import canonical_runner as cr

HERE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(HERE, 'figures')
os.makedirs(FIG, exist_ok=True)
d = json.load(open(os.path.join(HERE, 'canonical_results.json')))
p0, p1, p2, p3, p5 = d['P0_anchors'], d['P1_field_pi0'], d['P2_coupling'], d['P3_pollution'], d['P5_ablation']

m0, P, s = 0.01, 200.0, 40.0
acs = [round(0.05 * k, 2) for k in range(1, 21)]
cvs = [round(0.05 * k, 2) for k in range(1, 20)]
E0 = p0['E0_baseline']

# ---------- fig1: phase field at pi=0 ----------
sp = np.zeros((len(acs), len(cvs)))
for j, cv in enumerate(cvs):
    for i, ac in enumerate(acs):
        sol = cr.solve_two(m0, P, s, cv, ac, 0.0)
        sp[i, j] = E0 / sol[0] if sol else 0.0
fig, ax = plt.subplots(figsize=(7.6, 5.2))
im = ax.pcolormesh(np.array(cvs), np.array(acs), sp, cmap='RdYlGn', vmin=0.0, vmax=2.0, shading='auto')
# boundary overlay
star_cvs = sorted(p1['ac_star_by_cv'], key=float)
star_vals = [p1['ac_star_by_cv'][k] for k in star_cvs]
b_cvs = [float(k) for k in star_cvs if p1['ac_star_by_cv'][k] is not None]
b_vals = [v for v in star_vals if v is not None]
ax.plot(b_cvs, b_vals, 'k--', lw=2, label=r'boundary $ac^*(cv)$')
ax.axhline(0.5, color='gray', lw=1, ls=':', label='folklore "~50% accuracy"')
ax.set_xlabel('coverage cv'); ax.set_ylabel('accuracy ac')
ax.set_title('Fig 1. Speedup phase field, bandwidth coupling only ($\\pi=0$): '
             f'{p1["harmful_cells"]} harmful / {p1["n_cells"]} cells; '
             f'ac* {b_vals[0]:.3f}$\\rightarrow${b_vals[-1]:.3f}')
cb = fig.colorbar(im, ax=ax, label='speedup vs no-prefetch')
ax.legend(loc='upper left', fontsize=9)
fig.tight_layout(); fig.savefig(os.path.join(FIG, 'fig1_phase_field.png'), dpi=150); plt.close(fig)

# ---------- fig2: pollution law + folklore reconciliation ----------
pis = [float(k) for k in p3.keys()]
meas = [p3[k]['ac_star_max'] for k in p3.keys()]
law = [pi / (1.0 + pi) for pi in pis]
fig, ax = plt.subplots(figsize=(7.2, 5.0))
ax.plot(pis, meas, 'o-', lw=2, label='measured $ac^*_{\\max}$ (over cv)')
xs = np.linspace(0, 1, 200)
ax.plot(xs, xs / (1 + xs), '-', color='C1', lw=1.5, label='closed form $\\pi/(1+\\pi)$')
ax.axhline(0.5, color='gray', lw=1, ls=':', label='folklore "~50%"')
ax.axhline(p3['0.0']['ac_star_max'], color='C2', lw=1, ls='--', label='bandwidth floor 0.126')
ax.annotate('folklore = pure-pollution limit', xy=(1.0, 0.505), xytext=(0.42, 0.62),
            fontsize=9, arrowprops=dict(arrowstyle='->'))
ax.set_xlabel('cache pollution probability $\\pi$'); ax.set_ylabel('max crossover accuracy $ac^*_{\\max}$')
ax.set_title('Fig 2. Pollution channel reconciles the folklore 50% rule')
ax.legend(fontsize=9); ax.grid(alpha=0.3)
fig.tight_layout(); fig.savefig(os.path.join(FIG, 'fig2_pollution_law.png'), dpi=150); plt.close(fig)

# ---------- fig3: mechanism ablation (two panels) ----------
fig, (a, b) = plt.subplots(1, 2, figsize=(9.6, 4.2))
# (a) coupling ablation: harmful cells + corner speedup
labels = ['coupled service', 'decoupled service']
vals = [p2['harm_coupled'], p2['harm_decoupled']]
bars = a.bar(labels, vals, color=['#d62728', '#2ca02c'])
a.set_ylabel('harmful cells / 380'); a.set_ylim(0, 30)
for bar, v in zip(bars, vals):
    a.text(bar.get_x() + bar.get_width() / 2, v + 0.6, str(v), ha='center', fontsize=11)
a.set_title(f'Coupling ablation: corner sp {p2["corner_coupled_sp"]:.2f} $\\rightarrow$ '
            f'{p2["corner_decoupled_sp"]:.2f} (identical volume)')
# (b) pollution attribution
pis5 = list(p5.keys())
full = [p5[k]['harm_full'] for k in pis5]
pf = [p5[k]['harm_pollution_free'] for k in pis5]
xx = np.arange(len(pis5)); w = 0.36
b.bar(xx - w / 2, full, w, label='full model', color='#d62728')
b.bar(xx + w / 2, pf, w, label='pollution-free', color='#2ca02c')
b.set_xticks(xx); b.set_xticklabels([f'$\\pi$={k}' for k in pis5])
b.set_ylabel('harmful cells / 380'); b.set_title('Pollution is the marginal channel over the 22-cell bandwidth floor')
b.legend(fontsize=9)
for i, (f_, pf_) in enumerate(zip(full, pf)):
    b.text(i - w / 2, f_ + 1, str(f_), ha='center', fontsize=9)
    b.text(i + w / 2, pf_ + 1, str(pf_), ha='center', fontsize=9)
fig.suptitle('Fig 3. Same-volume mechanism attribution: harm = bandwidth/request coupling, not pollution', y=1.02)
fig.tight_layout(); fig.savefig(os.path.join(FIG, 'fig3_mechanism_ablation.png'), dpi=150,
                                bbox_inches='tight'); plt.close(fig)

print('figures written:', sorted(os.listdir(FIG)))
