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

/-! ## A real composed circuit: a 3-input AND from two AND gadgets

`z = (a ∧ b) ∧ c` is two 2-input AND gadgets wired on a shared intermediate spin `w`:
gadget 1 computes `w = a ∧ b`, gadget 2 computes `z = w ∧ c`. The circuit energy is the
sum of the two AND-gadget energies (the same `andE` the `AndGadget.lean` proof uses,
×4-to-integers). We prove the arithmetically-correct output `(w, z) = (a∧b, a∧b∧c)` is
the **strict global energy minimum** — for every input `(a, b, c)` — and we get it from
the general lemma above applied to the two gadget energies, NOT by re-proving the whole
two-gate circuit monolithically. This is the methodology of §7 worked on a circuit
larger than a single gadget. -/

/-- Spin value of a bool. -/
def sp : Bool → Int | true => 1 | false => -1

/-- The AND-gadget energy ×4 (matching `AndGadget.lean`): minimized iff `out = x ∧ y`. -/
def andE (x y out : Bool) : Int :=
  -sp x - sp y + 2 * sp out + sp x * sp y - 2 * sp x * sp out - 2 * sp y * sp out

-- The AND gadget's minimum energy is NOT a constant 0 (it varies with `x,y`), so naive
-- gadget-energy summation does not compose — gadgets must be **proper penalties**:
-- shifted so the value is 0 at the satisfied assignment and > 0 otherwise. We use the
-- gadget's strict minimum to do the shift.
theorem andE_min (x y out : Bool) : andE x y (x && y) ≤ andE x y out := by
  cases x <;> cases y <;> cases out <;> simp [andE, sp]
theorem andE_strict (x y out : Bool) (h : out ≠ (x && y)) :
    andE x y (x && y) < andE x y out := by
  cases x <;> cases y <;> cases out <;> simp_all [andE, sp]

/-- Circuit state: the two free spins `(w, z)` (inputs `a b c` are parameters/clamped). -/
abbrev Wire := Bool × Bool
/-- Gadget 1 as a PROPER PENALTY of the free state: `andE a b w` shifted to 0 at `w = a∧b`,
    `> 0` otherwise (≥ 0 everywhere). -/
def g1 (a b : Bool) : Wire → Int := fun s => andE a b s.1 - andE a b (a && b)
/-- Gadget 2 as a proper penalty: `andE w c z` shifted to 0 at `z = w∧c`, `> 0` otherwise. -/
def g2 (c : Bool) : Wire → Int := fun s => andE s.1 c s.2 - andE s.1 c (s.1 && c)

/-- The 3-input AND circuit's correct output is the STRICT global energy minimum, for
    every input — discharged from the two gadget penalties via `strict_global_min_of_terms`,
    NOT by re-proving the two-gate circuit monolithically. -/
theorem and3_circuit_strict_min (a b c : Bool) :
    ∀ s : Wire, s ≠ (a && b, (a && b) && c) →
      sumAt [g1 a b, g2 c] (a && b, (a && b) && c) < sumAt [g1 a b, g2 c] s := by
  refine strict_global_min_of_terms [g1 a b, g2 c] (a && b, (a && b) && c) ?_ ?_
  · -- hmin: each penalty is 0 at the correct joint assignment and ≥ 0 everywhere.
    intro t ht s
    simp only [List.mem_cons, List.not_mem_nil, or_false] at ht
    rcases ht with rfl | rfl
    · show andE a b (a && b) - andE a b (a && b) ≤ andE a b s.1 - andE a b (a && b)
      have := andE_min a b s.1; omega
    · show andE (a && b) c ((a && b) && c) - andE (a && b) c ((a && b) && c)
          ≤ andE s.1 c s.2 - andE s.1 c (s.1 && c)
      have := andE_min s.1 c s.2; omega
  · -- hstrict: any wrong joint assignment makes penalty 1 or penalty 2 strictly positive.
    intro s hs
    by_cases hw : s.1 = (a && b)
    · -- wire correct ⇒ the output spin is wrong ⇒ gadget 2's penalty is strict.
      have hz : s.2 ≠ ((a && b) && c) := fun hz => hs (by cases s; simp_all)
      have hz' : s.2 ≠ (s.1 && c) := by rw [hw]; exact hz
      have hstr := andE_strict s.1 c s.2 hz'
      refine ⟨g2 c, List.mem_cons_of_mem _ (List.mem_cons_self ..), ?_⟩
      show andE (a && b) c ((a && b) && c) - andE (a && b) c ((a && b) && c)
          < andE s.1 c s.2 - andE s.1 c (s.1 && c)
      omega
    · -- wire wrong ⇒ gadget 1's penalty is strict.
      have hstr := andE_strict a b s.1 hw
      refine ⟨g1 a b, List.mem_cons_self .., ?_⟩
      show andE a b (a && b) - andE a b (a && b) < andE a b s.1 - andE a b (a && b)
      omega

