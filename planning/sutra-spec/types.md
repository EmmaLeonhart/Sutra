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
- **`int`**, **`number`**, **`scalar`** — numeric types. All live
  on the canonical *number axis* of the synthetic subspace (see
  §"The number axis and the integer class" below). At runtime
  they are all Python floats; the distinction between them is
  compile-time metadata.

### The number axis and the integer class

User direction 2026-04-22 (evening): the synthetic subspace gets
a canonical *number axis* — one dimension, going up, that scalar
values live on. All numeric types share this axis. Everything in
Sutra is a float at runtime because everything is a vector; the
number axis is where those scalar floats sit.

**What lives on the number axis.** User direction, 2026-04-22:
*"integers are the only thing that ever enters this space unless
an LLM embedding goes there."* The axis is reserved, by design,
for integer-class values. Every Sutra-produced operation that
touches the number axis is a scalar arithmetic operation on an
`int`-classed value — no bind / bundle / rotation / learned-
matrix operation is specified to emit a nonzero number-axis
coordinate. The only thing that can leak onto the axis from
outside is an LLM embedding that happens to have nonzero
coordinate on that specific synthetic dimension; that's
incidental, not a design feature, and is expected to be
negligible in practice since embeddings live in the semantic
subspace and the synthetic subspace is structurally orthogonal.

