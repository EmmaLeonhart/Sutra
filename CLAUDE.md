# embedding-mapping → Sutra

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

- **Humans read the website at `sutra.emmaleonhart.com`.** It is a static site rendered from Markdown by `scripts/build_site.py` — a hand-rolled generator that replaced the old MkDocs Material setup (`mkdocs.yml`, `docs/stylesheets/`, `docs/assets/` are gone) onto the shared emmaleonhart.com identity. The build emits **one HTML page per Markdown file under `docs/`** (every `docs/*.md` and `docs/tutorials/*.md`, except any path containing `interactive/`), plus `/paper/` rendered from `paper/paper.md`. So the live site is **~23 pages, not two** — the swap from MkDocs to `build_site.py` changed the generator, not the page count. The set: the homepage (`docs/index.md`); the concept/tutorial pages (`vision`, `operators`, `ontology`, `compilation`, `loops`, `promises`, `numeric-math`, `typescript-to-sutra`, `what-is-sutra`, `memory`, `paradigms`, `primitive-classes`, `logical-operations`, `demos`, `history`, and the `tutorials/` set); `/paper/`; `/neurips-2026/` (`docs/neurips-2026.md`, the frozen-submission archive with the paper PDFs + reproduction zip); and `/arxiv/` (`docs/arxiv.md`). The homepage is **not** bare — it carries an "Explore" section linking the doc pages, a "Read the paper" button, and a NeurIPS 2026 archive card. `/arxiv/` is a direct-URL-only utility page for grabbing the LaTeX source bundle when a paper correction needs re-uploading; it carries a `noindex, nofollow` meta tag and `robots.txt` disallows the bundle file (`/sutra-arxiv-source.tar.gz`), so it stays out of search — every other page is indexable. Keep every website page free of repo-internal scratchpad references (`queue.md`, `todo.md`, `planning/...`, deep `sdk/...`).

The two surfaces are **not generated from the same source**. `docs/neurips-2026.md` is hand-written for the website; the canonical Markdown elsewhere in the repo is hand-written for agents. They are allowed to drift in framing, level of detail, and which examples they pick. They must not contradict each other on facts.

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

An MCP server is a core part of the language runtime. The website (`sutra.emmaleonhart.com`, a static multi-page site built by `scripts/build_site.py` from every `docs/*.md` plus `paper/paper.md`) is the human-facing surface — see §"Audiences" below.

### Next venue target: NeurIPS

clawRxiv auto-submit runs on every paper edit (per the §"Paper" section below). The longer-term venue target is **NeurIPS**. Work in `todo.md` answers the question *what does this language need to be NeurIPS-ready?*

## Workflow Rules
- **Commit early, often, and push immediately.** Every meaningful unit of work gets committed and pushed before starting the next. No local-only work.
- **Update `queue.md` in the same commit as the work.** If the session terminates mid-task, the next session must immediately know what's done, in-flight, and next. Stale queue.md = lost context.
- **Always use the task tool with queue.md.** Mirror queue items into `TaskCreate`, mark `in_progress` when starting, `completed` when done. Remove completed items from queue.md in the same commit. The task tool and queue.md are two views of the same list — do not let them drift.
- **When planning, write the plan to `queue.md` FIRST, then execute.** If you enter planning mode (or just stop to think before doing non-trivial multi-step work), the FIRST action after the plan is taking shape is to drop concrete items into `queue.md`. Only then begin executing them. The plan must not live only in chat context — chat dies on session interrupt; the queue survives.
- **Do not enter planning-only modes.** All thinking must produce files and commits.
- **Keep this file and README.md up to date.**
- **Deprecate, don't remove** unless the deprecated thing actively misleads, has no users, or is a maintenance liability.

### Vibe-coded projects need legacy code removed, not kept

