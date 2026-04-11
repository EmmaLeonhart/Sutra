# embedding-mapping → Akasha

## Project Overview
This project is pivoting from FOL discovery in embedding spaces to **Akasha**, a vector programming language that uses LLM embedding spaces as its computational substrate.

### The Akasha Pivot
The FOL discovery work proved that embedding spaces encode consistent vector arithmetic (86 predicates as FOL operations, r=0.78 consistency-prediction correlation). Akasha is the next step: instead of just *discovering* logic in embedding spaces, we *program* in them.

**Akasha** is named after the Sanskrit concept of ākaśa — the fundamental space or aether through which all things exist and connect. The language operates in the same continuous, all-encompassing medium that the name evokes. Where the akashic records encode all knowledge in a non-physical plane, Akasha encodes computation in embedding space.

### Akasha Core Design
- **Fuzzy-by-default.** Everything operates on fuzzy logic. Uncertainty is the ground truth; precision is the special case. This inverts how most languages work — normally you have crisp logic and bolt on probabilistic stuff as a library.
- **Vectors and matrices as primitives.** Instead of integers and strings, atoms are geometric objects in semantic space. Operations are things like similarity, projection, interpolation — computation is geometry.
- **Defuzzification via recursive `is_true`.** You can dial in confidence thresholds at whatever granularity you need. "How true is this" is a first-class concern rather than a boolean afterthought. This maps directly onto how LLM embeddings work — nothing is ever fully true or false in that space.
- **Commutative.** Every object is a vector that is decomposed with certain operations.
- **Long-range dependencies.** The semantics are too rich and context-dependent for any single file to capture. IDE/MCP tooling is load-bearing, not optional.

### S1/Akasha Dual Runtime
S1 serves as a companion layer — fast, cached, pattern-matched execution. Akasha is the deliberate semantic computation. A two-tier runtime that mirrors the cognitive architecture. Like TypeScript's type checker is a second interpreter running alongside the code, Akasha's IDE/MCP layer holds the semantic context that makes the fuzzy vector operations meaningful.

### Why This Is Novel
Most "AI-assisted" languages still compile to conventional computation. Akasha uses the embedding space as the execution environment, making it fundamentally semantic rather than symbolic — operations have meaning in a way that silicon arithmetic doesn't. It's less like a traditional programming language and more like a formal system for *reasoning under uncertainty* — closer to logic programming (Prolog) than Python, but operating in continuous rather than discrete space.

### Tooling Architecture
An MCP server is a core part of the language runtime, not an add-on. It tells AI where actual things are, resolving the long-range dependencies that would otherwise require guesswork. The tooling *becomes* part of the language runtime in a meaningful way.

### Prior Work (FOL Discovery)
The embedding-mapping FOL discovery work provides the empirical foundation for Akasha. See `planning/akasha-pivot.md` for the full design document. Key results that validate the approach are in the "Key Results" section below.

## CRITICAL: Paper Editing Rules (applies to VSA-paper/paper.md and akasha-paper/paper.md)
- **NEVER rewrite large sections of the paper at once.** One sentence, one paragraph, one table at a time.
- **ALWAYS show the diff to the user and wait for approval before committing.**
- **Pushing paper commits is fine.** `.github/workflows/submit-papers.yml` is `workflow_dispatch`-only, so pushing paper changes does NOT trigger a clawRxiv submission. Submission is a separate manual step, either via `gh workflow run submit-papers.yml` or the Actions tab in GitHub.
- **Submission to clawRxiv is its own decision.** Only trigger `submit-papers.yml` after explicit user approval. Every trigger is a new version on clawRxiv, so batch paragraph-level iterations between submissions rather than submitting after every edit.
- **Why the incremental-edits rule:** A wholesale rewrite turned a Strong Accept into Rejects. With big changes you cannot isolate what the reviewer disliked. Incremental changes only.

## Workflow Rules
- **Commit early and often.** Every meaningful change gets a commit with a clear message explaining *why*, not just what.
- **Commit and push everything.** Always push to remote after committing. No local-only work.
- **Do not enter planning-only modes.** All thinking must produce files and commits.
- **Keep this file up to date.** Record architectural decisions, conventions, and anything needed to work effectively.
- **Update README.md regularly.** It should always reflect the current state of the project.

## Architecture and Conventions
- **Stack:** Python + numpy + rdflib + Ollama (mxbai-embed-large, 1024-dim)
- **Source data:** Wikidata API + SPARQL endpoint
- **Storage:** Flat files (items.json, embeddings.npz, embedding_index.json) + optional SutraDB
- **Planning docs:** `planning/` directory for design decisions and roadmap

## Repo Structure
- **`VSA-paper/`** — FOL discovery / VSA paper (the empirical foundation)
- **`akasha-paper/`** — Akasha language paper (substrate-comparison experiments)
- **`planning/akasha-spec/`** — Akasha language specification
- **`planning/akasha-pivot.md`** — Full pivot design document
- **`examples/`** — `.ak` example programs
- **`fly-brain/`** — Akasha running on a literal Drosophila connectome substrate

## Key Scripts (in `VSA-paper/scripts/`)
- `random_walk.py` — BFS through Wikidata, imports entities and computes trajectories
- `import_wikidata.py` — Core import logic (fetch, embed, store, trajectories)
- `fol_discovery.py` — **Main analysis:** discovers FOL operations, evaluates prediction, tests composition
- `analyze_collisions.py` — Collision detection, density analysis, regime classification

## Key Results (FOL Discovery, current dataset)
- 41,725 embeddings from 14,796 entities (500 fully imported via BFS from Engishiki Q1342448)
- 86 predicates discovered as FOL operations (alignment > 0.5)
- 32 strong operations (alignment > 0.7), 4 with perfect prediction (MRR = 1.0)
- r = 0.78 correlation between consistency and prediction accuracy
- Two-hop composition: 28.3% Hits@10 on 5,000 tests
- 164,084 cross-entity embedding collisions at cosine ≥ 0.95

## Development Philosophy
- **Discovery, not construction.** We don't build spaces for logic. We find logic in existing spaces.
- **Trajectories are first-class objects.** Each trajectory has its own RDF identity with subject, object, predicate, and distance metrics.
- **Adding data IS building the pipeline.** Import tooling and data grow together.
- **Reproducible.** Full analysis runs in ~30 minutes on commodity hardware with local Ollama.

## Submission Target
Claw4S Conference 2026 (deadline **April 20, 2026** — extended from the original April 5 per `planning/competition-analysis-2026-04-09.md`)
- VSA paper: `VSA-paper/paper.md` + `VSA-paper/SKILL.md`
- Akasha paper: `akasha-paper/paper.md`
- Publish to clawRxiv (http://18.118.210.52) via `.github/workflows/submit-papers.yml` (manual `workflow_dispatch`)
