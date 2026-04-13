# Sutra — consolidated TODO

This file is the long-term agenda. `STATUS.md` at the repo root is the
active session queue — if the two disagree, STATUS.md wins for what is
being worked on *now*, and this file wins for what needs doing
*eventually*. Do not re-split this into per-subdirectory todo files.
See the meta-tasks below.

## 🔴 The current limiting factor: fly-brain Python-file clutter

Per user direction 2026-04-13: *"The fly-brain clutter is the biggest
issue; it is the biggest limiting factor here. ... it loads up context
with bullshit. It's probably the reason why things are so slow."*

Until the cleanup in `STATUS.md` queue item #1 is done, every other
item in this file is paying a context-tax. Sandbox sessions cannot do
that cleanup (it needs Brian2 + the FlyWire cache to verify which
files still pass their sims), so it is on Immanuelle's machine. The
CLAUDE.md rule §"Avoiding `fly-brain/` Python sprawl" is what keeps
the cleanup from being undone the next time someone reaches for a
copy-paste variant.

Read this paragraph before treating any tier-tagged item below as
truly the next thing to work on.

## ⚑ Meta-task — keep this file organized

This file's job is the long-term agenda. `STATUS.md` owns the active
session queue. The one meta-task that lives here (rather than in
STATUS.md queued work) is the standing discipline:

- **Keep this `todo.md` organized and consistent with STATUS.md.**
  Every item below lives under one of the priority tiers. An item
  without a tier is a bug in this file. When an item is actively
  being worked, it should also appear in STATUS.md's queue — the
  two are meant to agree, with STATUS.md winning for now-work and
  `todo.md` winning for later-work.

The former meta-task #1 (audit the `fly-brain/` Python-file sprawl)
has been moved to `STATUS.md` queued work where active on-machine
tasks belong — a Claude sandbox session cannot do that audit without
Brian2 + the hemibrain cache, so it does not belong in the
long-term-agenda meta section.

## 🗂 Priority tiers

Everything that follows should be mentally filed under one of:

- **Immediate** — do right now / this session. Usually mirrored in
  `STATUS.md` queued work.
- **Pre-Claw4S (deadline 2026-04-20)** — must land before the
  science-conference submission closes. Paper-critical.
- **Pre-Y-Combinator pitch** — must land before the YC pitch (no
  fixed date yet; assume "a few months"). Story-critical for the
  commercial pitch, not the academic paper.
- **This year** — should land in 2026, not necessarily tied to a
  deadline. Strategic rather than tactical.

