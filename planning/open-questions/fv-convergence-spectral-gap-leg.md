# Open Lean goal: self-adjoint + scalar Dirichlet gap ⇒ one-step L²(π) contraction

**Status:** open (2026-06-30). The one precise remaining lemma of the `Sutra.Convergence`
spine. Everything around it is machine-checked; this is the irreducible spectral step.

## What is already proven (CI-green, `fv-lean/mathlib/`)

- `GibbsMultiState.applyP_selfAdjoint` — reversibility ⇒ `⟨Pf,g⟩_π = ⟨f,Pg⟩_π`.
- `GibbsMultiState.applyP_stationary` — `∑_s π_s P_{st} = π_t`.
- `Convergence.applyP_preserves_piMean` — `Eπ[Pf] = Eπ[f]`, so the mean-zero subspace
  `{f | piMean π f = 0}` is `P`-invariant.
- `Convergence.normPiSq_applyP_selfAdjoint` — `‖Pf‖²_π = ⟨f, P²f⟩_π` (the bridge).
- `Convergence.geometric_convergence` — **takes** a one-step contraction `hgap` and
  concludes `‖Pⁿf‖²_π ≤ rⁿ‖f‖²_π`. The leg below is what *produces* `hgap`.
- `Convergence.loop_norm_preserved` — the `r = 1` (orthogonal-loop) instance.

## The open goal (precise statement)

Let `S` be a `Fintype`, `π : S → ℝ` with `π > 0`, `P : S → S → ℝ` row-stochastic and
`DetailedBalance π P` (so `applyP P` is π-self-adjoint). Suppose a **scalar Dirichlet/
Rayleigh spectral gap** `γ ∈ (0,1]`: for every mean-zero `f` (`piMean π f = 0`),

    |⟨f, applyP P f⟩_π| ≤ (1 - γ) · ‖f‖²_π.        -- the gap as a Rayleigh bound

**Goal:** the one-step L²(π) contraction on the mean-zero subspace,

    ‖applyP P f‖²_π ≤ (1 - γ)² · ‖f‖²_π   for all f with piMean π f = 0.

Feed this (with `r = (1-γ)²`) into `geometric_convergence` to get a fully-closed
`gap ⇒ geometric decay` with the gap as a *scalar Rayleigh hypothesis* the measured
`γ = 0.0397` instantiates — promoting the M-tier multi-state gap toward L.

## Proof route (elementary, no finite-dim spectral theorem)

For self-adjoint `P` the **numerical radius equals the operator norm**. Elementary
derivation, all on the `P`-invariant mean-zero subspace (closed under `±` and under `P`):

1. Polarization for self-adjoint `P` (real):
   `4⟨Pf,g⟩_π = ⟨P(f+g),(f+g)⟩_π − ⟨P(f−g),(f−g)⟩_π`
   (expand using `applyP_selfAdjoint`; pure bilinear algebra).
2. Bound each quadratic form by the Rayleigh hypothesis `|⟨Ph,h⟩_π| ≤ (1−γ)‖h‖²_π`, then
   the parallelogram law `‖f+g‖²_π + ‖f−g‖²_π = 2‖f‖²_π + 2‖g‖²_π`, giving
   `⟨Pf,g⟩_π ≤ (1−γ)·(‖f‖²_π + ‖g‖²_π)/2`.
3. Set `g = applyP P f` (still mean-zero, by `applyP_preserves_piMean`). Then the LHS is
   `⟨Pf, Pf⟩_π = ‖Pf‖²_π`, and a Cauchy–Schwarz / AM–GM normalization on the RHS closes
   `‖Pf‖²_π ≤ (1−γ)²‖f‖²_π`. (Equivalently: `‖Pf‖²_π = ⟨f,P²f⟩_π` via the bridge, then the
   numerical-radius bound on `P²`.)

## Progress update (2026-06-30): all the tooling is now CI-verified

The whole inner-product toolkit the capstone needs is built and machine-checked in
`Convergence.lean` (mathlib CI green): `innerPi_add_left`, `innerPi_sub_left`,
`innerPi_smul_left`, `normPiSq_parallelogram`, `normPiSq_nonneg`, `normPiSq_sub_smul`,
`normPiSq_applyP_selfAdjoint` (the `‖Pf‖²_π = ⟨f,P²f⟩_π` bridge), and
**`innerPi_cauchy_schwarz`** (`⟨f,g⟩²_π ≤ ‖f‖²_π‖g‖²_π`, via the `discrim_le_zero`
argument). So the remaining gap is **only the final assembly** — the numerical-radius =
operator-norm step for the self-adjoint `applyP P`:

> from `|⟨Ph,h⟩_π| ≤ (1−γ)‖h‖²_π` on mean-zero `h` (the Rayleigh gap), conclude
> `‖Pf‖_π ≤ (1−γ)‖f‖_π` (hence the one-step contraction with `r=(1−γ)²`).

Route, all tools now in hand: polarization `4⟨Pf,g⟩_π = ⟨P(f+g),f+g⟩_π − ⟨P(f−g),f−g⟩_π`
(from `applyP_selfAdjoint` + the `innerPi_*_left` bilinearity), bound the two quadratic
forms by the Rayleigh gap, collapse `‖f+g‖²_π+‖f−g‖²_π` by `normPiSq_parallelogram`, then
normalize via `innerPi_cauchy_schwarz` (case-split on `‖Pf‖_π = 0`). `applyP_preserves_piMean`
keeps every vector in the mean-zero subspace where the Rayleigh gap applies.

## Why the capstone is not done yet

This needs a small inner-product-space scaffold (bilinearity of `innerPi`, the
parallelogram law, real polarization) built directly on `innerPi`, plus Cauchy–Schwarz.
Each step is elementary but the assembly is non-trivial, and the mathlib layer **cannot be
built locally** (Windows `MAX_PATH`), so it must be iterated through CI (~2.5 min/cycle) —
unsuitable for blind grinding. Flagged for a focused, non-blind session. Do **not** mark
the gap proven until `lean` accepts this lemma `sorry`-free in CI.
