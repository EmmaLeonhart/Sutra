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

## [Pre-Anthropic-grant-app] Rotation-hashmap capacity + Monte-Carlo exploration

The rotation-hashmap library-pattern prototype landed 2026-04-22
(5/5 exact-lookup on nomic; `examples/_rotation_hashmap_test.py`).
Two follow-ups flagged during that work:

- [ ] **Capacity experiment.** Design doc is
  `planning/findings/2026-04-21-rotation-binding-capacity-experiment-design.md`;
  five concrete experiments, not yet run. Produces a findings doc
  with the capacity curve.
- [ ] **Monte-Carlo attractor search (real version).** User
  clarification 2026-04-22: this is NOT just "perturb v0 and snap to
  the nearest codebook entry" — that's random-rotation-plus-nearest-
  neighbor and is captured by the WIP placeholder script
  `examples/_king_queen_attractor_search.py`. The real Monte Carlo
  attractor search requires an MLP trained as an attractor function:
  iterating `x ← f(x)` pulls x into basins whose fixed points are the
  codebook vectors (or learned attractor points), and Monte Carlo
  samples many trajectories starting from v0 + noise to characterize
  the basin distribution. Work required:
    1. Design the MLP architecture and training objective. Hopfield-
       style energy minimization is one option; supervised training
       toward codebook attractors is another. Needs a literature
       sweep (Krotov/Hopfield modern Hopfield, Ramsauer et al. 2020,
       related attractor-network work).
    2. Train the MLP on the codebook (initially on just the 14 royal/
       family words; later on a richer vocabulary).
    3. Verify the codebook entries are fixed points (`f(cat) ≈ cat`)
       and that basin boundaries are sensible.
    4. Run the Monte Carlo sweep: from v0 = king - man + woman,
       perturb with noise, iterate f to convergence, record which
       attractor the trajectory lands in.
    5. Compare across substrates (this plus the per-program embedding
       override item below = a real cross-substrate attractor-quality
       benchmark).
  **User direction 2026-04-22: do this before the Anthropic grant
  app (~2026-04-29) but not today.** It's a real priority for the
  application window; it's just not a same-day item. Sequence after
  the smaller pre-app items (embedding override, learned-matrix
  bind, rotation-binding capacity characterization). The WIP
  placeholder script at `examples/_king_queen_attractor_search.py`
  stays to capture the name; do not confuse it for the real thing.

## [Pre-Anthropic-grant-app] Per-program embedding-space override

User direction 2026-04-22: *"programmes should be able to have their
native embedding space [declared] at the beginning of them as an
override thing so that we could have a bunch of different test
programmes that show it in different vector spaces."*

Current state: `NumpyCodegen.__init__` already accepts `llm_model=...`
as a kwarg, but there's no source-level way to set it — the codegen is
invoked with default args by `examples/_smoke_test.py`.

Minimum scope:
- [ ] Define the directive syntax. Leaning toward a magic first-line
  comment (`// @embedding: mxbai-embed-large`) that the test harness
  parses pre-compile; zero parser/compiler changes.
- [ ] Update `examples/_smoke_test.py` and the analogy harness to
  respect the directive.
- [ ] Write 3+ test programs that sweep the embedding models available
  locally (`nomic-embed-text`, `mxbai-embed-large`, `all-minilm`)
  over the same analogy task. Compare winners + margins.

Longer scope (later):
- [ ] Source-level declaration (not a comment) — a `embedding_space`
  pragma the parser recognizes. Decide after seeing how the magic-
  comment version is used in practice.

## [Pre-Anthropic-grant-app] Learned-matrix binding

Deferred from the 2026-04-22 rotation-binding pass (user priority —
grant app first). When picked up:

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

## [Pre-Anthropic-grant-app] Extended state vector + canonical truth axis

The 2026-04-21 design (semantic + synthetic subspaces) is committed at
the spec level (`planning/sutra-spec/binding.md`, `vision.md`). The
2026-04-22 rotation-binding implementation DELIBERATELY did not
implement the extended-state-vector split — rotation acts in the same
768-d subspace as sign-flip did, for prototyping speed. Upgrading to
the dedicated-synthetic-subspace design is follow-on work:

- [ ] Decide synthetic-subspace budget (fixed at language level,
  per-program, or dynamic).
- [ ] Extend the embedding pipeline so embedded vectors are
  `[semantic | zeros]` in the new block-diagonal layout.
- [ ] Move rotation binding to use 2D Givens planes in the synthetic
  subspace with compiler-allocated plane indices per variable/slot.
- [ ] Reserve one synthetic axis as the canonical truth axis.
  Implement `is_true` / defuzzification as projection onto it.
- [ ] Re-run smoke tests on the new layout; document any changes in
  capacity / cross-talk characteristics against the 2026-04-22
  prototype baseline.

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

## [This year] Tooling

- [ ] Diagnose why `!editor.bat` fails (likely JAVA_HOME or Gradle daemon
  issue). Get `sdk/intellij-sutra` `runIde` task working, verify `.su`
  syntax highlighting and completion in the sandbox IDE.

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

## [This year] Exploratory / parked

Long-form research sketches live in `planning/exploratory/` — not
commitments, just parking spots. Currently parked:
- `softmax-conditionals.md` — fuzzy conditional branching as softmax over
  named cases vs classic if/elif chains.
- `karpathy-llm-wiki.md` — Karpathy's "LLM wiki" concept; interest is in
  the context-management angle.

## [This year] Speculative

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
