# Sutra — consolidated TODO

This file is the long-term agenda. `STATUS.md` at the repo root is the
active session queue — if the two disagree, STATUS.md wins for what is
being worked on *now*, and this file wins for what needs doing
*eventually*. Do not re-split this into per-subdirectory todo files.

## 🗂 Priority levels

- **Immediate** — do right now / this session. Usually mirrored in `STATUS.md`.
- **Pre-Anthropic-grant-app (~2026-04-29)** — user's next external deadline;
  items here should land before that.
- **Pre-Y-Combinator pitch** — must land before the YC pitch (no fixed date).
- **This year** — should land in 2026, not necessarily tied to a deadline.

When adding an item, pick a level. When closing one, delete the line.

Note: the "Pre-Claw4S" priority level (deadline 2026-04-20) was retired
on 2026-04-20 when the papers/submission layer was removed from the
repo. Items that used to live under it have either been completed
(sign-flip removal → rotation binding, 2026-04-22) or no longer apply
(paper-scope maintenance) or moved to findings (substrate design work
is now ongoing under `planning/findings/` rather than deadline-driven).

---

## [This year] Make `sutralang.dev` more agent-accessible

Sutra's stance per CLAUDE.md is that agents are first-class consumers
of the documentation, not an afterthought. The site is already
markdown-driven, but specific moves to take it further:

- [ ] Audit each page on `sutralang.dev` for content that exists only
  in rendered form (animations, hover-only tooltips, JS-rendered code
  examples) and lift it back into the source markdown so an agent
  fetching the raw page gets the full content.
- [ ] Add a prominent agent-routing affordance on the landing page —
  an explicit "If you are an AI agent, the canonical source is the
  Markdown in `docs/` / the GitHub repo" hint, so agents can redirect
  themselves to the higher-fidelity source.
- [ ] Expose the docs through an MCP server (or a documented
  fetch-this-URL pattern) so agents can query Sutra's surface
  programmatically rather than scraping HTML.
- [ ] Verify the site renders sensibly when JS is disabled, since
  many agent fetchers don't execute scripts.

---

## [Pre-Anthropic-grant-app] Rotation-hashmap capacity + Monte-Carlo exploration

The rotation-hashmap library-pattern prototype landed 2026-04-22
(5/5 exact-lookup on nomic; `examples/_rotation_hashmap_test.py`).
Two follow-ups flagged during that work:

- [x] ~~**Capacity experiment.** Design doc is
  `planning/findings/2026-04-21-rotation-binding-capacity-experiment-design.md`;
  five concrete experiments, not yet run. Produces a findings doc
  with the capacity curve.~~ **DONE 2026-04-24.** All 5 experiments
  PASS. `experiments/synthetic_subspace_validation.py` +
  `planning/findings/2026-04-24-synthetic-subspace-validation.md`.
- [x] ~~Monte-Carlo attractor search (first-pass, nomic only).~~
  **DONE 2026-04-22** (commit TBD). User revised timing: "do it
  today, nomic only, since nomic is the best substrate we have."
  `examples/_king_queen_mlp_attractor.py` trains a 2-layer tanh
  MLP `f(x) = x + r(x)` with 14 codebook vectors as fixed points,
  iterates from v0 = king - man + woman, and runs a 4-noise-level
  Monte-Carlo basin sweep. Key finding: **queen is the attractor
  basin for v0 on nomic, but the boundary with king is proximal**
  — 0.05 noise flips 1 in 5 trajectories to king, 0.15 noise is
  near coin-flip. Written up in
  `planning/findings/2026-04-22-mlp-attractor-king-queen-nomic.md`.
  The older placeholder at `examples/_king_queen_attractor_search.py`
  (random-rotation-plus-nearest-neighbor, not attractor dynamics)
  stays as a fragility-check tool but is NOT the real attractor
  search.

- [ ] **Cross-substrate attractor comparison.** Follow-on to the
  2026-04-22 single-substrate result. Train separate MLPs on
  nomic, mxbai, and minilm codebooks. Compare: does v0 land in
  queen's basin on nomic only, or does the MLP "rescue" queen on
  the weaker substrates too? The cross-substrate sweep
  (`_king_queen_multi_substrate.py`) showed mxbai and minilm fail
  naive analogy — the interesting question is whether attractor
  dynamics can recover the right answer anyway. Likely a
  pre-Anthropic-grant-app item (not today).

- [ ] **Larger-codebook attractor.** 14 words is proof-of-mechanism.
  Scaling to thousands of codebook entries (a real concept-memory
  for a working agent-style program) is the next scaling step.
  Capacity characterization as a function of codebook size +
  MLP size would land alongside.

- [ ] **Attractor-MLP as a Sutra language builtin.** Currently the
  attractor is only accessible from Python. A language-level
  declaration like `attractor M = learn_attractor(codebook);`
  with a matching iteration op would let `.su` programs use
  attractor dynamics natively. Sequence after learned-matrix
  binding lands (which uses related machinery — fit a matrix at
  compile time).

## [Pre-Anthropic-grant-app] Per-program embedding-space override

User direction 2026-04-22: *"programmes should be able to have their
native embedding space [declared] at the beginning of them as an
override thing so that we could have a bunch of different test
programmes that show it in different vector spaces."*

Current state: `NumpyCodegen.__init__` already accepts `llm_model=...`
as a kwarg, but there's no source-level way to set it — the codegen is
invoked with default args by `examples/_smoke_test.py`.

Minimum scope:
- [x] ~~Define the directive syntax. Leaning toward a magic first-line
  comment (`// @embedding: mxbai-embed-large`) that the test harness
  parses pre-compile; zero parser/compiler changes.~~ DONE 2026-04-22.
