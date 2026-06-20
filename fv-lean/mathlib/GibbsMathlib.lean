/-
Sutra -> thrml, FV-in-Lean: the MID-SIZE mathlib step (Emma 2026-06-14).

The core-only floor (`fv-lean/GibbsChain.lean`) proved the single-gadget Glauber
chain is irreducible + aperiodic + Gibbs-mode-correct WITHOUT mathlib. Emma's
blocker-sweep call was to go to a *mid-size* mathlib step -- **detailed balance +
finite-chain stationary uniqueness** (Perron-Frobenius on the gadget), short of the
full t->infinity TV-mixing theorem. That needs the real-valued transition
probabilities + `exp`, hence mathlib. This file delivers it:

  1. `stationary_of_detailedBalance` -- GENERAL: for any finite row-stochastic
     kernel, detailed balance (reversibility) w.r.t. pi implies pi is stationary.
  2. The clamped AND-decode **Gibbs kernel** with REAL Boltzmann weights
     `exp(-beta * E)`: `gibbsKernel_rowSum` + `gibbsKernel_detailedBalance` ->
     (via 1) `gibbsKernel_stationary`. The Gibbs measure is stationary for the
     gadget's own sampling kernel, proven over the reals.
  3. `stationary_unique_two_state` -- finite-chain stationary UNIQUENESS for the
     2-state positive chain: any two normalized stationary measures coincide
     (the elementary Perron-Frobenius case the clamped decode lives in).

Together with the core-only irreducibility/aperiodicity, this is the reversible-
chain convergence picture: a positive, irreducible, reversible finite chain has a
unique stationary distribution = the Gibbs measure.

UPDATE 2026-06-19 (Emma): the mixing RATE is now mechanised too (§4-5 below) -- the
t->infinity spectral gap. For the 2-state clamped-decode chain the second eigenvalue
`lambda2 = 1 - P f->t - P t->f` is the per-step contraction factor, so TV distance
decays as `|lambda2|^n` (`two_state_tv_mixing`). Instantiated for the gadget's own
full-resampling Gibbs kernel, `lambda2 = 0` exactly, so it mixes in ONE step
(`gibbs_mixes_in_one_step`). The convergence picture is now complete: hypotheses +
stationary-limit object + RATE, all machine-checked.
-/
import Mathlib

open Finset

namespace GibbsMathlib

/-! ## 1. General: reversibility (detailed balance) implies stationarity. -/

/-- Detailed balance of a measure `π` w.r.t. a kernel `P`: `π s · P s t = π t · P t s`. -/
def DetailedBalance {S : Type*} (π : S → ℝ) (P : S → S → ℝ) : Prop :=
  ∀ s t, π s * P s t = π t * P t s

/-- For a finite, row-stochastic kernel `P` (`∑ t, P s t = 1`), detailed balance of
    `π` implies `π` is stationary: `∑ s, π s · P s t = π t`. This is the reversible-
    chain half of "the Gibbs measure is the stationary distribution". -/
theorem stationary_of_detailedBalance
    {S : Type*} [Fintype S] (π : S → ℝ) (P : S → S → ℝ)
    (hrow : ∀ s, ∑ t, P s t = 1)
    (hdb : DetailedBalance π P) :
    ∀ t, ∑ s, π s * P s t = π t := by
  intro t
  calc ∑ s, π s * P s t
      = ∑ s, π t * P t s := Finset.sum_congr rfl (fun s _ => hdb s t)
    _ = π t * ∑ s, P t s := by rw [Finset.mul_sum]
    _ = π t * 1 := by rw [hrow t]
    _ = π t := by ring

/-! ## 2. The clamped AND-decode Gibbs kernel over the reals.

The AND gadget with inputs `a,b` clamped and the output spin `z` sampled. State
space is `Bool` (z = false/true). Energy ×4 to integers (matching AndGadget.lean),
cast to ℝ; the Boltzmann weight is `exp(-β · E)`. The single-site Gibbs update fully
resamples z from its conditional, so `P z z' = w z' / (w false + w true)`. -/

/-- Spin value of a bool: `true ↦ +1`, `false ↦ -1`. -/
def sp (b : Bool) : ℝ := if b then 1 else -1

