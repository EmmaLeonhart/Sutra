# Type System Considerations

## Primitive Types

Sutra's primitive type set is:

- `scalar` — a real number (float).
- `vector` — a hypervector in the runtime's substrate dimension. The
  workhorse type; everything geometric lives here.
- `matrix` — a rectangular array of scalars, primarily for linear
  transforms that aren't directly expressible as VSA operations.
- `tuple` — a fixed-shape heterogeneous product.
- `string` — a UTF-8 string. Not a vector. String → vector conversion
  goes through `embed(...)`; there is no implicit cast.
- `bool` — a crisp boolean. Produced only by `defuzzy(...)` or the
  unsafe `(bool)` cast on a `fuzzy`.
- `fuzzy` — a graded truth value in `[0, 1]`. The default result type
  of similarity checks and the ground state for truth in the language.
  See `04-defuzzification.md`.
- `void` — no value, for statement-shaped functions.
- `permutation` — a fixed sign-flip mask over a `vector`. At the
  substrate level a permutation is a `vector` of ±1 entries, but it
  is a distinct compile-time type because the operations on it are
  different:
  - Permutations **compose** (`permute(a, permute(b, v)) ==
    permute(compose(a, b), v)`) and **invert** (`permute(inv(p),
    permute(p, v)) == v`).
  - Permutations **act on** vectors via `permute(p, v)`; they are not
    bundled with them.
  - A permutation is **involutive** iff it is its own inverse; the
    common ±1 sign-flip permutations used for negation-as-permutation
    are involutive by construction.

  The distinction matters for compile-to-brain code: the
  `permutation_conditional.su` example under `fly-brain/` compiles
  source-level `!x` into a permutation-key application on the query
  vector, which is algebraically equivalent to the original negation
  because sign-flip permutations distribute over `bind`. Bundling a
  permutation into a vector the way you'd bundle a feature is always a
  mistake — the type separation exists to make that mistake a
  compile-time diagnostic.
- `map<K, V>` — a generic associative container from keys of type
  `K` to values of type `V`. Written in type position as
  `map<K, V>` and constructed with the inline literal syntax
  `{k1: v1, k2: v2, ...}`. The empty literal is `{}`. Lookup uses
  the postfix subscript operator `m[k]`.

  `map` is a *primitive* container alongside `tuple`: the compiler
  knows its shape, and casing-drift detection is suppressed for it
  the same way it is for the other primitives. Keys are expressions,
  not just identifiers, which is what lets the fly-brain
  prototype-table pattern work — the keys in
  `map<vector, string> BEHAVIOR_OF = { proto_PH: "approach", ... }`
  are the prototype vectors themselves, not string labels.

  **Lookup semantics** (open question, tracked in
  `17-open-questions.md`): for scalar and string keys, `m[k]` is an
  exact-match lookup. For vector keys, the intended semantics are
  cosine-nearest — "the stored key closest to `k` in the substrate
  dimension" — because vector equality in a fuzzy-by-default language
  is a similarity question, not a bit-identical question. The current
  SDK validator does not enforce this distinction; it will once
  symbol tables and type inference land in v0.2.

  **Statement vs expression disambiguation.** A bare `{ ... }` at
  statement position is always a block, never a map literal. Map
  literals are only parseable in expression position (after `=`,
  `return`, as a function argument, etc.). Writing a map literal as
  a standalone top-level expression requires wrapping it in a
  declaration or a call — e.g. `var m = {a: 1};` rather than
  `{a: 1};`. This matches the convention in C-family languages and
  avoids a hard ambiguity with block statements.

## No Wrong Types, Only Noise
There are no type errors in Sutra. Binding two unrelated vectors produces a result — it's just semantically meaningless (low similarity to anything useful). The type system is replaced by **similarity checking**: "does this result look like what I expected?"

## Mixed-Regime Spaces
Not all dimensions need to be the same kind:
- **Binary/ternary dimensions:** Structural roles, categorical membership (crisp)
- **Continuous dimensions:** Similarity, degree, graded properties (fuzzy)
- **Hyperbolic dimensions:** Hierarchical/taxonomic relationships (tree-like)
- **Euclidean dimensions:** Lateral/analogical relationships (flat)

This is speculative but suggests Sutra's "vector" type could have geometric subtypes reflecting different kinds of semantic structure.

## Entity Resolution Is Native
The same symbol in different contexts maps to different vectors. Sutra handles this through context-dependent embedding — entity resolution is part of the runtime, not a preprocessing step. The MCP server maintains context for disambiguation.

## Computational Complexity

**Machine-level operations:**
- Algebraic ops (bind, bundle, similarity): O(1) each
- Non-algebraic ops (snap, cone, hop): O(log n) each

**Algorithm complexity** is separate — just as a CPU transistor switching is O(1) but algorithms built on it can be any complexity class, Sutra programs can have arbitrary complexity built from O(1) and O(log n) primitives.

**Capacity limits are real and quantifiable:**
- Bundling degrades signal-to-noise as items are superposed (geometric consequence of dimensionality)
- Binding depth accumulates noise through each operation
- Codebook size limits snap-to-nearest resolution
- These limits are a strength — they are predictable, unlike neural net capacity which is opaque

**On VSA and NP problems:** A "perfect embedding" that let you read off NP solutions in polynomial time would itself require exponential resources to construct. The impossibility of such an embedding is provably equivalent to P ≠ NP — same wall, different face.
