# Numbers-on-substrate broke scalar-consuming positions across the demos (hidden by demos-ci's path filter)

**Date:** 2026-06-21
**Status:** root-caused; each manifestation fixed forward; one systemic recommendation open (Emma's call)

## Summary

The numbers-on-substrate leg (commit `44127510` / `2eabf9a4`, this session) routed runtime
`int`/`number`/`scalar` arithmetic through the real-axis number ops (`num_add/sub/mul/div`), so a
*computed* number is now a real-axis number-**vector** (the value on `AXIS_REAL`, zeros elsewhere)
instead of a 0-d host scalar. That is correct and intended for pure numeric arithmetic. But it
**silently broke every place a number is consumed in a SCALAR position** — where the old 0-d scalar
broadcast or reduced cleanly and a full d-dim vector does not.

The leg was merged on "compiler suite 788 passed." It was not as done as that implied: the compiler
suite uses `bool`/vector-typed booleans and small hand-written programs; it does not exercise the
real demos (arithmetic at small `runtime_dim`, scalar gates over domain vectors, `select` with
arithmetic scores, `main` returning a number). Those live under `demos/`, and **`demos-ci.yml` is
path-filtered to `demos/**`** — so an `sdk/`-only compiler commit never runs them. The breakage sat
latent until a `demos/`-touching commit (the FV measurement-sweep) ran demos-ci and surfaced it.

## The one conceptual gap, four manifestations

A number-vector used where a **scalar** is expected needs **real-axis projection** (`_num_re` /
`AXIS_REAL` slice — a substrate-pure dot/slice, autograd-safe, NOT a host `.item()`). Each site that
consumes a scalar needed that projection added:

1. **Logical operators over `int` operands** (fixed earlier, commit `48b3e982`). The inlined Kleene
   Lagrange polynomial over truth-axis vectors got routed to `num_*` and destroyed the truth value.
   Fix: `_logical_truth` provenance marker → force element-wise. (Truth axis, not real axis — the
   mirror-image case: a vector wrongly sent to the number axis.)

2. **`select` scores** (`_select_softmax`, fixed this session). Score expressions like
   `-1000*(pos-t)^2` became real-axis vectors; stacking N of them gave a 2-D `(N, d)` tensor and the
   softmax-weighted sum collapsed to a 2-D `pos_vec`, which then broke `unbind`'s `_role_hash`
   (`bytes()` over a nested list). Fix: project a 2-D score stack onto `AXIS_REAL` before the softmax.
   Surfaced via `font_bound` / `font_bound_antipodal`.

3. **Scalar-gate multiplication** `vector * number` (the arith router, fixed this session). The blend
   idiom `advanced * (1.0 - has_typed) + typed_onehot * has_typed` (font_cycle's glyph-cursor RNN):
   `(1.0 - has_typed)` became a 108-dim real-axis vector, and `advanced` is a 36-dim domain one-hot,
   so the element-wise `*` crashed `36 vs 108`. (At equal dim it would have been silently wrong —
   element-wise mul by a value-on-AXIS_REAL-zeros-elsewhere vector zeros every non-real axis.) Fix:
   in the mixed `vectory * numbery` case, wrap the number operand in `_num_re` so it broadcasts as a
   0-d scalar multiplier. A host literal (`0.5`) passes through `_num_re` unchanged, so `truth_vec *
   0.5` and the logical Lagrange coefficients stay byte-identical.

4. **`main` returning a number** (test display boundary, fixed in `test_button_spec_ts.py`).
   `main`'s arithmetic returns a real-axis number-vector, but the test read it out with `.item()`
   expecting a 0-d scalar. Fix: project to the real-axis scalar at the display boundary (the same
   role as the font demos' `read_real`).

## Why the compiler suite missed all four

Dispatch-level cleanliness (every op runs on the substrate) is necessary, not sufficient — exactly
the CLAUDE.md "subtler substrate breaches" meta-rule. These four pass the dispatch check; they fail
on shape/semantics that only a *running program at a real dim* exposes. The compiler suite's
hand-written tests didn't have a scalar gate over a 36-dim domain vector, a `select` with arithmetic
scores, or a `main` returning a number — the demos do.

## Systemic recommendation (open — Emma's call)

**`demos-ci.yml` should arguably trigger on `sdk/**` too**, not just `demos/**`. The path filter is
why a compiler change can break every demo and nobody sees it until a demo file happens to change.
Counter-cost: the full demos suite is ~20-25 min with cache-miss recompiles (a codegen change
invalidates the source+codegen-hashed compile caches, and `font.su`'s 22500-op switch dominates), so
running it on every compiler push materially slows compiler-change iteration. That tradeoff is a
CI-policy decision, not made here. (The compiled `.compiled-*.py` caches were also committed-but-
gitignored, which could mask a runtime change behind a stale cache; untracked this session.)

## Verified

font_bound 2/2, font_bound_antipodal 2/2, font_cycle 4/4, button_spec 1/1, calc 27/27, count/toggle
6/6, font/frame 55/55; compiler `number`/`select`/`logical`/`arith` tests; full compiler suite;
OCaml transpiler 155. The scalar-multiply router change is byte-identical for host-literal
coefficients (the logical/Lagrange path), so it does not regress the earlier `_logical_truth` fix.
