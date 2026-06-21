# embedding-mapping → Sutra

## Skills

Workflow behaviors live as skills in `.claude/skills/` (auto-discovered by Claude Code):
`emergency-stop`, `cron-is-local`, `autonomous-loop`, `queue-driven-workflow`,
`writing-style`, `cleanvibe-update-check`. They are vendored into this repo and kept
current by the `cleanvibe-update-check` skill.

- **Last cleanvibe update check:** `never`
- **Updates source:** <https://cleanvibe.emmaleonhart.com/updates.md>


## Integrity and correctness (safety-critical)

Sutra is intended as a foundation for downstream hardware and software where correctness matters. If the math is wrong or an operation fakes its substrate, that error propagates silently into everything built on top — so substrate correctness is non-negotiable.

Rules:

1. **Every Sutra operation must actually run where the spec says it runs.** No host wrappers around substrate ops.
2. **Validation numbers are measurements, not targets.** If a test gives cos=0.84 and the threshold is 0.9, report 0.84, investigate, fix the physics. Do not doctor the number.
3. **"It ran without errors" is not success.** Compare decoded output to ground-truth and report the true delta.
4. **Negative results are required.** If an approach does not work, mark it, explain why, and do not wire it downstream.
5. **If spec and implementation disagree, stop and resolve it explicitly.** Either fix the implementation or update the spec. Do not ship code that contradicts the spec.
6. **If you catch yourself taking a shortcut, say so in plain text.** Surface it — don't rationalize it.

When in doubt: **do the real operation on the real substrate, even if it's slower or uglier.**

The canonical compile target is **PyTorch on the frozen-LLM semantic subspace** (`codegen_pytorch.py`, CPU or CUDA).

## Audiences

The repository has two audiences and they read different files. Do not conflate them.

- **AI agents and contributors read the repo Markdown.** That includes this `CLAUDE.md`, the `AGENTS.md` index at the repo root, `queue.md`, `todo.md`, `DEVLOG.md`, `paper/`, `paper/supplementary/`, and everything under `planning/` (`sutra-spec/`, `findings/`, `open-questions/`, `exploratory/`). This is the canonical, fullest-fidelity surface — when something is true about Sutra, it's true here first.

- **Humans read the website at `sutra.topazcomputing.com`.** Static site rendered by `scripts/build_site.py` — one HTML page per Markdown file under `docs/` (every `docs/*.md` and `docs/tutorials/*.md`, except paths containing `interactive/`), plus `/paper/` rendered from `paper/paper.md`. `/arxiv/` is a direct-URL-only utility page for grabbing the LaTeX source bundle (`noindex, nofollow`; bundle disallowed in `robots.txt`). MkDocs is gone — don't reintroduce it. **Keep every website page free of repo-internal scratchpad references** (`queue.md`, `todo.md`, `planning/...`, deep `sdk/...`).

The two surfaces are **not generated from the same source**. The website Markdown under `docs/` is hand-written for the website; the canonical Markdown elsewhere in the repo is hand-written for agents. They are allowed to drift in framing, level of detail, and which examples they pick. They must not contradict each other on facts.

If you are an AI agent landing in this repo, start with `AGENTS.md` for the file-by-file map, then come back here.

### Planning folders

- `planning/open-questions/` — design gaps where the implementation made a call the spec doesn't justify. Write a doc when you make a session-level call: what the question is, what we do now, why each side has force, what would close it.
- `planning/findings/` — dated experimental results worth keeping, especially negative/mixed ones. Write a finding when a number is interesting, surprising, or likely to be misread without context.
- `planning/exploratory/` — ideas not yet tried.

## Project Overview

**Sutra is a real, purely functional programming language** with a working compiler and PyTorch tensor-op runtime. `.su` source parses, validates, compiles to self-contained Python, and executes. The runtime picks CUDA if available, falling back to CPU.

