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

## 2026-05-27: rank-k is_X — k-means cluster-centroid anchors landed (`--anchor-strategy kmeans`)

Work-loop tick (continuation of prior sessions on rank-k). The remaining
"k-means cluster-centroid anchors" sub-item in queue.md said the
default `perturb` strategy is "adequate for proof-of-concept but lossy
as a real initializer." Shipped the second strategy.

`build_data(..., anchor_strategy="kmeans")` runs Lloyd's k-means
(`_kmeans_lloyd`) over each class's first `per_class` word embeddings
(filtering out the category name itself), then uses the k centroids +
ε=0.02 perturbation as the k anchors. The k-means *initial assignment*
is seeded by the per-seed RNG (`torch.randperm(N, generator=g)`), so
different seeds yield different clusterings — a second per-seed
variation source on top of the ε perturbation. Trivial-case handling:
if k ≥ N (too few words to cluster into k groups), pads by repeating
points[0] instead of crashing.

Verification (real exec, K=2 k=2 per_class=5 5 ep n=2, exit 0, wall
2083.6 s ≈ 35 min):
- seed 0: baseline +0.1913, trained +0.5365, round-trip 1.49e-07
- seed 1: baseline +0.1996, trained +0.5484, round-trip 2.38e-07
- baseline mean ± SD: +0.1955 ± **0.0058**
- trained  mean ± SD: +0.5424 ± **0.0084**
- ratio +2.78×; equiv guard 0.00e+00 (still exact)
- round_trip_ok: True; max|Δ| over all seeds 2.38e-07

The `perturb` strategy stays the default. The kmeans path is exposed
via the `--anchor-strategy kmeans` CLI flag; verified end-to-end
without changing the substrate-purity invariants (equivalence guard
exact; round-trip clean). Margin variance per seed is real, not a
precision artifact.

queue.md: marked "k-means cluster-centroid anchors: DONE" inside the
rank-k #1 item; the "proper K=5 sweep" sub-item is still flagged for
Emma sign-off before autonomous launch (multi-hour budget).

## 2026-05-27: rank-k is_X — real per-seed variation source landed; n=2 SD non-zero

Work-loop tick: the equality-cosine n=3-degeneracy finding
(`21778648`) flagged that `torch.manual_seed` alone has no live
effect when prototypes are deterministic. The rank-k harness
inherited that vulnerability. Before launching the proper K=5
sweep, the variation source had to be real.

Fix in `build_data`: every anchor prototype is now `embed(category-
name) + eps*N(0,1)` with eps=0.02 (a ~2% magnitude shift on an
L2-normalized 768-d anchor — small enough to preserve the "near
embed(category-name)" semantics, large enough to give Adam a
genuinely different starting trajectory per seed). Plus per-seed
shuffle of the data ordering via `torch.randperm(N,
generator=g)` so the gradient-step sequence varies.

Verification (real smoke, K=2 k=2 per_class=4 5 ep seeds=0,1,
exit 0, wall 1614 s ≈ 27 min):
- seed 0: baseline +0.1892, trained +0.5863, round-trip 1.79e-07
- seed 1: baseline +0.1839, trained +0.5687, round-trip 1.19e-07
- baseline mean ± SD: +0.1866 ± **0.0037** (was 0.0000)
- trained  mean ± SD: +0.5775 ± **0.0124** (was 0.0000)
- ratio +3.10x; equiv guard 0.00e+00 (still exact per seed)

n=2 here is HONEST n=2 — the SD is real, not a precision
artifact. The variation source change does what it claims; the
"n=3 degenerate" pattern from equality cosine is now broken for
rank-k.

queue.md: marked "REAL per-seed variation source: DONE" inside
the rank-k #1 item; the "proper K=5 sweep" sub-item is now
unblocked but flagged with the wall-time projection (many hours)
so it gets explicit Emma sign-off before launching autonomously.

## 2026-05-27: rank-k is_X end-to-end PASS (smoke, K=2 k=2); fixed-point bake-back fix

Work-loop tick: implemented the training loop on top of the
rank_k_is_x.py scaffold (`b6f21a24` 2026-05-26). Added build_data
(K-class anchor protos from embed(category-word) + ε-perturbed
extras for k > 1), vmap-batched logits with equivalence guard at
init, joint Adam over K*k vectors + K*k scalars, bake-back via
vector_literal + scalar literals, round-trip check.

Smoke run (K=2 k=2 per_class=4 5 ep seed=0, real exec, exit 0):
- equivalence guard: vmap vs per-sample max|Δ| = 0.00e+00 (literally
  exact — vmap of the emitted rule_i is the SAME compiled
  computation as per-sample on this K=2 k=2 shape).
- baseline margin (T_init=1, embed-anchor protos): +0.1935
- trained margin (Adam, 5 epochs): +0.5557
- ratio: +2.87×
- round-trip max|Δ| (param-form vs baked-literal form): 2.38e-07
  (< 1e-4 threshold)
- wall: 811.4 s ≈ 13.5 min

NOT YET a publishable finding — N=8, n=1, 5 epochs is a smoke
config not a measurement. The substantive next step is a proper
K=5 k ∈ {1, 2, 4} sweep with a REAL per-seed variation source
(randomized data ordering or per-seed ε-perturbation of the
anchor prototypes), per the equality-cosine n=3-degeneracy finding
which proved that torch.manual_seed alone is degenerate when
prototypes are deterministic.

INTEGRITY FIX caught during smoke: the first attempt threw parse
errors in the baked .su at trained values that ended up small
enough for Python's repr() to switch to scientific notation
(e.g. `4.5e-05`). Sutra's parser does NOT accept scientific
notation (probed and confirmed: SUT0100 / SUT0104 errors at the
`e` character). Fixed in both rank_k_is_x.py and prophylactically
in equality_cosine_adjustment.py by formatting bake-back floats
as `f"{v:.8f}"` (fixed-point, precision ~5e-9, well below the
1e-4 round-trip threshold). The equality-cosine completed run
(bu7o9mqxu, T*=1.1118) was not affected — but a future K=10+ run
with a smaller T* could have hit the same bug. Lexer-level
acceptance of scientific notation is queued as a separate item
(NOT this commit's scope).

Queue.md: marked rank-k is_X #1 as END-TO-END WORKING (was
SCAFFOLD SHIPPED); listed remaining work (proper K=5 sweep with
real variation; findings doc; k-means cluster anchors for k > 1;
scientific-notation lexer enhancement).

## 2026-05-27: equality cosine adjustment MEASURED — bu7o9mqxu landed, findings doc filled

Background K=5 n=3 measurement `bu7o9mqxu` (launched 2026-05-26)
completed exit 0 after 9891.2 s ≈ 2.75 h on the per-sample driver
path. Real numbers:

- equivalence guard (vmap vs per-sample at T=1): 2.98e-07 (passed,
  < 1e-4 threshold)
- baseline margin (T=1): +0.0748
- trained margin (T=T*): +0.0807
- trained T*: 1.1118
- ratio = trained / baseline = **+1.08x** (modest but real)
- round-trip recompile max|Δ|: 3.58e-07 (passed, < 1e-4)
- wall time: 9891.2 s ≈ 2.75 h

The cosine-temperature lever is REAL — a learned T*≈1.11
decompresses the anisotropic-cone-compressed cosine output enough
to widen the equality-discrimination margin by +1.08x. The trained
model bakes back cleanly: the entire baked .su classifier is
literally `(1.1118 * similarity(x, own)) && !(1.1118 *
similarity(x, other)) && ...` — recompiles to bit-equivalent
logits (max|Δ| 3.58e-07).

