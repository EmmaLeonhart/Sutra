/-
Sutra → thrml, FV-in-Lean: the CONTINUOUS-TIME decay of the thrml chain (audit item 2).

Emma's reframe (2026-07-04, AskUserQuestion): the formal-verification target is the **thrml
compile target's actual sampler** — `codegen_thrml.py` executes discrete-state block-Gibbs
over spin registers, whose continuous-time law is the finite-state Markov **jump process**
with generator `Q` (heat-bath rates), the exact object `fv_sampler_convergence.py` measures
(master equation `dp/dt = Qᵀp`; observable side `df/dt = Qf`; measured spectral gap
γ = 0.0397 on the 8-state AND gadget at β = 1). The continuous-SPACE Langevin diffusion is
NOT the substrate's object (and is out of proof-assistant reach — see
`planning/findings/2026-07-04-langevin-lean-scoping.md`); THIS file is the honest
continuous-time leg: lean-gap-audit item 2.

WHAT IS PROVED (machine-checked, any finite S):
  • `gen_applyP_piMean_zero` — a reversible generator (rows sum to 0 + detailed balance)
    conserves the π-mean of observables: `Eπ[Qh] = 0`.
  • `gen_rayleigh_eq_neg_dirichlet` — the generator-side Dirichlet identity
    `⟨Qf, f⟩_π = −E_Q(f)` with `E_Q(f) = ½∑ π_s Q_{st}(f_s−f_t)²` (the same per-edge form
    `gen_poincare` consumes; rows-sum-0 replaces row-stochasticity in `dirichlet_eq`).
  • `flow_piMean_const` — ANY trajectory of the observable master equation `df/dt = Qf`
    conserves the π-mean (derivative is zero, so the mean is constant — the mean-zero
    deviation subspace is flow-invariant).
  • `flow_energy_decay` — **the continuous-time convergence statement**: along any
    master-equation trajectory started mean-zero, a Poincaré constant
    `γ·‖h‖²_π ≤ E_Q(h)` on mean-zero h forces
        `‖f_t‖²_π ≤ exp(−2γt) · ‖f_0‖²_π`   for all t ≥ 0.
    Proof: `d/dt ‖f_t‖²_π = 2⟨Qf_t, f_t⟩_π = −2·E_Q(f_t) ≤ −2γ‖f_t‖²_π`, and the
    exponentially-weighted energy `‖f_t‖²_π·e^{2γt}` has nonpositive derivative, hence is
    antitone — Grönwall by hand, no ODE-library import.

WHAT REMAINS A HYPOTHESIS (honestly, not faked): the Poincaré constant itself. For the
8-state gadget generator the heat-bath rates vanish between non-neighbouring spin
configurations, so the per-edge ratio route (`gen_poincare`) cannot produce its γ — the
measured γ = 0.0397 instantiates `hpoin`'s VALUE as a measurement, exactly as on the
discrete-time side. The trajectory is likewise hypothesized to satisfy the master ODE
(`hderiv`) — this file verifies that ANY law obeying the thrml chain's master equation
decays, which is the verification-relevant statement; it does not construct `e^{tQ}`.
-/
import Convergence
import Mathlib.Analysis.SpecialFunctions.ExpDeriv
import Mathlib.Analysis.Calculus.Deriv.MeanValue

open Finset

namespace GibbsFlow

open GibbsMultiState SutraConvergence

variable {S : Type*} [Fintype S]

/-- A reversible generator conserves the π-mean: rows sum to 0 + detailed balance ⇒
    `Eπ[Qh] = 0`. (The generator-side analogue of `applyP_preserves_piMean`.) -/
