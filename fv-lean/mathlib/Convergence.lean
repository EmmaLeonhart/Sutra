/-
Sutra → thrml, FV-in-Lean: the CONVERGENCE leg of the `Sutra.Convergence` chain.

THE SPINE (FV-LEAN-HANDOFF-2026-06-29.md §⭐⭐ "THE ACTUAL FRAME"). A Sutra program on
any substrate is the relaxation of one fixed operator toward a fixed point that is the
answer. Verification is one interdependent chain, not a grab-bag of lemmas:
  1. fixed-point correctness — the ground state IS the answer (gadgets + composition, L).
  2. convergence to it — the dynamics reach the fixed point (THIS file).
  3. substrate instances of the SAME theorem — loop (Z-transform), Gibbs (spectral gap),
     quantum (unitary).

`GibbsMultiState.lean` discharged the reversible-self-adjoint FOUNDATION
(`applyP_selfAdjoint`, `applyP_stationary`) for any finite state space. This file builds
the next leg DIRECTLY on it: detailed balance ⇒ the chain preserves the π-mean (so the
mean-zero "deviation from stationarity" subspace is invariant), and the spectral gap —
stated as a one-step L²(π) contraction, which is exactly what the measured multi-state gap
`γ = 0.0397` quantifies — drives a GEOMETRIC decay of the squared π-norm. That is the
"convergence" half of the spine, proven by elementary algebra + induction off the
foundation, with NO finite-dimensional spectral theorem (small, cache-served closure).

WHAT IS PROVED HERE (machine-checked):
  • `applyP_preserves_piMean` — detailed balance + stochastic rows ⇒ `Eπ[Pf] = Eπ[f]`,
    so the mean-zero subspace is P-invariant. (Connects to `applyP_stationary`.)
  • `geometric_convergence` — a one-step squared-π-norm contraction by `r = (1-γ)² < 1`
    ⇒ `‖Pⁿf‖²_π ≤ rⁿ ‖f‖²_π`. Gap ⇒ geometric convergence.

THE SPECTRAL CAPSTONE (`applyP_gap_contraction`) IS NOW PROVED (machine-checked): for a
reversible (π-self-adjoint) row-stochastic chain, a *scalar* Dirichlet/Rayleigh gap
`|⟨Ph,h⟩_π| ≤ (1−γ)‖h‖²_π` on the mean-zero subspace ⇒ the one-step L²(π) contraction
`‖Pf‖²_π ≤ (1−γ)²‖f‖²_π`. This is the numerical-radius = operator-norm step for a
self-adjoint operator, done elementarily (polarization + parallelogram + the
Cauchy–Schwarz discriminant argument), with NO finite-dim spectral theorem. Feeding it
(with `r = (1−γ)²`) into `geometric_convergence` closes the `gap ⇒ geometric decay` chain
with the gap as a scalar Rayleigh hypothesis that the measured `γ = 0.0397` instantiates.

WHAT REMAINS A HYPOTHESIS (honestly, not faked): the *scalar Rayleigh gap itself*
(`hray` below) — that a particular chain HAS `γ > 0` — is an input, not proved here; its
VALUE is the measured `0.0397`. `applyP_gap_contraction` proves gap ⇒ contraction; it does
NOT prove any given chain has a gap. That measurement→bound boundary is the correct honest
line (a scalar Rayleigh number in, a machine-checked operator-norm contraction out).
-/
import GibbsMultiState
import Mathlib.Algebra.Order.BigOperators.Group.Finset
import Mathlib.Algebra.QuadraticDiscriminant
import Mathlib.Analysis.SpecificLimits.Basic
import Mathlib.Topology.Algebra.InfiniteSum.Order

open Finset

namespace SutraConvergence

open GibbsMultiState

variable {S : Type*} [Fintype S]

/-- `n`-fold application of the transition operator `P` to an observable. -/
def iterP (P : S → S → ℝ) : ℕ → (S → ℝ) → (S → ℝ)
  | 0,     f => f
  | (n+1), f => applyP P (iterP P n f)

@[simp] theorem iterP_zero (P : S → S → ℝ) (f : S → ℝ) : iterP P 0 f = f := rfl

