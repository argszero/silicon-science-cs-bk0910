#!/usr/bin/env python3
"""Issue #93 figures (R238). fig1 = 2D phase fields; fig2 = boundary curve + plateau law."""
import json, os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

HERE = '/Users/argszero/scm/github.com/argszero/silicon-science-cs/papers/issue-93'
r = json.load(open(os.path.join(HERE, 'canonical_results.json')))
figdir = os.path.join(HERE, 'figures')
os.makedirs(figdir, exist_ok=True)

# ---- fig1: 2D delay field g=0 vs g=1 ----
f0, f1 = r['P4_field']['0'], r['P4_field']['1']
NCS2, NLS2 = f0['NCS'], f0['NLS']
Z0 = np.array(f0['delay_ms']); Z1 = np.array(f1['delay_ms'])
fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.6), sharey=True)
for ax, Z, g in ((axes[0], Z0, 0), (axes[1], Z1, 1)):
    im = ax.imshow(Z, aspect='auto', origin='lower', cmap='RdYlBu_r',
                   extent=[NCS2[0], NCS2[-1], NLS2[0], NLS2[-1]],
                   vmin=0, vmax=20, interpolation='nearest')
    ax.set_xscale('log'); ax.set_yscale('log')
    ax.set_title('uncoupled (g = 0)' if g == 0 else 'coupled dualQ (g = 1)')
    ax.set_xlabel('classic flows  $N_c$')
    ax.set_xticks(NCS2); ax.set_yticks(NLS2)
    ax.set_yticklabels([str(n) for n in NLS2])
axes[0].set_ylabel('scalable (L4S) flows  $N_l$')
fig.colorbar(im, ax=axes, fraction=0.025, pad=0.02, label='L4S-class FIFO queueing delay (ms)')
fig.suptitle('Figure 1. L4S/classic coexistence phase map at a shared FIFO bottleneck '
             '(dual-queue PI marking; classic target 15 ms, L4S target 1 ms, buffer 5 BDP)')
fig.tight_layout()
fig.savefig(os.path.join(figdir, 'fig1_phase_field.png'), dpi=160)
plt.close(fig)

# ---- fig2: (a) boundary curve Nc*(Nl); (b) plateau-law parity ----
bnd = r['P3_boundary']
nls = sorted(int(k) for k in bnd)
ncs = [bnd[str(n)]['Nc_star'] for n in nls]
plat = r['P6_plateau']
fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.4))
ax = axes[0]
ax.plot(nls, ncs, 'o-', color='#c0392b', lw=1.8)
ax.axhline(0, color='gray', lw=0.6)
ax.set_xlabel('scalable (L4S) flows  $N_l$')
ax.set_ylabel('critical classic flows  $N_c^*$')
ax.set_title('(a) Coexistence boundary  $N_c^*(N_l)$ — uncoupled FIFO')
ax.annotate('coexistence\n(fragile)\nbelow (above) curve', xy=(0.55, 0.4),
            xycoords='axes fraction', fontsize=9, ha='center', color='#555')
for n, c in zip(nls, ncs):
    ax.annotate('%.1f' % c, (n, c), textcoords='offset points', xytext=(0, 6),
                fontsize=7.5, ha='center', color='#333')
ax = axes[1]
meas = [plat[k]['d_meas'] for k in sorted(plat)]
pred = [plat[k]['pred'] for k in sorted(plat)]
labels = ['T=15,N_l=20', 'T=15,N_l=40', 'T=30,N_l=20', 'T=30,N_l=40']
ax.plot([0, 45], [0, 45], '--', color='gray', lw=1, label='y = x')
ax.plot(pred, meas, 's', color='#2471a3', ms=8)
for (px, mx, lab) in zip(pred, meas, labels):
    ax.annotate(lab, (px, mx), textcoords='offset points', xytext=(6, 4), fontsize=8)
ax.set_xlabel('predicted  $(T_C + q_l)/C$  (ms)')
ax.set_ylabel('measured fragile delay (ms)')
ax.set_title('(b) Plateau law: delay = $(T_C+q_l)/C$')
ax.legend(loc='lower right')
fig.suptitle('Figure 2. Boundary and delay-plateau laws of coexistence fragility',
             y=1.0)
fig.tight_layout()
fig.savefig(os.path.join(figdir, 'fig2_boundary_plateau.png'), dpi=160)
plt.close(fig)
print('figures written:', os.listdir(figdir))