theorem gen_applyP_piMean_zero (π : S → ℝ) (Q : S → S → ℝ)
    (hrow0 : ∀ s, ∑ t, Q s t = 0) (hdb : DetailedBalance π Q) (h : S → ℝ) :
    piMean π (applyP Q h) = 0 := by
  unfold piMean applyP
  calc ∑ s, π s * ∑ t, Q s t * h t
      = ∑ s, ∑ t, π s * (Q s t * h t) := by
        refine Finset.sum_congr rfl (fun s _ => ?_); rw [Finset.mul_sum]
    _ = ∑ t, ∑ s, π s * (Q s t * h t) := Finset.sum_comm
    _ = ∑ t, (∑ s, π s * Q s t) * h t := by
        refine Finset.sum_congr rfl (fun t _ => ?_)
        rw [Finset.sum_mul]; exact Finset.sum_congr rfl (fun s _ => by ring)
    _ = ∑ t, (π t * ∑ s, Q t s) * h t := by
        refine Finset.sum_congr rfl (fun t _ => ?_)
        congr 1
        calc ∑ s, π s * Q s t = ∑ s, π t * Q t s :=
              Finset.sum_congr rfl (fun s _ => hdb s t)
          _ = π t * ∑ s, Q t s := by rw [Finset.mul_sum]
    _ = 0 := Finset.sum_eq_zero (fun t _ => by rw [hrow0 t]; ring)

/-- **Generator Dirichlet identity.** For a reversible generator (rows sum to 0 + detailed
    balance), `⟨Qf, f⟩_π = −E_Q(f)` where `E_Q` is the same per-edge Dirichlet form the
    discrete-time engine uses (`dirichlet`). Mirrors `dirichlet_eq`, with the diagonal
    terms killed by the zero row sums instead of contributing the norm. -/
theorem gen_rayleigh_eq_neg_dirichlet (π : S → ℝ) (Q : S → S → ℝ)
    (hrow0 : ∀ s, ∑ t, Q s t = 0) (hdb : DetailedBalance π Q) (f : S → ℝ) :
    innerPi π (applyP Q f) f = - dirichlet π Q f := by
  have hA : ∑ s, ∑ t, π s * Q s t * (f s * f s) = 0 := by
    refine Finset.sum_eq_zero (fun s _ => ?_)
    calc ∑ t, π s * Q s t * (f s * f s)
        = (π s * f s * f s) * ∑ t, Q s t := by
          rw [Finset.mul_sum]; exact Finset.sum_congr rfl (fun t _ => by ring)
      _ = 0 := by rw [hrow0 s]; ring
  have hB : ∑ s, ∑ t, π s * Q s t * (f s * f t) = innerPi π f (applyP Q f) := by
    unfold innerPi applyP
    refine Finset.sum_congr rfl (fun s _ => ?_)
    rw [Finset.mul_sum]
    exact Finset.sum_congr rfl (fun t _ => by ring)
  have hC : ∑ s, ∑ t, π s * Q s t * (f t * f t) = 0 := by
    have hswap : ∑ s, ∑ t, π s * Q s t * (f t * f t)
               = ∑ s, ∑ t, π t * Q t s * (f t * f t) :=
      Finset.sum_congr rfl (fun s _ => Finset.sum_congr rfl (fun t _ => by rw [hdb s t]))
    rw [hswap, Finset.sum_comm]
    refine Finset.sum_eq_zero (fun t _ => ?_)
    calc ∑ s, π t * Q t s * (f t * f t)
        = (π t * f t * f t) * ∑ s, Q t s := by
          rw [Finset.mul_sum]; exact Finset.sum_congr rfl (fun s _ => by ring)
      _ = 0 := by rw [hrow0 t]; ring
  have hpt : ∀ s, ∑ t, π s * Q s t * (f s - f t) ^ 2
           = (∑ t, π s * Q s t * (f s * f s))
             - 2 * (∑ t, π s * Q s t * (f s * f t))
             + (∑ t, π s * Q s t * (f t * f t)) := by
    intro s
    rw [Finset.mul_sum, ← Finset.sum_sub_distrib, ← Finset.sum_add_distrib]
    exact Finset.sum_congr rfl (fun t _ => by ring)
  have hmerge : (∑ s, ∑ t, π s * Q s t * (f s - f t) ^ 2)
        = (∑ s, ∑ t, π s * Q s t * (f s * f s))
          - 2 * (∑ s, ∑ t, π s * Q s t * (f s * f t))
          + (∑ s, ∑ t, π s * Q s t * (f t * f t)) := by
    calc ∑ s, ∑ t, π s * Q s t * (f s - f t) ^ 2
        = ∑ s, ((∑ t, π s * Q s t * (f s * f s))
                - 2 * (∑ t, π s * Q s t * (f s * f t))
                + (∑ t, π s * Q s t * (f t * f t))) :=
          Finset.sum_congr rfl (fun s _ => hpt s)
      _ = _ := by rw [Finset.sum_add_distrib, Finset.sum_sub_distrib, ← Finset.mul_sum]
  have hd : dirichlet π Q f = - innerPi π f (applyP Q f) := by
    unfold dirichlet
    rw [hmerge, hA, hB, hC]; ring
  rw [innerPi_comm π (applyP Q f) f, hd]; ring

