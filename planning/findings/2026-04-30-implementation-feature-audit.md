# Sutra implementation feature audit

**Date:** 2026-04-30
**Purpose:** Inventory every meaningfully-implemented language /
runtime / compiler feature so we stop losing track of them.
**Why this exists:** the Lagrange-interpolation-in-paper incident
showed that a real, defensible technical contribution had been
shrunk to a one-line throwaway in the paper, and the reviewer
correctly flagged it as "vague." That kind of underselling
probably happens to other features too. This doc enumerates
*what's actually built* so paper edits can lift specific items
into focus rather than relying on memory.

Each entry has: name, where it lives in the codebase, what it
does, and a `[NOTE]` line marking either:

- ⭐ **strong, undersold in the paper** — should get more weight
- ✓ **normal feature** — implemented, in the paper at appropriate
  scale
- 🚫 **NOT implemented** despite being parseable/discussed (so we
  don't overclaim)

---

## 1. Language surface (parser / AST / lexer)

### Types

- `int`, `float`, `complex`, `char`, `bool`, `fuzzy`, `vector`,
  `string` (`ast_nodes.py:32`, `parser.py`)
- All numeric types live on the same vector: `int`/`float` use
  `synthetic[AXIS_REAL]` only; `complex` uses both real and
  imaginary axes; `char` adds a `synthetic[AXIS_CHAR_FLAG] = 1`
  marker.
- `bool` is a subclass of `fuzzy`, not crisp — fuzzy-by-default.
- ⭐ **Strong, undersold.** The unified vector representation
  across primitive types is the technical foundation that lets
  the compiler treat everything as a tensor op. The paper
  mentions the extended-state-vector layout briefly (§3.2) but
  doesn't lean on the *uniformity* claim.

### Literals

- `int`, `float`, `imaginary` (e.g. `3i`), `complex` (e.g. `2 + 3i`),
  `string`, `char`, `bool`, **`unknown`** (`U`), **`wait`**
  (`ast_nodes.py:54-126`).
- ⭐ **`unknown` as a first-class literal**: this is the third
  value of Kleene three-valued logic. The paper now talks about
  Kleene 3VL (§1.2-1) but doesn't mention that you can write `U`
  directly in source.
- 🚫 `wait`: literal exists in the lexer/parser, demonstrated in
  `examples/wait_keyword_demo.su`, but the runtime semantics are
  underspecified — needs a separate audit before claiming.

### String interpolation

- `InterpolatedString` AST node (`ast_nodes.py:126`).
- ✓ Implemented at parse time; lowering is straightforward.

### Casts

- Regular `CastExpr` (`v as complex`)
- `UnsafeCastExpr` (`v unsafe_as complex` — bypasses type check
  with explicit grep-able marker)
- `UnsafeOverrideExpr` (third escape hatch — most aggressive)
- ⭐ **Strong, undersold.** Three-tier casting with explicit
  grep-able forbidden patterns is the audit-friendly version of
  unsafe-cast. The paper doesn't mention this at all.

### Defuzzification

- `DefuzzyExpr` (`defuzzy v`) — the AST/parser node for the
  recursive `is_true` / defuzzify operation.
- Runtime: `_VSA.defuzzify_trit(v, iters=10, beta=2.0)` —
  iterative Lagrange-poly application that polarizes a fuzzy
  value toward {-1, 0, +1} without binarizing.
- ⭐ **Strong, undersold.** Polarizes-but-doesn't-binarize is the
  whole point of fuzzy semantics surviving compilation. The
  paper doesn't really mention the operator.

### Embed expression

- `EmbedExpr` (`embed("hello")`) — runtime-fetched LLM embedding,
  distinct from compile-time `basis_vector("...")` lookup.
- Two distinct surfaces: `basis_vector` for compile-time codebook
  entries (deterministic, in the .sdb file), `embed` for runtime
  on-demand fetches (still cached, but not in the codebook).

### Operators

- Binary: arithmetic (`+ - * / %`), comparison (`== != < > <= >=`),
  logical (`&& || !`), bitwise — all defined in `ast_nodes.py:191`
- Unary: `! - +` plus prefix sign forms
- Postfix: `++ --`
- Assignment: `=` plus compound forms `+= -= *= /=`
- Subscript: `arr[i]` and `map[key]`

### Control flow surface (parses, but not all execute)

- `if/else`, `while`, `for`, `foreach`, `do-while`, `try` — parse,
  AST nodes exist
- ⭐ **The runtime form is different.** Sutra compiles all of these
  to substrate-pure forms (softmax-weighted superposition for
  `if`, RNN-cell unroll for `while`, etc.), not host-side
  branches. This is one of the core claims of the paper, but the
  *mapping* from source surface to substrate form is barely
  described.

### Loop function declarations (the canonical loop form)

- `LoopFunctionDecl` (`ast_nodes.py:370`) — first-class declared
  loop function. Four kinds: `do_while`, `while_loop`,
  `iterative_loop`, `foreach_loop`.
- Body uses `pass values;` or `return NAME(args);` (tail-recursive
  yield).
- `LoopCallStmt` (`ast_nodes.py:420`) — call site.
- ✓ In the paper as §1.2 contribution 3 and §3.3.
- ⭐ **`pass values` vs `return NAME(args)` equivalence** — both
  surfaces compile to the same recurrent-step. Tail-call surface
  is the principled form; `pass` is the imperative-flavored
  surface. Paper doesn't mention this dual-surface explicitly.

### Class declarations

- `ClassDecl`, `MethodDecl` (`ast_nodes.py:516, 527`) parse
- 🚫 Encapsulation rules (no closure across class boundary) parse
  but are NOT enforced. Paper §6.1 acknowledges this as future
  work.

### `slot` keyword

- Slot-typed variables get a 2D Givens plane in the function-scope
  state vector. Compiler tracks per-function `_slot_vars: dict[str, int]`
  (`codegen_base.py:263`).
- ⭐ **Strong, undersold.** Slots = static allocation of 2D rotation
  planes for state variables that need to survive across a loop's
  recurrent steps. This is *how* the constant-memory tail
  recursion works in practice. Paper doesn't surface this.

---

## 2. Runtime primitives (the `_TorchVSA` class in `codegen_pytorch.py`)

### VSA core

| Method | Line | Purpose |
|---|---:|---|
| `bind(role, filler)` | 543 | Haar-random orthogonal rotation `R_role @ filler` |
| `unbind(role, record)` | 551 | Inverse via matrix transpose |
| `bundle(*vectors)` | 559 | Normalized sum |
| `bundle_of_binds(*pairs)` | 577 | Fused bind+bundle (compile-time bundle of role-filler pairs) |
| `zero_vector()` | 571 | Zero-init constructor |

### Hash maps

| Method | Line | Purpose |
|---|---:|---|
| `hashmap_new()` | 608 | Empty rotation hashmap |
| `hashmap_set(acc, k, v)` | 613 | Functional update via rotation |
| `hashmap_get(acc, k)` | 618 | Lookup via inverse rotation |

⭐ **Strong, undersold.** "Rotation hashmap" is a real working
data-structure primitive. To the authors' knowledge it's the
first use of a high-dimensional rotation pattern as a hash map's
substrate. Paper §1.2 contribution 4 mentions this; the
underlying runtime primitive is solid.

### Synthetic-dimension slots (Givens planes)

| Method | Line | Purpose |
|---|---:|---|
| `_slot_plane(slot_idx)` | 632 | Index → 2D Givens plane spec |
| `slot_store(state, idx, x)` | 648 | Write scalar to slot |
| `slot_load(state, idx)` | 657 | Read scalar from slot (substrate-pure, no `.item()`) |
| `rotate_slot(state, idx, θ)` | 739 | In-plane rotation by angle θ |

⭐ **Strong, undersold.** Each function-scope slot variable gets
its own 2D Givens plane. Reads and writes are matrix-vector ops,
not Python scalar extraction. This is the load-bearing mechanism
for "no scalar extraction inside an operation" (the
substrate-purity rule).

### Binding arrays

| Method | Line | Purpose |
|---|---:|---|
| `array_from_literal(*values)` | 673 | Build a substrate vector with `arr[0]=length`, `arr[1..]=elements` |
| `array_length(arr)` | 685 | Read length axis |
| `array_get(arr, i)` | 691 | Indexed read via slot |

⭐ **Strong, undersold.** Sutra's "arrays" are not heap-allocated
— they're packed into a single substrate vector. The paper
doesn't mention this at all.

### Substrate-pure scalar primitives

| Method | Line | Purpose |
|---|---:|---|
| `truth_axis(v)` | 699 | Read truth scalar from a vector |
| `heaviside(x)` | 717 | Branchless step (substrate-pure) |
| `saturate_unit(x)` | 728 | Clamp to [0, 1] (substrate-pure) |

⭐ **Strong, undersold.** These are the primitives that let
control-flow constructs lower without Python branches. Paper
§3.3 mentions them in passing.

### Similarity & accessors

| Method | Line | Purpose |
|---|---:|---|
| `similarity(a, b)` | 751 | Cosine on the truth axis |
| `component(v, i)`, `semantic(v, i)`, `synthetic(v, i)` | 761-781 | Indexed reads (debug/monitoring only — not on the substrate hot path) |
| `real(v)`, `imag(v)`, `truth(v)` | 797-807 | Axis accessors (debug/monitoring only) |

### Number constructors

| Method | Line | Purpose |
|---|---:|---|
| `make_real(x)`, `make_complex(re, im)`, `make_char(cp)`, `make_truth(t)`, `make_trit(t)` | 812-921 | Vector literal forms for primitive types |

### Complex multiplication

| Method | Line | Purpose |
|---|---:|---|
| `complex_mul(a, b)` | 866 | Three-cached-matrix multiply (real, imag, swap-RI) — preserves substrate-purity (no `.item()` extraction) |
| `_swap_ri_matrix`, `_cm_real_matrix`, `_cm_imag_matrix` | 827-866 | Cached matrices for the multiply |

⭐ **Strong, undersold.** Earlier implementation extracted scalars
and did Python complex multiply, which violated the
substrate-purity rule. Current form is fully matrix-based. The
paper doesn't mention how complex multiplication is implemented
on the substrate.

### Defuzzification

| Method | Line | Purpose |
|---|---:|---|
| `defuzzify_trit(v, iters=10, beta=2.0)` | 921 | Iteratively pull a fuzzy scalar toward {-1, 0, +1} via Lagrange-poly squashing |

⭐ **Strong, undersold.** Polarizes without binarizing — keeps
the substrate fuzzy and differentiable. The paper now mentions
Kleene 3VL + functional completeness in §1.2-1; defuzzify is
the operational form that completes the story.

---

## 3. Compiler architecture

### Pipeline

`Lex → Parse → Validate → Inline stdlib → Simplify → Codegen →
Execute` (`__main__.py`, `codegen_pytorch.py:1250`).

### Inliner

- `inliner.py`: pulls stdlib operators (`logical_and`, `lt`, `neq`,
  etc.) inline at the call site so the simplifier sees the full
  expression body and can fold across the call.
- ⭐ **Strong, undersold.** This is the "aggressive expansion"
  half of beta-reduction-to-tensor-normal-form. The paper
  mentions beta reduction in §1.2-2 but doesn't credit the
  *inliner* by name.

### Simplifier

- `simplify.py`: hand-rolled algebraic rewrites
- `simplify_egglog.py`: optional egglog-based simplifier (egglog
  is an e-graph + equality saturation library)
- ⭐ **Strong, undersold.** Two-track simplifier (hand rules +
  egglog e-graph) is the "algebraic reduction" half of beta
  reduction. Paper §1.2-2 mentions egglog but doesn't explain
  what e-graphs are or why they help.

### Codegen

- `codegen_pytorch.py`: PyTorch tensor-op emitter (canonical)
- `codegen.py`: numpy-substrate emitter (deprecated as of
  2026-04-30 but kept for emit-shape tests)
- `codegen_base.py`: shared traversal logic (loop functions,
  slots, conditionals, etc.)

### Compile-time substrate population

- `embed_batch(names)` (line 323): batched Ollama prefetch — one
  HTTP round-trip for N strings instead of N round-trips
- `populate_sutradb()` (line 412): inserts every embedded string
  into the embedded codebook
- `prewarm_rotation_cache()` (line 442): precomputes Haar-random
  rotation matrices for every codebook entry at module init
- ⭐ **Strong, undersold.** These three together are the
  "compile-time substrate population" pass that's mentioned as
  pipeline step 4 in §4. The paper doesn't explain that
  `embed_batch` is a real performance optimization (one HTTP
  call, not N).

### Disk cache for embeddings

- Embedded substrate values get written to a disk cache at
  module init (`_load_disk_cache` / `_write_disk_cache` lines
  220-247)
- ⭐ **Strong, undersold.** Second-and-later runs of the same
  compiled program hit the disk cache rather than re-embedding.
  Effectively zero-cost for repeated executions. Paper doesn't
  mention this.

### Optional torch.compile wrapping

- `SUTRA_TORCH_COMPILE=1` env var wraps each loop function with
  `torch.compile(backend='eager')` so Dynamo unrolls the
  per-tick loop at trace time.
- 3 tests pass under this mode (`tests/test_torch_compile_wrap.py`).
- ✓ Mentioned in §3.3 as "optional torch.compile wrapping."

### Configurable T (loop unroll depth)

- CLI flag `--loop-T` (any int)
- Manifest: `[project.compile] loop_max_iterations = N` in
  `atman.toml`
- Walks up from the source file looking for the nearest manifest;
  defaults to 50 if no manifest declares it.
- ✓ In the paper as §1.2 (post-contribution-list paragraph) and
  §3.5 (manifest example).

---

## 4. Substrate / integration features

### Three substrate models tested

- `nomic-embed-text` (768-d, mean-centered) — default
- `all-minilm` (384-d) — `examples/analogy_minilm.su`
- `mxbai-embed-large` (1024-d) — `examples/analogy_mxbai.su`
- ⭐ **Strong, undersold.** Cross-substrate examples exist in the
  repo. Paper claims substrate-agnosticism but doesn't cite the
  cross-substrate demos.

### SutraDB embedded codebook

- 45K-line Rust crate (`sutraDB/`) — RDF + HNSW triplestore
- FFI'd via ctypes (`sutradb_embedded.py`)
- Stores compile-time `(label, embedding)` pairs in a `.sdb` file
- Indexed by HNSW for nearest-neighbor decode
- `nearest_string(query)` returns the nearest known label
- ✓ In the paper as §3.4. The user-facing claim ("embedded
  vector database that ships as part of the compiler — analogous
  to SQLite") is solid.

### atman.toml manifest

- `[project]` (entry, name, substrate, description)
- `[project.embedding]` (provider, model, dim, mean_center)
- `[project.compile]` (loop_max_iterations)
- ✓ In the paper as §3.5.

### MCP server

- Provides spec lookup + AST query as MCP tools
- Documented in `sdk/sutra-compiler/sutra_compiler/mcp_server.py` (if
  exists; check)
- 🚫 **Not yet exercised in the paper.** The CLAUDE.md note
  about "MCP server is a core part of the language runtime" is
  not load-bearing for any current paper claim.

---

## 5. Stdlib (`sdk/sutra-compiler/sutra_compiler/stdlib/`)

### Working / inlined

- `logic.su`: `defuzzy`, `logical_not`, `logical_and`, `logical_or`,
  `lt` — the propositional layer. Inlined into the simplifier so
  `&&`, `||`, `!` lower to the polynomial forms (§1.2-1).
- `similarity.su`: `neq` — pair-derived from `eq`.
- `embed.su`: target shape for compile-time embed primitives;
  partially blocked on intrinsics.

### Target shapes (blocked on intrinsics — bodies present, not yet executable)

- `vectors.su` — bind, unbind, bundle, permute. Bodies are
  pseudo-Sutra showing what the inliner *should* expand to once
  Sutra-callable primitives for matmul / matrix literals exist.
- `numbers.su` — `make_real`, `make_complex`, `make_char`,
  `complex_mul`. Blocked on indexed-construction primitives.
- `memory.su` — `zero_vector`, `hashmap_get`, `hashmap_set`.
  Blocked on `_VSA_zeros` and similar intrinsics.
- `rotation.su` — rotation primitives.
- `math.su` — transcendentals (log, exp, sin, cos, ...).
  **EXPLICITLY DISABLED** — compile-time error if used. The
  bound-table-via-binding approach hit a 2-scalar capacity wall;
  documentation in `planning/findings/2026-04-29-bound-table-
  capacity-limit.md`. Eigenrotation-as-modulus is the open
  question.
- 🚫 **Honest scope:** the stdlib has lots of "target shape" files
  that aren't yet executable. The paper doesn't claim these as
  contributions. The README in `stdlib/` is honest about it.

---

## 6. Tests (16 test files under `sdk/sutra-compiler/tests/`)

| File | What it covers |
|---|---|
| `test_branchless_loop.py` | Conditional → softmax-weighted superposition lowering |
| `test_codegen.py` | Numpy backend emit-shape tests (deprecated but kept) |
| `test_codegen_pytorch.py` | PyTorch backend behavior tests |
| `test_corpus.py` | Walks `examples/` and validates each file parses |
| `test_inliner.py` | Stdlib operator inlining |
| `test_lexer.py`, `test_parser.py` | Front-end |
| `test_loop_function_decl.py` | 23 tests for `do_while`/`while_loop`/`iterative_loop`/`foreach_loop`, halt propagation, T=50 convergence |
| `test_rotation_prewarm.py` | Compile-time rotation cache population |
| `test_simplify.py`, `test_simplify_egglog.py` | Simplifier passes |
| `test_stdlib_loader.py` | stdlib path resolution |
| `test_sutradb_embedded.py` | 7 tests for FFI roundtrip, nearest-neighbor decode, top-k, unicode labels, env-var path override |
| `test_torch_compile_wrap.py` | 3 tests for `SUTRA_TORCH_COMPILE=1` mode |
| `test_transcendentals_disabled.py` | Compile-time error fires when transcendentals are used |
| `test_workspace.py` | atman.toml manifest parsing |

⭐ **Strong, undersold.** 244+ tests pass. The paper says "13
demonstration programs in the smoke test (with 23 .su files)" but
doesn't cite the test count.

---

## 7. Examples (23 `.su` files, 1625 LOC total)

The 13 in the smoke test (canonical demos):
- `hello_world.su` (42 LOC) — embed + retrieve
- `fuzzy_branching.su` (92 LOC) — softmax-weighted conditionals
- `role_filler_record.su` (57 LOC) — bundled record encode/decode
- `classifier.su` (52 LOC) — decision rules
- `analogy.su` (55 LOC) — VSA capital→country lookup
- `knowledge_graph.su` (68 LOC) — multi-hop graph queries
- `predicate_lookup.su` (78 LOC) — predicate dispatch
- `fuzzy_dispatch.su` (90 LOC) — soft-mux scoring
- `nearest_phrase.su` (79 LOC) — string retrieval
- `sequence.su` (94 LOC) — sequence reduction
- `loop_rotation` (in tests) — geometric loops
- `concept_search` (in tests)
- `counter_loop` (in tests)

Additional `.su` files (not in smoke test but parse):
- `analogy_minilm.su`, `analogy_mxbai.su` — cross-substrate analogy
- `king_queen_naive.su` (81 LOC) — vector-arithmetic analogy
- `do_while_adder.su` (25 LOC) — loop demo
- `imperative_reversible.su`, `review_demo.su`, `tutorial.su`,
  `wait_keyword_demo.su`, `_legacy_syntax_tour.su`
- `rotation_book_catalog.su` (128 LOC), `rotation_hashmap.su`,
  `rotation_record.su`
- `classes_demo.su` (30 LOC)

---

## 8. What's particularly noteworthy / undersold (the headline list)

Ranked by "actually-implemented & defensible" × "absent from or
underweighted in the current paper":

1. **Polynomial fuzzy logic via Kleene 3VL + Lagrange + functional
   completeness.** Closed forms shipped in code; paper now has a
   proper §1.2-1 explanation as of commit 3e444c2.
2. **Constant memory in recursion depth via tail-recursion-folded
   state vector.** Just landed in §1.2-3 + §3.3 (commit 86038cb).
3. **Three-tier casting** (`as` / `unsafe_as` /
   `unsafe_override`) with explicit grep-able forbidden patterns.
   **Not in the paper at all.**
4. **`slot` keyword + Givens-plane allocation per state variable.**
   Load-bearing for substrate-pure state evolution. **Not in the
   paper.**
5. **Binding arrays packed into single substrate vectors**
   (`array_from_literal` / `array_length` / `array_get`).
   **Not in the paper.**
6. **Two-track simplifier (hand rules + egglog e-graph) as the
   "algebraic reduction" half of beta reduction.** Paper mentions
   egglog by name once; the architecture is more substantial.
7. **Compile-time substrate population: embed_batch,
   populate_sutradb, prewarm_rotation_cache.** These three are
   real performance and reproducibility wins. Paper §4 mentions
   the pipeline step but doesn't explain what each function does.
8. **Cross-substrate examples** (`analogy.su`,
   `analogy_minilm.su`, `analogy_mxbai.su` — three different
   embedding models). The paper claims substrate-agnosticism;
   the cross-substrate demos aren't cited.
9. **`unknown` (U) as a first-class literal.** Paper now talks
   about Kleene 3VL but doesn't mention you can write `U` in
   source.
10. **`defuzzify` operator with iterative Lagrange-poly
    squashing.** Polarizes without binarizing. Not in the paper.
11. **Disk cache for embeddings.** Second-run cost ~0. Not in the
    paper.
12. **Substrate-pure complex multiplication via three cached
    matrices.** No scalar extraction in the operation. Not in
    the paper.
13. **244+ test corpus.** Paper says "13 demos + 23 files" but
    doesn't cite the test count.

## 9. Honest scope (what we should NOT claim)

- **Transcendentals** (`log`, `exp`, `sqrt`, `sin`, `cos`, `tan`,
  `pow`): compile-time-disabled. Test
  `test_transcendentals_disabled.py` enforces the rejection.
- **Object encapsulation rules**: `class` declarations parse;
  encapsulation is not enforced.
- **Learned-matrix binding**: surface (`role X = learned_from(data)`)
  parses but the runtime rejects with a deferred-feature error.
  Per Emma 2026-04-30 the paper has been edited to *not* claim
  this as a contribution; that framing is correct.
- **Stdlib target-shape files** (`vectors.su`, `numbers.su`,
  `memory.su`, `rotation.su`): bodies are pseudo-Sutra; not yet
  inlinable. The runtime side is implemented in the codegen
  directly.
- **MCP server**: documented but not load-bearing for any current
  paper claim.

## How to use this doc

When making a paper edit, grep this file for the claim you're
about to make. If the feature is here under ⭐ "strong,
undersold," consider whether the edit can lift it into focus.
If the feature is under "honest scope (NOT implemented)," do
not claim it.

When adding a new feature to the language, add an entry here in
the same commit. Drift between this doc and the codebase is the
risk this doc exists to prevent.
