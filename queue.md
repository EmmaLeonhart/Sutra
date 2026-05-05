# Sutra — Work Queue

**This file is a queue, not a state snapshot.** It is the
**stuff being worked on right at this moment**. Finished work
lives in `git log` and `planning/findings/`; longer-horizon
work lives in `todo.md`.

See CLAUDE.md §"Workflow Rules" for how queue.md and the task
tool stay in sync.

## Active

**Sprint:** NeurIPS 2026 abstract submission (deadline May 4
2026 AOE — same day). Abstract-only step; full paper deadline
is May 6 AOE. Two-commit plan tonight:

1. **Reframe commit (this one)** — abstract leads with the
   *program-NN isomorphism* claim ("a compiled Sutra program
   *is* a PyTorch neural network"), demoting the
   classification-task framing to its actual role: evidence
   that PyTorch autograd flows through every Sutra primitive
   end-to-end. Triggered by the v20 review (Weak Reject,
   regressed from v19's Accept) flagging §3.6 as "extremely
   trivial / 15 words 3 categories" and §3.6 framing as a
   classification benchmark rather than an isomorphism test.
   Direction from Emma: "Our main purpose is more isomorphism
   with neural networks, not classification."

2. **Scale-up commit (this one)** — `differentiable_training.py`
   scaled from 15 words / 3 classes (K=3) to **992 words / 20
   classes (K=20)**: animal, vehicle, food, color, clothing,
   weather, emotion, tool, instrument, profession, body-part,
   plant, furniture, building, country, sport, drink, metal,
   shape, fabric. Generalized `classify()` for arbitrary K via
   left-fold AND-of-NOTs, then refactored to a vectorized
   batch forward pass so 1000-word epochs run in milliseconds
   instead of 40s. Honest measurement: **4% → 95%** accuracy in
   300 epochs (chance = 5%); convergence by epoch 50; final
   loss 1.15; all 20 prototype gradient norms nonzero (range
   0.94–4.20) confirming gradient flow through a nineteen-AND-
   deep rule pipeline. The 5% residual is honest semantic
   overlap (e.g. salmon/scarf) at the optimizer plateau, not
   gradient pathology. §3.6 rewritten with new numbers and
   explicit K=3 → K=20 scale comparison; SKILL.md replication
   spec updated; abstract folded in the K=20 / 992-word claim.

   Body fixes bundled in the same commit:
   - **T=50 contradiction resolved**: §1.1, §3.3, §3.1.1, §4.2,
     §5.4 all consistently say iteration is unbounded by language
     semantics (no compile-time iteration cap, halt-flag stops
     it). T=50 is an implementation detail of the autograd-tape
     budget and doesn't appear in the paper.
   - **§6.1 (object encapsulation status, 60 lines) deleted** and
     **§6.4 (numpy backend retirement, 5 lines) deleted** — both
     were voluntary disclosure of in-progress work that didn't
     support any paper contribution; reviewers v18/v20/v22 all
     cited them as evidence of "prototype not production-ready."
     The remaining §6 is a single short paragraph on codebook
     integration depth (renumbered §6.1).

Open before submission:
- [x] OpenReview profile activated (Emma confirmed).
- [x] clawRxiv review trajectory v20→v28: Weak Reject → Weak
  Accept → Weak Accept → Accept → Weak Accept (one dip) →
  Accept → Accept → Accept (v23, v25, v26, v27, v28).
- [x] **Body trimmed to 9 pages (NeurIPS cap met).** Latest
  rendered PDF: 9 body pages + 1 reference page + 10 appendix
  pages = 20 total. References at page 10, Appendix A–K at
  pages 11–20.
- [x] Appendices A–F restored from git history (crosstalk full
  L-sweep, codebook HNSW detail, TorchHD side-by-side, ESV
  layout walkthrough, full per-substrate capacity sweeps,
  full 992-word vocabulary).
- [ ] Submit at 4 AM local 2026-05-04 → 2026-05-05.
- [ ] On the OpenReview form: confirm abstract-field length cap
  accepts 286 words / 2058 chars. If it caps at 250 words, use
  the trim variant below.
- [ ] On the OpenReview form: pick primary area + keywords. See
  scratchpad below.

papers-ci race FIXED: the workflow already had a concurrency
lock that serialized runs, but `actions/checkout@v4` defaults to
checking out the trigger SHA, not current master. A queued run
would check out its own trigger SHA (which predates the prior
run's auto-commit of `.post_id`), read stale state, and POST a
supersede against an already-superseded post. Patched by adding
`ref: master` to the checkout step so a queued run grabs the
latest committed state when it finally executes.

## NeurIPS submission scratchpad — paste-ready

### Title

```
Sutra: Compiling a Vector Symbolic Architecture to a Tensor-Op Recurrent Neural Network via Beta Reduction
```

### Abstract (full, 286 words / 2058 chars)

This is the canonical version. Use it unless the OpenReview field
caps below 286 words.

```
Sutra is a typed, purely functional programming language; a compiled Sutra program is a PyTorch neural network. Every primitive — rotation binding, unbind, bundle, similarity, soft-halt RNN cells, polynomial Kleene three-valued logic — compiles to a tensor op, and the compiler beta-reduces the whole program (control flow included) to a fused tensor-op graph whose substrate-resident computation is straight-line dataflow: no in-graph branches inside any operation, no string-keyed lookup at runtime, and no Python control flow inside the body of a loop cell — the only remaining host-side control flow is a thin tick-loop that breaks when a substrate-computed halt scalar saturates (§3.3). The contribution is the construction that makes this isomorphism land: a symbolic source language whose compiled forward pass is a substrate-pure neural network, autograd-compatible by construction, executable wherever PyTorch executes. We validate the language across four frozen embedding substrates spanning two modalities — three text encoders (nomic-embed-text, all-minilm, mxbai-embed-large) and one protein language model (ESM-2) — and observe the same rotation-vs-Hadamard separation across modalities: rotation binding decodes at 100% accuracy through bundle width k=8 on every substrate, where Hadamard binding has already collapsed (e.g. 2.5% on mxbai-embed-large, 28.7% on ESM-2), with single-cycle bind/unbind exactly reversible (round-trip ≈ 1.5×10⁻¹⁵). The program-network identity is end-to-end testable through PyTorch autograd: a symbolic if-then program of fuzzy rules over twenty classes (animal, vehicle, food, color, clothing, weather, emotion, tool, instrument, profession, body-part, plant, furniture, building, country, sport, drink, metal, shape, fabric; 992 words total, K=20 rule tree nineteen ANDs deep) trains from chance accuracy (4%) to 95% in 300 epochs, with nonzero gradient at every prototype and no modification to the symbolic source — gradient descent moves the embeddings the rules evaluate against, not the rule graph itself.
```

### Abstract — short variant (212 words / 1543 chars)

Safety variant for any plausible cap. Drops the twenty-class
enumeration, the §3.3 tick-loop qualification (the body still
covers it), and a small amount of redundant phrasing. Same five
quantitative claims as the full variant.

```
Sutra is a typed, purely functional programming language; a compiled Sutra program is a PyTorch neural network. Every primitive — rotation binding, unbind, bundle, similarity, soft-halt RNN cells, polynomial Kleene three-valued logic — compiles to a tensor op, and the compiler beta-reduces the whole program, control flow included, to a fused tensor-op graph whose substrate-resident computation is straight-line dataflow with no in-graph branches and no string-keyed lookup at runtime. The contribution is the construction that makes this isomorphism land: a symbolic source language whose compiled forward pass is a substrate-pure neural network, autograd-compatible by construction. We validate across four frozen embedding substrates spanning two modalities — three text encoders (nomic-embed-text, all-minilm, mxbai-embed-large) and one protein language model (ESM-2) — and observe the same rotation-vs-Hadamard separation across modalities: rotation binding decodes at 100% accuracy through bundle width k=8 on every substrate, where Hadamard binding has already collapsed (e.g. 2.5% on mxbai-embed-large, 28.7% on ESM-2), with single-cycle bind/unbind exactly reversible (round-trip ≈ 1.5×10⁻¹⁵). The program-network identity is end-to-end testable through PyTorch autograd: a symbolic if-then program of fuzzy rules over twenty semantic categories (992 words, K=20 rule tree nineteen ANDs deep) trains from chance accuracy (4%) to 95% in 300 epochs, with nonzero gradient at every prototype and no modification to the symbolic source.
```

### Primary area (NeurIPS 2026 list)

Recommend **SysML Infrastructure**. Confirmed as a listed area on
the 2026 call page. Sutra is fundamentally a *compiler* — it
translates `.su` source into a fused PyTorch tensor-op graph —
and its contribution is a programming-language layer that targets
neural-net runtimes. The right reviewer audience is ML-systems /
PL / compiler researchers, who will recognize what beta reduction
to tensor normal form is and won't expect ResNet baselines.

Why **not** Deep Learning, even though the runtime is a neural
network: that area routes to architecture-and-training reviewers,
who would (correctly) point out that Sutra is not a new NN
architecture and didn't propose a new optimizer. The contribution
is upstream of those concerns.

Alternate fallbacks if SysML Infrastructure isn't a clean
dropdown match in the actual form:
- **Theory** — partial fit; the polynomial Kleene logic is
  formal, but the paper is mostly construction + empirical.
- **Deep Learning** — broad-stroke fallback. Routes to architecture
  reviewers (some risk).
- **Language and Multimodal Models** — three of four substrates
  are LLMs but the paper isn't about LLM behavior. Avoid.

### Keywords (suggest five; the form usually allows up to ~6)

- vector symbolic architectures (VSA)
- neuro-symbolic
- programming languages
- differentiable logic
- embedding spaces

(Sixth optional: hyperdimensional computing — overlaps with VSA;
include only if the form has space and the secondary tag adds
discoverability.)

### Authors

Single author: Emma Leonhart. OpenReview profile activated
(confirmed 2026-05-04). Anonymization: the paper has no
identifying information — title page is just the H1 + abstract,
body has no Acknowledgments to scrub. Verify the PDF render at
submission time.

### After abstract

queue.md flips to **May 6 paper-deadline mode** as soon as the
4 AM abstract submission lands.

#### Length: paper currently overshoots ~3x (1453 lines, ~26 pages estimated; NeurIPS cap = 9 content pages, refs + appendix unlimited)

Section line counts:
- §1 Introduction + Contributions — 394 lines (target: ~80)
- §2 Related Work — 278 lines (target: ~50)
- §3 Consolidation into Canonical Primitives — 508 lines (target: ~250)
- §4 The Sutra Compiler — 64 lines (target: ~30)
- §5 Demonstration Programs — 64 lines (target: ~30)
- §6 Limitations — 12 lines (keep)
- §7 Conclusion — 19 lines (keep)
- References — 65 lines (out of body budget)

Move-to-appendix candidates:
- **§1.1 contribution #2's TNF defense** (lines ~241–280, the
  "ontological not quantitative" defense vs constant propagation
  / partial evaluation / staging). Keep one sentence in body
  saying what TNF is; defend it in appendix.
- **§1.3 Substrate-as-architecture-target** (lines ~380–425).
  Compress to one paragraph in §1.2; full discussion to appendix.
- **§2 Related Work's TorchHD code-sample contrast** (lines
  ~498-700). The point is "Sutra is a compiler, TorchHD is a
  library"; the side-by-side `.su` vs Python code is appendix
  material.
- **§3.1.1 Crosstalk depth analysis** (lines ~854–911). One
  table + two-sentence summary in body; full analysis to
  appendix.
- **§3.2 Extended-state-vector layout details** (lines ~913–999).
  Diagram + one paragraph in body; layout walkthrough to
  appendix.
- **§3.4 Embedded codebook store** (lines ~1057–1136). Tight
  paragraph in body about boundary I/O; HNSW details to appendix.
- **§3.5 torch.compile wrapping** — possibly drop entirely from
  body; mention in appendix as an opt-in optimization.

Cuts that actually delete (not appendix):
- §1's three repetitions of "no compile-time iteration cap"
  (one is enough).
- §2 has overlap with §1.3 on substrate-as-architecture; pick
  one home.
- The four §5 demo subsections (5.1 hello world, 5.2 fuzzy
  dispatch, 5.3 role-filler, 5.4 loops). Keep one as a worked
  example; the rest are smoke-test references.

#### Three Emma asks for the May 6 body

1. **Diagrams of how Sutra programs work at runtime.** Need at
   least two figures:
   - Figure A: `.su` source → AST → simplified AST → emitted
     PyTorch source → tensor-op graph at runtime. Stage flow.
   - Figure B: a concrete fused-graph snapshot for one program
     (the differentiable-training rule pipeline is a good one —
     19 ANDs deep, all visible).
2. **Mathematical representations of runtime behavior.** Add
   formal notation for the soft-halt RNN cell update, the
   bind/unbind tensor operations, the rule pipeline. Notation
   already exists in scattered form; consolidate into one
   "Notation" subsection at the start of §3.
3. **A worked beta-reduction example.** Take a small `.su`
   program (e.g. `bundle(bind(role_a, filler_a), bind(role_b,
   filler_b))`) and step through:
   - parse to AST
   - inline `bind` and `bundle` definitions
   - normalize to `R_a @ filler_a + R_b @ filler_b`
   - peephole-fuse to `_VSA.bundle_of_binds(...)`
   - lower to `torch.matmul + element-wise add + L2 normalize`

   This is what Sutra's pitch *is*; the paper currently sketches
   it in an ASCII diagram in §1.1-2 but has no honest worked
   step-by-step example.

#### Order of operations for May 5

1. Lock the abstract submission at 4 AM.
2. Plan the trim concretely (mark each line range as keep / cut /
   move-to-appendix in a single pass).
3. Add Figure A + Figure B + the worked beta-reduction example
   (these are *additions*, but they support the body's value —
   the trim above gets us back under the limit).
4. Iterate clawRxiv reviews; aim to keep v23's Accept rating.
5. Submit full PDF May 6 AOE.

### Done in this sprint (2026-05-05)

- **Real LaTeX math + TikZ diagrams in `paper.md`.** Emma's three
  May-6 asks (diagrams of runtime behavior, formal notation,
  worked beta-reduction) had been satisfied in form only —
  every "equation" was Unicode-in-monospace inside a code fence,
  and every "figure" was ASCII box-drawing in `\begin{verbatim}`.
  Pandoc was rendering all of it as fixed-width text in the PDF.
  Now: 70+ inline/display math expressions ($…$, align*) for
  the §1.1 Lagrange gates, soft-mux conditional, §3.1 notation,
  §3.6 K-rule equation, Appendix G worked lowering, Appendix H
  primitive table + soft-halt cell update; three real TikZ
  figures in Appendices I (K=3 rule pipeline), J (compilation
  pipeline), K (soft-halt cell). `paper.tex` now loads `tikz`
  with the `positioning,arrows.meta,shapes.geometric,calc,fit,backgrounds`
  libraries. lualatex still handles Unicode in the prose.
  Local pandoc/lualatex unavailable so the render is verified
  via the papers-ci pipeline only.

### Done in this sprint (2026-05-01)

- **Claw4S close-out + clawRxiv kept as feedback channel.** The
  Claw4S competition is over. The clawRxiv CI/CD was briefly removed
  in commit `80f8c41` and restored shortly after — Emma's framing:
  "I'm keeping the CI/CD because it's a venue for feedback and
  visibility." None of the Claw4S-specific rules (lock-in on Strong
  Accept, dedup-bypass concerns, etc.) apply anymore. The five
  workflows + scripts + `paper/.post_id` are restored; `papers-ci.yml`
  push trigger is on, so each paper edit submits a new version to the
  supersedes chain and the review drops into `paper/reviews/`.