**Sutra** is named after the Sanskrit *sūtra* — thread/rule/aphorism, the word used for Pāṇini's foundational Sanskrit grammar.

### Core Design
- **Fuzzy-by-default.** Uncertainty is ground truth; precision is the special case.
- **Vectors and matrices as primitives.** Atoms are geometric objects in semantic space; computation is geometry.
- **Defuzzification via recursive `is_true`.** "How true is this" is a first-class concern.
- **No runtime errors by mechanism.** Type mismatches produce semantically meaningless but mathematically valid output. The compiler is the last line of defense.
- **Opinionated, not authoritarian.** Harmful patterns warn loudly but still compile. Escape hatches are explicit and grep-able.

An MCP server is a core part of the language runtime. The website (`sutra.topazcomputing.com`, a static multi-page site built by `scripts/build_site.py` from every `docs/*.md` plus `paper/paper.md`) is the human-facing surface — see §"Audiences" below.

### Next venue target: NeurIPS

clawRxiv auto-submit runs on every paper edit (per the §"Paper" section below). The longer-term venue target is **NeurIPS**. Work in `todo.md` answers the question *what does this language need to be NeurIPS-ready?*

### Vibe-coded projects need legacy code removed, not kept

This project is vibe-coded — decisions get made in chat, partially implemented, sometimes superseded a few sessions later. The standard "deprecate, don't remove" default assumes old code has known users; here the opposite holds: lingering legacy paths get quietly re-wired into newer code by sessions that don't know they were supposed to be retired. **When a design shift makes the old path *incorrect* (not just less preferred), remove it.** When an old code path contradicts the current spec, ask whether it's superseded-design residue before adding a workaround.

**Carve-out: intentional compatibility code is not legacy residue.** `JavaScriptObject` + operator overrides, the TS transpiler's coercion shims, `make_char` aliasing `make_string`, the legacy `AXIS_CHAR_FLAG` name — these absorb a different ecosystem and have a current purpose. Don't sweep them under the "remove legacy" rule.

`todo.md` is longer-horizon. `queue.md` is the next active session. Items migrate `todo.md` → `queue.md` → deleted on completion.

**⭐ VERY IMPORTANT (Emma 2026-06-18) — removing items as they are done is the SAFE option.** When a queue item is finished, **delete it from `queue.md` entirely** in the same commit that ships it. Do NOT leave it behind as a crossed-off / `~~struck-through~~` / "DONE" / "SHIPPED" marker — *that* is the unsafe option. Crossed-off completed items are the bloat that buries the open work and confuses the next session (it confused this agent into dumping a low-level decision-fork on Emma instead of just working). The queue holds only not-yet-done work; "done" lives in `git log`, `DEVLOG.md`, and `planning/findings/`. Removing-as-done keeps the queue an honest ordered execution list; accumulating crossed-off items destroys that. The git history is the safety net — nothing is truly lost by deleting a completed line, so delete it.

### Barrel through specified work; verify against spec; don't add false caution

**Counterbalance to §"Integrity and correctness".** Safety-critical means *don't fake results / don't fake substrate purity* — it does NOT mean treat every queue item as needing a multi-session gated approach. When the design is already in `planning/sutra-spec/*.md`:

1. **Read the spec.** It's the authoritative design, not an aspirational sketch.
2. **Check whether the code already matches.** `Audit.md` has per-leak status; tests under `sdk/sutra-compiler/tests/` are regression guards. Running them tells you what's true *now*, not what was true when an old session wrote a queue item.
3. **Barrel through.** If the spec is clear and the implementation is close, finish it. Verification (run tests, compare decoded output to ground truth) is how you discharge the safety rules — not by avoiding the work.
4. **Only flag "deliberate, gated session" when the spec is genuinely unsettled.** If no doc exists in `planning/open-questions/`, the design is settled and the work is implementation.

Codified rule: **read the spec, verify against ground truth, barrel through; don't multiply caution by quoting prior sessions.**