This project is built vibe-coding-first — large architectural decisions get made in chat, partially implemented, then sometimes superseded by a different shape a few sessions later. In a more traditional engineering process, "deprecate, don't remove" is the safe default because the old code has known users and predictable behavior. **In a vibe-coded project, the opposite tends to be true:** legacy code that lingers after a design shift gets quietly re-wired into newer paths by later sessions that don't know the old code was supposed to be retired. The 2026-05-10 host-Python-string bug is a concrete example — an April 10 design decision (string literals stay host because the codebook decode is the substrate boundary) was correct in its original scope but silently became wrong when a parallel string model landed on May 8, because no one removed the old emission path and the spec / code drift was invisible until a new use case exposed it.

In practice this means:

- When a design shift makes the old path *also* incorrect rather than just less preferred, remove the old path. Do not leave both alive on the assumption that callers will migrate.
- When you find an old code path that contradicts the current spec, **stop and ask whether it's legacy weirdness from a superseded direction** before adding a workaround. Workarounds that paper over spec drift are how the drift becomes load-bearing.
- The `feedback_check_what_is_open_before_pitching_blocker` memory generalizes here: read the spec and the open questions before assuming a long-lived code path is correct. A code path being present is not evidence that it's correct in the current design.

This rule is in tension with "deprecate, don't remove." The reconciliation: deprecate-don't-remove applies when the old path is *still correct* in its original scope and someone might depend on it. When the old path is no longer correct, removal is the right move and a stale-path-left-behind is the bigger risk.

**Carve-out for intentional compatibility code (Emma 2026-05-10).** Code that exists explicitly to absorb a different ecosystem — the `JavaScriptObject` class and its operator overrides, the TS transpiler's coercion shims, `make_char` as an alias for `make_string`, the legacy `AXIS_CHAR_FLAG` name — is not "legacy weirdness" in the sense above. It's intentional compatibility code that has a current purpose (let JS / TS source land correctly on the Sutra substrate). Don't sweep that away under the "remove legacy" rule. The rule targets *superseded-design residue* (an old code path that was correct in a previous design but is wrong in the current one); intentional compatibility code is a different category. Strings are core substrate types and need to be correct under the current design; JavaScript-object overrides are interop and exist precisely because the ecosystem they target is weird in known ways.

`todo.md` is for longer-horizon work. `queue.md` is for the next active session. Items migrate from `todo.md` → `queue.md` → deleted on completion.

### Barrel through specified work; verify against spec; don't add false caution

**Counterbalance to the §"Integrity and correctness" rules at the top of this file
(Emma 2026-05-20).** The safety-critical framing says do the real
operation on the real substrate, even if slower or uglier. It does NOT
say "treat every queued item as needing a multi-session gated approach
before touching it." When Emma adds an item to `queue.md` and the design
is already laid out in `planning/sutra-spec/*.md`, the expected behavior
is:

1. **Read the spec.** Promises/await is `promises.md` + `axon-io.md`.
   Loops is `control-flow.md`. Binding is `binding.md`. The specs are
   the authoritative design; they aren't aspirational sketches.
2. **Check whether the code already matches.** `Audit.md` keeps a
   per-leak status with file:line anchors. The tests under
   `sdk/sutra-compiler/tests/` are regression guards on the
   substrate-purity claims — running them tells you what's currently
   true, not what was true when an old session wrote a queue item.
