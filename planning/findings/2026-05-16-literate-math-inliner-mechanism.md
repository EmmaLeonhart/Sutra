# Literate-math: the namespaced-stdlib inliner mechanism (item #12 (c))

**Date:** 2026-05-16 (autonomous queue continuation)
**Author:** Claude (Opus 4.7)
**Touches:** `sdk/sutra-compiler/sutra_compiler/inliner.py`
**Context:** queue.md item 1 "literate math", task #12. Prereq (a)
(unify complex representation) was delivered 2026-05-15 (`ecf1c4cd`,
verified); (b) (`.real`/`.imaginary` projection) was obviated
(`realExp`/`imaginaryExp` project the axis internally). Only (c)
remained: make `Math.exp(z)` resolve the `.su` method body.

## What landed and is verified

The inliner only resolved `Call(Identifier(name))`. A namespaced
stdlib call `Math.exp(z)` is `Call(MemberAccess(Identifier("Math"),
"exp"))` — skipped, so a class-bodied stdlib method emitted a call
into a `Math` object that does not exist in the output (`NameError`).
Added: resolve `Call(MemberAccess(Identifier(C), m))` against the
stdlib table's qualified `C.m` entry and inline the single-return
body.

**Empirically verified working**: with `exp` written as a literate
body `static method scalar exp(scalar x){ return realExp(x) *
imaginaryExp(x); }`, `Math.exp(2.0)` inlined to
`_VSA.realExp(2.0) * _VSA.imaginaryExp(2.0)` — the `.su` body became
the executable reduction (the language's whole premise). The
intrinsic leaves passed through to `_VSA.*` unchanged.

**Verified inert + zero-regression** with the current all-intrinsic
`math.su` (no Math.* has a single-return body, so the new branch is
never taken): `test_transcendentals` + `test_corpus` +
`test_codegen_pytorch` + `test_inliner` 39 passed / 103 subtests;
`examples/_smoke_test.py` PASS.

## The ONE remaining bounded piece (precisely named, not "open")

The literate body `realExp(z) * imaginaryExp(z)` is only correct if
`*` dispatches to `complex_mul`. It currently does **not**:
`_is_complex_expr` (`codegen_base.py:2323`) has no `ast.Call` case,
so a call to `realExp` is not seen as complex, `*` falls through to
element-wise multiply, and the result is a d-dim tensor with the
wrong components — silently wrong math. That is why the literate
`exp` body was reverted to `intrinsic` (the verified scalar-boundary
runtime path) rather than shipped.

To finish (c), in order, each verified before the next:

1. **Extend `_is_complex_expr` to handle `ast.Call`**: return True
   when the callee resolves to a function/method whose declared
   return type is `complex`. Sources of truth already in codegen:
   `_class_method_return_types[(cls, m)]` (user classes) and the
   stdlib `FunctionDecl.return_type` from the loader (add a
   stdlib-return-type lookup keyed by bare + `Class.` name).
   Gate: the existing complex test suite (`36_complex_*`,
   `test_codegen_pytorch` complex cases) must stay green — this
   path is what every complex literal / `complex_mul` /
   `complex_div` relies on, so the blast radius is the whole
   numeric core. Do it deliberately, not as a rushed edit.

2. **Put the literate reduction on `cexp`, not `exp`.** `cexp` is
   the genuinely-complex operation = the user's exact vision
   `realExp(z.real) * imaginaryExp(z.imaginary)`. Declare
   `realExp` / `imaginaryExp` / `cexp` as returning `complex` in
   `math.su`; write `static method complex cexp(complex z){ return
   realExp(z) * imaginaryExp(z); }`. Keep `exp`/`cos`/`sin`/… as
   the verified intrinsic scalar boundary (`real(cexp(x))` /
   `real(cexp(iθ))` / `imag(cexp(iθ))`) so the ~hundreds of
   `scalar`-typed call sites and the test corpus keep working with
   no migration.

3. Verify: `Math.cexp` of a complex matches ground truth
   (`cexp(iπ)=-1`, `cexp(1+iπ/2)=ie`, `cexp(0.5+i)=0.89+1.39i`);
   `Math.exp(2.0)` still a 0-d real; transcendentals + corpus +
   smoke + leak grep all green. Only then mark #12 (c) done.

## The deeper, separate, documented-but-deferred decision

"There is no scalar — a real is a complex with imag 0" (the user's
repeated position). Making *every* transcendental return `complex`
and migrating all `scalar` call sites + the test corpus is the full
scalar→number migration. It is a decided *direction* but a large,
high-regression change; it is NOT a prerequisite for the literate
`cexp` reduction above (step 2 sidesteps it). It belongs in the
open-questions triage (task #15) as a RESOLVED-direction /
GENUINELY-OPEN-on-scope entry, not as a blocker pretended-resolved
here.

## Honest status

(c)'s *mechanism* (namespaced-stdlib inlining) is delivered and
verified. (c) is not "done" — the `_is_complex_expr` + `cexp`-body
steps above remain, and they are bounded and named, not an open
design gap. Nothing wrong-math was shipped; the inliner change is
correct and inert until literate bodies that need it land.
