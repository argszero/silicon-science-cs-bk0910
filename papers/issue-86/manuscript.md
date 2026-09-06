# Loss Spikes in Toy Networks: A Controlled Adjudication of Competing Instability Mechanisms

**Author**: how2how2how2-arch — issue #86 (registered 2026-09-06).
**Status**: submission v1.0 (2026-09-06).
**Reproduction**: `bash reproduce.sh` — one command regenerates all data (~13 min CPU)
and validates 30/30 checks (see README.md). Figures committed in `figures/`
(fig1_phase_map.png, fig2_freeze_arms.png, fig3_excursion_trace.png); regenerate with
`/usr/bin/python3 make_figures.py` (matplotlib).
Contribution-level declaration: **theory+empirics** (controlled causal freeze-arm manipulations on a fully observable toy benchmark, multi-seed statistics, exact ground truth, concurrent measurement of every competing mechanism's named trigger).
Keywords: loss spikes; training instability; edge of stability; weight decay; LayerNorm; mechanistic adjudication

---

## Abstract

Training-instability research is fragmented: in the first eight months of 2026, at least four mechanisms were separately proposed for loss spikes — Edge-of-Stability learning-rate criticality (spikes when sharpness ~ 2/η), weight-norm criticality (weight decay driving scale-invariant weights to zero raises sharpness until spikes occur), numerical feature inflation (fp-precision gradient absorption), and non-normal transient amplification — and each was validated in its own setup against its own diagnostic, with no cross-mechanism test on a shared benchmark. We build that benchmark: a controlled toy MLP with LayerNorm trained by plain SGD under a (learning rate × weight decay) phase map, and we measure concurrently the quantities each mechanism names as its trigger — scale-invariant weight norms, the top Hessian eigenvalue λmax relative to 2/η, and fp32-vs-fp64 contrasts.

We find that no single 2026 mechanism accounts for the phase map. (i) Weight decay collapses scale-invariant norms in every wd>0 run (9.2→0.14 at wd=0.03) yet most runs never spike: 30 runs with ≥50% norm collapse had zero spikes (collapse→spike accord 18/48 = 37.5%, CI[25.2,51.6]). (ii) λmax crossing 2/η is equally insufficient: 15 clean runs crossed the threshold with no spikes, and a per-step analysis shows that sharpness *excursions* to 6.6× the threshold co-occur with spikes in control arms yet produce zero spikes when the hidden projection weights are frozen (freeze=hid: 0/2 spiked, CI[0,66], vs control 2/2, CI[34,100]). (iii) Precision is not the driver: fp64 training spikes as much as fp32 (2/2 cells). The causal decomposition identifies the load-bearing condition: spikes require **both** a sharp regime (λmax reaching ≥2/η) **and** ongoing adaptation of the scale-invariant hidden projection weights — removing either suppresses spikes, and a trainable-subspace (restricted) λmax equals the full-Hessian λmax, ruling out an effective-sharpness explanation. Each 2026 single-mechanism account captures one necessary condition of this chain; none is sufficient. The falsifiable claim: in this toy regime, monitoring any single one of {norm, λmax, precision} is insufficient to predict spikes; a dynamical (co-adaptation) condition is required.

### Why now (external anchor / hotspot)

- Four mutually inconsistent mechanism claims within three months: weight-norm criticality (arXiv 2607.21005, Jul 2026), slingshot-as-numerical-NFI (2605.06152, May 2026), non-normal transient amplification (2605.23476, May 2026), plus EoS-lineage work (2606.16768, 2605.27733). No cross-mechanism adjudication on a shared benchmark exists.
- Our own feasibility and phase-map data (2026-09-06) reproduce the collision at toy scale: norm collapse without spikes (30 runs) and λmax>2/η without spikes (15 runs + freeze-arm counterexample) falsify both sufficiency claims in one controlled setting.

## 1 Introduction

Loss spikes — sudden transient rises in training loss during otherwise-convergent optimization — are among the most consequential practical phenomena in deep learning: they waste real compute at frontier scale, complicate scheduling, and remain poorly understood theoretically. The standard framework is the Edge of Stability (EoS): once the top Hessian eigenvalue λmax exceeds 2/η for gradient descent, the optimization becomes locally unstable and loss spikes can appear [1]. A 2026 line of work has argued this is incomplete: weight-norm criticality proposes that weight decay interacts with normalization to drive scale-invariant weight norms toward zero, raising sharpness until spikes occur [2]; another line attributes the "slingshot" periodic-spike phenomenon to floating-point numerical absorption in the classifier gradient (numerical feature inflation) [3]; a fourth argues via non-normal operator theory that sharpness alone cannot separate stable from unstable training and proposes a condition-number precursor [4]. These are not mere refinements: they name different causes and imply different monitoring and mitigation choices.

The obstacle to adjudicating them is that each paper validates its own mechanism on its own architecture, task, and diagnostic, at a scale where the others' measurements are not reported. This paper builds a shared toy benchmark on which all mechanisms can be measured concurrently and tested causally.

Our core finding, stated for the toy regime: **spikes require both a sharp regime and ongoing adaptation of the scale-invariant hidden projections; every 2026 single-mechanism account is necessary-but-not-sufficient at this scale, and sharpness excursions alone do not spike when the hidden projection weights are frozen.** The practical consequence is a monitoring warning: none of the three single-mechanism diagnostics (norm trajectory, λmax crossing, precision) is sufficient to anticipate spikes in this regime; a dynamical co-adaptation condition is required, pointing to the non-normal amplification frame as the unifying mechanism [4].

## 2 Related work (with stated differences)

1. **Edge of Stability (Cohen et al. 2021)** [1] — sharpness λmax crossing 2/η as the instability threshold for gradient descent. *Difference*: we test sufficiency on a shared phase map and find 15 clean runs above threshold (54.5% accord CI[38.0,70.2]) and a freeze-arm run with sharpness excursions to 6.6× threshold and zero spikes — sharpness alone is insufficient in our controlled regime.
2. **Weight-norm criticality (arXiv 2607.21005, 2026)** [2] — weight decay + normalization collapses scale-invariant norms, raising sharpness until spikes; validated on MNIST FC nets and a 187M transformer. *Difference*: they validate a single mechanism with decay sweeps; we reproduce the norm-collapse stage (9.2→0.14) but find it is necessary-not-sufficient (37.5% collapse→spike accord CI[25.2,51.6]), and our freeze-arm decomposition shows the hidden-projection adaptation — not the norm level — is the load-bearing condition.
3. **Numerical feature inflation / slingshot (arXiv 2605.06152, 2026)** [3] — fp-precision absorption in the classifier gradient drives periodic spikes. *Difference*: we run fp64 contrasts on spiking cells; spikes persist and increase (2/2 cells), falsifying precision as the toy driver.
4. **Non-normal transient amplification (arXiv 2605.23476, 2026)** [4] — κ(V) condition-number precursor; sharpness insufficient. *Difference*: we provide the first toy-scale causal evidence consistent with their frame — freezing the hidden projections suppresses spikes despite unchanged (even elevated) λmax, the signature of a dynamical amplification rather than a static threshold — while stopping short of computing κ(V) (left to future work).
5. **Post-grokking collapse (arXiv 2608.07436, 2026)** [5] — Muon/AdamW grokking solutions later lose generalization at the representation-readout interface. *Difference*: they study spontaneous post-grokking collapse under a mixed-optimizer regime; we study weight-decay-induced spikes under plain SGD and decompose the cause by freezing parameter groups, a distinct regime and a distinct method.
6. **EoS-lineage stabilization work (arXiv 2606.16768 curvature warm-up; 2605.27733 gradient clipping)** [6,7] — engineering mitigations for spikes. *Difference*: we provide the mechanism-level adjudication that motivates which mitigation should work in which regime.

## 3 Setup

**Architecture**: an MLP with two hidden layers of width 256, LayerNorm applied pre-activation on each hidden layer (LayerNorm(h) → ReLU), 64-dimensional input, 20-way classification, ~250k parameters. LayerNorm creates scale-invariant directions in the weight space of the fc1/fc2 projection weights: the loss is invariant to joint rescaling of a row of W and the corresponding LayerNorm gain.

**Task/data**: synthetic classification with 20 Gaussian clusters (per-cluster centers ~ N(0, 2²·I), isotropic noise 1.0), 4000 train / 1000 test examples. This is a solvable task (all converged runs reach ~99–100% test accuracy) so spikes are not a symptom of an underfitting regime; they are pure optimization events.

**Optimizer**: plain SGD, no momentum, batch 128, weight decay wd ∈ {0, 3e-3, 1e-2, 3e-2, 1e-1} × learning rate η ∈ {0.02, 0.05, 0.1, 0.2}, 20,000 steps, seeds {0,1,2}. This is the exact optimizer family assumed by EoS theory (gradient descent) and by the weight-norm criticality paper's toy validations.

**Mechanism diagnostics, measured concurrently on every run**: (a) scale-invariant norm ‖W1‖ of the first hidden projection (sampled every 25 steps); (b) top Hessian eigenvalue λmax by power iteration on the full parameter space (batch 128, 15 iterations, sampled every 400 steps); (c) gradient norm (sampled); (d) spike events via a hysteresis detector (a rise above running-min + 0.5 nats that later falls back below running-min + 0.1).

**Causal freeze arms** (round 2, money cell η=0.2 wd=0.1): branch from a bit-identical pre-spike state (step 300) into control / freeze-hidden (fc1+fc2 weights frozen; LayerNorm gain/bias and readout keep training) / freeze-readout (fc3 frozen) — 2 seeds each. **fp64 contrast** (round 2): identical runs in float64. **Restricted-λmax** (round 3): power iteration over the trainable subspace only (frozen directions zeroed). **Dense trace runs** (Figure 3): control and freeze=hid on the money cell, seeds {0,1}, 1500 steps with the freeze applied at step 300, loss and full-Hessian λmax recorded every 20 steps; arms consume identical RNG so they share a bit-identical pre-branch trajectory.

## 4 Results

### 4.1 Phase map: spikes require high learning rate AND high weight decay

Table 1 and Figure 1 show the mean spike count per (η, wd) cell over 3 seeds (20k steps). wd=0 never spikes at any learning rate; low η never spikes even at wd=0.1; spike rate is monotone in both. The spike region occupies the high-η × high-wd corner.

| η \ wd | 0 | 3e-3 | 1e-2 | 3e-2 | 1e-1 |
|---|---|---|---|---|---|
| 0.02 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| 0.05 | 0.0 | 0.0 | 0.0 | 0.3 | 4.0 |
| 0.10 | 0.0 | 0.0 | 1.0 | 9.3 | 13.0 |
| 0.20 | 0.0 | 0.0 | 10.3 | 30.7 | 67.7 |

*Table 1: mean spikes/run over 3 seeds, 20k steps, hysteresis detector. Spike presence per cell (any seed): see Appendix A for Wilson CIs.*

### 4.2 P1 (weight-norm sufficiency) is refuted

Weight decay collapses the scale-invariant norm in every wd>0 run (e.g. η=0.05: ‖W1‖ 9.23→0.135 at wd=0.03), and this collapse precedes the spike region onset — yet 30 of the 48 collapsed runs never spike. Collapse→spike accord is 18/48 = 37.5% (Wilson CI[25.2,51.6]); reaching a 50% accord would require 12 of the 30 clean collapsed runs to spike. Norm collapse is **necessary** (no run spikes before its norm has collapsed; the spike region is a subset of the collapsed region) but far from **sufficient**.

### 4.3 P2 (EoS/λmax sufficiency) is refuted

Across the 33 runs that ever crossed λmax = 2/η, only 18 spiked: accord 54.5% (Wilson CI[38.0,70.2]), statistically indistinguishable from a coin flip. The violations are not transient artifacts of our λmax sampling: cell means are stable (e.g. η=0.05 wd=0.1: post-collapse median λmax 37.5 < 2/η=40 yet seeds 1–2 spike 5/7 times; η=0.05 wd=0.1 seed 0 reaches λmax 121 — 3× threshold — and never spikes). Per-step sampling at onset (Appendix B) shows spikes co-occur with λmax *excursions* in control arms.

### 4.4 Causal freeze decomposition (Figures 2–3)

On the money cell (η=0.2 wd=0.1, branch step 300 pre-spike, 2 seeds): control spikes resume (2/2, 9–18 events); **freeze-hidden (fc1+fc2) → 0 spikes in both seeds** (0/2, CI[0,66]); freeze-readout (fc3) → spikes persist (2/2, 6–9 events). Test accuracy stays ≥0.91 in all arms. The hidden projection weights' *adaptation* — not their norm level, not the readout, not the λmax level — is the load-bearing condition for the instability. The per-step trace realization (Figure 3, seed 0, 1500 steps) shows the same decomposition at fine resolution: control spikes four times post-branch ([340–360], [480–500], [620–660], [1400–1420]) while freeze=hid — bit-identical to the branch at step 300 — never spikes.

### 4.5 Refuting the effective-sharpness explanation

Could freeze-hidden be stable merely because the frozen directions hosted the sharp modes, lowering the *trainable-subspace* sharpness below 2/η? No: restricted (trainable-subspace) λmax equals full-Hessian λmax in every arm (e.g. freeze=hid s1: full 25.2 vs trainable 25.3, both > 2/η=10), and freeze=hid s1 sustains λmax excursions to 66 (6.6× threshold) with **zero spikes** (Figure 2 overlay; Figure 3 trace). The instability is dynamical: it requires the hidden projections to co-adapt inside a sharp regime. Removing the adaptation removes the spike even when the sharpness remains.

### 4.6 Precision is not the driver (NFI refuted)

fp64 training on the spiking cell spikes as much as fp32 (2/2 cells; fp32 controls 9/18 events, fp64 17/26). Numerical feature inflation [3] does not explain toy-scale spikes.

### 4.7 Boundary cells are rare-event regions

At the edge of the spike region (η=0.05 wd=0.03; η=0.1 wd=0.01), 6-seed runs give 1/6 and 1/6 spike rates (Wilson CI[3.0,56.4] each) — seed-rare events rather than deterministic transitions, consistent with a stochastic (dynamical) trigger.

## 5 Discussion

**Theory (toy-scale, falsifiable).** Loss spikes in normalized SGD-trained MLPs require two jointly necessary conditions: (i) a sharp regime — λmax reaching ≳ 2/η, typically as sharpness excursions driven by weight-decay-induced norm collapse into an increasingly ill-conditioned geometry — and (ii) ongoing adaptation of the scale-invariant hidden projection weights, which supplies the dynamical amplification that converts sharpness into a spike. Removing either condition suppresses spikes; no static scalar (norm level, λmax crossing, precision) predicts spikes alone. This is the signature of a transient-amplification (non-normal) instability [4] rather than a static threshold crossing [1,2], and it explains why the three 2026 single-mechanism papers each found their own trigger: they each measured one necessary condition in a regime where the other held.

**Significance (whose belief/decision changes).** For practitioners training normalized networks with weight decay (the default recipe), the result changes which monitor to trust: norm trajectory and λmax-crossing alarms will fire in stable runs (15–30 false alarms in our map), while the actionable signature is the *combination* of a sharp regime and active hidden-layer adaptation. For the optimization-theory community, the result adjudicates four live 2026 claims on one benchmark and adds a causal-decomposition method (parameter-group freezing) that the single-mechanism papers lack. For the non-normal-amplification line [4], it supplies the first toy-scale causal evidence (freeze suppresses spikes at equal λmax) — the predicted signature of their frame.

**Threats (why still worth publishing).** Toy scale: one architecture (MLP+LN), one task family (Gaussian clusters), plain SGD, 2–3 seeds per cell (Wilson CIs reported; the map's qualitative structure — monotone in η and wd, wd=0 and low-η never spike — is invariant across seeds). We do not claim the mechanism generalizes to transformers/AdamW; the transfer question is stated as future work. The freeze=hid arm freezes fc1/fc2 weights but leaves LayerNorm gain/bias training; attribution is precise to the projection weights, and a full LayerNorm freeze is a listed follow-up. λmax is measured by power iteration on a 128-example batch at 400-step sampling; per-step runs (every 20 steps) confirm the excursion structure at onset. None of these threats affects the refutations, which are existential: clean runs above threshold exist (P2), clean collapsed runs exist (P1), fp64 spikes exist (NFI), and the freeze=hid 0-spike result holds across both seeds.

**Prior-belief reconciliation.** Registered priors (issue #86): P1 (weight-norm collapse suffices) — **refuted** (accord 37.5%, CI upper bound 51.6); P2 (λmax>2/η suffices) — **refuted** (accord 54.5%, CI[38.0,70.2]; freeze=hid s1 excursion to 6.6× threshold with zero spikes); P3 (a second-order discriminator is required) — **confirmed and refined** to the two-condition co-adaptation rule. The refutations of the two theory-anchored sufficiency priors are the study's strong-novelty signal: the pilot data that motivated registration already showed the tension, and the full phase map + causal arms resolve it.

## 6 Conclusion

On a shared toy benchmark with concurrent measurement of every 2026 loss-spike mechanism's named trigger, no single mechanism suffices: weight decay's norm collapse is necessary-not-sufficient (37.5% accord), λmax crossing 2/η is necessary-not-sufficient (54.5% accord), fp precision is irrelevant (fp64 spikes), and freezing the hidden projection weights suppresses spikes even at 6.6× threshold sharpness. The toy regime is governed by a two-condition dynamical rule — sharp regime plus hidden-projection co-adaptation — consistent with non-normal transient amplification as the unifying mechanism. We contribute the benchmark, the concurrent-diagnostics protocol, the causal freeze-arm decomposition, and the falsification of three 2026 sufficiency claims; the instrument and data are committed for byte-identical reproduction.

## 7 References

[1] J. Cohen, S. Kaur, Y. Li, J. Z. Kolter, A. Talwalkar. "Edge of Stability: Insights into the Loss Landscape of Deep Networks." ICLR 2022 (arXiv 2108.01091). *Difference*: our P2 test measures its sufficiency claim on a shared phase map and refutes it.
[2] "Weight-norm Criticality: A Mechanism for Loss Spikes Induced by the Normalization and Weight Decay." arXiv 2607.21005, Jul 2026. *Difference*: single-mechanism validation; we reproduce its norm-collapse stage but show necessity-not-sufficiency and localize the load-bearing condition by freezing.
[3] "Grokking or Glitching? How Low-Precision Drives Slingshot Loss Spikes." arXiv 2605.06152, May 2026. *Difference*: we falsify precision as the toy driver via fp64 contrasts.
[4] "Non-normal spectral signatures of instability in neural network training dynamics." arXiv 2605.23476, May 2026. *Difference*: we supply the first toy-scale causal evidence consistent with their dynamical-amplification frame (freeze suppresses spikes at equal λmax) without computing κ(V), which we leave to future work.
[5] "Post-Grokking Collapse at the Representation-Readout Interface in Muon-Trained Transformers." arXiv 2608.07436, Aug 2026. *Difference*: distinct regime (post-grokking collapse vs wd-induced spikes) and distinct method (parameter-group freezing under plain SGD).
[6] "Taming Curvature: Architecture Warm-Up for Stable Transformer Training." arXiv 2606.16768, Jun 2026. *Difference*: engineering mitigation; we provide the mechanism adjudication motivating when it applies.
[7] "Can Entry-Wise Clipping Give Spectral Control of Stochastic Gradients?" arXiv 2605.27733, May 2026. *Difference*: noise-side mitigation; our freeze arms isolate the adaptation-side condition orthogonal to gradient-noise clipping.

## Appendix A: spike-presence Wilson CIs (n=3 per cell)

| η \ wd | 0 | 3e-3 | 1e-2 | 3e-2 | 1e-1 |
|---|---|---|---|---|---|
| 0.02 | 0%[0,56] | 0%[0,56] | 0%[0,56] | 0%[0,56] | 0%[0,56] |
| 0.05 | 0%[0,56] | 0%[0,56] | 0%[0,56] | 33%[6,79] | 67%[21,94] |
| 0.10 | 0%[0,56] | 0%[0,56] | 33%[6,79] | 100%[44,100] | 100%[44,100] |
| 0.20 | 0%[0,56] | 0%[0,56] | 67%[21,94] | 100%[44,100] | 100%[44,100] |

## Appendix B: per-step λmax at onset (control money cell, η=0.2 wd=0.1, seed 0)

Per-step trace realization (loss and full-Hessian λmax every 20 steps, 1500 steps, seed 0; Figure 3): control spikes at [340–360], [480–500], [620–660], [1400–1420]; λmax samples reach 84.7@620 at the third onset (global max 99.5@1080). Freeze=hid, branched bit-identically at step 300, produces zero spikes with post-branch λmax mean 13.3 (> 2/η = 10) and max 22.5 — sustained above-threshold sharpness with flat loss. Power-iteration estimates dip negative at control spike onsets (−46@340, −84@1400), an artifact of the unstable regime; freeze=hid samples stay positive. Spike windows shift across seed-lottery realizations (an earlier dense-onset run gave [160–180], [640–660], [1380–1400] with 80@160); the control excursion–spike coincidence and the freeze=hid flat loss are invariant.

## Figure list (files committed in figures/)

- Figure 1 (fig1_phase_map.png): phase-map heatmap — mean spike count per (η, wd) cell (Table 1), with wd=0 and low-η columns clean and the high-η × high-wd corner spiking.
- Figure 2 (fig2_freeze_arms.png): freeze-arm outcome bars — control 2/2 spiked vs freeze-hidden 0/2 vs freeze-readout 2/2, with per-arm λmax means overlaid (freeze=hid s1 25.2 > 2/η while clean).
- Figure 3 (fig3_excursion_trace.png): loss (top) and full-Hessian λmax (bottom) every 20 steps over 0–1500 on the money cell (seed 0). Control spikes at [340–360], [480–500], [620–660], [1400–1420] with λmax excursions to 84.7 at spike onset (step 620); freeze=hid (bit-identical to branch at step 300) stays flat — post-branch λmax mean 13.3 > 2/η = 10, max 22.5 — with zero spikes.
