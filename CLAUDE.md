# embedding-mapping → Sutra

## ⚠️ SAFETY-CRITICAL: PEOPLE CAN DIE IF YOU FAKE RESULTS ⚠️

Sutra is the foundation for **biomedical hardware and software**. If the math is wrong or an operation fakes its substrate, **a patient downstream can be injured or killed.**

Rules:

1. **Every Sutra operation must actually run where the spec says it runs.** No host wrappers around substrate ops.
2. **Validation numbers are measurements, not targets.** If a test gives cos=0.84 and the threshold is 0.9, report 0.84, investigate, fix the physics. Do not doctor the number.
3. **"It ran without errors" is not success.** Compare decoded output to ground-truth and report the honest delta.
4. **Negative results are required.** If an approach does not work, mark it, explain why, and do not wire it downstream.
5. **If spec and implementation disagree, stop and resolve it explicitly.** Either fix the implementation or update the spec. Do not ship code that contradicts the spec.
6. **If you catch yourself taking a shortcut, say so in plain text.** Surface it — don't rationalize it.

When in doubt: **do the real operation on the real substrate, even if it's slower or uglier.**

The canonical compile target is **PyTorch on the frozen-LLM semantic subspace** (`codegen_pytorch.py`, CPU or CUDA).

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

An MCP server is a core part of the language runtime. The website (`sutralang.dev`, sourced from `docs/`) is agent-friendly by design.

## Workflow Rules
- **Commit early, often, and push immediately.** Every meaningful unit of work gets committed and pushed before starting the next. No local-only work.
- **Update `queue.md` in the same commit as the work.** If the session terminates mid-task, the next session must immediately know what's done, in-flight, and next. Stale queue.md = lost context.
- **Always use the task tool with queue.md.** Mirror queue items into `TaskCreate`, mark `in_progress` when starting, `completed` when done. Remove completed items from queue.md in the same commit. The task tool and queue.md are two views of the same list — do not let them drift.
- **Do not enter planning-only modes.** All thinking must produce files and commits.
- **Keep this file and README.md up to date.**
- **Deprecate, don't remove** unless the deprecated thing actively misleads, has no users, or is a maintenance liability.

`todo.md` is for longer-horizon work. `queue.md` is for the next active session. Items migrate from `todo.md` → `queue.md` → deleted on completion.

## Paper rules

### Always check the latest review rating before pushing paper changes

Before pushing **any** commit that touches `paper/paper.md`, `paper/paper.tex`, `paper/SKILL.md`, or `paper/REPRODUCE.md`, read the latest review file (`ls -t paper/reviews/v*_review.md | head -1`) and report its rating. If the latest rating is **Strong Accept**:

1. **Stop** — do not push automatically.
2. Surface the rating to Emma and ask before pushing.
3. The papers-ci workflow auto-submits each paper push as a new clawRxiv post in the supersede chain, and the leaderboard collapses chains to the LATEST post — so a follow-up Weak Reject will demote the chain even though the Strong Accept review file remains in git.

This rule exists because we lost the trajectory once already by pushing changes immediately after a Strong Accept landed and a noisy follow-up review knocked the leaderboard rating down.

### Locking in a Strong Accept by disabling papers-ci

Once a Strong Accept lands and Emma decides to lock it in: disable the auto-submit workflow before any further paper push.

The mechanism: edit `.github/workflows/papers-ci.yml` to either delete the file or replace its `on:` block with `workflow_dispatch:` only (manual trigger). This prevents subsequent pushes from auto-submitting and supersedes-chaining the paper. Reviews can still be fetched and committed manually via `scripts/quick_review.py` if Emma wants to test specific edits, but no automatic submission risks demoting the leaderboard.

The Strong Accept review file stays in git (`paper/reviews/v41_post2205_review.md` on 2026-05-01), and `paper/.post_id` keeps pointing at the Strong Accept post until Emma decides to push a new submission.

### No development internals in submitted text

