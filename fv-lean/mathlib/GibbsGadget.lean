/-
Sutra → thrml, FV-in-Lean: the CONCRETE 8-state AND-gadget Gibbs chain — gap COMPUTED.

This is queue leg (a2) (green-lit by Emma 2026-07-03): discharge a machine-checked spectral
gap for a literal 8-state AND-gadget Gibbs sampler, feeding the general conductance engine
(`gen_poincare` + `geometric_decay_of_poincare_lazy`, `Convergence.lean`) with a NUMERIC
per-edge constant κ — so the whole spine closes end-to-end on the gadget's actual
(transcendental) Gibbs measure with NO measured input.

THE KEY SIMPLIFICATION (found doing the math, replacing the anticipated
rational-lower-bounding of `exp(−βE)` entries): for a heat-bath / Barker acceptance
`π t / (π s + π t)` with a uniform full-support proposal, the transcendental factors CANCEL
in the per-edge ratio that `gen_poincare` needs:

    P s t / π t = 1 / (2n·(π s + π t)) ≥ 1 / (2n)        (since π s + π t ≤ 1),

an EXACT rational bound, uniform in β and in the energy. No transcendental arithmetic ever
enters the proof. For the 8-state gadget: κ = 1/16, hence geometric decay at rate
`(1 − 1/16)² = (15/16)²` per step.

WHAT IS PROVED (machine-checked, for any finite S then instantiated at the gadget):
  • `hbP` — the lazy uniform-proposal heat-bath kernel for a target law π: propose one of
    the `n` states uniformly, accept with the Barker ratio, all scaled by laziness 1/2
    (the diagonal absorbs the rest of the row).
  • `hbP_row`, `hbP_db`, `hbP_nonneg` — row-stochastic, reversible w.r.t. π, nonnegative.
  • `hbP_lazy` — PSD (`⟨Ph,h⟩_π ≥ 0`): via the Dirichlet identity, laziness reduces to the
    off-diagonal row mass being ≤ 1/2, which the 1/2 scaling guarantees.
  • `hbP_min_edge` — the per-edge ratio `(1/(2n))·π t ≤ P s t` (the κ above).
  • `hbP_geometric_decay` — for ANY strictly positive probability π on ANY finite S:
    `‖Pⁿf‖²_π ≤ ((1 − 1/(2n))²)ⁿ·‖f‖²_π` on the mean-zero subspace. γ = 1/(2n) COMPUTED.
  • `andGadget_gibbs_geometric_decay` — the instance at the LITERAL AND-gadget Gibbs law
    `π_β ∝ exp(−β·E4/4)` (the machine-checked energy from `fv-lean/AndGadget.lean`,
    mirrored below — separate Lake package, keep in sync), 8 states, ANY β:
    `‖Pⁿf‖²_π ≤ ((15/16)²)ⁿ·‖f‖²_π`. Fully discharged: π > 0 and ∑π = 1 are proven from
    `Real.exp_pos`, not assumed. No measured number anywhere in the chain.

HONEST SCOPE (integrity rules): the kernel proved here is the *uniform-proposal* (full
support) heat-bath sampler for the gadget's Gibbs law — the same Barker acceptance
`1/(1+exp(βΔE)) = π t/(π s+π t)` as the measured chain, but proposing any state rather than
single-spin flips. The measured γ = 0.0397 (`fv_sampler_convergence.py`) is for the
single-spin-flip CONTINUOUS-TIME generator and STAYS A MEASUREMENT; the single-flip kernel
has zero entries between non-neighbours, so a per-edge bound cannot see it — its Lean gap
would need the canonical-paths comparison method (open, harder). What this file removes is
the "no concrete multi-state Gibbs chain has a machine-checked gap" hole: this one does,
on the literal gadget energy and its literal transcendental Gibbs measure.
-/
import Convergence
import Mathlib.Analysis.SpecialFunctions.Exp

open Finset

namespace GibbsGadget

open GibbsMultiState SutraConvergence

variable {S : Type*} [Fintype S]

/-! ### The lazy uniform-proposal heat-bath (Barker) kernel, generically -/

/-- Heat-bath jump weight from `s` to `t`: uniform proposal (`1/n`) × Barker acceptance
    (`π t/(π s + π t)`) × laziness (`1/2`). `noncomputable` (real division). -/
