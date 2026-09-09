# Issue #96 — When Prefetching Flips: Helpful–Harmful Crossover in Hardware Prefetching

Submission package for issue #96 (cs.AR × mechanism science, `theory+empirics`).

## Contents

- `manuscript.md` — full manuscript (theory + empirics).
- `canonical_runner.py` — consolidated deterministic mean-field model; produces `canonical_results.json` (stdlib only, no randomness, no wall-clock fields).
- `canonical_results.json` — canonical artifact (sha256 pinned, see below).
- `validate.py` — 70 structural + semantic checks on the canonical artifact.
- `reproduce.sh` — one-command reproduction (run + validate + sha).
- `make_figures.py` + `figures/` — derived figures (fig1 phase field, fig2 pollution law, fig3 mechanism ablation). Run with `/usr/bin/python3` (requires matplotlib).
- `research/` — registration artifacts (git-ignored, not part of this package).

## One-command reproduction

```bash
bash reproduce.sh
```

Expected output: canonical run writes `canonical_results.json`; `validate.py` prints
`validate: 70 checks, 0 failures` / `ALL CHECKS PASS`; the script ends with

```
sha256 canonical_results.json = 576c55115a8d13f593183db81c23139fce3180bb0a28c73e33ba26209ea41d9f
== REPRODUCE ALL GREEN ==
```

Deterministic by construction: stdlib-only fixed-point arithmetic, no RNG, no timing;
the artifact is byte-identical across runs and machines (sha lock asserted inside
`validate.py`). Runtime ≈ 1 s.

Figures (optional, not part of the core reproduction):

```bash
/usr/bin/python3 make_figures.py   # matplotlib 3.9.4 required
```

## Claims verified by validate.py (summary)

- Anchors: baseline E0=3.060, oracle E=1.0 exact, added-bytes collapse sp=0.827 < 1.
- P1 phase map: 22 harmful / 380 cells at π=0; boundary ac*(cv) monotone 0.0878@cv0.5 →
  0.1221@cv0.9, undefined below cv=0.2 (never harmful); transition width ≤ 0.05 (grid-res sharp).
- P2 mechanism: decoupled service removes all harm (22 → 0); corner sp 0.827 → 2.509.
- P3 pollution: harm 22/60/87/109/129/142 over π = 0…1; ac*max tracks π/(1+π) (0.505 at π=1
  ≈ folklore 50%); pollution-free arm = 22 (bandwidth floor) at every π; combined law at
  cv=0.9 is sub-additive (0.210 vs 0.289 at π=0.2; … 0.350 vs 0.622 at π=1).
- Robustness: ac* falls with P, rises with s (directions physically sensible, 9 cells).
- P8 bus pressure (m-sweep at fixed s=40): ac*max 0.085 (m·s=0.16) → 0.126 (0.4) →
  0.155 (0.96), saturating far below folklore 0.5 even near bus saturation.
