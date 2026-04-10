# VSA Builtins

This file declares the formal signatures of Akasha's VSA builtin
functions. Each entry gives a signature in terms of the primitive
types from `05-type-system.md`, the semantic behavior, and — where
relevant — which runtime tier the operation belongs to under
`02-operations.md`.

The informal descriptions in `02-operations.md` are the *prose*
explanation of what these operations do. This file is the *signature*
declaration: what the parser, name-resolver, and type-checker should
treat as pre-declared in every Akasha compilation unit.

## Status and scope

These functions are **implicit globals**. They do not need to be
imported or declared at the top of a source file — every Akasha
translation unit sees them in its global scope, the same way a C
program sees `printf` once `<stdio.h>` is included or a Python
program sees `len` unconditionally.

The current SDK validator (`sdk/akasha-compiler/`) is *permissive*
about bareword calls: any identifier in call position is accepted
without checking that it resolves to a declared function. That will
change in v0.2 when name resolution lands, at which point undeclared
builtins would start firing a diagnostic on every real Akasha program
in the repo. Declaring the builtins in this file now heads off that
diagnostic avalanche — v0.2's name resolver will treat the entries
below as pre-declared and skip them during the "undefined symbol"
pass.

All of the builtins here are referenced by at least one `.ak` file
in the repo today. The ground truth for what needs to be declared
is the union of identifiers used in call position across
`fly-brain/*.ak`, `examples/*.ak`, and `akasha-demo-program.ak`.

## Notation

Signatures use the same declaration shape as user-written Akasha
functions, minus the function body:

```
function <return-type> <name>(<param-type> <param-name>, ...);
```

A trailing `...` in the parameter list denotes a variadic tail of
the preceding type. `T[]` denotes an array of `T` (see
`05-type-system.md` and the `22_array_literal.ak` / `23_subscript_access.ak`
test corpus for the array literal and subscript syntax).

## Algebraic builtins

These are the O(1) pure-algebra operations from tier 2 of
`02-operations.md`. Under the current fly-brain runtime
(`fly-brain/vsa_operations.py`), they execute in numpy on the host —
not on the mushroom body substrate — because the MB has no natural
analogue for sign-flip multiplication. A fully-biological runtime
would need a different compilation target for these; see
`19-substrate-candidates.md` and STATUS.md §3 in `fly-brain/`.

### `bind`

```
function vector bind(vector a, vector b);
```

Sign-flip binding: returns `a * sign(b)` elementwise. Self-inverse —
`bind(a, b) == unbind(a, b)` when the binding scheme is sign-flip.
The result is dissimilar to both inputs. Encodes key-value pairs and
role-filler structures. See `02-operations.md` §Bind for the
empirical justification of sign-flip over Hadamard on natural
embedding spaces.

### `unbind`

```
function vector unbind(vector role, vector bound);
```

Inverse of `bind`. For sign-flip binding this is algebraically
identical to `bind(role, bound)`; the separate name exists so that
user code documents intent and so that a future rotation-binding
backend can distinguish the bind and unbind paths without a source
rewrite.

### `bundle`

```
function vector bundle(vector first, vector... rest);
```

Elementwise superposition: `first + rest[0] + rest[1] + ...`.
Commutative, associative. Signal-to-noise degrades as more items are
bundled — this is a fundamental capacity limit of the substrate, not
a runtime bug. At least one operand is required; the variadic tail
may be empty (in which case `bundle(v) == v`).

### `similarity`

```
function fuzzy similarity(vector a, vector b);
```

Cosine similarity in `[-1, 1]`, returned as a `fuzzy`. The default
"how close are these?" operation and the primary bridge from the
vector world to the defuzzification machinery in
`04-defuzzification.md`. Magnitude is discarded — use Euclidean
distance directly if binding strength matters.

### `permute`

```
function vector permute(permutation p, vector v);
```

Apply a permutation key to a vector. For sign-flip VSA this is
pointwise multiplication by the `±1` mask stored in `p`. Involutive
when `p` is involutive (which the sign-flip permutations built by
`permutation_key` always are). Distributes over `bind`:

```
permute(p, bind(a, b)) == bind(permute(p, a), b)
                      == bind(a, permute(p, b))
```

This distributivity is the reason negation-as-permutation compiles
cleanly into the fly-brain prototype-table lookup — see
`fly-brain/STATUS.md` §Technical Insight 1.

### `compose`

```
function permutation compose(permutation a, permutation b);
```

Compose two permutations into a single permutation such that
`permute(compose(a, b), v) == permute(a, permute(b, v))`. For
sign-flip permutations this is pointwise multiplication of the
underlying `±1` masks. Composition is associative; for involutive
permutations it is also commutative.

## Construction builtins

These materialize primitive values from string names or from the
substrate's default state. They are side-effecting relative to the
runtime's codebook: calling `basis_vector("smell")` the second time
returns the same vector as the first call, within one execution.