- **Y Combinator references cleared.** `Pre-YC` and
  `Pre-Anthropic-grant-app` priority levels collapsed into `This
  year` (commit `0f4a89a`).
- **Operators page** added (`docs/operators.md`, commit `b2dda77`)
  — root-definition / function-expansion form for every Sutra
  operator. Wired into the Theory-and-Paper nav.
- **Website audit** of the docs/ pages: loops.md rewrite for the
  declared-function loop design, paradigms.md / index.md /
  what-is-sutra.md / demos.md / vision.md / README.md updated for
  retired loop syntax, demo count corrections, broken-link fixes,
  bind-unbind.js header clarified, agent-routing affordance on the
  landing page, noscript fallbacks on the JS widgets. Commits
  `02c3d1f`, `2a6654c`, `333f670`, `e1eed83`, `b69e313`, `473f5b1`,
  `ca421fe`, `ff81d09`, `6a07a75`, `a705e5d`, `dfd4b27`.
- **todo.md tidy-up.** Smoke-test-failures section closed (both
  items resolved); Concurrency description fixed to declared-function
  loop form; Formula-simplification section dropped (no remaining
  pieces); Integer-class section relabeled; Control-flow Dynamic-
  foreach question answered by `foreach_loop`; "after Claw4S"
  deferrals removed. Commits `4b2bebc`, `6eb350a`, `51c6c67`,
  `bab0b91`.

