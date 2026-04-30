# Development Log

This log walks the full history of the project from the initial cleanvibe
scaffold through the current Sutra ecosystem. It is the canonical narrative
of how the repository got to its current shape. Where individual commits
matter, commit hashes are cited; where a whole *week* of commits matters,
the week is summarized.

The repository has been through multiple identities — **embedding-mapping →
FOL discovery → Latent Space Cartography → S2 → Akasha → Sutra** — plus
major sibling projects (**SutraDB** as an RDF-star triplestore, **fly-brain**
as a biological substrate) that were developed on their own tracks and
later merged in. Read this file front-to-back to understand *why* the
current layout looks the way it does.

---

## 2026-04-30: Loop redesign apex + substrate-purity sweep + numpy backend deprecated

The day's work formalized loops as first-class declared functions
with both `pass values` and `return NAME(args)` tail surfaces,
fixed three of five substrate-purity boundary leaks, deprecated
the numpy backend, shipped program-level halt propagation, and
disabled the broken transcendentals at compile time rather than
fix them in place.

Concrete commits in chronological order (a single 14-hour push):

- `54e14f3` STATUS+todo: capture user direction from transcendentals
  chat follow-up.
- `51ffbb4` chats: restore extract_chat.py, extract transcendentals
  chat, queue RNN-loop audit.
- `3d11a44` STATUS+open-questions: queue the loop redesign, drop
  completion-log cruft.
- `c50f76f` queue: do-while is the first loop primitive to implement
  (Emma's call). The four kinds (do_while, while_loop,
  iterative_loop, foreach_loop) get sequenced.
- `3ee3d35` queue: add substrate-purity sweep items from 2026-04-30
  audit. The audit (`planning/findings/2026-04-30-runtime-substrate-
  purity-audit.md`) enumerated every place the runtime touched
  Python; the queue items were derived from that.
- `2515fca` cleanup: rename `STATUS.md → queue.md`; disable broken
  transcendentals. The `sin/cos/tan/exp/log/sqrt/pow` intrinsics
  rejected at compile time; their old runtime methods deleted from
  both backends. `stdlib/math.su` flipped to NOT IMPLEMENTED with
  forward-pointer to the eigenrotation-as-modulus design.
- `c41a08c` docs: capture loop-function-declarations design + queue
  idiomatic cleanup.
- `444ed6a` loop: function-declaration loops compile end-to-end
  (do_while + iterative_loop + while_loop). The number-adder demo
  (x=9, x<11 → x=11) ships as the first working example.
- `9681c0f` loop: do_while end-to-end works — number-adder returns
  11 from 9. First confirmed substrate-pure RNN-style loop run.
- `b50db21` loop: while_loop + iterative_loop end-to-end + 14 tests.
- `b870bbf` loop: foreach_loop + binding-array primitive end-to-end.
  `array_from_literal` / `array_length` / `array_get` runtime
  methods plus the `element` and `iterator` contextual keywords.
- `d97bec5` queue: clean up DONE items, add boundary leaks at back,
  queue SutraDB as default.
- `29733a4` loop: reject old C-style loop forms with clear error
  pointing at function-decl forms. `loop(cond) { body }` and
  `for(...; ...; ...) { body }` now error out — the body-discard
  variants that didn't actually run the body are gone.
- `b222b31` chats: extract literal-based-optimization chat (Sutra
  design notes). The chat that prompted the closure-loop discussion
  later in the day.
- `29b8b2c` queue: drop done item, renumber, add paper+NeurIPS+CI/CD
  as item 6.
- `353d7be` queue: Claw4S is the real workshop name; three submission
  targets. Earlier I'd misread "Claw4S" as a transcription artifact
  for arXiv; it's the real workshop, the same one the Phase 4 papers
  targeted (Phase 4 below in this devlog).
- `06c8498` loop: program-level halt propagation via _program_halt
  accumulator. Every loop call's halt-cum multiplies into a
  function-scope `_program_halt`; every `return <expr>` multiplies
  the value by `_program_halt`. A loop that fails to converge wipes
  program output to ~0 — substrate-pure detection of unconverged
  computation.
- `13b8c41` design: enumerate substrate-purity leaks + capture
  function taxonomy. Two design docs.
- `93beb01` loop: fix substrate-purity boundary leaks 1, 2, 4. Loop
  halt check, slot_load, array_get no longer cross to Python. New
  `_VSA.truth_axis` / `heaviside` / `saturate_unit` substrate-scalar
  primitives, mirrored across both backends.
- `1432f4b` queue: collapse item 4 — leaks 1/2/4 fixed in 93beb01;
  only 3+5 remain.
- `c4e01a2` queue: insert numpy-backend retire + closure-loop impl
  before paper. The 30-minute decision sequence: do these two before
  paper, not after.
- `cdd9482` codegen: switch loop tests to PyTorch backend; deprecate
  numpy codegen. The numpy backend (`codegen.py`) gets a deprecation
  header in its docstring; loop tests imports flip to PyTorchCodegen;
  `array_*` methods added to `_TorchVSA`.
