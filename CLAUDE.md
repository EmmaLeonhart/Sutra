# embedding-mapping → Sutra

## ⚠️ SAFETY-CRITICAL: PEOPLE CAN DIE IF YOU FAKE RESULTS ⚠️

**READ THIS BEFORE TOUCHING ANY CODE.**

Sutra is not an academic toy. The user is using this work as the foundation for **biomedical hardware and software** — real devices that will interface with real human bodies. If the math here is wrong, if an operation claims to run on the substrate but actually runs on the host, if a validation number is massaged to clear a threshold, if a "working" demo is papered over Poisson noise, **a patient downstream can be injured or killed.** This is not a figure of speech. The compiler, the substrate model, and the spec are load-bearing for a real medical pipeline.

Rules that follow from this:

1. **Every Sutra operation must actually run where the spec says it runs.** If the spec claims `bind` runs on spiking neurons, `bind` runs on spiking neurons — not numpy with a Brian2 fig leaf wrapped around it. If rotation is claimed to execute on the connectome, the rotation arithmetic is synaptic summation, not a host matmul. (The old "tier-2 / tier-3" framing this rule used to invoke is explicitly rejected — see the "No tier framing" section below.)
2. **Validation numbers are measurements, not targets.** If a test gives cos=0.84 and the threshold is 0.9, you do not lower the threshold, shorten the window to hide drift, or re-seed until it passes. You report 0.84, investigate the cause, and fix the physics or the threshold with justification. Doctoring the number is the thing that gets someone hurt.
3. **"It ran without errors" is not success.** A Brian2 simulation that emits spikes is not a working VSA operation. Compare decoded output to the ground-truth computation and report the honest delta every time.
4. **Negative results are required, not optional.** If an approach does not work, mark it as not working, explain why, and do not wire it into anything downstream. Silently keeping a broken module because "it runs" is the failure mode this rule is here to prevent.
5. **If the spec and the implementation disagree, stop and resolve the disagreement explicitly.** Either the spec is wrong and needs updating, or the implementation is wrong and needs fixing. You do not ship code that contradicts the spec, and you do not ship a spec that contradicts the code. A commit that closes one side of this gap must say which side was wrong and why.
6. **If you notice yourself taking a shortcut, stop mid-action and say so in plain text to the user.** Do not rationalize the shortcut with spec-citations or "pragmatic stopping points." The correct move when you catch yourself is to surface it, not to dress it up.

When in doubt, the default is: **do the real operation on the real substrate, even if it's slower, harder, or uglier.** Faster and cleaner code that lies about what it does is strictly worse than slow honest code. The person on the other end of the biomedical pipeline cannot tell the difference between math you faked and math you didn't — but their body will.

## The real substrate is the Shiu whole-brain LIF model

