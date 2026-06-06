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
- **17:00 (cron `9b7d8c5d`)** — start a THIRD clawRxiv paper (`paper/percepta-ntm/`)
  on implementing a DNC/NTM via the Percepta transformer + PCA and the measured
  results; wire its own CI (`percepta-ntm-paper-ci.yml`, model on `fv-paper-ci.yml`)
  for auto-submission; cite only measured numbers; commit+push (push triggers the CI).
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

- *(none open — the HF flat-CSV orphans were over-escalated; resolved to the
  sensible default: LEAVE them, they're harmless unreferenced duplicates and
  block nothing. Prune only if Emma later wants the tidy-up. See "Active —
  W2C".)*

## Context (read first, do not work on)

- **`paper/paper.md` is on arXiv and FROZEN through May 31, 2026.** Lock
  lifts automatically **2026-06-01**. Do not edit it (typos, findings,
  next-venue polish) until then. `paper/neurips/` is under its own
  separate **permanent** freeze. If a later result contradicts either,
  stop and tell Emma — don't silently amend. (DEVLOG 2026-05-20.)
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

- **ISO-5 — port the OCaml realisation into Sutra (UNBLOCKED 2026-06-06; gap
  analysis DONE).** The WASM isomorphism chain is transformer ≡ reference ≡ Rust ≡
  OCaml, byte-identical on all 6 programs (`WASM/iso/ocaml/`,
  `WASM/scripts/iso_equiv.sh`). On-ramp = the `sdk/sutra-from-ocaml/` frontend.
  Reconnaissance done (`planning/findings/2026-06-06-iso5-ocaml-to-sutra-gap-
  analysis.md`): the 189-line reference is *imperative* (refs/while/arrays/Buffer);
  it transpiles to visible `UNSUPPORTED-*` markers. Top-level value bindings + hex
  literals are now closed. **Ordered bounded transpiler items to drive ISO-5
  (also CLAUDE.md transpiler priority #1, OCaml):**
  1. ~~Sequence expressions + local mutation~~ **DONE** (`e1; e2` → statements;
     `ref`/`:=`/`!` → mutable Sutra locals; substrate-verified `seq_mut` = 15).
  2. **`while` → substrate `loop`** — DONE for the **scalar-ref shape**: OCaml
     `while COND do BODY done` over scalar `ref`s lowers to a hoisted Sutra
     `while_loop` (state = in-scope refs the cond/body touch; sequential body
     mutations; slot/loop/writeback call site). Substrate-verified `while_sum`
     (`while !i<5 do sum:=!sum+!i; i:=!i+1 done; !sum` = 10). The ISO-5 ref's 2
     real loops still need their inner constructs (arrays/try/match-with-br), so
     they degrade to `UNSUPPORTED-WHILE` (no broken output). `for` not yet done.
  3. **Char + string literals** — DONE: char → codepoint int (substrate-verified
     `char_code` `'A'`=65), string → Sutra `String` literal (compile-verified
     `string_lit`; function body-string return-type inferred as `String`).
  4. **Arrays** — **BLOCKED on a core-compiler defect** (NOT a transpiler issue):
     `dict<int,int>` (the substrate-faithful array target; `list<T>` is a Python
     host list, wrong for ISO-5) crashes — scalar keys aren't lifted to substrate
     vectors before `_role_hash` (`'int' object has no attribute 'detach'`), and
     even if lifted, exact read-what-you-wrote at array scale is unmeasured
     (rotation is identity on the synthetic axes where numbers live → bundling
     crosstalk risk). Finding: `planning/findings/2026-06-06-dict-int-keys-broken-
     blocks-arrays.md`. Fix is core-compiler work (dict scalar-key/value lift +
     measured exactness); do NOT hack the transpiler around it.
  6. **Nested-fn hoist** — DONE for the **closed** case (free vars ⊆ params ∪
     top-level names → hoisted to a sibling `function`; substrate-verified
     `nested_fn` `let dbl x = x*2 in dbl 5 + dbl 3` = 16). Closures (capturing an
     enclosing local — 7 of the ISO-5 ref's nested fns: `push`/`pop`/… over
     `stack` etc.) are correctly surfaced as UNSUPPORTED; closure conversion is a
     later item.
  5. **Tuples** — DONE: `(a,b)` → positional-field axon (`_0`/`_1`); `fst`/`snd`
     → `.item("_0"/"_1").real()`; tuple-body fn returns `Axon`; tuple-type param
     `int * int` → `Axon`. Substrate-verified `tuple_fst_snd` `sum2 (pair 7 9)` =
     16. Limitation (same as records): `fst`/`snd` need an **Axon-typed operand**
     (bound var / annotated param) — inline `fst (pair 7 9)` fails because Sutra
     method dispatch doesn't type a call result as Axon (torch `.item()` clash).
  5b. **Match catch-all name binding** (`| x -> body` binds the scrutinee) — DONE:
     `_MATCH_SUBST` substitutes the bound name into the arm body (bare for a
     simple-atom scrutinee to dodge the `(x) <op>`→cast ambiguity). Substrate-
     verified `match_bind` `classify 5` = 6, `classify 0` = 100. This is the
     substitution foundation the option/constructor-arg patterns reuse.
  5c. **option** (`Some`/`None`) — DONE for **body position**: tagged axon
     `{_tag,_val}`; `None`→tag 0, `Some e`→tag 1+val; `int option` param → Axon;
     `match o with Some x -> e1 | None -> e2` binds the payload. CRITICAL measured
     constraint: the match must bind `_tag`/`_val` to `int` locals first — an inline
     axon `o.item("_tag").real() == 1` defuzzes to truth 0 (not -1) for the false
     branch (measured), so option-match is FUNCTION-BODY-ONLY (nested expression →
     UNSUPPORTED). Substrate-verified `option_some` `get_or (mk 42) 0` = 42, None
     path = 7. The ISO-5 reference uses options in EXPRESSION position (inside
     `let input_base = … in`), so its option markers don't clear — a simpler test
     program would.
  5d. **`let … in` in expression position** — DONE for pure simple-atom bindings
     (identifier/number) via `_MATCH_SUBST`; substrate-verified `let_in_expr`
     `(let x = 5 in x + x) + 10` = 20. Compound/`ref`/nested-fn values stay
     UNSUPPORTED (need a real local / risk the cast ambiguity) — the reference's
     2 `let` markers (complex values) don't clear.
  5e. **`mod` operator + bitwise-op correctness fix** — DONE: OCaml `mod` → Sutra
     `%` (substrate-verified `modulo` `17 mod 5` = 2); `&&`/`||` made explicit in
     the op map. FIXED a latent bug: unknown infix operators (`land lor lxor lsl
     lsr asr`, `^`, `@`) were passed through verbatim → INVALID Sutra (compile
     error); they now emit `UNSUPPORTED-OP` (no Sutra bitwise operator exists —
     `&`/`|` are logical, `<<`/`>>` don't parse; a substrate bitwise stdlib is the
     real need). Verified 0 raw bitwise passthrough remains in the reference.
  5f. **Axon-returning-call -> local typed Axon** — DONE: a local bound to a call of
     a record/tuple/option-returning function is now typed `Axon`, so `let p = pair 7 9
     in fst p + snd p` works (was: p typed int -> `.item()` clash). Substrate-verified
     `tuple_local` = 16. (Inline `fst (pair 7 9)` on a bare call result still needs a
     bound local; that's the documented dispatch limit.)
  7. try/exceptions; 8. `match`-with-`br`; 9. stdlib (incl. substrate bitwise for
  `land`/`lsl`); 10. closure conversion; 11. core-compiler `dict<int,int>`.

  **Direction (Emma 2026-06-06): grind OCaml ISO-5 UNTIL NOON, then PIVOT to PCA.**
  Emma's update 2026-06-06 10:04: keep advancing the OCaml→Sutra transpiler for now,
  but **at noon (12:00 local) the loop pivots to the PCA on the WASM transformer**
  (todo.md TOP PRIORITY) regardless — one-shot cron `9d22a2f8` fires the pivot. Until
  noon, grind OCaml ISO-5 (option, string-match-with-`br`, exceptions, stdlib,
  closures, arrays/`dict<int,int>` core fix — all substantial/coupled, accept slower
  per-tick progress). After noon, PCA is the active item; the OCaml grind pauses.
  Do not re-ask the keep-grinding-vs-pivot question — it is answered (the noon cron
  carries the pivot).

  **Clarification — the two OCaml things (Emma asked 2026-06-06):** (1) *WebAssembly
  OCaml* = `WASM/iso/ocaml/bin/main.ml`, the OCaml isomorph of the transformer-VM
  (the WASM stack machine; the SOURCE program ISO-5 ports to Sutra). (2) *Sutra
  OCaml* = `sdk/sutra-from-ocaml/`, the OCaml→Sutra transpiler (the TOOL). The loop
  builds the TOOL (2), driven by the gaps surfaced when transpiling the WASM-OCaml
  reference (1); each feature is verified with a small standalone OCaml fixture on
  the substrate. End goal: the WASM machine running in Sutra.
  Destination (bigger than transpiler coverage): the fetch-execute loop as a
  substrate recurrence (state vectors across iterations, opcode dispatch as a
  defuzz match) — closing items 1–2 first runs a real WASM-machine fragment on
  Sutra. This is the end of the road for the isomorphism program.
- **PCA on the WASM transformer (todo.md TOP PRIORITY, now unblocked).** Promote
  from todo.md: PCA the analytic transformer's weights (`WASM/`, `d_model=38`,
  7 layers, 19 heads) to find the genuine low-dimensional attention structure to
  run for the DNC work. Gating lifted now that `WASM/` is in-tree.
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

## Next-venue paper polish (FROZEN through May 31; resumes 2026-06-01)

Blocked by the `paper/paper.md` freeze; do not start until June. Ablation
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
- [ ] (optional) File the Sutra `(atom) <binop>` → cast (`CastExpr`) parser
  ambiguity as an open-question — both frontends now work around it with
  fully-grouped blends, but the grammar ambiguity itself is unresolved.
- [ ] `let rec` — **tail-recursive accumulator shape DONE** (`let rec f p… =
  if COND then BASE else f a…` → Sutra `while_loop`; substrate-verified
  `sum_to 0 5 = 15`). Remaining: (a) **non-tail recursion** (factorial-shape,
  recursive call inside a larger expression) — still correctly UNSUPPORTED; needs
  a bounded-depth encoding, open question. (b) Non-comparison halt conditions
  (`&&`/bool) — needs a Sutra `not`/negation. [Simultaneous swap-update: DONE —
  temp-based update, substrate-verified `swaploop 7 9 2 = 7`.]
- [ ] `match … with`: **literal + trailing `_` DONE** (`classify 1 = 200`) and
  **nullary-constructor patterns DONE** (variant match, `label Green = 200`,
  substrate-verified; last case is the base, exact for exhaustive variant matches).
  Remaining: constructor-with-args / record-destructuring / or- / guarded patterns;
  `match` that binds a name in the catch-all (`| x -> …`).
- [ ] **Records -> axons: DONE for numeric fields** (substrate-verified
  `getx (mk 7 9) = 7.0`). `type X = {…}` erased + record-name prepass; record-typed
  params -> `Axon`; construction `{x=a;y=b}` -> `Axon r; r.add("x",a); …`; field
  access `p.x` -> `p.item("x").real()`. Key finding (`planning/findings/2026-06-05-
  axon-field-reads-need-real-projection.md`): numeric axon field reads REQUIRE
  `.real()` — without it they return zeros on the substrate. No type-tracking layer
  was needed (OCaml `p.x` is unambiguously a record field via `field_get_expression`).
  Remaining: tuples, non-numeric record fields (field-type-aware `.real()` off the
  record decl), record literals in argument position. (Nullary **variants** ->
  enum ints + constructor-pattern `match`: DONE — `label Green = 200`. Parameterised
  constructors `C of t` still UNSUPPORTED.)
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