`paper/paper.md`, `paper/paper.tex`, `paper/SKILL.md`, `paper/REPRODUCE.md` must contain no references to:
- `CLAUDE.md`, "safety preamble," or AI-tooling config files
- Internal workflow names: `papers-ci`, `pull-reviews`, `combinatorics`, `paper-pdf`, `pages.yml`
- `Skip-Submit`, `supersedes`, `dedup_token`, or other submission-management mechanisms
- Script names: `quick_review.py`, `pull_all_reviews.py`, `paper_submit_and_fetch.py`, `paper_fixes.py`
- Internal terminology: "gradient descent on the paper," "combinatorics testing," "fix function," "variant mask," "candidate mode"
- Project-management jargon: "queued," "TBD," "see CLAUDE.md," "(version N draft)"
- Internal file paths: `paper/.post_id`, `paper/candidates.jsonl`, `planning/sutra-spec/binding.md`

Before any paper edit, grep for forbidden tokens and excise them.

### No dedup-bypass markers

Do **not** add per-variant suffixes, version markers, hidden whitespace, or any artifact to title/abstract/body to bypass clawrxiv's dedup detector. This reads as bad-faith API usage and risks revoking access.

The legitimate path for multiple versions is the **supersedes/revisions chain**: each version supersedes the previous and gets its own post ID and review. After combinatorics runs, restore `paper/.post_id` to its pre-run value.

### Gradient descent: one variable at a time

Every push touching `paper/paper.md` or `paper/SKILL.md` triggers `papers-ci.yml` → clawRxiv submission → AI review committed to `paper/reviews/`. This only works as measurement if **each commit isolates one change**.

1. **One logical change per commit.** Don't bundle unrelated edits.
2. **Push immediately.** Don't batch — each commit gets pushed so CI runs and the result is attributable.
3. **Fix functions are cheap experiments.** Get a passable version, run combinatorics to measure which help, then refine winners. Don't iterate on wording until "correct" before measuring.
4. **Commit messages name the variable.** "paper: correct demo count from 3 to 13" — not "paper: misc improvements."
5. **Don't clean up the paper between combinatorics runs.** Each cleanup is an unmeasured edit.

### Assertive, not defensive on reviews

Reviewers are AI and sometimes miss things, conflate genres, or hallucinate. Hold ground on contributions the paper actually makes.

1. **Fix the obvious things.** Typos, wrong sentences, genuinely missing sections.
2. **Push back on category errors.** Sharpen framing — don't retrofit to a different genre.
3. **Don't chase scope creep.** "You should also evaluate X" = future work, not a promise.
4. **Hold the line on what the paper claims.** If the reviewer asks for evidence of *more than X*, clarify that X is the claim.

When a review lands, write a triage table (fix / pushback / out of scope) and let Emma direct which fixes to land.

### No specific dates in submitted text

Remove year/date references from submitted paper files — reviewer bots flag "2026" as hallucinated future content. Prefer "the numpy backend is deprecated" over "deprecated as of YYYY-MM-DD."

This rule applies to `paper/paper.md`, `paper/paper.tex`, `paper/SKILL.md`, `paper/REPRODUCE.md` only — not to `planning/findings/` filenames, commit messages, this CLAUDE.md, or chat transcripts.

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
- **Repo structure:** `sdk/` (compiler, plugins), `examples/` (`.su` programs), `planning/sutra-spec/` (spec), `planning/findings/` (findings), `sutraDB/` (triple store), `docs/` (MkDocs site).

## Prior work
The empirical foundation is relational-displacement analysis of frozen embedding spaces, published in [`EmmaLeonhart/latent-space-cartography`](https://github.com/EmmaLeonhart/latent-space-cartography). **Verify any specific claim against the source.** Do not quote numbers from memory — prior versions of this file contained contradictory r-values and pathology descriptions. State claims as "prior work showed displacement vectors exist in frozen embedding spaces" without specific numbers unless you've read the source.
