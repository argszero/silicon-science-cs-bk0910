# Plan Regret as a Phase Transition — Shared Benchmark Study (Issue #91)

**Title**: Plan Regret as a Phase Transition: A Shared Benchmark Test of the
Crossover-Fragility Law across Query-Execution Strategy Families
**Contribution level**: `theory+empirics` (closed-form theory model validated across
3 synthetic strategy families / 7 envelope boundaries / 5 error levels / 8 seeds;
deterministic byte-identical reproduction; independent two-tier validator)

## One-command reproduction

```bash
bash reproduce.sh
```

Expected outcome:
1. `canonical_runner.py` runs the full deterministic study (3 families × 7 boundaries
   × 5 error levels ε × 8 seeds × 2000 queries) and writes `canonical_results.json`.
2. `validate_v0.py` runs two independent check tiers and reports **7/7 checks passed**:
   - Tier A (structural, recomputed from first principles): A1 support (0 out-of-band
     flips), A2 oracle flips at every analytic boundary, A3 flip profile tracks
     (1−dw)/2 (worst |err| < 0.05), A4 P3 crossover exact.
   - Tier B (value checks over the artifact): B1 schema (7 boundaries × 5 ε = 35 rows),
     B2 P2 law (median H/(w/12) ∈ [0.7, 1.4]), B3 miscalibration band ≈ 1.00 decade.

**Determinism**: pure Python 3 stdlib; fixed seeds 0..7. `canonical_results.json` is
byte-identical across runs — committed reference checksum
`sha256 457c0acfd1a34374b32426edd34f67f6eaa2c112ec756f0bf0b364fe007734ff`.

Runtime: CPU seconds–minutes, single thread. No third-party dependencies for the
reproduction itself.

## Figures (optional, require matplotlib)

```bash
/usr/bin/python3 make_figures.py    # matplotlib 3.9.4 available in the system python
```

Writes `figures/fig1_flip_profile.png`, `figures/fig2_p2_law.png`,
`figures/fig3_p3_shift.png`.

## Files

| File | Purpose |
|---|---|
| `manuscript.md` | Full manuscript (theory + empirics) |
| `canonical_runner.py` | Deterministic study runner → `canonical_results.json` |
| `validate_v0.py` | Two-tier independent validator (7 checks) |
| `toy_regret_core.py` | Shared task machinery (sampler, error model, regret) |
| `canonical_results.json` | Committed deterministic artifact (checksum above) |
| `reproduce.sh` | One-command wrapper (runner + validator) |
| `make_figures.py` | Figure generation from the artifact |
| `figures/` | fig1 flip-profile collapse · fig2 P2 law parity · fig3 P3 shift + band |
| `research/` | Registration notes, heilmeier, theory derivation (git-ignored workspace) |

## Headline results (see manuscript for full tables)

- **P1 / Lemma 1 (support)**: regret is exactly zero outside windows of one error
  half-width (w = ln(1+ε)) around every envelope crossing — 0 violations across
  5.6M query decisions.
- **Lemma 2 (universal flip profile)**: P(flip | d/w) = (1 − dw)/2 — pooled worst
  |err| = 0.0177 across 23,346 window queries, family- and ε-independent. Window
  *width* = w (error reach), independent of cost-model margin.
- **P2 / Lemma 3 (zero-parameter height law)**: window-mean regret =
  (|V′|·s*/C)·w/12; measured H/(w/12) median 1.060, p10/p90 0.838/1.326 across
  7 boundaries × 5 ε. Geometry factor |V′|·s*/C spans 0.45–3.70 (8×) — predicted
  with no fitted parameters.
- **P3 / Lemma 4 (crossover shift + miscalibration band)**: heterogeneous structures
  shift the crossover as s*(M) = (N−P)/(M·N) ∝ 1/M; a planner calibrated at per-match
  cost M′ facing true M is systematically wrong on a band of width ln(M′/M) = 1.00
  decades = 25.0% of the log-selectivity range at 10× mismatch.

## Prior-belief reporting (registered R221 before any run)

- P1 thresholded regret in every family → **CONFIRMED in strong form** (exact zero,
  not merely small, outside windows).
- P2 window width scales with flip-margin 1/|V′| → **REFINED**: width = w (error
  reach); the margin-dependence lives in window-mean *height* (H = w/12).
- P3 steep/heterogeneous cost shifts crossover locations → **CONFIRMED
  quantitatively** (s*(M) ∝ 1/M; band = ln(M′/M) decades).