@[simp] theorem iterP_succ (P : S → S → ℝ) (n : ℕ) (f : S → ℝ) :
    iterP P (n + 1) f = applyP P (iterP P n f) := rfl

/-- The π-expectation (mean) of an observable: `Eπ[f] = ∑ s, π s · f s`. -/
def piMean (π f : S → ℝ) : ℝ := ∑ s, π s * f s

/-- The squared L²(π) norm / π-Dirichlet energy of an observable: `‖f‖²_π = ⟨f, f⟩_π`. -/
def normPiSq (π f : S → ℝ) : ℝ := innerPi π f f

/-- Detailed balance + stochastic rows ⇒ the chain PRESERVES the π-mean: `Eπ[Pf] = Eπ[f]`.
    Hence the mean-zero subspace `{f | Eπ[f] = 0}` (the deviation from stationarity) is
    P-invariant — the structural fact that lets the one-step contraction iterate. Pure exact
    finite-sum algebra; reuses `applyP_stationary` from the foundation. -/
theorem applyP_preserves_piMean (π : S → ℝ) (P : S → S → ℝ)
    (hrow : ∀ s, ∑ t, P s t = 1) (hdb : DetailedBalance π P) (f : S → ℝ) :
    piMean π (applyP P f) = piMean π f := by
  have hstat := applyP_stationary π P hrow hdb
  unfold piMean applyP
  calc ∑ s, π s * ∑ t, P s t * f t
      = ∑ s, ∑ t, π s * (P s t * f t) := by
        refine Finset.sum_congr rfl (fun s _ => ?_); rw [Finset.mul_sum]
    _ = ∑ t, ∑ s, π s * (P s t * f t) := Finset.sum_comm
    _ = ∑ t, (∑ s, π s * P s t) * f t := by
        refine Finset.sum_congr rfl (fun t _ => ?_)
        rw [Finset.sum_mul]; refine Finset.sum_congr rfl (fun s _ => ?_); ring
    _ = ∑ t, π t * f t := by
        refine Finset.sum_congr rfl (fun t _ => ?_); rw [hstat t]

/-- **Gap ⇒ geometric convergence — the convergence half of the spine.**
    If the transition operator contracts the squared π-norm by a factor `r = (1-γ)² < 1`
    in one step (`hgap`: the spectral gap stated as a one-step L²(π) Dirichlet/Rayleigh
    contraction — exactly what the measured multi-state gap `γ = 0.0397` quantifies), then
    the squared π-norm of the `n`-step iterate decays geometrically as `rⁿ`. Proven by
    elementary induction off the one-step bound; no finite-dim spectral theorem. -/
theorem geometric_convergence (π : S → ℝ) (P : S → S → ℝ) (r : ℝ) (hr0 : 0 ≤ r)
    (hgap : ∀ h : S → ℝ, normPiSq π (applyP P h) ≤ r * normPiSq π h)
    (f : S → ℝ) (n : ℕ) :
    normPiSq π (iterP P n f) ≤ r ^ n * normPiSq π f := by
  induction n with
  | zero => simp only [iterP_zero, pow_zero, one_mul, le_refl]
  | succ k ih =>
    calc normPiSq π (iterP P (k + 1) f)
        = normPiSq π (applyP P (iterP P k f)) := by rw [iterP_succ]
      _ ≤ r * normPiSq π (iterP P k f) := hgap _
      _ ≤ r * (r ^ k * normPiSq π f) := mul_le_mul_of_nonneg_left ih hr0
      _ = r ^ (k + 1) * normPiSq π f := by ring

