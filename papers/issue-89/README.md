# Issue #89 — Predicting Detector-Based Defense Collapse: A Shared Toy-Benchmark Test of the Channel-Control Hypothesis across Reasoning, Sequence, and Input Monitors

**Status**: submission (2026-09-08).

**Contribution level: `theory+empirics`** — a falsifiable cross-family mechanism law (three
propositions with proof sketches) instantiated and measured on three controlled toy families of one
shared detection task (5 control levels × 8 seeds each; exact ground truth; pooled Wilson 95% CIs;
committed byte-identical reproduction; 30-check two-tier validator). The three 2026 real-family
collapse reports (arXiv 2608.00583 reasoning-monitor / 2608.01388 formal-monitor / 2608.01373
input-guard) serve as qualitative calibration targets, with a quantitative fit to the published
entropy-coverage bound (2608.01388) as the partial-discrete special case.

## Manuscript

`manuscript.md` — full paper (abstract with falsifiable claim + contribution-level declaration;
introduction with the three anchors and stated differences; methods on the shared task and three
control instantiations; theory with Propositions F / PD / PC and the unified claim; results 5.1–5.5
with three result tables and two figures; registered-prior reconciliation P1–P3 (all confirmed);
discussion with the two-question deployment checklist; threats; conclusion; references [1]–[5]).
Figures in `figures/` (2 PNGs). `expected_output.committed.json` is the committed reference output
(sha256 `9ce135cff6aa1e35cd784ba8ab700b8c7e7462c8fb107c6647ef9e5891d7b08a`).

## One-command reproduction

```bash
bash reproduce.sh                  # ~2–4 min single-thread CPU; pure Python 3, no third-party deps
```

**What it does** (see `reproduce.py`): stage 1 runs the deterministic canonical experiment
(`canonical_exp.py`) to regenerate `expected_output.json`; stage 2 runs `validate.py`, a two-tier
validator, against the committed reference + structural laws.

**Expected output** (final line):

```
REPRODUCE: ALL STAGES PASSED
```

with the validator printing `VALIDATE: ALL CHECKS PASSED (30)` and every `PASS:` line above it.

**Two-tier validator** (`validate.py`):

- **Tier A (structural, exact, env-independent)**: A1 family-A laws (top-R recall monotone up as
  entropy H falls; top-R ≥ random-R at every concentrated cell; random-R within [0, 0.35]); A2
  family-B floor equality (|recall − FPR| ≤ 0.02 for every q>0, q=0 n/a) plus the committed entropy
  sweep at q=1.0 across all five alphas (A2c); A3 family-C laws (recall monotone non-increasing in
  eps; recall(0) ≥ 0.9; recall(high eps) ≤ 0.001; crossover eps* present) plus FP-availability arm
  (A3e FP monotone non-decreasing; A3f FP(high eps) > 0.5); A4 determinism — rerunning the
  experiment reproduces `expected_output.committed.json` byte-identically (sha256 equal).
- **Tier B (statistical, vs committed reference)**: B1 bidirectional Wilson-95% CI containment —
  every committed cell recall (and family-C FP rate) lies inside the freshly computed CI and vice
  versa (small pooling tolerance); B2 CI internal consistency (ci_lo ≤ point ≤ ci_hi).

**Environment**: pure Python 3 (stdlib only) for `reproduce.sh`. Figures require matplotlib
(`/usr/bin/python3 -m pip show matplotlib` on the test machine: matplotlib 3.9.4); regenerating
figures is optional: `/usr/bin/python3 make_figures.py` (writes into `figures/`).

## Files

| File | Purpose |
|---|---|
| `manuscript.md` | full manuscript (theory+empirics) |
| `figures/fig1_steering_laws.png` | 3-panel steering laws (Fig 1) |
| `figures/fig2_monitor_info.png` | family-A monitor-information map (Fig 2) |
| `canonical_exp.py` | deterministic canonical experiment (all cells, 5 levels × 8 seeds × 3 families) |
| `expected_output.committed.json` | committed reference output |
| `validate.py` | two-tier validator (30 checks) |
| `reproduce.py` / `reproduce.sh` | one-command reproduction driver |
| `make_figures.py` | optional figure regeneration (needs matplotlib) |

## Key numbers (committed)

- **Family A (partial-discrete; informed top-R=4 rules)**: recall = top-R coverage, rising
  monotonically with attack concentration: 0.127 [0.126, 0.129] at H=5.00 bits → 0.972 [0.971,
  0.973] at H=1.13 bits; uninformed random-R stays ~R/K ≈ 0.125.
- **Family B (full control)**: recall on the rewritten subset = FPR floor 0.099–0.100 for every
  q>0, and — entropy sweep, q=1.0 — 0.0997 at every H in {5.00 … 1.13} (P2 entropy-independence).
- **Family C (partial-continuous)**: recall 0.998 (eps=0) → ~0.000 (eps ≥ 4.5) with crossover
  eps* ∈ (1.5, 3.0); FP on benign 0.00000 → 0.74771 [0.74557, 0.74983] (eps=6.0).

All priors P1–P3 registered in issue #89 (2026-09-07) confirmed; no registered prior refuted.
