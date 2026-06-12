# Primitive operations

The primitive operations the compiler recognizes as builtins are
listed below. The BUILTINS table in
`sdk/sutra-compiler/sutra_compiler/codegen_base.py` is the
authoritative list; this section describes what each does and
where it currently runs.

## The builtin set (updated 2026-05-28)

| Op | Arity | Purpose | Backend status |
|---|---|---|---|
| `basis_vector` | 1 | String → vector via the substrate's embedder | ✓ (Ollama) |
| `bind` | 2 | Rotation binding: `Q_role @ filler` | ✓ |
| `unbind` | 2 | Inverse rotation: `Q_role^T @ record` | ✓ |
| `bundle` | variadic ≥ 1 | Superposition: `sum(vs) / norm(sum(vs))` | ✓ |
| `displacement` | 2 | Vector subtraction: `a - b` | ✓ |
| `similarity` | 2 | Cosine similarity | ✓ |
| `argmax_cosine` | 2 | Cleanup: nearest codebook entry by cosine | ✓ |
| `select` | 2 | Softmax-weighted superposition over named options | ✓ |
| `compose` | 2 | Pointwise multiply (sign-flip permutation composition) | ✓ |
| `permute` | 2 | Sign-flip permutation (legacy; see below) | ✓ |
| `permutation_key` | 1 | Sign-flip key derivation | ✓ |
| `identity_permutation` | 0 | `ones(d)` sign-flip identity | ✓ |
| `vector_literal` | variadic floats | Frozen 1-d substrate tensor from float literals (`_VSA.vector_from_floats`) | ✓ |
| `matrix_literal` | variadic row-vectors | Frozen 2-d substrate tensor, rows stacked (`_VSA.matrix_from_rows` → `torch.stack`) | ✓ (2026-05-28) |
| `dot` | 2 | Inner product → 0-d tensor (`_VSA.dot` → `torch.dot`), substrate-pure | ✓ |
| `hadamard` | 2 | Elementwise/buffer product `a * b` (`_VSA.hadamard` → `torch.mul`) — each component independent; distinct from `*` (complex_mul, the single-number real/imag-axis product). Buffer arithmetic; computes a whole frame in one op. | ✓ (2026-06-11) |
| `snap` | 1 | Cleanup against a real attractor circuit | ✗ rejected (no cleanup circuit) |
| `make_rotation` | 1–2 | Build a Haar-random rotation matrix | ✗ rejected (substrate-level) |
| `compile_prototypes` | 1 | Compile a codebook to substrate-readable patterns | ✗ rejected (substrate-level) |
| `geometric_loop` | 3–4 | Eigenrotation loop with prototype matching | ✗ rejected (substrate-level) |

The four rejected builtins require a real attractor / cleanup
circuit that the current pure-tensor PyTorch substrate doesn't
have. They were operational on the retired fly-brain backend; on
the current backend, programs that use them are rejected at
codegen time.

`vector_literal` / `matrix_literal` are the source-level frozen-constant
constructors — the bake-back form for trained vector/matrix parameters and the
way to write a fixed lookup/permutation matrix in `.su`. `matrix_literal(r0, r1,
…)` takes row vectors (each typically a `vector_literal`) and stacks them on the
runtime dtype/device; it is consumed by `Tensor.MatrixMul`. Example in anger:
`demos/font/font.su`'s `cycle_step` builds a frozen 36×36 cyclic-permutation
matrix with `matrix_literal` and advances a recurring one-hot glyph cursor by
`MatrixMul(P, glyph)` — a substrate-state RNN. (Both skip the egglog
simplify post-pass: their args are pure literals, nothing to algebraically
rewrite, and lifting a large literal tree into egglog is pathologically slow.)

### Complex transcendentals (substrate-pure, lookup + eigenrotation)

The math intrinsics live in `stdlib/math.su` and lower to `_VSA` methods in
`codegen_pytorch.py`. They are NOT libm/torch-elementwise shortcuts — each
decomposes to a crosstalk lookup table + eigenrotation composition:

| Op | Form | Notes |
|---|---|---|
| `realExp(z)` | `e^(Re z)` | crosstalk-lookup leaf (`_exp_table`) |
| `imaginaryExp(z)` | `e^(i·Im z)` = `[cos, sin]` | eigenrotation; `cos`/`sin` are its real/imag projections, each with its own table (`_COS_VALUES`/`_SIN_VALUES`) |
| `cexp(z)` | `realExp(z) ⊗ imaginaryExp(z)` | the documented keystone (`⊗` = `complex_mul`) |
| `exp(x)` | `real(cexp(x))` | scalar-boundary real exponential |
| `ccos(z)` | `(e^(i·z)+e^(−i·z))/2` | complex-argument cosine (2026-05-17); vs `cmath.cos` ≤2e-4 |
| `csin(z)` | `(e^(i·z)−e^(−i·z))/(2i)` | complex-argument sine (2026-05-28); vs `cmath.sin` <2e-2 |
| `log`/`ln` | natural log via inverse codebook | real-axis; complex log deferred |

`ccos`/`csin` are built only from the verified-pure `cexp` keystone +
`complex_mul`/`complex_add`/`complex_sub` — no new leaf, no host branch, no
scalar extraction; for real argument they reduce to exactly `[cos a, 0]` /
`[sin a, 0]` (zero imaginary leakage, so the paper-cited real `cos`/`sin` are
untouched). See `planning/findings/2026-05-17-complex-argument-cosine-implemented.md`
and `2026-05-28-csin-complex-sine-shipped.md`.

### Trainable surfaces (constrain-train)

