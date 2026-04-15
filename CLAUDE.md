# embedding-mapping → Sutra

## ⚠️ SAFETY-CRITICAL: PEOPLE CAN DIE IF YOU FAKE RESULTS ⚠️

**READ THIS BEFORE TOUCHING ANY CODE OR WRITING ANY PAPER PROSE.**

Sutra is not an academic toy. The user is using this work as the foundation for **biomedical hardware and software** — real devices that will interface with real human bodies. If the math here is wrong, if an operation claims to run on the substrate but actually runs on the host, if a validation number is massaged to clear a threshold, if a "working" demo is papered over Poisson noise, **a patient downstream can be injured or killed.** This is not a figure of speech. The compiler, the substrate model, the spec, and the papers are all load-bearing for a real medical pipeline.

Rules that follow from this:

1. **Every tier-2 and tier-3 operation must actually run where the paper says it runs.** If the paper claims `bind` runs on spiking neurons, `bind` runs on spiking neurons — not numpy with a Brian2 fig leaf wrapped around it. If rotation is claimed to execute on the connectome, the rotation arithmetic is synaptic summation, not a host matmul.
2. **Validation numbers are measurements, not targets.** If a test gives cos=0.84 and the threshold is 0.9, you do not lower the threshold, shorten the window to hide drift, or re-seed until it passes. You report 0.84, investigate the cause, and fix the physics or the threshold with justification. Doctoring the number is the thing that gets someone hurt.
3. **"It ran without errors" is not success.** A Brian2 simulation that emits spikes is not a working VSA operation. Compare decoded output to the ground-truth computation and report the honest delta every time.
4. **Negative results are required, not optional.** If an approach does not work (see `planning/findings/2026-04-13-cx-ring-attractor-no-direction-discrimination.md`, which had corr=0.97 between left- and right-drive outputs), mark it as not working, explain why, and do not wire it into anything downstream. Silently keeping a broken module because "it runs" is the failure mode this rule is here to prevent.
5. **If the spec and the implementation disagree, stop and resolve the disagreement explicitly.** Either the spec is wrong and needs updating, or the implementation is wrong and needs fixing. You do not ship code that contradicts the spec, and you do not ship a spec that contradicts the code. A commit that closes one side of this gap must say which side was wrong and why.
6. **If you notice yourself taking a shortcut, stop mid-action and say so in plain text to the user.** Do not rationalize the shortcut with spec-citations, "pragmatic stopping points," or reviewer-response framing. The correct move when you catch yourself is to surface it, not to dress it up.

When in doubt, the default is: **do the real operation on the real substrate, even if it's slower, harder, or uglier.** Faster and cleaner code that lies about what it does is strictly worse than slow honest code. The person on the other end of the biomedical pipeline cannot tell the difference between math you faked and math you didn't — but their body will.

## The real substrate is the Shiu whole-brain LIF model

