# embedding-mapping → Sutra

## ⚠️ SAFETY-CRITICAL: PEOPLE CAN DIE IF YOU FAKE RESULTS ⚠️

**READ THIS BEFORE TOUCHING ANY CODE.**

Sutra is not an academic toy. The user is using this work as the foundation for **biomedical hardware and software** — real devices that will interface with real human bodies. If the math here is wrong, if an operation claims to run on the substrate but actually runs on the host, if a validation number is massaged to clear a threshold, if a "working" demo is papered over Poisson noise, **a patient downstream can be injured or killed.** This is not a figure of speech. The compiler, the substrate model, and the spec are load-bearing for a real medical pipeline.

Rules that follow from this:

1. **Every Sutra operation must actually run where the spec says it runs.** If the spec claims a primitive runs on the substrate, it runs on the substrate — not on the host with a thin wrapper around it. (The old "tier-2 / tier-3" framing this rule used to invoke is explicitly rejected — see the "No tier framing" section below.)
2. **Validation numbers are measurements, not targets.** If a test gives cos=0.84 and the threshold is 0.9, you do not lower the threshold, shorten the window to hide drift, or re-seed until it passes. You report 0.84, investigate the cause, and fix the physics or the threshold with justification. Doctoring the number is the thing that gets someone hurt.
3. **"It ran without errors" is not success.** A simulation that produces output is not a working VSA operation. Compare decoded output to the ground-truth computation and report the honest delta every time.
4. **Negative results are required, not optional.** If an approach does not work, mark it as not working, explain why, and do not wire it into anything downstream. Silently keeping a broken module because "it runs" is the failure mode this rule is here to prevent.
5. **If the spec and the implementation disagree, stop and resolve the disagreement explicitly.** Either the spec is wrong and needs updating, or the implementation is wrong and needs fixing. You do not ship code that contradicts the spec, and you do not ship a spec that contradicts the code. A commit that closes one side of this gap must say which side was wrong and why.
6. **If you notice yourself taking a shortcut, stop mid-action and say so in plain text to the user.** Do not rationalize the shortcut with spec-citations or "pragmatic stopping points." The correct move when you catch yourself is to surface it, not to dress it up.

When in doubt, the default is: **do the real operation on the real substrate, even if it's slower, harder, or uglier.** Faster and cleaner code that lies about what it does is strictly worse than slow honest code. The person on the other end of the biomedical pipeline cannot tell the difference between math you faked and math you didn't — but their body will.

## The fly-brain experimental backend was retired 2026-04-26

Earlier sessions tried to compile Sutra programs to a connectome substrate — first the hemibrain MB, then the Shiu et al. 2024 whole-brain LIF model. That work produced informative negative findings (real FlyWire weight matrices do not function as rotation operators; CX ring-attractor circuits did not discriminate direction on real connectivity; etc.) which are preserved as historical record under `planning/findings/2026-04-1*-*` and `planning/findings/2026-04-2*-*`. The whole `fly-brain/` directory plus the `codegen_flybrain.py` backend were removed on 2026-04-26 — the substrate work outpaced the language's maturity, and keeping the half-finished compile-to-connectome path was clogging the repo without paying for itself.

