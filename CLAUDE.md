# embedding-mapping → Sutra

## ⚠️ SAFETY-CRITICAL: PEOPLE CAN DIE IF YOU FAKE RESULTS ⚠️

**READ THIS BEFORE TOUCHING ANY CODE OR WRITING ANY PAPER PROSE.**

Sutra is not an academic toy. The user is using this work as the foundation for **biomedical hardware and software** — real devices that will interface with real human bodies. If the math here is wrong, if an operation claims to run on the substrate but actually runs on the host, if a validation number is massaged to clear a threshold, if a "working" demo is papered over Poisson noise, **a patient downstream can be injured or killed.** This is not a figure of speech. The compiler, the substrate model, the spec, and the papers are all load-bearing for a real medical pipeline.

Rules that follow from this:

1. **Every tier-2 and tier-3 operation must actually run where the paper says it runs.** If the paper claims `bind` runs on spiking neurons, `bind` runs on spiking neurons — not numpy with a Brian2 fig leaf wrapped around it. If rotation is claimed to execute on the connectome, the rotation arithmetic is synaptic summation, not a host matmul.
2. **Validation numbers are measurements, not targets.** If a test gives cos=0.84 and the threshold is 0.9, you do not lower the threshold, shorten the window to hide drift, or re-seed until it passes. You report 0.84, investigate the cause, and fix the physics or the threshold with justification. Doctoring the number is the thing that gets someone hurt.
3. **"It ran without errors" is not success.** A Brian2 simulation that emits spikes is not a working VSA operation. Compare decoded output to the ground-truth computation and report the honest delta every time.
4. **Negative results are required, not optional.** If an approach does not work (see `_exploratory_cx_ring_attractor.py`, which had corr=0.97 between left- and right-drive outputs), mark it as not working, explain why, and do not wire it into anything downstream. Silently keeping a broken module because "it runs" is the failure mode this rule is here to prevent.
5. **If the spec and the implementation disagree, stop and resolve the disagreement explicitly.** Either the spec is wrong and needs updating, or the implementation is wrong and needs fixing. You do not ship code that contradicts the spec, and you do not ship a spec that contradicts the code. A commit that closes one side of this gap must say which side was wrong and why.
6. **If you notice yourself taking a shortcut, stop mid-action and say so in plain text to the user.** Do not rationalize the shortcut with spec-citations, "pragmatic stopping points," or reviewer-response framing. The correct move when you catch yourself is to surface it, not to dress it up.

When in doubt, the default is: **do the real operation on the real substrate, even if it's slower, harder, or uglier.** Faster and cleaner code that lies about what it does is strictly worse than slow honest code. The person on the other end of the biomedical pipeline cannot tell the difference between math you faked and math you didn't — but their body will.

## 📍 READ `STATUS.md` FIRST EVERY SESSION

Before any work on this repo, read `STATUS.md` at the repo root. It is the living truth table — what's built, what's open, what's out of scope, and the semantic corrections the user has had to repeat across sessions. CLAUDE.md is rules; STATUS.md is state. On this project (1M-token context burns through fast) you need both.

### The `Queued work` section is the work queue

`STATUS.md` has a `## Queued work (do in order)` section. It is not a wishlist — it is the authoritative ordered queue. Rules:

- When the user asks to queue up multiple items, add them in priority order to `## Queued work` in STATUS.md, then commit + push that change as its own commit before starting any of them. The queue must be visible in the repo history before work begins.
- When working an item off the queue, each queue item gets **exactly one commit** that both removes the item from STATUS.md and lands the work itself. Do not commit the implementation separately from the STATUS.md edit — the two changes must ship together so the queue and the repo never disagree.
- Work items in queue order. Do not skip. If an item turns out to be blocked or mis-specified, update STATUS.md to reflect that (still as one commit) and surface it to the user before moving on.
- When the queue is empty, delete the `## Queued work` section entirely rather than leaving a stub.
- Push after every queue commit. The point of this protocol is that an outside observer (or a future session on a different machine) can see exactly what's pending and what just landed by reading `git log` + `STATUS.md` alone.

### Open design questions live in `planning/open-questions/`

