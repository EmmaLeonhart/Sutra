# Sutra — Syntax reference

A concise reference for the language as implemented in this
archive. Every construct shown here is exercised by the example
programs under `examples/` and the test suite under
`sdk/sutra-compiler/tests/`. Speculative or unimplemented
features are not listed.

## Source files

A Sutra program lives in a `.su` file. Comments use `//`
(line) and `/* */` (block). The compiler entry point is

```bash
PYTHONPATH=sdk/sutra-compiler python -m sutra_compiler --run path/to/file.su
```

Every program declares a `main` function returning a value;
the runner prints that value's nearest-string lookup.

## Primitive classes

Every runtime value is a fixed-width vector laid out as
`[ semantic_block | synthetic_block ]`. The class on a
declaration tells the compiler which axes carry meaning for
that value:

| Class | Carrier | Notes |
|---|---|---|
| `vector` | full extended layout | the universal type |
| `int` | synthetic real-axis (integer-valued) | |
| `float` | synthetic real-axis | |
| `complex` | synthetic real + imag axes | |
| `bool` | synthetic truth axis, polarized | |
| `fuzzy` | synthetic truth axis, unpolarized | |
| `trit` | three-valued Kleene logic on the truth axis | |
| `char` | semantic block, char-flag set | |
| `string` | sequence-of-char layout | source-level only |
| `permutation` | role-rotation seed | |
| `matrix` | two-dimensional | precomputed at compile time |
| `map<K,V>` | static codebook, see "Maps and codebooks" below | |
| `dict<K,V>` | rotation-hashmap accumulator, see "Dictionaries" below | |
| `scalar` | numeric host scalar | for weights and similarities |
| `void` | no result | function returns |

## Declarations

Variables are declared with their type before the name:

```c
vector v = basis_vector("hello");
int x = 9;
float pi = 3.14;
const float TAU = 6.28;
```

Mutable per-iteration state inside a loop body is declared
with `slot`:

```c
slot int x = 9;
loop addNumber(x < 11, x);   // x is mutated by reference
```

`var` introduces a typed local that is reassigned within a
function body.

## Functions

Functions declare their parameter types and return type:

```c
function vector make_record(vector name, vector color, vector shape) {
    return bundle(
        bind(r_name,  name),
        bind(r_color, color),
        bind(r_shape, shape)
    );
}
```

The program's entry point is `main`:

```c
function string main() {
    return decode_field(rec, r_color);
}
```

The runner invokes `main()`, applies `nearest_string` against
the codebook for `string`-typed returns, and prints the
result. There is no `print` primitive; output happens at the
boundary.

## Vector primitives

Three operations come from VSA literature, lifted onto the
substrate:

| Primitive | Type | What it does |
|---|---|---|
| `basis_vector(string)` | `vector` | substrate-embedded basis vector for a content-addressed key |
| `embed(string)` | `vector` | substrate's native embedding of a literal |
| `bind(role, filler)` | `(vector, vector) -> vector` | role-seeded Haar-orthogonal rotation applied to filler |
| `unbind(role, bound)` | `(vector, vector) -> vector` | inverse rotation, recovers the filler |
| `bundle(v1, v2, ...)` | `(vector...) -> vector` | normalized superposition |
| `similarity(a, b)` | `(vector, vector) -> scalar` | cosine similarity |
| `argmax_cosine(query, codebook)` | `(vector, [vector]) -> vector` | nearest codebook entry |

The textbook VSA Hadamard binding is **not** the implemented
primitive: empirically, Hadamard collapses on dense correlated
embeddings (see §3.2 of the paper). Rotation binding is the
shipped operator.

## Maps and codebooks

A `map<K, V>` is a compile-time codebook: a static table of
(key, value) pairs known at compile time. Keys are typically
vectors and values are typically strings, used for the
"recover the vector, name what it is" pattern at the IO
boundary:

```c
map<vector, string> FILLER_NAME = {
    f_alice:  "alice",
    f_bob:    "bob",
    f_red:    "red"
};
```

Lookup uses the bracket syntax:

```c
return FILLER_NAME[winner];
```

Internally, the codebook is materialised at compile time as a
parallel pair of arrays — the keys stacked into a single
substrate matrix, and the values held host-side. The lookup
runs cosine similarity between the query vector and the key
matrix in one matmul, takes the argmax, and indexes into the
host-side value array at the IO boundary. There is no
runtime accumulator and no `unbind` — the codebook contents
are fixed when the program is compiled, so the lookup is a
single substrate matmul plus an output-boundary index.

## Dictionaries

A `dict<K, V>` is the runtime rotation-hashmap. Where
`map<K, V>` is a fixed compile-time codebook, `dict<K, V>` is
a mutable accumulator vector that grows additively as the
program adds entries. The accumulator is a single substrate
vector; storage and retrieval are pure rotation-binding
operations:

```c
function vector concept_demo() {
    dict<vector, vector> concept_memory = new dict();
    concept_memory.Add(cat,  whiskers);
    concept_memory.Add(dog,  bark);
    return concept_memory[cat];           // retrieved value
}
```