The substrate work may resume once the language is more mature. Until then, the canonical compile target is **PyTorch on the frozen-LLM semantic subspace** (`codegen_pytorch.py`, runs on CPU or CUDA depending on what's available at module init).

The safety-critical rules above still apply with full force — they're written in substrate-neutral terms now, but the "operations run where the spec says they run" rule is the single most load-bearing principle for the whole project, not just for the fly-brain experiment.

### Open design questions live in `planning/open-questions/`

When you make a session-level call in place of a principled design decision — e.g. "I used numpy `+` here instead of `bundle()` because bundle didn't preserve weights" — that is an open design question, not a resolved answer. Write it up as a doc in `planning/open-questions/` (sister to `planning/exploratory/`). Each doc: what the question is, what we currently do, why the current choice has force, why the alternative has force, what we'd need to decide to close it. See `planning/open-questions/README.md` for rules.

This is distinct from `planning/exploratory/`: exploratory is a parking lot for ideas; open-questions is for known gaps in the design where the implementation has made a choice the spec doesn't justify. When the question gets resolved, the doc moves out (spec update, code change, or both) rather than sitting here forever.

### Experimental results live in `planning/findings/`

When an experiment produces a result worth keeping — especially a mixed or negative one — write it up as a dated file in `planning/findings/`: what was measured, setup, raw numbers, interpretation, implications. Commit messages carry the diff, but the reasoning behind a number (*why* 3/5, *what* would move it, *what* it means for future sessions) has nowhere else to live without this layer.

Write a finding when the number is interesting, surprising, or likely to be misread by a future session without context. Don't write one for every green test run — use judgment. Negative and mixed results are the highest priority to capture because they otherwise get papered over in subsequent rounds.

The three planning/ sibling folders partition the work-adjacent writing cleanly: `exploratory/` is things we haven't tried, `open-questions/` is decisions we've avoided making, `findings/` is things we have tried and learned from.

## Project Overview

**Sutra is a real, purely functional programming language with a working compiler and a PyTorch tensor-op runtime.** `.su` source parses, validates, compiles to self-contained Python, and executes; three demonstration programs (hello world, fuzzy branching, role-filler record) run end-to-end with 23/23 outputs correct. The runtime picks CUDA at module init if available, falling back to CPU otherwise.

**Fly-brain is not the language's substrate.** The `fly-brain/` directory contains an attempted compile-to-connectome backend (Brian2 spiking simulation of the *Drosophila* mushroom body, plus scripts against the Shiu whole-brain model). That attempt produced interesting negative findings — the real FlyWire weight matrix does not function as a rotation operator, EPG ring-attractor circuits did not discriminate direction on real connectivity, etc. — documented in `planning/findings/`. It is a separate experimental target, not the primary runtime. Prior sessions repeatedly told the user "the fly-brain stuff works" when it did not; this framing is a corrective against that failure mode. If in doubt: the demo is numpy; fly-brain is segregated.

### The Sutra Pivot
Prior relational-displacement work on frozen embedding spaces — published externally in the `latent-space-cartography` repo — is the empirical foundation. **Do not quote specific numerical claims about that work from this file; verify against the source itself.** Earlier versions of this CLAUDE.md contained two different r-values for the same result and two incompatible descriptions of the mxbai pathology, which Claude propagated into prose as if they were verified. They were not. Treat any specific number ("86 predicates," any r-value) as unverified until you read the source in `EmmaLeonhart/latent-space-cartography`.

Sutra is the next step beyond that prior work: instead of just *discovering* relational structure in embedding spaces, *program* in them. The language, grammar, compiler, and runtime exist; `.su` source parses, validates, compiles to Python, runs on the PyTorch tensor-op backend hooked to a frozen LLM (currently `nomic-embed-text`, 768-d, mean-centered).

**Sutra** is named after the Sanskrit *sūtra* — thread/rule/aphorism, the word used for Pāṇini's foundational Sanskrit grammar.

### Sutra Core Design
- **Fuzzy-by-default.** Everything operates on fuzzy logic. Uncertainty is the ground truth; precision is the special case. This inverts how most languages work — normally you have crisp logic and bolt on probabilistic stuff as a library.
- **Vectors and matrices as primitives.** Instead of integers and strings, atoms are geometric objects in semantic space. Operations are things like similarity, projection, interpolation — computation is geometry.
- **Defuzzification via recursive `is_true`.** You can dial in confidence thresholds at whatever granularity you need. "How true is this" is a first-class concern rather than a boolean afterthought. This maps directly onto how LLM embeddings work — nothing is ever fully true or false in that space.
- **Commutative.** Every object is a vector that is decomposed with certain operations.
- **Long-range dependencies.** The semantics are too rich and context-dependent for any single file to capture. IDE/MCP tooling is load-bearing, not optional.
- **Runtime is committed to the math — no runtime errors by mechanism, not choice.** Once a Sutra program is compiled to operations on its substrate, there is no error-handling layer to invoke. A type mismatch, a wrong-space embedding, a malformed binding — none of these raise; they produce mathematically valid but semantically meaningless output (garbage in, garbage out). The compiler is therefore the last line of defense for correctness, and has to be paranoid in a way most compilers don't need to be. This is also why auditability is non-negotiable: the only place wrongness can be caught is at compile time, so every cast and override must be visible in the source.
- **Opinionated, not authoritarian.** Sutra is Turing-complete; you *can* write patterns the compiler considers harmful (unbounded loops, non-tail recursion, off-class operations). The compiler warns loudly and explains why — but it lets you compile. The escape hatches (legitimate cast / unsafe cast / force override; see `examples/uncertain/03-types-and-casts.su`) exist for the same reason: the language doesn't pretend the bad path doesn't exist, it just makes choosing it explicit and grep-able.

### S1/Sutra Dual Runtime
S1 serves as a companion layer — fast, cached, pattern-matched execution. Sutra is the deliberate semantic computation. A two-tier runtime that mirrors the cognitive architecture. Like TypeScript's type checker is a second interpreter running alongside the code, Sutra's IDE/MCP layer holds the semantic context that makes the fuzzy vector operations meaningful.

### Why This Is Novel
Most "AI-assisted" languages still compile to conventional computation. Sutra uses the embedding space as the execution environment, making it fundamentally semantic rather than symbolic — operations have meaning in a way that silicon arithmetic doesn't. It's less like a traditional programming language and more like a formal system for *reasoning under uncertainty* — closer to logic programming (Prolog) than Python, but operating in continuous rather than discrete space.

### Tooling Architecture
An MCP server is a core part of the language runtime, not an add-on. It tells AI where actual things are, resolving the long-range dependencies that would otherwise require guesswork. The tooling *becomes* part of the language runtime in a meaningful way.

The website (`sutralang.dev`, sourced from `docs/`) is **agent-friendly by design**: clean Markdown that renders cleanly for humans but is also directly consumable by AI agents — no animations, no JS-only UI, no information that exists only in rendered form. When agents land on the site they should be able to lift the relevant content out without parsing visual chrome. This pairs with the MCP-as-runtime stance: agents are first-class consumers of Sutra's documentation, not an afterthought.

### Prior work: relational displacements in frozen embedding spaces
The prior relational-displacement work (published in the external `latent-space-cartography` repo — see the "Prior work" section at the bottom of this file) is the empirical foundation for Sutra. See `planning/sutra-pivot.md` for the full design document. Do not quote specific numerical claims about that work from memory; verify against the source itself.

## Workflow Rules
- **Commit early and often.** Every meaningful change gets a commit with a clear message explaining *why*, not just what.
- **Commit and push everything.** Always push to remote after committing. No local-only work.
- **Do not enter planning-only modes.** All thinking must produce files and commits.
- **Keep this file up to date.** Record architectural decisions, conventions, and anything needed to work effectively.
- **Update README.md regularly.** It should always reflect the current state of the project.
- **Always use the task tool with queue.md.** Per Emma 2026-04-30, this is a general rule, not a per-session reminder: every time you're working from `queue.md`, mirror items into `TaskCreate`, mark them in_progress when you start, and completed when you finish. The task tool and queue.md are two views of the same list — do not let them drift.
- **Deprecate, don't remove.** Per Emma 2026-04-30, the language is in an early state but the convention is set: when something is superseded, mark it deprecated; don't delete it unless there's a specific reason. Reasons that warrant deletion: the deprecated thing actively misleads (e.g. the old C-style `loop(cond)` form whose body was discarded), it has no users in tests or examples, or its code is genuinely a maintenance liability. Otherwise, deprecation is a docstring/spec note, not a code change. Examples of deprecated-but-kept: `do_while NAME(...)` and `while_loop NAME(...)` (superseded by the tail-call surface 2026-04-30 but kept because they're still load-bearing in code and tests).