noncomputable def hbWeight (π : S → ℝ) (s t : S) : ℝ :=
  π t / (2 * (Fintype.card S : ℝ) * (π s + π t))

/-- The lazy uniform-proposal heat-bath kernel: off-diagonal entries are `hbWeight`; the
    diagonal absorbs the remaining row mass (so rows sum to 1 by construction). -/
noncomputable def hbP [DecidableEq S] (π : S → ℝ) : S → S → ℝ :=
  fun s t => (if s = t then 1 - ∑ u, hbWeight π s u else 0) + hbWeight π s t

/-- The π-weighted jump weight is symmetric — the detailed-balance kernel identity.
    Pure algebra (denominators agree after `add_comm`); no positivity needed. -/
theorem hbWeight_symm (π : S → ℝ) (s t : S) :
    π s * hbWeight π s t = π t * hbWeight π t s := by
  unfold hbWeight
  rw [add_comm (π t) (π s)]
  ring

/-- Rows of `hbP` sum to 1, by construction (the diagonal absorbs `1 − ∑ w`). -/
theorem hbP_row [DecidableEq S] (π : S → ℝ) (s : S) : ∑ t, hbP π s t = 1 := by
  unfold hbP
  rw [Finset.sum_add_distrib, Finset.sum_ite_eq, if_pos (Finset.mem_univ s)]
  ring

/-- `hbP` is reversible w.r.t. π (detailed balance), for ANY π: off-diagonal by
    `hbWeight_symm`, diagonal trivially. -/
theorem hbP_db [DecidableEq S] (π : S → ℝ) : DetailedBalance π (hbP π) := by
  intro s t
  unfold hbP
  by_cases hst : s = t
  · rw [hst]
  · rw [if_neg hst, if_neg (fun h => hst h.symm), zero_add, zero_add]
    exact hbWeight_symm π s t

/-- The jump weight is nonnegative for positive π. -/
theorem hbWeight_nonneg (π : S → ℝ) (hπ : ∀ s, 0 < π s) (s t : S) :
    0 ≤ hbWeight π s t := by
  have hs := hπ s
  have ht := hπ t
  have hc : (0 : ℝ) ≤ (Fintype.card S : ℝ) := Nat.cast_nonneg _
  unfold hbWeight
  apply div_nonneg (le_of_lt ht)
  nlinarith [mul_nonneg hc (by linarith : (0:ℝ) ≤ π s + π t)]

/-- Each jump weight is at most `1/(2n)` (the acceptance ratio is ≤ 1). -/
theorem hbWeight_le [Nonempty S] (π : S → ℝ) (hπ : ∀ s, 0 < π s) (s t : S) :
    hbWeight π s t ≤ 1 / (2 * (Fintype.card S : ℝ)) := by
  have hn : (0 : ℝ) < (Fintype.card S : ℝ) := by exact_mod_cast Fintype.card_pos
  have hs := hπ s
  have ht := hπ t
  have hne1 : (2 * (Fintype.card S : ℝ)) ≠ 0 := ne_of_gt (by linarith)
  have hne2 : (π s + π t) ≠ 0 := ne_of_gt (by linarith)
  unfold hbWeight
  -- `1/(2n) − π t/(2n(π s+π t)) = π s/(2n(π s+π t)) ≥ 0`.
  have key : 1 / (2 * (Fintype.card S : ℝ))
           - π t / (2 * (Fintype.card S : ℝ) * (π s + π t))
           = π s / (2 * (Fintype.card S : ℝ) * (π s + π t)) := by
    field_simp
    try ring
  have hge : 0 ≤ π s / (2 * (Fintype.card S : ℝ) * (π s + π t)) :=
    div_nonneg (le_of_lt hs) (by nlinarith)
  linarith [key, hge]

/-- The total jump mass out of any state is at most `1/2` (n terms, each ≤ `1/(2n)`) —
    the laziness margin. -/
