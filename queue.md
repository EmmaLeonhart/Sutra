# Sutra — Work Queue

**This file is a queue, not a state snapshot.** It is the **persistent
task list across sessions**. Claude loads items from here into the
task tool (`TaskCreate`) at session start, works through them, and
**removes completed items from this file** as they finish. Finished
work lives in `git log` and `planning/findings/`; this file is only
the *pending* work.

See CLAUDE.md §"queue.md and the task tool" for the full workflow.

The work here is **making Sutra the language actually work** — the
compiler, the spec, the substrate-backed runtime, the demo programs.
**The last queue item, after the language works, is writing the
paper and shipping it** (Claw4S workshop + NeurIPS + a follow-up
workshop, with a CI/CD pipeline). The question each queue item
answers is: *what does it take to make this language a real thing
someone can use, and then publish?*

Longer-horizon items (pre-Anthropic-grant-app, pre-YC-pitch, this-
year) live in `todo.md`. Items in this file are the ones Claude should
pick up next.

## Queued work — top of queue (work through in order)

### 1. Program-level completion flag propagation

`AXIS_LOOP_DONE` is set on the loop's local result vector but
doesn't propagate through layers to the program's final output.
Today the call-site writeback grabs `_loopret_x` (the state value)
and stores it back into the caller's slot var, dropping the
`_loopret_halt` (the completion flag) on the floor. So the program
returns a normal-looking value even if a loop didn't converge.

Emma's design: every loop's halt_cum should multiply through to the
program's final output via element-wise multiply (since halt_cum ∈
[0, 1]). If any loop in the call chain didn't complete, the program
emits a near-zero (detectably wiped) output rather than a partial
result.

Concrete shape:
- Each loop call accumulates its halt_cum into a function-scope
  `_program_halt` variable.
- At each function's `return <expr>`, multiply the return value by
  `_program_halt`.
- For nested loops, the inner halt_cum gets multiplied into the
  outer's, and so on up to main's return.

This is medium-scope codegen work. Tests: programs with reachable
loops return correct values; programs with unreachable loops
(impossible condition) return wiped outputs.

## Queued work — middle of queue

### 2. SutraDB integration as the default vector backend

Emma 2026-04-30: "we should be using SutraDB with `nomic-embed-text`.
... SutraDB and runtime are small enough that we can reasonably embed
it in what we make. ... Particularly for hash mapping and stuff, it's
probably better to do this than to rely on the arg max thing.
Especially in the future, for larger files, it should probably be the
default, the default thing that we compile with."

So this isn't just "use SutraDB for tests" — it's **make SutraDB the
default vector backend that every compiled Sutra program embeds and
queries.** The host-Python `argmax_cosine` / `snap` / hashmap-lookup
loops get replaced with SutraDB queries.

Concrete shape:
- **Embedded mode** (`.sdb` file like SQLite, no daemon). Each
  compiled Sutra program opens its own `.sdb` at module init and
  queries it inline.
- **`nomic-embed-text` is the embedding model** (already CLAUDE.md
  default). MxBai/MiniLM are the comparison substrates for
  cross-substrate experiments, but compiled programs default to
  nomic.
- **Hashmap (`hashmap_set` / `hashmap_get`) routes through SutraDB**
  too — instead of bind/bundle accumulator with bit-identical-key
  lookup, store key-value pairs as triples in SutraDB and query by
  vector similarity. Soft lookup falls out for free (HNSW is
  approximate-nearest-neighbor).
- **`argmax_cosine` / `snap`** become SutraDB nearest-neighbor
  queries. The "loop over candidates" violation dissolves: SutraDB
  does the work in Rust + HNSW.

Implementation pieces (rough sequencing):
1. Embed SutraDB CLI / FFI binding into the runtime so compiled
   modules can query a `.sdb` without a separate process.
2. Codegen: at module init, open a `.sdb` populated with the
   program's known vectors (codebook, role rotations, etc.).
3. Replace `argmax_cosine` / `snap` runtime methods with SutraDB
   nearest-neighbor queries.
4. Replace `hashmap_*` runtime methods with SutraDB triple
   insert/query.