When you make a session-level call in place of a principled design decision — e.g. "I used numpy `+` here instead of `bundle()` because bundle didn't preserve weights" — that is an open design question, not a resolved answer. Write it up as a doc in `planning/open-questions/` (sister to `planning/exploratory/`). Each doc: what the question is, what we currently do, why the current choice has force, why the alternative has force, what we'd need to decide to close it. See `planning/open-questions/README.md` for rules.

This is distinct from `planning/exploratory/`: exploratory is a parking lot for ideas; open-questions is for known gaps in the design where the implementation has made a choice the spec doesn't justify. When the question gets resolved, the doc moves out (spec update, code change, or both) rather than sitting here forever.

### Experimental results live in `planning/findings/`

When an experiment produces a result worth keeping — especially a mixed or negative one — write it up as a dated file in `planning/findings/`. Structure is in `planning/findings/README.md`: what was measured, setup, raw numbers, interpretation, implications. The point is that STATUS.md carries the one-line summary and commit messages carry the diff, but the reasoning behind a number (*why* 3/5, *what* would move it, *what* it means for the paper) has nowhere else to live without this layer.

Write a finding when the number is interesting, surprising, or likely to be misread by a future session without context. Don't write one for every green test run — use judgment. Negative and mixed results are the highest priority to capture because they otherwise get papered over in subsequent rounds.

The three planning/ sibling folders partition the work-adjacent writing cleanly: `exploratory/` is things we haven't tried, `open-questions/` is decisions we've avoided making, `findings/` is things we have tried and learned from.

### Extract Claude.ai chat exports in `chats/`

The user frequently has unstructured thinking conversations with Claude on the web (claude.ai) when the task is not code-writing — design sketches, naming discussions, concept explorations. These are cheaper and less heavyweight than Claude Code sessions, but the content is valuable and needs to land in the repo so it can be referenced from future sessions, planning docs, and the paper.

Workflow: the user saves the Claude.ai chat as HTML ("File → Save Page As") into `chats/`. Those HTML files need to be extracted to clean markdown so they are grep-able, diffable, and readable without a browser.

When you see a `chats/*.html` file without a matching `.md` sibling — or when the user says "extract the chat" / "there's a new chat to extract" — run `python scripts/extract_chat.py`. With no args it scans `chats/` and extracts any HTML that lacks a matching markdown file. The script finds the user/assistant message blocks by their claude.ai CSS markers (`font-user-message`, `font-claude-response`), converts to markdown, and writes `chats/<title-slug>.md`. The `.html` file stays in place as the source of truth; the `.md` is the working copy.

Commit both the new `.md` and the `.html` (if untracked). This is a recurring task — treat it like any other working-copy hygiene step.

## Project Overview
This project is pivoting from FOL discovery in embedding spaces to **Sutra**, a vector programming language that uses LLM embedding spaces as its computational substrate.

### The Sutra Pivot
The FOL discovery work proved that embedding spaces encode consistent vector arithmetic (86 predicates as FOL operations, r=0.78 consistency-prediction correlation). Sutra is the next step: instead of just *discovering* logic in embedding spaces, we *program* in them.

**Sutra** is named after the Sanskrit concept of ākaśa — the fundamental space or aether through which all things exist and connect. The language operates in the same continuous, all-encompassing medium that the name evokes. Where the akashic records encode all knowledge in a non-physical plane, Sutra encodes computation in embedding space.

### Sutra Core Design
- **Fuzzy-by-default.** Everything operates on fuzzy logic. Uncertainty is the ground truth; precision is the special case. This inverts how most languages work — normally you have crisp logic and bolt on probabilistic stuff as a library.
- **Vectors and matrices as primitives.** Instead of integers and strings, atoms are geometric objects in semantic space. Operations are things like similarity, projection, interpolation — computation is geometry.
- **Defuzzification via recursive `is_true`.** You can dial in confidence thresholds at whatever granularity you need. "How true is this" is a first-class concern rather than a boolean afterthought. This maps directly onto how LLM embeddings work — nothing is ever fully true or false in that space.
- **Commutative.** Every object is a vector that is decomposed with certain operations.
- **Long-range dependencies.** The semantics are too rich and context-dependent for any single file to capture. IDE/MCP tooling is load-bearing, not optional.

