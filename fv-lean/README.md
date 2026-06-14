# fv-lean — formal verification of the thrml gadgets in Lean

Machine-checked proofs of the **ground-state** claims the Sutra → thrml
exploration only *measured* (queue.md FV item, Emma 2026-06-14: "verify the thrml
gadgets in Lean"). Each proof shows the arithmetically-correct output of an
energy-based gadget is the **strict global minimum** of its energy — i.e. a
ground-state / min-energy decode is provably exact, not just empirically ~1.0.

## Proven (each: `_min` = correct output attains the energy minimum; `_strict` =
every wrong output strictly higher → unique minimiser; no `sorry`)

- `AndGadget.lean` — the derived AND Ising gadget (biases a:+¼ b:+¼ z:−½,
  couplings ab:−¼ az:+½ bz:+½). The gadget measured at 100% (A2) and re-learned
  by training (C), now formally correct.
- `XorGadget.lean` — the 3-body XOR/parity gadget `E = σx·σy·σz` (negative factor
  weight). Pins the **correct sign** — the one whose sign bug (positive → silently
  XNOR) was found + fixed 2026-06-14; the proof rules out that bug.
- `FullAdder.lean` — the 1-bit full adder (sum = `a⊕b⊕cin` via the 4-body parity
  factor, carry = `MAJ(a,b,cin)` via the pairwise factor). Proves the correct
  (sum, carry) is the strict global minimum for all 8 inputs → **addition's
  ground-state decode is exactly correct.** The 2×2 multiplier is these gates
  (AND + XOR) composed, so its correctness follows from the gate proofs.

## Check it

```bash
# needs lean4 (via elan); no mathlib (core `omega` only)
lean fv-lean/AndGadget.lean        # exit 0, prints the axiom dependencies
```

`scripts/check_fv_lean.sh` runs every `.lean` here. NOTE: Lean is **not yet in
CI** (toolchain install is heavy); these are verified locally. Next: the
3-/4-body XOR/parity and the adder-carry / full-adder ground-state proofs.