/-- For a reversible (π-self-adjoint) chain, the one-step squared π-norm is the
    `P²`-quadratic form: `‖Pf‖²_π = ⟨f, P²f⟩_π`. One line from `applyP_selfAdjoint`
    (move one `P` across the inner product). This is the BRIDGE that the open spectral
    leg needs: it turns the one-step contraction target `‖Pf‖²_π ≤ r‖f‖²_π` into a
    bound on the quadratic form `⟨f, P²f⟩_π`, where a scalar Dirichlet/Rayleigh gap on
    the self-adjoint `P` (still to be supplied) closes it. Concretely connects the
    self-adjoint FOUNDATION (`applyP_selfAdjoint`) to the CONVERGENCE hypothesis
    (`geometric_convergence`'s `hgap`), so the chain is one dependent development. -/
theorem normPiSq_applyP_selfAdjoint (π : S → ℝ) (P : S → S → ℝ)
    (hdb : DetailedBalance π P) (f : S → ℝ) :
    normPiSq π (applyP P f) = innerPi π f (applyP P (applyP P f)) := by
  unfold normPiSq
  exact applyP_selfAdjoint π P hdb f (applyP P f)

/-! ### Inner-product scaffold for the open spectral leg

The remaining `gap ⇒ one-step contraction` leg (see
`planning/open-questions/fv-convergence-spectral-gap-leg.md`) goes through polarization for
the self-adjoint operator. These are the reusable bilinearity facts of `innerPi` it needs —
pure finite-sum algebra, no analysis. Built here so the hard leg reduces to assembling
already-checked pieces rather than one monolithic blind proof. -/

/-- `innerPi` is additive in its left argument. -/
theorem innerPi_add_left (π f g h : S → ℝ) :
    innerPi π (f + g) h = innerPi π f h + innerPi π g h := by
  unfold innerPi
  rw [← Finset.sum_add_distrib]
  exact Finset.sum_congr rfl (fun s _ => by simp only [Pi.add_apply]; ring)

/-- `innerPi` subtracts in its left argument. -/
theorem innerPi_sub_left (π f g h : S → ℝ) :
    innerPi π (f - g) h = innerPi π f h - innerPi π g h := by
  unfold innerPi
  rw [← Finset.sum_sub_distrib]
  exact Finset.sum_congr rfl (fun s _ => by simp only [Pi.sub_apply]; ring)

/-- `innerPi` is additive in its right argument (via symmetry + left additivity). -/
theorem innerPi_add_right (π f g h : S → ℝ) :
    innerPi π f (g + h) = innerPi π f g + innerPi π f h := by
  rw [innerPi_comm π f (g + h), innerPi_add_left, innerPi_comm π g f, innerPi_comm π h f]

/-- `innerPi` subtracts in its right argument. -/
theorem innerPi_sub_right (π f g h : S → ℝ) :
    innerPi π f (g - h) = innerPi π f g - innerPi π f h := by
  rw [innerPi_comm π f (g - h), innerPi_sub_left, innerPi_comm π g f, innerPi_comm π h f]

/-- The parallelogram law in the π-weighted norm:
    `‖f+g‖²_π + ‖f−g‖²_π = 2‖f‖²_π + 2‖g‖²_π`. The identity the polarization step of the
    open spectral leg rests on. -/
theorem normPiSq_parallelogram (π f g : S → ℝ) :
    normPiSq π (f + g) + normPiSq π (f - g) = 2 * normPiSq π f + 2 * normPiSq π g := by
  unfold normPiSq innerPi
  rw [Finset.mul_sum, Finset.mul_sum, ← Finset.sum_add_distrib, ← Finset.sum_add_distrib]
  exact Finset.sum_congr rfl (fun s _ => by simp only [Pi.add_apply, Pi.sub_apply]; ring)

/-- `innerPi` is homogeneous in its left argument: `⟨c·f, g⟩_π = c⟨f,g⟩_π`. -/
theorem innerPi_smul_left (π : S → ℝ) (c : ℝ) (f g : S → ℝ) :
    innerPi π (c • f) g = c * innerPi π f g := by
  unfold innerPi
  rw [Finset.mul_sum]
  exact Finset.sum_congr rfl (fun s _ => by simp only [Pi.smul_apply, smul_eq_mul]; ring)

/-- The π-weighted norm is **positive semidefinite** when `π ≥ 0`: `0 ≤ ‖f‖²_π`. This is
    the PSD fact the Cauchy–Schwarz discriminant argument for the open spectral leg needs
    (it makes `‖f − t·g‖²_π ≥ 0` a nonnegative quadratic in `t`). -/
theorem normPiSq_nonneg (π f : S → ℝ) (hπ : ∀ s, 0 ≤ π s) : 0 ≤ normPiSq π f := by
  unfold normPiSq innerPi
  refine Finset.sum_nonneg (fun s _ => ?_)
  have h : π s * f s * f s = π s * (f s * f s) := by ring
  rw [h]
  exact mul_nonneg (hπ s) (mul_self_nonneg (f s))

/-- The squared π-norm of `f − t·g` as an explicit quadratic in `t`:
    `‖f − t·g‖²_π = ‖f‖²_π − 2t⟨f,g⟩_π + t²‖g‖²_π`. With `normPiSq_nonneg` this exhibits a
    nonnegative quadratic whose discriminant is `≤ 0` — the Cauchy–Schwarz argument. -/
theorem normPiSq_sub_smul (π f g : S → ℝ) (t : ℝ) :
    normPiSq π (f - t • g)
      = normPiSq π f - 2 * t * innerPi π f g + t ^ 2 * normPiSq π g := by
  unfold normPiSq innerPi
  rw [Finset.mul_sum, Finset.mul_sum, ← Finset.sum_sub_distrib, ← Finset.sum_add_distrib]
  exact Finset.sum_congr rfl (fun s _ => by
    simp only [Pi.sub_apply, Pi.smul_apply, smul_eq_mul]; ring)

/-- **Cauchy–Schwarz for the π-weighted inner product** (π ≥ 0):
    `⟨f,g⟩²_π ≤ ‖f‖²_π · ‖g‖²_π`. Proved by the classic discriminant argument: the quadratic
    `q(t) = ‖f − t·g‖²_π = ‖g‖²_π t² − 2⟨f,g⟩_π t + ‖f‖²_π` is `≥ 0` for all `t`
    (`normPiSq_nonneg` + `normPiSq_sub_smul`), so its discriminant is `≤ 0`
    (`discrim_le_zero`), which is exactly the Cauchy–Schwarz inequality. The bound that
    converts the Rayleigh gap into the operator-norm one-step contraction. -/
theorem innerPi_cauchy_schwarz (π f g : S → ℝ) (hπ : ∀ s, 0 ≤ π s) :
    innerPi π f g ^ 2 ≤ normPiSq π f * normPiSq π g := by
  have hq : ∀ t : ℝ,
      0 ≤ normPiSq π g * (t * t) + (-2 * innerPi π f g) * t + normPiSq π f := by
    intro t
    have h := normPiSq_nonneg π (f - t • g) hπ
    rw [normPiSq_sub_smul] at h
    nlinarith [h]
  have hd := discrim_le_zero hq
  simp only [discrim] at hd
  nlinarith [hd]

/-- The transition operator is additive: `P(f+g) = Pf + Pg`. Needed to expand the
    polarization identity for the (open) numerical-radius capstone. -/
theorem applyP_add (P : S → S → ℝ) (f g : S → ℝ) :
    applyP P (f + g) = applyP P f + applyP P g := by
  funext s
  simp only [applyP, Pi.add_apply]
  rw [← Finset.sum_add_distrib]
  exact Finset.sum_congr rfl (fun t _ => by ring)

/-- The transition operator respects subtraction: `P(f−g) = Pf − Pg`. -/
theorem applyP_sub (P : S → S → ℝ) (f g : S → ℝ) :
    applyP P (f - g) = applyP P f - applyP P g := by
  funext s
  simp only [applyP, Pi.sub_apply]
  rw [← Finset.sum_sub_distrib]
  exact Finset.sum_congr rfl (fun t _ => by ring)

/-- **Polarization for the self-adjoint form** `⟨P·,·⟩_π`:
    `⟨P(f+g),f+g⟩_π − ⟨P(f−g),f−g⟩_π = 4⟨Pf,g⟩_π`. The cross terms `⟨Pg,f⟩_π` collapse to
    `⟨Pf,g⟩_π` by self-adjointness (`applyP_selfAdjoint` + `innerPi_comm`); the diagonal
    terms cancel. This is the identity that lets the scalar Rayleigh gap bound `⟨Pf,g⟩_π`,
    the heart of the numerical-radius capstone. -/
theorem innerPi_polarization (π : S → ℝ) (P : S → S → ℝ) (hdb : DetailedBalance π P)
    (f g : S → ℝ) :
    innerPi π (applyP P (f + g)) (f + g) - innerPi π (applyP P (f - g)) (f - g)
      = 4 * innerPi π (applyP P f) g := by
  have hsym : innerPi π (applyP P g) f = innerPi π (applyP P f) g := by
    rw [applyP_selfAdjoint π P hdb g f, innerPi_comm]
  simp only [applyP_add, applyP_sub, innerPi_add_left, innerPi_sub_left,
             innerPi_add_right, innerPi_sub_right, hsym]
  ring

/-- **Loop (deterministic) instance — the marginal `r = 1` case of the SAME theorem.**
    On the deterministic tensor-op target the loop core is `state ← R · state` with `R`
    orthogonal: its poles lie ON the unit circle (the Z-transform picture; measured spectral
    radius `1.00000000`), so it is norm-PRESERVING, not contracting — the boundary `r = 1`
    case of `geometric_convergence`. Stating `R` as a π-isometry (`hiso`: it preserves the
    squared π-norm, the structural hypothesis the orthogonality of the emitted rotation
    instantiates), the `n`-step iterate preserves the π-norm exactly. So loop and Gibbs
    convergence are instances of ONE framework: contraction (`r < 1`, geometric decay) for
    the thermodynamic target, marginal (`r = 1`, norm-preserving + halt-gate termination) for
    the deterministic loop. Same `iterP`, same `normPiSq` — only the spectral condition on the
    operator changes, exactly as the paper's substrate table claims. -/
theorem loop_norm_preserved (π : S → ℝ) (R : S → S → ℝ)
    (hiso : ∀ h : S → ℝ, normPiSq π (applyP R h) = normPiSq π h)
    (f : S → ℝ) (n : ℕ) :
    normPiSq π (iterP R n f) = normPiSq π f := by
  induction n with
  | zero => rw [iterP_zero]
  | succ k ih => rw [iterP_succ, hiso, ih]

/-! ### The spectral capstone: scalar Rayleigh gap ⇒ one-step L²(π) contraction

`planning/open-questions/fv-convergence-spectral-gap-leg.md`. All the scaffold above is
CI-verified; this is the final assembly (numerical radius = operator norm for a self-adjoint
operator), proved elementarily off polarization + parallelogram + Cauchy–Schwarz, no
finite-dim spectral theorem. -/

/-- `piMean` is additive. -/
theorem piMean_add (π f g : S → ℝ) : piMean π (f + g) = piMean π f + piMean π g := by
  unfold piMean
  rw [← Finset.sum_add_distrib]
  exact Finset.sum_congr rfl (fun s _ => by simp only [Pi.add_apply]; ring)

/-- `piMean` subtracts. -/
theorem piMean_sub (π f g : S → ℝ) : piMean π (f - g) = piMean π f - piMean π g := by
  unfold piMean
  rw [← Finset.sum_sub_distrib]
  exact Finset.sum_congr rfl (fun s _ => by simp only [Pi.sub_apply]; ring)

/-- `piMean` is homogeneous: `Eπ[c·f] = c·Eπ[f]`. -/
theorem piMean_smul (π : S → ℝ) (t : ℝ) (f : S → ℝ) :
    piMean π (t • f) = t * piMean π f := by
  unfold piMean
  rw [Finset.mul_sum]
  exact Finset.sum_congr rfl (fun s _ => by simp only [Pi.smul_apply, smul_eq_mul]; ring)

/-- The squared π-norm is quadratic in a scalar: `‖t·f‖²_π = t²‖f‖²_π`. -/
theorem normPiSq_smul (π : S → ℝ) (t : ℝ) (f : S → ℝ) :
    normPiSq π (t • f) = t ^ 2 * normPiSq π f := by
  unfold normPiSq
  rw [innerPi_smul_left, innerPi_comm π f (t • f), innerPi_smul_left]
  ring

/-- **Rayleigh polarization bound.** If the self-adjoint form obeys the scalar Rayleigh gap
    `|⟨Ph,h⟩_π| ≤ c‖h‖²_π` on every mean-zero `h`, then for mean-zero `f, g`:
    `2⟨Pf,g⟩_π ≤ c(‖f‖²_π + ‖g‖²_π)`. Proof: polarization turns `4⟨Pf,g⟩_π` into the two
    diagonal forms `⟨P(f±g),f±g⟩_π`, the gap bounds each by `c‖f±g‖²_π`, and the
    parallelogram law collapses `‖f+g‖²_π + ‖f−g‖²_π` to `2‖f‖²_π + 2‖g‖²_π`. Pure bilinear
    algebra off the already-checked scaffold. -/
theorem rayleigh_polar_bound (π : S → ℝ) (P : S → S → ℝ) (c : ℝ)
    (hdb : DetailedBalance π P)
    (hray : ∀ h : S → ℝ, piMean π h = 0 → |innerPi π (applyP P h) h| ≤ c * normPiSq π h)
    (f g : S → ℝ) (hf0 : piMean π f = 0) (hg0 : piMean π g = 0) :
    2 * innerPi π (applyP P f) g ≤ c * (normPiSq π f + normPiSq π g) := by
  have hfg0 : piMean π (f + g) = 0 := by rw [piMean_add, hf0, hg0]; ring
  have hfmg0 : piMean π (f - g) = 0 := by rw [piMean_sub, hf0, hg0]; ring
  -- `|⟨Ph,h⟩_π| ≤ c‖h‖²_π` gives both an upper bound on `⟨P(f+g),f+g⟩_π` and a lower bound
  -- on `⟨P(f−g),f−g⟩_π` — the two pieces the polarization difference needs.
  have hb1 := abs_le.mp (hray (f + g) hfg0)
  have hb2 := abs_le.mp (hray (f - g) hfmg0)
  have e := innerPi_polarization π P hdb f g
  have par := normPiSq_parallelogram π f g
  have parc : c * (normPiSq π (f + g) + normPiSq π (f - g))
            = c * (2 * normPiSq π f + 2 * normPiSq π g) := by rw [par]
  nlinarith [e, hb1.1, hb1.2, hb2.1, hb2.2, parc]

/-- Pure real-arithmetic core of the capstone: a quadratic `c·a·t² − 2a·t + c·b ≥ 0` for all
    `t` (with `a,b,c ≥ 0`) forces `a ≤ c²·b`, by the discriminant (Cauchy–Schwarz) argument
    plus cancellation of a positive `a`. Isolated from the substrate so the discriminant step
    reuses the same `discrim_le_zero` pattern as `innerPi_cauchy_schwarz`. -/
theorem quad_to_bound {a b c : ℝ} (ha : 0 ≤ a) (hb : 0 ≤ b) (_hc : 0 ≤ c)
    (H : ∀ t : ℝ, 0 ≤ (c * a) * (t * t) + (-2 * a) * t + c * b) :
    a ≤ c ^ 2 * b := by
  have hd := discrim_le_zero H
  simp only [discrim] at hd
  by_cases hazero : a = 0
  · rw [hazero]; nlinarith [sq_nonneg c, hb]
  · have hapos : 0 < a := lt_of_le_of_ne ha (Ne.symm hazero)
    have h2 : a * a ≤ c ^ 2 * b * a := by nlinarith [hd]
    nlinarith [h2, hapos]

/-- **THE SPECTRAL CAPSTONE — scalar Rayleigh gap ⇒ one-step L²(π) contraction.**
    For a row-stochastic, reversible (π-self-adjoint) chain with `π ≥ 0`, if the self-adjoint
    form obeys the scalar Dirichlet/Rayleigh gap `|⟨Ph,h⟩_π| ≤ c‖h‖²_π` on the mean-zero
    subspace (with `c = 1 − γ` the measured gap complement), then the transition operator
    contracts the squared π-norm of a mean-zero observable by `c²`:
    `‖Pf‖²_π ≤ c²‖f‖²_π`.

    This is exactly `geometric_convergence`'s hypothesis `hgap` (with `r = c² = (1−γ)²`), so
    together they give a fully-closed `gap ⇒ geometric decay`. Proof = numerical-radius bound
    for the self-adjoint `P`: `rayleigh_polar_bound` gives `2⟨Pf,g⟩_π ≤ c(‖f‖²_π + ‖g‖²_π)`
    for every mean-zero `g`; instantiating `g = t·Pf` (mean-zero, by `applyP_preserves_piMean`)
    for all `t` exhibits a nonnegative quadratic in `t` whose discriminant (`quad_to_bound`)
    yields `‖Pf‖²_π ≤ c²‖f‖²_π`. No finite-dim spectral theorem. -/
theorem applyP_gap_contraction (π : S → ℝ) (P : S → S → ℝ) (c : ℝ)
    (hπ : ∀ s, 0 ≤ π s) (hc0 : 0 ≤ c)
    (hrow : ∀ s, ∑ t, P s t = 1) (hdb : DetailedBalance π P)
    (hray : ∀ h : S → ℝ, piMean π h = 0 → |innerPi π (applyP P h) h| ≤ c * normPiSq π h)
    (f : S → ℝ) (hf0 : piMean π f = 0) :
    normPiSq π (applyP P f) ≤ c ^ 2 * normPiSq π f := by
  have hPf0 : piMean π (applyP P f) = 0 := by
    rw [applyP_preserves_piMean π P hrow hdb f, hf0]
  refine quad_to_bound (normPiSq_nonneg π _ hπ) (normPiSq_nonneg π _ hπ) hc0 ?_
  intro t
  have hg0 : piMean π (t • applyP P f) = 0 := by rw [piMean_smul, hPf0, mul_zero]
  have hb := rayleigh_polar_bound π P c hdb hray f (t • applyP P f) hf0 hg0
  have e1 : innerPi π (applyP P f) (t • applyP P f) = t * normPiSq π (applyP P f) := by
    rw [innerPi_comm π (applyP P f) (t • applyP P f), innerPi_smul_left]; rfl
  have e2 : normPiSq π (t • applyP P f) = t ^ 2 * normPiSq π (applyP P f) :=
    normPiSq_smul π t (applyP P f)
  rw [e1, e2] at hb
  nlinarith [hb]

/-! ### The Z-transform pole = the contraction rate (loop and Gibbs as one theorem)

The spine's step 3 (`FV-LEAN-HANDOFF-2026-06-29.md` §⭐⭐): the deterministic loop and the
thermodynamic Gibbs chain are instances of the SAME convergence statement, unified by the
Z-transform. The generating function of the energy sequence `aₙ = ‖Pⁿf‖²_π` is
`G(z) = Σₙ aₙ zⁿ`; its radius of convergence is `1/r` where `r` is the one-step contraction
rate, so **the pole of the Z-transform sits at `|z| = 1/r`, i.e. the pole radius (in the
standard `z⁻¹` convention) equals `r`.** For the Gibbs chain `r = (1−γ)² < 1` (the spectral
gap), the pole is strictly inside and `G(1)` converges — the chain settles with finite total
deviation-energy. For the deterministic loop `r = 1` (orthogonal `R`, `loop_norm_preserved`),
the pole is exactly ON the unit circle — marginal stability, norm-preserving, termination is
the halt gate. Same `iterP`, same generating function; only the pole radius `= r` changes,
which is exactly the paper's substrate table. Proved by comparison with the geometric series
(`Mathlib.Analysis.SpecificLimits`), no finite-dim spectral theorem. This is the machine-checked
form of "the spectral gap IS a Z-transform pole." -/

/-- **Z-transform pole = contraction rate (Gibbs / contracting case).** If the transition
    operator contracts the squared π-norm by `r` in one step (`hgap`, e.g. `r = (1−γ)²` from
    the spectral gap), the energy generating function `G(z) = Σₙ ‖Pⁿf‖²_π zⁿ` is summable for
    every `0 ≤ z` with `r·z < 1` — i.e. for `z < 1/r`. So the Z-transform's pole is at
    `z = 1/r`: the pole radius equals the contraction rate `r`. -/
theorem energy_gen_summable (π : S → ℝ) (P : S → S → ℝ) (r z : ℝ)
    (hπ : ∀ s, 0 ≤ π s) (hr0 : 0 ≤ r) (hz0 : 0 ≤ z) (hrz : r * z < 1)
    (hgap : ∀ h : S → ℝ, normPiSq π (applyP P h) ≤ r * normPiSq π h)
    (f : S → ℝ) :
    Summable (fun n => normPiSq π (iterP P n f) * z ^ n) := by
  have hbound : ∀ n, normPiSq π (iterP P n f) * z ^ n ≤ normPiSq π f * (r * z) ^ n := by
    intro n
    have hg := geometric_convergence π P r hr0 hgap f n
    have hz : (0 : ℝ) ≤ z ^ n := pow_nonneg hz0 n
    calc normPiSq π (iterP P n f) * z ^ n
        ≤ (r ^ n * normPiSq π f) * z ^ n := mul_le_mul_of_nonneg_right hg hz
      _ = normPiSq π f * (r * z) ^ n := by rw [mul_pow]; ring
  have hnonneg : ∀ n, 0 ≤ normPiSq π (iterP P n f) * z ^ n := fun n =>
    mul_nonneg (normPiSq_nonneg π _ hπ) (pow_nonneg hz0 n)
  have hsum_geo : Summable (fun n => normPiSq π f * (r * z) ^ n) :=
    (summable_geometric_of_lt_one (mul_nonneg hr0 hz0) hrz).mul_left (normPiSq π f)
  exact Summable.of_nonneg_of_le hnonneg hbound hsum_geo

/-- **The chain settles (contraction ⇒ `G(1)` converges).** When `r < 1` the pole radius
    `1/r > 1`, so the Z-transform converges at `z = 1`: the total accumulated deviation-energy
    `Σₙ ‖Pⁿf‖²_π` is finite. This is the `z = 1` value of `energy_gen_summable`. -/
theorem energy_summable_of_contraction (π : S → ℝ) (P : S → S → ℝ) (r : ℝ)
    (hπ : ∀ s, 0 ≤ π s) (hr0 : 0 ≤ r) (hr1 : r < 1)
    (hgap : ∀ h : S → ℝ, normPiSq π (applyP P h) ≤ r * normPiSq π h)
    (f : S → ℝ) :
    Summable (fun n => normPiSq π (iterP P n f)) := by
  have h := energy_gen_summable π P r 1 hπ hr0 (by norm_num) (by rw [mul_one]; exact hr1) hgap f
  simpa using h

/-- **Loop (`r = 1`) boundary — the pole ON the unit circle.** For a π-isometry `R` the energy
    is CONSTANT (`loop_norm_preserved`), so its generating function is `‖f‖²_π · Σₙ zⁿ`, which
    converges exactly for `0 ≤ z < 1`: the pole sits AT `z = 1`, on the unit circle. Marginal
    stability — the same Z-transform picture as `energy_gen_summable`, at the boundary `r = 1`
    (norm-preserving; termination is the halt gate, not spectral decay). -/
theorem loop_energy_gen_summable (π : S → ℝ) (R : S → S → ℝ) (z : ℝ)
    (hz0 : 0 ≤ z) (hz1 : z < 1)
    (hiso : ∀ h : S → ℝ, normPiSq π (applyP R h) = normPiSq π h)
    (f : S → ℝ) :
    Summable (fun n => normPiSq π (iterP R n f) * z ^ n) := by
  have hconst : (fun n => normPiSq π (iterP R n f) * z ^ n)
              = (fun n => normPiSq π f * z ^ n) := by
    funext n; rw [loop_norm_preserved π R hiso f n]
  rw [hconst]
  exact (summable_geometric_of_lt_one hz0 hz1).mul_left (normPiSq π f)

#print axioms applyP_preserves_piMean
#print axioms geometric_convergence
#print axioms rayleigh_polar_bound
#print axioms quad_to_bound
#print axioms applyP_gap_contraction
#print axioms energy_gen_summable
#print axioms energy_summable_of_contraction
#print axioms loop_energy_gen_summable
#print axioms normPiSq_applyP_selfAdjoint
#print axioms innerPi_add_left
#print axioms innerPi_sub_left
#print axioms innerPi_add_right
#print axioms innerPi_sub_right
#print axioms innerPi_polarization
#print axioms normPiSq_parallelogram
#print axioms innerPi_smul_left
#print axioms normPiSq_nonneg
#print axioms normPiSq_sub_smul
#print axioms innerPi_cauchy_schwarz
#print axioms applyP_add
#print axioms applyP_sub
#print axioms loop_norm_preserved

end SutraConvergence
