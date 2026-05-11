# OS-blockers — the residual list

**Created:** 2026-05-10
**Trigger:** Emma 2026-05-10 — *"list all of this so-called 'honest
residual list.' All of this should be documented somewhere as the
things blocking us from making the operating system."*

This is the canonical list of work items that stand between the
current state of Sutra (a language toolchain that compiles TS to
substrate-pure PyTorch) and an actual operating system being
written in it (Yantra repo, separate from this one). Each item
includes the current state, the gap, what blocks what, and a
status line. Items get crossed off here as they ship.

## 1. JavaScriptObject operator overrides

**Status:** Mostly stubs. `js_add` is element-wise add only.

The `JavaScriptObject` class in stdlib is the inheritance root for
all transpiled TS classes (per the 2026-05-10 inheritance change).
It exists to absorb JavaScript's coercive semantics so TS programs
land correctly on the Sutra substrate. The MVP shipped only two
intrinsics (`wrap`, `js_add`). The full surface needs:

| Operator / function | What JS does | Current Sutra behavior | Gap |
|---|---|---|---|
| `a + b` | string concat if either is string; number add otherwise; loose coercion (`"1" + 1 === "11"`) | `js_add` does element-wise vector add; numeric-only | yes — branch on `AXIS_STRING_FLAG` |
| `a == b` | loose equality with coercion (`"1" == 1 === true`) | substrate `==` does cosine-fuzzy similarity | partial — coercion ladder not wired |
| `a === b` | strict equality, no coercion | not yet wired | yes — Emma 2026-05-10: `=== is defuzzify(a == b)` on the Sutra interpretation (more strictness, fuzzy-stripped) |
| `a - b` / `*` / `/` | numeric, with NaN propagation | runtime arithmetic on vectors | partial — NaN handling absent |
| `a < b`, `>` etc. | numeric for numbers, lex for strings | substrate comparison | yes — string-flag dispatch |
| `!a`, `Boolean(a)` | truthy/falsy table (0, "", null, undefined, NaN, false) | `is_true` polarizes but on truth axis only | yes — JS truthy table |
| `typeof a` | string `"number"`, `"string"`, `"object"`, `"undefined"`, etc. | not wired | yes — read flag axes, return string |
| `a in b`, `b instanceof T` | property/prototype check | not wired | yes — needs prototype chain spec |
| `[]` / `.prop` lookup | property access, returns `undefined` for missing | axon item / member access | partial — undefined sentinel missing |
| `JSON.parse / .stringify` | text round-trip | not wired | yes — string-axis encoding |

None of these block compilation. Real TS code will hit one every
few hundred lines as soon as the source isn't fully typed. The
2026-05-10 implementation pass started with `if`-without-`else`,
`===`, and a partial set; the rest land incrementally as real
programs surface the need.

## 2. `if` without `else`

**Status:** Was `UNSUPPORTED-STMT` in the TS transpiler. Shipped
2026-05-10 (this session) per Emma's "select-with-implicit-zero-else"
design — body is multiplied by `truth(cond)` and the missing else
contributes zero. Statement-form `if` now compiles.

## 3. No I/O primitives

**Status:** None wired.

Axon passing gives the *shape* of inter-program communication, and
the multi-program demo proves a vector can cross a serialization
boundary correctly. But there are no actual file, socket, timer,
device, or syscall primitives wired to substrate operations. A
program that needs to read `/proc/cpuinfo` has nothing to call.

Per Emma 2026-05-10: a kernel won't use embeddings — so the I/O
primitives need to work in an embedding-free mode (see item 6).

This is genuinely OS-design work, not language work. Lives in the
Yantra repo. The Sutra side might grow:
- A small `io` stdlib class declaring intrinsics like `read_file`,
  `write_file`, `open_socket`, `read_socket`, `sleep`, etc.
- Each intrinsic compiles to a substrate-side syscall vector and a
  monitoring-boundary host call (the only legitimate place numpy/
  Python runs).

