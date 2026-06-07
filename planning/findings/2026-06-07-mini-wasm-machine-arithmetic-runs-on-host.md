# mini_wasm_machine: ADD/SUB/MUL run on the HOST, not the substrate (substrate-purity breach)

**Date:** 2026-06-07
**Severity:** integrity — contradicts a published claim (percepta-ntm paper §5)
and the CLAUDE.md "no scalar arithmetic inside an operation" rule.

## What I found

While preparing to add DIV/REM opcodes I probed the substrate semantics and
discovered the mini_wasm_machine
(`experiments/iso5_substrate_dispatch/mini_wasm_machine.su`) computes its
per-opcode arithmetic on the **host**, not the substrate.

Measured (runtime_dim=2, the test config):

- `ramRead(addr).real()` returns a **Python float**, not a tensor.
- `top1 = ramRead(99+sp).real(); top2 = ramRead(98+sp).real(); v_add = top2 +
  top1` → `v_add` is a **host float** (probe: 3+4 → `float 7.0`). Same for
  `v_sub`, `v_mul`, and the comparison operand tests (`top2 == top1`,
  `top2 < top1` compare host floats).
- The dispatch flags (`is_add = truth_axis(defuzzy(op == 2))`) and the final
  blended writes ARE substrate tensors (probe: blend → `tensor(7., cuda:0)`):
  `defuzzy` re-grounds the host comparison onto the substrate, and the
  `(1+is_add)*v_add + ...` blend lifts the host float back to a tensor.

## What that means

This is the forbidden pattern from CLAUDE.md verbatim — "Reading v[AXIS_REAL],
doing scalar arithmetic, packing back into a vector." The machine's
**memory** (ramRead/ramWrite vector device), **dispatch/selection** (defuzzy +
blend), **bitwise** ops (`Bits.band/bor/bxor` on raw vectors), and **writes**
run on the substrate. But the **arithmetic values** (ADD/SUB/MUL) and the
comparison operand comparisons are computed on the host via `.real()` extraction,
then lifted back. The substrate carries the memory and the selection, not the
computation.

This makes the percepta-ntm paper §5 claim — "Measured on the substrate:
arithmetic (3+4=7, 100+23=123, chained 5×6−2=28)…" — an **overclaim**. The
selection of which opcode's result to keep, and the storage, are on the
substrate; the arithmetic itself is not. The 30/30 regression guard still passes
because host float arithmetic is correct — but "it ran and gave the right
number" is exactly the failure mode the integrity rules warn against (correct
output ≠ ran on the substrate).

## It is fixable (the bitwise ops already do it right)

Element-wise vector arithmetic IS substrate-pure and gives the right answer on
the real axis: for two `make_real` vectors, `a + b` and `a * b` (element-wise)
put the sum/product on AXIS_REAL and 0 elsewhere. The fix is to keep stack
values as VECTORS (don't `.real()` them), compute `v_add = top2_vec + top1_vec`,
`v_mul = top2_vec * top1_vec` as tensor ops, blend vectors, and `.real()` only
for the final monitoring/return — exactly how `Bits.band` already takes the raw
`ramRead` vectors. The `/` operator is the one caveat: vector/vector division
gives `0/0 = nan` on the non-real axes, so DIV needs a nan-safe real-axis divide
(a separate design question, which is what surfaced this).

## Status

STOPPED adding opcodes. Surfaced to Emma for the call: rework the machine to
vector arithmetic (fix), and/or re-scope the paper §5 claim. Did NOT silently
continue or silently amend the frozen-adjacent paper.
