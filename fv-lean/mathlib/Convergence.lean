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

WHAT IS NOT YET PROVED (the honest remaining spectral leg, flagged not faked): deriving
the one-step contraction hypothesis `hgap` from `applyP_selfAdjoint` + a scalar
Dirichlet-form gap `γ > 0` (self-adjoint ⇒ real spectrum ⇒ Rayleigh bound). `hgap` is
here a hypothesis — the spectral gap as a Poincaré/Dirichlet inequality — and the measured
`γ` is its instance. Do NOT read `geometric_convergence` as a proof that any particular
chain has a gap; it proves gap ⇒ decay.
-/
import GibbsMultiState
import Mathlib.Algebra.Order.BigOperators.Group.Finset

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

#print axioms applyP_preserves_piMean
#print axioms geometric_convergence
#print axioms normPiSq_applyP_selfAdjoint
#print axioms innerPi_add_left
#print axioms innerPi_sub_left
#print axioms normPiSq_parallelogram
#print axioms innerPi_smul_left
#print axioms normPiSq_nonneg
#print axioms normPiSq_sub_smul
#print axioms loop_norm_preserved

end SutraConvergence