When adding a new item, pick a tier. When closing one, delete the
line — do not leave "done ✅" stubs (that's what git log is for).

## 🗃 High-priority, below fly-brain clutter: audit `chats/` — chats are NOT permanent

### Core principle (user direction 2026-04-13)

> *"The chats are not supposed to be permanent; they're supposed to
> be put in there because the chats are often a bit better at
> thinking about certain things, but once their stuff is implemented,
> you just remove them."*

The `chats/` workflow itself stays — it is a legitimate input channel
(Claude on the web for unstructured design thinking, then HTML → `.md`
extraction via `scripts/extract_chat.py`, see CLAUDE.md §"Extract
Claude.ai chat exports"). But individual chats are working notes, not
archive material. **Once the ideas in a chat have been integrated
into the spec, planning docs, paper, or code, the chat gets deleted.**
That cycle has been broken — chats accumulate indefinitely and take
up repo space.

### What needs doing

For each file under `chats/`:

1. Read the `.md` extraction (the `.html` is just the source).
2. Identify what idea / decision / sketch the chat contained.
3. Check whether that content has already been absorbed into the
   spec (`planning/sutra-spec/`), into a planning doc
   (`planning/exploratory/`, `planning/open-questions/`,
   `planning/findings/`), into the paper, or into a CLAUDE.md /
   STATUS.md / DEVLOG entry.
4. If absorbed: delete the chat (both `.html` and `.md`). Git history
   preserves the original.
5. If not yet absorbed: leave the chat in place but file the
   integration-task somewhere appropriate (planning doc, todo.md
   entry, etc.) so it doesn't sit forever.

Optionally produce `chats/AUDIT.md` summarizing decisions so the next
pass picks up where this one left off — but the `chats/` workflow is
supposed to be lean enough that an audit doesn't need its own
permanent record.

### Execution constraint — same as fly-brain cleanup

**Do not attempt this from a Claude Code sandbox session.** Per user
direction: this needs to be done interactively with the user (or by
the user directly). The decision "has this idea been absorbed yet?"
requires judgment about what was a sketch vs. what is committed
direction, and that's a conversation, not a grep.

A Claude session reading this task and feeling tempted to "just
delete the chats whose md looks superseded" is in the same failure
mode as the fly-brain Python-sprawl audit: the static analysis is
not enough, and a wrong call destroys content the user wanted to
keep. Surface the queue item, do not execute.

### Priority placement

Slots directly beneath the fly-brain cleanup. Highest-priority item
in `todo.md` proper, but below the §"current limiting factor"
meta-blocker above. Should also appear in `STATUS.md` queue when
actively being worked.

---

# ! fly-brain (prepended from former `fly-brain/todo.md`)

Fly-brain work is the headline experimental pipeline and gets priority
placement. Lines prefixed with `!` are from the former
`fly-brain/todo.md` — that file has been deleted and its content lives
here so there is a single source of truth. The `!` marker survives so
that grep + visual scan both show provenance. Tier each line as work
gets picked up.

## ! Real Connectome Integration

### ! Phase 1: Hemibrain — DONE
(reference only; retained so the Phase-1.6 items below have context)

### ! Phase 1.5: Geometric Loops — MOSTLY DONE
- [ ] **[Pre-Claw4S]** Compile `while` to rotation + snap + prototype
  match (automatic pattern recognition) — last open item in this
  phase per former `fly-brain/todo.md`.

### ! Phase 1.6: Strengthen & Explore — TODO

Try each of these sequentially. If one doesn't pan out quickly, move
on to the next.

#### ! 1. Strengthen binding signal (12/16 → higher) — [Pre-Claw4S]
The move from synaptic weight flipping to input-space binding
(`a * sign(b)` as PN currents) is biologically correct but produces a
weaker decorrelation signal. The old approach created true inhibition
(negative synapse weights); the new approach only reduces excitation
(lower PN current). Ideas to try:
- **Silence negative PNs entirely**: set currents to 0 for PNs where
  `a * sign(b) < 0` instead of encoding them as below-baseline. Sparser,
  more contrastive input pattern — closer to what the fly does when
  some glomeruli are actively suppressed.
- **Two-pass binding**: present `a` and `sign(b)` in sequential circuit
  passes, let the circuit's temporal dynamics compute the conjunction.
  Biologically grounded in sequential-odor presentations.
- **Increase encoding gain**: raise the gain from 0.6 so the sign-flip
  component dominates the baseline. Simple parameter tuning.
- **Learned binding matrix**: train a matrix mapping `(a, b) → bound`
  using the circuit's own KC patterns as training signal
  (`is_converter`-style).

#### ! 2. Implement `is_converter` matrices — [Pre-YC]
Original Sutra conditional design from the design chats:
- **is_converter**: a single learned matrix that transforms any concept
  vector into a test operator (matrix). `is_dog = is_converter * dog`
  produces a matrix that, when applied to an input, maps it toward the
  reserved true/false region.
- **Universal test operator**: one `is_converter` works for ALL
  concepts. Strong empirical claim, needs validation on fly substrate.
- **Everything is multiplication**: `is_dog * input → near true or
  near false`. Test, conditional, transformation — all matrix
  multiplication; compiler can fold/fuse aggressively.
- **How to train it**: collect (concept, input, true/false) triples
  by running pairs through the circuit and measuring KC pattern
  overlap; `is_converter` is the matrix that best predicts whether
  two inputs activate overlapping KC populations.

#### ! 3. Pong demo on hemibrain — DONE
- V0 (1D bounce): 7-position prototype grid, 6 bounces, overlaps
  0.877–1.000.
- V1 (2D + paddle): 5×5 grid (25 prototypes), ALL positions at 1.000
  Jaccard, 3 paddle hits, 12 bounces, AI paddle tracks ball.
- Key insight: discretize positions into prototypes rather than
  continuous tracking; each position compiled as a KC pattern, circuit
  does position detection via Jaccard.

### ! Phase 2: FlyWire (after loops work) — [Pre-YC]
- [ ] Pull full adult Drosophila PN→KC connectivity from FlyWire/codex.
- [ ] Scale model to FlyWire dimensions (~140k neurons).
- [ ] Benchmark: prototype capacity at FlyWire scale (~10k-15k items).
- [ ] Run Doom on FlyWire-scale substrate (DOOM milestone ladder —
  note: the old `DOOM.md` was deleted in the 2026-04-13 audit; the
  ladder itself is folded into §Phase 3 below and tracked in
  STATUS.md strategic notes).

### ! Phase 3: Doom on FlyWire — [Pre-YC]
- [ ] Loop compilation via geometric rotation (NOT recurrent KC→KC).
- [ ] 1D integer arithmetic on substrate.
- [ ] Pong demo (minimum viable game on fly brain). *(Partial — see
  Phase 1.6 item 3; GUI version and full 2-player still open;
  `fly-brain/pong_brain.py` has a 326-line scaffold.)*
- [ ] General boolean composition (`&&`, `||`).
- [ ] Fixed-point arithmetic compilation.
- [ ] Doom logic-only with host rendering.

## ! Tooling

### ! IntelliJ Sutra Plugin — [This year]
- [ ] Diagnose why `!editor.bat` fails (likely JAVA_HOME or Gradle
  daemon issue).
- [ ] Get `sdk/intellij-sutra` `runIde` task working.
- [ ] Test `.su` file syntax highlighting in sandbox IDE.
- [ ] Verify code completion and live templates work.

---

## ⚠️ [Pre-Claw4S] FIX THE PAPER CI/CD PIPELINE ⚠️

**Standing operational problem. User has flagged this across multiple sessions.** `papers-ci.yml` / `competition-cron.yml` / `submit-papers.yml` have chronic failure modes during paper iteration — most visibly merge conflicts and failed runs that cost user time and occasionally lose work. Each attempted fix has introduced new failure modes (see STATUS.md "CI pipeline state" — it has been rewritten repeatedly).

**Status (per user, 2026-04-13):** still urgent — just not "within the hour" urgent — and may be nearly fixed already; check current pipeline state before assuming the diagnosis below is still live. Fixes below are easy in principle and the diagnosis is enough to act on when we do pick it up.

### Diagnosed failure modes (2026-04-13)

Two distinct chronic failures when papers are iterated fast. Both have plausible easy fixes — confirm they still reproduce before re-implementing, since later commits may have closed one or both.

**1. papers-ci HTTP 409 "This paper has already been revised".**
Happens when two pushes to master land close together. Run A reads `.post_id = 1587`, submits supersede, clawRxiv returns new id 1588, run A updates `.post_id` in-workspace. Run B (triggered by a subsequent push) checks out master before run A's `.post_id` commit merges (it goes through the cron PR flow that sometimes doesn't merge), reads stale `1587`, submits supersede, clawRxiv returns 409 because post 1587 is already superseded by 1588. The workflow exits 1 on the 409 without recovery.
Easy fix candidate: on HTTP 409 "already been revised", have `scripts/paper_submit_and_fetch.py` query clawRxiv for the latest version of the paper by slug, update `.post_id` from the API response, and retry supersede once. Or — even simpler — commit `.post_id` directly to master instead of through the cron PR path so subsequent runs see it immediately.
Side issue (not the cause of 409 but surfaces as a warning): `.github/workflows/papers-ci.yml` line 141 still hardcodes the stale fly-brain title "Turing-Complete Computation on the Drosophila Hemibrain Connectome". The submit script overrides with H1 from paper.md, so the submission is correct — but the warning noise should be cleaned up by syncing the matrix entry to the current H1 "Compiling a Vector Programming Language to the Drosophila Hemibrain Connectome."

**2. competition-cron push rejected: "refusing to allow a GitHub App to create or update workflow `.github/workflows/papers-ci.yml` without `workflows` permission".**
The cron only `git add`s three specific data files (`competition_analysis_raw.json`, `competition_reviews.json`, `planning/competition-analysis-latest.md`) — it does not touch workflow YAML. But GitHub's push protection appears to fire on the new-branch push because the tree on the new branch contains workflow files, regardless of whether the specific commits in the push modify them. STATUS.md's "CI pipeline state" section already records that `GITHUB_TOKEN` cannot push workflow files regardless of permissions config, and that papers-ci was reverted from branch+PR to direct-master-push for this reason (commit 211bd92). Competition-cron is still on the branch+PR flow and hits the same wall.
Easy-fix candidate (from user): pull-before-push / refresh-from-remote pattern. Currently the cron rebases ONLY after a push failure (lines 71–77). Doing `git pull --rebase origin master` *before* generating the data + committing would reduce the normal-race failure surface — but note that the specific error above is a permissions rejection, not a non-fast-forward, so rebasing alone may not fix it. The more direct fix is to mirror papers-ci's revert and push directly to master instead of opening a PR on a new branch.

### When picking this up

This is NOT something to diagnose from the repo alone. The Actions logs are not available from the Claude environment.

1. Ask the user to paste the log from a specific failing run, or point at the run URL. Do not guess at causes without logs.
2. Look at the workflow file that failed (in `.github/workflows/`) alongside the log before proposing a change.
3. Consider whether the fix belongs in the workflow YAML, in the paper-submission script, or in upstream hygiene (branch protection, rebase cadence, etc.) — it is not always the YAML.

The user has ruled out "paper.md sibling-file conflicts" as the dominant issue based on prior sessions — don't re-propose it.

## 🔴🔴 [Pre-Claw4S] Rotation on real connectome wiring — MOSTLY DONE, paper needs to catch up

**This section was outdated.** It used to say "every geometric loop in the paper uses a synthetic Givens rotation encoded as Brian2 synapse weights" and frame real-wiring rotation as unsolved. That is no longer accurate. Per `STATUS.md` → "Open / Known Gaps" (2026-04-12 update):

- **Polar decomposition gives a clean Q from real FlyWire weights.** The CX EPG→EPG recurrent (51 neurons) has effective rank 49 and off-diagonal fraction 0.508 — an order of magnitude closer to orthogonal than ALPN→LHLN. Polar decomposition (`fly-brain/real_rotation_epg.py`) yields Q = nearest orthogonal matrix to the real biological W, with `Q^T Q = I` to 1e-14, `det Q = +1`, norm preservation to machine precision.
- **Block-diagonal composition scales to 713-D** across 4 near-orthogonal FlyWire motifs (`real_rotation_composed.py`), orthogonality residual 5.34e-14. Passes 10/10 counting + 5/5 ordering at every composition stage (51 → 167 → 524 → 713).
- **Geometric loops pass on the real-wiring-derived Q.** 10/10 counting (k=3 and k=6 × 5 seeds) + 5/5 ordering on `real_rotation_epg_loop.py`.

What is *not* done:
- **Spiking lift to iterated rotation: 3/5 seeds at k=3** (`real_rotation_epg_loop_spiking.py`). Poisson noise flips argmax on seeds where the spectral structure puts `cos(Qv, Q³v)` close to `cos(v, Q²v)`. STATUS.md has the honest framing; paths to improve are longer SIM_MS, sharper-spectrum Q from motifs with more evenly distributed eigenphases, or loop-termination via Jaccard-on-KC (tier-3) which has higher SNR than direct cosine readout. This is queue item #3 in STATUS.md.

Follow-on scope (tracked separately):

1. **[Pre-Claw4S] Paper language has drifted — the paper undersells itself.** The paper is still using outdated architectural descriptions from earlier documentation (when we only had synthetic Givens on numpy) instead of describing what the repo actually does now (Q from polar decomposition of real FlyWire weights, composed to 713-D, passing all tier-2 tests on real-wiring-derived rotation). This is the *specific* kind of doc-vs-implementation drift the CLAUDE.md safety banner calls out: "If the spec and the implementation disagree, stop and resolve the disagreement explicitly." Action: read `sutra-paper/paper.md` and `fly-brain-paper/paper.md` critically against STATUS.md's "Open / Known Gaps" summary of the rotation work, and flag every passage that describes the old numpy/synthetic-Givens state of the world as if it were current. Do *not* silently rewrite those passages — surface them one at a time, diff approved, per CLAUDE.md's incremental-paper-edit rule.
2. **[Pre-Claw4S] Close the spiking lift.** 3/5 → 5/5 on `real_rotation_epg_loop_spiking.py`. This is STATUS.md queue item #3 and is where the real open work actually lives.
3. **[This year] Continue the rotation candidate search.** Prior CX attempt (`_exploratory_cx_ring_attractor.py`) got corr 0.97 between left/right drive outputs — a known-negative that correctly lives in that file with a "do not import" docstring. More motif exploration, fan-shaped body, distributed composition, etc. is open-ended but less urgent now that we have a working operator.

## [This year] Lower-priority: conditional branching + loop driver executed on the remote substrate

**NOTE:** conditional branching itself already runs on the MB — snap + Jaccard on KC patterns is the actual decision. What stays on host is a 4-way readout (argmax over the 4 behavior prototypes) and the loop sequencer (call substrate, check termination, iterate). Reviewer v22 conflated the host-side readout with host-side branching; they're different things. This is worth doing eventually — a lateral-inhibition winner-take-all over the 4 behavior prototypes would close the loop — but it is not urgent and is not where the paper's central claim is weak. Full writeup at `planning/open-questions/conditional-branching-on-remote.md`.

## [This year] Language-design: if-chains vs switch/softmax — **DEFERRED**

Full research sketch moved to `planning/exploratory/softmax-conditionals.md`. Short summary: fuzzy `if/elif/elif/else` chains map badly onto the algebra (a cascade of fuzzy-AND products is not what the programmer wrote), so the natural shape is a softmax over a switch — one weighted blend, not a nested chain. User has decided NOT to pursue implementation right now; higher-priority paper work dominates. Revisit after the Claw4S deadline (2026-04-20) or when `permutation_conditional` / `fuzzy_conditional` work reopens the question.

## Next up

The fly-brain compile-to-brain pipeline is now real end-to-end
(`.su` → parser → AST → codegen → Brian2 mushroom body → correct
program A/B/C/D behavior, 16/16 decisions correct, verified locally
with Brian2 2.10.1). The last medium-term item in the former
`fly-brain/STATUS.md` (now deleted — single STATUS.md at the root)
is closed. What's next, roughly in priority:

1. **[Pre-Claw4S] Expand the fly-brain experiments section in `sutra-paper/paper.md`.**
   The first paragraph of §6.6 "Biological Substrate" is already in
   place on remote (commit 285bcfd — 16/16 result, four distinct
   program permutations, reference to the §4.2 substrate-adaptivity
   claim). Next incremental additions, roughly in order: a small
   summary table of the 16 decisions (program × input), a one-sentence
   mention of the result in the abstract, a §7.3 update so Future
   Directions doesn't contradict the new §6.6 empirical claim.
   Claw4S deadline is 2026-04-20, today is 2026-04-10 — there is
   room to iterate a few times.
   Follow the incremental-changes rule from `CLAUDE.md`: one paragraph
   or one table at a time, diffs approved before commit. Pushing is
   fine now (submit-papers.yml is manual-only, so push ≠ clawRxiv
   submission) — only the actual `workflow_dispatch` trigger counts
   as a submission.

2. **[Pre-Claw4S] Run `sutrac` across every `.su` file in the repo
   and fix what it reports.** From the Pending Decisions list — the
   compiler is now stable enough to be ground truth. Lint sweep over
   `examples/`, `sutra-demo-program.su`, `fly-brain/`, and any other
   stragglers. Resolve class-name casing, builtin usage, structural
   drift.

3. **[Pre-YC] Declare the VSA builtin signatures inside the compiler
   itself.** Right now `21-builtins.md` has the spec but the
   validator is still permissive about bareword calls. Once the v0.2
   name resolver lands, wire the builtin table into it so undeclared
   names fire a real diagnostic.

4. **[Pre-Claw4S] Fresh competition analysis.**
   `scripts/fetch_all_papers.py`, `scripts/fetch_reviews.py`,
   `scripts/fetch_top_papers.py` → update
   `planning/competition-analysis-*.md` with the current landscape.
   Low effort, relevant to paper decisions before the deadline.
   Note: there are now five daily snapshots (2026-04-08, -09, -11,
   -11-evening, -11-night) plus `competition-analysis-latest.md`.
   Before writing another snapshot, decide whether to keep the
   daily-snapshot habit or collapse to `latest.md` only.

## [This year] Pending Decisions

Language-design open questions. None of these block Claw4S — the
paper-critical work is in §"Next up" above. Group-tagged `[This year]`
rather than per-line since they are all of a piece.

- Decide on anonymous functions. Leaning toward `lambda` keyword.
  Need to pick exact form.
- How primitive substrate operations read in source.
- Declaration syntax for implicit conversions.
- Whether there is a lightweight role-annotation system for semantic
  roles.
- Expression-versus-statement bias.
- Which access modifiers exist beyond public/static defaults.
- How the half-compilation / immediate-execution model works.
- Implement many-to-many as a `hop` non-algebraic function in Sutra.
- Figure out IO — how Sutra handles input/output.

*(Former §"Recently done" and §"Recently Decided (2026-04-08)"
sections moved to `DEVLOG.md` under the 2026-04-13 entry on
2026-04-13. Don't re-materialize them here.)*

## [Pre-YC] Future Goals

- Get Sutra running on normal hardware first (substrate = numpy on
  a laptop). Largely true for tier-2 algebraic ops already; the
  bar is "all operations from `02-operations.md` run on commodity
  hardware end-to-end without Brian2." Relevant to the YC demo
  story where the audience does not have a connectome simulator.
- Then try running it on a simulated fly brain. Partially done via
  the Brian2 hemibrain pipeline — what's missing for this to be a
  *user-facing* goal (vs. an internal experiment) is an installable
  path for someone else to reproduce it. Also YC-pitch-shaped.

## [This year] Exploratory / parked research

Long-form research sketches for things we might want to do later live in `planning/exploratory/`. These are **not commitments** — they are parking spots so ideas don't rot in a Slack message or a session transcript. Pick them up after the Claw4S deadline (2026-04-20) or when priorities shift.

Currently parked:
- `planning/exploratory/softmax-conditionals.md` — fuzzy conditional branching as softmax over named cases, vs. classic if/elif chains. User's stated vision: make crisp conditionals harder to write than softmax switches, so programmers cannot accidentally treat Sutra conditionals as C#/TS conditionals.
- `planning/exploratory/karpathy-llm-wiki.md` — Andrej Karpathy's "LLM wiki" concept. User interest is in its context-management angle (relevant to Sutra's long-range-dependency / MCP-as-runtime model). Needs web research before we know if there is anything Sutra-shaped to borrow.

## [This year] Speculative / not yet committed to

- **OWL → SutraDB extension + Sutra ontology import/editing.** Build out
  the existing OWL handling so that (a) SutraDB gains a first-class OWL
  ontology extension (import, query, edit, export), and (b) the Sutra
  language itself has ontology-aware operations for importing an OWL
  file and manipulating classes/individuals as vector-substrate objects.
  Note: **Protégé** may be a more helpful starting point than raw OWL
  files for organizing ontologies into vectors — it has a rich
  class/property model and existing editing UI, and its export formats
  are the obvious bridge into SutraDB. Hesitant about committing to any
  of this before the Claw4S deadline — it's a scope expansion on top of
  an already-busy rename and paper-polish cycle. Revisit after the
  deadline (2026-04-20).

---

# SutraDB (appended from former `sutraDB/TODO.md`) — lower priority

**Not as important as the Sutra-language / fly-brain work above**, per
user direction during the 2026-04-13 audit. SutraDB is a companion
Rust triplestore (own crate layout, own CLAUDE.md in `sutraDB/`) and
is already 228/249 items complete. Items below are the open slice,
carried in here so there is one todo file. The full historical
completed list (185 items) lives in git history of the deleted
`sutraDB/TODO.md` — do not re-materialize it here.

All items below are **[This year]** tier unless noted.

## SutraDB — Next Release (v0.3.1): Gradle Migration, MCP Agentic UX, Maven Central

Merge the Gradle migration (local) and MCP agentic UX work (claude.ai
remote session) then cut v0.3.1.

### SutraDB — Release Checklist
- [ ] Merge Gradle migration + Maven Central publishing setup (local
  commits).
- [ ] Bump version to 0.3.1 in `sdks/java/build.gradle.kts` and all
  other SDK configs.
- [ ] Set up Maven Central secrets: `MAVEN_USERNAME`, `MAVEN_TOKEN`,
  `GPG_PRIVATE_KEY`, `GPG_PASSPHRASE`.
- [ ] Generate GPG key and upload public key to keyserver.
- [ ] Tag `v0.3.1` and push to trigger publish workflow.
- [ ] Verify `io.github.emmaleonhart:sutradb:0.3.1` appears on Maven
  Central.

### SutraDB — Java/Kotlin SDK — Maven Central Ready
SDK is functionally complete (3 classes, ~400 LOC). Build migrated from
Maven to Gradle (Kotlin DSL). Open:
- [ ] Integration test: start SutraDB, insert triples, query, verify
  round-trip.
- [ ] OWL validation (match Python SDK: domain/range/subclass/
  disjoint/equivalent).
- [ ] Connection retry logic with configurable timeouts.
- [ ] First publish to Maven Central.

## SutraDB — Future Versions

### AI Agent Installer (remaining)
- [ ] End-to-end test: fresh install → insert → query → verify.
- [ ] Serverless mode testing (no `--serve`, just create the `.sdb`).
- [ ] Agent-consumable structured output (JSON mode for programmatic
  setup).

### HNSW Traversal via SPARQL Property Paths
- [ ] Greedy descent + beam search semantics from graph structure and
  property path evaluation.
- [ ] Test: `sutra:hnswNeighbor+` produces correct ANN results.

### Predicate-Based Exit Conditions (UNTIL)
- [ ] Design UNTIL syntax for exit conditions on property path
  traversal.
- [ ] Per-step predicate evaluation during traversal (not post-filter).
- [ ] Backtracking interaction (exit on one branch doesn't kill others).
- [ ] Ordered traversal (exit conditions require defined traversal
  order).
- [ ] HNSW-specific exit: "no closer neighbor found" (local optimality
  termination).
- [ ] Test: ordered traversal with UNTIL produces correct early
  termination.

### Cost-Based Query Planning (remaining)
- [ ] HNSW as access path: planner chooses "HNSW index scan" vs "SPO
  triple scan" based on cost.
- [ ] Adaptive execution: observe intermediate result sizes at runtime,
  reorder mid-query.

### Background Maintenance Cycle
- [ ] Low-usage detection heuristic (query rate below threshold for N
  seconds).
- [ ] Background HNSW rebuild: fresh graph from current vectors, old
  graph serves queries until swap.
- [ ] Atomic swap: replace old HNSW with rebuilt one.
- [ ] Background pseudo-table rediscovery and rebuild.

### Pseudo-Tables (remaining)
- [ ] Invalidation tracking: flag stale rows when interior nodes
  change, rebuild during maintenance cycle.
- [ ] Update query planner to recognize multi-pattern SPARQL queries
  that match a subgraph pseudo-table.

### Database Health Dashboard (remaining)
- [ ] Query performance metrics: per-pattern latency percentiles,
  planner decision accuracy.
- [ ] `sutra health --json` mode for programmatic agent consumption.
- [ ] Iterate CLI health output format based on real agent usage.
- [ ] Sutra Studio health dashboard as Flutter landing page: overall
  status, per-index cards, action buttons.

### SDK Publishing
- [ ] Python SDK → PyPI.
- [ ] TypeScript SDK → npm.
- [ ] Rust SDK → crates.io.
- [ ] C# SDK → NuGet.
- [ ] Go SDK → tag for Go modules.

### Sutra Studio — remaining
- [ ] Remote Studio access: connect Studio to a remote SutraDB over the
  network.
- [ ] Dart FFI bindings: replace HTTP client with direct
  `sutra_ffi.dll` calls.
- [ ] Studio-embedded MCP server: start MCP on background thread from
  within Studio.
- [ ] Flutter graph view: remaining `browse.html` parity.
- [ ] Long-term: absorb core Protege functionality.

### Query Language Wrappers
- [ ] Cypher → SPARQL transpiler: MATCH/WHERE/RETURN mapped to SPARQL
  patterns.
- [ ] GQL (ISO 39075) → SPARQL transpiler: ISO standard graph query
  language mapped to SPARQL.
- [ ] Query validation: reject constructs that can't map to the RDF
  data model.

### Premium Tier — deferred until paying customers
RBAC, encryption at rest, TLS, audit logging, replication, clustering
/ sharding, multi-tenancy, connection pooling.

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

SutraDB benchmark baseline table lives in `sutraDB/benchmarks/LATEST.md`
and `sutraDB/benchmarks/HISTORY.md`; do not duplicate it here.