5. `atman.toml` `[vector_db]` section to override defaults
   (nomic-embed-text, sdb file path, HNSW params).

This is bigger than the rest of the queue items combined. Will
likely need its own design doc + plan when the slot at the front
of the queue rolls around to it. Worth flagging as "default for
larger files in the future" — small programs may stay on the
in-process bind/bundle/argmax path during the transition.

### 3. make_random_rotation pre-warm at compile time

Today, the first call to `bind` for each role triggers
`make_random_rotation` (numpy random + QR + Givens construction).
Cache-hit path is fine; cache-miss is host Python.

Fix: scan all role names used in the program at compile time, emit
a pre-warm block at the top of the generated module that constructs
all role rotations up front. Runtime then only ever hits the cached
matmul.

Verify with a test that runs a compiled program twice with timing
and asserts the second run has zero rotation construction.

## Queued work — back of queue (boundary leaks; "Python is just IO" target)

### 4. Remaining boundary leaks

The 5 boundary leaks were enumerated in `planning/findings/
2026-04-30-substrate-purity-leak-enumeration.md` and **three of
five were fixed in commit 93beb01** (loop halt check, slot_load,
array_get). New `_VSA.truth_axis` / `_VSA.heaviside` /
`_VSA.saturate_unit` substrate primitives mirror across both the
numpy and PyTorch backends. Two leaks remain:

- **Rotation cache lookup** (`if key not in self._rot_cache`) —
  covered by item 3 (compile-time pre-warm). After pre-warm, the
  lookup is always a hit and can be replaced with a direct
  attribute access at compile time.
- **Loop tick counter** (`for _t in range(50)`) — covered by item 5
  (full unroll). Cosmetic for substrate-purity since the substrate
  sees the same T cell evaluations either way; matters for
  `torch.compile` fusion.

Both remaining leaks are bigger refactors and are tracked under
their own queue items (3 and 5).

### 5. "Python is just IO" target — three pieces

Emma's framing: ideally the Python wrapper does *only* IO/console
shell work; everything else runs as one big tensor-op graph.
Distance is small but non-zero:

- **Full unroll**: replace the `for _t in range(50)` in each loop
  function with T inline tensor-op calls. Substrate sees the same
  graph; emitted source has no Python loops at all. Mostly cosmetic
  but useful for `torch.compile` to fully fuse.
- **No `.item()` / `bool()` at the boundary**: see item 5 above.
  Same fix.
- **`torch.compile` the whole module**: once items 5+6 land, the
  emitted module is a pure tensor-op graph and torch.compile can
  trace + fuse the whole thing into a single CUDA kernel (or a few).

These are the "make Python wrapper genuinely just IO" pieces. After
they land, the wrapper is module load + `_VSA` instance setup +
`main()` call + return value to console — nothing else.

## Queued work — pre-paper consolidation

### 6. Retire the numpy backend; consolidate to PyTorch-only

Today's repo has TWO codegen backends — `codegen.py` (`_NumpyVSA`,
numpy ndarrays + Ollama, used by tests) and `codegen_pytorch.py`
(`_TorchVSA`, torch tensors + Ollama, used by `--emit` and `--run`).
Per CLAUDE.md and the project memory: **PyTorch is Sutra's compiler
library — one codegen target.** The dual-backend state is a
historical drift that needs to land before the paper claims a single
substrate-pure compile target.

**Plan:**
1. Move literal-lowering hooks (`_char_literal_src`,
   `_embed_expr_src`, `_bool_literal_src`, `_logical_op_src`,
   `_logical_not_src`, `_fuzzy_literal_init_src`) out of
   `codegen.py:Codegen` and into either `codegen_base.py:BaseCodegen`
   or directly into `codegen_pytorch.py:PyTorchCodegen`.
2. Make `PyTorchCodegen` extend `BaseCodegen` directly, not
   `Codegen`.
3. Retire `codegen.py` (delete or move to `planning/_archived/`).
4. Switch tests in `sdk/sutra-compiler/tests/` to compile via the
   PyTorch backend. Probably means installing torch in the test env;
   verify CPU-only torch works for the test corpus.
