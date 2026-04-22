# Types

This section describes the types the compiler recognizes today,
the declaration forms for each, and the extent (or absence) of
type checking. The compiler does not currently do static type
checking — types are spec commitments and runtime expectations,
not enforced constraints.

## The type surface

### Core types

Three base types at the bottom of the user-framed hierarchy:

- **`vector`** — the default. Almost everything in Sutra programs
  is a vector. At runtime a `vector` is a `numpy.ndarray` of
  shape `(dim,)` where `dim` is the substrate's dimension (768 on
  nomic-embed-text, 1024 on mxbai, etc.).
- **`matrix`** — two-dimensional; the user-framed base type for
  learned role matrices, rotation matrices, and defuzz matrices.
  Not yet a first-class declaration form (`matrix X = …` isn't
  accepted); matrices exist today only as rotation matrices
  inside the rotation-binding runtime.
- **`scalar`** — the base type for numbers. A `scalar` at runtime
  is a Python `float`.

### Subtypes of `vector`

- **`fuzzy`** — a vector representing a quantity between `true`
  and `false`. Per the spec design, a fuzzy is a scalar on the
  canonical truth axis of the synthetic subspace (the extended-
  state-vector design). **Implementation status**: deferred. The
  current runtime treats a `fuzzy` declared via `var x : fuzzy;`
  as a plain Python `float` zero, because the synthetic subspace
  isn't yet a runtime concept.
- **`bool`** — a subtype of `fuzzy`. Per design, a bool carries a
  defuzzification counter as compile-time metadata so the
  compiler can distinguish values that have been defuzzed N
  times from values that have been defuzzed M times. There is
  no crisp-boolean form in Sutra; `bool` is always still a fuzzy.
  Implementation is currently the same placeholder `float` zero
  as `fuzzy`.

### String and numeric types

- **`string`** — a Python `str` at runtime. Used as function
  parameter and return types (`function string main()`),
  `basis_vector(string) → vector`, and as values in `map<V, string>`
  lookup tables.
- **`int`**, **`number`** — numeric types. The compiler treats
  them as Python numbers; there's no distinction between `int`
  and `scalar` at the runtime level today.

### `map<K, V>`

A two-parameter generic map type. Used extensively in demos for
codebook-name lookup tables:

    map<vector, string> PHRASE_NAME = {
        v_hello:    "hello world",
        v_goodbye:  "goodbye",
    };

The compiler tracks the declared key type so subscript lookups
dispatch correctly: vector-keyed maps use an identity-first
comparison (`is` check) with cosine-similarity fallback; other
key types use ordinary dict lookup. See
`codegen_flybrain.py::_vector_map_lookup`.

## Declaration forms

Five forms of declaration work at both top level and inside
functions. The 2026-04-22 expansion (Candidate B surface syntax)
added the colon-typed `var` forms and the `role` contextual
keyword to the existing `TYPE X = expr;` / `var X = expr;` /
`const TYPE X = expr;` set.

### `TYPE X = expr;` — classic typed declaration

    vector r_name = basis_vector("role_name");
    map<vector, string> PHRASE_NAME = { ... };

The type appears before the name, initializer is required. This
is the form used by most `.su` demos today.

### `var X = expr;` — inferred type

    var x = basis_vector("foo");

Inferred type, initializer required. Rare in the existing demos
but accepted.

### `const TYPE X = expr;` — explicit const

    const vector TAU = basis_vector("constant");

Same as typed declaration but marked const. Not enforced
differently at runtime.

### `var X : TYPE;` / `var X : TYPE = expr;` — colon-typed var (2026-04-22)

    var storage : vector;          // zero-initialized slot
    var greeting : vector = embed("hello");
    var t_score  : fuzzy;          // scalar 0.0

The colon syntax is the new rotation-bound-storage form from
Candidate B. Without an initializer it allocates a typed zero
(`np.zeros(dim)` for vector, `0.0` for fuzzy/bool/int/scalar/
number). With an initializer it's equivalent to `TYPE X = expr`.

### `var[N] X : TYPE;` — array of N slots (2026-04-22)

    var[16] slots : vector;

Allocates a Python list of N zero-initialized values of the given
type. Intended for rotation-bound-array use cases. Initialized
array declarations (`var[N] X : TYPE = expr;`) are rejected at
codegen — the broadcast/replicate semantics aren't yet specified.

### `role X = expr;` — semantic role declaration (2026-04-22)

    role capital_of = basis_vector("capital_of");

`role` is a **contextual keyword**: the lexer emits IDENT for the
word "role" and the parser recognizes `role` as a declaration
keyword only at statement start with IDENT-IDENT-ASSIGN
lookahead. This keeps `vector role` as a valid parameter name
elsewhere.

Today `role X = expr;` behaves identically to `vector X = expr;`
at the codegen level; the `is_role` flag on the AST node is
metadata reserved for the deferred **learned-matrix binding**
path (when `role X = learned_from(data);` lands, the flag will
trigger matrix-fitting at compile time).

## Type checking — there isn't any

The compiler does not statically check:

- That a function's body returns something of the declared return
  type.
- That a function's arguments match the declared parameter types.
- That an expression's result is type-compatible with its
  destination (e.g. assigning a vector to a `scalar`-typed
  variable).
- That a `var X : TYPE` reference in an expression produces the
  declared type.

Type annotations are spec commitments and parser metadata; the
runtime is Python-duck-typed. A `.su` program that lies about its
types will compile and fail at runtime with a numpy or Python
error, not at compile time with a type error.

Type checking is a real future work item. Relevant questions:

- Should the checker be structural (based on expression shape) or
  nominal (based on declared types)?
- At what stage does checking happen — a separate pass after
  parsing but before codegen?
- What about substrate-specific types (e.g. a `kc_pattern` type on
  the fly-brain substrate that doesn't exist on numpy)?

Not in scope for the current spec. The fact that the runtime is
untyped is noted here so readers don't assume a static-checker
guarantee that isn't there.

## Tuples and lists

Tuples and lists exist at compile time but not at runtime per the
user's 2026-04-15 framing: they are scaffolding for writing the
math, they collapse to vectors / matrices / scalars at runtime.
List literals appear in `argmax_cosine` calls:

    argmax_cosine(query, [v_a, v_b, v_c])

These compile to a Python list in the emitted code; at codegen
time they're a container for an argmax iteration, not a runtime
container the program can reshape.

## Open questions

- **`bool`'s defuzz-counter ceiling.** The spec design says a
  bool carries a compile-time counter tracking how many defuzz
  steps have been applied. Does that counter have a ceiling?
  What happens when a bool has been defuzzed "all the way" —
  does it become a distinguished value?
- **Scalars as results.** Can a Sutra function return a `scalar`,
  or only accept scalars as inputs (thresholds, angles, iteration
  counts)?
- **Other subtypes of vector.** `probability`, `angle`,
  `unit_vector` are plausible if the subtyping is wanted. Not
  claimed; flagged because they're obvious candidates.
- **First-class matrix subtypes.** Does Sutra want
  `rotation_matrix`, `defuzz_matrix`, `is_X_matrix` as real
  types the compiler knows about, or are those purely
  conventional shapes?
- **`var[N]` with an initializer.** `var[N] X : TYPE = expr;` is
  rejected today. The broadcast semantics (does every slot get
  `expr`, or does `expr` unpack into the slots somehow?) is
  unspecified.
- **Static type checking.** Do we want one? If so, at what stage
  and how strict? Currently no checking is done.
