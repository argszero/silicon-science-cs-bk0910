# Issue #98 — When Does Proactive Beat Reactive? A Controlled Phase Map of Predictive-Controller Advantage in Adaptive Resource Allocation

Submission package for issue #98 (cs.DC x mechanism science, `theory+empirics`).

## Contents

- `manuscript.md` — full manuscript (theory + empirics).
- `canonical_runner.py` — consolidated deterministic model runner (P0-P7); produces `canonical_results.json` (stdlib only, deterministic, no wall-clock fields).
- `canonical_results.json` — canonical artifact (sha256 pinned, see below).
- `validate.py` — 279 structural + semantic checks on the canonical artifact.
- `reproduce.sh` — one-command reproduction (run + validate + sha).
- `make_figures.py` + `figures/` — derived figures (fig1 phase map, fig2 boundary parity, fig3 margin wall, fig4 aliasing). Run with `/usr/bin/python3` (requires matplotlib 3.9.4).
- `research/` — registration artifacts and dev scripts (git-ignored, not part of this package).

## One-command reproduction

```bash
bash reproduce.sh
```

Expected output: canonical run writes `canonical_results.json`; `validate.py` prints
`VALIDATE 279/279 ALL PASS`; the script ends with

```
sha256 bdd4498e069518931b2990a6d446b1e114ea9cc1190396d5457ecb43b128c985
REPRODUCE ALL GREEN
```

Deterministic by construction: stdlib-only, fixed mask seed 7, no RNG, no timing; the
artifact is byte-identical across runs and machines (sha lock asserted inside
`validate.py`). Runtime about 1 s.

Figures (optional, not part of the core reproduction):

```bash
/usr/bin/python3 make_figures.py   # matplotlib 3.9.4 required
```

## Claims verified by validate.py (summary)

- Anchors: none/oracle/reactive/proactive(rho=1); reactive resource equals oracle equals sum_d (lag is a pure cyclic shift); proactive rho=1 identical to oracle.
- P1 closed-form boundary law rho* = -[(1-phi)W - phi L]/[phi L (1-R) - (1-phi) W] vs sim over 18 (phi x R) cells (tolerance 0.01-0.02 grid); phi=0.5 tie-line rho* = 1/(1+R).
- P2 canonical (m x phi x R) surface: rho* falls with R, falls with phi, rises with m; monotonicity validator-checked; m at or above 1.2 = margin wall (all None).
- P3 margin wall: reactive violations 20,000, 10,000, 1,000, 0 at m* = 1.2 = (b+A)/b; proactive never wins beyond it.
- P4 aliasing: K-bin snapping extras 2000, 1040, 480, 400 at K = 2/4/8/20 (strictly decreasing, O(1/K)), continuous floor 2,000.
- P5 rise time: reactive violation 20,000 (tau=0) falls to 15,500 (tau=20); cost monotone.
- P6 same-margin floor parity: reactive res equals proactive(rho=1) res equals m x sum_d; rho=0.8 excess equals m x A x (W x n_fp - L x n_fn) = 20,000 x m.
- P7 RLScale-Bench committed cell: m=1.43 (70% target) beyond the wall yields zero violations for both controllers; consistent with published finding (i).