### S1/Sutra Dual Runtime
S1 serves as a companion layer — fast, cached, pattern-matched execution. Sutra is the deliberate semantic computation. A two-tier runtime that mirrors the cognitive architecture. Like TypeScript's type checker is a second interpreter running alongside the code, Sutra's IDE/MCP layer holds the semantic context that makes the fuzzy vector operations meaningful.

### Why This Is Novel
Most "AI-assisted" languages still compile to conventional computation. Sutra uses the embedding space as the execution environment, making it fundamentally semantic rather than symbolic — operations have meaning in a way that silicon arithmetic doesn't. It's less like a traditional programming language and more like a formal system for *reasoning under uncertainty* — closer to logic programming (Prolog) than Python, but operating in continuous rather than discrete space.

### Tooling Architecture
An MCP server is a core part of the language runtime, not an add-on. It tells AI where actual things are, resolving the long-range dependencies that would otherwise require guesswork. The tooling *becomes* part of the language runtime in a meaningful way.

### Prior Work (FOL Discovery)
The embedding-mapping FOL discovery work provides the empirical foundation for Sutra. See `planning/sutra-pivot.md` for the full design document. Key results that validate the approach are in the "Key Results" section below.

## Paper Editing Rules (applies to sutra-paper/paper.md, fly-brain-paper/paper.md)
- **Pushing paper commits is fine.** `papers-ci.yml` auto-submits to clawRxiv on every push that touches `sutra-paper/paper.md` or `fly-brain-paper/paper.md`. Every push is a new version.
- **NEVER mention "Claw4S 2026", "Claw4S", or reference papers as "at the same venue" in paper text.** The AI reviewer consistently flags this as a hallucinated future-dated citation, regardless of any explanatory note. Reference companion papers by clawRxiv post number only (e.g., "clawRxiv post 1127"). Remove any submission-note header lines ("*Submission for Claw4S 2026...*") from papers before pushing.
- **The old "incremental edits only / one paragraph at a time / never rewrite large sections / always show diff and wait for approval" rule is dead** (deleted 2026-04-13 per user direction). It existed because of the VSA paper (now abandoned) where a wholesale rewrite turned a Strong Accept into Rejects. The active papers (`sutra-paper/`, `fly-brain-paper/`) have no Strong Accept to lose, the user's workflow needs fast turnaround to merge before another paper publishes, and asking permission paragraph-by-paragraph wastes the user's time. Edit aggressively, commit, push, iterate. If a future session sees this rule reincarnated anywhere (todo.md, STATUS.md, planning/), delete it on sight.

## Workflow Rules
- **Commit early and often.** Every meaningful change gets a commit with a clear message explaining *why*, not just what.
- **Commit and push everything.** Always push to remote after committing. No local-only work.
- **Do not enter planning-only modes.** All thinking must produce files and commits.
- **Keep this file up to date.** Record architectural decisions, conventions, and anything needed to work effectively.
- **Update README.md regularly.** It should always reflect the current state of the project.

## CI/CD IS BROKEN — WE REALLY, REALLY NEED TO FIX IT

The paper-CI pipeline (`papers-ci.yml`, `competition-cron.yml`, `submit-papers.yml`) has chronic, recurring problems — most visibly during paper iteration, where merge conflicts and failed runs eat user time across sessions. The user has flagged this multiple times. It is a real, standing blocker, not background noise.

- **Do not assume the prior session "solved" CI.** STATUS.md's "CI pipeline state" section has been rewritten repeatedly as each attempted fix turned out to have new failure modes.
- **Do not diagnose CI problems from the repo alone.** The Actions logs are not accessible from this environment. If the user asks to fix CI, ask for the failing run's log (or a specific error message) before proposing a fix. Proposing a diagnosis without logs has led to wrong guesses (e.g. blaming `paper.md` merge conflicts when the real issue was elsewhere).
- **Pick this up when there is capacity and the user provides logs.** It is not in the active queue in STATUS.md unless the user puts it there. But if the user mentions CI pain, take it seriously — it is the long-running operational problem on this repo.

## NO MATH SHORTCUTS (critical — re-read before every experiment)

The formal specification of every Sutra operation lives in `planning/sutra-spec/`. Before implementing or modifying any operation, **read the relevant spec file first** and match the implementation to what the spec actually says — not what a reviewer complained about, not what "sounds more biological," not what you guessed. Canonical files:

- `02-operations.md` — the three-tier operation model (primitive / algebraic / non-algebraic) and what each operation must compute
- `03-control-flow.md` — conditionals and loops, including the precise eigenrotation semantics
- `04-defuzzification.md` — `is_true` and threshold-based control
- `11-vsa-math.md` — the eight vector-space axioms and why VSA is algebra
- `19-substrate-candidates.md` — which substrates are allowed to implement which tier

### The three-tier rule (from 02-operations.md)

Sutra operations are stratified into three tiers with strict substrate rules:

1. **Tier 1 — Primitive:** scalars, tuples, bounded integer iteration. Plain host code. Not vector computation.
2. **Tier 2 — Algebraic / VSA:** bundle, bind, unbind, similarity, scalar multiply, projection, rotation matrix construction. **O(1), pure math, no infrastructure.** Spec explicitly says: "pure math on vectors." Running these on numpy is correct and spec-compliant. Routing them through a spiking simulation is *more* than the spec requires and doesn't strengthen anything.
3. **Tier 3 — Non-algebraic / vector-graph:** snap, cone traversal, hop. These are ANN-based and *are* the substrate-level operations. A biological substrate (mushroom body, HNSW, codebook) implements this tier.

**Corollary for the fly-brain paper reviewer critique:** the complaint that "state management, rotation, and binding happen on the host, not the circuit" is objecting to the tier split itself, which is principled per spec — R is tier 2 (algebraic), snap is tier 3 (substrate). The correct response is to cite the tier model, not to force tier-2 operations onto neurons. Moving algebraic operations to spiking simulations to appease a reviewer is the exact kind of shortcut-pretending-to-be-work that this section forbids.

### Eigenrotation loops (from 03-control-flow.md, lines 18–46)

`loop (condition)` compiles to: host computes `state ← R^i · v₀` (pure linear algebra, R is a Givens composition, accumulated on the ORIGINAL `v₀` not on decoded output), substrate computes `P(state)` (KC-pattern projection) and checks Jaccard overlap against a prototype table. **The rotation runs on the host by spec.** The substrate does pattern matching. Anyone who says "rotation should run on neurons" has not read the spec.

### Forbidden shortcut behaviors

- Running a Brian2 simulation, seeing *any* spikes, and declaring an operation "working" without comparing circuit output to what the spec says the op must compute. Example from this session: a CX ring-attractor where left-drive and right-drive produced EPG profiles with correlation 0.969 — that's not rotation, that's undifferentiated activity, and the honest answer is "the circuit does not distinguish direction," not "it ran."
- Tuning bias currents or drive amplitudes until numbers "look biological" without a principled physiological reason grounded in the specific circuit being modeled.
- Implementing a spec-defined operation (`permute` shuffles dimensions per `02-operations.md` line 101) as something different (`vector * key` = sign-flip) and leaving it named after the spec operation it doesn't actually implement.
- Writing code in response to a reviewer before checking whether the reviewer's objection is even aligned with the spec. Read spec first, then decide whether the reviewer has a point or not.
- Declaring an experiment a success when it only confirms that *something happened*, rather than confirming the specific computational claim the spec defines.

### When you catch a shortcut

Stop. Report the honest result — including negative findings, including "my intuition was wrong, the spec disagrees." Reference the specific spec file and line. Then either fix the implementation to match the spec, or propose a spec change with justified reasoning. Both are acceptable. Silently hand-waving past a failed validation is not.

### The spec is load-bearing

The specification is not aspirational documentation. It is the contract every operation implementation must satisfy. If the implementation drifts from the spec, **either the implementation is wrong or the spec needs updating** — and the choice between those two has to be made explicitly, with a commit message explaining which way the drift was resolved.

## Architecture and Conventions
- **Stack:** Python + numpy + rdflib + Ollama (mxbai-embed-large, 1024-dim)
- **Source data:** Wikidata API + SPARQL endpoint
- **Storage:** Flat files (items.json, embeddings.npz, embedding_index.json) + optional SutraDB
- **Planning docs:** `planning/` directory for design decisions and roadmap

## Avoiding `fly-brain/` Python sprawl