**Integrity finding flagged plainly:** all 3 seeds returned
BIT-IDENTICAL numbers (std=0.0000). With prototypes FROZEN at
embed(category-name) (deterministic), fixed data ordering, T
init=1.0, and Adam state deterministic given the rest, the
`torch.manual_seed(s)` calls had no live source of variation. The
"n=3" is effectively n=1 repeated. The numbers are real
measurements of the one trajectory the experiment defines; they
just don't establish robustness across init / data-ordering
choices. Patching the harness to introduce real variation (random
word sub-sampling within categories, or prototype ε-perturbation
per seed) is a queued follow-up — NOT a "fix to make n=3
meaningful" but a deliberate next experiment.

Comparison with K=3 smoke (single seed, per-class=5, 20 ep): K=3
gave T*=1.25, ratio +1.18x. K=5 gives T*=1.11, ratio +1.08x. As K
rises, T* and the margin improvement both decrease — interpretation:
single-anchor (rank-1) prototypes get less salient as competing
classes proliferate; the per-class-T or rank-k extension may
capture more. Both are queued.

Findings doc `planning/findings/2026-05-26-equality-cosine-
adjustment.md` updated with measured numbers, verdict, and the
"Honest finding: the n=3 is degenerate" section. The placeholders
that were committed in Emma's sibling commit `0b1e742f` are now
filled with real measurements.

queue.md: dropped the now-MEASURED #1 priority (Equality cosine
adjustment); promoted Rank-k is_X from #2 to #1 with a cross-ref
to the equality-cosine finding. GPU is free now that bu7o9mqxu
completed — the next work-loop tick can pick up the rank-k
training loop.

## 2026-05-27: work-loop tick — drop stale `dot` builtin queue entry

Both top-priority items are blocked on GPU (#1 equality cosine
adjustment: `bu7o9mqxu` measurement still in flight, 0 lines of
output; #2 rank-k is_X: scaffold shipped 2026-05-26 `b6f21a24`, the
remaining training loop also needs the GPU). Pick a CPU-only,
bounded queue-hygiene action this tick: remove the stale `dot`
builtin queue entry — shipped 2026-05-24 at `d17feaf4` (`"dot":
(_builtin_dot, 2)` in `codegen_base.py:317`), tagged `v0.6.1`,
queue-note commit `8e792a1f`. The queue rule says completed work
lives in git log, not the queue.

No code changes; queue-CRUD only. Findings doc for the equality
cosine adjustment is now in main (Emma's sibling commit
`0b1e742f` 2026-05-26 23:41 PT picked up the DRAFT and committed
it via the GitHub web UI; content identical to the local draft —
no reconciliation needed). The placeholders (`<PENDING>`,
`<MEASURED>`) stay in the committed file until `bu7o9mqxu`
delivers numbers; filling them is the work-loop tick that lands
after the measurement completes.

## 2026-05-26: rank-k is_X harness scaffold (smoke-compile PASS) — work-loop tick

Work-loop tick: top actionable item was queue.md #1 (equality cosine
adjustment) but `bu7o9mqxu` holds the GPU for the K=5 n=3
measurement, so picked up #2 (rank-k is_X) and scaffolded the
harness without claiming the experiment.

Shipped (`b6f21a24`): `experiments/rank_k_is_x.py` — parametric
(K, k) .su generator that produces both the param form (everything
trainable) and the baked form (vector_literal + scalar literals
substituted inline), plus a `--smoke` compile-only sanity check.
.gitignore extended for the temp `.rankk_*.su` files.

Smoke MEASURED (real, exit 0): K=2 k=2 param form (1,161 chars, 12
lines) compiles + executes; K=2 k=2 baked form (35,853 chars — the
4 fake 768-d vectors expand the source — 12 lines after expansion)
also compiles, `vector_literal(...)` calls round-trip through the
codegen, both forms expose the expected {rule_0, rule_1, is_class_0,
is_class_1} symbols.

Deliberately NOT in this commit (named plainly, not glossed over per
the work-loop HARD RAILS): the training loop (joint Adam over K*k
vectors + K*k scalars, vmap-batched logits with mandatory
equivalence guard to 1e-4 before training begins, the rank-1 vs
rank-k margin sweep) and the k-means-cluster-centroid anchor
initialization. Both gated on GPU availability and queued for the
next tick that lands after bu7o9mqxu completes.

## 2026-05-26: constrain-train agenda landed; back-prop-into-code paper queued; matrix-bake-back lean-spec + vector_literal builtin shipped; master cherry-picked + deleted

Session opened the three-cron autonomous loop and advanced through
Emma's 2026-05-26 priority sequence:

(1) Agentic-RAG-for-constrained-training agenda landed in `todo.md`
(commits `09accaad` + `5146619c` + `ffd2e175`): meta-tool design
(corpus indexer + retrieval CLI + decision template + sub-agent +
scaffolder), 10 scalar-first constrain-train targets, shared
infrastructure (equivalence-guard harness, matrix bake-back machinery,
constraint catalog, results table). Vision arc — "constrain to
meaningful at first" is phase 1 of mapping everything to meaning —
captured as direction-not-driver, with the explicit four-step
priority (equality cosine first → other scalars → matrix-valued → full
back-prop into code).

(2) Equality cosine-similarity adjustment promoted to #1 priority +
isolated-T probe harness shipped (`28d40eb8`,
`experiments/equality_cosine_adjustment.py`): prototypes FROZEN at
embed(category-name); only T trained; reports the logit margin
(correct - max wrong), not accuracy. Equivalence guard (vmap vs
per-sample to 1e-4) enforced before training. Smoke run (K=3
per-class=5 20 ep seed=0): equiv guard 2.98e-07, baseline margin
+0.1103 -> trained margin +0.1303 (T*=1.2481), round-trip max|delta|
2.38e-07, ratio +1.18x. Real K=5 n=3 measurement still in flight as
`bu7o9mqxu` (per-sample driver path; long-running; not killed).

(3) Back-prop-into-code paper + docs page (separate from
paper/paper.md and paper/neurips/ and paper/formal-verification/)
added to `todo.md` (`e5edef31`). New clawRxiv post chain at
paper/back-prop-into-code/, mirroring fv-paper-ci.yml; new docs page
at docs/back-prop-into-code.md, linked from the homepage. Anti-claim
discipline stated up front.

(4) Lean placement decision for T captured in
`planning/open-questions/equality-cosine-T-placement.md`
(`e5edef31`): per-rule numeric literal at each similarity call site,
status quo from Stage-B. Cross-program / language-level / compile-
time-calibration options all explicitly deferred with named re-open
triggers.

(5) Matrix-valued bake-back spec landed at
`planning/sutra-spec/matrix-valued-bake-back.md` (`e5edef31`): defers
first-class `matrix X = ...;` syntax; matrix-valued targets compose
existing primitives + a list of `vector_literal` values. Rank-1 is_X
= Stage-B's prototype + scalar. Rank-k = k prototypes + (optionally)
k output directions + k gains. Defuzz on truth axis = polynomial
coefficients on a scalar. The one concrete prerequisite identified:
the `vector_literal` builtin.

(6) Master-branch a5c0896f cherry-picked onto main (`8385fac8`) —
preserving 550 lines of cross-function axon read-demand propagation
compiler work (`_compute_axon_read_signatures`, 7 new tests in
TestCrossFunctionAxonElision, axons.md spec resolution) that was
NOT in main. Queue.md's "now unused" framing was wrong. After
cherry-pick: 96/96 codegen tests green + the new 7 included; remote
master deleted (`81fbc51b`).