theorem hbWeight_sum_le [Nonempty S] (π : S → ℝ) (hπ : ∀ s, 0 < π s) (s : S) :
    ∑ u, hbWeight π s u ≤ 1 / 2 := by
  have hn : (0 : ℝ) < (Fintype.card S : ℝ) := by exact_mod_cast Fintype.card_pos
  calc ∑ u, hbWeight π s u
      ≤ ∑ _u : S, 1 / (2 * (Fintype.card S : ℝ)) :=
        Finset.sum_le_sum (fun u _ => hbWeight_le π hπ s u)
    _ = (Fintype.card S : ℝ) * (1 / (2 * (Fintype.card S : ℝ))) := by
        rw [Finset.sum_const, Finset.card_univ, nsmul_eq_mul]
    _ = 1 / 2 := by
        rw [mul_one_div, mul_comm (2 : ℝ) (Fintype.card S : ℝ), div_mul_eq_div_div,
            div_self (ne_of_gt hn)]

/-- `hbP` is a genuine (nonnegative) transition kernel: the laziness margin keeps the
    diagonal nonnegative. -/
theorem hbP_nonneg [DecidableEq S] [Nonempty S] (π : S → ℝ) (hπ : ∀ s, 0 < π s) (s t : S) :
    0 ≤ hbP π s t := by
  unfold hbP
  by_cases hst : s = t
  · rw [if_pos hst]
    have h1 := hbWeight_sum_le π hπ s
    have h2 := hbWeight_nonneg π hπ s t
    linarith
  · rw [if_neg hst, zero_add]
    exact hbWeight_nonneg π hπ s t

/-- **Laziness (PSD): `⟨Ph,h⟩_π ≥ 0`.** Via the Dirichlet identity
    `⟨Ph,h⟩_π = ‖h‖²_π − E(h)`, this is `E(h) ≤ ‖h‖²_π`: the per-edge bound
    `(a−b)² ≤ 2a²+2b²`, the symmetry of the weighted edges, and the row-mass bound
    `∑_t w(s,t) ≤ 1/2` collapse the Dirichlet form below the norm. -/
