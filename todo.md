# Sutra — consolidated TODO

This file is the long-term agenda. `STATUS.md` at the repo root is the
active session queue — if the two disagree, STATUS.md wins for what is
being worked on *now*, and this file wins for what needs doing
*eventually*. Do not re-split this into per-subdirectory todo files.

## 🗂 Priority levels

- **Immediate** — do right now / this session. Usually mirrored in `STATUS.md`.
- **Pre-Claw4S (deadline 2026-04-20)** — must land before the science-conference
  submission closes.
- **Pre-Y-Combinator pitch** — must land before the YC pitch (no fixed date).
- **This year** — should land in 2026, not necessarily tied to a deadline.

When adding an item, pick a level. When closing one, delete the line.

---

## [Pre-Claw4S] Paper scope catch-up after the 2026-04-14 pivot

The embedding paper (`sutra-paper/paper.md`, retitled *"Sign-Flip Binding and
Vector Symbolic Operations on Frozen LLM Embedding Spaces"*) and the fly-brain
paper (`fly-brain-paper/paper.md`) have both been trimmed to their actually
defensible contribution. Open work from that pivot:

- [ ] Re-read both papers end-to-end once the dust settles and flag any
  remaining passage that implies the paper is about "the Sutra language" or
  that the fly-brain is a general-purpose computational substrate. The pivot
  (STATUS.md §"Pivot (2026-04-14)") is explicit: the language paper is on hold
  pending the connectionist-computer-of-our-own-design substrate work; the
  embedding paper is the empirical-operations paper; the fly-brain paper is
  the compile-to-connectome paper. Neither current paper is the language
  paper.
- [ ] Decide whether the `sutra-paper/` directory name is load-bearing. It
  is now misleading (the paper is the embedding paper). Renaming forces
  CI matrix + `.post_id` fixup — not urgent while the title is correct in
  the matrix and the H1.

## [Pre-Claw4S] Build the connectionist-computer-of-our-own-design substrate

Per the 2026-04-14 pivot, the new primary substrate is a spiking population
(LIF or similar) whose wiring is a *parameter* matching what each Sutra
operation needs — not the fly connectome (which is now a downstream
compatibility target). Open work:

- [ ] Sketch what each of Sutra's primitives (`bundle`, `bind`, `unbind`,
  `similarity`, `snap`, `select`, `gate`) needs from an ideal substrate.
  The fly-brain negatives (EPG no-recurrence, bind role-discrimination)
  are data for this — they tell us what wiring would have made the op
  work. File the sketch under `planning/open-questions/ideal-substrate-per-op.md`.
- [ ] Stand up a minimal spiking simulator where connectivity is
  parameter-controlled. Decide: Brian2, a sparse PyTorch LIF, or lift the
  Shiu runtime pattern to arbitrary W.
- [ ] Run each Sutra op on that substrate with a principled wiring; report
  results as findings under `planning/findings/`.

## [Pre-Claw4S] sutrac hygiene

- [ ] Run `python -m sutra_compiler` across every `.su` file in the repo
  and fix whatever it reports. The compiler is stable enough to be ground
  truth; lint sweep over `examples/`, `fly-brain/`, and any stragglers.

## [Pre-Claw4S] Competition landscape

- [ ] Re-run `scripts/fetch_all_papers.py` / `fetch_reviews.py` /
  `fetch_top_papers.py` and update `planning/competition-analysis-latest.md`
  with the current landscape. Decide whether to keep daily snapshots or
  collapse to `latest.md`.

## [Pre-Claw4S] CI/CD pipeline reliability

Standing operational problem — `papers-ci.yml` / `competition-cron.yml` /
`submit-papers.yml` have chronic failure modes during fast paper iteration.
Do **not** diagnose from the repo alone; Actions logs are not available to
the Claude environment. When picking this up, ask the user for a specific
failing run's log or URL before proposing a fix. Prior guesses (e.g. "it's
paper.md merge conflicts") have been wrong.

Known-plausible fixes when logs confirm them:
- papers-ci HTTP 409 "already revised" on close-together pushes — have
  `scripts/paper_submit_and_fetch.py` query clawRxiv for the latest version
  by slug, update `.post_id`, and retry.
- competition-cron push rejected for workflows permission — mirror papers-ci's
  revert to direct-master-push instead of the branch+PR flow.

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