`select` carries a softmax **temperature** that is a trainable parameter — the
second *mechanism* constrain-train instance after the equality `==` cosine-scale
scalar (the one *shipped* instance). See `equality-and-defuzzification.md` and
the 2026-05-28 select-T findings; the full per-item training status is in the
website capabilities inventory.

## Binding (semantic + rotation)

Spec detail for `bind`/`unbind` is in `binding.md`. Summary:

- Two binding kinds: **semantic** (learned-matrix, `R @ filler`
  where R is fit from corpus data — deferred implementation) and
  **rotation** (role-seeded Haar-random orthogonal, currently the
  implementation of `bind` on both backends).
- **Sign-flip binding is retired** as the runtime mechanism (as
  of 2026-04-22). The `permute` / `permutation_key` /
  `identity_permutation` / `compose` builtins are retained as
  legacy sign-flip operations for programs that specifically want
  non-semantic ±1 diagonal matrices, but new code uses `bind` /
  `unbind` and gets rotation binding.
- The argument convention is **role-first**: `bind(role, filler)`
  and `unbind(role, record)`. Four of the existing `.su` demos
  were migrated to this convention in the 2026-04-22 pass.

## `displacement(a, b) = a - b`

Vector subtraction. Added 2026-04-22 as a builtin because bare `-`
on vectors is not supported by the operator path (binary operators
pass through to Python unchanged, and Python's `-` on numpy arrays
is elementwise — which happens to be what we want, but the
operator path doesn't carry the vector-type knowledge for the
subtraction to be spec-visible).

Named "displacement" because the cartography work's rank-0 learned
role matrix IS a displacement vector: `R @ v = v + d`. The
rank-0 case of Sutra's semantic binding is exactly `displacement`
applied symmetrically. The name is on-brand rather than ad-hoc.

Used primarily for analogy-style formulas like
`bundle(displacement(king, man), woman)` (see
`examples/king_queen_naive.su`).

## `bundle(v1, v2, ...)` — superposition

Sum + normalize. The current implementation returns
`sum(vs) / norm(sum(vs))`. Whether normalization is part of the
operation's semantics or a post-hoc convenience is one of the
open questions below.

## `similarity(a, b)` — cosine by default

Current implementation: cosine similarity, `dot(a, b) / (|a||b|)`.
The user's earlier framing flagged "cosine might be overused" and
suggested normalized-dot as a candidate alternative; that's an
open question not yet settled. The substrate-level operation
available cheaply may dominate the choice eventually.

## `argmax_cosine` vs `snap`

- `argmax_cosine(query, codebook)` — returns the codebook entry
  with the highest cosine similarity to the query. Pure-numpy
  operation, always available, what the demo path uses.
- `snap(v)` — symbolic "cleanup to the nearest attractor" on a
  substrate that actually has one. No such substrate is currently
  wired in the compiler, so it is rejected at codegen time on the
  PyTorch backend.

Whether the language should expose a single name that lowers
differently per substrate (so a program written with `snap` runs
on numpy by mapping `snap` to `argmax_cosine`) or keep the two
distinct is an open question.

## `select` is branching, not a vector op

`select(scores, options)` is the softmax-weighted-superposition
branching primitive. Spec for it lives in `control-flow.md`.

## Binary operators

Binary operators (`+`, `-`, `*`, `/`, `==`, `!=`, `<`, `>`, `<=`,
`>=`, `&&`, `||`) in `.su` source pass through to Python unchanged
in both codegens. This means:

- `a + b` on strings is Python string concatenation (used in
  `examples/fuzzy_dispatch.su`).
- `a + b` on two numpy vectors is elementwise addition (works,
  but not a spec-blessed operation — use `bundle` for the
  vector-sum semantics).
- `a - b` on two vectors is elementwise subtraction (works, but
  use `displacement(a, b)` for the semantic operation).
- `!` (unary not) is not supported — rewrite as an appropriate
  `permute` or `displacement` expression.

The "pass-through" nature of binary operators is an implementation
shortcut, not a design statement. A future pass should decide
which operators are spec operations (and with what semantics per
type) vs. which are Python artifacts.

## Open questions

- **Default similarity.** Cosine, dot, normalized dot, or
  substrate-dependent. Still open.
- **`bundle` semantics.** Straight sum? Sum-then-normalize?
  Weighted sum? Substrate-specific superposition?
- **`snap` vs. `argmax_cosine` unification.** One name with
  backend-dispatched lowering, or stay distinct?
- **Semantic-role matrix fitting.** When `role X =
  learned_from(data)` lands (deferred, see queue.md /
  todo.md), what fitting procedure — lstsq, ridge, Procrustes,
  low-rank? Substrate-dependent.
- **Vector binary operators.** Are elementwise `+` / `-` / `*`
  on two vectors spec operations, or are `bundle` /
  `displacement` / a hypothetical scale the only blessed paths?
- **Additional primitives.** Rotation (as a first-class op),
  projection, scalar multiplication. Not in BUILTINS today; the
  algebraic simplification a compiler would need for implicit
  concurrency might pull one or more of these in.

## Prior-art pointer

The cartography work (Leonhart, *Latent space cartography applied
to Wikidata* — sibling repo `EmmaLeonhart/latent-space-cartography`)
showed that the rank-0 case of a learned role matrix (a
displacement vector) lives consistently across multiple frozen LLM
embedding spaces. That empirical result is the foundation for
Sutra's semantic-binding commitment. Specific numbers from that
work — predicate counts, correlation values — should be cited
from the cartography source itself rather than quoted here (see
CLAUDE.md note on prior-work claims).