## queue.md and the task tool

`queue.md` at the repo root is the **persistent work queue across
sessions**. It is not a state snapshot and it is not a log of finished
work. Items live in it until they are done; then they are removed.
Completed work is preserved in `git log` and in dated findings docs
under `planning/findings/`.

The task tool (`TaskCreate` / `TaskUpdate` / `TaskList`) is the
session-level counterpart. **The intended workflow is that the task
tool runs off of `queue.md`:**

1. **At the start of a session when you're about to do work from the
   queue**, read `queue.md` and call `TaskCreate` for each queued
   item (or each sub-item if a queue item naturally breaks down).
   Task subjects should be short and action-oriented; descriptions
   should reference the queue.md entry so nothing is lost.
2. **Work through the tasks**: `TaskUpdate` to `in_progress` when you
   start, `completed` when you finish. This is the same task tool you
   already use for multi-step coding work.
3. **When a task is completed**, also **edit `queue.md` to remove
   the corresponding queue item in the same commit that closes the
   work**. Not at session end; as each item finishes. The delete is
   the explicit signal that an item is done.
4. **If you realize a queue item needs to split into smaller pieces**
   before it fits in one task, split it in the task tool first, and
   reflect the split back into queue.md so the two views stay in
   sync.

This is the reason queue.md is a queue, not a state snapshot:
**queue.md and the task tool are two views of the same list**, one
persistent across sessions and one session-local. Drift between them
defeats the purpose.

