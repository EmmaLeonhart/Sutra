/-
Sutra → thrml, FV-in-Lean: GENERAL finite-state reversibility (the multi-state step).

`GibbsMathlib.lean` mechanised the **2-state** (`Bool`) convergence picture in full —
detailed balance ⇒ stationarity, the 2-state spectral gap, TV mixing. The *measured*
multi-state gap (audit row 9: the 8-state AND-gadget chain, γ = 0.0397) is tier **M**
(numerical), not **L** (Lean). Promoting it is the spine's open M→L item.

This file is the first **general-finite-state** (`Fintype S`, any size) leg of that
promotion. It proves, for an arbitrary finite reversible chain, the structural facts on
which the whole multi-state convergence-rate argument rests — all by exact finite-sum
algebra from detailed balance, with NO spectral-theory import (so the dependency closure
is small and cache-served):

  1. `innerPi_comm`         — the π-weighted inner product is symmetric.
  2. `applyP_stationary`    — detailed balance ⇒ the Gibbs/stationary vector is fixed by
                              the chain (general-S, mirrors `stationary_of_detailedBalance`).
  3. `applyP_selfAdjoint`   — detailed balance ⇒ the transition operator is SELF-ADJOINT
                              w.r.t. the π-weighted inner product: ⟨Pf, g⟩_π = ⟨f, Pg⟩_π.

(3) is the key one: self-adjointness is exactly what makes the multi-state spectral gap
well-defined — a π-self-adjoint operator on a finite-dimensional inner-product space has a
real spectrum and an orthonormal eigenbasis, so the gap `γ = 1 − λ₂` (second-largest
eigenvalue) is real and the L²(π) deviation from π contracts by `(1 − γ)` per step. That
last eigenvalue step is mathlib's finite-dim spectral theorem on this self-adjoint
operator — the documented next leg; this file discharges the reversible-self-adjoint
foundation it stands on, for ANY finite state space (the 8-state gadget chain included).
-/
import Mathlib.Algebra.BigOperators.Ring.Finset
import Mathlib.Algebra.BigOperators.Group.Finset.Sigma
import Mathlib.Data.Real.Basic
import Mathlib.Tactic.Ring
import Mathlib.Tactic.LinearCombination

open Finset

namespace GibbsMultiState

variable {S : Type*} [Fintype S]

/-- Detailed balance (reversibility) of `π` w.r.t. kernel `P`: `π s · P s t = π t · P t s`. -/
def DetailedBalance (π : S → ℝ) (P : S → S → ℝ) : Prop := ∀ s t, π s * P s t = π t * P t s

/-- The π-weighted inner product on observables `S → ℝ`: `⟨f, g⟩_π = ∑ s, π s · f s · g s`. -/
def innerPi (π f g : S → ℝ) : ℝ := ∑ s, π s * f s * g s

/-- The transition operator acting on observables (forward action): `(P·f) s = ∑ t, P s t · f t`. -/
def applyP (P : S → S → ℝ) (f : S → ℝ) : S → ℝ := fun s => ∑ t, P s t * f t

/-- The π-weighted inner product is symmetric. -/
theorem innerPi_comm (π f g : S → ℝ) : innerPi π f g = innerPi π g f := by
  unfold innerPi; exact Finset.sum_congr rfl (fun s _ => by ring)

/-- GENERAL finite-state: detailed balance ⇒ the stationary (Gibbs) vector `π` is a fixed
    point of the chain's right action `∑ s, π s · P s t = π t`. The reversible half of
    "the Gibbs measure is the stationary distribution", for ANY finite state space. -/
theorem applyP_stationary (π : S → ℝ) (P : S → S → ℝ)
    (hrow : ∀ s, ∑ t, P s t = 1) (hdb : DetailedBalance π P) :
    ∀ t, ∑ s, π s * P s t = π t := by
  intro t
  calc ∑ s, π s * P s t
      = ∑ s, π t * P t s := Finset.sum_congr rfl (fun s _ => hdb s t)
    _ = π t * ∑ s, P t s := by rw [Finset.mul_sum]
    _ = π t * 1 := by rw [hrow t]
    _ = π t := by ring

/-- GENERAL finite-state: detailed balance ⇒ the transition operator is SELF-ADJOINT in
    the π-weighted inner product: `⟨Pf, g⟩_π = ⟨f, Pg⟩_π`. This is the reversible-chain
    fact that makes the multi-state spectral gap real and well-defined (real spectrum,
    `γ = 1 − λ₂`). Pure exact finite-sum algebra from detailed balance — no spectral theory. -/
theorem applyP_selfAdjoint (π : S → ℝ) (P : S → S → ℝ) (hdb : DetailedBalance π P)
    (f g : S → ℝ) : innerPi π (applyP P f) g = innerPi π f (applyP P g) := by
  -- Unfold (beta-reducing the applied kernel) and distribute every product-of-sum into a
  -- double sum, then swap the LHS summation order to range as ∑ a ∑ b like the RHS.
  simp only [innerPi, applyP, Finset.sum_mul, Finset.mul_sum]
  rw [Finset.sum_comm]
  refine Finset.sum_congr rfl (fun a _ => Finset.sum_congr rfl (fun b _ => ?_))
  -- term: (π b · P b a · f a · g b) = (π a · P a b · f a · g b), via π b·P b a = π a·P a b.
  linear_combination (f a * g b) * hdb b a

#print axioms innerPi_comm
#print axioms applyP_stationary
#print axioms applyP_selfAdjoint

end GibbsMultiState