From 2026-04-13 forward, the canonical substrate for this project is the **Shiu et al. 2024 whole-brain LIF model** (138,639 AlphaLIF neurons, 15,091,983 synapses, real FlyWire v783 W as the sparse connectivity matrix, Shiu's calibrated parameters). It lives at `C:/Users/Immanuelle/shiu-fly-brain` and runs on PyTorch CUDA via `run_pytorch.py`.

Every Sutra operation gets tried on this substrate, persistently, from scratch when needed. The small hemibrain MB (140 PN → 1,882 KC) was useful scaffolding, but the Shiu model is the real thing — it reproduces ground-truth fly spike activity at 91% accuracy, and if an operation doesn't work there, it doesn't work on a real connectome.

Rules:

1. **Default target for any new operation test is the Shiu model**, not the hemibrain MB. If a test isn't runnable on Shiu (e.g. it requires MB-specific circuitry), say so explicitly and justify the smaller substrate.
2. **Be persistent.** A first attempt that returns zero recurrence or a collapsed state is a data point, not a verdict. Try different protocols (drive rate, window length, drive targets, readout — cosine vs snap vs Jaccard vs bump-centroid). Record each as a finding; the negative results compound into a map of what the substrate does and doesn't implement.
3. **Start from scratch when needed.** If an existing `fly-brain/*.py` script encodes assumptions that turned out wrong (e.g. polar-decomposition `Q` as "rotation on the connectome"), don't patch around them — write a new script that exercises the operation directly against Shiu with no inherited premise.
4. **Every operation gets its turn on Shiu.** Bundle, bind, unbind, similarity, snap, permute, rotate, cone, hop, scalar multiplication, projection. Some already have Shiu results (bundle cos=0.97, snap 15/16, EPG rotation negative). The rest get scripts. The result — positive, negative, or marginal — is the honest research contribution.

### Open design questions live in `planning/open-questions/`

When you make a session-level call in place of a principled design decision — e.g. "I used numpy `+` here instead of `bundle()` because bundle didn't preserve weights" — that is an open design question, not a resolved answer. Write it up as a doc in `planning/open-questions/` (sister to `planning/exploratory/`). Each doc: what the question is, what we currently do, why the current choice has force, why the alternative has force, what we'd need to decide to close it. See `planning/open-questions/README.md` for rules.

This is distinct from `planning/exploratory/`: exploratory is a parking lot for ideas; open-questions is for known gaps in the design where the implementation has made a choice the spec doesn't justify. When the question gets resolved, the doc moves out (spec update, code change, or both) rather than sitting here forever.

### Experimental results live in `planning/findings/`

When an experiment produces a result worth keeping — especially a mixed or negative one — write it up as a dated file in `planning/findings/`: what was measured, setup, raw numbers, interpretation, implications. Commit messages carry the diff, but the reasoning behind a number (*why* 3/5, *what* would move it, *what* it means for future sessions) has nowhere else to live without this layer.

Write a finding when the number is interesting, surprising, or likely to be misread by a future session without context. Don't write one for every green test run — use judgment. Negative and mixed results are the highest priority to capture because they otherwise get papered over in subsequent rounds.

The three planning/ sibling folders partition the work-adjacent writing cleanly: `exploratory/` is things we haven't tried, `open-questions/` is decisions we've avoided making, `findings/` is things we have tried and learned from.

### Extract Claude.ai chat exports in `chats/`

The user frequently has unstructured thinking conversations with Claude on the web (claude.ai) when the task is not code-writing — design sketches, naming discussions, concept explorations. These are cheaper and less heavyweight than Claude Code sessions, but the content is valuable and needs to land in the repo so it can be referenced from future sessions and planning docs.

Workflow: the user saves the Claude.ai chat as HTML ("File → Save Page As") into `chats/`. Those HTML files need to be extracted to clean markdown so they are grep-able, diffable, and readable without a browser.

When you see a `chats/*.html` file without a matching `.md` sibling — or when the user says "extract the chat" / "there's a new chat to extract" — run `python scripts/extract_chat.py`. With no args it scans `chats/` and extracts any HTML that lacks a matching markdown file. The script finds the user/assistant message blocks by their claude.ai CSS markers (`font-user-message`, `font-claude-response`), converts to markdown, and writes `chats/<title-slug>.md`. The `.html` file stays in place as the source of truth; the `.md` is the working copy.

Commit both the new `.md` and the `.html` (if untracked). This is a recurring task — treat it like any other working-copy hygiene step.

## Project Overview

**Sutra is a real, purely functional programming language with a working compiler and a pure-numpy matrix runtime.** `.su` source parses, validates, compiles to self-contained Python, and executes; three demonstration programs (hello world, fuzzy branching, role-filler record) run end-to-end with 23/23 outputs correct. The demo path has zero fly-brain imports. PyTorch/GPU is the next refactor target, not a dependency of anything today.

**Fly-brain is not the language's substrate.** The `fly-brain/` directory contains an attempted compile-to-connectome backend (Brian2 spiking simulation of the *Drosophila* mushroom body, plus scripts against the Shiu whole-brain model). That attempt produced interesting negative findings — the real FlyWire weight matrix does not function as a rotation operator, EPG ring-attractor circuits did not discriminate direction on real connectivity, etc. — documented in `planning/findings/`. It is a separate experimental target, not the primary runtime. Prior sessions repeatedly told the user "the fly-brain stuff works" when it did not; this framing is a corrective against that failure mode. If in doubt: the demo is numpy; fly-brain is segregated.

### The Sutra Pivot
Prior relational-displacement work on frozen embedding spaces — published externally in the `latent-space-cartography` repo — is the empirical foundation. **Do not quote specific numerical claims about that work from this file; verify against the source itself.** Earlier versions of this CLAUDE.md contained two different r-values for the same result and two incompatible descriptions of the mxbai pathology, which Claude propagated into prose as if they were verified. They were not. Treat any specific number ("86 predicates," any r-value) as unverified until you read the source in `EmmaLeonhart/latent-space-cartography`.

Sutra is the next step beyond that prior work: instead of just *discovering* relational structure in embedding spaces, *program* in them. The language, grammar, compiler, and runtime exist; `.su` source parses, validates, compiles to Python, runs on a pure-numpy backend. Hooking the numpy backend to a frozen LLM (currently `nomic-embed-text`, 768-d, mean-centered) is ongoing.

**Sutra** is named after the Sanskrit *sūtra* — thread/rule/aphorism, the word used for Pāṇini's foundational Sanskrit grammar.

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

### Prior work: relational displacements in frozen embedding spaces
The prior relational-displacement work (published in the external `latent-space-cartography` repo — see the "Prior work" section at the bottom of this file) is the empirical foundation for Sutra. See `planning/sutra-pivot.md` for the full design document. Do not quote specific numerical claims about that work from memory; verify against the source itself.

## Workflow Rules
- **Commit early and often.** Every meaningful change gets a commit with a clear message explaining *why*, not just what.
- **Commit and push everything.** Always push to remote after committing. No local-only work.
- **Do not enter planning-only modes.** All thinking must produce files and commits.
- **Keep this file up to date.** Record architectural decisions, conventions, and anything needed to work effectively.
- **Update README.md regularly.** It should always reflect the current state of the project.

## STATUS.md and the task tool

`STATUS.md` at the repo root is the **persistent work queue across
sessions**. It is not a state snapshot and it is not a log of finished
work. Items live in it until they are done; then they are removed.
Completed work is preserved in `git log` and in dated findings docs
under `planning/findings/`.

The task tool (`TaskCreate` / `TaskUpdate` / `TaskList`) is the
session-level counterpart. **The intended workflow is that the task
tool runs off of `STATUS.md`:**

1. **At the start of a session when you're about to do work from the
   queue**, read `STATUS.md` and call `TaskCreate` for each queued
   item (or each sub-item if a queue item naturally breaks down).
   Task subjects should be short and action-oriented; descriptions
   should reference the STATUS.md entry so nothing is lost.
2. **Work through the tasks**: `TaskUpdate` to `in_progress` when you
   start, `completed` when you finish. This is the same task tool you
   already use for multi-step coding work.
3. **When a task is completed**, also **edit `STATUS.md` to remove
   the corresponding queue item in the same commit that closes the
   work**. Not at session end; as each item finishes. The delete is
   the explicit signal that an item is done.
4. **If you realize a queue item needs to split into smaller pieces**
   before it fits in one task, split it in the task tool first, and
   reflect the split back into STATUS.md so the two views stay in
   sync.

This is the reason STATUS.md is a queue, not a state snapshot:
**STATUS.md and the task tool are two views of the same list**, one
persistent across sessions and one session-local. Drift between them
defeats the purpose.

Longer-horizon commitments that aren't "next active session" work
belong in `todo.md` instead. STATUS.md is for what Claude should pick
up on the next working pass; `todo.md` is for what Claude should pick
up eventually. When an item moves from "eventually" to "now", it
migrates from `todo.md` to `STATUS.md`; when it completes, it
disappears from both.

Do not use STATUS.md as a log of completed work or as a state
snapshot. If you need to record what was done, that's a commit
message, a findings doc, or a git tag — not STATUS.md.

## NO MATH SHORTCUTS (critical — re-read before every experiment)

The specification of every Sutra operation lives in `planning/sutra-spec/`. Before implementing or modifying any operation, **read the relevant spec file first** and match the implementation to what the spec actually says — not what "sounds more biological," not what you guessed. The old numbered spec (`02-operations.md` etc.) was deprecated on 2026-04-15 for containing Claude-invented content that didn't match the user's vision. The current un-numbered spec is under active rewrite; see `planning/sutra-spec/README.md`. Current canonical files:

- `vision.md` — how Sutra inverts VSA's random-role premise
- `operations.md` — what each Sutra operation computes
- `binding.md` — semantic vs non-semantic binding (both matrix-based)
- `control-flow.md` — conditionals and loops
- `equality-and-defuzzification.md` — `is_true`, the undersymbolic realm
- `types.md`, `program-structure.md`, `concurrency.md`
- `open-questions.md` — index of unresolved spec decisions

### Every operation runs on the substrate. No exceptions. No tier framing.

The primitive / algebraic / non-algebraic (tier-1 / tier-2 / tier-3) stratification is dead, and it is dead on purpose. It is a framing the user has explicitly rejected because it was used across many prior sessions to justify running operations (especially rotation) on numpy at the host. Do not reintroduce it under any name — not "tier 2," not "algebraic tier," not "the O(1) pure-math operations," not "the on-host side of the split." If you catch yourself reaching for a two-class hierarchy to decide where an op runs, stop: that is the attractor.

The rule is flat. Every Sutra operation — bundle, bind, unbind, similarity, scalar multiplication, projection, rotation, snap, cone, hop — executes on the substrate at runtime. Scaffolding (scalars, tuples, bounded iteration) is not a Sutra operation; it is counting and grouping around the vector work. A backend that cannot execute an operation on its substrate must either implement it or refuse to compile programs that use it.

### Numpy: compile and monitor only, never runtime

Numpy has exactly two legitimate roles:

1. **Compilation.** Translating a Sutra program into substrate state — e.g. polar-decomposing a FlyWire weight matrix to get Q, building a codebook, laying out motif blocks, fitting thresholds, handing Q to Brian2 as `syn.w`. Happens before the run.
2. **Monitoring.** Decoding and viewing substrate output — reading Brian2 membrane voltage, cosine against a reference prototype for reporting, plotting, verification. Happens around the run.

Numpy is **not** allowed as part of the runtime computation itself. `state = Q @ state` inside an iteration loop that is supposed to be eigenrotation on the connectome is the forbidden thing. A numpy result returned as the output of a Sutra operation, with a Brian2 simulation wrapped cosmetically around it, is a lie about what executed. Where a current implementation does this (e.g. `real_rotation_140D_jaccard.py` iterates rotation on numpy), that is a gap to close — and results produced that way must be reported as host-iterated, not as "rotation on the connectome."

### Eigenrotation loops (from control-flow.md)

`loop (condition)` iterates `state ← R · state` on the substrate, projects the state through the substrate's cleanup to a KC pattern, and terminates when the pattern matches a compiled prototype by Jaccard overlap. The rotation runs on the substrate; the match runs on the substrate. Earlier spec language that said rotation could "accumulate on the host as `R^i v₀`" was a rationalization that got baked in when the tier framing was active. It is gone. If an implementation still computes `R^i v₀` on numpy, say so in the result as a limitation.

### Forbidden shortcut behaviors

- Running a Brian2 simulation, seeing *any* spikes, and declaring an operation "working" without comparing circuit output to what the spec says the op must compute. Example: a CX ring-attractor where left-drive and right-drive produced EPG profiles with correlation 0.969 — that's not rotation, that's undifferentiated activity; the result to report is "the circuit does not distinguish direction," not "it ran."
- Tuning bias currents or drive amplitudes until numbers "look biological" without a principled physiological reason grounded in the specific circuit being modeled.
- Implementing a spec-defined operation (`permute` shuffles dimensions) as something different (`vector * key` = sign-flip) and leaving it named after the spec operation it doesn't actually implement.
- Declaring an experiment a success when it only confirms that *something happened*, rather than confirming the specific computational claim the spec defines.
- Writing "algebraic," "pure math," "no infrastructure," "O(1) on the host," or "runs on host by spec" about any Sutra operation. Every one of those phrases has been used to justify runtime host-math and is now rejected framing.

### When you catch a shortcut

Stop. Report what actually executed, including negative findings. Reference the specific spec file. Then either fix the implementation to match the spec, or propose a spec change with justified reasoning. Both are acceptable. Silently hand-waving past a failed validation is not.

### The spec is load-bearing

The specification is not aspirational documentation. It is the contract every operation implementation must satisfy. If the implementation drifts from the spec, **either the implementation is wrong or the spec needs updating** — and the choice between those two has to be made explicitly, with a commit message explaining which way the drift was resolved.

## Architecture and Conventions
- **Stack:** Python + numpy + Ollama. The demo numpy backend currently uses `nomic-embed-text` (768-d, mean-centered); see `sdk/sutra-compiler/sutra_compiler/codegen_numpy.py` for the authoritative embedding config.
- **Source data:** Wikidata API + SPARQL endpoint (for prior cartography work); Sutra itself does not require Wikidata.
- **Planning docs:** `planning/` directory for design decisions and roadmap.

## Global efficiency, not local — every operation stays a tensor operation

**Sutra is not aiming for local efficiency.** Doing `5 * 3` by multiplying two 800-dimensional vectors is locally wasteful. That is fine. That is the point.

What the language aims at is **global efficiency** — per-thread, per-program. Because every value in a Sutra program has the same essential shape (a vector in the extended-state layout) and every operation is a tensor operation on that shape, the compiler can treat the whole program as a single tensor computation. That lets it:

- Fuse chains of operations into cached matrices at compile time.
- Batch operations across threads and programs onto the same GPU kernel launch.
- Treat the whole runtime as a dataflow graph of tensor ops — no branches, no type dispatch at the leaves, no host/device round-trips.

Breaking uniformity to optimize a local operation — e.g. extracting scalars from a vector to do a "cheap" scalar multiply — **gives you local efficiency at the expense of global efficiency.** The compile-time fusion pass can't see past a scalar extraction. One operation that escapes the tensor-ops-only invariant breaks the whole chain.

**Rules that follow:**

1. **Every Sutra operation is a tensor operation.** Matmul, element-wise multiply, element-wise addition / subtraction, and nonlinear element-wise functions (`tanh`, `exp`, `sqrt`, `abs`, `sign`) are the allowed primitives. Nonlinear is fine. What's not fine is leaving tensor land.

2. **No scalar extraction inside an operation.** If an operation reads `v[AXIS_REAL]` to pull out a float, does scalar arithmetic on that float, and packs it back into a vector, it has broken the invariant. The fact that the vector is "effectively 2-dimensional" or "only has content on one axis" does not license this — the operation still has to be expressible as matmul + element-wise so the simplifier can fold it. This was a specific trap: complex multiplication was implemented with scalar extraction ("the data is 2D so scalar form is fine") — the correct implementation is three cached matrices and two tensor multiplies, and that fixed form is what ships.

3. **No Python control flow inside an operation.** `if`, `for`, `while` on scalar predicates break uniformity the same way scalar extraction does. Zero-norm guards, tie checks, and loop-unrolls all have tensor-native substitutes: `x / (||x|| + eps)` instead of `if norm == 0`; `tanh(k · x)` instead of `sign(x)`; iterate-in-the-emitted-graph instead of iterate-at-compile-time. The only acceptable Python `for` is one that is semantically part of the operation's definition (e.g. defuzzify's `iterate N times` where N is fixed at compile time and the loop body is itself a tensor op).

