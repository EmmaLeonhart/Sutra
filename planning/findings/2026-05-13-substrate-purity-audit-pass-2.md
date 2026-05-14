# Substrate-purity audit, pass 2 — `%` was never wired; `complex` `/` was silently wrong

**Date:** 2026-05-13
**Author:** Claude (Opus 4.7) under Emma's direction
**Supersedes:** `planning/findings/2026-04-30-runtime-substrate-purity-audit.md`
extended (does not invalidate — that pass caught the transcendentals;
this pass extends to binary operators that the prior audit's scope
didn't cover).

## What triggered this audit

Emma 2026-05-13: the `%` operator was running on host Python at
runtime, not on the substrate, and producing Python's floor-modulus
semantics (`-1 % 3 == 2`) where JS / C / Rust / TS expect truncation
modulus (`-1 % 3 == -1`). User asked: when did this become a
fall-through? Is anything else falling through?

## Regression history — `%` was never wired

`%` was lexed and parsed correctly from the initial SDK scaffold at
commit `af650b0d` (2026-04-10), which introduced the `PERCENT` token
and the `_parse_multiplicative` parser rule that accepts it.

The first codegen, `dc8b591d` (2026-04-10, AST → FlyBrainVSA
translator), had no special case for `%` — `BinaryOp` translation
emitted `f"({left} {expr.op} {right})"` for every operator the
special-case path didn't catch. That generic fall-through migrated
intact into `BaseCodegen` on `c7d380df` (2026-04-23, "Break
NumpyCodegen's fly-brain dependency; extract BaseCodegen") and
sat there until today.

So this was **never a regression** — `%` was a never-wired path
the entire time. It survived because:

1. No `.su` program in the corpus actually used `%`. The corpus
   tests cover complex multiplication, transcendentals, loops,
   strings, axons, classes — but no integer modulo program.
2. The 2026-04-30 substrate-purity audit was scoped to
   transcendental functions (the obvious `Math.*` leaks). Binary
   operators were outside that audit's frame.
3. The TS transpiler only added `Math.*` shims in the May 2026 push;
   before that no TypeScript-derived path needed `%`.

The leak surfaced today only because the user pushed on the
modulus library directly.

## What pass 2 caught

### Leak 1 — `%` operator (FIXED)

`codegen_base.py:2647` fell through to `(left % right)` — host Python
modulo. **Fixed**: route through `_VSA.fmod(left, right)`
substrate-pure truncation mod, JS / C / Rust / TS compatible. See
queue.md item 3 and
`planning/findings/2026-05-13-modulus-rotation-vs-sawtooth.md`.

### Leak 2 — `complex + scalar` and `complex - scalar` (FIXED)

Worse than the `%` leak because the math was silently **wrong**.

For complex `a = 3 + 4i` and scalar `1.0`, the expression `a + 1.0`
was emitted as raw `(a + 1.0)` — element-wise tensor + Python float,
which broadcasts the scalar across **every** axis of the extended
state vector including imag. Result: `4 + 5i` instead of `4 + 4i`.

Same shape for `complex - scalar`. **Fixed**: route `+` and `-`
through `_VSA.complex_add(a, b)` / `_VSA.complex_sub(a, b)`, both of
which coerce both operands via `_as_complex_vector` (scalar → `make_real`)
before the element-wise op.

### Leak 3 — `complex / complex` (FIXED, SAFETY-CRITICAL)

The worst of the three. `(5+5i) / (2+0i)` was emitted as `(a / b)` —
element-wise tensor division. Element-wise gives `a_real / b_real`
and `a_imag / b_imag`. For the test case: `5/2 = 2.5` on the real
axis, `5/0 = inf` on the imag axis. The correct complex division
formula is `(ac+bd)/(c²+d²) + ((bc-ad)/(c²+d²))i = 2.5 + 2.5i`.

So a Sutra program that did complex division would silently produce
mathematically wrong answers and could inject `inf` / `NaN` into
downstream computation. Per CLAUDE.md's safety rule
("biomedical hardware and software; if the math is wrong people can
die"), this is exactly the class of failure that must not exist.

**Fixed**: route `/` through `_VSA.complex_div(a, b)`, substrate-pure
implementation. Uses three cached d×d matrices (`_conj_matrix`,
`_broadcast_real_matrix`, plus the existing `_swap_ri_matrix` and
`_cm_*_matrix` family) and one `complex_mul` call. No scalar
extraction inside the operation — the conjugate, the numerator, and
the modulus-squared all stay on tensors.

Verified against ground-truth Python complex arithmetic on 8 cases
covering complex+scalar, complex+complex, complex-scalar,
complex-complex, complex/real_scalar, real_complex_division,
unit-imaginary, and the all-real case. All eight pass.

## Not leaks (verified)

The audit also confirmed:

- **Bitwise operators `&` `|` `^`** are lexed (lexer tokens
  `BIT_AND`, `BIT_OR`, `BIT_XOR`) but not parsed — `_parse_*` rules
  don't consume them, so user code with `a & b` errors at parse time
  rather than fall-through. No substrate-purity risk.
- **Power `**`** and **floor-div `//`** don't exist as tokens.
- **Comparison operators** `<` / `>` / `<=` / `>=` already dispatch
  through `_comparison_src` for number-axis operands; comparisons
  on plain Python int / float fall through to Python's own `<` etc.
  which is the documented and correct behavior (`5 < 3` is a Python
  bool literal at compile time, not a Sutra truth-axis value).
- **Equality `==` `!=`** dispatch through `_equality_src` — already
  substrate-routed.
- **Logical `&&` `||`** dispatch through `_logical_op_src` — Zadeh
  fuzzy min/max on the truth axis.
- **Unary `!`** dispatches through `_logical_not_src`. Unary `+` /
  `-` pass through to Python, which is correct: `-x` on a torch
  tensor is a substrate op, and on a Python int/float it stays a
  Python scalar (the documented fast-path for compile-time integer
  arithmetic).

## Remaining open

- **`Math.round` ties-to-even vs JS ties-to-positive.** Documented
  semantic mismatch with JS. Not a substrate-purity issue but a
  JS-compat issue. Tracked under modulus library queue item.
- **`torch.atan2` inside `Math.rotation_mod`.** Per the no-libm-
  shortcut memory, transcendental decompositions should use lookup
  tables rather than libm. atan2-via-lookup-table is the natural
  follow-on, same architecture as exp/log/sin/cos. Documented in
  the modulus library queue item and in `Math.mod`'s docstring.

## Lesson for future audits

The 2026-04-30 audit scoped itself to "transcendentals" and missed
binary operators entirely. The 2026-05-13 trigger was an unrelated
user push, not a proactive audit catching it. **Future audits
should sweep every codegen emission for any raw Python operator
between values that could possibly be Sutra-typed at runtime, not
just the obvious named functions.** Specifically: any line in the
codegen that produces `f"({left} {op} {right})"` or
`f"{thing} {pythonop} {thing}"` deserves a "what if both sides are
substrate vectors at runtime?" check.

The corpus sweep at the bottom of this audit (see
`experiments/substrate_leak_sweep.py` — to be added) walks every
`.su` program under `tests/corpus/valid/` and `examples/`, compiles
each one, and greps the emitted Python for suspicious patterns.
That should become a CI gate.