### When Emma gives an algorithmic explanation, IMPLEMENT it — don't brush it off

Emma designed Sutra and knows its mechanisms far better than any agent landing in this repo. Recurring failure mode: she gives a concrete algorithm on the substrate; the agent decides it "can't work," substitutes a variant, the variant fails, and the agent reports the idea as blocked. **Almost every time Emma's original idea was correct** and the agent never built what she described.

1. **Implement Emma's algorithm first**, exactly as described, before proposing alternatives. Build, run, read the real output.
2. **"I think that can't work" is a hypothesis, not a conclusion.** Test it on the substrate — the integrity rules *require* measuring and never license unmeasured dismissal.
3. **If it seems not to compose, the gap is usually a missing primitive to expose, not a wrong idea.**
4. **Substituting your own variant for Emma's stated method is the anti-pattern** — especially on Sutra internals, where she has ground truth and you do not.

## Cross-repo workflow: Sutra ↔ Yantra

Sutra is consumed downstream by **Yantra** (the GPU-native OS built in Sutra).
**As of 2026-06-16 Yantra is being deprecated as an independent repo and vendored in-tree**
as a shallow subtree at `external/Yantra/` (squashed from `EmmaLeonhart/Yantra` main, website
stripped; gitignored-no-more — it is committed here). Its runtime references to the Sutra SDK
are rewired to this repo's `sdk/sutra-compiler` (no submodule recursion). Historically Yantra
pinned this repo as a git submodule at its own `external/Sutra`; that relationship is winding
down as the two merge. Commit messages mentioning Yantra are the workflow operating as designed.

**Division of responsibility:**
- **Yantra** — kernel orchestration (`kernel/`, axon router, storage tiers,
  capability checks, FS bridge, GUI/browser stack, Yantra paper).