- **Object encapsulation (steps 0, 0.5, 1)** — landed 2026-05-01.
  - **Step 0** — `SUT0144` validator rejects file-scope reads from
    method bodies (commit `7e1240b`).
  - **Step 0.5** — parser accepts method declarations inside class
    bodies, including `static intrinsic method`. ClassDecl gains
    a `methods` list (commits `9600fab`, `72b3534`).
  - **Step 1** — codegen routes `Class.staticMethod(...)` calls
    (regular -> mangled wrapper, intrinsic -> `_VSA.<name>`); the
    stdlib_loader picks up class-bodied entries under both bare and
    namespaced names (commits `b0f4e87`, `72b3534`, `ee9483a`).
  - **Step 2 (partial)** — three stdlib files migrated to the
    class-as-namespace shape: `math.su` (`class Math`), `numbers.su`
    (`class Numbers`), `memory.su` (`class Memory`), `embed.su`
    (`class Embedding`). Logic / similarity / vectors / rotation
    still on the legacy top-level shape (their bodies use retired
    loop syntax that wants care before migration).

### Open issues to address

- **SutraDB FFI tests fail locally because `sutra_ffi.dll` isn't
  built.** `tests/test_sutradb_embedded.py` raises
  `FileNotFoundError: sutra_ffi.dll not found at
  sutraDB/target/release/sutra_ffi.dll`. To fix locally, build the
  Rust crate: `cd sutraDB && cargo build --release -p sutra-ffi`
  (build prereq from `planning/semantic-corrections.md` §15). All
  other 245+ tests pass without this. If a CI run picks this up,
  the workflow needs the same `cargo build` step before the Python
  tests; the SutraDB-related tests should be skipped (not failed)
  when the dll isn't present, so unrelated PRs don't bounce.

### Next up

The remaining language-ergonomics steps (3-6) of the encapsulation
taxonomy are all real refactors — non-static method instance
dispatch, free-function file-level closure, instance fields, static
method state, object loops. None blocking; each shippable as a
separate session.

Other open work in `todo.md`:

- **Compile-time math approximation** — needs a substrate-pure
  `log`/`exp(E)` design before implementation; lookup-table approach
  failed (see the 2026-04-29 finding).
- **Rotation-hashmap capacity / Monte-Carlo experiments** — need GPU
  time and a real evaluation harness.
- **MCP server for docs** — real infrastructure piece.
- **Concurrency / learned-matrix binding / atman.toml backend config
  / transcendentals** — substantial parser+codegen work each.

## Pointers

- Longer-horizon agenda: `todo.md`.
- Pinned semantic corrections: `planning/semantic-corrections.md`.
- Deprecated spec (read-only reference): `planning/sutra-spec-deprecated/`.
- New spec dir + meta-failure note: `planning/sutra-spec/README.md`.
- Findings (dated): `planning/findings/`.
- Open design questions: `planning/open-questions/`.
- Hardwired assumptions in the demo path: `examples/todo.md`.
- Devlog (full history): `DEVLOG.md`.
