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
  | zero => simp only [iterP_zero, pow_zero, one_mul]
  | succ k ih =>
    calc normPiSq π (iterP P (k + 1) f)
        = normPiSq π (applyP P (iterP P k f)) := by rw [iterP_succ]
      _ ≤ r * normPiSq π (iterP P k f) := hgap _
      _ ≤ r * (r ^ k * normPiSq π f) := mul_le_mul_of_nonneg_left ih hr0
      _ = r ^ (k + 1) * normPiSq π f := by ring

#print axioms applyP_preserves_piMean
#print axioms geometric_convergence

end SutraConvergence