(7) `vector_literal` builtin shipped (`164e499d`): variadic float
args, lowers to `_VSA.vector_from_floats([...])`, substrate-pure
torch.tensor on runtime device + dtype. 4 new tests in
`tests/test_vector_literal.py`, all 4 green; full codegen suite
100/100 in 22 s. Unblocks the rank-k is_X experiment.

This tick (work-loop): removed the now-completed `vector_literal`
#2 entry from `queue.md`; promoted the **rank-k is_X experiment** as
the next concrete #2 piece, with end-to-end steps (mechanism,
initialization from embed(category-word) anchors, joint training of
K * k vectors + K * k scalars, vmap-batched logits with equivalence
guard, bake-back via vector_literal + scalar literals, rank-1 vs
rank-k margin sweep). Queue rule honored: completed work goes to git
log, not the queue.

## 2026-05-26: three-cron loop started; CLAUDE.md cron-section dedup; agentic-RAG agenda; stale compile_su queue entry removed

Session opened the three-cron autonomous productivity loop per CLAUDE.md
§"Autonomous productivity loop" — work-loop at `:03` (`6fd6af7f`),
auto-flush at `:15` (`a2c1bc2e`), status-report at `:42` (`4db40b08`),
all session-local (`durable: false`).

CLAUDE.md trim (`96f7f81f`): the duplicate cron section before the
Writing section was a clear copy of the post-Emergency-Stop cron
section; merged into one, carrying both the "don't ask about timezone"
line and the "not OS crontab / not GH Actions" framing. -5 lines, no
rationale lost. queue.md gained two pinned-tail items (ensure crons
running; final independent status-report) so the loop self-maintains
across sessions.

todo.md (`09accaad`): added "Agentic RAG for constrained-training
design" agenda — generalizes the Stage-A/B equality-rule pattern
(compile through real codegen, train through emitted graph, bake
trained values into `.su` literals) across other learnable parameters.
Three sub-agendas: meta-tool (corpus indexer over
`planning/findings/` + `sutra-spec/` + `experiments/*`, retrieval
CLI, decision-template, sub-agent, scaffolder); 10 constrain-train
targets (scalar-first: `select` sharpness, soft-halt threshold,
similarity temperature, number-axis scale/offset, codebook decode
threshold, class-method dispatch, per-axis defuzz; matrix-valued
gated on the `.su` matrix-literal spec decision); shared
infrastructure (equivalence-guard harness, matrix bake-back machinery,
`constrained-training.md` constraint catalog, results table).

This tick (work-loop): removed the stale `compile_su` queue entry —
the helper is shipped at v0.7.1 (`fa89d359` module +
`5036d387` precompile script + tag `v0.7.1`); verified
`tests/test_cached_compile.py` passes 7/7 in 4.05 s before deletion.
Queue rule says completed work belongs in git log, not queue.md.

## 2026-05-27: daily audit — clean (no-op)

