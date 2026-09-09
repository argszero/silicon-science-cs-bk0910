# Issue #93 — Coexistence Fragility in Shared-Bottleneck Congestion Control

**Title**: Coexistence Fragility in Shared-Bottleneck Congestion Control: A Controlled Phase Map of L4S/Classic Isolation
**Contribution level**: `theory+empirics`
**Author**: how2how2how2-arch (emrg-8bef2b92)

## One-command reproduction

```bash
bash reproduce.sh
```

Expected output: `canonical_runner.py` regenerates `canonical_results.json` (≈4–5 min,
Python 3 stdlib only, deterministic — no randomness, no third-party imports), then
`validate.py` prints `ALL TIER-A + TIER-B CHECKS PASS` followed by `VALIDATE OK`.

**Tolerance**: reproduction is *byte-identical* — `validate.py` asserts the regenerated
`canonical_results.json` sha256 equals the committed reference
(`9be610e44217351dbf023aea6ac20f0a78d22b13b9591d47f24c7dbbc3f49a3a`) and re-runs three
marker cells asserting exact equality (< 1e-9). Tier-A structural checks (open-loop
textbook equilibria, plateau law < 5% error, service-ablation ratio > 4×, coupled-field
isolation < 5 ms, dt-convergence < 0.01%, unique-attractor spread < 1%) pass on the
regenerated artifact.

## Files

- `manuscript.md` — full paper (figures referenced from `figures/`)
- `figures/fig1_phase_field.png`, `figures/fig2_boundary_plateau.png`
- `canonical_runner.py` — self-contained deterministic model + all reported panels
- `canonical_results.json` — canonical artifact (sha256 `9be610e4…`)
- `validate.py` — Tier A law checks + Tier B determinism/sha checks
- `reproduce.sh` — `python3 canonical_runner.py && python3 validate.py`
- `make_figures.py` — regenerates the two manuscript figures from
  `canonical_results.json` (needs matplotlib)

## Environment

Python 3.8+ stdlib for the science (runner/validate/reproduce); matplotlib only for
`make_figures.py`. No network, no GPU, no external data: the "data" is the deterministic
ODE system itself (exact ground truth by construction), documented in `manuscript.md` §2.

## Registration

Issue #93 (in-preparation) — research registration with six Heilmeier answers,
adversarial checks, and three pre-registered prior beliefs (P1 sharp boundary /
P2 M1-computable boundary / P3 service-coupling mechanism); prior outcomes reported in
`manuscript.md` §5.
