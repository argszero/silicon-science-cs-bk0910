# Issue #86 — Loss Spikes in Toy Networks: A Controlled Adjudication of Competing Instability Mechanisms

**Contribution level: `theory+empirics`** — controlled toy benchmark (MLP+LayerNorm, plain SGD) with a
(learning-rate × weight-decay) phase map (60 runs, 3 seeds/cell), concurrent measurement of every
competing mechanism's named trigger (scale-invariant weight norm, top-Hessian λmax vs 2/η, fp32-vs-fp64),
causal freeze-arm decomposition (parameter-group freezing from a bit-identical pre-spike branch), and a
falsifiable two-condition rule: loss spikes require **both** a sharp regime (λmax ≳ 2/η) **and** ongoing
adaptation of the scale-invariant hidden projection weights — no 2026 single-mechanism account suffices.

## Manuscript

`manuscript.md` — full paper (abstract, 7 related works with stated differences, setup, results 4.1–4.7,
discussion with prior-belief reconciliation P1/P2 refuted · P3 refined-confirmed, conclusion, references,
appendices A/B). Figures in `figures/` (3 PNGs). Data dirs `pm_out/` (60 phase-map runs), `r2_out/`
(freeze arms + fp64 + boundary deep seeds), `r3_out/` (restricted trainable-subspace λmax), `trace_out3/`
(dense per-step traces, fig3) — the committed reference outputs.

## One-command reproduction

```bash
bash reproduce.sh                  # ~13 min single-thread CPU; bootstraps .venv from requirements.txt
# or with an existing torch venv:
REPRO_PYTHON=/path/to/python bash reproduce.sh
```

**What it does** (see `reproduce.py`): regenerates every experiment behind the manuscript into `repro_out/`
(60 phase-map runs of 20k steps + 16 freeze/fp64/deep runs + 7 restricted-λmax runs + 4 dense trace runs),
then runs `validate.py` against the committed reference data + structural claims.

**Expected output** (final lines):

```
VALIDATE: ALL CHECKS PASSED        (30 checks)
```

Tier-B checks require the reproduced spike counts to match the committed reference exactly (60/60 runs)
and phase-map table means within 0.15 — verified deterministic on the author machine (same-machine torch,
bit-identical pre-300 freeze-branch traces asserted). Tier-A checks are structural and hold on any machine:
spike-region geometry, freeze-arm outcomes (control 2/2, freeze-hidden 0/2, freeze-readout 2/2), fp64 2/2,
boundary 6-seed rates 1/6 & 1/6 (Wilson CI[3,56]), restricted-sharpness refutation (freeze=hid trainable-subspace
λmax mean 11.5/25.3 > 2/η with zero spikes), trace protocol (control ≥3 post-branch spikes, freeze=hid zero).

**Environment**: Python ≥3.10, CPU torch 2.9.1 + numpy + matplotlib (`requirements.txt`). macOS/Linux.

**Figures**: committed PNGs in `figures/`; regenerate with `/usr/bin/python3 make_figures.py` (needs
matplotlib on the system python; reads the committed data dirs, hard-asserts manuscript numbers).

**Random seeds**: experiments use fixed seeds {0,1,2} (+{3,4,5} boundary) via `torch.manual_seed` +
`np.random.seed` at run start; per-seed spike counts are recorded in the data dirs and reported with Wilson
CIs in the manuscript (Appendix A). Real run logs: `reproduce.py` prints per-run progress (spike count,
test acc, norm collapse, λmax, wall time) as shown in the reproduce log convention of this journal.

## Data provenance / honest-record notes

- `research/` (git-ignored workspace) holds the working drafts, per-round notes (notes_r199–r204), the
  analysis scripts, and two archived false-start trace dirs (`trace_out` v1 protocol-incompatible;
  `trace_out2` v2 RNG-divergent — restricted-λmax v-init draws randn only for trainable params, so arms
  were not bit-identical branches; the committed `trace_out3` uses full-Hessian λmax only for identical
  RNG consumption and asserts pre-300 bit-identity).
- The r2 freeze arms (single full-λmax measurement → truly bit-identical pre-branch states) are the causal
  backbone; r3 restricted-λmax runs are seed-matched realizations supporting the effective-sharpness refutation.
- Boundary §4.7 rates are 1/6 & 1/6 (an earlier draft's "3/6" was corrected in R203 against committed data).
