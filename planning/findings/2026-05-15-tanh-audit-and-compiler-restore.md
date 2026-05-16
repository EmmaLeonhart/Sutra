# tanh substrate-leak audit + compiler restore

**Date:** 2026-05-15 (autonomous queue run)
**Author:** Claude (Opus 4.7)
**Touches:** `sdk/sutra-compiler/sutra_compiler/stdlib/math.su`

## The explicit question: did tanh leak the substrate?

**Yes, it did — and it is now fixed, independently verified here.**

- **Before 2026-05-15:** `tanh` (and the whole transcendental family)
  did `xv = float(x)` / `return float(...)` — a host-scalar sandwich
  around the tensor `_lerp`. A real substrate leak, of exactly the
  class CLAUDE.md's safety preamble forbids. The codegen comment even
  claimed "substrate-pure" above code that was not.
- **Fixed in commit `21a9ff77`** (prior session, documented in
  `2026-05-15-transcendental-substrate-leak-fixed.md`).
- **Independently re-verified in this run** (not taking the prior
  claim on faith, because the user explicitly distrusts prior
  purity claims):
  1. Read the emitted runtime: `tanh` → `exp(2·_st(x))` →
     `cexp` → `_exp_table`/`cos`/`sin` → `_lerp`
     (`matmul`/`clamp`/`round`) → tensor arithmetic → tensor return.
  2. Ran it: `Math.tanh(1.0)` returns a `torch.Tensor` (not a host
     `float`), value `0.76162` vs `math.tanh(1.0)=0.76159`.
  3. Grepped the emitted `_st..floor` block for leak signatures
     (`float(`, `.item()`, host `if`, `raise`, `for…range`):
     **0 occurrences.**

So the tanh leak was real, is fixed, and the fix is genuine — this
is a verified statement, not a repeated claim. The GPU primitives in
play (`matmul`, `clamp`, elementwise `+−×÷`, `round`) are all
SIMD-class tensor ops; none is a host branch.

## The thing the user actually hit: the compiler was 100% down

`math.su` contained a hand-written vision block in Java syntax
(`public static number exp(number x){ return realExp(x.real) *
imaginaryExp(x.imaginary); }`). That is a `SUT0140` parse error.
The stdlib loader treats stdlib parse errors as fatal, so **every
`.su` program failed to compile** — not a leak, a total outage.

Restored by rewriting `math.su` in the requested terse literate
style (one-line identity citations onto the two leaves; no bloaty
essays, no lying-confession comments), methods `intrinsic` routing
to the verified-pure `_VSA.*`.

Verified before commit: `test_transcendentals` 3/20-subtests,
corpus+stdlib_loader 15/103-subtests, `examples/_smoke_test.py`
PASS, 0 leak signatures, tensor returns matching `math.*`.

## What is genuinely open (NOT faked as done)

The user's literate vision is that the `.su` method *bodies* are the
executable beta-reduction:

```
static method number exp(number z) {
    return realExp(z.real) * imaginaryExp(z.imaginary);
}
```

Making that real (not docstring-only) needs three things, each of
which is genuinely unfinished and must not be claimed otherwise:

1. **One complex representation.** The verified-pure `cexp`/`exp`/
   `cos`/`sin` chain returns a length-2 `[re, im]` stack. Complex
   literals + `complex_mul` use the d-dim synthetic-axis layout
   (`AXIS_REAL`/`AXIS_IMAG`). They disagree. Wiring `realExp(z) *
   imaginaryExp(z)` across that boundary today makes
   `complex_mul(0-d tensor, d-dim vector)` broadcast — **silently
   wrong complex math**. Unifying onto the d-dim layout is the
   prerequisite and is the real first task.
2. **Substrate-pure `.real` / `.imaginary`.** Member access on a
   complex currently falls through to Python `x.real` (codegen_base
   :2766), which on a real-dtype tensor is torch's no-op `.real`
   — not an `AXIS_REAL` projection. Needs a one-hot/matrix
   projection (pure tensor op).
3. **Namespaced-stdlib inlining.** `Math.exp(z)` is
   `Call(MemberAccess(Math, exp))`; the inliner only resolves
   `Call(Identifier)`. A ~10-line extension makes the namespaced
   form inline so the `.su` body becomes the executable reduction.
   Drafted this run, then **reverted** — correct in principle but
   not verifiable end-to-end until (1) and (2) land, and shipping
   unverified changes to a safety-critical compiler is the exact
   failure mode being corrected.

`scalar` vs `number`: the user's position is that `scalar` is a
substrate-leak-shaped type and the true numeric type is the complex
`number` (real+imag). That is a numeric-core migration, downstream
of (1). Logged, not started, not faked.

## Why it was not pushed further in this run

The honest reason: completing (1)–(3) correctly is a numeric-core
refactor of a safety-critical compiler. A half-built version
produces wrong complex arithmetic. Shipping that with a
"substrate-pure / done" label is precisely the lie that triggered
this whole audit. The disciplined outcome is: compiler restored and
verified, leak question answered and verified, deep refactor scoped
honestly and queued — not a fake completion.
