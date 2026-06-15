/-
Sutra -> thrml, FV-in-Lean: the GENERAL gadget-composition lemma (machine-checked).

The per-gadget proofs (`AndGadget`, `XorGadget`, `FullAdder`) each show one gadget's
arithmetically-correct output is the STRICT global minimum of that gadget's energy. A
complete circuit is gadgets *wired together*, and on the energy-based target wiring is
**addition of energies**: the circuit energy is the sum of the gadget energies over the
shared spin register. This file proves, in general, that composition of the
strict-minimum proofs is a sum-of-minimized-terms argument:

  if every penalty term is minimized at a global state `s0` (`hmin`), and for every
  other state at least one term is STRICTLY larger at `s0` (`hstrict`), then the SUM of
  the terms is uniquely minimized at `s0`.

Consequence: a circuit assembled only from gadgets whose `_strict` theorems hold has its
correct output as the strict global energy minimum — machine-checked once, here, for any
number of gadgets, rather than re-proved monolithically per circuit. Core Lean only (no
mathlib): `List.sum` over the penalty terms, integer arithmetic closed by `omega`.
-/

set_option linter.unusedSimpArgs false

namespace Composition

/-- The total energy at state `s` of a circuit given as a list of penalty terms
    (each term is one gadget's energy as a function of the global state). -/
def sumAt {S : Type} (ts : List (S → Int)) (s : S) : Int :=
  (ts.map (fun t => t s)).sum

/-- If every term is `≤` at `s0` than at `s`, the total energy is `≤` at `s0`. -/
theorem sum_le {S : Type} (s0 s : S) :
    ∀ ts : List (S → Int), (∀ t ∈ ts, t s0 ≤ t s) → sumAt ts s0 ≤ sumAt ts s
  | [], _ => by simp [sumAt]
  | a :: rest, h => by
      have ha := h a (List.mem_cons_self ..)
      have hr := sum_le s0 s rest (fun u hu => h u (List.mem_cons_of_mem a hu))
      simp only [sumAt, List.map_cons, List.sum_cons] at hr ⊢
      omega

/-- If every term is `≤` at `s0` and at least ONE is strictly smaller at `s0`, the total
    energy is STRICTLY smaller at `s0`. The inductive core of composition. -/
theorem sum_lt {S : Type} (s0 s : S) :
    ∀ ts : List (S → Int),
      (∀ t ∈ ts, t s0 ≤ t s) → (∃ t ∈ ts, t s0 < t s) → sumAt ts s0 < sumAt ts s
  | [], _, hlt => by obtain ⟨t, ht, _⟩ := hlt; simp at ht
  | a :: rest, hle, hlt => by
      obtain ⟨t, ht, htlt⟩ := hlt
      have hr_le := sum_le s0 s rest (fun u hu => hle u (List.mem_cons_of_mem a hu))
      have ha := hle a (List.mem_cons_self ..)
      simp only [sumAt, List.map_cons, List.sum_cons] at hr_le ⊢
      rcases List.mem_cons.1 ht with rfl | htr
      · -- the strict witness is the head `a`: head strict, tail `≤`.
        omega
      · -- the strict witness is in `rest`: head `≤`, tail strict by recursion.
        have hr_lt := sum_lt s0 s rest
          (fun u hu => hle u (List.mem_cons_of_mem a hu)) ⟨t, htr, htlt⟩
        simp only [sumAt, List.map_cons, List.sum_cons] at hr_lt
        omega

/-- GENERAL gadget composition: if `s0` minimizes every penalty term, and every other
    state makes at least one term strictly larger than at `s0`, then `s0` is the STRICT
    global minimum of the circuit energy `sumAt ts`. A circuit of gadgets whose `_strict`
    theorems give exactly these two hypotheses therefore has its correct output as the
    strict global energy minimum — for any number of gadgets, with no monolithic re-proof. -/
theorem strict_global_min_of_terms {S : Type} (ts : List (S → Int)) (s0 : S)
    (hmin : ∀ t ∈ ts, ∀ s, t s0 ≤ t s)
    (hstrict : ∀ s, s ≠ s0 → ∃ t ∈ ts, t s0 < t s) :
    ∀ s, s ≠ s0 → sumAt ts s0 < sumAt ts s := by
  intro s hs
  exact sum_lt s0 s ts (fun t ht => hmin t ht s) (hstrict s hs)

/-! ## A concrete instantiation

Two penalty terms over a shared two-spin state, each strictly minimised at the same
joint assignment `(true, true)` — the shape of two wired gadgets that must agree on a
shared register. The general lemma discharges the composed strict minimum from the two
per-term strict minima, exactly as a real circuit's correctness is discharged from its
gadgets'. -/

abbrev St2 := Bool × Bool

/-- Penalty forcing the first spin true: 0 at `true`, 1 at `false`. -/
def p1 (s : St2) : Int := if s.1 then 0 else 1
/-- Penalty forcing the second spin true: 0 at `true`, 2 at `false`. -/
def p2 (s : St2) : Int := if s.2 then 0 else 2

theorem two_term_circuit_strict_min :
    ∀ s : St2, s ≠ (true, true) → sumAt [p1, p2] (true, true) < sumAt [p1, p2] s := by
  refine strict_global_min_of_terms [p1, p2] (true, true) ?_ ?_
  · intro t ht s
    simp only [List.mem_cons, List.not_mem_nil, or_false] at ht
    rcases ht with rfl | rfl
    · cases h : s.1 <;> simp [p1, h]
    · cases h : s.2 <;> simp [p2, h]
  · intro s hs
    -- s ≠ (true,true) ⇒ s.1 = false or s.2 = false ⇒ p1 or p2 is strictly larger.
    cases h1 : s.1
    · exact ⟨p1, List.mem_cons_self .., by simp [p1, h1]⟩
    · cases h2 : s.2
      · exact ⟨p2, List.mem_cons_of_mem _ (List.mem_cons_self ..), by simp [p2, h2]⟩
      · exact absurd (by cases s; simp_all) hs

#print axioms strict_global_min_of_terms
#print axioms two_term_circuit_strict_min

end Composition