4. **Accessor methods (`real()`, `imag()`, `truth()`, `component()`) are not compute path.** They're monitoring / debugging — extracting a scalar for host-side display. Those are fine because they don't sit inside another operation's definition.

5. **The rule covers nonlinear functions, not just linear.** `tanh`, `exp`, `sqrt` are acceptable tensor ops. The constraint is "tensor operation," not "linear transformation." The AND / OR polynomials use element-wise multiply (nonlinear) and that's correct; equality uses sqrt (nonlinear) and that's correct. What's forbidden is not nonlinearity — it's dropping out of tensor land to scalars or Python branches.

If a review finds a runtime method that reads a component, does scalar arithmetic, and writes the result back, the fix is to rewrite the operation in tensor form, not to justify the extraction with "but the data is conceptually scalar."

## Avoiding `fly-brain/` Python sprawl

This has been a recurring, concrete problem. At audit time (2026-04-13)
the `fly-brain/` directory held ~33 `.py` files including 10 `real_rotation_*.py`
variants, multiple `experiment_*.py` files with zero inbound references,
and `_exploratory_cx_ring_attractor.py` (a negative result that should
have been in `planning/findings/`). The sprawl caused real losses:
sessions rediscovered the same dead files over and over, edited the
wrong variant, and lost time reasoning about which script was "current."
The 2026-04-13 cleanup pass dropped `fly-brain/` from 33 to 15 `.py`
files without losing any experimentally-backed result — the evidence
that most of those files were duplicates accumulated over time, not
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
   file implies "this is used by the test suite / the substrate" —
   exploratory code does not meet that bar.