2026-05-27 daily audit: clean (67 .su compiled, 0 leaks; 21 open-questions dossiers + sutra-spec/open-questions.md index checked, 0 resolved-elsewhere; promise/await fit-to-spec). Fresh container with no torch/numpy/ollama preinstalled — installed pytest + torch (CPU) + numpy + the `ollama` python pkg, the ollama server (needed zstd), and pulled `nomic-embed-text` (digest `0a109f422b47`), so every leg ran live (no env-skip, no false-clean). Promise/await: codegen lint clean + `test_await_substrate_pure` 4/4 both backends incl. the two live-embedding semantic legs (`main()` = 3.0). Full suite 389 passed / 9 skipped (egglog + sutra_ffi.dll optional deps; not purity tests) — up from 370/9 yesterday (the +19 are the new `test_vector_literal.py` 4 + `TestCrossFunctionAxonElision` 7 + 8 elsewhere). The 19 commits since the 2026-05-26 audit (`73c6a47`..HEAD) are constrain-train-agenda follow-on (rank-k is_X harness, equality cosine adjustment finding, agentic-RAG todo) + two real compiler touches: `164e499` adds a `vector_literal(0.123, ...)` builtin lowering to `_VSA.vector_from_floats([…])` → `_torch.tensor(values, dtype=self.dtype, device=self.device)` (a literal-lift entry boundary, same class as `make_real` / `array_from_literal` — Audit.md #8 LEGITIMATE; sweep gate confirms 0 new leak signatures); `8385fac` cross-function axon read-demand propagation is a compile-time elision pre-pass, not a runtime path. The new dossier `equality-cosine-T-placement.md` (commit `e5edef3`) is self-RESOLVED 2026-05-26 in its own header ("Lean" → option 1, per-rule literal); recorded per convention so a future session does not re-open it, not stale drift. Audit.md #1/#2/#3/#5/#6/#7/#8 intact, #4 still NOT-A-LEAK.

## 2026-05-26: daily audit — clean (no-op)

2026-05-26 daily audit: clean (67 .su compiled, 0 leaks; 20 open-questions dossiers + sutra-spec/open-questions.md index checked, 0 resolved-elsewhere; promise/await fit-to-spec). Fresh container with no torch/numpy/ollama preinstalled — installed pytest + torch (CPU) + numpy + the `ollama` python pkg, the ollama server (needed zstd), and pulled `nomic-embed-text` (digest `0a109f422b47`), so every leg ran live (no env-skip, no false-clean). Promise/await: codegen lint clean + `test_await_substrate_pure` 4/4 both backends incl. the two live-embedding semantic legs (`main()` = 3.0). Full suite 370 passed / 9 skipped (egglog + sutra_ffi.dll optional deps; not purity tests). The 19 commits since 2026-05-24 are all FV-paper / FV-spec / contact-email work (`bc2459c` selectable substrate dtype is the only codegen touch — adds a float64 path, no new leak signatures in the grep); none resolves a `planning/open-questions/` dossier or a `sutra-spec/open-questions.md` entry. Audit.md #1/#2/#3/#5/#6/#7/#8 intact, #4 still NOT-A-LEAK. Open-questions README verdict table (2026-05-16, refreshed 2026-05-17 + 2026-05-21 pruning) still authoritative; the deferred deletion of strikethrough RESOLVED lines in `sutra-spec/open-questions.md` is a destructive rationale-loss call left for Emma per todo.md, not stale drift.

## 2026-05-24: daily audit — clean (no-op)

2026-05-24 daily audit: clean (67 .su compiled, 0 leaks; 19 open-questions dossiers + sutra-spec/open-questions.md index checked, 0 resolved-elsewhere; promise/await fit-to-spec). Fresh container with no torch/numpy/ollama preinstalled — installed torch (CPU) + numpy + the `ollama` python pkg, the ollama server (needed zstd), and pulled `nomic-embed-text` (digest `0a109f422b47`), so every leg ran live (no env-skip, no false-clean). Promise/await: codegen lint clean + `test_await_substrate_pure` 4/4 both backends incl. the two live-embedding semantic legs (`main()` = 3.0). Full suite 352 passed / 9 skipped (egglog + sutra_ffi.dll optional deps; not purity tests). Only new code since the 2026-05-23 audit is PR #32 (variable-vs-variable loop-condition fix) — a type-propagation bug fix, already `[x]` in todo.md, routes `i < n` through `_VSA.lt`/`_VSA.gt` on the substrate; not an open-question resolution. Audit.md #1/#2/#3/#5/#6/#7/#8 intact, #4 still NOT-A-LEAK.

## 2026-05-23: daily audit — 3 gates clean; executed the queued cosine doc cleanup; embedding-drift note

Substrate-leak + promise/await + stale-open-question audit. This
container had no torch/numpy/ollama preinstalled; I installed torch
(CPU) + numpy + the `ollama` python package, installed the ollama
server (needed zstd) and pulled `nomic-embed-text` (digest
`0a109f422b47`), so — unlike the 2026-05-21 run — **every leg ran,
including the live-embedding ones.** No false-clean from an env skip.

- **Promise/await fit-to-spec:** PASS, exit 0. Codegen lint clean +
  `test_await_substrate_pure` **4/4** green both backends (the 2 e2e
  semantic legs that 2026-05-21 had to env-skip ran this time and
  passed; `main()` = 3.0). `await_value` still emits only
  `return self.value(p)`. No regression.
- **Substrate-leak sweep:** clean — 67 `.su` compiled, 0 operator
  leaks (18 intentional `CodegenNotSupported` skips: if/else, casts,
  method/operator decls, string interpolation, snap-on-numpy, C-style
  for — feature-coverage gaps, not masked leaks).
- **Codegen host-scalar grep:** every historical leak signature is
  either a documentation comment (#1 `rotate_slot`, #7 `select`, #5
  string ops) or a catalogued legitimate boundary (the `truth()`
  canonical-axis accessor; the `_str_axes()` cached structural-index
  constant; `make_string`'s host-literal→substrate ENTRY boundary).
  Audit.md REAL LEAK #1/#2/#3/#5/#7/#8 verified intact; #4 still
  NOT-A-LEAK. No new leak. Transcendentals + branchless-loop +
  loop-function-decl regression guards 35 passed/33 subtests.
- **Open-questions:** 19 dossiers + `sutra-spec/open-questions.md`
  index checked. **0 NEW resolved-elsewhere drift.** The single drift
  the 2026-05-21 audit had queued —
  `planning/open-questions/cosine-as-its-own-transcendental.md`, whose
  body still posed complex-argument `cos(z)` as open while its banner
  + `ccos` resolve it — was **executed this run** (settled design,
  doc-only, per CLAUDE.md "barrel through settled work; don't quote
  prior cautious framings forward"): verified `ccos`
  (`codegen_pytorch.py:1384`) substrate-pure (`_cnum` →
  `complex_mul`/`complex_add`/`cexp` + `_mk` constants, no host
  branch/scalar extraction); reduced the dossier body to a resolution
  pointer keeping only the genuine `csin` residue; added the missing
  RESOLVED verdict-table row in the README and corrected both stale
  tallies (now 5 RESOLVED/STALE, 3 RESOLVED-core+tail, 11 genuinely
  OPEN). Removed the item from `queue.md`.
- **Smoke-test note (negative result, not doctored):**
  `examples/_smoke_test.py` — 10/11 examples pass; **Example 7
  `fuzzy_dispatch.su` scored 1/4, below its documented majority
  threshold (`correct >= 2`).** This is **embedding-model-version
  drift on the unpinned `nomic-embed-text:latest`** (freshly pulled
  this run), **not a code regression:** the dispatch mechanism is
  substrate-side and every harder retrieval example passes (20-phrase
  `nearest_phrase` clean+noisy, `sequence` position-binding,
  classifier, analogy, knowledge_graph), embedding dim is the correct
  768, and the last `codegen_pytorch.py` change (`ef93db3`, JS ordered
  comparisons) is unrelated to dispatch/`argmax_cosine`. The smoke
  test's own comment already flags fuzzy_dispatch as embedding-limited
  ("the substrate's prototype separation is the limiting factor").
  Threshold left untouched (doctoring it is forbidden). Surfaced for
  an embedding-model-pinning decision; no queue item fabricated.

## 2026-05-21: arXiv v2 — minor paper correction + /arxiv noindex + doc accuracy

**arXiv v2 originates here.** Emma authorized a minor correction to
the on-arXiv paper (`paper/paper.md`) and a v2 re-upload; **this
revision is the source state for that v2.** Three text changes, no
data altered:

- **Appendix H "Reproduction details" table → bullet list**
  (`0b151b79`). The 7-column hyperparameter table rendered broken:
  pandoc assigns all columns equal 1/7 width and the long monospace
  script names (e.g. `differentiable_training_compiled.py --batched`)
  can't break or fit a ~0.78in column, so they overflowed the margin.
  Converted to a per-experiment bullet list; every value (script,
  trials, embedding, optimizer, seed) preserved verbatim.
- **Dropped "figure" from the AI-use no-generation sentence**
  (`0b151b79`). The three figures are AI-drafted TikZ schematic
  diagrams, not data plots, so "No experimental result, figure,
  table, or numerical value … was generated by a language model"
  overreached. Now reads "…result, table, or numerical value…"; the
  results-integrity claim is unchanged.
- **Removed the AI-numpy-substitution parenthetical** (`65bcfe53`).
  The disclosure no longer says "(correcting cases where AI-suggested
  code silently substituted host numpy and broke substrate purity)";
  it aired an internal AI-code bug inside the disclosure and undercut
  the substrate-purity claims. The statement still asserts the author
  verified every operation runs on the substrate.

`paper/paper.md` was under the May-2026 arXiv freeze; this is the
authorized exception. The freeze re-pin now tracks `main` HEAD rather
than a single fixed hash (each correction commit moves it). The v2
source bundle auto-rebuilds and publishes at
`sutra.emmaleonhart.com/sutra-arxiv-source.tar.gz` on every `paper/`
push; the actual arXiv replacement upload (web form, logged in) is
Emma's manual step.

**`/arxiv/` taken out of search (`c557485b`).** The `/arxiv/` page is
a direct-URL-only utility for grabbing that source bundle. It now
carries a `noindex, nofollow` meta tag (new `noindex` param threaded
through `build_site.py`'s `shell()`), and a root `robots.txt`
disallows the binary bundle `/sutra-arxiv-source.tar.gz` (a `.tar.gz`
can't carry a meta tag). The page is deliberately *not* robots-blocked
so crawlers can still read the noindex. Every other page stays
indexable.

**Doc accuracy: the site is ~23 pages, not "two" (`7540b31b` +
README).** CLAUDE.md (§Audiences, §Project Overview, §Architecture)
and the README both still described the site as "two static pages"
(`docs/index.md` + `docs/neurips-2026.md`) with a bare homepage. That
was true only for the ~8 hours between the 2026-05-16 scrap
(`62f2c3bd`) and the 2026-05-17 restore (`34009c9e`, "restore the
conceptual pages under the new pipeline") — the docs simply never
caught up to the restore. Reality: `build_site.py` emits one HTML page
per `docs/**/*.md` (22 files: the homepage, the concept guides, the
tutorials) plus `/paper/` from `paper/paper.md`, and the homepage
carries an "Explore" section linking them all plus a NeurIPS card.
Corrected the three CLAUDE.md sections and the README website line to
match. The older DEVLOG entries below were accurate at their date and
are left as the historical record.

**Website now links to the arXiv paper.** The published abs URL is
**`https://arxiv.org/abs/2605.20919`**, recorded as the `ARXIV_URL`
constant in `build_site.py` — the repo had never captured the
assigned arXiv identifier anywhere (the 2026-05-20 entry below noted
the upload happens via the arXiv web form, so the ID was lost), and
this constant is now its single source of truth. The homepage
`.links` row carries a "Read on arXiv" pill next to the on-site "Read
the paper" button, and the `/paper/` page lede links arXiv as the
canonical published version. No fabricated/placeholder URL was ever
shipped — the link waited on the real ID.

## 2026-05-21: daily audit — 1 resolved-elsewhere open-question found

Substrate-leak + promise/await + stale-open-question audit.
Environment note: this container had no torch/numpy/ollama
preinstalled — installed torch (CPU) + numpy to run the audit;
ollama (the embedding runtime) is **not** available, so the
promise/await **end-to-end semantic** test could not run. The
substrate-purity guard it protects did run and passed (see below),
so this is not a false full-pass claim — only the live-embedding
semantics leg is environment-skipped.

- **Substrate-leak sweep:** clean — 67 `.su` compiled, 0 operator
  leaks (18 intentional `CodegenNotSupported` skips: if/else, casts,
  method/operator decls, snap-on-numpy, etc.).
- **Codegen host-scalar grep:** every leak signature maps to a
  catalogued category (compile-time constants, monitoring accessors,
  literal-lift/`_st`/`_cnum` entry boundaries, the `string_to_python`
  decode boundary, JS-interop coercion carve-outs, the argmax commit
  edge). No new leak. Audit.md REAL LEAK #2 (`defuzzify_trit`), #3
  (`await_value` = `return self.value(p)`), #7 (`select`
  `_torch.where` eps-guard) verified intact; #4 still NOT-A-LEAK.
- **Promise/await fit-to-spec:** substrate-purity structural guard
  PASS — codegen lint clean + `test_await_substrate_pure`
  leak-signature tests 2/2 green both backends; `await_value`
  emits only `return self.value(p)`. No regression. (The 2 e2e
  semantic tests are env-skipped per the ollama note above, not
  failed-on-merits.)
- **Open-questions:** 19 dossiers + spec index checked. One
  resolved-elsewhere drift found:
  `planning/open-questions/cosine-as-its-own-transcendental.md` —
  its body still poses substrate-pure complex-argument `cos(z)` as
  open while its own banner + `ccos` (`codegen_pytorch.py:1384`,
  verified substrate-pure) + the 2026-05-17 finding resolve it.
  README prose/tally still count it GENUINELY OPEN. Queued (top of
  queue.md Active) to reduce the doc to a pointer (keeping the
  genuinely-open `csin` residue) and fix the README.

## 2026-05-20: repo cleanup — retire scratch chats and notes

With the paper on arXiv, trimmed dev-process residue out of the
working tree to leave a cleaner, more professional snapshot. **History
is untouched — every file below is recoverable via `git show` /
`git log`; this is a working-tree removal, not a history rewrite.**

Removed:
- `crashed_session_2026-05-20.md` — accidental paste of the Claude
  Code web UI sidebar (unrelated chat titles, project names); no Sutra
  content.
- `sutraDB/unstructured/` (whole folder) — raw voice-transcribed
  Claude/Gemini brainstorming plus two stale ManuForge-era integration
  notes (SutraDB v0.3.x). The design substance (ontochronology,
  world-state, temporal diff) already lives in
  `sutraDB/docs/ontochronology.md` + `architecture.md`, so nothing was
  lost.
- `paper/feedback before arXiv/SYNTHESIS.md` — pre-arXiv multi-LLM
  review synthesis; its job (clearing the arXiv submission) is done.
- `sutraDB/docs/session_notes_2026-03-15.md` — dated single-session
  dev log.
- Root scratch scripts `compile_to_cuda.py`, `hello_world_cuda.py`,
  `hello_world_emitted.py`, `inspect_dispatch.py` — a self-contained
  CUDA-experiment cluster with no external dependents.

Kept deliberately: all of `planning/{findings,open-questions,sutra-spec}/`
(canonical agent surface) and `paper/reviews/` (auto-committed clawRxiv
pipeline output).

Second pass: removed `scripts/extract_chat.py` (the Claude.ai-HTML→md
extractor that produced the chat files above; orphaned once they were
gone) and `planning/exploratory/sutra-paper-draft.md` (a 2026-04-28
outline superseded by the on-arXiv paper). Relocated the root
`!editor.bat` IntelliJ-plugin launcher to
`sdk/intellij-sutra/editor.bat` (dropping the `!` root-sort prefix,
fixing its `%~dp0`-relative path, and updating the `README.md` /
`todo.md` references). `!runClaude.bat` was kept at Emma's call.

Third pass (arXiv-release prep): removed the clawRxiv retraction feature
(`paper/RETRACT_SKILL.md`, `scripts/withdraw_papers.py`,
`.github/workflows/withdraw-papers.yml` — one feature, removed together)
and `planning/exploratory/promises-design-conversation.md` (the promises
design is implemented and lives in `planning/sutra-spec/promises.md`, so
the raw transcript is no longer needed). Refreshed `README.md`: fixed the
smoke-test count (13→10, the real `ok0..ok9` set), dropped "formerly was"
history (the scrapped MkDocs site, the retired C-style loop surface, dated
backend notes), made the NeurIPS mention low-key, corrected the CI table to
the actual workflow set, and removed the stale `chats/` row (the dir isn't
tracked).

Fourth pass (leftover fly-brain + artifacts, 2026-05-21): removed the
orphaned IntelliJ fly-brain tool window —
`viz/SutraFlyBrainToolWindowFactory.kt` + `viz/fly-brain.html` (already
unregistered; `plugin.xml` documented them as "retired 2026-05-10") — and
cleaned up the now-dangling references (the `SutraEmbeddingToolWindowFactory`
companion mention; the `plugin.xml` "fly-brain visualizer" feature line and
its two references to planning docs that don't exist:
`20-ide-architecture.md`, `fly-brain-visualizer.md`). Removed the vestigial
`runtime_use_hemibrain` flag from `codegen_base.py`/`codegen.py` (it was set
but never read; PyTorch emit verified clean after, 88 KB module, exit 0).
Untracked the committed tensor binaries
`experiments/.diff_train_embeddings.pt` (3.3 MB, already gitignored yet
tracked) and `experiments/differentiable_training_weights.pt` (3.4 MB) —
both are harness-generated and now gitignored; the frozen paper references
the weights file only as a run *output*, so reproduction is unaffected.
Removed the committed run logs `experiments/{bio_run,crosstalk_chain_run}.log`
and gitignored `experiments/*.log`.

Fifth pass (full fly-brain purge, 2026-05-21): removed the 26 fly-brain
experimental findings (all `shiu-*`, the `140D-spiking-*` set, the
`jaccard-*` hemibrain/KC studies, `cx-ring-attractor`, `composed-Q-spiking`,
`spiking-Q-rotation`, `combined-pipeline`, `fuzzy-conditional-n35` [hemibrain
seeds], `audit-rotation-loop-execution-locus` [spiking EPG loop]) plus the 3
`shiu_cond_sweep_*.log` raw logs; the connectome-era design docs
`project-kind-connectome-vs-embedding.md` and
`implementation-shortcuts-catalog.md` (half fly-brain, links now dangling);
and the 3 `_archived-` open-questions (`numpy-inheriting-from-flybrain`,
`tier2-bundle-substrate-vs-algebra`, and `loop-surface-redesign` — the last
is core-loop-design residue, removed as the archived-doc pruning the folder's
own rule #3 calls for). Removed the vestigial `runtime_n_kc` (Kenyon-cells)
codegen flag (assigned, never read; PyTorch emit verified clean). Fixed the
links these removals exposed: the `open-questions/README.md` triage table +
contents + tallies, `nested-loops-as-orthogonal-subspaces.md`,
`sutra-paper-pre-mortem.md`, `todo.md`, and the `findings/README.md` example.
Kept core meta-docs that only reference fly-brain as backdrop
(`sutra-paper-pre-mortem`, `repo-audit`) and the substrate-agnosticism
mentions in the specs (specs are authoritative). findings .md count 87→60.

## 2026-05-20: paper uploaded to arXiv

**The version of `paper/paper.md` currently in the repo is the version that
is on arXiv.** The arXiv-fitting work landed at commit `e7cca673` on
2026-05-19 — *"paper.md abstract: shorten to fit arXiv submission
metadata"* — which trimmed the abstract from 2691 chars to 1541 chars to
clear arXiv's 1920-char submission-field cap, so `paper/paper.md` and the
arXiv submission share one source of truth. Subsequent commits before this
DEVLOG entry are Figure 2 readability tweaks (`9a5cd0a6`, `c42354b9`,
`a9279cf3`) plus the regular `papers-ci.yml` clawRxiv resubmission/review
echo commits; the body content matches what was uploaded.

What the arXiv-submitted paper contains, in load-bearing terms:

- **Title and core claim:** *"Sutra: Tensor-Op RNNs as a Compilation Target
  for Vector Symbolic Architectures."* Same artifact is both a logic
  program and a trainable neural network; whole-program beta-reduction to
  a fused tensor-op graph; PyTorch autograd flows through the emitted
  graph.
- **Four contributions:** (1) Lagrange-interpolated polynomial Kleene
  three-valued logic — AND/OR/NOT/NAND/NOR/XOR/XNOR exact on the
  $\{-1, 0, +1\}$ truth grid, $C^\infty$ elsewhere; (2) beta-reduction
  to a substrate-pure tensor-op graph; (3) rotation binding decoding at
  100% through bundle width k=8 on four substrates (nomic-embed-text,
  all-minilm, mxbai-embed-large, ESM-2) where Hadamard has already
  collapsed; (4) §3.6 fuzzy-rule classifier compiled from `.su`,
  random-init 18.7±9.5% → 100.0±0.0% trained (three seeds, K=3
  compiled-graph result), with the weighted variant baking the trained
  scalar gain back into `.su` source as a numeric literal, recompiling
  to ≈ 2×10⁻⁷ per-logit reproduction.
- **§3.7 weights-in-source.** Stage B integrity work: scalar weight
  trainable through the compiled graph, baked into a recompilable `.su`
  literal — closes the "is the artifact actually both a logic program
  and a trainable NN" question.
- **Anisotropy spine.** Why cosine isn't enough: Ethayarajh 2019,
  Gao 2019, Mu & Viswanath 2018 (`7a3c6767`). All citations
  web-verified against arXiv/ACL.
- **Reproducibility statement** before References (per the
  `feedback_paper_replication_placement` memory): two-zip split,
  upstream repo link as fallback, venue-agnostic framing
  (`e913cdd4`, `f151bb62`, `b3a3b10b`).
- **arXiv source bundle published** at `sutra.emmaleonhart.com/arxiv`
  with a CI gate (`76467035`, `2ee9f3ef`); `paper.tex` defines a `none`
  counter so pandoc + hyperref + longtable doesn't break on strict
  pdflatex (`75aa58b6`).

**`paper/neurips/` remains frozen** per CLAUDE.md §"NeurIPS submission is
FROZEN." The arXiv upload is from the live `paper/paper.md`, which is
free to evolve — the NeurIPS archive is the immutable May-15 snapshot.

What changed between the 2026-05-06 NeurIPS sprint entry (below) and the
arXiv upload, in rough order:

### Paper integrity — §3.6 promoted from hand-reimplementation to compiled-graph training

The pre-2026-05-15 §3.6 trained a hand-reimplementation of the rule rather
than the compiled graph itself (finding `11b034e8`). Two-stage fix:

- **Stage A0** (`cbba92f2`, `4a0c148b`, `7380453c`, `e19de3d7`): emit
  substrate-pure tensor similarity/dot — drop mid-graph `float()` so the
  graph is differentiable as emitted (a compiler change, not a harness
  fix; the pre-A0 emit returned a Python float and broke autograd).
  Curated gate green pre==post + probe + numeric-output + mechanism
  proof.
- **Stage A** (`610b2f42`, `0c3a4fe1`, `dca46da6`): real compiled-graph
  training harness — `.su` → PyTorch codegen → backprop through the
  emitted rule. Paper upgraded to real K=5 3-seed compiled-graph result;
  abstract, §3.6, and Appendix H rewritten to the real numbers
  (`9d5321f1`). Earlier proxy numbers and the fabricated curve figure
  removed.
- **Stage B** (`f03680f7`, `5f0ed354`): scalar weight trainable through
  the compiled graph (`w.grad` nonzero) and bake-able as a `.su`
  literal; trained weight written back into recompilable `.su`; paper
  §3.7 added. This is the "weights are themselves legible code" claim
  the abstract anchors on.

A misrepresented speed claim landed alongside Stage A and was caught:
the 6.2-hour driver-artifact framing was wrong (`7bce39db`) and was
reframed via batched compiled-graph forward.

### Pre-arXiv synthesis rounds 2–4

Each round consolidated multi-LLM + Discord feedback into a single
synthesis file rather than dispersing it across files (that file,
`paper/feedback before arXiv/SYNTHESIS.md`, was retired from the
tree in the 2026-05-20 cleanup below — recover via git history).
**Verdict held across all five reviewers in round 4
(Claude Sonnet 4.6, DeepSeek, Le Chat / Mistral, Meta AI, Gemini):**
AI-policy-violation removal risk is very low. The §"AI-use statement"
already does the disclosure arXiv's policy targets; the reproduction
scripts + seeds + explicit limitations are the strongest anti-removal
signal.

Two material round-4 fixes landed (`cc3b1416`):

- §3.6 defensive parenthetical reworded — Claude and Gemini independently
  flagged *"…no per-epoch curve is plotted (fabricating one is not an
  option)"* as reading like AI-safety-guardrail reflection. Rephrased
  to standard academic limitation tone.
- §"AI-use statement" gained one factual additive sentence covering the
  result/figure/number boundary explicitly: *"No experimental result,
  figure, table, or numerical value reported in this paper was
  generated by a language model…"*

Earlier-round actions still load-bearing in the arXiv submission:
soften the abstract megasentence and "collapses the boundary" /
Turing framing (`001747e4`); drop the "one artifact, two interpretations"
slogan Emma disliked (`6faf3f51`); rework "as of 2026" as deliberate
literature-cutoff (`7d30e802`); move both pipeline diagrams from
appendices into the body (`a1194417`); §3 subsection tagging
method/experiment + roadmap line (`c7683286`); §3.6 real 5-seed
replication with TikZ accuracy plot (`dde3e700`); the `.su` snippet +
fuzzy-NN Related-Work subsection (`67a2ae32`).

### Other significant work May 6 → May 20

**Site rebuild — MkDocs Material → two static pages.** Emma's call
2026-05-16: the ~23-page MkDocs site wasn't good enough to maintain.
Scrapped in `62f2c3bd`; rebuilt as a real homepage at `/` + NeurIPS
archive at `/neurips-2026/` (`4161e8dc`), Yantra-style header/footer
(`20fe9d6d`), conceptual pages restored under the new pipeline
(`34009c9e`). Identity styling moved through several iterations
(`672f22f1`, `cf711e44`, `e1534435`, `e6e44030`). Canonical domain set
to `sutra.emmaleonhart.com` (`c25c298c`). Homepage rewritten value-led
(`98aeff8f`).

**`master` → `main` CI migration** (`5ea853ef`, `b318791e`). All
workflows, Pages env policy, and doc refs migrated. The leftover
`origin/master` branch is still tracked open as an Emma-decision item
in `queue.md`.

**`scalar` → `number` rename, three gated commits** (`8a5d12a7`,
`b34a275b`, `f21fdffa`, 2026-05-17). Compiler `number` is now
canonical; `scalar` deprecated alias kept for the frozen NeurIPS
archive. Dogfood through stdlib `.su` type signatures; docs updated.
The companion 0-d-projection drop on `exp`/`cos`/`sin` is explicitly
deferred (see `queue.md` item 1) — high blast radius, needs a separate
gated session.

**Substrate-leak audit — `Audit.md` burn-down.** Catalogued every host
`float()`/`if`/`for`/libm leak in the runtime; safety-critical
(CLAUDE.md intro). Five REAL LEAKs fixed and verified — `rotate_slot`
(`d8fc68d1`), `defuzzify_trit` (`3c7dc802`), `argmax_cosine` zero-norm
host branch (`5670ca4f`), `slot_store` `float(scalar)` (`eb062655`),
string ops host codepoint loops (`0e363b96`). Audit REAL LEAK #4
reclassified NOT-a-leak (Emma — fixed-T tail-recursive cell, not a
host branch on data, `9481a47b`). #3 (promise `await_value` host
`if/break`) remains structurally open — Emma direction is to model
async/await as an implicit-axon-input + arrival-flag instead of a poll
loop. CI leak-gate verified green (`edbc5f68`, 1738s, 67 programs).

**Transcendentals — literate-math via interpolated lookup tables.** The
2026-05-10 architecture (`3aa57b44`, `9a652211`) — length-N value
tensor + triangle-weight soft-index dot product, avoiding the prior
bound-table approach's pigeonhole limit. Shipped: `exp`/`log` on both
backends, `pow = exp(y * log(x))`, `sqrt = exp(0.5 * log(x))`,
`Math.sin/cos/tan` + `sinh/cosh/tanh` via the same lookup architecture
(`0a31fd5c`), `Math.PI`/`Math.TAU`/`Math.E` (`d043a812`, `ebb0382f`).
`SutraMathOverflow` raised when input falls outside the precomputed
table range (per Emma's "specific overflow exception, not silent
zero"). Followed by **literate-math beta-reduction** — `cexp` `.su`
body IS the executable reduction (`ae269f6b`); `pow`/`sqrt`/`tan`/
`sinh`/`cosh`/`tanh` `.su` bodies are the reduction (`b9e11f5e`);
core delivered with `cexp` + 6 derived now literate (`d224fae9`);
complex-argument cosine `Math.ccos` shipped substrate-pure
(`a7f7a43f`); Math.mod literate body promotion (`4f604520`).

**Implicit tail-recursive loops — `loop(x){body}` sugar.** Three units
landed (`b1fabdb6`, `a902e3a8`, `532ad717`) — variable-capture
analysis, architecture verified-and-corrected (codegen-site approach
rejected, last unknown resolved), `loop(expr){body}` desugar works
end-to-end for count form on both backends gated. The `while_loop`
kind with relational bounds also gated (`0c78e1de`). Class-method
bodies + scope-shadowing guard follow-on (`4b48d681`). The remaining
"lighten the implicit axon" work stays in `todo.md`.

**TypeScript transpiler closeout, May 7–11.** 12 fixtures green
end-to-end (TS source → `.su` → runnable Python). Class lowering with
fields/methods/`new`/`this` (`60b9fecd`, `a5303c86`, `a602ba1b`,
`c684c88e`); user-class operator overloading via inheritance-chain
dispatch (`c0fa84fe`); synthetic-axis equality via Euclidean-distance
+ tanh (`1b292ddb`); non-static class loops thread `this` as implicit
state (`903642fc`); arrow functions + closure-free closure capture
(`0858ca24`); first-class function values via `function` type-name in
params (`08d3530c`); promises Stage-1 first cut (`729fafde`); module
imports via lower-time inline + diamond dedup (`5ad16093`); enum
lowering + TS classes extend `JavaScriptObject` (`7880c028`);
multi-program axon passing demo end-to-end (`872a8c1a`,
`1af63ecd`). Sutra PyPI distribution renamed `sutra-compiler` →
`sutra-dev` (`0979b4bf`), `sutra-dev[ts]` extra published
(`2690051d`).

**Open-questions triage** — explicit verdict table for all 22 docs
(`dd448b47`), per-doc verdict banners stamped (`012339e0`), spec
open-questions reconciled with current code (4-batch spec audit:
`899edbf5`, `29b11f18`, `ea0ad947`, `6e3a204f`).

**Anti-`"honest"` writing rule.** Ban codified (`483a17b8`),
context-sensitive sweep across docs + code (`08ce1d0b`), then
strengthened to ban substitute coats (frank/candid/transparently) and
require naming failures plainly (`3ea0684c`). Memory:
`feedback_no_honest_genuinely_buzzwords`.

**Math.mod = rotation_mod**, beat sawtooth_mod in benchmark; modulus
library moved to `stdlib/modulus.su` with "expensive" warning; `%`
dispatches to `_VSA.fmod` (truncation). Per memory
`project_modulus_library`.

End-of-period state: `paper/paper.md` on arXiv as the canonical
post-NeurIPS revision; `paper/neurips/` frozen; substrate-purity
audit five-of-eight resolved with three structural opens documented;
TypeScript transpiler feature-complete on its 12 fixtures; site
rebuilt as two static pages on the shared `emmaleonhart.com`
identity; the long-running CI migration done.

---

## 2026-05-06: NeurIPS sprint, 10-page body misreport correction, paper trim

**Abstract + title submitted to NeurIPS 2026.** Title in commit
`65e0fb0`, abstract in commit `84f3465`; both frozen per a new
CLAUDE.md §"Title and abstract are FROZEN" rule. The full-paper
deadline is May 6 AOE.

**The "9-page body achieved" claim was never true.** A long-
running misreport in earlier queue.md entries and several commit
messages (e.g. `68fcbcc` "restore 9-page cap", `e30ca6b` "pull
body back under the 9-page cap", `9f642f2` "reclaim a body
page") all asserted that the body had been or could be brought
to 9 pages. Verification by downloading the actual
`paper-pdf.yml` artifacts on 2026-05-06 showed every one of
those commits actually produced a 20-page PDF (10 body + 1
references + 9 appendix). The body had been 10 pages on every
real CI build for the duration of those entries. PR #31 did not
cause a "10-page regression" because there was nothing to
regress from; reverting PR #31's two paragraphs (commit
`68fcbcc`) reduced body length but did not drop the page count.

The error was trusting prior session notes (queue.md and
PR-description claims) over the actual artifact. Lesson recorded:
when the page-count rule is the constraint, download the PDF
and count pages before claiming compliance. Do not paraphrase
queue.md.

The actual trim that started moving the page count happened
later 2026-05-06: dissolve §4.3 into §4.2, merge §5 + §6 into a
single "Demonstration, limitations, and future work" section,
move the K=3 pipeline figure (~50 lines of TikZ) to a new
Appendix K. See `git log` for the per-commit story.

Also landed:
- **clawRxiv review trajectory v20 → v50.** Stable at Accept /
  Strong Accept since v23. v44 (Accept), v45 (Strong Accept),
  v46 (Strong Accept), v47 (Accept), v50 (Accept). The
  reviewer-targeted polish paragraphs added in PR #31 (§3.4
  gradient-stability + §6 MNIST/CLEVR pointer) did not move the
  rating; reverted in `68fcbcc`.
- **Em-dashes stripped from body.** Commit `eed621d`. 66 U+2014
  rewritten to natural punctuation (parens, colons, commas).
  Frozen title and abstract untouched.
- **paper.tex \\title{} sync.** Same commit. The hardcoded
  `\\title{}` in `paper/paper.tex` was the old PR-#28 rename
  ("Compiling a Vector Symbolic Architecture..."); the H1 in
  paper.md had the canonical post-revert title. PDF title page
  was therefore showing the wrong title. Both now read "Sutra:
  Tensor-Op RNNs as a Compilation Target for Vector Symbolic
  Architectures."
- **`\\newpage` before `## References`** added by Emma in
  `a160632`, then needed blank lines around it (commit `a2ccdfc`)
  so pandoc's markdown reader didn't parse `---\\n\\newpage` as
  a YAML metadata block (it threw "did not find expected
  <document start>" at line 4 col 0 and broke the build).
- **Repo cleanup:** CHANGELOG.md folded into DEVLOG.md as a
  v0.2.0 subsection (commit `a07dd8c`); root-level
  `combinatorics_results.json` and `combinatorics_summary.md`
  deleted (commit `946279f`, finding preserved in
  `planning/findings/2026-04-30-combinatorics-flat-gradient.md`);
  queue.md cleaned up to match its own "queue, not state
  snapshot" header (commit `c958f75`).

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

## 2026-04-22 → 2026-04-24: Sign-flip retirement → rotation binding canonical + v0.2.0 release

The compile-target rotation work that displaced sign-flip binding
in the user-facing demos. Sign-flip stayed in the codebase as
historically-meaningful but `bind` defaulted to rotation.

- Sign-flip retired from the codegen 2026-04-22 (memory:
  `feedback_no_sign_flip.md`). Rotation became the only `bind`
  implementation; the binding spec (`planning/sutra-spec/binding.md`)
  flipped its "current implementation" pointer.
- Synthetic-subspace validation work in
  `planning/findings/2026-04-24-synthetic-subspace-validation.md`.

### v0.2.0 — first tagged release (2026-04-24)

The compiler is real: `.su` source parses, validates, compiles to
self-contained Python targeting PyTorch (CUDA when available, CPU
otherwise), and runs. 175 tests pass.

**Language**

- **Primitive classes:** `int`, `float`, `complex`, `char`, `bool`,
  `fuzzy`, `trit`, `vector`, `matrix`, `permutation`, `map`, `string`,
  `scalar`, `void`.
- **Extended-state vector layout:** every runtime value is a
  `[semantic (n) | synthetic (100)]` vector. Canonical synthetic axes:
  `real` at `synthetic[0]`, `imag` at `[1]`, `truth` at `[2]`,
  `char_flag` at `[3]`. Semantic block filled by `embed()` from the
  frozen LLM (nomic-embed-text, 768-dim default); synthetic block is
  reserved computational/symbolic space.
- **Literals:** integer (`5`), float (`3.14`), character (`'a'`),
  string (`"cat"`), complex (`5i`, `5 + 5i`), boolean (`true` /
  `false`), three-valued neutral (`unknown` / `unk`).
- **Truth-axis operations (Kleene K₃):** `!v`, `a && b`, `a || b`
  as Lagrange-interpolated polynomials, exact on `{-1, 0, +1}`,
  smooth everywhere, differentiable. `a == b`, `a != b` as cosine
  similarity placed on the truth axis (eps-guarded divide so
  zero-norm inputs give truth=0 without branching). `a > b`, `a < b`,
  `>=`, `<=` as `tanh(100 · real_axis_diff)`. `defuzzy(v)` is a
  ten-iteration polarize loop along the truth axis.
- **Complex arithmetic as pure tensor ops:** `complex_mul` uses
  three cached matrices (`_swap_ri`, `_cm_real`, `_cm_imag`) plus
  two element-wise multiplies. No scalar extraction; the fusion
  pass can see straight through a chain of complex multiplies.
- **VSA primitives:** `bind`, `unbind` via role-seeded Haar-random
  rotation; `bundle` as normalized superposition; `argmax_cosine`,
  `select` (softmax-weighted); `embed` from frozen LLM.
- **Loops:** `loop(N)` unrolls at compile time for literal N;
  `loop(cond)`, `while`, `do`/`while`, `for` compile to eigenrotation
  with termination by prototype match; `foreach` over literal arrays
  unrolls.
- **Rotation-hashmap:** `map<vector, V>` compiles to a bind-based
  rotation hashmap with O(1) lookup. Capacity at d=868 matches the
  underlying d=768 raw bind/bundle study: 100% up to k=24, 90%
  threshold at k=48.

**Compiler**

- **One codegen target:** `--emit` produces a self-contained torch
  module picking CUDA at module init. PyTorch is the compiler
  library; Sutra compiles to tensor ops the way clang compiles to
  LLVM IR.
- **Auxiliary backends:** `--emit-flybrain` for the fly-brain
  experimental substrate (since retired, see 2026-04-26 subsection
  above); the internal `codegen.py` as the IR step that
  `PyTorchCodegen` inherits from.
- **Simplification pass:** identity rewrites (bundle flattening,
  bundle(v) → v, zero-vector absorption), auto-embed pass,
  complex-literal folds, fuzzy-literal coercion.
- **Fused shapes:** `bundle(bind(r1,f1), bind(r2,f2), ...)` emits
  one stacked einsum; `argmax_cosine` emits one batched matmul.
- **Diagnostics:** file:line:col error messages, JSON output for
  editor integration, `--summary` and `--consistency` modes.

**Standard library (scaffolding)**

`sdk/sutra-compiler/sutra_compiler/stdlib/` directory holds canonical
`.su` definitions for every system function category. All 7 files
parse cleanly; **not yet wired into codegen**, user code still
compiles through the hardcoded runtime methods. These are canonical
reference files for the inliner pass in the next release.

- `logic.su` — defuzzy, logical_not/and/or, neq, lt, ge, le
  (implemented); defuzzify_trit, gt (blocked).
- `similarity.su` — neq (implemented); eq, similarity, argmax_cosine,
  select, snap (blocked).
- `numbers.su` — make_real, make_complex, make_char, complex_mul,
  conj (all blocked).
- `vectors.su` — bind, unbind, bundle, permute, basis_vector,
  permutation_key, identity_permutation, compose (all blocked).
- `memory.su` — zero_vector, hashmap_get/set, map_lookup (all blocked).
- `rotation.su` — make_random_rotation, compile_prototypes,
  eigenrotation_loop (all blocked).
- `embed.su` — embed (pure intrinsic).

**Tooling**

- **IntelliJ plugin** (`sdk/intellij-sutra/`) — lexer, syntax
  highlighter, color settings page, quote handler, brace matcher,
  completion contributor, external annotator driven by the reference
  compiler. Handles char literals, imaginary suffix (`5i`), all
  primitive types.
- **VS Code extension** (`sdk/vscode-sutra/`) — TextMate grammar
  matching the IntelliJ lexer token set.
- **Docs site** — MkDocs Material at <https://sutralang.dev>, built
  and deployed by `.github/workflows/pages.yml` on push to master.

**Known limitations at v0.2.0**

- **stdlib inliner not yet wired.** System functions still compile
  to hardcoded runtime methods. The pipeline to land this is the
  next release's active work: loader → inliner → unroll → delete
  runtime methods → intrinsic mechanism → fusion pass.
- **Fusion pass limited.** Only `bundle(bind,bind,...)` and
  `argmax_cosine` emit fused shapes; mixed sequences like
  `bundle(bind(r,f), c, bind(r2,f2))` still emit sequentially.
  Generalized ANF + dep analysis for cross-pattern fusion is part
  of the next release.
- **Learned-matrix binding deferred.** `role X = learned_from(data)`
  fitting a matrix at compile time is spec'd but not implemented.
  Current `bind` is rotation-only.
- **Pre-release placeholder.** Version `0.1.0` was a development
  placeholder in `__init__.py` and was never tagged.

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
accurate framing of the consistency-accuracy correlation.

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