Both surface forms are supported: subscript-assign
(`d[k] = v`) and the C#-style method form (`d.Add(k, v)`)
lower to the same functional update. Subscript-read
(`d[k]`) returns the raw recovered vector. Both forms compile
to:

```
new dict()        -> _VSA.hashmap_new()        -> zero vector
d[k] = v          -> d = _VSA.hashmap_set(d, k, v)
d.Add(k, v)         (synonym for the above)
                  -> acc + bind(k, v)
d[k]              -> _VSA.hashmap_get(d, k)
                  -> unbind(k, acc)             (raw, no cleanup)
```

Capacity at d=868 is approximately 32 keys with clean
recovery against a 200-filler codebook (90% accuracy at
k=48); see `experiments/rotation_hashmap_capacity.py` and
the corresponding finding for the curve.

## Conditionals

Sutra has no `if`/`else` control flow. Branches are expressed
as **fuzzy weighted superposition** — every branch contributes
to the result, weighted by its similarity to the query
condition:

```c
function string fuzzy_decide(
    vector smell, vector hunger,
    vector beh_PH, vector beh_PF, vector beh_AH, vector beh_AF
) {
    vector query = bind(smell, hunger);
    scalar w_PH = similarity(query, proto_PH);
    scalar w_PF = similarity(query, proto_PF);
    scalar w_AH = similarity(query, proto_AH);
    scalar w_AF = similarity(query, proto_AF);
    vector result =
        w_PH * beh_PH + w_PF * beh_PF +
        w_AH * beh_AH + w_AF * beh_AF;
    return BEHAVIOR_NAME[argmax_cosine(result, [b1, b2, b3, b4])];
}
```

The Kleene three-valued connectives `&&`, `||`, `!` are
Lagrange-interpolated polynomials: exact on the discrete
truth grid `{−1, 0, +1}`, smooth and differentiable
everywhere else.

## Loops

Two top-level forms:

### Compile-time unroll: `loop (N) { body }`

Unrolls at compile time. The body is emitted N times in
sequence, no runtime iteration. Inside the body, `iterator`
is the per-copy compile-time constant.

### Runtime tail-recursive loops

Four declared-function forms whose parameters are the
recurrent state. The body uses `pass` to yield the next
iteration's values; call sites use the `loop` prefix:

```c
do_while addNumber(x < 11, int x) {
    pass x + 1;
}

function int main() {
    slot int x = 9;
    loop addNumber(x < 11, x);
    return x;
}
```

| Form | Semantics |
|---|---|
| `do_while NAME(...)` | body runs once, condition checked between iterations |
| `while_loop NAME(...)` | condition checked first, body skipped if false |
| `iterative_loop NAME(...)` | runs N times; body sees `iterator` (N can be runtime) |
| `foreach_loop NAME(...)` | walks a binding-array; body sees `element` |

All four compile to substrate-pure soft-halt RNN cells with
constant state-vector width. Termination uses substrate
primitives (`heaviside`, `saturate_unit`); the host driver
runs a thin tick-loop that exits when the halt scalar
saturates.

The retired form is C-style imperative loops
(`while (cond) { body }`, `for (init; cond; step) { body }`).
Those did not survive the substrate-purity audit.

## Compilation pipeline

```
.su source
   |  (1) lex + parse
   v
   AST
   |  (2) inline + simplify  (stdlib operator inlining; egglog
   v                          algebraic simplification + CSE)
   simplified AST
   |  (3) codegen             (emit Python module + inline
   v                           runtime class)
   self-contained .py
   |  (4) compile-time substrate population
   v                          (embed_batch, prewarm_rotation_cache,
                               populate_sutradb)
   warm runtime artifact
   |  (5) execute             (CUDA if available; CPU fallback)
   v
   output vector -> nearest_string -> label
```

Stages 1–4 run at compile time; stage 5 is the runtime
forward pass. Every compile-time decision (extended-state-
vector dimensions, codebook contents, role rotations, SutraDB
path) is baked into the emitted source.

## Substrate-purity invariants

The compiler enforces three invariants on every primitive:

1. **Every primitive runs on the substrate.** numpy is
   permitted at compile time (codebook construction, rotation
   pre-warm) but never on the runtime hot path.
2. **No scalar extraction inside an operation.** A primitive
   may not unpack a Python float from a substrate vector, do
   scalar arithmetic, and pack the result back.
3. **No Python control flow inside an operation.** Loop halt
   uses substrate primitives (`heaviside`, `saturate_unit`)
   in place of Python ternaries.

Violations are caught at codegen time.

## Type checking

Type information is read by the inliner and the layout pass
before the tensor graph is built. The type checker is
opinionated rather than strict: a divergent assignment warns
and still emits a graph, because the runtime guarantee is
mathematical not structural — a type mismatch produces a
semantically meaningless but mathematically valid output
rather than a runtime exception. The compiler catches the
class of error that would otherwise pollute the loss
silently.