Longer-horizon commitments that aren't "next active session" work
belong in `todo.md` instead. queue.md is for what Claude should pick
up on the next working pass; `todo.md` is for what Claude should pick
up eventually. When an item moves from "eventually" to "now", it
migrates from `todo.md` to `queue.md`; when it completes, it
disappears from both.

Do not use queue.md as a log of completed work or as a state
snapshot. If you need to record what was done, that's a commit
message, a findings doc, or a git tag — not queue.md.

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

1. **Compilation.** Translating a Sutra program into substrate state — building a codebook, laying out canonical-axis blocks, fitting thresholds, precomputing fused matrices for the runtime to load. Happens before the run.
2. **Monitoring.** Decoding and viewing substrate output — cosine against a reference prototype for reporting, plotting, verification. Happens around the run.

Numpy is **not** allowed as part of the runtime computation itself. The runtime is PyTorch tensor ops; numpy on the hot path is the forbidden thing. A numpy result returned as the output of a Sutra operation, with a torch wrapper around it cosmetically, is a lie about what executed.

### Eigenrotation loops (from control-flow.md)

`loop (condition)` iterates `state ← R · state` on the substrate, projects the state through the substrate's cleanup, and terminates when the cleaned state matches a compiled prototype. The rotation runs on the substrate; the match runs on the substrate. Earlier spec language that said rotation could "accumulate on the host as `R^i v₀`" was a rationalization that got baked in when the tier framing was active. It is gone.

### Forbidden shortcut behaviors

- Declaring an operation "working" because *something* ran, without comparing the output to what the spec says the op must compute.
- Tuning thresholds or parameters until the numbers "look right" without a principled justification grounded in the specific computation being modeled.
- Implementing a spec-defined operation (`permute` shuffles dimensions) as something different (`vector * key` = sign-flip) and leaving it named after the spec operation it doesn't actually implement.
- Declaring an experiment a success when it only confirms that *something happened*, rather than confirming the specific computational claim the spec defines.
- Writing "algebraic," "pure math," "no infrastructure," "O(1) on the host," or "runs on host by spec" about any Sutra operation. Every one of those phrases has been used to justify runtime host-math and is now rejected framing.