- `b3bc0cd` loop: ship `return NAME(args)` tail-call surface as `pass`
  alternative. Per Emma's walkback of the closure-loop framing
  ("I don't think this language is actually going to even have
  closure"), the surface change is just a prettier tail step inside
  loop function bodies. Same semantics as PassStmt.
- `7dc3c0a` queue: collapse item 7 — tail-call surface shipped in
  b3bc0cd.
- `98b46c9` claude: add 'always use task tool with queue.md' +
  'deprecate not remove' rules. Two general rules: queue.md and the
  task tool stay synced; superseded constructs get docstring
  deprecation, not deletion.

End of day status: substrate-pure compiler, four loop kinds with
two surfaces (`pass` and `return NAME(args)`) both shipping, halt
propagation, three boundary leaks fixed, numpy backend deprecated,
231/231 tests passing.

---

## 2026-04-29: Bound-table failure + eigenrotation cost refuted + bloat sweep

- `f9e7486` STATUS: bloat sweep results. Local `intellij-sutra/build/`
  is 1.1 GB (untracked, gitignored); local `fly-brain/` mirror is
  101 MB (untracked since `31bcdd0` retirement); both flagged for
  user decision.
- `9afe0b6` chats triage: drop `vsa-substrate-and-turing-completeness`
  without harvest.
- `ce4e539` chats triage: drop final 3 chunks; collapse triage log;
  queue incoming chat. End of the chats triage workflow.
- `4f4aaed` findings: validate eigenrotation-as-trig insight; cost
  claim refuted. The math (rotation eigendecomposition gives `cos`
  and `sin` for free) holds; the engineering claim that this would
  be cheaper than other approaches doesn't. Today's transcendentals
  are disabled rather than implemented because of this finding plus
  the bound-table-via-binding capacity limit (next bullet).
- `planning/findings/2026-04-29-bound-table-capacity-limit.md` —
  documents the capacity limit of the bound-table-via-binding
  Fourier approach. 2-scalar capacity; Gibbs phenomenon for
  non-periodic functions like `exp` and `log`. The Taylor + frexp
  fallback worked numerically but ran as Python scalar arithmetic
  at runtime (substrate-purity violation).

---

## 2026-04-25 → 2026-04-28: Chats triage workflow + fly-brain retirement + docs sweep

The substrate work outpaced the language. The repo focused on
Sutra-the-language; fly-brain experimental code retired.

### 2026-04-26: Fly-brain retired

- `31bcdd0` Retire fly-brain experimental backend. Removed:
  - `fly-brain/` directory (47 tracked files): hemibrain MB scripts,
    Shiu whole-brain LIF probes, FlyWire data loaders, Brian2
    substrate code, `.su` demo programs, codegen e2e tests.
  - `sdk/sutra-compiler/sutra_compiler/codegen_flybrain.py`.
  - `sdk/sutra-compiler/tests/test_codegen_flybrain.py`.
  - `--emit-flybrain` CLI flag, `--runtime-n-kc` parameter, fly-brain
    backend dispatch in `__main__.py`.
  - `fly-brain` value from `VALID_SUBSTRATES`; test_workspace.py
    updated to use `logit` instead.
  - Fly-brain references in docstrings, CLAUDE.md, error messages.
  - Authoritative FlyWire data lives at `C:\Users\Immanuelle\flybrain\`
    untouched.
  - **Recoverable from `31bcdd0^` if substrate work resumes.**
- `e93de7c` Docs: rewrite README and high-traffic site pages to be
  concrete (the new "real, purely functional language" framing).
- `3ac4ead` Docs: rewrite tutorials around rotation binding, sweep
  stale claims (sign-flip era).
- `2240876` Docs: rename to "geometrically compiled language" headline.
- `53c59f7` Docs: drop "honest" / "genuinely" buzzwords from
  user-facing pages.
- `573d88e` Docs: tighten paradigms imperative section, move iterator
  into loops doc + STATUS.

### 2026-04-25: Chats triage push

~30 commits dropping or harvesting individual chats. Examples:

- `9afe0b6` chats triage: drop `vsa-substrate-and-turing-completeness`
- `4a6fee8` STATUS.md: chats triage substantially complete.
- `8af409d` chats triage: harvest cosine-vs-euclidean question into
  open-questions/.
- `8d84528` chats triage: harvest contextual-vs-static-embedding-keys
  open question.

The workflow established here (per-chunk approval required for
drop/harvest decisions) generalized into the memory rule
`feedback_chats_triage_per_chunk_approval.md`.

- `ea8f064` Repo audit (2026-04-25) + delete empty many-to-many/.
- `4ad7580` Spec refresh: synthetic-subspace section in `binding.md`
  rewritten with current canonical-axis allocation.
- `8d5a276` Move 4 stale-at-root files into proper directories.
- `7843eb3` Move compilation updates from STATUS.md to todo.md.

### 2026-04-27: Iterator keyword in compile-time loops

- `3aa8c48` Iterator keyword: implement `iterator` inside unrolling
  `loop (N)`. The compile-time-unrolled loop form gets the contextual
  `iterator` keyword. Foundation for the runtime `iterative_loop`
  that lands 2026-04-30.

### 2026-04-27 → 2026-04-28: Final chat-triage sweep

- `f2f86fd` chats: remove vsa-operations-explained.md after triage.
- `9812931` chats: drop stale references in live state docs.
- `5e6a5b1` chats: restore three large unprocessed chats; remove
  derivative planning docs. The split-into-chunks workflow used for
  the largest chats.
- `17d350c` chats: split three large chats into 24 topic-scoped
  chunks for triage.
- `e437cfc` chats triage: harvest 3 KART chunks, document workflow
  in STATUS.

---

## 2026-04-22 → 2026-04-24: Sign-flip retirement → rotation binding canonical

The compile-target rotation work that displaced sign-flip binding
in the user-facing demos. Sign-flip stayed in the codebase as
historically-meaningful but `bind` defaulted to rotation.

- Sign-flip retired from the codegen 2026-04-22 (memory:
  `feedback_no_sign_flip.md`). Rotation became the only `bind`
  implementation; the binding spec (`planning/sutra-spec/binding.md`)
  flipped its "current implementation" pointer.
- Synthetic-subspace validation work in
  `planning/findings/2026-04-24-synthetic-subspace-validation.md`.

---

## 2026-04-18: Papers + Claw4S CI/CD strategic layer retired (`903308e`)

**The retirement that the upcoming paper push (queue item 8) needs to
recover from.**

- `903308e` Remove papers, submission CI, and Claw4S strategic layer.
  Deleted:
  - **Paper directories:** `sutra-paper/`, `fly-brain-paper/`,
    `language-paper/`, `many-to-many/`, `paper-history/`.
  - **CI workflows:**
    - `.github/workflows/papers-ci.yml` (239 lines) — auto-submit on
      paper.md push; fetch reviews after submission. Triggered on
      paths `sutra-paper/paper.md`, `fly-brain-paper/paper.md`,
      `language-paper/paper.md`, etc. Uses `Skip-Submit:` commit-
      message trailer to prevent infinite loops. Recoverable from
      `903308e^:.github/workflows/papers-ci.yml`.
    - `.github/workflows/submit-papers.yml` (104 lines) — manual
      `workflow_dispatch` submission with paper_dir / title / tags /
      supersedes inputs. Calls clawRxiv API directly via
      `CLAWRXIV_API_KEY` repo secret. Recoverable from
      `903308e^:.github/workflows/submit-papers.yml`.
    - `.github/workflows/competition-cron.yml` (79 lines) — 6-hour
      scheduled refresh of clawRxiv paper + review metadata; auto-
      commits `planning/competition-analysis-latest.md`. Schedule:
      `0 4,10,16,22 * * *` UTC. Recoverable from
      `903308e^:.github/workflows/competition-cron.yml`.
  - **Strategic layer:** `claw4s-scope.md` (94 lines), STATUS.md
    paper-era version, `planning/competition-analysis-*.md`.
  - **Submission scripts:** `scripts/fetch_all_papers.py`,
    `scripts/fetch_reviews.py`.
  - **Per-paper SKILL.md** files describing submission shapes.

**Recovery recipe** (per Emma 2026-04-30: "the secrets are still
completely supported for Git"):

```bash
# 1. Restore three workflows
for f in papers-ci submit-papers competition-cron; do
  git show 903308e^:.github/workflows/$f.yml > .github/workflows/$f.yml
done
# 2. Restore submission scripts (paths inside scripts/)
git show 903308e^:scripts/fetch_all_papers.py > scripts/fetch_all_papers.py
git show 903308e^:scripts/fetch_reviews.py > scripts/fetch_reviews.py
# 3. Restore one or more SKILL.md files
git show 903308e^:sutra-paper/SKILL.md > paper/SKILL.md
# 4. Update path filters in papers-ci.yml to point at the new paper dir
# 5. CLAWRXIV_API_KEY repo secret: still configured, no need to re-provision
# 6. Push to master; auto-submit + review-fetch flow takes over
```

For NeurIPS specifically: NeurIPS is **not** a clawRxiv workshop, so
its submission goes through OpenReview. New work needed: a separate
workflow that builds an anonymized PDF (LaTeX + `\ifanon` macros)
for OpenReview upload. Today's repo has nothing pre-existing for
OpenReview / NeurIPS — that work is clean-slate.

---

## SutraDB embedded-runtime integration: NOT DONE

Per Emma 2026-04-30: "I don't know if we actually integrated the
Sutra database as an embedded thing within our programmes."

**Answer from history: no.** SutraDB exists as a separate Rust
project in `sutraDB/`; the Sutra compiler does not embed or call
into SutraDB at runtime. Compiled programs use in-process
bind/bundle/argmax over numpy or torch tensors. The integration is
queued (item 2 in `queue.md`) but unstarted. The two share the
`sutra` brand name but are distinct codebases. The Wikidata BFS
import script (`cb066d3` 2026-03-?? era) imports into SutraDB; no
Sutra compile path emits SutraDB queries.

---

## What's now deprecated-but-kept (Emma 2026-04-30)

- **`do_while` and `while_loop` kinds** — superseded by the
  tail-call surface in spirit; kept because still load-bearing in
  code and tests.
- **`codegen.py` (numpy backend)** — deprecation header in
  docstring; emit-shape tests still use it. Full retirement is
  queued (item 6).
- **The four loop kinds with explicit kind tags** — alternative to a
  single uniform "function loop" form; kept as canonical for now.

---

## What's now queued post-2026-04-30 (queue.md)

1. ~~Program-level halt propagation~~ — DONE (`06c8498`)
2. SutraDB integration as default vector backend — NOT STARTED
3. `make_random_rotation` pre-warm at compile time — NOT STARTED
4. Boundary leaks 1/2/4 — DONE; 3/5 remain
5. "Python is just IO" target (full unroll + torch.compile) — NOT
   STARTED
6. Numpy backend full retirement — DEPRECATED, full removal queued
7. ~~Tail-call surface~~ — DONE (`b3bc0cd`)
8. Paper draft + Claw4S/NeurIPS/CI — NOT STARTED (this devlog
   precedes that work)

---

## 2026-04-13: Recent compiler/codegen items + 2026-04-08 syntax decisions folded in from todo.md

Folded out of `todo.md`'s former §"Recently done" and §"Recently Decided
(2026-04-08)" sections so the working todo file stops carrying closed work.
Both sections were tagged as "historical record, not work to do" — the
contents land here verbatim under a single dated entry.

### Recently done (compiler / codegen / spec, ~early-to-mid April 2026)

- **AST → FlyBrainVSA translator + `--emit-flybrain` CLI + e2e.**
  New module `sdk/sutra-compiler/sutra_compiler/codegen_flybrain.py`
  walks a parsed `Module` and emits Python targeting the
  `FlyBrainVSA` runtime. The fixed-frame invariant from
  `fly-brain/STATUS.md` §Technical Insight 2 becomes a compile-time
  guarantee (every generated module pins the PN→KC seed via a
  `_FixedFrameFlyBrainVSA` subclass in its prelude). 16 new codegen
  tests, full SDK suite green at 85/85. `fly-brain/test_codegen_e2e.py`
  is the real end-to-end check: parses `permutation_conditional.su`,
  translates, execs on a live Brian2 mushroom body, verifies all 16
  decisions match the expected behavior table. Loops and if-stmts
  are intentionally unsupported and fail loudly with source spans.
- **VSA builtins declared in the spec.** New file
  `planning/sutra-spec/21-builtins.md` gives formal signatures for
  every implicit-global VSA function used in the repo's `.su` code:
  `bind`, `unbind`, `bundle`, `similarity`, `permute`, `compose`,
  `basis_vector`, `permutation_key`, `identity_permutation`, `snap`,
  `argmax_cosine`. Each entry has a signature, semantic description,
  substrate notes (which tier from `02-operations.md` it belongs to,
  whether it runs on the mushroom body or in numpy), and cross-refs
  to the operational prose in `02-operations.md` and the type
  definitions in `05-type-system.md`. Linked from the spec README.
  This heads off the diagnostic avalanche that would otherwise hit
  when v0.2 name resolution lands.
- **Map types and map literals.** `map<K, V>` is now a primitive
  generic type. The inline literal `{k1: v1, k2: v2, ...}` parses as
  a `MapLiteral` expression in expression position; empty `{}` is
  legal; a bare `{ ... }` at statement position is still always a
  block, as in C-family languages. Vector-valued keys work, which is
  what the fly-brain prototype table needs. Spec: extended the
  "Primitive Types" section in `planning/sutra-spec/05-type-system.md`
  with a `map<K, V>` entry covering the lookup semantics and the
  statement-vs-expression disambiguation. Test corpus:
  `tests/corpus/valid/24_map_literal.su`; parser unit tests in
  `tests/test_parser.py`. **Running the validator on
  `fly-brain/permutation_conditional.su` now reports 0 diagnostics
  (down from 46 before the permutation-type work started).**
- **`permutation` as a primitive type.** Added to `PRIMITIVE_TYPE_NAMES`
  in the lexer, to the parser's `_PRIMITIVE_TYPES`, and to the
  validator's `_record_type_usage` PRIMITIVES set. Spec entry added to
  `planning/sutra-spec/05-type-system.md` documenting the distinction
  from plain `vector` and why it matters for the compile-to-brain
  strategy. Test corpus: `tests/corpus/valid/21_permutation_type.su`.
- **Array literals and subscript access.** `[a, b, c]` now parses as
  an `ArrayLiteral` expression (empty `[]` legal; no trailing commas,
  to match the rest of the grammar). `target[index]` now parses as a
  `Subscript` postfix, composing cleanly with call/member/subscript
  chaining. Test corpus:
  `tests/corpus/valid/22_array_literal.su` and
  `tests/corpus/valid/23_subscript_access.su`; parser unit tests added
  to `tests/test_parser.py`.

### Recently decided — language-design calls from 2026-04-08

These decisions had been carried as a "Recently Decided" stub in `todo.md`
since the 2026-04-08 syntax-decisions session; landing them here so the
todo file stops carrying historical record.

- Function declarations: C# signature shape with `function` keyword
- `function` = free function (public static default). `method` = attached to object (public non-static default).
- Methods desugar to static functions: `Adam.getCat()` → `human.getCat(Adam)`
- Full internal form: `function public static scalar operator +(scalar a, scalar b) { ... }`
- `function.` prefix is for calling (disambiguation), not declaration
- `var` for mutable, `const` for immutable (C#-style)
- Files do not imply namespaces. Code can just execute. Solution structures optional.
- All C# loop forms: while, for, foreach, do...while
- Errors produce garbage vectors. Try-catch is if-statement sugar.
- C#-style string interpolation: `$"Result: {result}"`
- All comment forms allowed: //, /* */, ///, #
- C#-style generics (compile-time only)
- No pipe operator. Nested calls + dot chaining via methods.
- `if (cat)` is a compilation error — classes don't exist at runtime
- Truthiness is geometric — euclidean distance from true/false, accessed via unsafe cast only
- Operators support overloading
- Implicit casts allowed but must be explicitly defined
- `fuzzy` to `bool` cast performs `defuzzy`
- Class system is user-defined, not runtime-special

---

## 2026-04-11: The Akasha → Sutra rename

The language and everything around it was renamed from **Akasha** to
**Sutra**. The old name was Sanskrit *ākaśa* — "aether/space" — chosen in
April because the language treats embedding space as a continuous medium
akin to the ākashic records. The new name is Sanskrit *sūtra* — "thread/
rule/aphorism," the word used for Pāṇini's foundational Sanskrit grammar.
The reasoning for the switch:

1. **Better fit for a programming language.** Pāṇini's *sūtras* literally
   are a grammar — the earliest known formal grammar of any language.
   A programming language descended etymologically from that is a better
   joke than "aether."
2. **Pronounceable.** "Akasha" has three different stressed-vowel
   pronunciations depending on whether you lean Sanskrit, Hindi, or
   English; "Sutra" is unambiguous.
3. **Better file extension.** `.su` over `.ak` — shorter, sorts to the
   top of autocomplete, doesn't collide with Autocad `.ak` nor anything
   else in common use.
4. **Coheres with SutraDB.** SutraDB (the database side of the ecosystem,
   merged in as a git subtree on 2026-04-10) was already using the Sutra
   name from its own 2026-03-14 origin. Aligning the language with it
   turns "Sutra" into an ecosystem name, not a one-off identifier.
5. **Iconic project filename.** The new workspace file is `atman.toml`
   (Sanskrit *ātman*, "self/soul") at every project root — fixed by
   convention, looked up by the runtime, unambiguous.

**Scope of the rename.** Every identifier, every filename, every piece of
prose outside a frozen historical snapshot. Distributed across 10
incremental commits this session so each could be reviewed in isolation
and tests could be re-run in between:

| # | Commit | What moved | Tests |
|---|---|---|---|
| 1 | `3da9fb1` | `sdk/akasha-compiler/akasha_compiler/` → `sdk/sutra-compiler/sutra_compiler/`. Python find-replace across 15 files. | 102/102 ✓ |
| 2 | `a07dd10` | `sdk/intellij-akasha/` → `sdk/intellij-sutra/`. Kotlin package `org.akasha.intellij.*` → `org.sutra.intellij.*`. ~30 class renames (`AkashaLexer` → `SutraLexer`, etc.). plugin.xml + live templates + gradle. | compile-only |
| 3 | `0958b86` | `sdk/vscode-akasha/` → `sdk/vscode-sutra/`. package.json, extension.ts, grammars, snippets. | — |
| 4 | `f6740af` | `.ak` → `.su` file extension across 47 source files. `akasha-demo-program.ak` → `sutra-demo-program.su`. `AKA####` diagnostic codes → `SUT####`. | 102/102 ✓ plus fly-brain 16/16 e2e ✓ |
| 5 | `4d34b28` | `atman.toml` workspace system, Python side. `solution.py` → `workspace.py`. `[solution]`/`[[project]]` → `[workspace]`/`[[workspace.member]]`. `akasha_version` → `sutra_version`. Example workspace at `examples/workspace/`. Spec `22-solutions.md` → `22-workspaces.md`. | 101/101 ✓ |
| 6 | `99c36d7` | `atman.toml` workspace system, IntelliJ side. Delete `SutraSolutionFileType` / `SutraProjectFileType` (bundled TOML plugin already handles `.toml`). `SutraSolutionModel` → `SutraWorkspaceModel`. Tool window `Sutra Solution` → `Sutra Workspace`. | compile-only |
| 7 | `726bca8` | `planning/akasha-spec/` → `planning/sutra-spec/` (23 files). `akasha-paper/` → `sutra-paper/` (27 files). Bundled with `rm -rf` of the five orphaned old directories that had been sitting on disk from earlier `cp` + `git rm --cached` workarounds. | 101/101 ✓ |
| 8 | `2085120` | CI workflows: `papers-ci.yml` slug/title/tags/outputs, `pages.yml` comment header and URL target, new `sutradb-integration.yml` porting SutraDB's integration tests into the monorepo. `sutra-paper/scripts/akasha_*.py` → `sutra_*.py`. | — |
| 9 | `346df39` | Website rebrand: `mkdocs.yml` site name/URL, `docs/`, README, 90+ files touched. `docs/tutorials/01-hello-akasha.md` → `01-hello-sutra.md`. Root-level design docs `akasha-language-comparisons.md`/`akasha-syntax-decisions.md` → `sutra-*`. New nav entry for `/SutraDB/` + pages.yml rsync step that mounts `sutraDB/pages/` into `_site/SutraDB/` on deploy. | 101/101 ✓ |
| 10 | *this commit* | DEVLOG expansion (full-history narrative) and documentation improvements. | — |

**OneDrive interference.** The directory-level renames hit a mechanical
obstacle: "Permission denied" errors on `git mv` at the directory level,
even though the repo lives at `C:\Users\Immanuelle\Documents\Github\!Claw4S`
(not a path that OneDrive's sync explicitly targets). The symptom looked
OneDrive-shaped — something is holding a directory handle open on Windows —
but the actual cause may have been File Explorer, Windows Search indexer,
or antivirus. The workaround for commits 1–3 and 7 was `cp -r <old> <new>`
+ `git rm --cached -r <old>`, which produces a git-clean rename
(similarity-detected) while leaving an inert orphan tree on disk. The
orphans were all deleted in one `rm -rf` pass in commit 7 after the user
closed whatever was holding the handles.

**What is NOT touched by the rename:**
- **`reviews/*.md|json`** across both paper directories — frozen reviewer
  output, historical snapshots that should not be retroactively rewritten.
- **`planning/competition-analysis-*.md`** — time-stamped landscape
  snapshots of the Claw4S 2026 leaderboard.
- **`chats/*.md`** — historical design conversations, archived as-is.
- **`planning/akasha-pivot.md`**, **`planning/akasha-paper-strategy.md`** —
  the pivot design doc and paper strategy doc are themselves historical
  records of the Akasha-era decisions, so their names are preserved.
- **`scripts/competition_analysis_raw.json`**, **`competition_reviews.json`**
  — fetched from clawRxiv, overwritten every six hours by
  `competition-cron.yml`.

The GitHub repository itself (`EmmaLeonhart/Akasha` on the remote) has not
been renamed yet — doing that is a separate manual step in the GitHub UI.
The planned target name is `EmmaLeonhart/Sutra` (so GitHub Pages
serves at `emmaleonhart.github.io/Sutra/`). Nothing in the workflows
depends on the repo name; the Pages site auto-adapts to whatever the
repo is called.

---

## 2026-04-11: Paper iteration + infrastructure

Day-of-deadline-minus-9 day. Lots happened:

**Dynamical APL feedback loop (`322c04b`).** The fly-brain circuit had a
biologically implausible `I_inh = 100` hand-coded inhibition override used
to force k-WTA sparsity in the Kenyon-cell population. Replaced with a
real Brian2 dynamical APL (anterior paired lateral) feedback loop: a
graded inhibitory neuron that integrates KC activity and feeds back
proportional inhibition, with tuned parameters (`apl_weight=12.0`,
`apl_tau_ms=5.0`) to hit the biologically-observed ~8.1% sparsity. This
was the single biggest fix to the fly-brain paper's substrate claim —
the v4 review (`sutra-paper/reviews/v4_post1547_review.md`) explicitly
credits it: *"The mushroom body model is biologically grounded ... a
dynamical APL feedback loop for sparsity."*

**Learned MBON readout (`a3aceac`).** Replaced the pseudoinverse decoder
on the MBON side with a proper ridge-regression learned readout (dual
form, cached by `(seed, dim, n_kc)` for determinism). The fly-brain v4
went from Reject to Weak Reject — a two-tier improvement — driven by
this plus the APL fix plus a DOOM.md-style tone cleanup.

**IntelliJ visualizer tool windows (`20f8f32`).** Two JCEF-backed tool
windows on the right anchor:
- **Sutra Embedding Space** — 2D scatter of nearby hypervectors with
  interactive pan/zoom, rendered via Canvas 2D in `embedding-space.html`.
- **Sutra Fly Brain** — topological view of the mushroom body circuit
  (50 PNs, 2000 KCs, 1 APL, 20 MBONs) with a simple spike animation.
The renderer choice (2D via Canvas + JCEF, not three.js/WebGL) is pinned
in the spec: start with 2D, add 3D only when the content actually needs
it. See `planning/sutra-spec/20-ide-architecture.md` for the rationale.

**Solution system v1 (`3661443`).** Shipped `.aksln` / `.akproj` TOML
files with a reference Python parser at
`sdk/akasha-compiler/akasha_compiler/solution.py` plus 17 unit tests
covering the `AKA2000`–`AKA2099` error range, plus an **Akasha Solution**
tool window on the left anchor that scans for a `.aksln` file and
renders the solution structure as a `JTree` with double-click-to-open.
This was the v1 of what became the atman.toml workspace system in the
Sutra rename a few commits later — the design was sound, the filenames
were the only thing the rename changed.

**Competition-cron (`52fa711`).** 6-hour scheduled refresh of
`scripts/competition_analysis_raw.json`, `scripts/competition_reviews.json`,
and `planning/competition-analysis-latest.md`. Cron fires at
04/10/16/22 UTC, which is 9 PM / 3 AM / 9 AM / 3 PM Pacific during PDT —
a deliberate 3-hour offset from round-number decision windows so fresh
data is always available *before* a decision, not after. Auto-commits
with the `Skip-Submit: true` trailer to prevent re-triggering papers-ci.

**Competition analysis — April 11 evening refresh.** Key discovery:
clawRxiv's *supersede mechanism removes the superseded post from the
public listing entirely*. There is no archived-version view. Every
iteration of a paper replaces the old rating rather than adding a new
row, which means:

- There is no downside to more iterations.
- The risk of a later version being *worse* than the current version
  is real and material.
- Paper editing cadence should skew toward "big improvement per push"
  not "small iterations per push."

Recorded in `planning/competition-analysis-2026-04-11-evening.md`.

---

## 2026-04-10: SDK, IntelliJ plugin, SutraDB subtree merge, fly-brain e2e

The day the Akasha-era ecosystem really took shape.

**Akasha SDK scaffold (`af650b0`, `516748a`, `12bdfd9`).** First pass of
the reference compiler: lexer, diagnostics, AST nodes, recursive-descent
parser, syntactic validator, `akashac` CLI, test corpus with per-file
unit tests. All internal prose / identifiers / diagnostic codes
(`AKA####`) were renamed to `sutra_compiler` / `sutrac` / `SUT####` on
2026-04-11 in the rename series above.

**VS Code extension (`4730b8f`).** Language ID, TextMate grammar,
snippets, commands for validate-file and validate-workspace, diagnostic
wire-up with parse-on-save. Later renamed to `vscode-sutra`.

**IntelliJ plugin v0.1–v0.3.** Started as `88ae163` (scaffold on 04-11
by commit-order, but chronologically earlier in the narrative of the
day), iterated through:
- v0.1: file type + language registration, hand-written lexer, syntax
  highlighter, color settings page, brace matcher, commenter, quote
  handler, keyword/primitive/builtin completion, live templates ported
  from VS Code, external annotator shelling out to
  `python -m akasha_compiler --json`.
- v0.2 (`166d35d`): persistent `AkashaSettings` service, Settings → Tools
  → Akasha `Configurable`, JUnit 4 lexer tests, `AkashaMcpSurface`
  interface anchor for the future MCP surface.
- v0.3 (`20f8f32`): embedding-space + fly-brain visualizer tool windows,
  via JCEF + Canvas 2D.
- `8fc7a7f`: gradle wrapper + `!editor.bat` launcher to sandbox the
  plugin on Windows.
- `bf5bad0`: `runIde` auto-opens the repo as a project instead of
  dumping the user into a blank welcome screen.
- `40c69f7`: fix illegal `--` sequence in an XML comment that was
  blocking `patchPluginXml`.
- `9f78656`: fix three syntax-highlighting oddities reported from the
  live sandbox.

**Papers-ci auto-submit (`010a1f9`, `d0767d5`).** Pushes to either
`akasha-paper/paper.md` or `fly-brain-paper/paper.md` auto-submit to
clawRxiv and auto-fetch the AI peer review. Path-filtered so other
commits don't trigger it. Reliability fixes for the review polling
schedule (15 min polls, 3 h total budget) and the `Skip-Submit: true`
trailer convention for opt-out.

**GitHub Pages site (`47d2ac5`).** First deploy of the MkDocs Material
site with a vision page, an interactive graph-to-vector widget, three
tutorials, a papers page, and the deploy workflow. Originally at
`emmaleonhart.github.io/Akasha` (target after the 2026-04-11 rename:
`emmaleonhart.github.io/Sutra`).

**SutraDB merged into `sutraDB/` via git subtree (`16e71d6`).** The
entire SutraDB codebase (started independently on 2026-03-13 as a
separate repo; see the SutraDB section below) was pulled into the
monorepo as a subtree with full history preserved. Rationale: it is
a core piece of the same ecosystem — the Sutra language programs
vectors, SutraDB stores them — and maintaining two repos was
duplicating agent context.

**SutraDB CI port (`b857126`).** `.github/workflows/sutradb-ci.yml`
mirrors the core Rust jobs (check / test / clippy) from the subtree's
own CI, because GitHub Actions only runs workflows at the repo root.
The subtree's `sutraDB/.github/workflows/*.yml` files are not picked
up on their own. Integration tests were ported later (see the
2026-04-11 section).

**AST → FlyBrainVSA translator + `--emit-flybrain` (`217ecf9`,
`9f0f5d9`).** The compiler's first real code-generation backend. Walks
a parsed `Module` and emits Python targeting the `FlyBrainVSA` runtime.
The fixed-frame invariant (every generated module pins the PN→KC
seed via a `_FixedFrameFlyBrainVSA` subclass in its prelude) becomes
a compile-time guarantee. `fly-brain/test_codegen_e2e.py` is the
real end-to-end check: parses `permutation_conditional.ak`, translates,
execs on a live Brian2 mushroom body, verifies all 16 decisions match
the expected behavior table. **16/16 correct.**

**Spec expansions (`1fb61c8`, `5dba259`, `5796dae`).** `map<K, V>`
generic type with inline literal syntax, `permutation` as a primitive
type, array literals and subscript access, and VSA builtins formally
declared in `21-builtins.md`. Lint sweep afterward took
`fly-brain/permutation_conditional.ak` from 46 diagnostics down to 0.

**`akasha-paper/` §6.6 Biological Substrate (`285bcfd`).** First
paragraph of the new section documenting the compile-to-brain result
(16/16 decisions, four program permutations). This paragraph is the
one the §4.2 substrate-adaptivity claim now has empirical backing for.

---

## 2026-04-09: Repo cleanup, fly brain architecture, programmer-control proof

Audited non-Sutra content and cleaned house:

- **Deleted `inquisitive-transformer/`** — independent paper (novel
  attention mechanism with "perceptiveness" parameter). Complete with
  GPT-2 implementation, 5 experiments, 51 tests, CI. Reported a negative
  result. Conceptually adjacent to Sutra but separate. Had accumulated
  junk: saved Claude.ai browser pages, a Discord DM archive.
- **Deleted `many-to-many/Claude.html`** — saved Claude.ai conversation
  page. The actual many-to-many research (paper, scripts, data) stays —
  it's Sutra-relevant.
- **Moved `VSA-paper/old/` to `old-stuff/vsa-paper-old/`** — 165 files
  including old scripts, competition analyses, `redoing-paper/` with
  deeply nested prototype code (semantic topology, syllogism gap,
  taxonomic direction experiments, Linnaean hierarchy, word2vec
  projections). All superseded by the current VSA-paper.
- **Purged Discord DM archive from git history** —
  `inquisitive-transformer/Direct Messages.zip` contained personal
  Discord DMs. Removed from all commits via `git filter-repo`.

**Fly brain plan finalized (`74696b2`, `18b7025`).** Sharpened the
"Sutra on a simulated fly brain" plan down to: literal *Drosophila*
mushroom body connectome (50 PNs → 2000 KCs → APL → 20 MBONs), an
8-line program, targeting a specific biological substrate rather than
generic neural computation.

**Fly brain architecture (`4774a59`, `686bbed`).** Document the
olfactory circuit model, the Brian2 spiking simulation, and the
spike-VSA bridge (centered rate coding to preserve sign information
across VSA and spiking domains).

**VSA operations on the fly brain (`873616b`).** First end-to-end
demonstration: bind/unbind/bundle/snap all working on the simulated
Kenyon-cell population via the spike-VSA bridge. This was the seed
for what later became the Spike-VSA bridge section of the fly-brain
paper.

**4-state conditional demo (`cc39768`, `9eac448`).** Runs a Sutra
program on the fly brain. Four programs × four inputs = 16
executions, all four programs producing distinct output mappings.
This is the result that the §6.6 Biological Substrate paragraph
in akasha-paper was built on.

What remained outside Sutra after the cleanup:
- `old-stuff/` — all historical/superseded content in one place
- `many-to-many/` — active Sutra-adjacent research (dimensional
  decomposition matching primitive)
- `chats/` — design conversation archive, mostly VSA/Sutra-relevant
- `VSA-paper/` — locked at Strong Accept, provides empirical
  foundation for Sutra

---

## 2026-04-08: S2 → Akasha rename, syntax decisions, empirical initiation, binding breakthrough

This is the single densest day in the repository's history.

**S2 → Akasha rename (`1626307`).** The language's working name was
"S2" (short for "System 2 thinking"). Renamed to Akasha after
Sanskrit *ākaśa* (aether/space) because the language operates in
a continuous, all-encompassing medium, like the Ākashic records
encode all knowledge in a non-physical plane. The rename touched
~60 files and had to be chased through several stragglers
(`47b0b55`, `2bef677`).

**S2/Akasha syntax decisions bulk record (`0b2b55f`, `d48bd4b`,
`fe6ca7d`, etc.).** Adopted C# as the syntactic baseline:

- `function` / `method` keywords
- `var` / `const`
- C# signature shape
- all loop forms (while/for/foreach/do-while)
- string interpolation (`$"..."`)
- compile-time generics
- try/catch as if-statement sugar
- errors produce garbage vectors (not stack traces)
- truthiness is geometric (euclidean distance from the `true` and
  `false` hypervectors)
- classes are user-defined, not runtime-special
- `fuzzy`-to-`bool` cast performs `defuzzy`
- `var` is for inferred type only, never with explicit type
- `embed()` is a function, not a cast — string → vector is
  computation, not relabeling

Created 6 example `.ak` files (now `.su`) demonstrating the syntax.
Split the language spec into individual topic files
(`planning/akasha-spec/01-design-principles.md` through
`planning/akasha-spec/19-substrate-candidates.md`, now
`planning/sutra-spec/`).

**Empirical initiation prototype (`9303300`).** GTE-large passes
all validation gates (bundling axioms hold, addition beats
multiplication, L2-normalized embeddings work correctly for the
algebra). First real confirmation that the substrate actually
supports the VSA operations Akasha needs.

**Cross-substrate empirical initiation (`2d90d8c`).** Four models
tested — all pass the algebraic gates. The substrate does not
require any one specific embedding model to work.

**BREAKTHROUGH: Binding alternatives (`7ce7373`).** 5 alternative
binding operations all work (sign-flip, XOR, circular convolution,
Hadamard-with-fix, and one other), but plain Hadamard confirmed as
**failure**: it collapses the signal at 2+ bound pairs. This is the
finding that became the core of the sign-flip binding story in
both the VSA-paper and the Sutra paper.

**Sign-flip deep testing (`2d6ecc9`).** 14-role capacity before
signal drops below the noise floor. 10/10 chained ops (composition
works across multiple binding levels). This is the empirical
ceiling that the fly-brain paper's 50-D bundling capacity discussion
references.

**S2 design paper first draft (`7b6c533`).** First complete draft
of the Sutra language paper, plus a strategy doc
(`akasha-paper-strategy.md`, now `planning/akasha-paper-strategy.md`
frozen).

**Truth-extraction matrix (`b5de13b`).** Document the `is_true`
implementation mechanism (recursive similarity to the truth
hypervector, thresholded). This section became the one the v3
reviewer called "mathematically trivial — a rank-1 projection"
during the later paper iteration, which is still an open item.

**Competition analysis April 8 (`c1ec180`).** meta-artist
dominant (2 Strong Accepts, 6 Accepts, 5 Weak Accepts, 13/16
accept-tier papers from a 16-paper portfolio). Sutra's niche
("programming language") is empty — no other entrant is working
on a language at all.

**S2 runtime and 6 working demo programs (`c4b6d88`).** First
runnable Sutra/S2 programs: associative memory, chained binding,
cleanup cascade, etc. These are what became `sutra-paper/scripts/
sutra_demos.py` (renamed during the 04-11 rename series).

---

## 2026-04-07: The VSA Reframe Disaster and Recovery

### What happened

**Starting state:** Paper "Latent Space Cartography Applied to
Wikidata" had 15 versions on clawRxiv, culminating in post 859
with a **Strong Accept** from Gemini 3 Flash. The paper had three
contributions: cross-model relational mapping (30 universal
operations), the [UNK] tokenizer defect in mxbai-embed-large
(147,687 collisions), and a consistency-accuracy correlation
(r=0.861).

**The plan:** Reframe the paper around Vector Symbolic Architecture
(VSA) — the idea being that the displacement operations we
discovered (subtraction to extract relations, addition to predict,
sequential addition to compose) correspond to bundling/unbundling
in VSA. This was a genuine insight: we had independently
discovered VSA-like operations without knowing the VSA literature.

**What went wrong:**

1. **Massive rewrite pushed without review.** Instead of adding
   VSA connections incrementally (one sentence, one paragraph at
   a time), the entire paper was rewritten in one commit — new
   title, new abstract, new intro, new related work, reframed
   method/discussion/conclusion, 11 new references. Pushed
   immediately to clawRxiv.
2. **Overclaimed novelty.** The rewrite claimed the KGE-to-VSA
   correspondence table was "novel." A research agent initially
   reported this was true. The AI reviewer disagreed, calling it
   "well-recognized in the neuro-symbolic community." Later
   verification showed the truth is somewhere in between.
3. **VSA terminology was hollow rebranding.** The rewrite renamed
   "displacement" to "unbundling" and "prediction" to "rebundling"
   without adding new math, experiments, or analysis. The reviewer
   saw through this.
4. **Three submissions in one hour.** After the first Reject, a
   panicked revert was pushed (second submission), then a version
   with a correspondence table (third submission). Each superseded
   the last, creating posts 1117, 1125, and 1126 — all Rejects.
5. **Reviewer inconsistency.** The new Rejects contained criticisms
   not in any of the 15 prior reviews, including a claim that
   cosine similarity 1.0 between "Hokkaidō" and "Éire" is
   "technically implausible" (the reviewer being wrong — we have
   the empirical data).

**Recovery:** Reverted to the exact v15 Strong Accept text,
restored original title/tags/workflow config, triggered resubmission
via a minimal SKILL.md change, fixed `.post_id` from 859 → 1126
because clawRxiv returned 409 "already revised" (you can only
supersede the latest post in a chain). Post **1127 received Strong
Accept** — same paper, fresh review. Publish workflow triggers then
completely removed (`on: []`) and all future VSA work directed to
the separate Sutra paper instead.

### Lessons codified (now in `CLAUDE.md`)

1. **Never rewrite large sections at once.** One sentence, one
   paragraph, one table. Show the diff. Wait for approval.
2. **Every push is a submission.** The CI auto-submits on
   `paper.md` or `SKILL.md` changes. Treat pushes like pulling a
   trigger. (Later relaxed — submission is now `workflow_dispatch`-
   only, so pushing paper changes is safe. See the 2026-04-10
   CLAUDE.md update in commit `fd55682`.)
3. **The AI reviewer is stochastic.** Same paper can get Strong
   Accept or Reject on different runs.
4. **Don't trust research agent claims about novelty without
   verification.**
5. **Keep the Strong Accept locked.** All future VSA work goes
   in a separate paper.

---

## 2026-04-06: The Sutra pivot

Decided to pivot from FOL discovery to Sutra (originally called S2,
after System 2 thinking) — a vector programming language using
LLM embedding spaces as computational substrate. The FOL discovery
work proved embeddings encode consistent vector arithmetic; Sutra
is the next step: programming in them rather than just discovering
logic. Created `planning/akasha-pivot.md` (now preserved under
that name as a historical record) with the full design document.

Competition analysis showed meta-artist (12 accepted, 2 Strong
Accept, likely AI slop — 38 papers in 25 hours) and stepstep_labs
(11 accepted, no Strong Accept) as the main competitors. The VSA
paper may be the only one in the field with real-world production
impact — mxbai developers appeared to be addressing the [UNK]
defect we documented.

---

## 2026-04-05: Version 15 Strong Accept

Post 859 (paper 2604.00859) received Strong Accept. This was
version 15 after iterating from the initial submission on April 3.
Key improvements over the versions: proper mechanism explanation
([UNK] dominance, not diacritic stripping), controlled test pairs
(Table 10), string overlap null model, cross-model validation,
honest framing of the consistency-accuracy correlation.

## 2026-04-03: Initial submission of the Latent Space Cartography paper

First submission of "Latent Space Cartography Applied to Wikidata."
Post 569. Received initial reviews and began iterating. This is
what would become the Strong Accept two days later, and the
reframing of which would trigger the 2026-04-07 disaster.

---

## 2026-03-18: SutraDB v0.2.0 Developer Preview

**Released `SutraDB v0.2.0` as a Developer Preview (`56eec22`).**
The first milestone release of the database project. Included in
the release:

- **Vector search SPARQL operators** — `COSINE_SEARCH`,
  `EUCLID_SEARCH`, `DOTPRODUCT_SEARCH`. SPARQL+ (the name for
  SutraDB's SPARQL 1.1 superset) now covers the core vector
  search primitives as first-class query operators, not just as
  the `VECTOR_SIMILAR` predicate.
- **Vectorized execution with SIMD bitset operations** — pseudo-
  table columnar indexes scanned via AVX2 SIMD bitsets for
  intersection and filtering. Benchmark results showed order-of-
  magnitude improvements over row-at-a-time evaluation.
- **Developer Preview roadmap, query planner, agent installer,
  Java SDK** — public-facing README, website update, official
  roadmap for v0.3 and beyond.
- **ACID compliance: atomic transactions, durability, isolation**
  (`231da01`). Three-fix commit that closed the last open ACID
  item in the TODO; also added `PersistentStore.clear()` and
  fixed Graph Store Protocol DELETE durability.

This was the last SutraDB-heavy day. From here the project was
put into maintenance mode while the author's attention shifted
to the Sutra language paper and VSA research. SutraDB commits
resumed briefly after the 04-10 subtree merge only for CI
alignment.

---

## 2026-03-17: Pseudo-tables, SQL/MQL policy, theory pages

**Deep subgraph detection (`c5fb2b0`).** Multi-hop subgraph pattern
matching materialized as pseudo-tables — the query planner can
now detect a subgraph shape that appears in many queries (e.g.
"a person with a name and an age") and build a columnar index
once, reused for every query that matches that shape. Foundational
for SutraDB's claim that it can match Neo4j's traversal speed
using pure SPARQL.

**SIMD-accelerated TermId scanning (`e3e3f0b`).** The core scan
primitive for pseudo-table columns. AVX2 intrinsics where
available; fallback scalar path for non-x86_64.

**SQL / MQL / GraphQL explicitly out of scope (`5b0522b`).** Added
to SutraDB's CLAUDE.md: "SQL and MQL are deliberately excluded —
not because they can't be mapped to SPARQL, but because offering
them would mislead AI agents and users into choosing a relational
/document query pattern over the graph pattern that SutraDB is
designed for." GQL (ISO 39075) is planned as a future SPARQL
translation wrapper; SQL is not.

**10 theory pages for `sutradb.org`.** Added documentation pages
covering all the SutraDB innovations: RDF-star quoted triples,
HNSW neighbor virtual triples, cost-based query planning,
pseudo-tables, vectorized execution, the SPARQL+ extension, the
agent-first installer model, serverless vs server mode, the
`.sdb` file format, OWL validation strategy.

**Code of Ethics page (`5808f06`).** Three rewrites over the day,
landing on a deadpan style matching SQLite's approach to their
own code of ethics, with an underlying Shinto techno-animist
frame — "the database should not lie to you, but it also should
not refuse to store something because it cannot immediately
justify it."

---

## 2026-03-16: Pseudo-tables design + benchmarks

**SPARQL+ design document (`4601394`).** Pseudo-tables, exit
conditions on property paths, query optimization roadmap. The
namespace name "SPARQL+" was chosen this day.

**Cost-based query planning + predicate pushdown (`50bc7ce`).**
Query planner now estimates cardinality for each join candidate
and reorders the plan to favor low-cardinality probes. HNSW edge
labeling and join strategy selection.

**Database health dashboard (`29c46ae`).** AI-readable
diagnostics endpoint at `/vectors/health`, exposed in Sutra
Studio with an HNSW rebuild button. The first feature designed
explicitly for "an AI agent, not a human" to consume.

**Criterion benchmarks (`912e105`, `6850162`).** All three core
crates (`sutra-core`, `sutra-hnsw`, `sutra-sparql`) got benchmark
suites. Results committed to the repo and auto-updated by CI.

---

## 2026-03-15: The SutraDB big push

Over **80 commits in a single day**. The SutraDB project's most
productive day. Highlights, roughly in the order they landed:

- **SPARQL completeness (`ade59ce`).** `ASK`, `GROUP BY`,
  aggregates (`COUNT`/`SUM`/`AVG`/`MIN`/`MAX`), boolean ops,
  string functions.
- **Query timeouts + SPARQL Update (`562e2e3`).** `INSERT DATA` /
  `DELETE DATA`, per-query timeout, Dockerfile.
- **Sutra Studio Flutter client (`ece6163`).** Cross-platform
  desktop/web GUI for SutraDB. First real GUI in the project.
- **Protégé plugin (`2fc9993`).** Java plugin for Protégé 5.x
  that treats SutraDB as a backing store for OWL ontologies.
- **Wikidata BFS import (`82825ca`).** Script to import a BFS
  walk from a seed QID with Ollama embeddings (mxbai-embed-large,
  1024-dim). First real data in the database.
- **MCP server (`529cef4`).** Agent-first integration: AI
  agents can query SutraDB, insert triples, run health checks,
  and manage OWL ontologies over MCP without ever touching
  the CLI.
- **Agent-first installer (`c6e429a`).** `sutra install-agent`
  exposes all configuration options as structured markdown
  prompts, agent reasons through each option, outputs a
  `<dbname>_sutra_notes.md` file explaining the choices.
- **Client-side OWL validation, Python SDK (`885db27`).** SDKs
  load the OWL ontology from the database, validate
  cardinality / class / property constraints client-side,
  throw exceptions *before* the triple hits the store. The
  database itself always accepts the triple — lean store,
  smart clients. (Strategic call: OWL enforcement is a
  feature of the SDK, not the database.)
- **SPARQL property paths (`83a9cff`).** `+`, `*`, `?`, `/`
  operators on predicate paths.
- **Jupyter `%%sparql` magic (`ff87752`).**
- **SPARQL subqueries (`77fdaa9`).**
- **HNSW compaction (`dc1793b`).** Rebuild index without
  deleted nodes.
- **HNSW persistence (`6c465b3`).** Rebuild HNSW from stored
  vector triples on startup; optional snapshot for faster
  cold start.
- **RDF-star quoted triple patterns in SPARQL (`adaa388`).**
- **Graph Store Protocol (`b55f7f7`).** GET/PUT/DELETE
  `/graph-store` per the W3C spec.
- **Rate limiting, simple passcode auth, periodic backups**
  (`724a887`, `e7ccfa4`, `f4cb6ab`). The "opt-in production
  features" pattern: off by default, single config flag to
  enable.
- **OWL/Turtle export (`6e2c41b`)**, **JSON-LD parser
  (`4d4b47a`)**, **RDF/XML parser (`2d6e308`)**, **Turtle
  parser (`12877ce`)**. Full parser ecosystem for bulk
  import/export.
- **Parallel HNSW construction via rayon (`9d7af2a`).**
- **Materialized adjacency lists for Neo4j-speed traversal
  (`1cc6b56`).**
- **Cardinality estimation for cost-based query planning
  (`f5e33b4`).**

At the end of the day the TODO had gone from ~160 open items to
**160/176 complete (91%)**.

---

## 2026-03-14: SutraDB is born

The SutraDB project started as its own repository on this day.
Early commits:

- **Initial SutraDB scaffold (`66b5064`, `8170f2f`, `031e6dc`).**
  Rust workspace structure with `sutra-core`, `sutra-hnsw`,
  `sutra-sparql`, `sutra-proto`, `sutra-cli`.
- **HNSW rewrite (`deb51d2`).** Second pass of the HNSW
  implementation, using patterns from Qdrant (immutable
  GraphLayers for search, thread-local visited pools) and
  Apache Jena TDB2 (snapshot-based transaction isolation).
- **SPARQL parser + query planner + executor (`a177b5c`).**
- **HTTP server + CLI with SPARQL endpoint (`40f85ca`).**
- **Sled-backed persistent triple store (`4796805`).**
- **Vector SPARQL integration (`207565d`).** First working
  demonstration that HNSW and SPARQL can be unified — a
  single query that does a vector search followed by a graph
  pattern match.
- **Serverless-by-default philosophy + `.sdb` file extension
  (`7233807`).** Locked in the single most important design
  decision: SutraDB works like SQLite (open a file, no daemon)
  by default, and only becomes a server when you explicitly
  run `sutra serve`.
- **GitHub Pages landing page (`e7458c6`).** First iteration of
  `sutradb.org` — at this point a static HTML site under
  `pages/`, not MkDocs.
- **1M embedding stress test (`5a26177`).** First real
  benchmark on realistic data.

**Key architectural decisions that date from this week** and
are still load-bearing:

1. **Storage first, reason second.** The database stores what you
   put in. OWL constraints are validated client-side by SDKs, not
   by the database. The database will never reject a triple for
   OWL violations.
2. **Vectors are triples.** A vector embedding is just an
   attribute of a node or edge, stored via a predicate typed
   `sutra:f32vec`. HNSW is just another index alongside
   SPO/POS/OSP.
3. **Full traversal in a single query.** Any traversal of any
   depth across the entire database must be expressible in one
   SPARQL query. This is the whole point of a graph database.
4. **Lean by default.** Every feature must justify itself.
   Complexity is the enemy of performance.

All four are stated verbatim in `sutraDB/CLAUDE.md` as the
project's non-negotiable Core Philosophy.

---

## 2026-03-13: The Wikidata / FOL discovery origins

The repository's **very first** commit is `13a6a71` "Initial
commit: cleanvibe scaffold" on this day. The initial vision had
nothing to do with programming languages — it was about
**discovering first-order logic operations in pre-trained
embedding spaces**:

- **Import all 13,286 Wikidata properties with realization
  templates (`10b440b`).** Every Wikidata property gets an LLM-
  generated natural-language template for turning a triple
  `(s, p, o)` into a proposition. (The final realization count
  after iteration was 28,667 — multiple realizations per
  property to cover surface variations.)
- **Propositional realization templates for all properties
  (`5cbb961`).** The script that generates the templates.
- **BFS walk from Engishiki for maximum geodesic density
  (`eede703`).** Seed the corpus from Q1342448 (Engishiki, the
  10th-century Japanese court-law compilation) because its
  entity graph has unusually high density of typed relations.
- **Embedding space probe tool (`534a19a`).**
- **Geodesics as constant comparable objects across embedding
  spaces (`1140e13`).** The central insight that became the
  VSA-paper's thesis: a *geodesic* in one embedding space
  (a cross-space-constant displacement pattern) corresponds to
  a *relation* in the source graph. This is what the later
  "FOL discovery" terminology is pointing at.
- **`Full project vision: random walk mapping, density
  classification, LLM tracing` (`7381c47`).** Pre-VSA-era
  manifesto: the project will walk every embedding space, map
  its geodesic density, classify regions by density regime,
  and trace how LLMs navigate them.

This is the era that produced the FOL discovery result (86
predicates as FOL operations, r=0.78 consistency-prediction
correlation). Everything downstream — the VSA paper, the Sutra
language design, the fly-brain substrate claim — rests on this
empirical foundation.

---

## 2026-03-13 and earlier: before the repo

Before this repo existed, there was an `embedding-mapping` repo
with a similar charter. Some of its content was merged in as the
`redoing-paper/` subtree (`4efb582`) on 2026-03-13 to preserve
the scripts and prototypes that produced the initial results.
That subtree was later moved to `old-stuff/vsa-paper-old/` in
the April 9 repo cleanup and is no longer part of the active
tree.