- [x] ~~Update `examples/_smoke_test.py` and the analogy harness to
  respect the directive.~~ DONE 2026-04-22.
- [x] ~~Write 3+ test programs that sweep the embedding models available
  locally (`nomic-embed-text`, `mxbai-embed-large`, `all-minilm`)
  over the same analogy task. Compare winners + margins.~~
  **DONE 2026-04-24.** 5/5 correct on all three substrates.
  `examples/_analogy_substrate_sweep.py` +
  `planning/findings/2026-04-24-capital-country-across-substrates.md`.

Longer scope (later):
- [ ] Source-level declaration (not a comment) — a `embedding_space`
  pragma the parser recognizes. Decide after seeing how the magic-
  comment version is used in practice.

## [Pre-YC] `main(embedding_space: string)` compile-time override

User direction 2026-04-23: *"the runtime override, honestly, it
wouldn't be at runtime; it would be at compile time"* and *"both of
those things go after the anthropic application."* Moved from
STATUS.md (where it was erroneously framed as runtime override) to
this post-Anthropic-grant-app bucket.

File-level (`// @embedding`) and project-level (`atman.toml`
`[project.embedding]`) declarations landed 2026-04-22. What remains
is the third layer — a `.su`-language-level way to set the
embedding substrate from inside source code itself, so a test
program can declare its own substrate without a harness-level hint.

Scope:
- [ ] Pick the source-level syntax. Candidates: a
  `main(embedding_space: string)` signature that the compiler reads
  at compile time (NOT passed as a runtime arg — the codegen bakes
  it into the `_NumpyVSA` constructor); or an explicit
  `embedding_space "nomic-embed-text";` pragma at the top of the
  file. Either way the substrate resolves before any `embed()` call
  is compiled, so no runtime lazy-init.
- [ ] Wire the chosen syntax into the parser and have
  `NumpyCodegen.__init__` accept the resolved model.
- [ ] Make sure file-level and project-level declarations still
  override correctly when the source-level form is also present.
  Precedence order is source > file > project > compiler default.

## [Pre-YC] Concurrency — only the cases that need explicit handling

User direction 2026-04-22 (afternoon): concurrency is implicit by
default in Sutra because the language's functional algebraic nature
already gives the compiler license to evaluate independent sub-
expressions in parallel via formula simplification. **An explicit
syntax is only needed for the cases where the compiler can't derive
the parallelism algebraically**. Moved to pre-YC 2026-04-23: the user
confirmed that rotation-hashmap capacity is the only pre-Anthropic-
grant-app item still active, and concurrency + learned-matrix both
move to the post-Anthropic bucket.

The shapes that still need explicit handling:

- [ ] **Concurrent looping.** `loop` today is a single trajectory
  (bounded unroll for `loop[N]`, eigenrotation for `loop(cond)`).
  A concurrent form would run N independent trajectories in
  parallel. Surface syntax TBD — probably an extension of existing
  `loop` rather than a new keyword, given the user's "implicit
  except where needed" framing.

- [ ] **MLP attractor search.** N independent trajectories through
  an attractor MLP, each from `v0 + noise[i]`, each iterated until
  its fixed point, collected as a basin distribution. This is the
  first-class concrete use case driving the concurrency work (see
  `planning/findings/2026-04-22-mlp-attractor-king-queen-nomic.md`).
  Currently hand-rolled in Python; the pre-grant-app work lets the
  language express it natively.

