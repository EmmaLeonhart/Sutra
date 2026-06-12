# Sutra — Work Queue

**This file is a queue, not a state snapshot.** It lists what is being
worked on right now and what is next. Finished work lives in `git log`,
`DEVLOG.md`, and `planning/findings/` — NOT here. If you catch yourself
writing "✅ DONE / SHIPPED / RESOLVED" status in this file, stop: delete
the item instead and let git log / DEVLOG / a finding hold the history.
That CRUD is exactly what bloats this queue (2026-05-30 cleanup). Remove
completed items in the same commit as the work (CLAUDE.md §Workflow Rules).

`todo.md` is longer-horizon. Items migrate `todo.md` → `queue.md` →
deleted on completion. Keep the task tool in sync with this file.

---

## 🟢 HANDOFF — READ THIS FIRST (Emma restarting computer 2026-05-30)

**What this session did, in plain terms.** The track is "weight→code" —
recovering a program's source from its learned weights, and building the
training data for that. Two things finished today:

1. **The corpus is built, hardened, and at scale.** Now 3600 small Sutra
   programs (15 structures, incl. 5 inference-forcing families) whose
   behavior is carried by matrices, each paired with its weight matrices
   (CSV files) and its substrate input→output behavior. It lives in its own
   git repo as the `corpus/` submodule (`EmmaLeonhart/sutra-w2c-corpus`).
   Every entry is self-consistency-checked, GitHub + HF mirror in sync.

2. **A first weight→code model works end-to-end.** A small Transformer
   (`experiments/w2c_seq2seq/`) reads a program's weights + IO and GENERATES
   its `.su` source. Trained on 2160 programs, tested on 240 held-out:
   - regenerates the correct source for **202 / 240 = 84.2%**;
   - verified on the real substrate — the generated source, recompiled and
     run, reproduces the held-out IO for the **same 202 / 240**;
   - **0 compile failures.** The 38 misses are all one bug-class: the model
     gets the matrix multiply right but drops the `+x` / `−x` correction
     term in the `diff` / `residual` program families.
   Write-up: `planning/findings/2026-05-30-w2c-seq2seq-substrate-eval.md`.
   Shas: data prep `eb8140a9`, model+train `f9a7ef14`, substrate eval
   `8648a24f`.

**Option A (harden + retrain) — DONE and measured.** All three ticks shipped:
harder families, full 3600-program regen (GitHub `03336b9` + HF `d464fdb`),
retrain + substrate re-eval. The 84.2% *was* templating: on the harder space
exact-match drops to **0.678**, substrate IO-repro to **0.706**, with the
collapse localized entirely to the coefficient families (`chain4` still 1.0).
Write-up: `planning/findings/2026-05-30-w2c-tick3-hardened-corpus-eval.md`.
Next levers (corpus canonicalization, coefficient head) in the "Active — W2C"
section below.

**About the restart.** The hourly crons (work-loop / auto-flush / status /
blocker-sweep) are session-local — restarting the computer kills them and
this session, so the next session must recreate them (see Pinned tail). All
work is committed and pushed. `data/` (dataset + model checkpoint) is
gitignored, so re-running the model means: `git submodule update --init
corpus` → `py experiments/w2c_seq2seq/prepare.py` → `…/model.py` →
`…/eval_substrate.py`.

## ⏰ Scheduled milestones — 2026-06-06 (session-local crons; RECREATE if the session restarts)

Emma set three timed tasks today. The crons are `durable:false` (die on restart),
so if a new session starts before these fire, recreate them:

- **2026-06-07 10:00 (cron `81aab3d7`)** — COMPLETELY UNFREEZE `paper/paper.md`
  (the regular paper) + full audit + update for a NEW submission. Must reconcile
  every claim with the 2026-06-07 substrate-purity findings (no overclaiming
  "pure substrate" / "fused neural network / weight file" as done — that's the
  in-progress target). Update author contact email → `contact@emmaleonhart.com`.
  Do NOT touch `paper/neurips/` (permanent freeze). Commit+push for resubmission.

- **11:30 (cron `7f2732b4`)** — full end-to-end attempt: transpile the COMPLETE
  `WASM/iso/ocaml/bin/main.ml` → Sutra, then HAND-EDIT the output until it compiles,
  runs on the substrate, and reproduces the OCaml machine's reference output (fill
  the transpiler's `UNSUPPORTED` gaps by hand). Compare to ground truth, no faking;
  if the full machine is too big, get the simplest program (`hello`) working
  end-to-end and report what was hand-filled vs transpiled. Save the working `.su` +
  a finding, commit+push. (Has until 12:30 before the PCA pivot.)
- **12:30 (cron `12c5f8b2`, moved from noon)** — PIVOT to PCA on the WASM
  transformer (todo.md TOP PRIORITY); overrides the OCaml grind from then on. (The
  11:30 hand-edit now has a full hour before this fires.)
- **17:00 — DONE.** Third clawRxiv paper created: `paper/percepta-ntm/paper.md`
  (DNC/NTM via the Percepta transformer + PCA + the Turing-complete substrate
  machine); CI `percepta-ntm-paper-ci.yml` wired; pushed (triggers clawRxiv submit).
  The hourly-:30 feedback loop now maintains it.
- **18:00 (cron `3dced803`)** — edit `paper/percepta-ntm/paper.md` to add a Related
  Work / lit-review section if absent, citing at least: Neural Computers (Zhuge et
  al. 2026, arXiv:2604.06425), the DNC (Graves et al., Nature 2016), the NTM (Graves
  et al. 2014, arXiv:1410.5401), + the Percepta transformer-vm blog. Commit+push (a
  second clawRxiv review cycle on the changed paper).
- **HOURLY at :30 (RECURRING cron `bbcdf32c`) — paper feedback loop.**
  Replaces the earlier one-shot 6:30/7:00/7:30 paper crons (deleted). Each cycle on
  main: pull → read newest clawRxiv review (under `paper/percepta-ntm/reviews/`,
  side-by-side with prior) + recent findings → IF something substantive to fold in
  (an unaddressed con OR a new measured finding), adjust the paper and commit+push
  (triggers `percepta-ntm-paper-ci.yml` → next review cycle = continuous feedback);
  ELSE no-op (NO marker-bump resubmission — avoid clawRxiv spam). Skips if the paper
  doesn't exist yet (before 17:00). Auto-expires after 7 days.
- **Paper lifecycle note:** each push triggers a new clawRxiv review cycle on a
  meaningfully-different version (real content / feedback responses), NOT a
  marker-bump. Address load-bearing cons with measurements, not rewording.

Until 11:30: keep grinding the OCaml→Sutra transpiler (ISO-5 items).