From 2026-04-13 forward, the canonical substrate for this project is the **Shiu et al. 2024 whole-brain LIF model** (138,639 AlphaLIF neurons, 15,091,983 synapses, real FlyWire v783 W as the sparse connectivity matrix, Shiu's calibrated parameters). It lives at `C:/Users/Immanuelle/shiu-fly-brain` and runs on PyTorch CUDA via `run_pytorch.py`.

Every Sutra operation gets tried on this substrate, persistently, from scratch when needed. The small hemibrain MB (140 PN → 1,882 KC) was useful scaffolding and backs §Result 1 of the paper, but the Shiu model is the real thing — it reproduces ground-truth fly spike activity at 91% accuracy, and if an operation doesn't work there, it doesn't work on a real connectome.

Rules:

1. **Default target for any new operation test is the Shiu model**, not the hemibrain MB. If a test isn't runnable on Shiu (e.g. it requires MB-specific circuitry), say so explicitly and justify the smaller substrate.
2. **Be persistent.** A first attempt that returns zero recurrence or a collapsed state is a data point, not a verdict. Try different protocols (drive rate, window length, drive targets, readout — cosine vs snap vs Jaccard vs bump-centroid). Record each as a finding; the negative results compound into a map of what the substrate does and doesn't implement.
3. **Start from scratch when needed.** If an existing `fly-brain/*.py` script encodes assumptions that turned out wrong (e.g. polar-decomposition `Q` as "rotation on the connectome"), don't patch around them — write a new script that exercises the operation directly against Shiu with no inherited premise.
4. **Every operation gets its turn on Shiu.** Bundle, bind, unbind, similarity, snap, permute, rotate, cone, hop, scalar multiplication, projection. Some already have Shiu results (bundle cos=0.97, snap 15/16, EPG rotation negative). The rest get scripts. The result — positive, negative, or marginal — is the honest paper contribution.

This is a policy shift. Prior sessions treated the hemibrain MB as the primary surface because it was fast; from now on the MB is a secondary surface and Shiu is primary.

## 📍 READ `STATUS.md` AND `claw4s-scope.md` FIRST EVERY SESSION

Before any work on this repo, read both:

- **`STATUS.md`** — the **work queue**. Not a state snapshot, not a truth table, not a changelog. It is a list of open items to do. **When you finish an item, you DELETE it from STATUS.md.** Completed work lives in `git log` and `planning/findings/`, never as an accumulating section in STATUS.md. If STATUS.md is bloated with "done" items or long-winded narrative, that is a bug — prune it.
- **`claw4s-scope.md`** — the **strategic direction**. What we're actually building toward, what's in scope, what's out. STATUS.md items should serve this scope; if one doesn't, question it.

CLAUDE.md is rules. `claw4s-scope.md` is direction. STATUS.md is the live queue against that direction. On this project (1M-token context burns through fast) you need all three but they each do a different job — keep them lean and do not let STATUS.md drift back into being a dumping ground for session state.

### STATUS.md queue discipline

- Items are added in priority order. When the user queues multiple items, commit + push the STATUS.md change as its own commit before starting any of them.
- **When working an item off the queue, each item gets exactly one commit that both removes it from STATUS.md and lands the work.** The queue entry disappears in the same commit as the implementation. No "done" markers, no strikethrough, no "✅ completed" lines — it's gone from the file.
- Work items in queue order. If one is blocked or mis-specified, update STATUS.md to reflect that (still one commit) and surface it to the user before moving on.
- When the queue is empty, STATUS.md can be nearly empty (a pointer to `claw4s-scope.md` plus any pinned semantic corrections is fine). Do not leave stub sections.
- Push after every queue commit. An outside observer should be able to read `git log` + current `STATUS.md` and know exactly what's pending and what just landed.
- Strategic direction, long-term agenda, "what the project is about" — none of that goes in STATUS.md. It goes in `claw4s-scope.md` or (for long-term, post-submission) `todo.md`.

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
- **NEVER mention the publication venue inside the paper text — not "Claw4S 2026", not "Claw4S", not "clawRxiv", not "at the same venue", not clawRxiv post numbers.** The AI reviewer consistently flags any venue/post-number reference as a hallucinated citation, regardless of context or explanatory note. Earlier guidance to "reference companion papers by clawRxiv post number" was wrong — that change made the next review call clawRxiv itself hallucinated. Cite companion or prior work by author + descriptive title only ("Leonhart, *Latent space cartography…*"); the venue is metadata of the submission, not content of the paper. Remove any submission-note header lines from papers before pushing.
- **NEVER propose mxbai-embed-large as a substrate for new work in either paper.** The model has a documented attention-sink defect on diacritics (see the latent-space-cartography work) and is treated by this project as a known-broken baseline, cited only to flag the pathology. New design intent (e.g. fitting `t_true` to a centroid) targets working substrates, not mxbai.
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

- `02-operations.md` — what each Sutra operation computes
- `03-control-flow.md` — conditionals and loops, including eigenrotation
- `04-defuzzification.md` — `is_true` and threshold-based control
- `11-vsa-math.md` — the eight vector-space axioms and why VSA is algebra
- `19-substrate-candidates.md` — which substrates can implement which operations

### Every operation runs on the substrate. No exceptions. No tier framing.

The primitive / algebraic / non-algebraic (tier-1 / tier-2 / tier-3) stratification is dead, and it is dead on purpose. It is a framing the user has explicitly rejected because it was used across many prior sessions to justify running operations (especially rotation) on numpy at the host. Do not reintroduce it under any name — not "tier 2," not "algebraic tier," not "the O(1) pure-math operations," not "the on-host side of the split." If you catch yourself reaching for a two-class hierarchy to decide where an op runs, stop: that is the attractor.

The rule is flat. Every Sutra operation — bundle, bind, unbind, similarity, scalar multiplication, projection, rotation, snap, cone, hop — executes on the substrate at runtime. Scaffolding (scalars, tuples, bounded iteration) is not a Sutra operation; it is counting and grouping around the vector work. A backend that cannot execute an operation on its substrate must either implement it or refuse to compile programs that use it.

### Numpy: compile and monitor only, never runtime

Numpy has exactly two legitimate roles:

1. **Compilation.** Translating a Sutra program into substrate state — e.g. polar-decomposing a FlyWire weight matrix to get Q, building a codebook, laying out motif blocks, fitting thresholds, handing Q to Brian2 as `syn.w`. Happens before the run.
2. **Monitoring.** Decoding and viewing substrate output — reading Brian2 membrane voltage, cosine against a reference prototype for reporting, plotting, verification. Happens around the run.

Numpy is **not** allowed as part of the runtime computation itself. `state = Q @ state` inside an iteration loop that is supposed to be eigenrotation on the connectome is the forbidden thing. A numpy result returned as the output of a Sutra operation, with a Brian2 simulation wrapped cosmetically around it, is a lie about what executed. Where a current implementation does this (e.g. `real_rotation_140D_jaccard.py` iterates rotation on numpy), that is a gap to close — and results produced that way must be reported as host-iterated, not as "rotation on the connectome."

### Eigenrotation loops (from 03-control-flow.md)

`loop (condition)` iterates `state ← R · state` on the substrate, projects the state through the substrate's cleanup to a KC pattern, and terminates when the pattern matches a compiled prototype by Jaccard overlap. The rotation runs on the substrate; the match runs on the substrate. Earlier spec language that said rotation could "accumulate on the host as `R^i v₀`" was a rationalization that got baked in when the tier framing was active. It is gone. If an implementation still computes `R^i v₀` on numpy, say so in the result as a limitation.

### Forbidden shortcut behaviors

- Running a Brian2 simulation, seeing *any* spikes, and declaring an operation "working" without comparing circuit output to what the spec says the op must compute. Example: a CX ring-attractor where left-drive and right-drive produced EPG profiles with correlation 0.969 — that's not rotation, that's undifferentiated activity; the result to report is "the circuit does not distinguish direction," not "it ran."
- Tuning bias currents or drive amplitudes until numbers "look biological" without a principled physiological reason grounded in the specific circuit being modeled.
- Implementing a spec-defined operation (`permute` shuffles dimensions) as something different (`vector * key` = sign-flip) and leaving it named after the spec operation it doesn't actually implement.
- Writing code in response to a reviewer before checking whether the reviewer's objection aligns with the spec. Read the spec first, then decide whether the reviewer has a point.
- Declaring an experiment a success when it only confirms that *something happened*, rather than confirming the specific computational claim the spec defines.
- Writing "algebraic," "pure math," "no infrastructure," "O(1) on the host," or "runs on host by spec" about any Sutra operation. Every one of those phrases has been used to justify runtime host-math and is now rejected framing.

### When you catch a shortcut

Stop. Report what actually executed, including negative findings. Reference the specific spec file. Then either fix the implementation to match the spec, or propose a spec change with justified reasoning. Both are acceptable. Silently hand-waving past a failed validation is not.

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
The 2026-04-13 cleanup pass dropped `fly-brain/` from 33 to 15 `.py`
files without losing any paper-backing result — the evidence that
most of those files were duplicates accumulated over time, not
distinct contributions.

**The underlying pattern:** sessions reach for "create a new file"
when they should reach for "edit the existing file." A new variant
feels safe (doesn't break the old one), but the graveyard of stale
variants is exactly what the sprawl-tax runs on. Edit in place;
use git to preserve the old state if needed. The `real_rotation_*.py`
family and the `experiment_*.py` family are both artifacts of this
failure mode — each was a copy-paste branch that should have been a
flag or a parameter on the original.

Rules for new Python work under `fly-brain/` (and anywhere else in
the repo — this generalizes):

1. **Do not copy-paste a script to make a variant.** If `real_rotation_epg_loop.py`
   needs to be tried with Jaccard readout, add a flag or a parameter,
   do not create `real_rotation_epg_loop_jaccard.py`. The existing
   `real_rotation_*.py` family is technical debt, not a template to
   extend — consult `fly-brain/ROTATION-MANIFEST.md` before adding a
   new rotation file, and if you do add one, update the manifest in
   the same commit.
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

This rule-set is what prevents the 2026-04-13 cleanup from becoming
a recurring task instead of a one-shot.

## FlyWire connectome data — storage layout
The full FlyWire v783 connectome is stored in **two locations on purpose:**
- **`C:\Users\Immanuelle\flybrain\`** — authoritative copy, **outside this repo**. 14 GB including skeletons and the synapse table. Survives repo rebases, resets, fresh clones.
- **`fly-brain/flywire_data/`** — working mirror inside the repo, **gitignored**. Only the small essential CSVs (~74 MB total).

**Why both:** This repo is rebased/reset frequently during paper iteration; the in-repo copy can vanish. The external copy is what you trust long-term. On a fresh clone, copy the small files from `C:\Users\Immanuelle\flybrain\` back into `fly-brain/flywire_data/` — instructions also live in `fly-brain/FLYWIRE_SETUP.md` and in `C:\Users\Immanuelle\flybrain\README.md`.

Use `fly-brain/flywire_loader.py` to load the data. It resolves the directory in order: `$FLYWIRE_DATA_DIR` env var → repo mirror → external copy. First run parses CSVs (~3 s), subsequent runs use `flywire_cache.npz` (<1 s).

## Repo Structure
- **`sutra-paper/`** — Sutra language paper (substrate-comparison experiments)
- **`fly-brain-paper/`** — Fly-brain paper (programming the hemibrain connectome)
- **`planning/sutra-spec/`** — Sutra language specification
- **`planning/sutra-pivot.md`** — Full pivot design document
- **`examples/`** — `.su` example programs
- **`fly-brain/`** — Sutra running on a literal Drosophila connectome substrate
- **`sdk/`** — compiler, IntelliJ plugin, VS Code extension

## Prior work (published elsewhere, not in this repo)
The empirical foundation of the Sutra pivot — relational displacement analysis of frozen embedding spaces, discovering 86 predicates as consistent vector operations, r = 0.861 consistency-prediction correlation, the mxbai `[UNK]` tokenizer defect — lives in [`EmmaLeonhart/latent-space-cartography`](https://github.com/EmmaLeonhart/latent-space-cartography) and as clawRxiv post 1127 (Strong Accept). Cite as (Leonhart, 2026) when referenced from Sutra or fly-brain papers. Do not re-derive or re-implement those results here.

## Submission Target
Claw4S Conference 2026 (deadline **April 20, 2026** — extended from the original April 5 per `planning/competition-analysis-2026-04-09.md`)
- Sutra paper: `sutra-paper/paper.md`
- Fly-brain paper: `fly-brain-paper/paper.md`
- Publish to clawRxiv (http://18.118.210.52) via `.github/workflows/papers-ci.yml` (auto on push) or `submit-papers.yml` (manual)