Deferred sub-questions (from the original 2026-04-14/15 open-
question doc; the user has not expressed a position on these and
they don't block the two shapes above):

- Convergence test formula — cosine threshold? snap identity?
  Both-finished as a fallback?
- Timing mismatch — return-fast-cancel-slow vs. wait-both.
- External concurrency (parallel Ollama calls) — probably just
  compiler-does-it given the "implicit by default" framing, but
  I/O error modes may force a more explicit treatment.

Source-of-truth for the design: `planning/sutra-spec/concurrency.md`
(implicit-by-default, with explicit as fallback).
`planning/open-questions/concurrency-and-monads.md` (monad framing
was considered and demoted).

## [Pre-YC] Learned-matrix binding

Deferred from the 2026-04-22 rotation-binding pass; moved to pre-YC
on 2026-04-23 when the user confirmed the pre-Anthropic bucket is
just rotation-hashmap capacity. The feature is genuinely useful (see
`feedback_learned_matrix_is_not_next.md`) — it's simply not the next
active item. When picked up:

- [ ] Add a matrix-fitting step at compile time. A `role X =
  learned_from(data)` declaration reads `(input, output)` embedding
  pairs and fits R via lstsq (or Procrustes, or low-rank —
  substrate-dependent).
- [ ] Wire the `role` surface syntax into the parser. STATUS.md item
  3's decision (Candidate B: `role` / `var`) is resolved at the spec
  level but not implemented in `sdk/sutra-compiler/`.
- [ ] Emit `R @ filler` runtime for semantic roles; `R.T @ record`
  for unbind (or precomputed pinv for non-orthogonal R).
- [ ] A new demo that exercises learned-matrix bind end-to-end (e.g.
  a `located_in_country` program using cartography-style displacement
  data).

## [Pre-YC] Extended state vector — remaining integration

The runtime-primitive half of the extended-state / synthetic-subspace
design landed 2026-04-24 (`planning/findings/2026-04-24-slot-rotation-
runtime.md`). `_VSA` now exposes `slot_store` / `slot_load` /
`rotate_slot` — 48 disjoint 2D-Givens slots in the synthetic block,
exact reversibility, zero semantic drift. All 4 reversibility tests
PASS on the compiled runtime.

What this pass closed:
- [x] ~~Decide synthetic-subspace budget~~ — fixed at 100 dims
  language-level default (DEFAULT_SYNTHETIC_DIM in codegen.py).
- [x] ~~Extend the embedding pipeline so embedded vectors are
  `[semantic | zeros]` in the block-diagonal layout.~~ DONE 2026-04-23.
- [x] ~~2D-Givens-per-slot primitive in the synthetic subspace.~~
  Runtime methods landed 2026-04-24.
- [x] ~~Reserve one synthetic axis as canonical truth axis; implement
  `is_true` / defuzzification as projection onto it.~~ AXIS_TRUTH=2,
  `make_truth`, `_truth_projector`, defuzzy unrolled to truth-axis
  polarization — landed 2026-04-23.

What remains:
- [x] ~~Sutra-language surface syntax for slot primitives.~~ DONE
  2026-04-25. `slot TYPE name [= expr];` parses, validates, and
  IDE-highlights cleanly. Codegen rejects with SUT0150 — the
  codegen integration itself is tracked under "Compilation updates"
  below.
- [x] ~~Imperative-reversible demo `.su` program.~~ DONE 2026-04-25.
  `examples/imperative_reversible.su` runs end-to-end and returns
  0.0, confirming the rewrite chain `99 → 13 → 7` produces the
  same final slot state as a single `7`. Will be rewritten with
  natural assignment syntax once slot codegen integration lands.
- [x] ~~Spec-text refresh in `planning/sutra-spec/binding.md`.~~
  DONE 2026-04-25. Rotation-binding section now opens with an
  "empirically validated and runtime-supported as of 2026-04-24"
  callout.
- [ ] Compile-time slot allocator — map named variables to slot
  indices deterministically, with a compile-error when capacity
  (48 slots per program at synthetic_dim=100) is exceeded. Lands
  alongside the slot codegen integration (see "Compilation updates"
  below).

## [Pre-YC] Compilation updates

Compiler-side integration for primitives that already landed at the
runtime / surface-syntax level. The egglog post-pass and slot
rotation runtime both shipped 2026-04-24/25; what remains here is
the codegen work that turns those primitives into things `.su`
programs can rely on without explicit harness intervention.

### Egglog — linearity analysis codegen

The egglog rules already do the algebra (matrix-chain fusion via
`R @ S` associativity + apply distribution + cost model preferring
fused chains). The remaining work is **codegen integration**:
function bodies that are pure linear tensor-op compositions get a
single cached matrix `M` and compile down to `M @ arg`.

- [ ] Detect when a function body's egglog form is a single
  `(M_n @ ... @ M_1)` composed-matrix expression.
- [ ] Extend the lift/lower bridge in
  `sdk/sutra-compiler/sutra_compiler/simplify_egglog.py` to handle
  matrix-compose forms.
- [ ] Emit `M = M_n @ ... @ M_1` at module init; replace the call
  site with one matrix-vector op.

Sub-200 lines of compiler work. This is the pass that makes the
global-efficiency story (every linear function compiles to one
cached matrix) actually realize.

### Egglog — CSE pass

Falls out of equality saturation when the cost model charges per-use
rather than per-node. Implementation is mostly in the lower step.

- [ ] Adjust the cost model in `simplify_egglog.py` to charge
  per-use.
- [ ] Emit Python `let`-bindings (a temporary variable) for any
  subexpression that appears more than once in the extracted form,
  instead of inlining.

Adjacent prior art: JuliaSymbolics hash consing reports 3.2× speedup
+ 5× faster codegen on similar workloads.

### Slot codegen integration

Surface syntax landed 2026-04-25 — `slot TYPE name [= expr];`
parses, validates, and IDE-highlights. The codegen rejects with
SUT0150 ("slot declaration is parsed but the codegen integration
... isn't wired yet"), so user programs fail fast with a clear
message. Roughly 200 lines of compiler work to finish.

- [ ] Per-scope state vector that holds slot contents.
- [ ] Transform slot-name reads to `slot_load` calls at codegen
  time.
- [ ] Transform slot-name writes to `slot_store` (then reassign the
  state vector).
- [ ] Wire the compile-time slot allocator (deterministic
  name → index map; 48-slot capacity check at synthetic_dim=100).

Once this lands, `examples/imperative_reversible.su` can be
rewritten using natural `x = a; x = b; x = a;` assignment syntax
instead of the explicit harness it uses today.

## [This year] Monotonicity of fuzzy logic polynomials

The current AND/OR polynomials are Lagrange-interpolated on the
three-valued grid `{-1, 0, +1}²`. Exact at grid corners, smooth
everywhere, but **non-monotonic between grid points.** Concrete
example: `AND(a, 0)` as a function of `a` peaks at `a = 0.5`
(value 0.125) and drops back to 0 at `a = 1`. Derivative
`(1 + b − 2a + 2ab²)/2` is negative for `a > 0.5` when `b ≈ 0`.

Fuzzy logic does not strictly require monotonicity, but preferring
it would make the operators behave less surprisingly on off-grid
inputs.

Options to restore monotonicity:

- **Use `minimum` / `maximum` primitives directly.** `np.minimum`
  and `torch.minimum` are vectorized tensor ops — monotonic and
  exact on the grid. Tradeoff: kink at `a = b` (non-smooth there;
  differentiable almost everywhere via subgradients).
- **Higher-degree polynomial.** Some degree-6 or higher polynomial
  might be both exact on the grid and monotonic. Hasn't been
  explored; likely more expensive.
- **Softened min/max** (Einstein t-norm, Yager family, soft-min
  with temperature). Smooth + monotonic but loses exactness at
  the grid corners.

User preference (2026-04-24): prefers more monotonic than current,
not essential. Parked here rather than switched immediately.

## [This year] Language-design open questions

Not paper-critical; revisit after Claw4S. Grouped because they are of a piece.

- Anonymous functions (leaning toward `lambda` keyword).
- How primitive substrate operations read in source.
- Declaration syntax for implicit conversions.
- Lightweight role-annotation system for semantic roles.
- Expression-vs-statement bias.
- Access modifiers beyond public/static defaults.
- Half-compilation / immediate-execution model.
- `hop` non-algebraic function.
- IO — how Sutra handles input/output.
- Softmax-over-switch vs. if/elif chains —
  `planning/exploratory/softmax-conditionals.md`.

## [This year] Docs / website

- [ ] **Expand `docs/paradigms.md` once more is built.** The page was
  shrunk on 2026-04-27 to a single Java contrast (assignment, loops,
  classes) plus the no-memory-points / non-locality core. The earlier
  version had Haskell, Prolog, C, and Curry/Mercury sections that ran
  ahead of what the language can actually demonstrate. Once we have
  more substantive working programs (real class bodies post-ontology
  work, working learned-matrix binding examples, more
  cross-language-flavor demos that compile and run), revisit the page
  and add back whichever comparisons are now backed by code that
  actually executes — not aspirational prose. Do not restore the old
  text wholesale; rewrite from current ground truth.

- [ ] Interactive pipeline viewer: paste `.su` source, see the AST,
  the simplified AST, the emitted Python, and the expanded polynomial
  form of any expression, side-by-side with rewrite highlights. Same
  stylistic template as the existing widgets (`graph-to-vector`,
  `bind-unbind`, `snap-to-nearest`, `fuzzy-logic`). Lives on
  `docs/interactive/` when built.

## [This year] Smoke-test failures

The smoke test (`examples/_smoke_test.py`) currently returns FAIL
overall — 4 of 97 individual checks miss. Not blocking the language
work; flagged so it doesn't get forgotten.

- [ ] **`fuzzy_dispatch.su` returns 2/4.** The four-way dispatch
  resolves the music and timer cases correctly but misses the
  weather and cancel cases. Likely either a prototype-similarity
  margin issue or a structured-record decode regression introduced
  by one of the recent simplifier / fusion passes — a `git bisect`
  against the 2026-04-23..2026-04-25 simplifier work is the cheap
  first step.
- [ ] **`sequence.su` self-similarity check fails.** `sim(fox, dog)
  = 0.827` against an expected window of `(0, 0.5)`. Either the
  expected window is too tight for the current bundling normalization
  or the position-bound bundle is no longer producing the disjointness
  the test assumes. Inspect the actual cosine across the bundle and
  decide whether to widen the window or fix the bundle.

## [This year] Compile-time math function approximation

User direction (2026-04-25): "Make a math library and some
compilation wizardry." The Kolmogorov–Arnold angle says any
continuous function decomposes into univariates, which can be
approximated as tensor ops on a bounded domain. Sutra should
compile `log`, `sqrt`, `sin`, `exp`, etc. to tensor expressions at
compile time rather than calling out to libm at runtime. See
`docs/numeric-math.md` § "Transcendental functions" for the
design.

Concrete work:

- [ ] **Add `[math]` section to `atman.toml`** with
  `approximation_precision` (target abs error) and
  `approximation_method` (`"chebyshev"` / `"lookup"` /
  `"cordic"`). Parse it in `sdk/sutra-compiler/sutra_compiler/
  workspace.py` (or wherever atman.toml is read).
- [ ] **Compile-time Chebyshev coefficient generator.** Given a
  function family (`log`, `sqrt`, …) plus a bounded domain plus a
  precision target, emit a coefficient vector of the right
  polynomial degree. Most of these have closed-form Chebyshev
  expansions; precompute at compile time, dot at runtime.
- [ ] **Lookup-table tier.** For functions where Chebyshev is
  impractical, emit a precomputed table tensor + a sparse-matmul
  interpolation. Sutra's "table is just another tensor" advantage
  is real here — verify it on at least one transcendental.
- [x] ~~**`stdlib/math.su` math intrinsics** that route to the
  approximation pass: `log`, `sqrt`, `exp`, `sin`, `cos`, `tan`,
  `pow` for starters.~~ **Placeholders landed 2026-04-25.** The
  intrinsics are declared in `stdlib/math.su`; both numpy and
  pytorch backends emit stub runtime methods that raise
  `NotImplementedError` with a pointer to this entry. User code
  that calls `sqrt(x)` compiles successfully and fails fast with
  a clear message at runtime. The approximation pass that
  replaces these stubs with real Chebyshev / lookup-table tensor
  ops is the remaining work.
- [ ] **Bounded-domain inference.** For the polynomial-tier path
  to work the compiler needs to know `x ∈ [a, b]`. Either via
  type annotations (e.g. `bounded<scalar, 0.01, 10> x`), via
  static analysis on simple cases, or via runtime guard +
  fallback. Pick a path; type annotation is the most consistent
  with the rest of the language.
- [ ] **Precision-vs-speed test corpus.** Three programs at
  three precisions (1e-3, 1e-6, 1e-12); show the polynomial
  degree shifts and the result still matches. This is the
  audit-friendly story for finance use cases.

## [This year] `atman.toml` backend / dtype configuration

Companion to the math-approximation work. Today `atman.toml` only
carries `[project.embedding]`. Per the Kolmogorov chat (2026-04-25):

```toml
[backend]
target = "cuda"               # or "cpu", "metal", "tpu"
dtype = "float16"             # or "float32", "bfloat16"
mixed_precision = true

[pytorch]
compile = true                # torch.compile
```

Dtype is the more interesting half — float16 vs float32 vs
bfloat16 changes both throughput and what the compiled tensor's
precision contract actually realizes. Right now the codegen hard-
codes float64 for the numpy backend; the pytorch backend picks at
init. Letting projects set this per-program closes the precision-
contract story.

Concrete work:

- [ ] Extend `atman.toml` schema with `[backend]` (target, dtype,
  mixed_precision) and `[pytorch]` (compile, etc.).
- [ ] Plumb the dtype through `codegen_pytorch.py` so `_VSA.dim`
  and the tensor allocations honor it.
- [ ] Document the interaction with `[math]` precision — a
  1e-12 precision target on float16 storage is incoherent; the
  compiler should warn or escalate dtype.

## [Pre-YC] Ontology — make the class system real

User reflection (2026-04-25): "We have the ontology somewhat, but
I don't think we've really implemented classes that much, even
though we should be implementing classes, or ontology. […]
Defining classes is going to be a relatively late thing for us
to do in this, once we've more or less done a large amount of
other stuff."

Sutra calls its type system an *ontology* deliberately — both
because it's a knowledge-representation framing (OWL/RDF sense),
because it communicates "rules of how to use things" rather than
proof-theoretic structure, and because the user is a philosopher
and the framing fits. See `docs/ontology.md` for the existing
exposition.

**Audited state of the ontology / class / function surface
(2026-04-25):**

- **Functions** — fully working. `function T name(T arg) { … }`
  parses, validates, codegens, runs. Used in nearly every `.su`
  example.
- **Methods** — parsed (`MethodDecl` AST node, `method` keyword
  in lexer). **Rejected at codegen** with "method declarations
  are not supported by the V1 codegen." Surface syntax
  exists; no method ever actually runs. `examples/uncertain/01-
  objects-and-methods.su` shows the intended shape and explicitly
  fails to run.
- **Generics** — same shape. `function T Identity<T>(T value)`
  parses, codegen rejects with "generic function declarations
  are not supported by the V1 codegen."
- **`class Foo extends Bar { }` declaration form** —
  ✅ MVP landed 2026-04-25. Empty bodies, single inheritance,
  parent-chain must bottom out at a primitive. See
  `docs/ontology.md` § "MVP declaration form" and
  `examples/classes_demo.su`. Diagnostic codes SUT0140
  (non-empty body), SUT0141 (duplicate), SUT0142 (extends
  unknown).
- **Inheritance / operator overloading on user classes** — not
  at all. Operators are defined on primitive classes only, in
  `codegen.py` / `codegen_pytorch.py`.

`docs/ontology.md` now describes both the intended end-state and
the MVP landing point. The compiler-recognized "ontology" today
is: the primitive hierarchy (vector / int / float / complex /
fuzzy / trit / bool / char / string), user-declared empty-body
classes that bottom out at a primitive, plus user-named
identifiers in type positions that the validator tolerates but
the codegen treats as plain vectors.

Concrete things still missing — the next layer above the MVP:

- [ ] **Class bodies that aren't empty.** Field declarations
  (storage layout — which axes the class uses), method
  declarations, operator implementations. Each is rejected by
  the parser today (SUT0140 for non-empty bodies). The MVP
  empty-body form is the wedge; this entry is the actual
  ergonomics.
- [ ] **Instance constructors / instantiation.** Today a `Cat`
  is just a vector — there's no `new Cat(...)` form, no
  constructor body, no per-class layout. The user's framing:
  "objects don't even show up as a non-implemented stub." That
  gap is real.
- [ ] **Operator implementations on a class.** A class body
  defining `+`, `-`, `*`, etc. that subclasses inherit or
  override. This is the path that makes `Dollar + Dollar` work
  but `Dollar + Euro` fail — the F# units-of-measure
  replacement story.
- [ ] **Inheritance chains that the type checker walks at
  operator dispatch.** Today the validator tracks the chain
  for diagnostic purposes only; the codegen still treats the
  value as the primitive root. A real chain that the compiler
  uses to resolve `(Dollar)x + (Dollar)y` to a Dollar-typed
  result requires per-class operator tables.
- [ ] **Method dispatch on user-defined classes.** Drop the
  current SUT-style rejection and actually wire it through.
- [ ] **Generic functions and classes.** Drop the current
  "generic declarations not supported" rejection.

When these land, the natural follow-on demos are:

- A `Currency` base class in the stdlib whose subclasses
  (Dollar, Yen, etc.) inherit "addable to same currency only"
  semantics. The Kolmogorov-Arnold chat (2026-04-25) sketched
  this as the F# units-of-measure replacement story; it's the
  canonical demo of the ontology working end-to-end.
- Re-examine `codegen-v1-feature-coverage.md` in
  `planning/open-questions/` — that doc tracks the V1-codegen-
  rejects-this-construct list, and most of those rejections
  trace back to this gap.

This is **deferred — not because it's unimportant, but because
it's hard and most other Sutra work doesn't depend on it.** The
math-approximation work and the egglog migration both proceed
without the ontology layer being filled in. When the ontology
work happens, the natural follow-on items are:

- A `Currency` base in the stdlib whose subclasses (Dollar, Yen,
  etc.) inherit "addable to same currency only" semantics. The
  Kolmogorov-Arnold chat (2026-04-25) sketched this as the F#
  units-of-measure replacement story; it's the canonical demo of
  the ontology working. Originally captured here as a "[This year]
  Currency stdlib base class" item; merged into this entry because
  it depends on real class-declaration support landing first.
- Re-examine `codegen-v1-feature-coverage.md` in
  `planning/open-questions/` — that doc tracks the V1-codegen-
  rejects-this-construct list, and most of those rejections trace
  back to the ontology gap.

## [This year] Tooling

- [ ] Diagnose why `!editor.bat` fails (likely JAVA_HOME or Gradle daemon
  issue). Get `sdk/intellij-sutra` `runIde` task working, verify `.su`
  syntax highlighting and completion in the sandbox IDE.
- [ ] **Class system as autocomplete recommendation, not enforcement.**
  Originally surfaced in the project-genesis chat: the
  implicit class system in Sutra is meant to *suggest* meaningful ways
  to bind / unbind / bundle / unbundle / permute, not enforce them.
  Violating a class still produces a vector — possibly noise, possibly
  accidentally meaningful — and the language doesn't error. The IDE
  / MCP layer should surface class-coherent operations as autocomplete
  options ranked by ontological fit, while leaving off-class
  combinations callable with no warning. Pairs with the recognition-
  layer / ontology-detector idea: completion quality is bounded by
  how well the recognizer identifies what region of semantic space a
  vector occupies.

## [This year] Chats audit — do NOT run from a Claude Code sandbox

Per user direction 2026-04-13: *"chats are not supposed to be permanent...
once their stuff is implemented, you just remove them."* For each file
under `chats/`, check whether its content has been absorbed into spec,
planning doc, paper, or code; delete if absorbed (git preserves history),
leave and file an integration task if not. **Must be done interactively
with the user** — the "has this been absorbed?" judgment is a conversation,
not a grep. Surface, do not execute, from a sandbox session.

## [Pre-YC] Future Goals

- **Pick the multi-option `select` firing threshold.** Single-option
  `select` has a 0.5 default with a clean justification (softmax-of-one-
  vs-not is a probability distribution, and 0.5 is its natural decision
  boundary — see §26 "Single-option `select`"). For a `select` over
  k > 1 options the equivalent rule is unresolved. Candidates: winning
  weight exceeds `1/k + δ`; winning weight exceeds runner-up by a
  margin; absolute threshold (no clean softmax justification at k > 1);
  or no firing threshold at all (downstream consumers decide). Decision
  needs a multi-option demo where firing/not-firing matters. Logged as
  open question in §26 "What this document does not settle" §3.
- **Revisit the single-option `select` default threshold (0.5).** Picked
  provisionally over 0.9. If a real demo shows 0.5 lets too much fire,
  raise it. Either way, log the rationale in §26 alongside the
  decision.
- **IntelliJ / VS Code: inline interpretation hints for `select`,
  `is_true`, and other Sutra-specific constructs.** Modeled on the way
  Visual Studio shows git-blame author/commit hints inline against the
  code. The Sutra version would surface "this `select` will polarize
  with default threshold 0.5 and fire if `is_true(score) ≥ 0.5`",
  "this `is_true` polarizes the fuzzy state but does not binarize it",
  etc. — small, dismissable, contextual annotations that explain how
  the language interprets the code at the cursor. Helps onboard
  readers who don't yet have the spec in their head. Should hook into
  the LSP / MCP layer that already holds the semantic context (S1
  side of the dual runtime). Lives alongside the existing IDE work in
  `sdk/`.
- **Pick the `else_score` formula in `select(...) else fallback`.** Spec
  §26 currently pencils in `s_else = 0` as the working default — the
  user has flagged this as discouraged because a constant baseline does
  not measure "how unlike any of the named options the input is," which
  is what the else clause is supposed to capture. Plausible
  alternatives: `1 - max(scores)`, `-logsumexp(scores)`, or a
  substrate-computed novelty score. Decision needs a demo that actually
  exercises `select … else` semantics so the trade-offs are concrete.
  When the formula changes, update `planning/sutra-spec/26-select-and-gate.md`
  ("What this document does not settle" §1) and any backend that has
  started implementing `select … else`. Also fold a corresponding grammar
  change into `24-grammar.{ebnf,md}` (the `select(...) else fallback`
  production is not in the grammar yet — added at the spec level
  2026-04-15, still TBD in the grammar).
- **Split project kinds: connectome-target vs embedding-space-target vs
  general-connectionist.** A Sutra project compiles to one of three
  qualitatively different substrates. Design doc:
  `planning/open-questions/project-kind-connectome-vs-embedding.md`.
  Unblocks the YC demo (which cannot run on a connectome).
- **Sutra on commodity hardware end-to-end.** Every operation from
  `02-operations.md` running on a laptop substrate (the connectionist-
  computer work above is the path here). Numpy allowed only at the
  compile/monitor boundary, never at runtime.

## [This year] Formula simplification — remaining pieces

AST simplification pass + batched Ollama pre-fetch landed
2026-04-22 (sdk/sutra-compiler/sutra_compiler/simplify.py,
codegen_numpy embed_batch). 2.93× measured speedup on
nearest_phrase.su. Later the same day, aggressive simplifier
expansion + fused bundle-of-binds + disk cache landed (see
commit on `claude/enable-gpu-support-rczYD`). Remaining pieces:

- [x] ~~Identity simplification~~ — `bundle(v) → v`, bundle
  flattening. Done in simplify.py.
- [x] ~~Batched Ollama pre-fetch~~ — `basis_vector(...)` strings
  collected at compile time, one batched embed call at module
  init instead of N sequential HTTP round-trips. Done.
- [x] ~~Additional algebraic rewrites.~~ `displacement(a, a) →
  zero_vector()`, `unbind(R, bind(R, x)) → x`, `bind(R, unbind(R,
  x)) → x`, `similarity(a, a) → 1.0`, compose flattening,
  zero-absorption in + / − / bundle, arithmetic constant folding
  (x+0, x*1, x*0, x/1). All in `simplify.py`; covered by
  `tests/test_simplify.py`.
- [x] ~~Basis-vector on-disk cache.~~ Runtime cache at
  `~/.cache/sutra/embeddings/<model>-d<dim>.npz`. First run fetches
  from Ollama + writes atomically; second run loads from disk with
  zero Ollama calls. (Compile-time inlining — emitting embedded
  numpy literals directly into the generated module — is a further
  optimization; the runtime cache captures the value for now.)
- [x] ~~Scheduled parallel evaluation (fused dispatch).~~ Scoped
  to the two patterns that cover the demo programs:
  - `bundle(bind(r1,f1), ..., bind(rN,fN))` → fused runtime
    primitive `_VSA.bundle_of_binds(...)` doing one batched einsum
    over stacked rotations + stacked fillers. Replaces N sequential
    binds + an N-arg bundle with one op. On GPU, this collapses
    O(N) kernel launches into O(1).
  - `argmax_cosine(q, [a,b,c,...])` → stacked-candidate matmul +
    argmax. One numpy call instead of a Python for-loop.
  **Not done:** generalized ANF + dep-graph scheduling for
  arbitrary independent sub-expressions (e.g. `bundle(bind(r,f), c,
  bind(r2,f2))` still emits sequentially because one arg isn't a
  bind). For the three demos the targeted fusion is sufficient;
  larger programs would benefit from the general pass. Deferred
  until it has a concrete demo driving it.

## [This year] Integer class — follow-on work

The integer class landed as a compile-time tag on 2026-04-22
(augmented assignment works; `var n : int = 0; n += 1;` compiles
and runs). The canonical number axis in the synthetic subspace is
spec'd (see `planning/sutra-spec/types.md` §"The number axis and
the integer class" and
`planning/sutra-spec/equality-and-defuzzification.md` §"Canonical
axes in the synthetic subspace").

What landed:
- [x] ~~Augmented assignment~~ — `+=`, `-=`, `*=`, `/=` emit
  Python's native compound assign. Done.
- [x] ~~Spec commitment to the number axis~~ — documented
  alongside the truth axis. Done.

Follow-on work for a future pass:
- [ ] **Compile-time integer-specific checks.** Overflow bounds,
  mod-N wrap semantics, division by constant zero, etc. Today
  `var n : int` is a float at runtime with no checks; an integer-
  class compile-time pass could catch obvious mistakes.
- [ ] **Range-typed integers** — `int<0..N>` for loop indices,
  slot indexing into `var[N] slots : vector`, etc. Natural fit
  with the extended-state-vector design's rotation-slot allocation
  (each rotation plane is indexed by an int in a known range).
- [ ] **Type propagation through expressions.** Currently
  `var x : int = 3; var y = x + 1;` leaves y untyped (Python-
  duck-typed at runtime). A type-propagation pass would infer
  that y is also int-classed, which enables the checks above
  and sharpens IDE surface.
- [ ] **Float class as a separate tag.** The user's framing says
  "doubles have it to some extent too, but [integers] please it
  more." Making `float` / `double` a distinct compile-time tag
  alongside `int` would unlock float-specific behaviors (e.g.
  explicit precision, NaN / inf handling). Not urgent.

## [This year] Control-flow completion

- [ ] **Dynamic `foreach`.** Today (2026-04-22) `foreach` unrolls
  over a compile-time-known array literal `[a, b, c]` only.
  Anything else — a named variable, an expression returning a
  collection — is a compile-time error. The dynamic case requires
  deciding what "runtime iteration over a Sutra collection"
  actually looks like: is a named collection a compile-time tuple
  that the compiler can still unroll (if the initializer is an
  array literal)? Is there a runtime collection type whose
  iteration order is meaningful? How does the loop-body lower —
  as a host `for` (counters on the host, rejected by the CLAUDE.md
  rule), as an eigenrotation-indexed loop, as something else?
  Deferred pending a concrete use case.

- [ ] **`try-catch`.** Parser accepts it; codegen rejects. Sutra
  has no `raise` / `throw` primitive, so "what does a catch
  catch" is the open question — not just an implementation gap.
  Candidates: substrate-level errors (Ollama down, rotation
  produced NaN), user-level errors via a hypothetical `raise`
  primitive, fuzzy-threshold failures (a `select` where nothing
  fired). None have been designed. Park until a real use case
  pushes one of these forward.

## [This year] Exploratory / parked

Long-form research sketches live in `planning/exploratory/` — not
commitments, just parking spots. Currently parked:
- `softmax-conditionals.md` — fuzzy conditional branching as softmax over
  named cases vs classic if/elif chains.
- `karpathy-llm-wiki.md` — Karpathy's "LLM wiki" concept; interest is in
  the context-management angle.

## [This year] Speculative

- **Sutra-embedded-in-Python (`@sutra` decorator + import hook).**
  Longer-term interoperability path. User vision (2026-04-22): a
  Python function decorated with
  `@sutra` has a Python signature (types at the boundary become the
  FFI contract) but a body written in Sutra syntax. Example:

      @sutra
      def greet(name: str) -> str:
          vector v_name = basis_vector(name);
          vector winner = argmax_cosine(v_name, [v_hello, v_goodbye]);
          return PHRASE_NAME[winner];

  The `def` line is the FFI; strings and numpy arrays cross cleanly;
  the body can only use pure Sutra ops (no imperative mutation,
  which the compiler enforces). Mechanism options: an import hook
  that preprocesses `.py` files before Python sees them, or
  explicit `sutra.compile(fn)` / `sutra.run("""...""")` calls for a
  less magical version. PHP-in-HTML is the prior-art analogy —
  host language is declarative scaffolding, embedded language is
  the active computation, demarcation is meaningful not cosmetic.

  Why this matters: adoption. HDC researchers live in Python; their
  vectors live next to datasets and pipelines. A Sutra that ships
  as a PyPI library with `@sutra`-decorated functions lets them
  write real Sutra programs without leaving their existing
  environment. The segregation (imperative Python handles I/O,
  functional Sutra handles vector computation) is a *feature*, not
  a compromise.

  Scope sketch:
  1. PyPI package (`pip install sutra`) that wraps the existing
     `sdk/sutra-compiler`.
  2. `@sutra` decorator that marks a function for Sutra compilation.
     The Python-visible function becomes a thin wrapper that
     marshals args in, executes the compiled Sutra body, and
     marshals return values out.
  3. Import-hook or AST-preprocessing so the Python parser doesn't
     choke on Sutra syntax in the decorated body. A compilation
     step that runs before Python sees the file is the simplest
     path; import hooks are the seamless path.
  4. Type marshalling: `str → vector` via `basis_vector`, `numpy
     array → vector` pass-through, `vector → str` via codebook
     lookup or caller-supplied serializer.
  5. IDE support for the dual-layer file. VSCode's embedded-language
     mechanism (CSS-in-JS precedent) is designed for this pattern
     but is non-trivial to wire up for a new outer+inner language
     pair.

- **OWL → SutraDB extension + Sutra ontology import/editing.** Build out
  OWL handling so SutraDB gains a first-class ontology extension and Sutra
  gains ontology-aware operations. Protégé may be a more helpful starting
  point than raw OWL files. Scope expansion; revisit after Claw4S.

---

# SutraDB (appended from former `sutraDB/TODO.md`) — lower priority

Companion Rust triplestore (own crate, own `sutraDB/CLAUDE.md`); 228/249
items complete. All items below are **[This year]** unless noted.

## SutraDB — Next Release (v0.3.1): Gradle Migration, MCP Agentic UX, Maven Central

- [ ] Merge Gradle migration + Maven Central publishing setup (local commits).
- [ ] Bump version to 0.3.1 in `sdks/java/build.gradle.kts` and all other
  SDK configs.
- [ ] Set up Maven Central secrets: `MAVEN_USERNAME`, `MAVEN_TOKEN`,
  `GPG_PRIVATE_KEY`, `GPG_PASSPHRASE`. Generate GPG key, upload public key
  to keyserver.
- [ ] Tag `v0.3.1` and push to trigger publish workflow. Verify
  `io.github.emmaleonhart:sutradb:0.3.1` appears on Maven Central.

## SutraDB — Java/Kotlin SDK

- [ ] Integration test: start SutraDB, insert triples, query, verify
  round-trip.
- [ ] OWL validation (match Python SDK: domain/range/subclass/disjoint/
  equivalent).
- [ ] Connection retry logic with configurable timeouts.

## SutraDB — Future Versions

### AI Agent Installer
- [ ] End-to-end test: fresh install → insert → query → verify.
- [ ] Serverless mode testing.
- [ ] Agent-consumable structured output (JSON mode).

### HNSW Traversal via SPARQL Property Paths
- [ ] Greedy descent + beam search semantics from graph structure and
  property path evaluation.
- [ ] Test: `sutra:hnswNeighbor+` produces correct ANN results.

### Predicate-Based Exit Conditions (UNTIL)
- [ ] Design UNTIL syntax for exit conditions on property path traversal.
- [ ] Per-step predicate evaluation during traversal.
- [ ] Backtracking interaction, ordered traversal, HNSW-specific exit.

### Cost-Based Query Planning
- [ ] HNSW as access path: planner chooses HNSW index scan vs SPO scan.
- [ ] Adaptive execution: observe intermediate result sizes, reorder mid-query.

### Background Maintenance Cycle
- [ ] Low-usage detection heuristic.
- [ ] Background HNSW rebuild with atomic swap.
- [ ] Background pseudo-table rediscovery and rebuild.

### Pseudo-Tables
- [ ] Invalidation tracking; update planner to match multi-pattern SPARQL
  queries to subgraph pseudo-tables.

### Database Health Dashboard
- [ ] Per-pattern latency percentiles, planner decision accuracy.
- [ ] `sutra health --json` for programmatic agent consumption.
- [ ] Sutra Studio health dashboard as Flutter landing page.

### SDK Publishing
- [ ] Python → PyPI, TypeScript → npm, Rust → crates.io, C# → NuGet,
  Go module tag.

### Sutra Studio
- [ ] Remote Studio access over the network.
- [ ] Dart FFI bindings replacing HTTP client.
- [ ] Studio-embedded MCP server (background thread).
- [ ] Flutter graph view parity with `browse.html`.
- [ ] Long-term: absorb core Protégé functionality.

### Query Language Wrappers
- [ ] Cypher → SPARQL transpiler.
- [ ] GQL (ISO 39075) → SPARQL transpiler.
- [ ] Query validation: reject constructs that can't map to RDF.

### Premium Tier — deferred until paying customers
RBAC, encryption at rest, TLS, audit logging, replication, clustering /
sharding, multi-tenancy, connection pooling.

## SutraDB — Reference Architectures

| System | Why |
|--------|-----|
| [Qdrant](https://github.com/qdrant/qdrant) | HNSW impl, visited pools, normalize-at-insert |
| [Oxigraph](https://github.com/oxigraph/oxigraph) | RDF storage, SPO/POS/OSP, SPARQL pipeline |
| [DataFusion](https://github.com/apache/datafusion) | Cost-based planning, join ordering, vectorized execution |
| [DuckDB](https://github.com/duckdb/duckdb) | Columnar analytics, zonemap pruning, join ordering |
| [GlueSQL](https://github.com/gluesql/gluesql) | Small readable query engine |
| [Limbo](https://github.com/tursodatabase/limbo) | Rust SQLite reimpl, storage ideas |
| [Materialize](https://github.com/MaterializeInc/materialize) | Streaming SQL on Differential Dataflow |

SutraDB benchmark baseline: `sutraDB/benchmarks/LATEST.md`.