### When you catch a shortcut

Stop. Report what actually executed, including negative findings. Reference the specific spec file. Then either fix the implementation to match the spec, or propose a spec change with justified reasoning. Both are acceptable. Silently hand-waving past a failed validation is not.

### The spec is load-bearing

The specification is not aspirational documentation. It is the contract every operation implementation must satisfy. If the implementation drifts from the spec, **either the implementation is wrong or the spec needs updating** — and the choice between those two has to be made explicitly, with a commit message explaining which way the drift was resolved.

## Architecture and Conventions
- **Stack:** Python + PyTorch + Ollama. The runtime currently uses `nomic-embed-text` (768-d, mean-centered) as the embedding substrate. **PyTorch is the canonical compile target** (`codegen_pytorch.py`, runs on CPU or CUDA). The numpy backend (`codegen.py`) is **deprecated as of 2026-04-30** and being retired (queue item 6); some tests still assert against its numpy-specific emit shape, but new code uses `PyTorchCodegen`. See either file for the embedding config — they share method names and the layout is bit-for-bit identical.
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

## Avoiding Python sprawl

A recurring, concrete failure mode: sessions reach for "create a new
file" when they should reach for "edit the existing file." A new
variant feels safe (doesn't break the old one), but the graveyard of
stale variants is what the sprawl-tax runs on. The retired `fly-brain/`
directory was the canonical example — at peak it held ~33 `.py` files
including 10 `real_rotation_*.py` copy-paste branches, multiple
zero-reference `experiment_*.py` files, and exploratory negative-
result scripts that should have lived under `planning/findings/`.

Rules to prevent this from happening again:

1. **Do not copy-paste a script to make a variant.** If a script
   needs to be tried with a different parameter, add a flag or
   parameter, don't create `script_v2.py`.
2. **Exploratory / negative-result scripts go in `planning/findings/`
   or `planning/exploratory/`**, not in the runtime tree with a `_`
   prefix or a "do not import" docstring. A file in the runtime tree
   implies "this is used" — exploratory code does not meet that bar.
3. **Every new `.py` gets a docstring-first line that states (a) what
   it does, (b) what calls it.** A file with no docstring stating its
   role is the first kind of dead weight an audit catches.
4. **Before adding a new `test_*.py`, check whether it is discovered
   by a real test runner.** A test file that nothing runs is worse
   than no test at all because it rots and lies. Wire new tests into
   the same runner as `sdk/sutra-compiler/tests/` or clearly document
   the manual invocation.
5. **When an experiment is closed or superseded, delete the file or
   move it.** Do not leave it with a "DEPRECATED" comment and hope a
   future session does the cleanup.

## Repo Structure
- **`sdk/`** — compiler, IntelliJ plugin, VS Code extension
- **`examples/`** — `.su` example programs
- **`planning/sutra-spec/`** — Sutra language specification
- **`planning/sutra-pivot.md`** — Full pivot design document
- **`planning/findings/`** — dated experimental findings (negative and positive)
- **`sutraDB/`** — SutraDB subtree (triple store)
- **`docs/`** — MkDocs site for the language

## Prior work (published elsewhere, not in this repo)
The empirical foundation of the Sutra pivot is the relational-displacement analysis of frozen embedding spaces, published in [`EmmaLeonhart/latent-space-cartography`](https://github.com/EmmaLeonhart/latent-space-cartography). **Verify any specific claim about that work against the source itself.** Previous revisions of this section contained contradictory numbers and contradictory pathology descriptions; they have been stripped rather than reconciled-by-guessing. If you need specific numbers, either read the cartography source directly (the sibling repo is not present locally — ask the user or pull it) or state the claim as "prior work showed displacement vectors exist in frozen embedding spaces" without numbers. Do not re-derive or re-implement those results here.
