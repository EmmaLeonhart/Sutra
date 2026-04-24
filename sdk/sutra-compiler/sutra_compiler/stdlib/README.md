# Sutra standard library (stdlib)

Canonical Sutra definitions for built-in operations.

## The gap this directory exists to close

Today most system functions — `defuzzy`, `logical_and/or/not`, `eq`, `neq`,
`gt`, `lt`, `ge`, `le`, `complex_mul`, the rotation primitives — are
hardcoded as runtime methods emitted by `codegen.py`'s `_emit_prelude`.
The generated Python module carries the whole runtime as a class body.
That works, but it means:

- **System functions are opaque to the compiler.** `defuzzy(v)` in user
  code compiles to a runtime call `_VSA.defuzzify(v)` with a
  `for _ in range(10)` loop inside. The compiler can't see the loop to
  unroll it, and the fusion pass can't see the chain of equality ops to
  collapse them.
- **Every backend re-emits the runtime method bodies.** `def defuzzify(...)`
  appears in both `codegen.py` and `codegen_pytorch.py` with nearly
  identical logic, just numpy-vs-torch ops.
- **There's no Sutra-level overriding or specialization.** Since the
  definitions aren't Sutra source, user code can't replace or extend
  them from within the language.

## Direction

System functions live here as `.su` files. The compiler's function-expansion
pass inlines calls to them into user AST; the existing `loop(N)` compile-time
unroll kicks in; the (future) fusion pass collapses the unrolled
straight-line tensor chain into a cached matrix applied in a single matmul.

## Status (2026-04-23)

`logic.su` holds the canonical definitions for the truth-axis and
logic-op family. Parses cleanly under the full `sutrac` validator;
**not yet wired into the codegen pipeline** — user code that writes
`defuzzy(v)` or `a && b` today still compiles to the hardcoded runtime
call. This file is the target shape for the expansion work.

Two sections inside logic.su:

**Implemented in pure Sutra** (8 functions):
- `defuzzy` — ten-iteration cosine-eq polarization loop
- `logical_not` — `0 - v` (Kleene K₃ negation)
- `logical_and` — `(a + b + ab - a² - b² + a²b²) / 2` (Lagrange polynomial)
- `logical_or` — `(a + b - ab + a² + b² - a²b²) / 2` (dual polynomial)
- `neq` — composed via `!(a == b)`
- `lt` — swapped `>` arguments
- `ge` / `le` — collapse to `>` / `<` on the differentiable scheme

**Blocked on intrinsics** (4 functions, commented-out pseudo-Sutra bodies):
- `eq` — needs `dot`, `sqrt`, `make_truth`, `finfo.tiny`
- `gt` — needs `tanh` on vectors, axis-projector matrices, matmul operator
- `defuzzify_trit` — needs truth-projector matrix, β-sharpening primitive
- `complex_mul` — needs three cached matrix literals and matmul operator

The blocked ones stay as hardcoded runtime methods in codegen.py until
an `intrinsic` mechanism lands (letting .su files declare "this is
implemented by the runtime" for the leaf primitives) or until those
primitives get first-class language surfaces.

## Next work

1. Add a loader in `sutra_compiler` that parses every `*.su` file under
   this directory at compiler init and builds a symbol table
   `{function_name → FunctionDecl}`.
2. In the simplify pass, when encountering a `Call(Identifier(name), args)`
   whose name is in the stdlib symbol table, inline the function body —
   beta-reduce arguments into parameters, splice into the caller's AST.
3. Existing compile-time unrolls fire naturally on the inlined body:
   `loop(N)` with literal `N` becomes `N` straight-line statements.
4. Delete the corresponding runtime method from `_emit_prelude` once all
   callers are inlined — the method is dead code.
5. (Follow-up) Fusion pass: recognize chains of linear tensor ops in
   the straight-line code and fold them into cached matrices.

Once this pipeline is live, adding a new builtin is "write a .su file
here, maybe add an intrinsic for the leaf primitive it needs." No
codegen method edits, no per-backend duplication.