**11:30 milestone RESULT (done):** full-machine transpile + hand-edit attempt.
Full machine = 28 UNSUPPORTED markers; it's a stack machine needing substrate
arrays (dict<int,int> broken), bitwise ops (none), and exceptions (none) — can't
run via transpile OR hand-edit until those land. Ground truth unavailable (the
transformer-vm submodule data .txt is not initialized here). NEW measured blocker:
a hand-written substrate fetch-execute loop misfires because **comparing a
loop-carried state var against a LITERAL** (`pc == 2`) defuzzes false even when
equal (state==state and arithmetic are exact) — this breaks per-tick opcode
dispatch, the machine's core. Finding:
`planning/findings/2026-06-06-iso5-full-machine-handedit-and-dispatch-blocker.md`;
artifacts `experiments/iso5_substrate_dispatch/`. Largest runnable fragment:
`to_signed(100)` = 100. Next-direction idea: one-hot opcode masks carried as loop
state (avoid literal-vs-loop-state comparison).

## A.0 — Ask Emma (drain via AskUserQuestion; phone notification)

- **A.0(c) — Axon string fillers — RESOLVED (Emma 2026-06-08): strings are NOT axon fillers.**
  Axon fillers are numbers/vectors only; strings are passed as separate codepoint-array
  values, not inside axons. So the string round-trip "failure" (`a.item("k")`→72='H') is BY
  DESIGN, not a bug. Consequence: OCaml/TS string record fields stay UNSUPPORTED (a record
  with a string field can't be an axon-with-string-filler). Axon vision/docs updated to match
  (`axons.md`); memory `[[project_axon_ipc_payload_is_strings_and_numbers]]` corrected.
  Open-question doc closed: `planning/open-questions/axon-string-filler-roundtrip.md`.

- **A.0(a) — DECISIONS (RESOLVED autonomously 2026-06-07, Emma "do those items autonomously").**
  1. **Boolean representation** — RESOLVED (Emma + spec `equality-and-defuzzification.md:92`):
     a boolean is a scalar on the **truth axis**, +1 true / −1 false, a subclass of
     fuzzy; only compile-time literals may be declared ±1. Comparison ops already
     return exactly this (`eq_synthetic`/`gt`). No truth→real 0/1 conversion — the
     machine holds booleans on the truth axis; BR_IF defuzzes the truth axis.
  2. **RAM address decode** — KEEP as the I/O wire (per `ram-pointers` finding); the
     device-address decode is the legitimate boundary, not in-language introspection.
  3. **JS-interop carve-out** — KEEP ring-fenced (CLAUDE.md intentional-compat
     carve-out); JS shims cross to host BY DESIGN to mimic JS. Not the target of the
     no-introspection purge.
  4. **Verification without readout** — substrate-to-substrate: compare output
     vector to expected vector via a substrate op; the host harness reading the final
     result is the one external terminal boundary (external tooling, not the language).
  5. **Axon field decode (NEW sub-task)** — `.item("field")` returns an axon FILLER,
     not a clean number-vector; arithmetic on it collapses to ~0 (measured 2026-06-05),
     which is why tuple/record/option field reads emit `.real()`. Removing it needs a
     substrate filler→number-vector decode primitive (NOT `.real()`). Real work, not a
     blind removal. RAM reads (array) are exempt — RAM stores clean number-vectors.

## ⭐ TRACK COMPLETE — Neural Turing Machine via PCA + codable attention (Emma 2026-06-08)

**Emma's call (2026-06-08, AskUserQuestion): the content-addressing thread is DONE — the
key/value-VECTOR associative recall IS the intended demonstration; do NOT build content-
addressing over the RAM device. Move on (transpiler track / composed-network training).**
So the whole arc shipped + measured: build (attention-on-RAM parser, 3 tasks substrate-
exact) → compare (evaluate vs SGD-learn agree) → reduce (dim floor 3) → content addressing
(soft learns / hard inert; differentiable on the substrate via select+similarity;
sharpens to crisp retrieval in a finite-β window) → packaged as a runnable `.su`
(`examples/content_addressed_read.su`, NTM read head, 3/3). NEXT EFFORT = transpiler track
(below) per CLAUDE.md priority-1. Do NOT re-open "content-address the RAM device" (Emma
declined it). The detail below is retained as the record of what was built.

DONE (removed from this queue per the queue-cleared rule; see DEVLOG + git log): the
substrate-purity -> fused-NN overhaul is complete — `real()`/scalar extraction removed
ENTIRELY (language is substrate-pure; `realvec(v)` is the on-substrate replacement;
host-readout gate 18, remaining are by-design I/O/JS/control boundaries); loop step
fuses + exports as a weight file (#6/#7); the main Sutra paper was re-run on the pure
substrate (data reproduces EXACTLY — §3.2 100%@k=8, §3.7 ~2e-7) and cleaned of all
leak/in-progress narrative, pushed (4b49946e).

### NTM track — Emma's REFRAMED vision (NOT a trainable NTM; do NOT chase clawRxiv bot)
Use **PCA on Percepta's `transformer-vm`** + **Python->OCaml** to build something
**identical in structure** to that transformer but that uses an **attention mechanism
for simple straight-up parsing** ("attention on RAM"). Percepta's artifact is not
literally an NTM and neither is ours — it is in the same *ballpark* (one of the three
Turing-completeness archetypes: RNN / reservoir / NTM — see the metabolised roadmap in
todo.md). The thing must be **codable**; SGD could later change where it does its
memory (optional, future). Do NOT iterate the percepta-ntm paper against clawRxiv cons
(not the vision); the paper advances only from real vision-aligned measured findings.

STATE (measured): PCA done — magnitude-PCA is the wrong lens (1e30 dynamic range); the
reducible structure is the exactly-zero parts (2 zero attention sublayers; 42/133 used
heads). Pruned core BUILT + verified output-IDENTICAL to full on 8/8 random inputs
(experiments/wasm_transformer_pca/repack_reduced.py; finding
2026-06-07-pruned-transformer-repack-reduced-core). Findings:
planning/findings/2026-06-0{6,7}-{pca,pruned}-*.

NEXT (concrete, in order):
1. UNBLOCK the 6-program byte-for-byte oracle (task #1). The canonical .wasm +
   token-prefix + reference `_ref.txt` fixtures need clang/uv, ABSENT locally. Route
   generation through a clang-equipped GitHub Actions job (runners have clang/llvm):
   run ensure_data() + generate_all(), commit the fixtures back (the model papers-ci
   uses). Then verify the pruned core reproduces all 6 byte-for-byte (decoded == ref,
   MEASURED — not "ran").
2. The reframed build: PCA-reduced core -> Python->OCaml -> a codable attention-parser
   ("attention on RAM" for parsing). DESIGN DOC + BUILD (a)(b)(c) DONE:
   `planning/exploratory/codable-attention-on-ram-parser.md`; one constructed (untrained)
   attention head reading a RAM tape, three parse tasks RUN ON THE SUBSTRATE exact to the
   Python oracle (`attn_sum_tape`=10, `attn_dot_tape`=-2 [linear regression over memory],
   `attn_select_field`=22; finding `2026-06-08-attention-on-ram-substrate.md`; CI-guarded
   `_RUNNABLE_FIXTURES` + `experiments/attention_on_ram/`). O1/O2 RESOLVED by measurement
   (linear attention = exact weighted sum, no softmax needed; hard-addressing = indexed
   RAM read; O2: accumulator-in-RAM + scalar-index-slot is the substrate-correct loop
   shape, the mini_wasm_machine pattern — a `ref` accumulator can't hold a vector ramRead).
   O3 ANSWERED (Emma 2026-06-08): "do all of them so we can compare them". COMPARISON SET
   COMPLETE + MEASURED: `sum_tape`/`dot_tape`/`select_field` (constructed, substrate-exact)
   + the SGD-fit soft read (`ntm_ram/trainable_read.py`). The evaluate-vs-learn comparison
   (`attention_on_ram/compare_variants.py`, guard `test_evaluate_and_learn_agree`) shows
   constructed-eval (max|ŷ-y|=8.9e-16, exact) and SGD-fit (recovers c, ‖w-c‖=6e-8) realize
   the SAME linear-regression-over-memory operator (agreement 2.2e-7). Finding
   `2026-06-08-attention-on-ram-evaluate-vs-learn.md`.
   (d) DIM REDUCTION DONE (measured): all three fixtures pass at the FLOOR runtime_dim=3
   (synthetic-axis minimum, semantic_dim=0 — zero LLM capacity, 0 basis_vector), ~13-16×
   below the transformer-vm's d=38 / the CLI default. Sweep `attention_on_ram/dim_sweep.py`,
   guard `test_parser_reduces_to_synthetic_axis_floor`, finding
   `2026-06-08-attention-on-ram-dim-reduction.md`.
   CONTENT-BASED ADDRESSING (Emma 2026-06-08, the NTM/DNC hard part): editing RAM
   normally / hard-argmax / fixed-coefficient reads are the easy, inert side; the
   load-bearing thing is content-based SOFT addressing (softmax over query·content), where
   the gradient flows through the addressing so the system LEARNS WHERE TO LOOK. MEASURED
   (`content_addressed_read.py`, guard `test_content_addressing_soft_learns_hard_inert`,
   finding `2026-06-08-content-based-addressing-soft-vs-hard.md`): soft read learns content
   retrieval (loss→0, attends target weight 1.0, ‖∇q‖=0.48); hard/argmax read is
   differentiable-on-paper but INERT (‖∇q‖=0, never learns). This is the
   "theoretically-differentiable vs does-stuff" line Emma drew.
   >>> SUBSTRATE SOFTMAX — RESOLVED BY DISCOVERY (grep-first): the primitive ALREADY EXISTS.
   `select(scores, options)` (`_select_softmax`, spec 26-select-and-gate.md) is the
   autograd-preserving softmax read; `similarity(q,k)` is the content match. Content-based
   addressing on the substrate = `select([similarity(q,K_i)...],[V_i...])` — exactly
   `examples/fuzzy_dispatch.su`. MEASURED differentiable on the substrate
   (`substrate_content_read.py`, guard `test_substrate_select_content_read_is_differentiable`,
   finding `2026-06-08-substrate-content-addressing-via-select.md`): soft read learns
   directionally (‖∇q‖=0.028, cos→0.80); hard argmax inert (‖∇q‖=0). Did NOT build a
   redundant softmax. MEASURED LIMITATION: `select` has fixed β=1, so the read stays a
   diffuse blend (weight_on_target 0.37) — sharpening is a β/temperature lever (NOT a
   differentiability issue), ties into existing `experiments/select_temperature_adjustment.py`.
   SHARPENING — DONE (measured): with a temperature (score-scaling `similarity/T`, the
   established select-temperature lever, no primitive change) the substrate content read
   sharpens from diffuse (β=1: cos 0.80/weight 0.37) to CRISP retrieval (β=16: cos 1.0/
   weight 0.9998, ‖∇q‖=0.35, gradient still flows); β=64 (toward hardmax) COLLAPSES (cos
   0.06) — a finite-β "does-stuff" window between diffuse and saturated. Finding
   `2026-06-08-substrate-content-addressing-temperature-window.md`, guard
   `test_substrate_content_read_sharpens_with_temperature`. The content-addressing thread
   is complete + measured on the substrate (differentiable + sharpenable, no new primitive).
   `.su` PACKAGING — DONE: `examples/content_addressed_read.su` is the NTM read head as a
   runnable Sutra program — associative recall via `select`+`similarity` content addressing
   with a BETA=8 temperature; 3/3 keys retrieve the right value on the substrate
   (red→apple, green→leaf, blue→sky), guarded in `examples/_smoke_test.py` (Example 7b).
   >>> REMAINING (separable, low urgency): a TRAINABLE-query `.su` (the host loop already
   trains a query through the compiled select); training the composed reduced network
   end-to-end (still open research).
   REMAINING: grow the example set (more parse tasks/tapes) per design doc §5; O4
   (head/operator-count reduction — fresh-isomorphic one-head construction is already the
   single-read minimum; a multi-head parse would be the next comparison) = my engineering
   call, low priority. The attention-on-RAM track's core deliverables (build + compare +
   reduce, all measured) are DONE; what remains is breadth, not feasibility.

HARD RAIL: every step RUN + verified substrate-to-substrate (decoded output ==
reference); no faking; measure, don't claim. Use engineering judgment; do NOT ask Emma
incomprehensible low-level questions.

## Context (read first, do not work on)

- **`paper/paper.md` is UNFROZEN (Emma 2026-06-07)** — arXiv lock lifted (was
  through May 31); now the live revision target for a new submission, audited
  against measured reality. `paper/neurips/` stays under its own **permanent**
  freeze (do NOT touch). Integrity discipline still applies (measured numbers
  only; no overclaiming substrate-purity/fused-network as done).
- **Promise/await is fit-to-spec** (verified 2026-05-20;
  `test_await_substrate_pure.py` 4/4). Guarded by the watchdogs below.

## 🌐 Merged queue — from the Neural WebAssembly (`WASM/`) repo

> **Origin banner.** These items were merged in from the `queue.md` of the
> **Neural WebAssembly** repo (`EmmaLeonhart/neural-webassembly`, local dir
> `replicating-neural-computers-2`) when it was subtreed into `WASM/` on
> 2026-06-06 (full history, no squash). Completed WASM items (replication 6/6,
> ISO-1..4, learned-ops E0–E2/E4, E3a) are NOT carried over — they live in
> `WASM/devlog.md` + that repo's git log. Long-horizon WASM items are in the
> merged agenda at the top of `todo.md`. Overview: `docs/neural-webassembly.md`.

- **ISO-5 — WASM machine in Sutra (substantially advanced 2026-06-06).** The
  transpiler (`sdk/sutra-from-ocaml/`) now lowers the OCaml constructs the machine
  needs (value bindings, hex, sequences + ref mutation, while→loop, char/string,
  nested-fn, tuples, match incl. catch-all + option, let-in-expr, mod, bitwise
  land/lor/lxor + lsl/lsr, arrays→RAM, failwith→sentinel). OCaml suite 79 passing.
  Substrate primitives shipped + verified: bitwise stdlib (band/bor/bxor), arrays→RAM
  (ramRead/ramWrite + RAM-device hardening). **CAPSTONE: a RAM-state WASM stack machine
  RUNS on the substrate** and is now TURING-COMPLETE (21 opcodes 0-20:
  HALT/CONST/ADD/SUB/MUL/AND/BR_IF/LOAD/STORE/EQ/LT/OUTPUT/OR/XOR/DUP/SWAP/DROP/GT/GE/
  LE/NE + backward BR_IF memory loop: counter loop N=1/3/5 -> acc N, factorial(3)=6;
  comparison equality boundaries gated by clean ==; CI-guarded 30/30 in
  test_mini_wasm_machine.py)
  — RAM memory + fresh-`ramRead` dispatch + conditional-no-op-write side effects +
  HALT (= `raise Exit`); host-driven steps dodge the v1 one-slot-`recur` limit.
  Findings: `planning/findings/2026-06-06-iso5-*`,
  `2026-06-06-substrate-comparison-equality-boundary.md`; artifacts
  `experiments/iso5_substrate_dispatch/`. The four hard substrate questions
  (memory/dispatch/multi-state/side-effects) are answered with measurements.
  **Remaining:** breadth (the other ~23 opcodes — same blended dispatch; arithmetic
  DIV/REM, shifts SHL/SHR, more stack ops); a SCALABLE
  RAM device for the 10MB linear memory (host RAM-list doesn't scale); ground-truth
  .txt build (BLOCKED: `uv`/`clang` missing locally; `iso_equiv.sh` uses WSL).
- **PCA on the WASM transformer (todo.md TOP PRIORITY — ACTIVE; first pass DONE).**
  Built the analytic transformer (MILP, 5.7s; `plan.yaml` cached; needs `pulp`+
  `highspy`, now pip-installed) and SVD'd every weight matrix. Finding:
  `planning/findings/2026-06-06-pca-wasm-transformer.md`. Headline: the model is
  already tiny (d=38, 144,286 params) and magnitude-PCA is the WRONG lens — weights
  span ~1e30+ dynamic range (hardmax/address switches), so energy-rank is a
  giant-SV artifact (importance ≠ norm). Concretely reducible: (a) `attn.5`+`attn.6`
  are ALL-ZERO (2/7 attention layers prunable), (b) token/head embeddings are ~3/38
  rank @99% energy (915-vocab ≈ 3-d). The attention CORE must be reduced from the
  computation graph/schedule, not SVD. Script `experiments/wasm_transformer_pca/`.
  Graph-level attention usage DONE: only 42/133 nominal heads attend (31.6%; peak 11/
  layer over layers 0-4; L5/L6 zero) — the genuine reduced-attention target for the
  DNC. Remaining: feed all numbers to the 17:00 paper.
- **PRUNED TRANSFORMER — build the reduced core + verify (Emma greenlit 2026-06-06,
  "Full pruned core + verify").** The positive result the PCA only diagnosed: actually
  construct the smaller transformer and confirm it still executes WASM. Staged:
  - **STEP 1 DONE (2026-06-06):** dropped the 2 all-zero ATTENTION SUBLAYERS
    (`attn.5`,`attn.6` — measured exactly zero; layers 5/6 keep non-zero FFNs so it's
    the attention sublayer only, not whole layers). Verified output-preserving
    token-for-token on 5/5 random inputs; −11,552/146,680 params (7.9%). Script
    `experiments/wasm_transformer_pca/prune_zero_attention.py`; finding
    `planning/findings/2026-06-06-pruned-transformer-step1-zero-attention.md`.
  - **STEP 2 DONE (2026-06-06):** measured that all 91 idle head-slots are *fully*
    zero (V rows AND out_proj cols exactly zero, not just Q/K), so dropping them is
    lossless — output-preserving on 5/5 random inputs. 68% of attention params are
    zero; the model uses 42/133 heads. Script `head_prune_verify.py`; finding
    `planning/findings/2026-06-06-pruned-transformer-step2-head-pruning.md`.
  - **RE-PACK DONE (2026-06-07):** built the concrete reduced model — per-layer attention
    sliced to its used heads ([7,5,11,11,8,0,0]=42/133), attention params 40,432→12,768
    (68.4% removed); output-IDENTICAL to full on 8/8 random inputs (exact, since removed
    rows/cols are zero). Script `repack_reduced.py`; finding
    `planning/findings/2026-06-07-pruned-transformer-repack-reduced-core.md`. The pruned
    core is now BUILT + locally verified; only the canonical 6-program oracle remains.
  - **STEP 3 DONE (2026-06-06) — NEGATIVE:** the token/head embedding has 99% energy
    in 3 dims but is NOT SVD-compressible at ANY rank — even the full rank-38 round-trip
    (1.1e-12 reconstruction error) flips the output, because the 1e5 head + 1e10 hardmax
    amplify any perturbation. Confirms magnitude≠importance even for the embedding;
    fixed the paper's overclaiming "low-rank vocab" bullet to match. Script
    `vocab_compress_verify.py`; finding
    `planning/findings/2026-06-06-pruned-transformer-step3-embedding-not-compressible.md`.
    So the only output-preserving reductions are the exactly-zero ones (steps 1-2).
  - **VERIFICATION DECISION (Emma 2026-06-06): commit wasm/token fixtures.** Generate
    the 6 programs' `.wasm` + token prefix `.txt` + reference `_ref.txt` ONCE on a
    clang-equipped environment and COMMIT them, so the byte-for-byte oracle becomes
    runnable locally forever with no toolchain. This machine has no clang/uv, so the
    one-time generation routes through a clang-equipped path: preferred = a GitHub
    Actions job (runners have clang/llvm) that runs `ensure_data()` + `generate_all()`
    and commits the fixtures back (like the paper CI commits reviews); fallback = WSL
    or Emma's other machine. After fixtures land: steps 2/3 verify byte-for-byte
    against them (plus random-input equivalence for fast local checks). Multi-session;
    local submodule branch for model edits (don't push to Percepta).
  HARD RAIL: "still works" means decoded output == reference, measured, not "ran".
- **E3 — integrate a native `i32.sat_add_u` opcode (spec done; impl remaining).**
  Spec `WASM/notes/e3_native_opcode_spec.md`; E3a verified the `op_dot` vocabulary
  extensible (28 spare points). Remaining = the build (own session): add to
  `OPCODES`/`STACK_DELTA`, `result_byte`/`result_carry`, `reference.py` + both
  isomorphs, `compile_wasm.py`, a test program; rebuild weights (MILP solves);
  end-to-end vs reference; no regression on 6 programs; re-run `iso_equiv.sh`.
  On a local submodule branch (don't push to Percepta).
- **Optional — hull Python path.** `apt install python3-dev`, then
  `uv run wasm-eval --hull` / `pytest -m "not slow"`; quantify hull (O(log n)) vs
  `--nohull` to substantiate the attention-scaling claim.
- **Yantra OS integration** — forward goal; design in
  `WASM/notes/yantra_integration.md`; phased P0–P6 in the merged `todo.md` agenda.

## Active — RAM inline `await ramRead` surface syntax (Emma chose 2026-06-01)

Goal: `number x = await ramRead(pointer);` / `ramWrite(pointer, data);`
compile + run directly in `.su` (today only the hand-wired
`experiments/ntm_ram` harness does it). **Studied 2026-06-02:** the
Stage-1 desugar (`promise_desugar.py`) ALREADY lowers inline `await x` →
`Promise.await_value(x)` and handles the `v = await x; return g(v)`
continuation — so no new continuation transform is needed. The gap is the
**external producer**: `await_value` currently short-circuits to
`value(p)` (no producer wired). Per `promises.md` (await resolves when an
external producer populates the slot) + `ram-pointers.md` (the RAM
device/orchestrator is that producer), the spec-grounded design — NOT a
substituted synchronous variant — is:

**DONE (steps 1-2 + tests, 0587e6b8 + this commit):** `_VSA.ram` device +
`ram_read`/`ram_write` (round-to-nearest, OOB→zero); `ramRead`/`ramWrite`
codegen builtins. Measured working + guarded (`test_ntm_ram.py`
`TestRamInlineSurface`, 4 cases):
- synchronous `ramRead(ptr)` / `ramWrite(ptr, data)` (any function);
- `number x = await ramRead(ptr)` inside an **async** function (flows
  through the existing promise desugar → `await_value` passes the
  already-resolved device read through — no `await_value` change needed,
  `test_await_substrate_pure` 4/4 intact);
- the **NTM read head as a `recur` loop using *synchronous* `ramRead`**:
  per-tick reads advance on the substrate (cursor is a recurring VRAM
  tensor; `real()` is the I/O-wire address decode — state-locus holds).

**Realization note (honesty):** the inline surface compiles to a
synchronous read of the host-attached `_VSA.ram` device (matches Emma's
"RAM is a discrete IO device you read/write" framing). The separable-
orchestrator VRAM-mailbox model (request emitted as substrate data for a
*separate* process) is the distinct `experiments/ntm_ram` harness, kept
for the multi-program/Yantra IPC story.

**Remaining:**
1. **`await` inside a non-async `recur` (Emma's exact read-head example)
   — BLOCKED on the await-lowering phase.** Measured: it hits
   `CodegenNotSupported` ("await lowering to a gated while_loop not yet
   implemented"; promises.md). The synchronous-`ramRead`-in-`recur` form
   above already gives the NTM read head functionally; the `await`
   keyword in non-async recur is sugar pending the await→while_loop
   lowering (the larger async/recur-composition work). Do NOT hack the
   desugar to process non-async recur without settling that semantics.
2. ~~Migrate a demo to the inline surface~~ **DONE:**
   `experiments/ntm_ram/text_scan_inline.su` + `run_inline_demo.py` — a
   `recur` read head calling inline `ramRead(cur)` against a host-attached
   `_VSA.ram`; decodes "HELLO, RAM!" exact (guarded by `test_ntm_ram.py`,
   11/11).

Open follow-up (todo.md): await→while_loop lowering for recur+await;
model-free hash-keyed-role axon for the mailbox dim cost.

## Active — W2C weight→code (option A hardening complete; next levers)

### HF mirror — DONE (7200 sharded corpus live); orphan cleanup low-priority (default: leave)

Resolved the HF 10000-files/dir rejection by sharding into 20 per-seed
subdirs (`s{seed}/`). Submodule `3b33e5e9` (GitHub) + generator + migration
`experiments/shard_corpus_to_subdirs.py`. HF re-mirror succeeded (commit
`6ffae459`): the 7200-program sharded corpus is on HF and referenced by
`corpus.jsonl` — usable. Verified spot-check 6/6 IO + full `prepare`
(6480/720), no path errors.

**Loose end (low priority — default = leave):** `upload_folder` doesn't
delete, so 5760 flat CSVs from the old 1× layout remain on HF as
unreferenced orphans (harmless duplicate cruft + 2× storage; the dataset
is fully usable via `corpus.jsonl`). Not blocking anything. If a tidy-up
is wanted later: precise explicit-path delete of the flat files (NOT a
`*.csv` wildcard — recursive, would nuke the sharded CSVs) + harden
`mirror_corpus_to_hf.py` to prune stale files on each mirror.

Hardening done (all 3 ticks): generator harder families, full 3600-program
regen + GitHub + HF, **and retrain + substrate re-eval**. Result measured and
written up: `planning/findings/2026-05-30-w2c-tick3-hardened-corpus-eval.md`.
Headline: exact-match 0.842→**0.678**, substrate IO-repro 0.842→**0.706**, 0
compile/run fails, first **10 behavioral wins**. The drop is localized to the
coefficient axis — `chain4` (deepest chain) is solved 1.0, every coefficient
family collapses (`scaled_res` 0.083, `scaled_diff` 0.125, `gen_affine` 0.25,
`two_mat_affine` 0.33 exact). Unit-coeff cases exact 0.000 (model correctly
simplifies `1.0 *` away — corpus artifact); non-unit cases exact 0.241 (real
inference, mostly fails). This validates option A: structure transfers, scalar
coefficients do not.

**Follow-up #1 — DONE (eval-side canonicalization).** `eval_substrate.py` now
reports `exact_match_canonical` (strips redundant `1.0 *`) + per-structure
`exact_canon_rate`; guard `canonicalize_source` test in `test_eval_substrate.py`
(6/6). Measured: canonical exact 244→**254 = IO-repro exactly**, in every one of
the 15 families — so the "10 behavioral wins" were a pure scoring artifact, not
equivalent-code diversity (tick-3 finding Corrected). Generator-side
canonicalization is now optional (corpus cleanliness only, no metric impact);
deferred unless we regen for another reason.

**Follow-up #2 — DONE (coefficient WALL, 3 levers exhausted).** The coefficient
head diagnostic + both follow-on levers are written up in
`planning/findings/2026-05-30-w2c-coeff-head-diagnostic.md`. Net: the coefficient
is only ~½ decodable from the encoder rep (~0.60 probe / ~0.30 coeff-family IO),
and all three architecture levers came back negative/null — aux loss (hurts the
decoder), post-hoc substitution (0.61 head too weak), matmul input feature (no
movement). weight→code recovers *structure* near-perfectly (chain4 = 1.0) but
scalar coefficients are a wall for this architecture.

**Scale model + corpus (Emma 2026-05-31 decision) — both halves DONE & measured.**
1. **Bigger model — NOT capacity-bound.** d256/L6 (≈4–8× params) left the probe
   flat (~0.60), coeff-family IO flat-to-down (0.31→0.23). Readout, not capacity.
2. **Bigger corpus (2×, 7200) — HELPED, contradicts the architectural read.**
   Same d128/L3, 40 epochs, 2× data: decoder exact 0.689→**0.811**, canonical/IO
   0.714→**0.825**, coeff-family IO 0.31→**0.41**. The coefficient wall is at
   least partially **data-bound**, not purely architectural. Still far from
   solved (0.41) and the gain bundles more-data + more-steps. Written up in the
   coeff-head finding § "Bigger-corpus test". Scratch only — NOT pushed to
   submodule/HF (the official-push decision is Emma's; see A.0).

## Corpus (built & at scale — not active work)

The weights↔code corpus is built and at **7200 programs** (15 structures ×
6 K {4,6,8,10,12,16} × 4 weight-kinds × 20 seeds; scaled 1×→2× 2026-06-01,
submodule `3b33e5e9`, CSVs sharded into `s{seed}/` subdirs), on the
`corpus/` submodule (`EmmaLeonhart/sutra-w2c-corpus`) + HF mirror
(commit `6ffae459`, 7200 corpus live + referenced; 5760 old-layout flat
orphans remain to be pruned — see A.0). Consistency-guarded
(`test_weight_to_code_corpus.py`, `test_gemma_codegen_corpus.py`).
Scale further = one-flag bump (`--seeds`/`--ks`) on
`experiments/weight_to_code_corpus.py` → push submodule →
`experiments/mirror_corpus_to_hf.py` → bump the Sutra pointer + card stats.
Open/deferred: a category/semantic *trained* weight-kind (needs embeddings;
heavy 768²/nomic, uncertain value at small K). Detail: DEVLOG 2026-05-29/30.

## Formal verification (roadmap lives in formal-verification.md + todo.md)

Discharged set + open obligations are authoritative in
`planning/sutra-spec/formal-verification.md` (key-soundness discharged
2026-05-29). Remaining substantive work, in order: (1) k=8 → real capacity
curve; (2) PIT term-count honesty; (3) widen/tighten the decided fragment;
(4) general obligation checker. These are longer-horizon → `todo.md`.
Keep `paper/formal-verification/paper.md` updated as each lands (CI
auto-submits to clawRxiv on push).

## Watchdogs (verification, not new work)

- Hourly local cron: runs `test_await_substrate_pure.py` + greps
  `codegen_pytorch.py` for the `await_value` leak signatures; reopens an
  item here if anything regresses.
- Daily remote routine (claude.ai cloud): spec-audit pass over
  `planning/sutra-spec/*.md` vs the runtime; commits findings.
- Daily substrate-honesty audit (`.github/workflows/daily-audit.yml`)
  prepends an audit item; discharge it (review commits since the last
  audit vs CLAUDE.md §"Subtler substrate breaches") then delete it.

## Next-venue paper polish (UNFROZEN 2026-06-07 — active)

`paper/paper.md` is unfrozen and editable. Ablation
table; polynomial-interpolant-rationale paragraph (prose in `git show
41fa446b`); Le Chat section-granular AI-use breakdown; optional Futamura
1971 bib entry.

## Transpiler track (source -> Sutra; OCaml first) — 1pm cron, owns this section only

Roadmap: todo.md §"Multi-language transpiler frontends".

**PRIORITY ORDER (Emma 2026-06-05):**
**(1) OCaml first** — keep advancing it; it fits Sutra best and is the most
complete *verified-running* frontend, so it's the reference impl for the rest.
**(2) Fix TypeScript** (the axon-`.real()` runtime bug below).
**(3) The other languages**, in roadmap order: **Scala -> F# -> Elixir/Erlang
-> Clojure -> Haskell -> then Rust -> then WASM.** Each is scaffolded below so
it's documented even before work starts; new frontends model on
`sutra-from-ocaml` (not `-ts`, which has the latent axon bug).

This section is driven by the 1pm transpiler work-loop cron; it pulls+rebases
first and never touches the RAM/W2C sections above.

### Priority 1 — OCaml frontend (`sdk/sutra-from-ocaml/`)
- **ISO-5 now drives the OCaml priority order.** The bounded items needed to port
  `WASM/iso/ocaml/` to Sutra (sequence-expr + mutation → while/for → substrate
  loop → chars/strings → arrays → tuples/option → nested-fn) are the highest-value
  OCaml work; see the merged-WASM-queue ISO-5 item + `planning/findings/
  2026-06-06-iso5-ocaml-to-sutra-gap-analysis.md`. [Top-level value bindings
  (`let x = const`) → Sutra top-level constants: DONE — hex/oct/bin/`_`/width-
  suffix number literals normalized to decimal; substrate-verified `toplevel_const`
  `(300 - 0xFF) + 5 = 50`. Sequence-expr + ref mutation (`e1;e2`, `ref`/`:=`/`!`):
  DONE — substrate-verified `seq_mut` = 15. `while`→substrate `loop` (scalar-ref
  shape): DONE — substrate-verified `while_sum` = 10. Char→codepoint-int +
  string→String literal: DONE — substrate-verified `char_code` = 65, compile-verified
  `string_lit`. Closed nested-fn hoisting: DONE — substrate-verified `nested_fn` = 16
  (closures correctly UNSUPPORTED). Arrays BLOCKED on core-compiler `dict<int,int>`
  defect (finding 2026-06-06-dict-int-keys-broken). Tuples→positional axon + fst/snd:
  DONE — substrate-verified `tuple_fst_snd` = 16. Match catch-all name binding
  (`| x -> body`): DONE — substrate-verified `match_bind` = 6. Option Some/None
  (tagged axon, body-position match): DONE — substrate-verified `option_some` = 42
  (None path = 7). `let..in` in expression position (simple-atom): DONE —
  substrate-verified `let_in_expr` = 20. `mod`→`%` + bitwise-op-passthrough fix
  (now UNSUPPORTED-OP): DONE — substrate-verified `modulo` = 2. Axon-returning-call ->
  local typed Axon: DONE — substrate-verified `tuple_local` = 16. OCaml suite 71 passed.]
- [ ] `let rec` — **tail-recursive accumulator shape DONE** (`let rec f p… =
  if COND then BASE else f a…` → Sutra `while_loop`; substrate-verified
  `sum_to 0 5 = 15`). Remaining: (a) **non-tail recursion** (factorial-shape,
  recursive call inside a larger expression) — still correctly UNSUPPORTED; needs
  a bounded-depth encoding, open question. (b) **Non-comparison halt conditions: DONE** —
  `_negate_cond` now negates any boolean halt (`&&`/`||`/bool-flag/`not`) via Sutra `!(…)`,
  keeping precise `_NEG_CMP` for comparisons; substrate-verified `tail_rec_bool` = 15
  (`if (n=0)||(acc>100) then acc else f (acc+n) (n-1)`). [Simultaneous swap-update: DONE —
  temp-based update, substrate-verified `swaploop 7 9 2 = 7`.]
- [ ] `match … with`: **literal + trailing `_` DONE** (`classify 1 = 200`) and
  **nullary-constructor patterns DONE** (variant match, `label Green = 200`,
  substrate-verified; last case is the base, exact for exhaustive variant matches).
  **Or-patterns DONE** (`| 1 | 2 | 3 -> r` → disjunction of `==` tests via `||`;
  substrate-verified `match_or` = 300). **Catch-all name binding DONE** (`match_bind`).
  **Guarded patterns DONE** (`| x when x>0 -> …` → test = guard, or `(pat==k) && guard`;
  bound name substituted via `_MATCH_SUBST`; substrate-verified `match_guard` = 60).
  **Record-destructuring DONE** (`| {x; y} -> body` → bind each field to
  `realvec(scrut.item("f"))`, irrefutable terminal; substrate-verified `match_record` = 16).
  **Constructor-with-args patterns DONE** (`| Lit x -> x` binds the payload to `_vval`;
  `| Pair (a, b) -> a + b` binds a (parenthesized) tuple pattern component-wise to `_val{i}`;
  substrate-verified via `variant_arg`, `variant_multiarg`). The paired construction side
  (single-arg, nullary, multi-arg, all argument positions) is also DONE — see the
  constructor/aggregate group below.
- [ ] **Records -> axons: DONE for numeric fields** (substrate-verified
  `getx (mk 7 9) = 7.0`). `type X = {…}` erased + record-name prepass; record-typed
  params -> `Axon`; construction `{x=a;y=b}` -> `Axon r; r.add("x",a); …`; field
  access `p.x` -> `p.item("x").real()`. Key finding (`planning/findings/2026-06-05-
  axon-field-reads-need-real-projection.md`): numeric axon field reads REQUIRE
  `.real()` — without it they return zeros on the substrate. No type-tracking layer
  was needed (OCaml `p.x` is unambiguously a record field via `field_get_expression`).
  **Record literals in argument position: DONE** (`f { x = 7; y = 9 }` → hoist the record
  to a temp Axon local before the call; substrate-verified `record_arg` = 16; covers
  body-position calls — nested under operators like `f{..}+g{..}` is a follow-on recursive
  hoist). **Tuple literals in argument position: DONE** (`f (7, 9)` → hoist to a temp
  positional Axon, same machinery; substrate-verified `tuple_arg` = 16). **Non-numeric
  (string) record fields: UNSUPPORTED BY DESIGN** (Emma 2026-06-08: strings are NOT axon
  fillers — axon fillers are numbers/vectors only, strings are separate codepoint-array
  values). The measured `add("name","Alice")`+`item("name")`→65 collapse is expected, not a
  bug to fix. Numeric record fields remain the supported scope; finding
  `2026-06-08-ocaml-nonnumeric-record-fields-blocked-axon-string.md`. (Nullary **variants** ->
  enum ints + constructor-pattern `match`: DONE — `label Green = 200`.)
- [ ] **Parameterised constructors `C of t` (single-arg ADTs) — DONE for construction-via-helper
  + match (2026-06-08).** A variant with any parameterised ctor uses a UNIFORM tagged-axon
  `{_tag,_val}` for ALL its ctors (`_VARIANT_CTORS`, prepass); nullary-only variants stay enum-int
  (`_CONSTRUCTORS`). Construction `C x` in body position -> `{_tag:idx,_val:x}` (Axon-returning fn);
  the variant type name maps to `Axon` for params; match `| C x -> … | D -> …` reads `_vtag`/`_vval`
  and blends by tag, binding the payload to `_vval`. Substrate-verified `variant_arg` = 2
  (`eval (Lit 7) + eval (Neg 5)` = 7 + (-5)); option/enum-variant fixtures green (full suite).
  **Construction in ARGUMENT position: DONE** (`eval (Lit 7)` → the aggregate-arg hoist now
  hoists variant values to a temp tagged Axon, same as records/tuples; substrate-verified
  `variant_arg_pos` = 7; body-position calls, like the record/tuple hoist).
  **Direct construction in LOCAL-BINDING position: DONE** (`let z = Zero in …` / `let a = Lit 7
  in …` → `_lower_local_binding` detects `_variant_value_kind` and emits the tagged-axon
  construction into the binder, same machinery as body/arg positions; nullary stores `_val`=0;
  substrate-verified `variant_nullary_value` = 7 = `let z = Zero in let a = Lit 7 in eval z +
  eval a`). The helper path (`let a = lit 7` via an Axon-returning fn) was already covered; this
  is the direct-constructor case.
  **Multi-arg constructors (`C of a * b`): DONE.** Arity is now counted from the payload type
  components (prepass; `Pair of int * int` → arity 2), construction stores `_val0`/`_val1`/…
  (single-arg keeps `_val`, backward-compatible), `_variant_value_kind` extracts the tuple
  components from `C (a, b)`, and the variant match reads `_val{i}` + binds a (parenthesized)
  `tuple_pattern` component-wise. Works in body, local-binding, AND argument position (shared
  hoist machinery). Substrate-verified `variant_multiarg` = 16 (`let q = Pair (7,9) in let r =
  Origin in sum_pt q + sum_pt r` = (7+9)+0; `| Pair (a, b) -> a + b`). Param must be annotated
  (`(p : point)`) so it maps to `Axon`, same requirement as single-arg.
  **Aggregate args nested under operators (`f {..} + g {..}`): DONE (the shared recursive
  hoist).** `_hoist_aggregate_args_deep` walks the return expression, hoists every aggregate
  -literal call argument (record / tuple / variant construction) anywhere in the tree to a temp
  Axon (`_ah0`, `_ah1`, …), and registers each node in `_ARG_HOIST` so `_lower_expression`
  emits the temp at the call site (nested calls recursed into; aggregate-in-aggregate-field left
  to lower normally). Benefits records, tuples, AND variants at once. Substrate-verified
  `aggregate_arg_nested_op` = 12 (`getx {x=7;y=9} + eval (Lit 5)` = 7 + 5).
  **Top-level ctor value binding (`let z = Zero` / `let p = Pair (7,9)` at module scope): DONE.**
  The zero-param top-level value-binding path detects `_variant_value_kind` and emits a top-level
  multi-statement axon construction (`Axon z; z.add("_tag", …); …`) — a top-level Axon is visible
  inside functions on the substrate (verified). Substrate-verified `variant_toplevel_value` = 16
  (`let z = Zero  let p = Pair (7,9) … sum_e z + sum_e p` = 0 + 16). The constructor/aggregate
  group (single-arg, nullary, multi-arg, arg-position, local-binding, top-level, nested-under-
  operators) is now COMPLETE for numeric payloads. Numeric
  payloads only (strings aren't axon fillers).
### Priority 2 — fix TypeScript (`sdk/sutra-from-ts/`)
- [ ] (follow-on) Per-variable interface typing so field-type lookup is exact even
  when two interfaces share a field name with different types (current global
  field-type map marks such collisions non-numeric to stay safe). Low priority —
  no fixture needs it. [The axon-field `.real()` bug is FIXED: numeric axon field
  reads now project via `.real()` (global interface/alias field-type map; string/
  literal fields untouched). interface_pass + discriminated_union RUN = 25.0 on the
  substrate (were zeros), guarded by new `test_fixture_runs_on_substrate`. TS suite
  43 passed / 1 xfail.]

### Priority 3 — new-language frontends (each `sdk/sutra-from-<lang>/`, model on `sutra-from-ocaml`)
Each: source reader (`tree-sitter-<lang>`) -> `lower.py` -> `.su` emission ->
fixtures that compile **AND run on the substrate** (the OCaml harness's
`_RUNNABLE_FIXTURES` pattern, not the TS compile-only bar). Functional first
(they map cleanly), then Rust, then WASM.
- [ ] **Scala** — `sdk/sutra-from-scala/` (`tree-sitter-scala`).
- [ ] **F#** — `sdk/sutra-from-fsharp/` (ML-family, close cousin of OCaml — should reuse much of the OCaml lowering shape).
- [ ] **Elixir / Erlang** — `sdk/sutra-from-erlang/` (the BEAM pair; immutable, message-passing maps onto the axon IPC story).
- [ ] **Clojure** — `sdk/sutra-from-clojure/` (Lisp; homoiconic, persistent data structures).
- [ ] **Haskell** — `sdk/sutra-from-haskell/` (purest; laziness + typeclasses are the hardest edges — last of the functional set).
- [ ] **Rust** — `sdk/sutra-from-rust/` (the imperative language that maps cleanly: expression-oriented, immutable-by-default, algebraic enums + exhaustive match).
- [ ] **WASM** — Phase 3 (todo.md), tied to the `WASM/` subtree once integrated.

### Cross-cutting (any frontend)
- [ ] End-to-end verification: each fixture's `.su` compiles AND runs AND
  reproduces ground-truth output (beyond the parse+codegen syntax check the TS
  harness does today). [OCaml's `_RUNNABLE_FIXTURES` already does this — the
  pattern to extend to every frontend.]
- [ ] CI: no workflow currently runs the `sdk/sutra-from-*` frontends. Consider a
  `transpilers-ci.yml` that installs the tree-sitter grammars + runs every
  `sutra-from-*` test suite. Scope decision — not auto-started.

## ⭐ GUI — substantial expansion (Emma 2026-06-11; the LAST work block before the pinned tail)

**Vision (Emma).** GUI is a much stronger component of Sutra for *early adoption*
than earlier framing assumed — a window of substrate-computed pixels is the most
legible "Sutra actually runs and produces something you can see" demo there is.
Invest substantially more here. This block is the last work item in the queue; the
work loop barrels the rest of the queue, then lands on this. The long-horizon GUI
agenda continues in `todo.md` once this is decomposed and underway.

**Grounding (what exists today — do NOT reinvent; build on it).**
- `demos/gui/frame.su` — per-pixel substrate brightness field `pixel(x,y)=1−x²−y²`;
  host (`demos/gui/window.py`) walks the grid, calls `pixel` per cell, paints a window.
- `demos/gui/count.su`, `toggle.su` — stateful demos, plus drivers
  (`counter_demo.py`, `click_demo.py`, `counter_substrate_server.py`) + tests
  (`test_gui_{click,counter,render}.py`).
- `demos/font/` — substrate font rendering (companion surface).
- Audit: `planning/findings/2026-05-28-demos-gui-substrate-audit.md` (dim hygiene PASS
  — dim=8, 0 basis_vector; the two stateful demos are host-state-shuttle, refactor flagged).

**HARD RAILS for ALL GUI work (CLAUDE.md):**
- Every pixel/step value is computed ON THE SUBSTRATE. No host arithmetic inside ops.
- **No host readout inside the language.** `real()`/`make_real`-as-readout is removed;
  `realvec(v)` is the on-substrate replacement. The ONE legitimate boundary is the
  orchestrator/host reading the FINAL frame vector to paint it (terminal I/O, the
  orchestrator-model boundary) — not per-op extraction.
- Stateful GUI MUST be a substrate-RNN: hidden state is a VECTOR carried across loop
  iterations, NOT a Python variable shuttled between calls (the count/toggle failure).
- Verify against ground truth: decoded frame/pixels == expected, MEASURED, not "it ran".

**Decomposition (work top→bottom; each its own commit + DEVLOG entry):**
1. **Bring the existing GUI demos current to the post-purity language.** `frame.su` +
   `window.py` (and font drivers) still use pre-2026-06-07 `real()`/`make_real` host
   readout. Re-lower so the per-op path is substrate-pure (`realvec`), the host reads
   only the final frame. Re-run the demos; confirm the painted output is unchanged
   (measured: same brightness field). Update the now-stale "recurrent loop" driver/test
   docstrings flagged by the audit.
2. **Substrate-RNN refactor of the stateful demos (`count.su`, `toggle.su`).** Rewrite
   so the counter/toggle state is a vector carried across `loop` iterations on the
   substrate (no host `n += 1`). Add a state-locus test (walk N steps, assert no host
   extraction between ticks — the template the audit names). This discharges the
   long-flagged "host-state-shuttle dressed as recurrence" design failure.
3. **Whole-frame render in ONE substrate call** (the "fuller form" Emma described):
   a single returned vector decoded to a full frame via a reverse-CNN-style decoder,
   instead of N per-pixel calls. (Original Yantra-era sketch `planning/24-first-gui.md`
   was NOT migrated — write a fresh `planning/exploratory/` design doc here first, then
   build the smallest version and measure decoded-frame == per-pixel-field as the oracle.)
4. **Broaden the widget / interaction set** — more demos establishing GUI as the
   early-adoption showcase: richer rendering (gradients/shapes/animation via the
   substrate-RNN step), input handling (click → substrate state transition), simple
   layout. Each demo: a runnable `.su` + driver + a test asserting substrate-side
   correctness, dim-audited (smallest `runtime_dim` it needs).
5. **A human-facing GUI page on the website** (`docs/…`, rendered by
   `scripts/build_site.py`) — "see Sutra draw pixels." Website discipline: NO
   repo-internal refs (no queue/todo/planning/sdk paths), no numpy mentions; show the
   real mechanism (substrate computes the image field, host paints).

Mirror these into the task tool. As each lands: delete it here, append a dated DEVLOG
entry, push. When this block is cleared, the GUI long-horizon agenda lives in `todo.md`.

## Pinned tail (always present — bracket every session)

Per CLAUDE.md §"Autonomous productivity loop" lifecycle: a fresh session
starts the three crons up front; the tail ensures they're still running +
summarizes. Not consumed between fires.

- **A. Ensure the crons run** (`CronList`; re-create work-loop :03,
  auto-flush :15, status-report :42, AskUserQuestion blocker-sweep :50 if
  missing; `durable: false`). See the Handoff section at the top.
- **B. End-of-session status report** (reporting only, no commits): what
  advanced (shas + one-line), queue state, how the rails held, blockers,
  test health.

## Parked / longer-horizon (in todo.md)

C → Sutra transpiler (`sdk/sutra-from-c/`, parked, keep in tree); Promises
Stage-3 / container-method-dispatch / multi-statement try-catch; TS
transpiler closeout; website visual remake; Yantra migration tail (dim-audit
`examples/*.su`; migrated-demo docs/headers; lessons-learned writeup).

## Pointers

- Substrate-leak catalogue: `Audit.md`. Longer-horizon: `todo.md`.
- Findings (dated): `planning/findings/`. Open design questions:
  `planning/open-questions/`. Devlog: `DEVLOG.md`.
- Corpus repo: `github.com/EmmaLeonhart/sutra-w2c-corpus` (submodule
  `corpus/`) + `huggingface.co/datasets/EmmaLeonhart/sutra-w2c-corpus`.
- Yantra (downstream OS): `../Yantra/`.