/-- AND-gadget energy ×4 (reals), inputs `a b` clamped, output spin `z`. -/
def E4 (a b z : Bool) : ℝ :=
  -sp a - sp b + 2 * sp z + sp a * sp b - 2 * sp a * sp z - 2 * sp b * sp z

/-- Unnormalized Gibbs (Boltzmann) weight of state `z` at inverse temperature `β`. -/
noncomputable def w (β : ℝ) (a b z : Bool) : ℝ := Real.exp (-β * E4 a b z)

/-- Boltzmann weights are strictly positive. -/
lemma w_pos (β : ℝ) (a b z : Bool) : 0 < w β a b z := Real.exp_pos _

/-- Local partition function: the sum of the two weights over the sampled spin. -/
noncomputable def Z (β : ℝ) (a b : Bool) : ℝ := w β a b false + w β a b true

lemma Z_pos (β : ℝ) (a b : Bool) : 0 < Z β a b :=
  add_pos (w_pos β a b false) (w_pos β a b true)

/-- The single-site Gibbs kernel: resample z from its Boltzmann conditional. The
    next state's probability is its weight over the local partition (independent of
    the current z — a single spin is fully resampled). -/
noncomputable def gibbsKernel (β : ℝ) (a b : Bool) (_z z' : Bool) : ℝ :=
  w β a b z' / Z β a b

/-- The Gibbs kernel is row-stochastic: `∑ z', P z z' = 1`. -/
theorem gibbsKernel_rowSum (β : ℝ) (a b : Bool) :
    ∀ z, ∑ z', gibbsKernel β a b z z' = 1 := by
  intro z
  -- Sum over Bool, then both terms share the denominator Z; (wT+wF)/Z = 1 since
  -- Z = wF+wT. Provide Z ≠ 0 for the actual denominator (do not unfold Z under it).
  rw [Fintype.sum_bool]
  unfold gibbsKernel
  rw [← add_div, div_eq_iff (ne_of_gt (Z_pos β a b))]
  unfold Z; ring

/-- The Gibbs measure satisfies detailed balance w.r.t. the Gibbs kernel. Both sides
    equal `w z · w z' / Z`, since the kernel's denominator (the local partition) does
    not depend on the current state. -/
theorem gibbsKernel_detailedBalance (β : ℝ) (a b : Bool) :
    DetailedBalance (w β a b) (gibbsKernel β a b) := by
  intro z z'
  -- π z · (w z' / Z) = π z' · (w z / Z): both = w z · w z' / Z. `ring` clears /Z
  -- (a field operation) and commutes the numerators.
  unfold gibbsKernel
  ring

/-- Hence the Gibbs measure is STATIONARY for the gadget's own sampling kernel. -/
theorem gibbsKernel_stationary (β : ℝ) (a b : Bool) :
    ∀ t, ∑ z, w β a b z * gibbsKernel β a b z t = w β a b t :=
  stationary_of_detailedBalance (w β a b) (gibbsKernel β a b)
    (gibbsKernel_rowSum β a b) (gibbsKernel_detailedBalance β a b)

/-! ## 3. Finite-chain stationary UNIQUENESS (the 2-state Perron-Frobenius case).

The clamped decode is a 2-state chain. For a 2-state chain whose stationary
equation holds, any two stationary measures with the SAME total mass coincide --
the elementary uniqueness the gadget chain inhabits. -/

/-- Two stationary distributions of a 2-state chain with equal total mass are equal,
    provided the chain genuinely moves mass `false → true` (`0 < P false true`) and
    has a non-negative reverse rate (`0 ≤ P true false`). This is the finite,
    positive, irreducible Perron-Frobenius stationary uniqueness specialised to
    |S| = 2 — the case the clamped-decode gadget chain inhabits. -/
theorem stationary_unique_two_state
    (P : Bool → Bool → ℝ)
    (hrow : ∀ s, ∑ t, P s t = 1)
    (hPft : 0 < P false true) (hPtf : 0 ≤ P true false)
    (π ρ : Bool → ℝ)
    (hπ : ∀ t, ∑ s, π s * P s t = π t)
    (hρ : ∀ t, ∑ s, ρ s * P s t = ρ t)
    (hmass : π false + π true = ρ false + ρ true) :
    π = ρ := by
  -- Row sum at `true` and stationarity at `true`, expanded over Bool (term order
  -- is whatever `Fintype.sum_bool` gives — we never assume it; `linear_combination`
  -- and `linarith` are ring/order-agnostic).
  have hPt := hrow true;  rw [Fintype.sum_bool] at hPt
  have hπt := hπ true;    rw [Fintype.sum_bool] at hπt
  have hρt := hρ true;    rw [Fintype.sum_bool] at hρt
  have hPtt : P true true = 1 - P true false := by linarith
  -- Stationarity ⟹ the cross-balance `π false · P f→t = π true · P t→f`.
  have e1 : π false * P false true = π true * P true false := by
    rw [hPtt] at hπt; linear_combination hπt
  have e2 : ρ false * P false true = ρ true * P true false := by
    rw [hPtt] at hρt; linear_combination hρt
  -- Solve each `false` weight in terms of its `true` weight (P f→t > 0).
  have pf : π false = π true * P true false / P false true := by
    rw [eq_div_iff (ne_of_gt hPft)]; linear_combination e1
  have rf : ρ false = ρ true * P true false / P false true := by
    rw [eq_div_iff (ne_of_gt hPft)]; linear_combination e2
  rw [pf, rf] at hmass
  -- Equal mass ⟹ (π true − ρ true)·(P t→f / P f→t + 1) = 0, and the factor is > 0.
  have hc : 0 < P true false / P false true + 1 := by positivity
  have htrue : π true = ρ true := by
    have key : (π true - ρ true) * (P true false / P false true + 1) = 0 := by
      linear_combination hmass
    rcases mul_eq_zero.mp key with h | h
    · exact sub_eq_zero.mp h
    · exact absurd h (ne_of_gt hc)
  have hfalse : π false = ρ false := by rw [pf, rf, htrue]
  funext b; cases b
  · exact hfalse
  · exact htrue

/-! ## 4. Mixing RATE: the 2-state spectral gap (Emma 2026-06-19).

The piece named-but-not-yet-mechanised in `planning/sutra-spec/formal-verification.md`:
the t→∞ mixing RATE (how *fast* the chain reaches the now-proven unique stationary
measure). The clamped-decode chain is 2-state; its transition matrix has eigenvalues
`1` and `λ₂ = 1 − P f→t − P t→f`, and that second eigenvalue IS the contraction factor.
For any mass-1 distribution `μ` and the mass-1 stationary `π`, the deviation from `π`
scales by exactly `λ₂` each step, so after `n` steps it is `λ₂^n` times the initial
deviation, and the total-variation distance (which for 2 states equals `|deviation|`)
decays as `|λ₂|^n`. This is the explicit spectral-gap / mixing-rate statement — proven
with the same `linear_combination`/`linarith` machinery as `stationary_unique_two_state`,
no heavy spectral theory. -/

/-- One application of the chain to a distribution (the left action `μ ↦ μ P`). -/
def stepP (P : Bool → Bool → ℝ) (μ : Bool → ℝ) : Bool → ℝ :=
  fun t => ∑ s, μ s * P s t

/-- The second eigenvalue / spectral contraction factor of a 2-state chain. -/
def lambda2 (P : Bool → Bool → ℝ) : ℝ := 1 - P false true - P true false

/-- The chain preserves total mass (`∑ = const`) for a row-stochastic `P`. -/
lemma stepP_mass (P : Bool → Bool → ℝ) (hrow : ∀ s, ∑ t, P s t = 1) (μ : Bool → ℝ) :
    stepP P μ false + stepP P μ true = μ false + μ true := by
  simp only [stepP, Fintype.sum_bool]
  have hf := hrow false; rw [Fintype.sum_bool] at hf
  have ht := hrow true;  rw [Fintype.sum_bool] at ht
  linear_combination (μ false) * hf + (μ true) * ht

/-- Iterating the mass-1-preserving chain keeps total mass at 1. -/
lemma stepP_iterate_mass (P : Bool → Bool → ℝ) (hrow : ∀ s, ∑ t, P s t = 1)
    (μ : Bool → ℝ) (hμ : μ false + μ true = 1) (n : ℕ) :
    ((stepP P)^[n] μ) false + ((stepP P)^[n] μ) true = 1 := by
  induction n with
  | zero => simpa using hμ
  | succ k ih => rw [Function.iterate_succ_apply', stepP_mass P hrow]; exact ih

/-- ONE-STEP CONTRACTION (the spectral-gap multiplier). For a row-stochastic 2-state
    `P`, the mass-1 stationary `π`, and any mass-1 `μ`, the deviation from `π` at `true`
    is multiplied by exactly the second eigenvalue `λ₂ = 1 − P f→t − P t→f`. -/
theorem two_state_step_contraction
    (P : Bool → Bool → ℝ)
    (hrow : ∀ s, ∑ t, P s t = 1)
    (π : Bool → ℝ)
    (hπ : ∀ t, ∑ s, π s * P s t = π t)
    (hπmass : π false + π true = 1)
    (μ : Bool → ℝ)
    (hμmass : μ false + μ true = 1) :
    stepP P μ true - π true = lambda2 P * (μ true - π true) := by
  -- Subtract the stationary fixed point, then expand over Bool.
  have hstat : stepP P π true = π true := hπ true
  have hexp : stepP P μ true - π true
      = (μ false - π false) * P false true + (μ true - π true) * P true true := by
    have key : stepP P μ true - stepP P π true
        = (μ false - π false) * P false true + (μ true - π true) * P true true := by
      simp only [stepP, Fintype.sum_bool]; ring
    rw [hstat] at key; exact key
  -- masses: μ f − π f = −(μ t − π t); row sum: P t t = 1 − P t f.
  have hmd : μ false - π false = -(μ true - π true) := by linarith
  have hPt := hrow true; rw [Fintype.sum_bool] at hPt
  have hPtt : P true true = 1 - P true false := by linarith
  rw [hexp, hmd, hPtt, lambda2]; ring

/-- GEOMETRIC DECAY. Iterating the chain `n` times multiplies the deviation from the
    stationary `π` at `true` by exactly `λ₂^n`. -/
theorem two_state_geometric_mixing
    (P : Bool → Bool → ℝ)
    (hrow : ∀ s, ∑ t, P s t = 1)
    (π : Bool → ℝ)
    (hπ : ∀ t, ∑ s, π s * P s t = π t)
    (hπmass : π false + π true = 1)
    (μ : Bool → ℝ)
    (hμmass : μ false + μ true = 1)
    (n : ℕ) :
    ((stepP P)^[n] μ) true - π true = (lambda2 P) ^ n * (μ true - π true) := by
  induction n with
  | zero => simp
  | succ k ih =>
    rw [Function.iterate_succ_apply',
        two_state_step_contraction P hrow π hπ hπmass _
          (stepP_iterate_mass P hrow μ hμmass k),
        ih, pow_succ]
    ring

/-- Total-variation distance on `Bool`. -/
noncomputable def tvDist (μ ν : Bool → ℝ) : ℝ :=
  (|μ false - ν false| + |μ true - ν true|) / 2

/-- For two mass-1 distributions on `Bool`, TV distance = `|deviation at true|`. -/
lemma tvDist_two_state (μ ν : Bool → ℝ)
    (hμ : μ false + μ true = 1) (hν : ν false + ν true = 1) :
    tvDist μ ν = |μ true - ν true| := by
  unfold tvDist
  have h : μ false - ν false = -(μ true - ν true) := by linarith
  rw [h, abs_neg]; ring

/-- MIXING RATE (TV form). The total-variation distance to the stationary `π` decays
    geometrically with rate `|λ₂| = |1 − P f→t − P t→f|` — the explicit spectral gap.
    `tvDist (μ Pⁿ) π = |λ₂|^n · tvDist μ π`. -/
theorem two_state_tv_mixing
    (P : Bool → Bool → ℝ)
    (hrow : ∀ s, ∑ t, P s t = 1)
    (π : Bool → ℝ)
    (hπ : ∀ t, ∑ s, π s * P s t = π t)
    (hπmass : π false + π true = 1)
    (μ : Bool → ℝ)
    (hμmass : μ false + μ true = 1)
    (n : ℕ) :
    tvDist ((stepP P)^[n] μ) π = |lambda2 P| ^ n * tvDist μ π := by
  rw [tvDist_two_state _ _ (stepP_iterate_mass P hrow μ hμmass n) hπmass,
      tvDist_two_state _ _ hμmass hπmass,
      two_state_geometric_mixing P hrow π hπ hπmass μ hμmass n,
      abs_mul, abs_pow]

/-! ## 5. The gadget Gibbs kernel: explicit rate (mixes in ONE step).

Instantiate the 2-state spectral gap for the gadget's OWN single-site Gibbs sampler.
The kernel fully resamples `z` (`gibbsKernel z z' = w z' / Z`, independent of the
current `z`), so its second eigenvalue is exactly 0: `λ₂ = 1 − w_true/Z − w_false/Z
= 1 − Z/Z = 0`. The spectral gap is therefore maximal (`1 − |λ₂| = 1`) and the chain
reaches the (normalized) Gibbs measure in a SINGLE step — TV distance 0 for all
`n ≥ 1`. This is the mixing-rate statement made fully concrete for the gadget. -/

/-- The normalized Gibbs measure (total mass 1) — the stationary distribution. -/
noncomputable def gibbsPi (β : ℝ) (a b : Bool) (z : Bool) : ℝ := w β a b z / Z β a b

/-- The normalized Gibbs measure has total mass 1. -/
lemma gibbsPi_mass (β : ℝ) (a b : Bool) :
    gibbsPi β a b false + gibbsPi β a b true = 1 := by
  have hZ : Z β a b ≠ 0 := ne_of_gt (Z_pos β a b)
  unfold gibbsPi
  field_simp
  unfold Z; ring

/-- The normalized Gibbs measure is stationary (scale `gibbsKernel_stationary` by 1/Z). -/
lemma gibbsPi_stationary (β : ℝ) (a b : Bool) :
    ∀ t, ∑ z, gibbsPi β a b z * gibbsKernel β a b z t = gibbsPi β a b t := by
  intro t
  have h := gibbsKernel_stationary β a b t
  unfold gibbsPi
  rw [← h, Finset.sum_div]
  exact Finset.sum_congr rfl (fun z _ => by ring)

/-- The gadget's single-site Gibbs kernel FULLY RESAMPLES (next-state probability is
    independent of the current state), so its second eigenvalue is exactly 0. -/
theorem gibbs_lambda2_zero (β : ℝ) (a b : Bool) :
    lambda2 (gibbsKernel β a b) = 0 := by
  have hZ : Z β a b ≠ 0 := ne_of_gt (Z_pos β a b)
  simp only [lambda2, gibbsKernel]
  field_simp
  unfold Z; ring

/-- MIXING RATE for the gadget: the Gibbs chain reaches its stationary measure in ONE
    step. For any mass-1 start `μ` and any `n ≥ 1`, the TV distance to the normalized
    Gibbs measure is exactly 0 (`λ₂ = 0` ⇒ spectral gap 1). -/
theorem gibbs_mixes_in_one_step (β : ℝ) (a b : Bool)
    (μ : Bool → ℝ) (hμmass : μ false + μ true = 1) (n : ℕ) (hn : 1 ≤ n) :
    tvDist ((stepP (gibbsKernel β a b))^[n] μ) (gibbsPi β a b) = 0 := by
  rw [two_state_tv_mixing (gibbsKernel β a b) (gibbsKernel_rowSum β a b)
        (gibbsPi β a b) (gibbsPi_stationary β a b) (gibbsPi_mass β a b) μ hμmass n,
      gibbs_lambda2_zero, abs_zero, zero_pow (by omega : n ≠ 0), zero_mul]

-- Axiom audit: the mid-size results rest only on the standard mathlib classical
-- foundations (no `sorry`). `#print axioms` is verified at build time.
#print axioms stationary_of_detailedBalance
#print axioms gibbsKernel_detailedBalance
#print axioms gibbsKernel_stationary
#print axioms stationary_unique_two_state
#print axioms two_state_step_contraction
#print axioms two_state_geometric_mixing
#print axioms two_state_tv_mixing
#print axioms gibbs_lambda2_zero
#print axioms gibbs_mixes_in_one_step

end GibbsMathlib