theorem hbP_lazy [DecidableEq S] [Nonempty S] (π : S → ℝ) (hπ : ∀ s, 0 < π s) (h : S → ℝ) :
    0 ≤ innerPi π (applyP (hbP π) h) h := by
  rw [innerPi_rayleigh_eq_dirichlet π (hbP π) (hbP_row π) (hbP_db π) h]
  -- Reduce to `dirichlet ≤ normPiSq`.
  -- Step A: in the Dirichlet sum the kernel can be replaced by the weights
  -- (diagonal terms vanish on both sides).
  have hA : ∑ s, ∑ t, π s * hbP π s t * (h s - h t) ^ 2
          = ∑ s, ∑ t, π s * hbWeight π s t * (h s - h t) ^ 2 := by
    refine Finset.sum_congr rfl (fun s _ => Finset.sum_congr rfl (fun t _ => ?_))
    by_cases hst : s = t
    · subst hst; simp
    · unfold hbP; rw [if_neg hst, zero_add]
  -- Step B: per-edge bound `(a−b)² ≤ 2a² + 2b²`.
  have hB : ∑ s, ∑ t, π s * hbWeight π s t * (h s - h t) ^ 2
          ≤ ∑ s, ∑ t, π s * hbWeight π s t * (2 * h s ^ 2 + 2 * h t ^ 2) := by
    refine Finset.sum_le_sum (fun s _ => Finset.sum_le_sum (fun t _ => ?_))
    have hw := hbWeight_nonneg π hπ s t
    have hp := le_of_lt (hπ s)
    have hsq : (h s - h t) ^ 2 ≤ 2 * h s ^ 2 + 2 * h t ^ 2 := by
      nlinarith [sq_nonneg (h s + h t)]
    exact mul_le_mul_of_nonneg_left hsq (mul_nonneg hp hw)
  -- Split the bound into the two square pieces.
  have hsplit : ∑ s, ∑ t, π s * hbWeight π s t * (2 * h s ^ 2 + 2 * h t ^ 2)
      = 2 * (∑ s, ∑ t, π s * hbWeight π s t * h s ^ 2)
        + 2 * (∑ s, ∑ t, π s * hbWeight π s t * h t ^ 2) := by
    rw [Finset.mul_sum, Finset.mul_sum, ← Finset.sum_add_distrib]
    refine Finset.sum_congr rfl (fun s _ => ?_)
    rw [Finset.mul_sum, Finset.mul_sum, ← Finset.sum_add_distrib]
    exact Finset.sum_congr rfl (fun t _ => by ring)
  -- Step C: the `h t²` piece equals the `h s²` piece (weighted-edge symmetry + swap).
  have hswap : ∑ s, ∑ t, π s * hbWeight π s t * h t ^ 2
             = ∑ s, ∑ t, π s * hbWeight π s t * h s ^ 2 := by
    calc ∑ s, ∑ t, π s * hbWeight π s t * h t ^ 2
        = ∑ s, ∑ t, π t * hbWeight π t s * h t ^ 2 :=
          Finset.sum_congr rfl (fun s _ => Finset.sum_congr rfl (fun t _ => by
            rw [hbWeight_symm π s t]))
      _ = ∑ t, ∑ s, π t * hbWeight π t s * h t ^ 2 := Finset.sum_comm
  -- Step D: collapse the `h s²` piece onto the row masses and bound them by 1/2.
  have hD : ∑ s, ∑ t, π s * hbWeight π s t * h s ^ 2
          = ∑ s, π s * h s ^ 2 * ∑ t, hbWeight π s t := by
    refine Finset.sum_congr rfl (fun s _ => ?_)
    rw [Finset.mul_sum]
    exact Finset.sum_congr rfl (fun t _ => by ring)
  have hE : ∑ s, π s * h s ^ 2 * ∑ t, hbWeight π s t
          ≤ ∑ s, π s * h s ^ 2 * (1 / 2) := by
    refine Finset.sum_le_sum (fun s _ => ?_)
    have hm : 0 ≤ π s * h s ^ 2 := mul_nonneg (le_of_lt (hπ s)) (sq_nonneg _)
    exact mul_le_mul_of_nonneg_left (hbWeight_sum_le π hπ s) hm
  have hnorm : ∑ s, π s * h s ^ 2 * (1 / 2) = normPiSq π h * (1 / 2) := by
    unfold normPiSq innerPi
    rw [Finset.sum_mul]
    exact Finset.sum_congr rfl (fun s _ => by ring)
  -- Assemble: `E(h) = (ΣΣ)/2 ≤ ‖h‖²_π`.
  have hchain : ∑ s, ∑ t, π s * hbWeight π s t * (h s - h t) ^ 2 ≤ 2 * normPiSq π h := by
    calc ∑ s, ∑ t, π s * hbWeight π s t * (h s - h t) ^ 2
        ≤ ∑ s, ∑ t, π s * hbWeight π s t * (2 * h s ^ 2 + 2 * h t ^ 2) := hB
      _ = 4 * (∑ s, ∑ t, π s * hbWeight π s t * h s ^ 2) := by rw [hsplit, hswap]; ring
      _ = 4 * (∑ s, π s * h s ^ 2 * ∑ t, hbWeight π s t) := by rw [hD]
      _ ≤ 4 * (∑ s, π s * h s ^ 2 * (1 / 2)) := by linarith [hE]
      _ = 2 * normPiSq π h := by rw [hnorm]; ring
  have hdir : dirichlet π (hbP π) h ≤ normPiSq π h := by
    unfold dirichlet
    rw [hA]
    linarith [hchain]
  linarith [hdir]

/-- **The per-edge ratio — the transcendentals cancel.** For a strictly positive
    probability π, every off-diagonal entry obeys `(1/(2n))·π t ≤ P s t`: the ratio
    `P s t / π t = 1/(2n(π s + π t))` is at least `1/(2n)` because `π s + π t ≤ 1`.
    This is `gen_poincare`'s `hedge` with the EXACT rational `κ = 1/(2n)` — no bound on
    any `exp(−βE)` entry is ever needed. -/
