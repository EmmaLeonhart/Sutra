# VSA Builtins

This file declares the formal signatures of Sutra's VSA builtin
functions. Each entry gives a signature in terms of the primitive
types from `05-type-system.md` and the semantic behavior. Every
builtin is meant to execute on the substrate at runtime; where the
current fly-brain implementation runs an op on numpy instead, that
is recorded as a limitation of the implementation, not a property
of the op.

The informal descriptions in `02-operations.md` are the *prose*
explanation of what these operations do. This file is the *signature*
declaration: what the parser, name-resolver, and type-checker should
treat as pre-declared in every Sutra compilation unit.

## Status and scope

These functions are **implicit globals**. They do not need to be
imported or declared at the top of a source file — every Sutra
translation unit sees them in its global scope, the same way a C
program sees `printf` once `<stdio.h>` is included or a Python
program sees `len` unconditionally.

The current SDK validator (`sdk/sutra-compiler/`) is *permissive*
about bareword calls: any identifier in call position is accepted
without checking that it resolves to a declared function. That will
change in v0.2 when name resolution lands, at which point undeclared
builtins would start firing a diagnostic on every real Sutra program
in the repo. Declaring the builtins in this file now heads off that
diagnostic avalanche — v0.2's name resolver will treat the entries
below as pre-declared and skip them during the "undefined symbol"
pass.

All of the builtins here are referenced by at least one `.su` file
in the repo today. The ground truth for what needs to be declared
is the union of identifiers used in call position across
`fly-brain/*.su`, `examples/*.su`, and `sutra-demo-program.su`.

## Notation

Signatures use the same declaration shape as user-written Sutra
functions, minus the function body:

```
function <return-type> <name>(<param-type> <param-name>, ...);
```

A trailing `...` in the parameter list denotes a variadic tail of
the preceding type. `T[]` denotes an array of `T` (see
`05-type-system.md` and the `22_array_literal.su` / `23_subscript_access.su`
test corpus for the array literal and subscript syntax).

## Vector builtins

These are the vector operations defined in `02-operations.md`. Each
is meant to run on the substrate. Under the current fly-brain runtime
(`fly-brain/vsa_operations.py`), several of them still execute in
numpy on the host because no substrate mapping has been wired up yet —
the mushroom body has no natural analogue for sign-flip
multiplication, and a biological mapping for bind/unbind/bundle
requires a different circuit than the MB cleanup the runtime
currently uses. That is a gap to close in the implementation, not a
spec-sanctioned execution mode. See `19-substrate-candidates.md` and
queue.md §3 in `fly-brain/` for the candidate mappings.

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
`fly-brain/queue.md` §Technical Insight 1.

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
to introduce a named atom into an Sutra program.

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
in the query rewrite strategy described in `queue.md`.

### `identity_permutation`

```
function permutation identity_permutation();
```

Return the identity permutation: `permute(identity_permutation(), v) == v`
for every `v`. Used as a neutral element when a program variant wants
to *not* apply a negation to one of its axes — see the Program A /
Program B / Program C / Program D dispatch in
`fly-brain/permutation_conditional.su`.

## Substrate-graph builtins

These are the ANN / vector-graph operations from `02-operations.md`.
In the fly-brain runtime, `snap` is the one builtin that actually
executes on the mushroom body circuit end-to-end today.

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
`fly-brain-paper/paper.md` (formerly `fly-brain/METHODOLOGY.md`).

**Runtime contract (fixed frame):** every `snap` call inside a
single program execution must share the same PN→KC connectivity
matrix, or else prototype-table comparisons are meaningless. The
reason and the measured numbers are in `fly-brain/queue.md`
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
an array-typed variable; see `22_array_literal.su` for the literal
syntax.

Ties are broken by index order. `candidates` must be non-empty —
passing an empty array is a runtime error (it will become a
compile-time error once name resolution and type inference land in
v0.2).

## Summary table

| Name | Signature | Runs on substrate today? |
|------|-----------|---------------------------|
| `bind` | `vector, vector -> vector` | No — numpy, gap to close |
| `unbind` | `vector, vector -> vector` | No — numpy, gap to close |
| `bundle` | `vector, vector... -> vector` | No — numpy, gap to close |
| `similarity` | `vector, vector -> fuzzy` | No — numpy, gap to close (monitoring readout also uses numpy, which is allowed) |
| `permute` | `permutation, vector -> vector` | No — numpy, gap to close |
| `compose` | `permutation, permutation -> permutation` | Compile-time construction on numpy, allowed |
| `basis_vector` | `string -> vector` | Compile-time construction, allowed |
| `permutation_key` | `string -> permutation` | Compile-time construction, allowed |
| `identity_permutation` | `() -> permutation` | Compile-time construction, allowed |
| `snap` | `vector -> vector` | **Yes** — MB circuit |
| `argmax_cosine` | `vector, vector[] -> vector` | No — numpy, gap to close |

## Open questions tracked elsewhere

- **Variadic `bundle` vs binary `bundle` + fold.** The current SDK
  accepts both, and the fly-brain runtime exposes a variadic form.
  The question of which is canonical at the language level is in
  `17-open-questions.md`.
- **Map lookup with vector keys.** `BEHAVIOR_OF[winner]` in
  `permutation_conditional.su` depends on cosine-nearest semantics
  rather than bit-identical key equality. That's specified in
  `05-type-system.md` §`map<K, V>` as an explicit open question.
- **Generalized boolean compilation.** `permute` cleanly compiles
  source-level `!`, but there is no known VSA-to-substrate
  compilation scheme for general `&&`/`||`. This is the first
  long-term research question in `fly-brain/queue.md`.
