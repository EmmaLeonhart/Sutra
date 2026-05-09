# Sutra — consolidated TODO

This file is the long-term agenda. `queue.md` at the repo root is the
active session queue — if the two disagree, queue.md wins for what is
being worked on *now*, and this file wins for what needs doing
*eventually*. Do not re-split this into per-subdirectory todo files.

## 🗂 Priority levels

- **Immediate** — do right now / this session. Usually mirrored in `queue.md`.
- **This year** — should land in 2026, not necessarily tied to a deadline.

When adding an item, pick a level. When closing one, delete the line.

Note: the "Pre-Claw4S" priority level (deadline 2026-04-20) was retired
on 2026-04-20 when the papers/submission layer was removed from the
repo. Items that used to live under it have either been completed
(sign-flip removal → rotation binding, 2026-04-22) or no longer apply
(paper-scope maintenance) or moved to findings (substrate design work
is now ongoing under `planning/findings/` rather than deadline-driven).

---

## TS transpiler / Sutra postponed pieces (2026-05-08)

Four deferred dimensions of the TS → Sutra pipeline. The core
transpiler shipped 2026-05-08 with 12 fixtures green end-to-end
(TS source → `.su` → runnable Python). These are explicitly
postponed; pick up when context-shifts.

- [ ] **`Math.*` shims** (`Math.sqrt`, `Math.PI`, `Math.sin`, etc.).
  Gated on Sutra-side transcendentals — currently disabled in the
  codegen with a `CodegenNotSupported` pointer at
  `sdk/sutra-compiler/sutra_compiler/stdlib/math.su`. The TS
  transpiler can already emit `Math.sqrt(x)`-shape calls; they
  fail at Sutra codegen until the transcendental work below is
  picked up. See "[This year] Compile-time math function
  approximation" below.

