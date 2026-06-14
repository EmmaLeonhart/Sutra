/-
Sutra -> thrml, FV-in-Lean: the full-adder ground-state (machine-checked).

The 1-bit full adder used by the ripple-carry adder (approach #4/A1). Given inputs
a,b,cin, the outputs are sum s = a XOR b XOR cin and carry cout = MAJ(a,b,cin).
Energy (spins sigma=2*bit-1):
  E = -sigma_a sigma_b sigma_cin sigma_s  -  sigma_cout (sigma_a + sigma_b + sigma_cin)
    (the 4-body parity factor for the sum + the pairwise carry/majority factor).
Claim: the correct (s, cout) is the STRICT global minimum over all (s, cout) for
every input -- i.e. addition's ground-state decode is exactly correct. 5 spins,
32 configs, closed by `omega` after case-splitting.
-/

set_option linter.unusedSimpArgs false

def sp : Bool → Int
  | true  => 1
  | false => -1

def sumOut  (a b cin : Bool) : Bool := xor (xor a b) cin
def carryOut (a b cin : Bool) : Bool := (a && b) || (a && cin) || (b && cin)

def Efa (a b cin s cout : Bool) : Int :=
  -(sp a * sp b * sp cin * sp s) - sp cout * (sp a + sp b + sp cin)

attribute [local simp] sp sumOut carryOut Efa
  Bool.xor_self Bool.xor_true Bool.xor_false Bool.true_xor Bool.false_xor
  Bool.and_self Bool.and_true Bool.and_false Bool.true_and Bool.false_and
  Bool.or_self Bool.or_true Bool.or_false Bool.true_or Bool.false_or
  Bool.not_true Bool.not_false

/-- The correct (sum, carry) attains the minimum energy for every input. -/
theorem fulladder_min : ∀ a b cin s cout : Bool,
    Efa a b cin (sumOut a b cin) (carryOut a b cin) ≤ Efa a b cin s cout := by
  intro a b cin s cout
  cases a <;> cases b <;> cases cin <;> cases s <;> cases cout <;> simp <;> omega

/-- Any WRONG (sum, carry) has strictly higher energy -> unique minimiser. -/
theorem fulladder_strict : ∀ a b cin s cout : Bool,
    (s, cout) ≠ (sumOut a b cin, carryOut a b cin) →
    Efa a b cin (sumOut a b cin) (carryOut a b cin) < Efa a b cin s cout := by
  intro a b cin s cout h
  cases a <;> cases b <;> cases cin <;> cases s <;> cases cout <;>
    first
      | exact absurd rfl h
      | (simp <;> omega)
      | simp

#print axioms fulladder_min
#print axioms fulladder_strict