/-- **The flow conserves the π-mean.** Any trajectory of the observable master equation
    `df/dt = Qf` has constant π-mean: its derivative is `Eπ[Qf_τ] = 0`
    (`gen_applyP_piMean_zero`), and a function with vanishing derivative is both antitone
    and monotone, hence constant. Keeps the flow inside the mean-zero deviation subspace. -/
theorem flow_piMean_const (π : S → ℝ) (Q : S → S → ℝ)
    (hrow0 : ∀ s, ∑ t, Q s t = 0) (hdb : DetailedBalance π Q)
    (f : ℝ → S → ℝ)
    (hderiv : ∀ s t, HasDerivAt (fun τ => f τ s) (applyP Q (f t) s) t)
    (t : ℝ) : piMean π (f t) = piMean π (f 0) := by
  have hg : ∀ τ : ℝ, HasDerivAt (fun σ => piMean π (f σ)) 0 τ := by
    intro τ
    have hsum : HasDerivAt (fun σ => ∑ s, π s * f σ s)
        (∑ s, π s * applyP Q (f τ) s) τ :=
      HasDerivAt.fun_sum (fun s _ => (hderiv s τ).const_mul (π s))
    have hval : (∑ s, π s * applyP Q (f τ) s) = 0 := by
      simpa [piMean] using gen_applyP_piMean_zero π Q hrow0 hdb (f τ)
    rw [hval] at hsum
    simpa only [piMean] using hsum
  have hdiff : Differentiable ℝ (fun σ => piMean π (f σ)) :=
    fun τ => (hg τ).differentiableAt
  have hanti : Antitone (fun σ => piMean π (f σ)) :=
    antitone_of_deriv_nonpos hdiff (fun τ => (hg τ).deriv.le)
  have hmono : Monotone (fun σ => piMean π (f σ)) :=
    monotone_of_deriv_nonneg hdiff (fun τ => (hg τ).deriv.ge)
  rcases le_total 0 t with h0t | ht0
  · exact le_antisymm (hanti h0t) (hmono h0t)
  · exact le_antisymm (hmono ht0) (hanti ht0)

/-- The deviation-energy `‖f_τ‖²_π` is differentiable along the flow, with derivative
    `2⟨Qf_t, f_t⟩_π` — the product rule summed over states. -/
theorem flow_energy_hasDeriv (π : S → ℝ) (Q : S → S → ℝ)
    (f : ℝ → S → ℝ)
    (hderiv : ∀ s t, HasDerivAt (fun τ => f τ s) (applyP Q (f t) s) t)
    (t : ℝ) :
    HasDerivAt (fun σ => normPiSq π (f σ))
      (2 * innerPi π (applyP Q (f t)) (f t)) t := by
  have hsum : HasDerivAt (fun σ => ∑ s, π s * f σ s * f σ s)
      (∑ s, (π s * applyP Q (f t) s * f t s + π s * f t s * applyP Q (f t) s)) t := by
    refine HasDerivAt.fun_sum (fun s _ => ?_)
    exact ((hderiv s t).const_mul (π s)).fun_mul (hderiv s t)
  have hval : (∑ s, (π s * applyP Q (f t) s * f t s + π s * f t s * applyP Q (f t) s))
      = 2 * innerPi π (applyP Q (f t)) (f t) := by
    calc ∑ s, (π s * applyP Q (f t) s * f t s + π s * f t s * applyP Q (f t) s)
        = ∑ s, 2 * (π s * applyP Q (f t) s * f t s) :=
          Finset.sum_congr rfl (fun s _ => by ring)
      _ = 2 * ∑ s, π s * applyP Q (f t) s * f t s := by rw [Finset.mul_sum]
      _ = 2 * innerPi π (applyP Q (f t)) (f t) := rfl
  have hgoal := hval ▸ hsum
  simpa only [normPiSq, innerPi] using hgoal