### `basis_vector`

```
function vector basis_vector(string name);
```

Return the hypervector registered to `name` in the current runtime's
codebook, creating a fresh random hypervector if none exists. Within
one execution, `basis_vector(n)` is deterministic in `n` — two calls
with the same string return equal vectors. This is the standard way
to introduce a named atom into an Akasha program.

The name is a compile-time string; the mapping from name to vector
is an execution-time property of the runtime. Two runs of the same
program may produce different basis vectors, but the *structure* of
the program (which atoms are compared, which are bound) is
reproducible.

### `permutation_key`

```
function permutation permutation_key(string name);
```

Return the permutation registered to `name`, creating a fresh
involutive sign-flip permutation if none exists. Every permutation
produced by this builtin is its own inverse (`permute(p, permute(p, v)) == v`).
This is the primitive that implements source-level `!` at the
substrate level: `!X` compiles to `permute(permutation_key("NOT_X"), X)`
in the query rewrite strategy described in `STATUS.md`.

### `identity_permutation`

```
function permutation identity_permutation();
```

Return the identity permutation: `permute(identity_permutation(), v) == v`
for every `v`. Used as a neutral element when a program variant wants
to *not* apply a negation to one of its axes — see the Program A /
Program B / Program C / Program D dispatch in
`fly-brain/permutation_conditional.ak`.

## Non-algebraic builtins

These belong to tier 3 of `02-operations.md`: they require
substrate-level machinery beyond pure vector algebra. In the
fly-brain runtime, `snap` is the one builtin that actually executes
on the mushroom body circuit.

### `snap`

```
function vector snap(vector noisy);
```

Cleanup / discretization. On the fly-brain substrate, `snap` encodes
`noisy` as projection-neuron input currents, runs the spiking
mushroom body simulation for `snap_duration_ms` (default 300 ms),
and decodes the Kenyon-cell population activity back to a
hypervector. The APL-enforced 5% KC sparsity is structurally
identical to VSA cleanup — hence the substrate mapping described in
`fly-brain/METHODOLOGY.md`.

**Runtime contract (fixed frame):** every `snap` call inside a
single program execution must share the same PN→KC connectivity
matrix, or else prototype-table comparisons are meaningless. The
reason and the measured numbers are in `fly-brain/STATUS.md`
§Technical Insight 2. Enforcement is currently a runtime convention
(`FixedFrameFlyBrainVSA` subclass); the medium-term compilation
path in todo.md promotes it to a compile-time guarantee.

### `argmax_cosine`

```
function vector argmax_cosine(vector query, vector[] candidates);
```

Return the element of `candidates` with the largest cosine
similarity to `query`. The biological analogue is "N MBONs compete
for a winner" when `candidates` is the prototype table from a
compiled if-tree. The `candidates` argument is an array literal or
an array-typed variable; see `22_array_literal.ak` for the literal
syntax.

Ties are broken by index order. `candidates` must be non-empty —
passing an empty array is a runtime error (it will become a
compile-time error once name resolution and type inference land in
v0.2).

## Summary table

| Name | Signature | Tier | Runs on brain? |
|------|-----------|------|----------------|
| `bind` | `vector, vector -> vector` | Algebraic | No (numpy) |
| `unbind` | `vector, vector -> vector` | Algebraic | No (numpy) |
| `bundle` | `vector, vector... -> vector` | Algebraic | No (numpy) |
| `similarity` | `vector, vector -> fuzzy` | Algebraic | No (numpy) |
| `permute` | `permutation, vector -> vector` | Algebraic | No (numpy) |
| `compose` | `permutation, permutation -> permutation` | Algebraic | No (numpy) |
| `basis_vector` | `string -> vector` | Construction | No |
| `permutation_key` | `string -> permutation` | Construction | No |
| `identity_permutation` | `() -> permutation` | Construction | No |
| `snap` | `vector -> vector` | Non-algebraic | **Yes** (MB circuit) |
| `argmax_cosine` | `vector, vector[] -> vector` | Non-algebraic | No (host cosine argmax) |

## Open questions tracked elsewhere

- **Variadic `bundle` vs binary `bundle` + fold.** The current SDK
  accepts both, and the fly-brain runtime exposes a variadic form.
  The question of which is canonical at the language level is in
  `17-open-questions.md`.
- **Map lookup with vector keys.** `BEHAVIOR_OF[winner]` in
  `permutation_conditional.ak` depends on cosine-nearest semantics
  rather than bit-identical key equality. That's specified in
  `05-type-system.md` §`map<K, V>` as an explicit open question.
- **Generalized boolean compilation.** `permute` cleanly compiles
  source-level `!`, but there is no known VSA-to-substrate
  compilation scheme for general `&&`/`||`. This is the first
  long-term research question in `fly-brain/STATUS.md`.