theorem hbP_min_edge [DecidableEq S] [Nonempty S] (π : S → ℝ) (hπ : ∀ s, 0 < π s)
    (hprob : ∑ s, π s = 1)
    (s t : S) (hst : s ≠ t) :
    (1 / (2 * (Fintype.card S : ℝ))) * π t ≤ hbP π s t := by
  have hn : (0 : ℝ) < (Fintype.card S : ℝ) := by exact_mod_cast Fintype.card_pos
  have hs := hπ s
  have ht := hπ t
  -- `π s + π t ≤ 1`: the pair-sum is at most the full (probability) sum.
  have hpair : π s + π t ≤ 1 := by
    have hsum : ∑ u ∈ ({s, t} : Finset S), π u ≤ ∑ u, π u :=
      Finset.sum_le_sum_of_subset_of_nonneg (Finset.subset_univ _)
        (fun u _ _ => le_of_lt (hπ u))
    rw [Finset.sum_pair hst] at hsum
    linarith [hsum, le_of_eq hprob]
  have hne1 : (2 * (Fintype.card S : ℝ)) ≠ 0 := ne_of_gt (by linarith)
  have hne2 : (π s + π t) ≠ 0 := ne_of_gt (by linarith)
  unfold hbP hbWeight
  rw [if_neg hst, zero_add]
  -- `π t/(2n(π s+π t)) − (1/(2n))·π t = π t·(1−(π s+π t))/(2n(π s+π t)) ≥ 0`.
  have key : π t / (2 * (Fintype.card S : ℝ) * (π s + π t))
           - 1 / (2 * (Fintype.card S : ℝ)) * π t
           = π t * (1 - (π s + π t)) / (2 * (Fintype.card S : ℝ) * (π s + π t)) := by
    field_simp
    try ring
  have hge : 0 ≤ π t * (1 - (π s + π t)) / (2 * (Fintype.card S : ℝ) * (π s + π t)) :=
    div_nonneg (mul_nonneg (le_of_lt ht) (by linarith)) (by nlinarith)
  linarith [key, hge]

/-- **The heat-bath chain for ANY positive probability target decays geometrically —
    γ = 1/(2n) COMPUTED.** The whole conductance engine assembled: per-edge ratio
    (`hbP_min_edge`) ⇒ Poincaré constant `κ = 1/(2n)` (`gen_poincare`) ⇒ with laziness
    (`hbP_lazy`) the Rayleigh gap ⇒ one-step contraction ⇒
    `‖Pⁿf‖²_π ≤ ((1 − 1/(2n))²)ⁿ·‖f‖²_π` on the mean-zero subspace
    (`geometric_decay_of_poincare_lazy`). No spectral theorem, no measured input. -/
theorem hbP_geometric_decay [DecidableEq S] [Nonempty S] (π : S → ℝ)
    (hπ : ∀ s, 0 < π s) (hprob : ∑ s, π s = 1)
    (f : S → ℝ) (hf0 : piMean π f = 0) (n : ℕ) :
    normPiSq π (iterP (hbP π) n f)
      ≤ ((1 - 1 / (2 * (Fintype.card S : ℝ))) ^ 2) ^ n * normPiSq π f := by
  have hn : (0 : ℝ) < (Fintype.card S : ℝ) := by exact_mod_cast Fintype.card_pos
  have hπ0 : ∀ s, 0 ≤ π s := fun s => le_of_lt (hπ s)
  have hκ0 : (0 : ℝ) ≤ 1 / (2 * (Fintype.card S : ℝ)) := by
    apply div_nonneg (by norm_num)
    linarith
  have hcard1 : (1 : ℝ) ≤ (Fintype.card S : ℝ) := by
    have h1 : 1 ≤ Fintype.card S := Fintype.card_pos
    exact_mod_cast h1
  have hκ1 : 1 / (2 * (Fintype.card S : ℝ)) ≤ 1 := by
    rw [div_le_one (by linarith)]
    linarith
  exact geometric_decay_of_poincare_lazy π (hbP π) (1 / (2 * (Fintype.card S : ℝ)))
    hπ0 hκ0 hκ1 (hbP_row π) (hbP_db π) (fun h => hbP_lazy π hπ h)
    (fun g hg => gen_poincare π (hbP π) (1 / (2 * (Fintype.card S : ℝ))) hπ0 hprob
      (fun s t hst => hbP_min_edge π hπ hprob s t hst) g hg)
    f hf0 n

#print axioms hbWeight_symm
#print axioms hbP_row
#print axioms hbP_db
#print axioms hbP_nonneg
#print axioms hbP_lazy
#print axioms hbP_min_edge
#print axioms hbP_geometric_decay

/-! ### The concrete instance: the 8-state AND-gadget Gibbs chain