- **Sutra (this repo)** — the language itself. `sdk/sutra-compiler/`, the
  language frontends `sdk/sutra-from-{ts,ocaml,rust,scala,clojure,elixir,erlang,fsharp,haskell,c}/`
  (each a fixture-tested, substrate-verified lowering pass; OCaml is the reference,
  TS is Yantra's gate, C is parked), lowering passes, axon spec, multi-process
  runtime, runtime ABI.

**GUI integration — the substrate window in the orchestrator.** Yantra `apps/` GUI entries are
host surfaces over substrate compute: a surface spawns a Sutra substrate-server and does only
window/clicks/paint. The trainable click-button rides this pattern end-to-end:
`demos/gui/button_substrate_server.py` (the Sutra-side stdin/stdout bridge over `ButtonAdam`) is
spawned by `external/Yantra/apps/gui-button/button_surface.py` (the Yantra host surface), which
forwards owner A/B preferences + visitor clicks and paints the substrate-rendered button — the
owner×CTR steering and the render run on the substrate; the host is I/O. (The Yantra-side
prose under `external/Yantra/` still describes the old `external/Sutra` submodule pin in places
— stale since the in-tree merge; cosmetic.)

**Rules that bind regardless of who's driving the change** — when a Yantra-driven
session edits Sutra source, the rules in this file still apply: integrity /
substrate-correctness (top of file); NO MATH SHORTCUTS; Workflow Rules
(commit+push immediately, plan-into-queue.md-first, no local-only work — this
repo's queue.md is the one that binds when editing this repo).

**Release vs. push:** tag a release when Yantra needs to depend on a specific
Sutra version (new extra, new public API, bug fix affecting Yantra tests);
Yantra pins to the tag. Just push to master for docs/refactor — Yantra can bump
its submodule pointer to HEAD without a release ceremony.

## Paper

Claw4S the competition is over. clawRxiv the platform stays — it's a feedback / visibility channel, not a leaderboard we're chasing. Each push to `paper/paper.md` or `paper/supplementary/SKILL.md` triggers `papers-ci.yml`, which submits to clawRxiv, polls for the AI peer review, and commits the review back under `paper/reviews/v<N>_post<ID>_review.{json,md}`. `paper/.post_id` tracks the latest post in the supersedes chain.

None of the prior Claw4S-specific rules apply (no "lock in a Strong Accept by disabling submission," no "always check the latest review before pushing," no dedup-bypass concerns). Reviews are signal, not verdicts. NeurIPS is the longer-term target — see `todo.md`.

**Second paper — formal verification (live, kept in sync with the work).** `paper/formal-verification/paper.md` (clawRxiv post 2613, paper_id 2605.02613) is a SECOND paper with its own supersedes chain (`paper/formal-verification/.post_id`) and its own workflow `.github/workflows/fv-paper-ci.yml` (auto-submits on push to `paper/formal-verification/paper.md`). It is a **live artifact: as formal-verification work lands (an obligation discharged, a checker built, a scope change), update this paper in the same session** — cite only measured numbers, mirror the §"What we are not claiming" discipline. Ground truth it must not contradict: `planning/sutra-spec/formal-verification.md`. Agenda: `todo.md` § "Formal verification". The FV paper is a separate paper from `paper/paper.md`; both are freely editable.

### `paper/paper.md` is UNFROZEN (Emma 2026-06-07) — live revision target

**The arXiv lock lifted (it was time-bounded through May 31; Emma explicitly unfroze it 2026-06-07 for a new submission).** `paper/paper.md` is now freely editable — audit it against current measured reality and revise toward the next submission. The prior arXiv-v2 snapshot is preserved in git history (uploaded 2026-05-19; correction series `0b151b79`). When revising `paper/paper.md`, keep the integrity discipline: cite only measured numbers, no honest/genuinely buzzwords, replication URL only in the Reproducibility statement, and do not overclaim substrate-purity / fused-network status as *done* where the 2026-06-07 purity overhaul is still in progress.

### Paper-code durability — keep the live paper's examples working

Every `.su`, reproduction script, and supplementary surface that `paper/paper.md` references should continue to compile, run, and produce the same observable outputs — the downloadable artifacts (paper PDF, replication package) are built from it and people may try to reproduce it. If the code legitimately drifts: prefer keeping an alias when a feature is renamed (cheap, preserves reproducibility), or update the cited description in `paper/paper.md`.

In practice: surface syntax cited by `paper/paper.md` (`map<vector, string>` codebooks, `bind`/`unbind`/`bundle`, `loop` forms, `dict<K, V>` rotation hashmaps) should stay valid. `examples/_smoke_test.py` keeps passing; if a refactor regresses it, the refactor is wrong. Reproduction scripts under `experiments/` (per `paper/supplementary/SKILL.md` / `REPRODUCE.md`) keep producing the same output (modulo documented sampling noise). `paper/supplementary/SYNTAX.md` should keep matching what the compiler emits for the cited surface — add an alias, or update the description.

If a change would break reproducibility of the cited path: (a) make it additive + keep the old form working, (b) update `paper/paper.md` to reflect the new shape, or (c) flag the conflict to the user. Don't silently break the cited path. The supplementary zip is a build artifact (not committed) regenerated by `scripts/build_supplementary_zip.py`.

### Reference PDFs are re-downloaded each session, not committed

When we need to read an arXiv (or other) paper for grounding, the PDF goes into a gitignored cache (e.g. `references/`) and is **re-downloaded every time**. Do not commit reference PDFs. The reason is IP: we never redistribute, we always fetch fresh from the original source. A `scripts/fetch_reference_pdfs.py` (or similar) handles fetching; only the script is committed. If the cache is empty, run the fetch script first.

## NO MATH SHORTCUTS

Before implementing or modifying any operation, **read the relevant spec file in `planning/sutra-spec/`** and match the implementation to what the spec actually says. Current canonical files:

- `vision.md` — how Sutra inverts VSA's random-role premise
- `operations.md` — what each Sutra operation computes
- `binding.md` — semantic vs non-semantic binding
- `control-flow.md` — conditionals and loops
- `equality-and-defuzzification.md` — `is_true`, the undersymbolic realm
- `axons.md` — structured embeddings, role-as-operator, the hardware-linked-monad framing
- `strings.md` — synthetic-axis-encoded codepoint arrays; `String` and `Character` classes
- `types.md`, `program-structure.md`, `concurrency.md`
- `open-questions.md` — index of unresolved spec decisions

### Every operation runs on the substrate. No exceptions. No tier framing.

The tier-1/tier-2/tier-3 stratification is **dead and explicitly rejected** — it was used to justify running operations on numpy at the host. Do not reintroduce it under any name. The rule is flat: every Sutra operation (bundle, bind, unbind, similarity, scalar multiplication, projection, rotation, snap, cone, hop) executes on the substrate at runtime.

### Numpy: compile and monitor only

Numpy has exactly two legitimate roles:
1. **Compilation** — building codebooks, precomputing fused matrices, fitting thresholds. Happens before the run.
2. **External analysis of non-Sutra artifacts** — e.g. inspecting a third-party model's weights (the `transformer-vm` PCA). This is host analysis of an external object, NOT introspection of a running Sutra program.

Numpy is **not** allowed on the runtime hot path. A numpy result with a torch wrapper is a lie about what executed. **Note (Emma 2026-06-07):** "decoding substrate output for monitoring/verification" is NOT a sanctioned role — see §"NO introspection" below. The language has no readout; how to verify a substrate program *without* reading values out is an open question, not "call numpy/`.real()` on the output."

### Tensor operations only — global not local efficiency

Every Sutra operation must be a tensor operation (matmul, element-wise ops, nonlinear element-wise: `tanh`, `exp`, `sqrt`, `abs`, `sign`). Doing `5 * 3` via 800-d vectors is locally wasteful — that's fine, that's the point. Breaking tensor uniformity to optimize locally breaks the compile-time fusion pass.

**Forbidden:**
- **Scalar extraction inside an operation.** Reading `v[AXIS_REAL]`, doing scalar arithmetic, packing back into a vector breaks the invariant.
- **Python control flow inside an operation.** `if/for/while` on scalar predicates. Use tensor-native substitutes: `x / (||x|| + eps)` not `if norm == 0`; `tanh(k·x)` not `sign(x)`.
- Declaring an operation "working" because *something* ran, without comparing to the spec's definition.
- Tuning thresholds until numbers "look right" without principled justification.
- Writing "algebraic," "pure math," "O(1) on the host," or "runs on host by spec" about any Sutra operation.

`loop (condition)` iterates `state ← R · state` on the substrate; both rotation and match run on the substrate.

### NO introspection — no readout, no logging, no monitoring, no debugging (Emma 2026-06-07)

**Sutra has no way to read a value off the substrate, log, monitor, or debug — by design. There is no escape hatch.** This is load-bearing language identity, not a convenience to be reintroduced.

- The accessors `real()`, `imag()`, `truth()`, `component()` (and `norm`) are **violations** and are being **removed from the language** (parser/codegen/runtime). They compile to `float(v[...].item())` — a host readout that (a) runs subsequent arithmetic on the CPU and (b) **detaches the autograd graph**, so any program touching them is neither substrate-pure nor end-to-end differentiable.
- The prior ruling here ("accessors are monitoring/debugging only — fine") came from the 2026-04-30 purity audit and was **wrong**: it blessed a hole in the core invariant. `.real()` then spread into operations (the mini_wasm_machine) and into transpiler output.
- Enforcement, not aspiration: the codegen must emit **zero** host-readout (`.item()` / `float(tensor…)` that returns to host computation) inside any operation. This is grep-auditable; a CI gate should fail the build on new occurrences.
- Consequence being worked out: a substrate-only language with no readout forces **substrate-to-substrate verification** — you cannot `.real()` a result in a test. (Open design question; see `queue.md`.)

See the audit + removal plan in `queue.md` and `planning/findings/2026-06-07-codegen-host-readout-audit.md`.

### When you catch a shortcut

Stop. Report what actually executed, including negative findings. Reference the specific spec file. Fix the implementation or propose a justified spec change. Silently hand-waving past a failed validation is not acceptable.

### Subtler substrate breaches — measurement-required (Emma 2026-05-28)

Three failure modes the "every op runs on the substrate" check does NOT
catch. The Yantra OS attempt (paused 2026-05-28 — see `DEVLOG.md`) shipped
all three as "substrate-pure" for weeks. Dispatch-level cleanliness is
necessary, not sufficient — these three are the sufficient set.
The FV paper §4.4 names this rule formally.

**1. Dimension audit.** If a `.su` has zero `basis_vector` calls, the LLM
codebook is unused — `runtime_dim` can drop from the default 868 to ~108
or ~16 with no loss of correctness. Yantra apps ran at 768 despite zero
basis_vector calls; 96× cost paid silently for weeks. **Rule:** count
`basis_vector` calls and pick the smallest `runtime_dim` the task needs.

**2. State-locus audit.** A `.su` function taking a scalar and returning
`make_real(value)`, called in a host loop that extracts via `vsa.real()`
between calls, is **NOT an RNN** — the recurrence lives in a Python
variable. **Rule:** for any claim of "recurrent" / "RNN" / "substrate-pure
state," the state MUST be a vector surviving across calls without host
`real()` extraction. `make_real(scalar) → host → real(...)` per tick is
a counter, not an RNN. Yantra `count.su` / `toggle.su` / `font_demo`
`cycle_step` wore the RNN label until 2026-05-28 corrected the framing.

**3. Signal-separation audit.** A substrate function can return numbers
via `make_real(some_op(...))` while the numbers fail to distinguish the
classes the function is supposed to distinguish. First Yantra `font_bound`
encoding (`bundle(bind(p,LIT)/(p,UNLIT))`): lit and unlit cell cosines
OVERLAPPED at every `runtime_dim` 16..256. **Rule:** every substrate
classifier ships with a measured `gap = min(positive_class) -
max(negative_class)` table. Without the table, the claim "the substrate
decides X" is unverified.

**The meta-rule.** All three pass the dispatch check; dispatch is
necessary, not sufficient. Dim audit + state-locus audit + signal-
separation audit are the sufficient set. Put the numbers in the commit
message or the planning doc.

## Architecture and Conventions
- **Stack:** Python + PyTorch + Ollama. Runtime uses `nomic-embed-text` (768-d, mean-centered). PyTorch is the canonical compile target (`codegen_pytorch.py`, CPU or CUDA).
- **Numpy backend** (`codegen.py`) is deprecated and being retired. New code uses `PyTorchCodegen`.
- **Repo structure:** `sdk/` (compiler, plugins), `examples/` (`.su` programs), `planning/sutra-spec/` (spec), `planning/findings/` (findings), `sutraDB/` (triple store), `docs/` (static-site source for `sutra.topazcomputing.com`, built by `scripts/build_site.py` — not MkDocs).

## Prior work
The empirical foundation is relational-displacement analysis of frozen embedding spaces, published in [`EmmaLeonhart/latent-space-cartography`](https://github.com/EmmaLeonhart/latent-space-cartography). **Verify any specific claim against the source.** Do not quote numbers from memory — prior versions of this file contained contradictory r-values and pathology descriptions. State claims as "prior work showed displacement vectors exist in frozen embedding spaces" without specific numbers unless you've read the source.

## K=5 rank-k sweep — LAST attempt; do not restart if it dies (Emma 2026-05-28)

The K=5 rank-k sweep (`experiments/rank_k_is_x.py --K 5 --k {1,2,4}`) has failed repeatedly (~3+h of subprocess time, 0 usable bytes). Emma's call: **the current run is the last attempt.**

- **Alive: leave it** — don't kill it; results are a bonus, not worth interrupting for.
- **Dead / already-dead: do not restart.** Remove the entry from `queue.md` State Inventory A.1 + task #20; note in the commit that Emma closed it.
- **Do not re-queue in future sessions** unless Emma re-greenlights explicitly. "The smoke passed at K=2" / "the bug is fixed at both levels" is NOT justification to relaunch — the failure that matters is the wall-clock outcome (0 useful output), not per-fix verification.

## Severity ladder for asking-vs-doing (Emma 2026-05-28 — DRAFT, will refine)

Failure modes ordered worst-to-best. Top of list = most critical to avoid.

**1. (WORST) Build 4 of 5 things and defer the 5th via chat-only mention.**
When Emma gives a list of N things and I can do N-1 but not the Nth, the failure mode is: do the N-1, mention in a chat reply that "the Nth is deferred / blocked / pending input." That mention is **not enough**. By the time the chat scrolls past, Emma may be away (auto mode), the Nth becomes assumed-built, downstream work depends on the gap, and the failure surfaces hours/days later as compounding technical debt. **Force the use of `AskUserQuestion` for the missing piece — it triggers a phone notification; chat messages do not.** If the tool is technically available in the current mode, use it. If it isn't, surface the gap in a way Emma can't miss (top of the response, NOT a passing aside).

**2. Sit with a large instruction set without doing anything *and* without asking.**
For deep systems work the AI's judgment about "is this a question or just-do-it?" is poor; the safer default is asking. The fact that I might not have well-formed multiple-choice options is NOT a reason to skip `AskUserQuestion` — generate four plausible attempts, the Other field exists for Emma to override. Getting Emma's answer into the loop is the tool's purpose; demonstrating well-formed options is not.

**3. Treat "push to remote" mentions as routine.** When Emma's message references pushing to remote, that's almost always one of two things:
- She wants to access the repo from a different machine — the push has to happen before she can pull there.
- She wants to trigger CI/CD — especially clawRxiv paper submissions, which need every revision pushed individually so each gets its own AI-reviewer cycle. **This is usually the primary thing she's actually asking for.**

Either way: **prioritize the push.** Don't batch it with unrelated work. Don't defer it. The push itself is the action Emma is asking for. **Work more aggressively to get the push out than you would in normal commit flow.**

Emma's calibration on when "push to remote" appears: *she wouldn't say it during serious building / hard-mode work — it shows up specifically in paper-edit-like situations where CI/CD matters*. So a "push to remote" mention is also a signal that the current work is paper-edit-shaped, not deep-implementation-shaped.

**Aggressive rebasing + failed CI runs are acceptable, often correct.** When push-to-remote requests stack (rapid paper edits, cron bumps, clawRxiv resubmissions), push-fast-rebase-as-needed beats wait-for-clean-moment. A failed CI run from aggressive pushing is usually fine — the cron heals across runs. Conservative batching costs more (lost reviews, lost signals, Emma waiting on her other machine) than cancelled workflow runs.

**Merge conflicts mean GO FASTER and merge CONTINUOUSLY.** Conflicts on main are rare and trivial (typically `paper/formal-verification/.post_id` and similar bot-managed files take origin's value). When they appear, it's because two agents are racing on the same remote — the conflict signals parallelization. Resolve, rebase, push faster. **The deeper why:** in a cross-agent setup, one agent has finite tasks (paper edits, audit ticks) and the other has one hours-long task (substantial migration, long experiment). I might not know which I am. The danger is the long-task agent reading stale code because the finite-task agent didn't keep origin merged in. Fix: `git fetch origin && git pull --ff-only` (or `--rebase`) is part of every action, not optional.

**Cross-cutting:** `AskUserQuestion` is the phone-notification escape hatch. Plain chat does not notify. If the tool is available and a decision Emma should make is in front of me, the choice is "use the tool" or "carry the debt"; pick the tool.