- [ ] **`async` / `await` / `Promise`**. Sutra has no concurrency
  primitive that matches Promise semantics today. **User
  hypothesis (2026-05-08): promise / async are likely related to
  axons** — both are lazy-materialization stories (a Promise is a
  value-not-yet-computed; an axon defers materialization to the
  receiver's actual reads). The user explicitly noted they don't
  know JS Promise semantics well enough to commit to a mapping;
  flagged for design work when the time comes. If the axon angle
  pans out: `async function f(): Promise<T>` could lower to a
  function returning an axon, with `await p` becoming an axon
  read. Park until either `planning/sutra-spec/concurrency.md`
  consolidates a surface OR the multi-program axon demo (below)
  reveals what shape inter-program lazy values actually want.

- [ ] **Module imports** (`import { X } from "./foo"`). v1 is
  single-file: each `.ts` file lowers independently to one `.su`
  file with no cross-file resolution. Lifting needs a Sutra-side
  module system first (`planning/sutra-spec/program-structure.md`
  is explicit there is no `import` today) and a transpiler-side
  mapping from TS module graphs to whatever cross-file form Sutra
  adopts. Cross-cuts with the multi-program axon demo below.

- [ ] **Multi-program axon passing with lazy evaluation.**
  `axons.md` claims that only the keys the receiver references
  actually cross a program boundary. Never demonstrated end-to-
  end: every `.su` example is single-program, and
  `program-structure.md` is explicit there's no module / import
  system. User flagged this 2026-05-08 as the actual open axon
  question — within a program the loop's recurrent state already
  *is* an implicit axon, but between-program axon passing is
  unbuilt. Concrete shape of the demo: two `.su` programs, one
  publishes a wide axon (10+ keys), the other reads a small
  slice; verify in the compiled artifact that only the
  referenced slice materializes on the wire. Spec-validation
  task. Cross-cuts with module imports above (both want inter-
  program semantics) and with promise/async above (both are
  lazy-materialization stories).

---

## [This year] Object encapsulation — language ergonomics

**Source:** Emma 2026-04-30 (during the loop-tail-call-surface work).
**Steps 0, 0.5, 1, 2 (partial), 3 (no-op), 4, 6 (partial) shipped 2026-05-01.**

The rule: free (non-object) functions read file-scope; object
methods (static or non-static) do not. The validator emits
**SUT0144** on any method body that reads a file-scope name.
Class bodies accept method declarations (regular, static,
intrinsic, static-intrinsic) and loop function declarations.
Static methods compile via mangled wrappers; non-static methods
take `this` as their first param; class loop functions emit as
`_loop_{Class}_{name}`. `Class.method(...)` and
`loop Class.name(...)` both dispatch correctly. The
stdlib_loader picks up class-bodied static methods alongside
top-level FunctionDecls.

Per Emma's 2026-05-01 correction: there is no closure in Sutra
— what the design calls "closure" is namespace-access scoping
(free functions read file-level names through Python's natural
emission, methods see only their class). The "free-function
file-level closure" step is therefore a no-op.

See `planning/open-questions/function-taxonomy-and-closure.md`
for the full taxonomy.

Remaining work:

- [ ] **Migrate the four remaining stdlib files** to class-as-namespace
  shape: `logic.su`, `similarity.su`, `vectors.su`, `rotation.su`.
  Their bodies use the `loop (10)` form which still works but
  needs a careful check that the inliner still expands them
  correctly inside class bodies (it does, per the 2026-05-01
  inliner extension).
- [ ] **Field declarations inside class bodies** (`field x : int;`).
  Without fields there's no per-class state for non-static methods
  to encapsulate, and step 5 (class-level slots) has no referent.
- [ ] **Non-static object loops with `this` threading.** Today
  class loops are effectively static — the cell function takes
  only the declared state params. Per Emma's design, non-static
  loops should pass `this` through each iteration so the loop
  walks the same instance. Implementation: insert `this` as an
  implicit additional state parameter on non-static class loops.
- [ ] **Instance-syntax dispatch on typed variables** (`g.method(args)`
  for `Greeter g`). Needs variable type tracking through the
  codegen.

## [This year] Make `sutralang.dev` more agent-accessible

Sutra's stance per CLAUDE.md is that agents are first-class consumers
of the documentation, not an afterthought. The site is already
markdown-driven, but specific moves to take it further:

- [ ] Expose the docs through an MCP server (or a documented
  fetch-this-URL pattern) so agents can query Sutra's surface
  programmatically rather than scraping HTML.

---

## [This year] Rotation-hashmap capacity + Monte-Carlo exploration

The rotation-hashmap library-pattern prototype landed 2026-04-22
(5/5 exact-lookup on nomic; `examples/_rotation_hashmap_test.py`).
Two follow-ups flagged during that work:

- [ ] **Cross-substrate attractor comparison.** Follow-on to the
  2026-04-22 single-substrate result. Train separate MLPs on
  nomic, mxbai, and minilm codebooks. Compare: does v0 land in
  queen's basin on nomic only, or does the MLP "rescue" queen on
  the weaker substrates too? The cross-substrate sweep
  (`_king_queen_multi_substrate.py`) showed mxbai and minilm fail
  naive analogy — the interesting question is whether attractor
  dynamics can recover the right answer anyway.

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

## [This year] Per-program embedding-space override

User direction 2026-04-22: *"programmes should be able to have their
native embedding space [declared] at the beginning of them as an
override thing so that we could have a bunch of different test
programmes that show it in different vector spaces."*

Current state: `NumpyCodegen.__init__` already accepts `llm_model=...`
as a kwarg, but there's no source-level way to set it — the codegen is
invoked with default args by `examples/_smoke_test.py`.

Minimum scope:
- [ ] Source-level declaration (not a comment) — a `embedding_space`
  pragma the parser recognizes. Decide after seeing how the magic-
  comment version is used in practice.

## [This year] `main(embedding_space: string)` compile-time override

User direction 2026-04-23: *"the runtime override, honestly, it
wouldn't be at runtime; it would be at compile time"* and *"both of
those things go after the anthropic application."* Moved from
queue.md (where it was erroneously framed as runtime override) to
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

## [This year] Concurrency — only the cases that need explicit handling

User direction 2026-04-22 (afternoon): concurrency is implicit by
default in Sutra because the language's functional algebraic nature
already gives the compiler license to evaluate independent sub-
expressions in parallel via formula simplification. **An explicit
syntax is only needed for the cases where the compiler can't derive
the parallelism algebraically**.

The shapes that still need explicit handling:

- [ ] **Concurrent looping.** Each declared loop function
  (`do_while` / `while_loop` / `iterative_loop` / `foreach_loop`)
  is a single trajectory today. A concurrent form would run N
  independent trajectories in parallel — same cell, different
  initial states, collected as a basin distribution. Surface
  syntax TBD; probably an extension of the existing call form
  (e.g. `loop[N] NAME(...)` for N parallel runs) given the
  user's "implicit except where needed" framing.

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

## [This year] Learned-matrix binding

Deferred from the 2026-04-22 rotation-binding pass. The feature is
genuinely useful (see `feedback_learned_matrix_is_not_next.md`) — it's
simply not the next active item. When picked up:

- [ ] Add a matrix-fitting step at compile time. A `role X =
  learned_from(data)` declaration reads `(input, output)` embedding
  pairs and fits R via lstsq (or Procrustes, or low-rank —
  substrate-dependent).
- [ ] Wire the `role` surface syntax into the parser. queue.md item
  3's decision (Candidate B: `role` / `var`) is resolved at the spec
  level but not implemented in `sdk/sutra-compiler/`.
- [ ] Emit `R @ filler` runtime for semantic roles; `R.T @ record`
  for unbind (or precomputed pinv for non-orthogonal R).
- [ ] A new demo that exercises learned-matrix bind end-to-end (e.g.
  a `located_in_country` program using cartography-style displacement
  data).

## [This year] Extended state vector — remaining integration

The runtime-primitive half of the extended-state / synthetic-subspace
design landed 2026-04-24 (`planning/findings/2026-04-24-slot-rotation-
runtime.md`). `_VSA` now exposes `slot_store` / `slot_load` /
`rotate_slot` — 48 disjoint 2D-Givens slots in the synthetic block,
exact reversibility, zero semantic drift. All 4 reversibility tests
PASS on the compiled runtime.

What this pass closed:
- [ ] Compile-time slot allocator — map named variables to slot
  indices deterministically, with a compile-error when capacity
  (48 slots per program at synthetic_dim=100) is exceeded. Lands
  alongside the slot codegen integration (see "Compilation updates"
  below).

## [This year] Compilation updates

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

Not blocking the active work; grouped because they are of a piece.

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
- **`^` (exponent) as a Sutra operator** (declared 2026-04-29 from
  the transcendentals chat). Not a function call (`pow(x, y)`),
  not a derived form — a first-class infix operator on the number
  axis. User reasoning: "there are no bits in Sutra," so `^` is a
  numeric primitive, not a bitwise XOR (which is what `^` means
  in C/Python). When implementation lands: lexer needs `^` token,
  parser needs an infix-binary production at the appropriate
  precedence (above `*`, right-associative is the math convention),
  codegen routes through whatever exponentiation tier the math-
  approximation work picks (Chebyshev for non-integer exponents,
  potentially the rotation-based path from the transcendentals
  chat for the trig family). Source-of-truth for the algorithm:
  the §"Transcendental functions — design absorbed from voice
  chat" section at the bottom of this file.

## [This year] Make loops idiomatic

The 2026-04-30 loop redesign (`planning/open-questions/loop-function-declarations.md`)
ships loops as first-class declared functions with `pass` for tail-recursive
yield and `loop name(args)` call sites that mutate caller variables by
reference. Emma 2026-04-30: "this is a bit of a weird thing... it's
unidiomatic... I'm probably going to figure out a nicer way to represent
this at some point. I'm not going to be able to do this right now though...
my priority is making it fucking work."

So: ship the by-reference form first (substrate-pure RNN cell, body
actually runs, completion flag propagates), then later this year revisit
to make it idiomatic. Likely cleanup direction: loop calls return a
tuple of state values that the caller assigns explicitly, eliminating
the by-reference surprise:

```sutra
x = loop addNumber(x < 11, x);          // single-state return
(max, count) = loop findMax(arr, 0, 0); // multi-state return
```

Don't touch this until the function-declaration form has shipped and a
few real programs have exercised it — premature cleanup risks designing
the wrong thing.

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

## [This year] Smoke-test substrate-margin notes

The smoke test (`examples/_smoke_test.py`) reports overall PASS as of
2026-05-01. Two soft notes worth keeping:

- **`fuzzy_dispatch.su` lands 2/4 dispatches.** The dispatch
  mechanism itself (soft-mux on Lagrange-fuzzy AND/NOT scores) is
  correct; nomic-embed-text places "weather"/"music" and
  "cancel"/"alarm" on adjacent prototype clusters, so the
  argmax_cosine resolves the wrong neighbor. Test relaxed to require
  ≥ 2/4 (`run_fuzzy_dispatch` line ~256). A better-separated
  substrate or a manually-tuned prototype set would push this to
  4/4 without compiler changes — the demo isn't broken, the
  embedding geometry is the limit.
- **`sequence.su` self-similarity** previously failed an
  unrealistically tight `(0, 0.5)` window for `sim(fox, dog)`; the
  test now reports `sim(fox,dog)=+0.827` and asserts only "cross <
  self," which holds.

## [This year] Sutra-NumPy: a substrate-native numerical library

User direction 2026-04-29: build Sutra's equivalent of NumPy — a
numerical library whose primitives compile to substrate operations
(rotations, eigenrotations, matmul, lookup tables, Chebyshev
polynomials) instead of libm / BLAS calls. **Explicitly NOT in the
initial MVP.** This is later-this-year scope; the MVP keeps the
existing math intrinsics as stubs (per the math-approximation
section below) and the language-correctness work stays the focus.

The umbrella covers what's already broken out below as separate
entries plus what isn't yet broken out:

- **Already tracked**: compile-time math approximation tiers
  (Chebyshev / lookup / CORDIC — see next section), `[backend]`
  dtype configuration, eigenrotation-as-trig (de-prioritized
  architectural-uniformity refactor — see findings 2026-04-28).
- **Not yet broken out** (umbrella scope to add later):
  substrate-native linear algebra primitives (matmul, decomp,
  pinv) routed through the rotation/Givens machinery where
  possible, rather than calling torch.linalg directly. Random
  number generation. Statistics primitives. Array-creation /
  slicing / broadcasting as first-class language constructs.

The pitch: when Sutra is doing math, it should be doing math on
its own substrate, not bouncing out to torch's host-side numerical
stack. The architectural-uniformity argument from the
eigenrotation finding (2026-04-28) generalizes — uniform substrate
operations enable global-efficiency fusion in a way that
host-side calls never can. The cost-per-op story is mixed (see
that finding); the *whole-program-fusion* story is the actual win.

This entry exists so the broader vision is captured without
expanding the MVP. When the MVP lands and the focus shifts here,
the per-piece work below will get re-organized under this
umbrella. Until then, treat the per-piece entries as the active
slice.

## [This year] Compile-time math function approximation

User direction (2026-04-25): "Make a math library and some
compilation wizardry." The Kolmogorov–Arnold angle says any
continuous function decomposes into univariates, which can be
approximated as tensor ops on a bounded domain. Sutra should
compile `log`, `sqrt`, `sin`, `exp`, etc. to tensor expressions at
compile time rather than calling out to libm at runtime. See
`docs/numeric-math.md` § "Transcendental functions" for the
design.

User direction (2026-05-01): the unlock is **natural log + exp(E)**.
If we get a reliable, substrate-pure way to represent those two,
everything else cascades — `Pow(a, b) = exp(a * log(b))` makes `^`
work, and the rest of the transcendental family composes from
there. Lookup-table approach was attempted and didn't pencil out
(see `planning/findings/2026-04-29-bound-table-capacity-limit.md`);
worth retrying with a different shape. The principle: every
non-recursive function beta-reduces to its components, so once the
two leaves work, the chain is done.

Pieces below are sub-pieces of the broader Sutra-NumPy umbrella
above; tracked separately because they're the active slice.

Concrete work:

- [ ] **Add `[math]` section to `atman.toml`** with
  `approximation_precision` (target abs error) and
  `approximation_method` (`"chebyshev"` / `"lookup"` /
  `"cordic"`). Parse it in `sdk/sutra-compiler/sutra_compiler/
  workspace.py` (or wherever atman.toml is read).
- [ ] **`stdlib/math.su` math intrinsics** (`log`, `sqrt`, `exp`,
  `sin`, `cos`, `tan`, `pow`). 2026-04-29 implementation was
  withdrawn 2026-04-30 because it ran as host Python scalar
  arithmetic at runtime (substrate-purity violation; values were
  correct but architecture wrong). Codegen now rejects calls
  with a clear CodegenNotSupported pointing at math.su. Future
  direction: eigenrotation-as-modulus (Emma 2026-04-30 hunch —
  the unit circle is naturally periodic so applying R unboundedly
  could give substrate-pure trig without floor-based range
  reduction). Re-implementation needs a real design first;
  belongs in `planning/open-questions/` when picked up.
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
- [ ] **Eigenrotation as a substrate-uniformity refactor for trig
  intrinsics** (de-prioritized 2026-04-28 after validation).
  User insight 2026-04-28: rotation matrices contain sin/cos as
  their entries by definition, so `sin(x)` = "build R(x), apply
  to (1,0), read y-coordinate." Exploratory writeup:
  `planning/exploratory/eigenrotation-for-sine-and-modulus.md`.
  Validated 2026-04-28 in
  `planning/findings/2026-04-28-eigenrotation-as-trig-validation.md`
  via `experiments/eigenrotation_as_trig.py`:
  - Math identity holds (trivially).
  - "Modulus for free" is real but inherited from libm's range
    reduction — not a Sutra-specific differentiator.
  - **Cost-saving claim REFUTED.** Rotation path is 1.41× scalar
    direct trig and 99× vectorized direct trig on numpy CPU. The
    rotation builder calls *both* `cos` and `sin` to fill R, then
    adds a 2×2 matvec — strictly more work, not less.
  - Surviving Sutra-specific value is architectural only: one
    runtime code path instead of two (substrate-uniformity for
    trig). Not a speed win.
  - Cost-win story would only materialize on hardware rotation
    primitives (CORDIC / FPGA / future native instructions),
    which is not where Sutra runs today.

  Implication: this is a "nice cleanup if/when we touch the
  math-tier code" item, NOT a priority feature. It does not
  justify prioritizing it ahead of the Chebyshev / lookup /
  CORDIC tiers above. Kept in the queue so we don't re-derive
  the insight; not a near-term work item.

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

## [This year] Ontology — make the class system real

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
- [ ] Build `sutra_ffi.dll` so `tests/test_sutradb_embedded.py` stops
  raising `FileNotFoundError`. Local fix: `cd sutraDB && cargo build
  --release -p sutra-ffi`. All 245+ other tests pass without it; not
  paper-blocking, fix when convenient.
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

## [This year] Future Goals

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
- **Sutra on commodity hardware end-to-end.** Every operation from
  `02-operations.md` running on a laptop substrate (the connectionist-
  computer work above is the path here). Numpy allowed only at the
  compile/monitor boundary, never at runtime.

## [This year] Integer class — follow-on work

The integer class landed as a compile-time tag on 2026-04-22
(augmented assignment works; `var n : int = 0; n += 1;` compiles
and runs). The canonical number axis in the synthetic subspace is
spec'd (see `planning/sutra-spec/types.md` §"The number axis and
the integer class" and
`planning/sutra-spec/equality-and-defuzzification.md` §"Canonical
axes in the synthetic subspace").

Follow-on work (none of this is in master yet):
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

The `foreach_loop NAME(array, state) { pass element(state); }`
declared-function form (2026-04-30 redesign) walks a Sutra
binding-array at runtime, so the old "Dynamic foreach" question is
now answered: dynamic iteration goes through `foreach_loop` over a
binding-array (`array_from_literal` / `array_length` /
`array_get`). The earlier compile-time `foreach (x in [a,b,c])`
unroll-over-literal form is folded into the same surface — a
literal array is just a binding-array constructed at compile time.

Remaining piece:

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

## C → Sutra transpiler — parked (deprioritized 2026-05-08)

Skeleton landed at `sdk/sutra-from-c/` (commit `6970c52`); `c2su`
CLI exits 2 pointing at `DESIGN.md`. Decision 2026-05-08: user no
longer views transpiling Linux as a useful path to OS-level Sutra
work, so the C transpiler is no longer paired with the TypeScript
transpiler as a Yantra prerequisite. TypeScript is the sole
transpiler gate.

The skeleton stays in tree — do not delete it. If a future use case
revives the need for C-source ingestion (some specific kernel
component, a runtime library someone wants to lift into Sutra), the
DESIGN.md and skeleton are the starting point.

Until then this is the very back of the queue.

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
  point than raw OWL files.

## [This year] Transcendental functions — design absorbed from voice chat

User direction (voice conversation, mid-2026 — full chat absorbed
2026-05-02 from `chats/implementing-transcendental-functions.md`,
which has since been deleted). The intuition that crystallized
during the chat: in the complex plane, the four "main"
transcendentals — exponential, logarithm, sine, arc-sine — are
all the same operation viewed from different angles.

- `exp(x + iy)` is scaling (real part) plus rotation (imaginary
  part). On the unit circle (`x = 0`) it's pure rotation by `y`
  radians. Scaling and rotation compose because exponents
  multiply: `exp(a + b) = exp(a) * exp(b)`.
- `sin` is the imaginary part of `exp(iθ)`. Cosine is the real
  part. They're not independent operations — they're projections
  of the rotation onto the two axes.
- `log` inverts: real part of the log is the magnitude (how much
  scaling), imaginary part is the angle (how much rotation).
  `log(-1) = iπ`, `log(i) = iπ/2`. The "log of negative numbers
  doesn't exist" graph is lying by omission — it just means the
  output is on the imaginary axis. Zero is the only genuine
  asymptote.
- `arcsin` is just `log` in disguise — given an imaginary value,
  find the rotation that produced it. The branch-cut artifact
  arises from picking which of the infinite valid rotations to
  return.

### Two primitives, lookup tables, everything else derived

The Sutra implementation reduces to **two primitives**: `exp` and
`ln`. Both backed by lookup tables. Everything else beta-reduces:

```
x ^ p              ->  pow(x, p)            (operator desugar)
pow(x, p)          ->  exp(p * ln(x))       (change-of-base identity)
log(b, x)          ->  ln(x) / ln(b)        (change-of-base for log)
sin(θ)             ->  imag(exp(iθ))        (definitional)
cos(θ)             ->  real(exp(iθ))        (definitional)
arcsin(z)          ->  imag-extract(log(...))  (deferred)
sinh / cosh / tanh ->  combinations of exp(x), exp(-x)  (deferred)
```

`exp(1)` returns Euler's number — no need to hardcode `e` as a
constant; it falls out of the primitive.

### `^` operator (no XOR conflict in Sutra)

`^` is exponentiation. Sutra has no bits to flip, so the C-family
"^ means bitwise XOR" convention doesn't apply — XOR exists only
as a logical connective on the truth axis (and is reachable as
the keyword `xor` plus the parser-level chain reductions). `^`
binds above `*`, right-associative is the math convention.

### `sin` via rotation matrix, not lookup

Per the Emma 2026-04-28 eigenrotation finding (validated, refuted
on speed but accepted for substrate-uniformity), sine via rotation
matrix is one matmul. The rotation matrix entries are sin/cos of
the angle, so it does a self-referential thing internally — but
once Sutra has `exp` working on the imaginary axis, the rotation
matrix can be built from `exp(iθ)` instead of calling out to libm
sin/cos. That closes the loop: every transcendental in the
language compiles down to `exp` and `ln` lookups.

### Implementation order, when picked up

1. **`exp(x)` lookup table** for real x in a bounded range, plus
   integer-iteration for the part outside the range and
   geometric-root for the fractional part. Substrate-pure (no
   host scalar arithmetic — that was the architecture mistake
   the 2026-04-29 implementation made and got withdrawn).
2. **`ln(x)` lookup table** for positive real x. Negative x
   handled by `ln(-x) + iπ`. Zero raises (genuine asymptote).
3. **`exp(z)` for complex z** = `exp(real(z)) * (cos(imag(z)) +
   i sin(imag(z)))`. With the rotation-matrix path for sin/cos,
   this is one scalar lookup plus one rotation matmul.
4. **`pow`, `log`, `sin`, `cos`** as inliner-expanded calls over
   the two primitives. No new runtime ops.
5. **`arcsin`, hyperbolic** deferred — useful for completeness
   but not needed for the language to be complete.

The bound-table-via-binding approach didn't pencil out
(`planning/findings/2026-04-29-bound-table-capacity-limit.md`),
but the lookup-table approach the chat settled on is different —
it's a flat table-plus-interpolation, not a VSA-bundle of bound
table entries. Worth retrying.

This is a "later this year" item, not blocking. Re-implementation
needs a real design doc in `planning/open-questions/` before
codegen, plus a re-validation pass against the substrate-purity
audit.

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