Specific Yantra needs will dictate the surface. Sutra doesn't have
to pre-design it.

## 4. Lazy materialization on axons

**Status:** Not built.

The spec promises (per `planning/sutra-spec/axons.md` § "Lazy
evaluation across boundaries") that only the keys the receiver
references should actually cross the wire. Today the full bundle
crosses. Works fine for ~5 keys; at 12+ keys with LLM-embedded
fillers the rotation-binding capacity wall hits, but for the
typical OS payload (small strings + small numbers — see the
2026-05-10 OS-shaped demo) capacity is not an issue.

Implementation shape: a compile-time pass that walks the consumer's
`axon_item` calls to collect referenced keys, then rewrites the
producer's `axon_add` chain to skip the unreferenced ones. Cross-
program analysis across an import / linkage boundary. Tracked
under todo.md §"TS transpiler / Sutra postponed pieces" with the
"Multi-program axon passing demo" entry as the empirical
motivation.

## 5. Performance

**Status:** Inherent property — tensor ops on 868-d vectors per
primitive operation.

Many orders of magnitude slower than a conventional kernel. Fine
for prototype OS work; not fine for anything time-critical. Not
"a bug to fix" — a consequence of compiling every operation to a
substrate matmul. The mitigations are:

- Egglog matrix-chain fusion (collapse a chain of linear ops into
  one cached matrix) — already exists for some shapes, partially
  integrated. Tracked in todo.md §"Egglog — linearity analysis
  codegen."
- Smaller substrate (e.g. lower-dim embedding model for code that
  doesn't need nomic's 768d). Already supported via `atman.toml`
  and the per-program embedding-space override.
- Skip embeddings entirely when not needed (item 6).

Performance is a tradeoff dial, not a blocker. Yantra will
characterize what's actually too slow once real programs run.

## 6. Sutra-without-embeddings mode

**Status:** Not yet a first-class concept.

Per Emma 2026-05-10: *"I don't think that the kernel is going to be
using embeddings at all, because it's a kernel, and Sutra should be
able to be used without embeddings."*

Today every compiled Sutra program initializes a `_VSA` instance
with `semantic_dim + synthetic_dim`, eagerly tries to load an
Ollama embedding model, builds a codebook, etc. A program that
uses zero embeddings (no `basis_vector(...)` calls, no
`argmax_cosine` against a vector codebook, no `embed(string)`)
still pays this cost.

A real "kernel mode" Sutra needs:
- Compile-time detection: if the program never references the
  embedding subsystem, don't emit `_VSA.embed(...)`, don't load
  Ollama, don't allocate the semantic block.
- `_VSA.dim` collapses to just the synthetic block. Strings stay
  as codepoint arrays. Numbers stay on the synthetic axes.
- Bind/unbind still works (the rotation cache stores per-key
  matrices; those don't need embeddings, they just need a hash
  seed which can come from the key string).
- Axons still work (axon_add with string/number fillers
  per-key-permutes correctly without ever touching the embedding
  subsystem).

This is a meaningful but tractable change. Spec it in a planning
doc when starting; implementation is mostly subtraction (skip
the Ollama init when no embedding ops are used).

## What's NOT on this list

- Spec / implementation drift — that was the spec audit's job
  (2026-05-10). Drift is closed.
- TS transpiler surface coverage — feature-complete enough to
  attempt OS work. Remaining surface items (if-without-else done,
  module imports done, classes done, async done, Math done, enums
  done, JS-coercion overrides per item 1) are tracked above.
- The frozen NeurIPS submission — separate concern; lives at
  `paper/neurips/`. See `docs/neurips-2026.md`.

## When this list is "done"

When Yantra (`../Yantra/`) can compile a non-trivial OS-style
program in TS, the program crosses program boundaries via axons,
and at least basic syscalls (file I/O + sleep) work end-to-end.
At that point this doc gets archived or moved into Yantra's own
planning surface.

Items 1, 4, 5, 6 are mostly forward work. Item 2 is done. Item 3
is Yantra's call.