This has been a recurring, concrete problem. At audit time (2026-04-13)
the `fly-brain/` directory held ~33 `.py` files including 10 `real_rotation_*.py`
variants, multiple `experiment_*.py` files with zero inbound references,
and `_exploratory_cx_ring_attractor.py` (a negative result that should
have been in `planning/findings/`). The sprawl caused real losses:
sessions rediscovered the same dead files over and over, edited the
wrong variant, and lost time reasoning about which script was "current."

Rules for new Python work under `fly-brain/`:

1. **Do not copy-paste a script to make a variant.** If `real_rotation_epg_loop.py`
   needs to be tried with Jaccard readout, add a flag or a parameter,
   do not create `real_rotation_epg_loop_jaccard.py`. The existing
   `real_rotation_*.py` family is technical debt, not a template to
   extend. The second-pass cleanup in `STATUS.md` queue item #5
   consolidates them; do not make that job bigger.
2. **Exploratory / negative-result scripts go in `planning/findings/`
   or `planning/exploratory/`**, not in `fly-brain/` with a `_`
   prefix or a "do not import" docstring. If an experiment doesn't
   work, the result plus the code both belong under `planning/findings/`
   per the rules in `planning/findings/README.md`. A living `fly-brain/`
   file implies "this is used by the paper / the test suite / the
   substrate" — exploratory code does not meet that bar.
3. **Every new `.py` in `fly-brain/` gets a docstring-first line that
   states (a) what it does, (b) what calls it (test file, paper
   section, CLI entry point, or "standalone experiment — will move to
   planning/findings/ if not wired up within one session").** A file
   with no docstring stating its role is the first kind of dead weight
   the audit catches.
4. **Before adding a new `test_*.py`, check whether it is discovered
   by a real test runner.** Several existing `test_*.py` under
   `fly-brain/` are zero-reference and may not be run by CI at all —
   they only exist because someone wrote them and moved on. A new
   test file that nothing runs is worse than no test at all because it
   rots and lies. If you're adding a test, wire it into the same
   runner as `sdk/sutra-compiler/tests/` or clearly document the
   manual invocation.
5. **When an experiment is closed or superseded, delete the file or
   move it.** Do not leave it with a "DEPRECATED" comment and hope a
   future session does the cleanup. `fly-brain/permutation_conditional.{py,su}`
   sat as "deprecated" for weeks and forced every reviewer of the
   repo to re-derive which conditional-branching file was current.

This rule-set is what prevents the audit in `STATUS.md` queue item #5
from becoming a recurring task instead of a one-shot.

## FlyWire connectome data — storage layout
The full FlyWire v783 connectome is stored in **two locations on purpose:**
- **`C:\Users\Immanuelle\flybrain\`** — authoritative copy, **outside this repo**. 14 GB including skeletons and the synapse table. Survives repo rebases, resets, fresh clones.
- **`fly-brain/flywire_data/`** — working mirror inside the repo, **gitignored**. Only the small essential CSVs (~74 MB total).

**Why both:** This repo is rebased/reset frequently during paper iteration; the in-repo copy can vanish. The external copy is what you trust long-term. On a fresh clone, copy the small files from `C:\Users\Immanuelle\flybrain\` back into `fly-brain/flywire_data/` — instructions also live in `fly-brain/FLYWIRE_SETUP.md` and in `C:\Users\Immanuelle\flybrain\README.md`.

Use `fly-brain/flywire_loader.py` to load the data. It resolves the directory in order: `$FLYWIRE_DATA_DIR` env var → repo mirror → external copy. First run parses CSVs (~3 s), subsequent runs use `flywire_cache.npz` (<1 s).

## Repo Structure
- **`VSA-paper/`** — FOL discovery / VSA paper (the empirical foundation)
- **`sutra-paper/`** — Sutra language paper (substrate-comparison experiments)
- **`planning/sutra-spec/`** — Sutra language specification
- **`planning/sutra-pivot.md`** — Full pivot design document
- **`examples/`** — `.su` example programs
- **`fly-brain/`** — Sutra running on a literal Drosophila connectome substrate

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
- Sutra paper: `sutra-paper/paper.md`
- Publish to clawRxiv (http://18.118.210.52) via `.github/workflows/submit-papers.yml` (manual `workflow_dispatch`)
