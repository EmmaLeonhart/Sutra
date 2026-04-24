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

- **`logic.su`** — canonical definition of `defuzzy`. Parses cleanly as
  Sutra but is **not yet wired into the codegen pipeline**. User code
  that writes `defuzzy(v)` today still compiles to the hardcoded runtime
  call. This file is the target shape for the expansion work.
- Other logic primitives (`logical_and/or/not`, `eq/neq`, `gt/lt/ge/le`)
  will land here once their Sutra-level form is settled. Some
  (`logical_not`, `logical_and`) are polynomial tensor ops today; their
  Sutra-source form depends on deciding whether the polynomial
  constants live in the language or stay as codegen magic.

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