3. **Barrel through the work.** If the spec is clear and the
   implementation is close, finish it. The §"Integrity and correctness" rules
   are about *faking results* and *fake substrate purity*, not about
   pace. Verification (run the tests, check decoded output against
   ground truth, read what's emitted) is how you discharge the safety
   rules — not by avoiding the work.
4. **Only flag "deliberate, gated session" when the spec is genuinely
   not settled.** Spec-level open questions belong in
   `planning/open-questions/`; if the open question doesn't exist
   there, the design is settled and the work is implementation.

Concrete anti-pattern Emma flagged 2026-05-20: I copied an old
"deliberate, gated" framing for `await_value` from a stale handoff
into a fresh queue item without first reading `promises.md` +
`axon-io.md` + `Audit.md`. That reading would have shown the leak was
already fixed 2026-05-17 as the exact algebraic reduction of the
spec-2 lowering. Adding a queue item for already-done work isn't
caution — it's noise that makes future sessions think there's
something pending.

The rule the user wants codified: **read the spec, verify against
ground truth, barrel through; don't multiply caution by quoting
prior sessions.**

### When Emma gives an algorithmic explanation, IMPLEMENT it — don't brush it off

**Added 2026-05-24 after a repeated, costly pattern.** Emma designed
Sutra and knows its mechanisms — defuzzification, saturation, the
canonical axes, `select`, binding — far better than any agent landing
in this repo. The recurring failure mode: Emma gives a concrete
algorithmic explanation of how to do something on the substrate; the
agent decides it "can't work," substitutes its own variant, the
variant fails or is uglier, and the agent reports the idea as blocked.
**Almost every time, Emma's original idea was correct** and the agent
simply never built the thing she actually described.

Concrete instance (2026-05-24): exact operator dispatch for the Yantra
calculator. Emma said *defuzzify `select` enough and the branches stop
blending.* The agent first concluded "`select` is softmax, never a hard
one-hot, so it can't be exact," then tried Lagrange polynomial masks,
then elementwise `tanh` masks (which failed on vector noise). Only when
it finally built **the literal thing Emma described** — `select` with
scores sharpened past the float32 softmax-saturation point (`exp(-120)`
underflows to exactly `0.0`), scored by `dot(op - t, make_real(1))` —
did it come out **18/18 bit-exact**. The detour burned most of a session.

The rule:
1. **When Emma describes an algorithm, implement that algorithm first**,
   exactly as described, before proposing alternatives. Build it, run it,
   read the real output.
2. **"I think that can't work" is a hypothesis to test, not a
   conclusion.** Test it on the substrate. The integrity rules *require*
   measuring; they never license dismissing an idea unmeasured.
3. **If it seems not to compose, the gap is usually a primitive to
   expose, not a wrong idea.** Here `dot` simply wasn't a callable
   builtin; exposing it made Emma's approach work.
4. **Substituting your own variant for Emma's stated method is the
   anti-pattern** — especially on Sutra internals, where she has the
   ground truth and you do not.

## Cross-repo workflow: Sutra ↔ Yantra

Sutra is consumed downstream by **Yantra**
(`https://github.com/EmmaLeonhart/Yantra`), the GPU-native operating
system being built in Sutra. Yantra pins this repo as a git submodule
at `external/Sutra` and may **drive Sutra-side changes from inside
Yantra sessions**. This isn't a typical workflow but it's the right
shape because the projects are tightly coupled — Yantra is "the OS
that uses Sutra"; Sutra is "the language Yantra is built in."

If you see a Sutra commit message that mentions Yantra (e.g.,
"sutra-from-ts v0.1.0: docs catch up to working CLI; sutra-dev[ts]
extra"), that's the workflow operating as designed, not someone
pushing from the wrong repo. The Yantra-side companion CLAUDE.md
documents the same pattern from the other end.

### Division of responsibility

- **Yantra — actual kernel orchestration, runtime shape, OS-level
  concerns.** `kernel/` (the Connectome Manager + axon router),
  the Rust orchestrator (eventually), storage-tier moves
  (disc/RAM/GPU), capability check architecture, the FS bridge,
  the GUI/browser stack, the Yantra paper.
- **Sutra (this repo) — the language. Connecting things together
  at the language level, debugging the language, language-side
  primitives Yantra needs.** `sdk/sutra-compiler/`,
  `sdk/sutra-from-ts/`, `sdk/sutra-from-c/`, the lowering passes,
  the axon spec, the multi-process runtime, the
  serialise-process-state primitive, the runtime ABI Yantra
  consumes.

### Rules that bind regardless of who's driving the change

When a Yantra-driven session is editing Sutra source, the rules in
this file still apply, in this order of force:

1. **The integrity / substrate-correctness rules at the
   top of this file.** A
   change driven by "Yantra needs this primitive" does not get a
   pass on substrate-purity validation.
2. **The "NO MATH SHORTCUTS" section.** Same reason. Every Sutra
   operation runs on the substrate; numpy is compile + monitor
   only; tensor operations only on the runtime hot path.
3. **The Workflow Rules above** (commit + push immediately,
   plan-into-`queue.md`-first, mirror to the task tool, no
   local-only work). Yantra's own queue.md is separate; this
   repo's queue.md is the one that binds when editing this repo.
4. **The frozen `paper/neurips/` archive.** Don't touch it. If a
   Yantra-driven change makes the NeurIPS paper claims look shaky,
   surface that to the user; do not silently amend.

When the Yantra-driven change is purely docs / pyproject / CLI
scaffolding (no runtime code touched), the substrate-purity rules
don't directly bite, but the workflow rules still do.

### When to tag a Sutra release vs. just push to master

- **Tag a release** when Yantra needs to depend on a specific
  Sutra version that carries the change (e.g., a new optional
  extra, a new public API, a bug fix that affects Yantra's tests).
  Yantra then pins its `external/Sutra` submodule at the new tag.
- **Just push to master** for docs-only fixes, internal
  refactors, or anything where Yantra doesn't need version
  pinning. Yantra can bump its submodule pointer to the new
  master HEAD without a release ceremony.

## Paper

Claw4S the competition is over. clawRxiv the platform stays — it's a feedback / visibility channel, not a leaderboard we're chasing. Each push to `paper/paper.md` or `paper/supplementary/SKILL.md` triggers `papers-ci.yml`, which submits to clawRxiv, polls for the AI peer review, and commits the review back under `paper/reviews/v<N>_post<ID>_review.{json,md}`. `paper/.post_id` tracks the latest post in the supersedes chain.

None of the prior Claw4S-specific rules apply (no "lock in a Strong Accept by disabling submission," no "always check the latest review before pushing," no dedup-bypass concerns). Reviews are signal, not verdicts. NeurIPS is the longer-term target — see `todo.md`.

**Second paper — formal verification (live, kept in sync with the work).** `paper/formal-verification/paper.md` (clawRxiv post 2613, paper_id 2605.02613) is a SECOND paper with its own supersedes chain (`paper/formal-verification/.post_id`) and its own workflow `.github/workflows/fv-paper-ci.yml` (auto-submits on push to `paper/formal-verification/paper.md`). It is a **live artifact: as formal-verification work lands (an obligation discharged, a checker built, a scope change), update this paper in the same session** — cite only measured numbers, mirror the §"What we are not claiming" discipline. Ground truth it must not contradict: `planning/sutra-spec/formal-verification.md`. Agenda: `todo.md` § "Formal verification". This is NOT under the `paper/paper.md` / `paper/neurips/` freezes — those are separate, frozen papers; the FV paper is free to evolve.

### 🔒 NeurIPS submission is FROZEN at `paper/neurips/`; `paper/paper.md` is now the live revision target

**Updated 2026-05-10.** The freeze applies to `paper/neurips/` only. The
`paper/paper.md` at the parent directory is the **live, evolving copy**
and is free to receive updates toward the next venue, journal extension,
or any other future revision.

`paper/neurips/` contains the camera-ready NeurIPS 2026 submission as a
permanent snapshot:
- `paper/neurips/paper.md`
- `paper/neurips/paper.tex`
- `paper/neurips/neurips_2026.sty`
- `paper/neurips/supplementary/{README,SKILL,REPRODUCE,SYNTAX}.md`

NeurIPS does not accept post-deadline edits, so the files under
`paper/neurips/` are treated as immutable to keep them in sync with
what was submitted.

This means:
- Do not edit any file under `paper/neurips/` — not the title, not the abstract, not the body, not the references, not the appendix, not the supplementary docs. Not for rewording, not for tightening, not for new findings, not for clawRxiv reviewer feedback, not for typos, not for anything.
- Do not "improve" the NeurIPS frozen version in response to a review. Reviews are signal for the next venue, not edits to the submitted version.
- If a later result contradicts a claim in the NeurIPS paper, **stop and tell the user** — do not silently amend `paper/neurips/paper.md` to match. The user decides whether to file an erratum at the next venue, draft a separate revision in `paper/paper.md`, or accept the discrepancy.
- If the user explicitly says "unfreeze the NeurIPS paper" or "edit `paper/neurips/` anyway," then and only then does this rule lift. Mention the lock first if the user appears to be requesting an edit to the frozen archive; do not assume implicit consent.

The live `paper/paper.md` is **not** under this freeze. It is free to evolve. The downloadable artifacts on the website (camera-ready PDF, anonymized PDF, supplementary zip) are built from `paper/neurips/`, not from `paper/paper.md`. See `docs/neurips-2026.md` for the user-facing download page and `paper/neurips/README.md` for the in-repo explanation.

### 🔒 `paper/paper.md` is also FROZEN through May 2026 (the arXiv lock)

**Added 2026-05-20.** Emma uploaded `paper/paper.md` to arXiv on
2026-05-19 (the arXiv-fitting abstract-trim commit is `e7cca673`).
**Updated 2026-05-21:** Emma authorized a minor arXiv correction and
a v2 re-upload (correction series starting at commit `0b151b79`):
(1) fixed the broken Appendix H hyperparameter table (overflowing
7-column table → per-experiment bullet list, no data changed);
(2) dropped "figure" from the AI-use statement's "no … was generated
by a language model" sentence (the figures are AI-drafted TikZ
schematics, not data plots); (3) removed the AI-use statement's
parenthetical about AI-suggested code substituting host numpy (aired
an internal bug inside the disclosure). **The arXiv-v2 target is the
current `main` HEAD** — the freeze is re-pinned to whatever HEAD is
once the v2 correction series lands, not to a single fixed hash,
because each correction commit moves it. Until **June 1, 2026** the
live `paper/paper.md` is otherwise treated as immutable so the repo
state matches what was uploaded.
This is a *time-bounded* freeze, not the permanent NeurIPS one above
— the lock lifts automatically the moment May 2026 ends, and the
live paper resumes being the free-to-evolve next-venue draft.

This means, until June 1:

- Do not edit `paper/paper.md`. Not for typos, not for clawRxiv
  reviewer feedback, not for new findings, not for tightening,
  not for the next-venue polish items previously queued (ablation
  table, polynomial-rationale paragraph, section-granular AI-use
  breakdown, Futamura bib entry). All of those wait until June.
- Do not edit any file referenced from the arXiv submission as
  if it were the source of an arXiv-visible claim (e.g. the
  supplementary docs the arXiv source bundle links into).
- `paper/neurips/` stays under its own permanent freeze (above).
  Both locks are active concurrently.
- The `papers-ci.yml` auto-resubmit on `paper/paper.md` push is
  fine to leave running — there is just nothing to push.
- If a later finding *contradicts* the arXiv text, stop and tell
  the user; do not silently amend. Same discipline as the
  NeurIPS freeze.

If the user explicitly says "unfreeze the paper" before June 1,
the lock lifts. Mention the freeze first if a user request appears
to ask for a `paper/paper.md` edit before then, so there is no
silent overriding.

### Paper-code durability — keep the original NeurIPS paper's examples working

Every `.su` program, reproduction script, and supplementary surface that the **NeurIPS submission** (now frozen at `paper/neurips/`) references must continue to compile, run, and produce the same observable outputs **for at least one year after submission, ideally indefinitely**. The frozen paper text cannot be patched if the code drifts; the only way the NeurIPS claims stay reproducible is if the code keeps working.

In practice this means:
- Surface syntax used in any example cited by `paper/neurips/paper.md` (`map<vector, string>` codebooks, `bind`/`unbind`/`bundle`, `loop` forms, `dict<K, V>` rotation hashmaps, etc.) stays valid. If a feature is renamed or restructured, keep an alias / deprecation shim — do not break the spelling the NeurIPS paper uses.
- The supplementary smoke test (`examples/_smoke_test.py`) keeps passing. If a refactor regresses it, the refactor is wrong, not the smoke test.
- The reproduction scripts under `experiments/` referenced by `paper/neurips/supplementary/SKILL.md` / `REPRODUCE.md` continue to produce the same output (modulo run-to-run sampling noise that's already documented as such).
- The supplementary `SYNTAX.md` description (frozen under `paper/neurips/supplementary/SYNTAX.md`) must keep matching what the compiler actually emits for the NeurIPS-cited surface. If implementation drifts past those forms, **add a new alias** rather than retroactively changing the frozen description.

If a change would break NeurIPS-paper-code reproducibility, the right move is one of: (a) make the change additive and keep the old form working, (b) update the live `paper/paper.md` (which is allowed to evolve) so the next-venue version reflects the new shape, or (c) flag the conflict to the user so they can decide whether the gain is worth the break. Do not silently break the NeurIPS-cited path.

The supplementary zip is a build artifact (not committed) regenerated by `scripts/build_supplementary_zip.py`; rebuilding and re-uploading it is fine and expected when the doc/compiler need to be brought back into sync.

### Reference PDFs are re-downloaded each session, not committed

When we need to read a paper from arxiv (or anywhere else) to ground a comparison or check structure, the PDF goes into a gitignored cache directory (e.g. `references/`) and is **re-downloaded every time it's needed**. Do not commit the PDF to the repo.

The reason is intellectual property: arxiv papers are freely accessible to download but redistributing them inside another project's repo is a different question, and the cleanest answer is "we never redistribute, we always fetch fresh from the original source." A small `scripts/fetch_reference_pdfs.py` (or similar) downloads the file each time. The cache directory itself is gitignored; only the fetch script is committed.

If a reference is needed and the cache is empty, run the fetch script first, then proceed.

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
2. **Monitoring** — decoding substrate output for reporting/verification. Happens around the run.

Numpy is **not** allowed on the runtime hot path. A numpy result with a torch wrapper is a lie about what executed.

### Tensor operations only — global not local efficiency

Every Sutra operation must be a tensor operation (matmul, element-wise ops, nonlinear element-wise: `tanh`, `exp`, `sqrt`, `abs`, `sign`). Doing `5 * 3` via 800-d vectors is locally wasteful — that's fine, that's the point. Breaking tensor uniformity to optimize locally breaks the compile-time fusion pass.

**Forbidden:**
- **Scalar extraction inside an operation.** Reading `v[AXIS_REAL]`, doing scalar arithmetic, packing back into a vector breaks the invariant.
- **Python control flow inside an operation.** `if/for/while` on scalar predicates. Use tensor-native substitutes: `x / (||x|| + eps)` not `if norm == 0`; `tanh(k·x)` not `sign(x)`.
- Declaring an operation "working" because *something* ran, without comparing to the spec's definition.
- Tuning thresholds until numbers "look right" without principled justification.
- Writing "algebraic," "pure math," "O(1) on the host," or "runs on host by spec" about any Sutra operation.

`loop (condition)` iterates `state ← R · state` on the substrate; both rotation and match run on the substrate.

Accessor methods (`real()`, `imag()`, `truth()`, `component()`) are monitoring/debugging only — fine because they don't sit inside another operation's definition.

### When you catch a shortcut

Stop. Report what actually executed, including negative findings. Reference the specific spec file. Fix the implementation or propose a justified spec change. Silently hand-waving past a failed validation is not acceptable.

## Architecture and Conventions
- **Stack:** Python + PyTorch + Ollama. Runtime uses `nomic-embed-text` (768-d, mean-centered). PyTorch is the canonical compile target (`codegen_pytorch.py`, CPU or CUDA).
- **Numpy backend** (`codegen.py`) is deprecated and being retired. New code uses `PyTorchCodegen`.
- **Repo structure:** `sdk/` (compiler, plugins), `examples/` (`.su` programs), `planning/sutra-spec/` (spec), `planning/findings/` (findings), `sutraDB/` (triple store), `docs/` (static-site source for `sutra.emmaleonhart.com`, built by `scripts/build_site.py` — not MkDocs).

## Prior work
The empirical foundation is relational-displacement analysis of frozen embedding spaces, published in [`EmmaLeonhart/latent-space-cartography`](https://github.com/EmmaLeonhart/latent-space-cartography). **Verify any specific claim against the source.** Do not quote numbers from memory — prior versions of this file contained contradictory r-values and pathology descriptions. State claims as "prior work showed displacement vectors exist in frozen embedding spaces" without specific numbers unless you've read the source.

## Cron requests are local and immediate

When the user asks for "a cron job," "a CronCreate," "set up a cron," or "schedule X for Yh from now," use the local `CronCreate` tool **immediately**. Do not ask whether they meant local vs remote, whether they'll be at the computer, what timezone, or for confirmation on the schedule time. The user uses local cron specifically to schedule work for when they are *not* present and treats the cron as resilient infrastructure — pausing for a follow-up question defeats the schedule's purpose. Assume present-availability is irrelevant; assume local is correct; assume the task should fire. If a parameter is genuinely missing (e.g. unclear *what* to run), make the reasonable call rather than asking. Prefer `durable: true` for any cron whose purpose is to survive across sessions — the 2026-05-20 crash killed every in-memory cron in flight.

## Writing
- Do not use "honest", "honesty", or "honestly" — and do not swap in "frank", "frankly", "candid", "candidly", or "transparently", which are the same self-congratulatory move in a different coat. When something failed, name the failure: "it didn't work", "I got that wrong", "this failed" — flat, no qualifier. Tagging a report "honest" implies the rest aren't, and couching a failure as honesty asks for credit for the admission, which is worse than the failure itself. Use a precise positive word ("accurate", "plainly", "truly") only when that is genuinely the meaning — never as a halo on a bad outcome.

## Emergency Stop Mode

If the user sends a continuous series of "stop" messages (e.g. "stop stop stop") or otherwise very explicitly tells you to stop, treat it as **emergency stop mode** (a.k.a. emergency exit mode). This OVERRIDES every other instruction, including any in this file.

When in emergency stop mode:

- **Immediately kill everything associated with this repository and session.** Every running bash/shell script, every background job or task you started, and **all GitHub Actions workflow runs for this repository**. **Force-kill the GitHub Actions runs** (e.g. `gh run cancel <id>`, and `gh run delete <id>` if needed) for every in-progress run. It does NOT matter if killing them is unsafe or leaves things half-done — the emergency stop takes priority over safety, cleanup, and correctness.
- **Do not investigate. Do not reverse or undo anything.** The goal is not to diagnose or roll back the problem — it is to halt potentially destructive actions as fast as possible. Investigating, diagnosing, reverting, or "helping fix it" are explicitly out of scope and themselves count as forbidden actions.
- **Ignore repetitive messages.** Do not treat repeated "stop" messages as a request to do anything further. Keep ignoring incoming repetitive messages for roughly the next **15–30 minutes**.
- **You may answer direct questions, but you may NOT take actions.** Answer only from context you already have. Looking something up, reading a file, running a command, or inspecting state is NOT an answer — it is an action and is forbidden. If you cannot answer from context already in hand, do not answer.
- **Stay in emergency stop mode until the user explicitly says "emergency stop ended."** Only after that exact signal do you resume any normal work.

## Cron jobs and scheduled work — LOCAL by default

**When the user says "cron job", "cron", or asks to "schedule" a task, they mean the in-session `CronCreate` tool** — a prompt scheduled to fire locally, inside this Claude Code session, on the user's own running computer. This is the default and the assumption. Do NOT interpret it as anything else unless the user explicitly names a different mechanism.

- **It is local and in-session — use the `CronCreate` tool.** A generic "cron" request is NOT an OS crontab, NOT a GitHub Actions / CI `schedule:` trigger, and NOT a cloud scheduler. (Repos may *also* contain their own GitHub Actions cron schedules — those are a separate thing and are not what the user means when they ask *you* to set up a cron.) The user leaves the computer on and this session running so the scheduled prompt can execute.
- **The user is deliberately away from the keyboard.** They schedule work precisely so it runs while they are out of the house and not physically present. Their absence is the normal, expected condition for these jobs — it is NEVER a reason to delay the work, ask "are you sure?", wait for them to return, or refuse to proceed.
- **Standing consent — just set it up.** Cron / `CronCreate` requests are pre-authorized. Create the job immediately and locally, then report what was scheduled. Do not block on confirmation or follow-up questions. Treating a routine cron request as something that needs hand-holding is itself the obstacle this section exists to remove.