/-- **Continuous-time decay of the thrml chain — Grönwall by hand.** Along any trajectory
    of the observable master equation `df/dt = Qf` for a reversible generator, started
    mean-zero, a Poincaré bound `γ‖h‖²_π ≤ E_Q(h)` on the mean-zero subspace forces
    `‖f_t‖²_π ≤ e^{−2γt}‖f_0‖²_π` for all `t ≥ 0`. This is the continuous-time analogue of
    `geometric_decay_of_poincare_lazy` and the machine-checked form of the decay that
    `fv_sampler_convergence.py` MEASURES on the 8-state AND-gadget generator (rate = the
    spectral gap, measured γ = 0.0397 — the γ VALUE stays a measurement; see the header). -/
theorem flow_energy_decay (π : S → ℝ) (Q : S → S → ℝ) (γ : ℝ)
    (hrow0 : ∀ s, ∑ t, Q s t = 0) (hdb : DetailedBalance π Q)
    (hpoin : ∀ h : S → ℝ, piMean π h = 0 → γ * normPiSq π h ≤ dirichlet π Q h)
    (f : ℝ → S → ℝ)
    (hderiv : ∀ s t, HasDerivAt (fun τ => f τ s) (applyP Q (f t) s) t)
    (hmz0 : piMean π (f 0) = 0)
    (t : ℝ) (ht : 0 ≤ t) :
    normPiSq π (f t) ≤ Real.exp (-(2 * γ * t)) * normPiSq π (f 0) := by
  have hmz : ∀ τ, piMean π (f τ) = 0 := fun τ => by
    rw [flow_piMean_const π Q hrow0 hdb f hderiv τ, hmz0]
  -- the exponentially-weighted energy and its derivative
  have hφderiv : ∀ τ : ℝ, HasDerivAt (fun σ => normPiSq π (f σ) * Real.exp (2 * γ * σ))
      ((2 * innerPi π (applyP Q (f τ)) (f τ)) * Real.exp (2 * γ * τ)
        + normPiSq π (f τ) * (Real.exp (2 * γ * τ) * (2 * γ))) τ := by
    intro τ
    have hlin : HasDerivAt (fun σ : ℝ => 2 * γ * σ) (2 * γ) τ := hasDerivAt_const_mul (2 * γ)
    exact (flow_energy_hasDeriv π Q f hderiv τ).fun_mul hlin.exp
  -- the weighted energy is antitone: its derivative is ≤ 0 everywhere
  have hφanti : Antitone (fun σ => normPiSq π (f σ) * Real.exp (2 * γ * σ)) := by
    refine antitone_of_deriv_nonpos (fun τ => (hφderiv τ).differentiableAt) (fun τ => ?_)
    rw [(hφderiv τ).deriv, gen_rayleigh_eq_neg_dirichlet π Q hrow0 hdb (f τ)]
    have key : (γ * normPiSq π (f τ) - dirichlet π Q (f τ)) * Real.exp (2 * γ * τ) ≤ 0 :=
      mul_nonpos_of_nonpos_of_nonneg (by linarith [hpoin (f τ) (hmz τ)])
        (le_of_lt (Real.exp_pos _))
    nlinarith [key]
  have hφle : normPiSq π (f t) * Real.exp (2 * γ * t)
            ≤ normPiSq π (f 0) * Real.exp (2 * γ * 0) := hφanti ht
  have hφle' : normPiSq π (f t) * Real.exp (2 * γ * t) ≤ normPiSq π (f 0) := by
    simpa using hφle
  have hmul := mul_le_mul_of_nonneg_right hφle' (le_of_lt (Real.exp_pos (-(2 * γ * t))))
  calc normPiSq π (f t)
      = normPiSq π (f t) * Real.exp (2 * γ * t) * Real.exp (-(2 * γ * t)) := by
        rw [mul_assoc, ← Real.exp_add]
        simp
    _ ≤ normPiSq π (f 0) * Real.exp (-(2 * γ * t)) := hmul
    _ = Real.exp (-(2 * γ * t)) * normPiSq π (f 0) := by ring

#print axioms gen_applyP_piMean_zero
#print axioms gen_rayleigh_eq_neg_dirichlet
#print axioms flow_piMean_const
#print axioms flow_energy_hasDeriv
#print axioms flow_energy_decay

end GibbsFlow
