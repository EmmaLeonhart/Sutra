/-
Sutra -> thrml, FV-in-Lean: the AND-gadget ground-state property (machine-checked).

The derived AND Ising gadget (used by the experiments + the codegen): biases
a:+1/4 b:+1/4 z:-1/2, couplings ab:-1/4 az:+1/2 bz:+1/2. It was MEASURED to compute
z = a AND b at 100% (approach A2) and re-LEARNED by training (approach C). Here we
PROVE what those only measured: z = a AND b is the STRICT global minimum of the
gadget energy -- so a ground-state / min-energy decode is exactly correct.

Spins as Bool (true = +1, false = -1). Energy x4 to integers:
  4*E(a,b,z) = -A - B + 2Z + A*B - 2*A*Z - 2*B*Z,   A,B,Z in {-1,+1}.
8 configs; closed by `omega` after case-splitting (NOT `decide`: it gets stuck on
Int in the kernel).
-/

set_option linter.unusedSimpArgs false

def sp : Bool → Int
  | true  => 1
  | false => -1

def andOut (a b : Bool) : Bool := a && b

def E4 (a b z : Bool) : Int :=
  -sp a - sp b + 2 * sp z + sp a * sp b - 2 * sp a * sp z - 2 * sp b * sp z

/-- `a AND b` attains the minimum energy for every input. -/
theorem and_gadget_min : ∀ a b z : Bool, E4 a b (andOut a b) ≤ E4 a b z := by
  intro a b z
  cases a <;> cases b <;> cases z <;> simp only [E4, andOut, sp, Bool.and_self,
    Bool.and_true, Bool.and_false, Bool.true_and, Bool.false_and] <;> omega

/-- Any WRONG output has strictly higher energy -> the minimiser is unique. -/
theorem and_gadget_strict : ∀ a b z : Bool,
    z ≠ andOut a b → E4 a b (andOut a b) < E4 a b z := by
  intro a b z h
  cases a <;> cases b <;> cases z <;> simp_all only [E4, andOut, sp,
    Bool.and_self, Bool.and_true, Bool.and_false, ne_eq, reduceCtorEq,
    not_true_eq_false, not_false_eq_true] <;> omega

#print axioms and_gadget_min
#print axioms and_gadget_strict
