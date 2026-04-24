# Sutra standard library (stdlib)

Canonical Sutra definitions for built-in operations.

## The gap this directory exists to close

Today most system functions — `defuzzy`, `logical_and/or/not`, `eq`, `neq`,
`gt`, `lt`, `ge`, `le`, `complex_mul`, `bind`, `unbind`, `bundle`, the
rotation primitives, `embed`, the hashmap ops, `make_real` / `make_complex`
/ `make_char`, `zero_vector` — are hardcoded as runtime methods emitted
by `codegen.py`'s `_emit_prelude`. The generated Python module carries
the whole runtime as a class body. That works, but it means:

- **System functions are opaque to the compiler.** `defuzzy(v)` in user
  code compiles to a runtime call with a `for _ in range(10)` loop
  hidden inside. The compiler can't see the loop to unroll it, and the
  fusion pass can't see the chain of equality ops to collapse them.
- **Every backend re-emits the runtime method bodies.**
- **There's no Sutra-level overriding or specialization.**

## Direction

System functions live here as `.su` files. The compiler's function-expansion
pass inlines calls to them into user AST; the existing `loop(N)` compile-time
unroll kicks in; the (future) fusion pass collapses the unrolled
straight-line tensor chain into a cached matrix applied in a single matmul.

## Inventory (2026-04-23)

All files parse cleanly under the full `sutrac` validator. **None are yet
wired into the codegen pipeline** — user code still compiles to the
hardcoded runtime methods. These are canonical reference files that the
inliner will consume when it lands.

### `logic.su` — truth-axis and logic ops
- **Implemented in Sutra:** `defuzzy`, `logical_not`, `logical_and`,
  `logical_or`, `neq`, `lt`, `ge`, `le`
- **Blocked on intrinsics:** `defuzzify_trit` (β-sharpening polarizer),
  `gt` (tanh + projector matrices)

### `similarity.su` — cosine / similarity / argmax
- **Implemented in Sutra:** `neq` (via `!(a == b)`)
- **Blocked on intrinsics:** `eq`, `similarity` / `Cosine`,
  `argmax_cosine`, `select`, `snap` (substrate-level cleanup)

### `numbers.su` — number family (int / float / complex / char)
- **Blocked on intrinsics:** `make_real`, `make_complex`, `make_char`,
  `complex_mul`, `conj`

### `vectors.su` — VSA ops
- **Blocked on intrinsics:** `bind`, `unbind`, `bundle`, `basis_vector`
  (alias for embed), `permute`, `permutation_key`, `identity_permutation`,
  `compose`

### `memory.su` — memory / lookup
- **Blocked on intrinsics:** `zero_vector`, `hashmap_get`, `hashmap_set`,
  `map_lookup`

### `rotation.su` — rotation matrices and eigenrotation
- **Blocked on intrinsics:** `make_random_rotation`, `compile_prototypes`,
  `eigenrotation_loop` (what `loop(cond)` / `while` compile to)

### `embed.su` — LLM embedding intrinsic
- **Pure intrinsic:** `embed(string) -> vector`. No Sutra body — the
  operation is a leaf in the dataflow graph (hits Ollama, caches,
  normalizes).

## Pipeline needed to make this live

1. **Loader.** Parse every `*.su` file under this directory at compiler
   init. Build a symbol table `{function_name → FunctionDecl}` plus a
   parallel set of names marked `@intrinsic`.
2. **Inliner in simplify.py.** When encountering a
   `Call(Identifier(name), args)` whose name is in the stdlib symbol
   table, inline the function body — beta-reduce args → params, splice
   into the caller's AST.
3. **Unroll.** Existing compile-time `loop(N)` unroll fires naturally on
   the inlined body: `loop(10) { ... }` becomes 10 straight-line
   statements.
4. **Delete runtime methods.** Once every caller is inlined, the
   corresponding `def defuzzify(...)` / `def logical_and(...)` / etc. in
   `_emit_prelude` is dead code. Drop them.
5. **Intrinsic mechanism.** Define the surface for functions whose
   body lives in the runtime — either a `@intrinsic` decorator keyword
   on a function with no body, or a dedicated `intrinsic` statement. The
   leaf primitives (`dot`, `sqrt`, `tanh`, matrix literals, `@` matmul,
   axis-slot indexed read/write, Haar rotation factory, LLM embedding)
   become the set of things the runtime must implement.
6. **Fusion pass (follow-up).** Recognize chains of linear tensor ops
   in the inlined+unrolled straight-line code and fold them into cached
   matrices. This is the pass that makes the "ten-iteration defuzzy
   loop collapses to one matmul" promise real.

Once this pipeline is live, adding a new builtin is: write a `.su` file
here, mark the leaf primitives it needs as `@intrinsic`, land any
missing primitives in the runtime. No codegen prelude edits, no
per-backend duplication.