This is the same cleanliness guarantee the truth axis carries
(see `equality-and-defuzzification.md` §"The canonical truth
axis"): because the synthetic subspace is orthogonal to the
semantic subspace by construction, the axis stays clean — it
doesn't accumulate noise from semantic operations elsewhere in
the program.

The **integer class** is a compile-time tag, parallel to `bool`'s
defuzz counter: it marks values that should behave integer-like.
Its primary role is to make *augmented assignment* (`+=`, `-=`,
`*=`, `/=`) first-class. `var n : int = 0; n += 1; n += 1;` is
the canonical integer-style iteration pattern and is what turns
Sutra into "something of a convention" — a programming language
that looks like programmers expect while the underlying substrate
is still vector math.

As of 2026-04-22, augmented assignment works on any scalar-typed
target. The codegen emits Python's native `target op= value` form,
which has identical semantics for Python floats (what scalars are
today) and numpy arrays (what `var x : vector += y` would be,
though vector-valued compound assignment isn't really the use case).

Future work on the integer class (tracked in `todo.md`):
- Compile-time integer-specific checks (overflow bounds, mod-N
  wrap semantics, etc.).
- Range-typed integers (`int<0..N>`) for loop indices and slot
  ranges.
- The distinction between `int` and `float` / `number` as
  propagated type metadata through expressions.

`scalar` and `number` remain available as "numeric type, class
unspecified" when the program doesn't need the integer class's
extra behavior.

### `map<K, V>` — compile-time literal-initialized lookup table

Two-parameter generic map type. Used extensively in demos for
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

Maps are **compile-time-initialized constants**. For runtime
key-value storage, use `dict` (below).

### `dict<K, V>` — runtime rotation-hashmap

`dict<K, V>` is the runtime-writable key-value store. It compiles
to a rotation-hashmap: a bundled-accumulator vector where each
entry is a rotation-binding of a value under its key's hash
(see `binding.md` §"Rotation binding"). Subscript access routes
through the runtime's `hashmap_get` / `hashmap_set`:

    dict<vector, vector> concept_memory;
    concept_memory[v_cat] = v_whiskers;
    concept_memory[v_dog] = v_bark;
    vector looked_up = concept_memory[v_cat];

- **Declaration** (`dict<K, V> d;`) emits `d = _VSA.hashmap_new()`
  — an empty accumulator. Initialized form `dict<K, V> d = ...;`
  is not yet specified (a literal-initialized `dict` would need
  its own syntax separate from `map`'s literal form).
- **Subscript read** (`d[k]`) dispatches to
  `_VSA.hashmap_get(d, k)`.
- **Subscript write** (`d[k] = v`) dispatches to
  `d = _VSA.hashmap_set(d, k, v)` — functional update; the name
  is rebound to the new accumulator.
- **Compound assignment** on a dict subscript (`d[k] += v`) is
  not yet specified; rejected at codegen.

The rotation-hashmap mechanism gives dict soft-lookup potential
(noisy-key retrieval) when the hash is made continuous; the
current prototype uses a bit-hash of the key bytes, so only
exact-key lookup works. Soft-lookup is future work per
`planning/open-questions/rotation-hashmap-as-language-feature.md`.

### `list<T>` — compile-time-dynamic collection

`list<T>` is the familiar Python/TypeScript list — a collection
of T values whose length is known at compile time (either set
explicitly or inferred from an initializer literal). Today it
compiles to a Python list:

    list<int> items = [10, 20, 30];
    foreach (int x in [10, 20, 30]) {
        total += x;
    }

Two declaration shapes (per user direction 2026-04-22 evening):

- **Compile-time dynamic**: `list<T> xs = [a, b, c];` — length
  determined by the initializer. The compiler knows the length
  at compile time; the runtime representation is a Python list.
- **Set memory allocation**: `list<T>[N] xs;` — fixed-size
  declared up front. Parses the same way as `var[N] xs : T`
  today; which surface form is preferred is an open question.

Subscript access, iteration, and common list operations work
via Python under the hood. Append at runtime is not a first-class
operation yet — the point of `list` in Sutra is compile-time
dynamism, not runtime-unbounded growth (that would require
substrate-level reallocation semantics not yet designed).

### `array<T, N>` (future — currently spelled `var[N] x : T`)

Fixed-size array of N elements of type T. Today spelled
`var[N] x : T` per the Candidate B surface-syntax decision. The
`array<T, N>` generic surface form may be added later for
TypeScript/C# familiarity; both desugar to the same underlying
Python list.

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

### `TYPE X = wait;` — explicit deferred initialization (2026-04-25)

    int answer = wait;
    // ... prep ...
    answer = 42;

`wait` is a literal that's only legal as the RHS of a typed var
declaration. It marks the declaration as "I will assign this before
the function returns — hold me to that." The codegen lowers it to
the same zero-of-type emission as the uninitialized `var X : TYPE;`
form. The validator enforces:

- Function scope only (top-level `wait` is rejected — SUT0133).
- Concrete type required; no `var x = wait;` (SUT0131).
- Initializer position only; `wait` outside a var-decl is a
  position error (SUT0130).
- At least one assignment to the wait-declared variable in the
  enclosing function body (SUT0132).

`wait` is the explicit-deferred-init form (Candidate D in
`planning/open-questions/no-null.md`). Use it when the deferral is
intentional and you want it visible at the declaration site; use
`var x : TYPE;` when you want a zero-initialized slot and don't
intend to override it.

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

## Classes exist — but only at compile time (2026-04-22)

User direction 2026-04-22 evening:

> Classes exist and are decently well defined, but classes only
> exist at compile time and they only exist so you do not do an
> illegal operation on them.

A **class** in Sutra is a compile-time tag that carries
enforcement rules — constraints on what operations are allowed
on values of that class. Classes do not exist at runtime; they
leave no runtime representation. Their whole point is to catch
illegal uses before the program runs.

Classes currently in the language:

- **`bool`** — compile-time defuzz counter, compile-time check
  that you're not treating a fuzzy as crisp.
- **`int`** — compile-time tag that enables augmented assignment
  and will enable integer-specific checks (bounds, mod-N, etc.)
  as those land.
- **`dict`**, **`list`** — compile-time collection classes that
  will eventually enforce element-type consistency and
  operation-legality (e.g. "you can't subscript a list with a
  string" if that's a rule we want).
- **`role`** — compile-time marker for semantic-binding declarations
  (distinct from rotation-bound `var`). Today a stub flag on
  VarDecl awaiting the learned-matrix binding implementation.

The TypeScript/C#/Python comparison the user uses: all the
conventional collection and scalar types should be available in
the source, even if they don't work exactly like their equivalents
in those languages. The class tags are what make the surface
syntax familiar while the underlying execution is Sutra-specific
(vector-space for scalars, rotation-hashmap for dict, etc.).

A class does not imply a vtable, runtime dispatch, or any heap
representation. It is a compile-time assertion: "this value is
of class X, so the compiler should reject operations that
aren't defined for X."

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