5. CLI: drop the dispatch-by-flag and always emit PyTorch.
6. Update CLAUDE.md, README, queue.md, devlog with the
   "single codegen target" framing.

**Risk:** torch on CPU is slower than numpy for the test corpus.
Verify the suite still finishes in reasonable time after the switch.
If it's catastrophic, plug `torch.set_num_threads` or similar.

### 7. Loop tail-call surface — SHIPPED 2026-04-30 (commit b3bc0cd)

`return NAME(args)` is now an alternative to `pass values` inside
loop function bodies. Same semantics; both surfaces work. Per Emma
2026-04-30, the original "closure-loop" chat framing was a
misnomer — what shipped is just the prettier tail-call surface, no
closure machinery. Design doc:
`planning/open-questions/loop-tail-call-surface.md`. Object
encapsulation deferred to todo.md.

## Queued work — final item (paper + submission pipeline)

### 8. Paper draft, three submission targets, and CI/CD pipeline

After items 1-5 land and the language works end-to-end on real
programs, the last queue item is **writing the paper and shipping
it**. Three submission targets (Emma 2026-04-30):

1. **Claw4S workshop** — the AI-workshops conference / preprint
   server pair (`clawRxiv`). Repo had a substantial Claw4S submission
   pipeline before the Sutra rebrand; that infrastructure should be
   recoverable from git history (commits like `b353ff3 exploratory:
   Claw4S paper draft on Sutra as compile-time VSA`, `f09a3f2
   Complete documentation overhaul + SKILL.md for Claw4S submission`,
   `1b73781 Reorganize repo for two Claw4S 2026 papers`).
2. **NeurIPS** — main conference, double-blind. Emma's read 2026-04-30
   is the current pipeline already follows NeurIPS rules properly,
   but verify before submitting.
3. **A second workshop after NeurIPS** — TBD which one; identify
   during 6a.

#### Sub-items, in rough order

**6a. Audit submission rules for all three targets first.** Read
current Claw4S, NeurIPS, and the post-NeurIPS workshop author guides;
capture in a findings doc:
- Page limit + format per target (LaTeX templates).
- Anonymization rules (double-blind for NeurIPS at minimum).
- Supplementary material rules.
- Reproducibility checklist requirements.
- Deadlines: abstract registration, full submission, camera-ready.

Output: `planning/findings/YYYY-MM-DD-paper-submission-rules.md`.
This document is what the CI/CD pipeline gets built against.

**6b. Recover Claw4S infrastructure from git history.** The repo
previously had Claw4S submission pipeline files, an SKILL.md, paper
drafts, and CI plumbing — all removed during the Sutra rebrand
(see `903308e Remove papers, submission CI, and Claw4S strategic
layer`). The dev log dive (queued separately) will surface what's
recoverable; restore selectively rather than reinventing.

**6c. Write the paper itself.** Substance, not yet plumbing:
- The narrative arc per `project_sutra_paper_real_scope.md`:
  displacements in frozen embedding spaces → consolidate into rotation
  binding → learned matrices as the natural extension. Sign-flip is at
  most a side note; the headline is learned-matrix (semantic) binding.
- Empirical foundation from `latent-space-cartography` (sibling repo
  — verify numbers against source, do not quote from memory).
- The Sutra language as the realization of the program: a programming
  language whose primitives are the operations that fall out of the
  embedding-space analysis.
- Substrate-purity story: every operation runs as tensor ops on the
  substrate; no host-Python compute; the compiler is the safety
  boundary because the runtime has no error channel by mechanism.
- Demo programs (`hello world`, `fuzzy_dispatch`, `role_filler_record`,
  the loop demos) as worked examples.

This is the work-product itself, not infrastructure. Likely lives in
a new `paper/` directory at repo root with `paper.tex` + `paper.bib`
+ figures.

**6d. CI/CD pipeline — single source, four outputs.** From the same
LaTeX/Markdown source, the pipeline produces:
1. **HTML on the docs site** (`sutralang.dev`) — for casual readers
   and AI-agent consumers.
2. **Downloadable PDF on the website** — full version with author
   names, links, acknowledgments.
