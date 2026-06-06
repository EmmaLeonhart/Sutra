# Learned CPU operations on the analytic scaffold — findings (E1–E4)

The thesis: because `transformer-vm`'s analytic weights live in a standard
differentiable transformer, new CPU operations can be **learned by gradient** on the
frozen scaffold and **crystallized** to exact weights — the constructed+trained
hybrid. Result below; full design in `notes/experiment_learned_ops.md`.

## What learns to bit-exactness, and what doesn't

| Op | Kind | Output | Result |
|----|------|--------|--------|
| `i32.and` | bitwise | bits | ❌ **not learnable** from raw integers — plateaus ~23% |
| `sat_add_u` = min(a+b, 255) | arithmetic | value | ✅ **100.0000%** exact (0/65 536 wrong) |
| `sat_sub_u` = max(a−b, 0) | arithmetic | value | ✅ **100.0000%** exact |
| `min_u` = min(a, b) | arithmetic | value | ✅ **100.0000%** exact |
| `max_u` = max(a, b) | arithmetic | value | ✅ **100.0000%** exact |

All verified on all 65 536 byte pairs at hardmax (`tests/test_value_ops_exact.py`,
`tests/test_sat_add_checkpoint_exact.py`). Trainer: `src/learned_ops/train_and.py`
(value-output MLP, full-table, hard-example focusing, ~few hundred epochs each).

## The two laws this established

1. **Spectral bias decides learnability.** AND's low result bits are the
   *highest-frequency* functions of the integer inputs (`bit0(a&b) = [a odd]&[b odd]`,
   a period-2 square wave). MLPs are low-frequency-biased, so bit-exact AND from raw
   integers is unreachable by SGD — and `lower.py` confirms the architecture itself
   avoids runtime bitwise ops (only constant-mask lowering; no runtime bit
   decomposition). *Gradient-learning bit-exact arithmetic is exactly what's hard —
   which is why the paradigm constructs weights instead of training them.*
2. **Output representation must match the op's nature.** Arithmetic ops are
   *value-natured* and low-frequency (saturating add/sub, min, max are piecewise-
   linear — a few ReLUs). Output the **byte value** (regress + round), not 8
   thresholded bits (which re-imposes the LSB-parity wall on every op). The scaffold
   itself holds bytes as values — so **arithmetic ops are its natural learnable
   extensions; bitwise ops are not.** This is a concrete map of what this architecture
   can and cannot learn.

## Crystallization (learn → understand → re-compile)

`sat_add_u` was crystallized (`src/learned_ops/crystallize.py`) to its exact minimal
DSL form — `a + b − relu(a+b−255)`, a single ReGLU neuron — and verified to (a) be
100% exact and (b) **agree with the learned net on all 65 536 pairs**
(`tests/test_crystallize_sat_add.py`). So a new instruction discovered by gradient
becomes a permanent, deterministic, bit-exact construction. The same crystallization
applies to sat_sub (`a − b + relu(b−a)` ... = a − min(a,b) form), min, and max
(each one/two ReGLU/`select` primitives) — a follow-up if needed.

## Status

E1 (learn) ✅ · E2 (crystallize sat_add) ✅ · E4 (more ops + this note) ✅. The
genuinely-new instruction the user asked for — **saturating arithmetic** — is learned
and crystallized. Remaining: E3 (wire a learned op as a *native opcode* end-to-end
through the transformer) — a deeper build into the analytic construction; spec it
before implementing (hard rail: don't blind-hack the construction).
