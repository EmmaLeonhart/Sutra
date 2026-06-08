# Attention-on-RAM: evaluate vs learn the same linear regression over memory

**Date:** 2026-06-08
**Context:** NTM-archetype track step (e) — Emma's "do all of them so we can compare
them" (answer to O3). Brings the constructed and trained attention-on-RAM variants
together on ONE task and measures whether they realize the same operator.
Harness: `experiments/attention_on_ram/compare_variants.py` (guard
`test_reference.py::test_evaluate_and_learn_agree`).

## The comparison set

One attention head reading a RAM tape, four variants, on the axis Emma cares about —
**evaluate a given linear model vs. learn one from data**, both being "linear
regression over memory":

| variant | regime | what it computes | where it runs |
|---|---|---|---|
| `sum_tape` | evaluate (constructed) | q=ones → Σ tape | substrate (`attn_sum_tape`) |
| `dot_tape` | evaluate (constructed) | q=w → Σ wᵢxᵢ = ŷ=w·x | substrate (`attn_dot_tape`) |
| `select_field` | evaluate (constructed) | hardmax → tape[j] | substrate (`attn_select_field`) |
| soft linear read | **learn (SGD)** | fit w to (X, X·c); recover c | substrate read, host-fit |

The first three are the constructed parser (run on the Sutra substrate via the OCaml
fixtures, finding `2026-06-08-attention-on-ram-substrate.md`). The fourth is the
trainable soft read (`experiments/ntm_ram/trainable_read.py`).

## The apples-to-apples result (measured)

One coefficient vector `c = [2, -1, 0.5, 3]`, one set of 24 tapes `X`, targets
`y = X·c`.

- **Evaluate (constructed):** the head with query `q = c` computes `ŷ = c·x` —
  `max|ŷ − y| = 8.9e-16` (machine epsilon; exact).
- **Learn (SGD):** the differentiable soft read fits `w` from `(X, y)` —
  loss `12.68 → 2.3e-14`, `‖grad‖ = 7.45` at step 0 (gradients flow), recovered
  `w = [2.0, -1.0, 0.5, 3.0]`, `‖w − c‖ = 6.0e-8`. Evaluating with the *learned* `w`
  gives `max|ŷ − y| = 2.2e-7`.
- **Agreement:** `max|ŷ_evaluate − ŷ_learn| = 2.2e-7` — the constructed head (given
  `c`) and the trained head (recovering `c` from data) **converge to the same
  linear-regression-over-memory operator**.

All constructed parse tasks remain exact (10/10 oracle).

## Why this is the comparison Emma asked for

"Linear regression over memory" has two readings — evaluate a fixed model, or fit one
— and Emma's answer was "do all of them so we can compare them." This shows they are
the *same operator* reached two ways: hand-construction writes the coefficients into
the query; SGD recovers them from data. The constructed route is exact and runs on the
substrate; the learned route is differentiable and trains to the same answer. That is
the bridge the percepta-ntm paper §7 names ("a seed that SGD could grow"): the
first-step operator is both constructible and learnable, and the two agree.

## Scope / not claimed

The SGD fit is on the **smooth** read operator (the low-magnitude form §7 says training
operates on), NOT on the saturated 1e30 hardmax transformer weights — training the
composed reduced network end-to-end stays open. The fit is compile-time training (the
sanctioned building/fitting role); the constructed evaluation is torch analysis off the
runtime hot path. The substrate-RUN instances are the three OCaml `attn_*` fixtures;
this harness is the cross-variant comparison oracle, not itself a substrate program.
