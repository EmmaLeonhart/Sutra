/-
Sutra -> thrml, FV-in-Lean: the XOR/parity gadget ground-state (machine-checked).

The 3-body XOR factor `z = x XOR y` (used in the multiplier's half-adders). For
spins sigma=2*bit-1, z=x^y corresponds to prod(sigma)=-1, i.e. NEGATIVE factor
weight -> energy E = sigma_x*sigma_y*sigma_z. (Getting this sign wrong silently
encodes XNOR -- the bug found+fixed 2026-06-14; this proof pins the correct sign.)
Claim: z = x XOR y is the STRICT global minimum of E.
-/

set_option linter.unusedSimpArgs false

def sp : Bool → Int
  | true  => 1
  | false => -1

def xorOut (a b : Bool) : Bool := xor a b

def Exor (a b z : Bool) : Int := sp a * sp b * sp z

/-- `x XOR y` attains the minimum energy for every input. -/
theorem xor_gadget_min : ∀ a b z : Bool, Exor a b (xorOut a b) ≤ Exor a b z := by
  intro a b z
  cases a <;> cases b <;> cases z <;> simp only [Exor, xorOut, sp, Bool.xor_self,
    Bool.xor_true, Bool.xor_false, Bool.true_xor, Bool.false_xor, Bool.not_true, Bool.not_false] <;> omega

/-- Any WRONG output has strictly higher energy -> the minimiser is unique. -/
theorem xor_gadget_strict : ∀ a b z : Bool,
    z ≠ xorOut a b → Exor a b (xorOut a b) < Exor a b z := by
  intro a b z h
  cases a <;> cases b <;> cases z <;>
    first
      | exact absurd rfl h
      | (simp only [Exor, xorOut, sp, Bool.xor_self, Bool.xor_true, Bool.xor_false,
          Bool.true_xor, Bool.false_xor, Bool.not_true, Bool.not_false]; omega)

#print axioms xor_gadget_min
#print axioms xor_gadget_strict