/-! ## A heterogeneous composed circuit: a half-adder (XOR sum + AND carry)

`and3_circuit_strict_min` composes two AND gadgets (one gadget *type*, wired in series).
This instance instead composes **two different gadget types** over a shared input
register: a half-adder on inputs `(a, b)` emits `sum = a XOR b` (the XOR gadget,
sign-pinned to XOR not the XNOR bug) and `carry = a ∧ b` (the AND gadget). The circuit
energy is the sum of the XOR-gadget and AND-gadget penalties; the correct output
`(a XOR b, a ∧ b)` is the strict global energy minimum for every input — discharged from
the two heterogeneous gadget penalties via the same `strict_global_min_of_terms`, showing
the composition lemma is gadget-type-agnostic. (XOR-gadget energy reproduced inline:
these files are checked standalone with no cross-imports.) -/

/-- The XOR/parity gadget energy: product of spins, minimised iff `z = a XOR b`. -/
def exorE (a b z : Bool) : Int := sp a * sp b * sp z

theorem exorE_min (a b z : Bool) : exorE a b (xor a b) ≤ exorE a b z := by
  cases a <;> cases b <;> cases z <;> simp only [exorE, sp, Bool.xor_self, Bool.xor_true,
    Bool.xor_false, Bool.true_xor, Bool.false_xor, Bool.not_true, Bool.not_false] <;> omega
theorem exorE_strict (a b z : Bool) (h : z ≠ xor a b) :
    exorE a b (xor a b) < exorE a b z := by
  cases a <;> cases b <;> cases z <;>
    first
      | exact absurd rfl h
      | (simp only [exorE, sp, Bool.xor_self, Bool.xor_true, Bool.xor_false,
          Bool.true_xor, Bool.false_xor, Bool.not_true, Bool.not_false]; omega)

/-- Half-adder sum penalty: XOR gadget shifted to 0 at `sum = a XOR b`, `> 0` otherwise. -/
def hSum (a b : Bool) : Wire → Int := fun s => exorE a b s.1 - exorE a b (xor a b)
/-- Half-adder carry penalty: AND gadget shifted to 0 at `carry = a ∧ b`, `> 0` otherwise. -/
def hCarry (a b : Bool) : Wire → Int := fun s => andE a b s.2 - andE a b (a && b)

/-- The half-adder's correct output `(a XOR b, a ∧ b)` is the STRICT global energy
    minimum for every input — composed from a XOR gadget and an AND gadget (different
    types) via the general lemma, not re-proved monolithically. -/
theorem half_adder_strict_min (a b : Bool) :
    ∀ s : Wire, s ≠ (xor a b, a && b) →
      sumAt [hSum a b, hCarry a b] (xor a b, a && b) < sumAt [hSum a b, hCarry a b] s := by
  refine strict_global_min_of_terms [hSum a b, hCarry a b] (xor a b, a && b) ?_ ?_
  · -- hmin: each penalty is 0 at the correct output and ≥ 0 everywhere.
    intro t ht s
    simp only [List.mem_cons, List.not_mem_nil, or_false] at ht
    rcases ht with rfl | rfl
    · show exorE a b (xor a b) - exorE a b (xor a b) ≤ exorE a b s.1 - exorE a b (xor a b)
      have := exorE_min a b s.1; omega
    · show andE a b (a && b) - andE a b (a && b) ≤ andE a b s.2 - andE a b (a && b)
      have := andE_min a b s.2; omega
  · -- hstrict: a wrong sum makes the XOR penalty strict; a wrong carry, the AND penalty.
    intro s hs
    by_cases hsum : s.1 = xor a b
    · have hc : s.2 ≠ (a && b) := fun hc => hs (by cases s; simp_all)
      have hstr := andE_strict a b s.2 hc
      refine ⟨hCarry a b, List.mem_cons_of_mem _ (List.mem_cons_self ..), ?_⟩
      show andE a b (a && b) - andE a b (a && b) < andE a b s.2 - andE a b (a && b)
      omega
    · have hstr := exorE_strict a b s.1 hsum
      refine ⟨hSum a b, List.mem_cons_self .., ?_⟩
      show exorE a b (xor a b) - exorE a b (xor a b) < exorE a b s.1 - exorE a b (xor a b)
      omega

#print axioms strict_global_min_of_terms
#print axioms two_term_circuit_strict_min
#print axioms and3_circuit_strict_min
#print axioms half_adder_strict_min