3. **Anonymized PDF on the website** — author names stripped, repo
   URLs anonymized, third-person self-references. This is the version
   that goes to NeurIPS double-blind review. (Why on the website too?
   So reviewers who find the paper outside the OpenReview portal land
   on the same anonymized version they're supposed to be reviewing.)
4. **Claw4S / clawRxiv upload** — Claw4S workshop submission +
   preprint mirror. The previous repo had a working push-to-clawRxiv
   action; recover it (per 6b).

Pipeline shape (rough): GitHub Actions workflow on push to
`paper/` triggers two LaTeX builds (full + anonymized via `\if`
macros), uploads the PDFs as workflow artifacts, deploys both PDFs
+ rendered HTML to the docs site, and (optionally, on a tag) pushes
to the preprint server's API.

**6e. Anonymization macros.** A single-source approach uses LaTeX
conditionals to swap in/out the deanonymizing pieces:
```latex
\ifanon
  \author{Anonymous Authors}
  \newcommand{\repo}{[anonymized repository]}
\else
  \author{Emma Leonhart}
  \newcommand{\repo}{\url{https://github.com/...}}
\fi
```
Build flag (`-DANON=1`) flips between modes. Avoids the trap of
forking two paper sources that drift from each other.

**6f. Reproducibility submission.** NeurIPS reproducibility
checklist will require pointing at runnable code. The Sutra repo
itself is the answer; the submission references it (anonymized in
6e via `\repo`) and includes a `paper/REPRODUCE.md` with
"clone, install, run these commands, get these numbers."

#### Why this is at the end, not the start

The paper claims things about the language. The language has to
actually do those things first. Items 1-5 are the language being
*real* (substrate-pure, complete RNN compilation, no boundary
leaks, default vector backend). Item 6 is the language being
*defended* in print. Doing 6 first would mean writing a paper about
aspirational software, which is the failure mode the
safety-critical preamble in CLAUDE.md exists to prevent.

#### Likely scope

This item is bigger than items 1-5 combined. Will need its own
plan + several findings docs (NeurIPS rules audit, paper outline
review, pipeline design) when it rolls to the front of the queue.

## Queued work — flagged but not blocking

### Repo bloat sweep — flagged item

**Flagged for user decision:** local `fly-brain/` working copy is
**101 MB** as of 2026-04-29. Gitignored (`.gitignore` line 39),
canonical copy at `C:\Users\Immanuelle\flybrain\` outside the
repo. Worth confirming whether the local mirror is actively
needed or whether it can be reclaimed.

## Deferred (see `todo.md`)

These are real commitments but not "next active session" work. Kept
here as pointers so they don't fall off the radar:

- **`main(embedding_space: string)` compile-time override.** Partial
  progress: file-level (`// @embedding`) and project-level
  (`atman.toml` `[project.embedding]`) substrate declarations both
  land in the harness 2026-04-22. The third layer — declaring the
  substrate from inside `.su` source itself — is a compile-time
  concern (not runtime as earlier framed) and sequenced post-
  Anthropic-grant-app per user direction 2026-04-23. Full scope
  in `todo.md`.
- **Learned-matrix binding** (pre-Anthropic-grant-app): `role X =
  learned_from(data)` fits a matrix at compile time; `bind` for
  semantic roles becomes `R @ filler`. Deferred from 2026-04-22 per
  user priority. Full spec in `todo.md` and
  `planning/sutra-spec/binding.md` §"Semantic binding".
- **MLP-backed Monte-Carlo attractor search** (pre-Anthropic-grant-
  app, not today): train an MLP as an attractor function over the
  codebook, run Monte-Carlo trajectories from `v0 = king - man +
  woman` into the learned basins, compare attractor quality across
  substrates. Full details in `todo.md`.
- **Exception channel unification.** `AXIS_LOOP_DONE = 4` is the
  first instance of a broader pattern: reserved synthetic axes
  flagging "this output is suspect" conditions (divide-by-zero,
  log of zero, NaN propagation, future user-defined try/catch).
  Should be unified into one shared exception-flags sub-block.
  Sketched in
  `planning/findings/2026-04-30-rnn-loop-architecture.md` § "Unify
  with the broader exception channel".

## Pinned semantic corrections (I keep dropping these)

1. **`loop(N)` literal N unrolls at compile time. Zero runtime
   iteration.** The four function-declaration loop kinds (`do_while`,
   `while_loop`, `iterative_loop`, `foreach_loop`) are the runtime
   data-dependent forms.
2. **No loop counters live on the host at runtime.** The "counter"
   for substrate iteration IS the soft-mask cumulative halt in a
   fixed-T tensor-op unroll. The `for _t in range(50)` in the
   emitted Python is meta-iteration, not a runtime counter — the
   substrate sees T inline cell evaluations regardless.
3. **Rotation runs in the synthetic subspace, not on connectome
   weights.** Real FlyWire weight matrices do not function as
   rotation operators (they're compressive projections). Synthetic
   Givens rotations on the dedicated subspace are what the language
   compiles to today.
4. **Semantic roles are learned matrices; semantic `bind` is
   `R @ filler`.** Not random vectors (HRR), not sign-flip. A
   *semantic* role is a matrix fit to the substrate.
   See `planning/sutra-spec/binding.md` §"Semantic binding".
   **Implementation status: deferred.**
5. **Sutra has two binding kinds: semantic (learned-matrix) and
   rotation.** Rotation binding works today; semantic binding is
   deferred.
6. **Sign-flip binding is retired** (from the codegen as of
   2026-04-22). Rotation is the current `bind` implementation.
7. **Truth is designed as a canonical axis in the synthetic
   subspace.** `synthetic[AXIS_TRUTH=2]`.
8. **PyTorch is the compiler's runtime target.** `codegen_pytorch.py`
   emits torch modules picking CUDA at module init.
9. **Defuzzification polarizes, never binarizes.** `is_true` and
   `defuzzify` keep the result fuzzy and differentiable. No commit
   primitive exists; `select` does all branching. Don't reintroduce
   `gate`.
10. **`bool` is a subclass of `fuzzy`, not crisp.**
11. **Sutra's "arrays" are binding-based, not heap-allocated.** A
    binding-array is a substrate vector with `arr[0] = length` and
    `arr[1..length] = elements`. Built on `array_from_literal` /
    `array_length` / `array_get` runtime methods (shipped 2026-04-30).
12. **Canonical synthetic axis allocation:** `synthetic[0]=AXIS_REAL`,
    `[1]=AXIS_IMAG`, `[2]=AXIS_TRUTH`, `[3]=AXIS_CHAR_FLAG`,
    `[4]=AXIS_LOOP_DONE`, `[5+]=SLOT_BASE` (47 disjoint 2D Givens
    slots at default `synthetic_dim=100`).
13. **Loops are first-class declared functions** (Emma 2026-04-30).
    `<kind> NAME(condition_or_array_or_count, type state, ...) { body; pass values; }`.
    Body uses `pass <exprs>` (tail-recursive yield, one expr per
    state param; `replace` keyword keeps an input value). Call site
    is `loop NAME(...)` and mutates caller variables by reference.
    Loop functions have NO outer-scope access — pure functions over
    their declared parameters only. The four kinds: `do_while` (body
    runs once + while-style continuation), `while_loop` (body skipped
    if cond false at start), `iterative_loop` (runs N times; body
    sees `iterator` keyword), `foreach_loop` (walks binding-array;
    body sees `element` keyword). Substrate execution: T fixed cell
    steps with soft-halt sigmoid + monotone cumulative + soft-mux
    freeze. AXIS_LOOP_DONE marks completion.
14. **Idiomatic-loop cleanup is queued for later this year.** Today's
    by-reference call shape is acknowledged non-idiomatic; the
    cleanup direction (return tuples, no by-ref mutation) is in
    `todo.md` § "Make loops idiomatic." Don't touch the design
    until a few real programs have exercised the by-ref form.

## Pointers

- Longer-horizon agenda: `todo.md`.
- Deprecated spec (read-only reference): `planning/sutra-spec-deprecated/`.
- New spec dir + meta-failure note: `planning/sutra-spec/README.md`.
- Findings (dated): `planning/findings/`.
- Open design questions: `planning/open-questions/`.
- Hardwired assumptions in the demo path: `examples/todo.md`.
