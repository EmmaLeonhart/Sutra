# fv-lean — formal verification of the thrml gadgets in Lean

Machine-checked proofs of the **ground-state** claims the Sutra → thrml
exploration only *measured* (queue.md FV item, Emma 2026-06-14: "verify the thrml
gadgets in Lean"). Each proof shows the arithmetically-correct output of an
energy-based gadget is the **strict global minimum** of its energy — i.e. a
ground-state / min-energy decode is provably exact, not just empirically ~1.0.

## Proven

- `AndGadget.lean` — the derived AND Ising gadget (biases a:+¼ b:+¼ z:−½,
  couplings ab:−¼ az:+½ bz:+½). `and_gadget_min`: `a AND b` attains the minimum
  energy for every input; `and_gadget_strict`: every wrong output is strictly
  higher → the minimiser is unique. Both depend only on `[propext, Quot.sound]`
  (no `sorry`). This is the gadget measured at 100% (A2) and re-learned by
  training (C); now it is formally correct.

## Check it

```bash
# needs lean4 (via elan); no mathlib (core `omega` only)
lean fv-lean/AndGadget.lean        # exit 0, prints the axiom dependencies
```

`scripts/check_fv_lean.sh` runs every `.lean` here. NOTE: Lean is **not yet in
CI** (toolchain install is heavy); these are verified locally. Next: the
3-/4-body XOR/parity and the adder-carry / full-adder ground-state proofs.
