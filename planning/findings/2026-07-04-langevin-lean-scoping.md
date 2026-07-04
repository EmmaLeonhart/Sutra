# Continuous-space Langevin in Lean — scoping verdict: OUT OF LIBRARY REACH (negative result)

**Date:** 2026-07-04. **Author:** queue session (leg (c) scoping pass, per queue.md).
**Question scoped:** lean-gap-audit item 3 — machine-check the continuous-space overdamped
Langevin diffusion `dX = −∇U dt + √(2/β) dW` on a relaxed energy (existence of the dynamics,
stationarity of the Gibbs measure, exponential decay to it). Emma green-lit both heavy legs
2026-07-03; the audit's own note on item 3 was *"confirm it is in scope before starting."*
This is that confirmation, and **it fails**.

## What the ecosystem actually has (checked 2026-07-04)

- **mathlib (recent, ~v4.30 era):** Gaussian measures, Kolmogorov extension, the
  Kolmogorov–Chentsov continuity theorem, and the construction of **Brownian motion / the
  Wiener measure** (Degenne–Ledvinka–Marion–Pfaffelhuber line of work, arXiv:2511.20118,
  Nov 2025). Martingale convergence and Markov kernels (arXiv:2510.04070) exist. **No Itô
  integral, no stochastic calculus, no SDEs in mathlib proper.**
- **State of the art outside mathlib:** "A Machine-Checked Itô Calculus for Brownian Motion"
  (Coelho, arXiv:2606.15089, June 2026; repo `raphaelrrcoelho/formal-mathfin`, ~7,900 lines
  over 26 modules, builds on mathlib + the BrownianMotion package). It reaches: the Itô
  integral as an L² isometry, Itô's formula for **C³ functions with bounded derivatives**,
  L²-quadratic variation, and a continuous-modification local-martingale result. Its own
  explicit non-goals: **SDE existence/uniqueness**, general semimartingale integrators,
  unrestricted C² Itô. Fokker–Planck and Langevin dynamics are not formalized there — or,
  as far as this scoping pass could find, **in any proof assistant**.

## Why the leg is blocked, concretely

The Langevin statement we would need has three layers, every one currently missing in Lean:

1. **The dynamics exist:** strong (or weak) solutions of `dX = −∇U dt + √(2/β) dW` — SDE
   existence/uniqueness under Lipschitz/dissipativity hypotheses. Not formalized anywhere;
   the only machine-checked Itô formula is C³-bounded, which already excludes the standard
   proof pipeline for typical `U`.
2. **The Gibbs measure is stationary:** needs the generator `L = −∇U·∇ + (1/β)Δ` and
   integration-by-parts against `π ∝ e^{−βU}` on ℝⁿ — diffusion semigroup/generator theory,
   not formalized.
3. **Exponential decay:** a continuous-space Poincaré or log-Sobolev inequality for
   `e^{−βU}dx` (e.g. via Bakry–Émery `∇²U ⪰ λI`) — not formalized.

Building these from scratch is the scale of the whole `formal-mathfin` effort several times
over — multiple person-months to person-years of Lean work, not a queue leg. Per the audit's
own gate ("confirm in scope before starting") the honest disposition is: **name it, do not
claim it, do not start it.** The FV paper already carries exactly this framing (§7 "named not
claimed") — no paper change is needed for this verdict.

## The tractable adjacent target (audit item 2, NOT item 3)

What *is* in reach with the existing `Sutra.Convergence` assets is the **continuous-TIME,
finite-state** decay — lean-gap-audit item 2, which the audit already ordered before Langevin:
for a trajectory obeying the master ODE `df/dt = Q f` (the finite jump process the measured
γ = 0.0397 actually lives on), the deviation-energy obeys
`d/dt ‖f_t‖²_π = 2⟨Q f_t, f_t⟩_π ≤ −2γ‖f_t‖²_π`, and Grönwall gives
`‖f_t‖²_π ≤ e^{−2γt}‖f_0‖²_π`. Everything is finite-dimensional; mathlib has the Grönwall
lemma and derivative calculus; the Dirichlet/Poincaré data is the same `gen_poincare`-style
per-edge input the discrete-time engine already consumes (a generator satisfies
`⟨Qf,f⟩_π = −E_Q(f)` by the same algebra as `dirichlet_eq`). Cost estimate: one focused
session, iterating through `fv-lean-mathlib-ci` (this container cannot build locally —
egress policy; note a shallow `git clone --branch v4.30.0` of mathlib4 IS possible here for
lemma-name grepping, only building is blocked).

## Disposition — UPDATED after Emma's answer (2026-07-04)

Emma's response to the AskUserQuestion: *"I mean are we not using THRML for the formal
verification lol?"* — i.e. the verification target is the **thrml compile target's actual
sampler**, not textbook SDE theory. Checked against `codegen_thrml.py`: the thrml backend
executes **discrete-state block-Gibbs sampling** over spin registers (`SpinNode`,
`BlockGibbsSpec`, `SpinGibbsConditional` — single-site heat-bath blocks on a schedule). Its
continuous-time law is the finite-state **jump process** (`dp/dt = Qᵀp`, exactly what
`fv_sampler_convergence.py` measures) — NOT a continuous-space diffusion. So:

- Leg (c) as stated (continuous-space SDE) is **out of scope for the substrate**, on top of
  being out of proof-assistant reach — the diffusion was the audit's "further limit," not the
  thrml object. Dropped from the agenda (paper §7 updated to say scoped-out, not open).
- The thrml-relevant continuous-time statement IS audit item 2: the master-ODE /
  jump-process decay `‖f_t‖²_π ≤ e^{−2γt}‖f_0‖²_π` above. **Proceeding with it** as the
  next Lean leg (this session), framed explicitly as the thrml chain's continuous-time law.
- The most thrml-faithful *discrete-time* object (single-site block-Gibbs kernel — zeros
  between non-neighbours) still needs canonical paths for its own gap; unchanged, named in
  the queue as not-green-lit.
- Revisit the SDE leg only if the substrate ever becomes a continuous-space analog device
  AND mathlib lands Itô/SDEs.

Sources: [arXiv:2606.15089](https://arxiv.org/abs/2606.15089) (machine-checked Itô calculus,
scope + non-goals), [arXiv:2511.20118](https://arxiv.org/abs/2511.20118) (Brownian motion in
Lean/mathlib), [arXiv:2510.04070](https://arxiv.org/abs/2510.04070) (Markov kernels in mathlib).
