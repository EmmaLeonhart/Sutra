# Substrate strict `<` / `>` are ~0.5 at exact equality; gate with the clean `==`

**Date:** 2026-06-06
**Context:** ISO-5 WASM machine — adding comparison opcodes GT/GE/LE/NE to
`experiments/iso5_substrate_dispatch/mini_wasm_machine.su`.

## What happened

GT/GE/LE/NE were derived from the substrate truth values the machine already
used for EQ/LT:

```
v_gt = (defuzzy(top1 < top2) + 1) / 2     // top2 > top1
v_ge = 1 - v_lt
v_le = 1 - v_gt
v_ne = 1 - v_eq
```

The guard (`test_mini_wasm_machine.py`, RUN on the substrate, runtime_dim=2)
failed exactly two cases, both at **equality**:

- `7 >= 7` → got 0, expected 1
- `5 <= 5` → got 0, expected 1

Every strict case (`5>3=1`, `3>5=0`, `7!=8=1`, `7!=7=0`) passed.

## Measured cause

The substrate's strict less-than / greater-than (`defuzzy(a < b)`) returns a
truth value at the **boundary (~0)** when `a == b`, i.e. `v_lt ≈ 0.5` for equal
operands — not a clean 0. So `v_ge = 1 - v_lt ≈ 0.5`, which `round()`s to 0.
The exact-equality predicate `==` (`v_eq`) **is** clean {0,1} there: the EQ
opcode's `7==7 → 1` / `7==8 → 0` cases passed cleanly, and the loop/factorial
dispatch (which leans on `==`) is exact.

This is a specific instance of the general substrate dispatch behavior: equality
against a known value is sharp; strict ordering across the equality point is a
smooth crossing, so it is ambiguous *at* the crossing.

## Fix

Gate the strict comparisons by the clean `v_eq`, so equality is decided by `==`
and only the genuinely-strict region uses `<` / `>`:

```
v_lt = (1 - v_eq) * v_lt_raw     // 0 when equal (was ~0.5)
v_gt = (1 - v_eq) * v_gt_raw
v_ge = 1 - v_lt                  // 1 when equal (v_eq carries it)
v_le = 1 - v_gt
v_ne = 1 - v_eq
```

At equality `v_eq = 1` zeroes the ambiguous raw comparison; at strict
inequality `v_eq = 0` passes the (clean) raw comparison through. This also
hardens the existing LT/GT at the equality boundary (`5<5 = 0`, `5>5 = 0`),
which the original code left untested.

## Reusable takeaway

When building a substrate comparison that must be correct **at** the equality
point, do not rely on a strict `<` / `>` alone — derive `>=`, `<=` (and harden
`<`, `>`) by gating with the clean `==` truth. All purely-strict comparisons
(distinct operands) are fine as-is.