The spin space, the machine-checked gadget energy, and its Gibbs law at inverse
temperature β. `E4` mirrors `fv-lean/AndGadget.lean` (a separate no-mathlib Lake package,
so it cannot be imported here — keep the two definitions in sync; the core file proves
`z = a AND b` is `E4`'s strict global minimum). -/

/-- The AND-gadget state: `(a, b, z)` as Booleans — 8 configurations. -/
abbrev AndState := Bool × Bool × Bool

/-- Spin encoding, `true ↦ +1`, `false ↦ −1` (mirrors `AndGadget.lean`). -/
def sp : Bool → ℤ
  | true  => 1
  | false => -1

/-- The AND-gadget energy ×4 (mirrors `AndGadget.lean`, where `andOut` is proven its
    strict global minimizer): `4E = −A − B + 2Z + AB − 2AZ − 2BZ`. -/
def E4 (s : AndState) : ℤ :=
  -sp s.1 - sp s.2.1 + 2 * sp s.2.2 + sp s.1 * sp s.2.1
    - 2 * sp s.1 * sp s.2.2 - 2 * sp s.2.1 * sp s.2.2

/-- The Gibbs law of the AND gadget at inverse temperature β (physical energy `E4/4`,
    matching the measured chain's convention). Transcendental entries — and the theorem
    below never needs to bound them. -/
noncomputable def gibbsPi (β : ℝ) : AndState → ℝ :=
  fun s => Real.exp (-(β * ((E4 s : ℝ) / 4)))
    / ∑ u, Real.exp (-(β * ((E4 u : ℝ) / 4)))

theorem gibbsPi_pos (β : ℝ) : ∀ s, 0 < gibbsPi β s := by
  intro s
  exact div_pos (Real.exp_pos _)
    (Finset.sum_pos (fun u _ => Real.exp_pos _) Finset.univ_nonempty)

theorem gibbsPi_prob (β : ℝ) : ∑ s, gibbsPi β s = 1 := by
  have hZ : (0 : ℝ) < ∑ u, Real.exp (-(β * ((E4 u : ℝ) / 4))) :=
    Finset.sum_pos (fun u _ => Real.exp_pos _) Finset.univ_nonempty
  unfold gibbsPi
  calc ∑ s, Real.exp (-(β * ((E4 s : ℝ) / 4))) / ∑ u, Real.exp (-(β * ((E4 u : ℝ) / 4)))
      = ∑ s, Real.exp (-(β * ((E4 s : ℝ) / 4)))
          * (∑ u, Real.exp (-(β * ((E4 u : ℝ) / 4))))⁻¹ :=
        Finset.sum_congr rfl (fun s _ => div_eq_mul_inv _ _)
    _ = (∑ s, Real.exp (-(β * ((E4 s : ℝ) / 4))))
          * (∑ u, Real.exp (-(β * ((E4 u : ℝ) / 4))))⁻¹ := by rw [← Finset.sum_mul]
    _ = 1 := mul_inv_cancel₀ (ne_of_gt hZ)

/-- **The concrete 8-state AND-gadget Gibbs chain decays geometrically — γ = 1/16
    COMPUTED, for every β, with no measured input.** The lazy uniform-proposal heat-bath
    sampler targeting the gadget's literal Gibbs law contracts the mean-zero deviation
    energy by `(15/16)²` per step: the per-edge κ is `1/(2·8) = 1/16` because the
    `exp(−βE4/4)` factors cancel in the ratio `P s t/π t`. (The measured single-flip
    continuous-time γ = 0.0397 remains a measurement — see the header.) -/
theorem andGadget_gibbs_geometric_decay (β : ℝ) (f : AndState → ℝ)
    (hf0 : piMean (gibbsPi β) f = 0) (n : ℕ) :
    normPiSq (gibbsPi β) (iterP (hbP (gibbsPi β)) n f)
      ≤ ((15 / 16 : ℝ) ^ 2) ^ n * normPiSq (gibbsPi β) f := by
  have h := hbP_geometric_decay (gibbsPi β) (gibbsPi_pos β) (gibbsPi_prob β) f hf0 n
  have hcard : Fintype.card AndState = 8 := by decide
  rw [show (1 : ℝ) - 1 / (2 * (Fintype.card AndState : ℝ)) = 15 / 16 by
    rw [hcard]; norm_num] at h
  exact h

#print axioms gibbsPi_pos
#print axioms gibbsPi_prob
#print axioms andGadget_gibbs_geometric_decay

end GibbsGadget