3. **Every new `.py` in `fly-brain/` gets a docstring-first line that
   states (a) what it does, (b) what calls it (test file, CLI entry
   point, or "standalone experiment — will move to planning/findings/
   if not wired up within one session").** A file with no docstring
   stating its role is the first kind of dead weight the audit catches.
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
   future session does the cleanup.

This rule-set is what prevents the 2026-04-13 cleanup from becoming
a recurring task instead of a one-shot.

## FlyWire connectome data — storage layout
The full FlyWire v783 connectome is stored in **two locations on purpose:**
- **`C:\Users\Immanuelle\flybrain\`** — authoritative copy, **outside this repo**. 14 GB including skeletons and the synapse table. Survives repo rebases, resets, fresh clones.
- **`fly-brain/flywire_data/`** — working mirror inside the repo, **gitignored**. Only the small essential CSVs (~74 MB total).

**Why both:** The in-repo copy can vanish during resets. The external copy is what you trust long-term. On a fresh clone, copy the small files from `C:\Users\Immanuelle\flybrain\` back into `fly-brain/flywire_data/` — instructions also live in `fly-brain/FLYWIRE_SETUP.md` and in `C:\Users\Immanuelle\flybrain\README.md`.

Use `fly-brain/flywire_loader.py` to load the data. It resolves the directory in order: `$FLYWIRE_DATA_DIR` env var → repo mirror → external copy. First run parses CSVs (~3 s), subsequent runs use `flywire_cache.npz` (<1 s).

## Repo Structure
- **`sdk/`** — compiler, IntelliJ plugin, VS Code extension
- **`examples/`** — `.su` example programs
- **`planning/sutra-spec/`** — Sutra language specification
- **`planning/sutra-pivot.md`** — Full pivot design document
- **`planning/findings/`** — dated experimental findings (negative and positive)
- **`fly-brain/`** — experimental substrate code (Brian2 MB + Shiu whole-brain)
- **`sutraDB/`** — SutraDB subtree (triple store)
- **`docs/`** — MkDocs site for the language

## Prior work (published elsewhere, not in this repo)
The empirical foundation of the Sutra pivot is the relational-displacement analysis of frozen embedding spaces, published in [`EmmaLeonhart/latent-space-cartography`](https://github.com/EmmaLeonhart/latent-space-cartography). **Verify any specific claim about that work against the source itself.** Previous revisions of this section contained contradictory numbers and contradictory pathology descriptions; they have been stripped rather than reconciled-by-guessing. If you need specific numbers, either read the cartography source directly (the sibling repo is not present locally — ask the user or pull it) or state the claim as "prior work showed displacement vectors exist in frozen embedding spaces" without numbers. Do not re-derive or re-implement those results here.
