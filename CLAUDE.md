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

### Next venue target: NeurIPS

clawRxiv auto-submit runs on every paper edit (per the §"Paper" section below). The longer-term venue target is **NeurIPS**. Work in `todo.md` answers the question *what does this language need to be NeurIPS-ready?*

## Workflow Rules
- **Commit early, often, and push immediately.** Every meaningful unit of work gets committed and pushed before starting the next. No local-only work.
- **Update `queue.md` in the same commit as the work.** If the session terminates mid-task, the next session must immediately know what's done, in-flight, and next. Stale queue.md = lost context.
- **Always use the task tool with queue.md.** Mirror queue items into `TaskCreate`, mark `in_progress` when starting, `completed` when done. Remove completed items from queue.md in the same commit. The task tool and queue.md are two views of the same list — do not let them drift.
- **Do not enter planning-only modes.** All thinking must produce files and commits.
- **Keep this file and README.md up to date.**
- **Deprecate, don't remove** unless the deprecated thing actively misleads, has no users, or is a maintenance liability.

`todo.md` is for longer-horizon work. `queue.md` is for the next active session. Items migrate from `todo.md` → `queue.md` → deleted on completion.

## Paper

clawRxiv auto-submit is back on (restored 2026-05-01). Each push to `paper/paper.md` or `paper/SKILL.md` triggers `papers-ci.yml`, which submits to clawRxiv, polls for the AI peer review, and commits the review back under `paper/reviews/v<N>_post<ID>_review.{json,md}`. `paper/.post_id` tracks the latest post in the supersedes chain (currently `2216`, the v51 Accept). NeurIPS is the longer-term target — see `todo.md`.

Reviewer behavior: ratings can drift either direction commit-to-commit; the AI reviewer is data, not a verdict. If a Strong Accept lands, you don't need to "lock it in" by disabling submission — just keep working. The supersedes chain keeps every prior version available, and rating noise on later versions doesn't retroactively change earlier ones.

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
