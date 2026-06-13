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

## Context (read first, do not work on)

- **`paper/paper.md` is UNFROZEN (Emma 2026-06-07)** — the live revision target
  for a new submission. `paper/neurips/` stays under its own **permanent**
  freeze (do NOT touch). Integrity discipline applies (measured numbers only;
  no overclaiming substrate-purity/fused-network as done).
- **Promise/await is fit-to-spec** (verified 2026-05-20;
  `test_await_substrate_pure.py` 4/4). Guarded by the watchdogs below.
- **NEVER use `Math.mod`** (Emma 2026-06-12 — worst-implemented function; measured
  vector-collapse/NaN, finding `2026-06-12-rotation-mod-vector-collapse-…`). For
  wrap/periodic behavior use complex rotation (`demos/gui/live_frame.su`).

## Active — transpiler track (source -> Sutra) — top priority

> New-language frontends are the loop's active track (Emma roadmap order:
> Scala → F# → Elixir/Erlang → Clojure → Haskell → Rust → WASM). Each models on
> `sutra-from-ocaml` (the reference frontend; OCaml `let rec` incl. non-tail
> recursion is done — foldable CPS transform + Tree RNN, see DEVLOG/findings).
> Roadmap: todo.md §"Multi-language transpiler frontends".

- [ ] **F# next increments** (`sdk/sutra-from-fsharp/`; through tail recursion →
  `while_loop` shipped 2026-06-12, suite 10/10): type annotations; foldable
  non-tail CPS transform; variant/record `match` patterns; records/DUs → axons.
  Measured grammar quirk: parenthesize call operands under infix.
  [Scala's named roadmap set is COMPLETE 2026-06-12, 18/18.]
- [ ] **Elixir next increments** (`sdk/sutra-from-elixir/`; MVP shipped
  2026-06-12, suite 4/4 — defmodule fns, if/else blend, binary ops): tail
  recursion → `while_loop` + foldable non-tail CPS (recursion IS iteration in
  Elixir — the load-bearing increment); `case` → blends; multi-clause `def`
  heads; maps/structs → axons. (Erlang proper is a separate later frontend.)
- [ ] **Clojure next increments** (`sdk/sutra-from-clojure/`; through `recur` →
  `while_loop` shipped 2026-06-12, suite 12/12): foldable non-tail CPS; maps →
  axons; destructuring binds.
- [ ] **Haskell next increments** (`sdk/sutra-from-haskell/`; through tail
  recursion → `while_loop` shipped 2026-06-12, suite 6/6; laziness out of
  scope): foldable non-tail CPS, pattern equations → blends, guards, where/let,
  `data` ADTs → tagged axons.
- [ ] **Rust next increments** (`sdk/sutra-from-rust/`; through tail recursion →
  `while_loop` shipped 2026-06-12, suite 10/10): structs → axons; foldable
  non-tail CPS; `while`/`loop` → substrate loops; nested/non-tail `match`.
- [ ] **WASM** — Phase 3 (todo.md), tied to the `WASM/` subtree.
- [ ] **OCaml: arrays → RAM blocked on the core-compiler `dict<int,int>` defect**
  (finding `2026-06-06-dict-int-keys-broken`) — verify whether still broken; if so,
  fix the core defect (it gates OCaml arrays and the full ISO-5 machine).
- [ ] **TS follow-on (low priority):** per-variable interface typing so field-type
  lookup is exact when two interfaces share a field name with different types
  (current global map marks collisions non-numeric to stay safe; no fixture needs it).
- [ ] **Cross-cutting:** extend OCaml's compile-AND-run `_RUNNABLE_FIXTURES` bar to
  every frontend; consider a `transpilers-ci.yml` running all `sutra-from-*` suites
  (scope decision — not auto-started).

## Next-venue paper polish (UNFROZEN — active)

`paper/paper.md`: ablation table (requires DEFINING + RUNNING the ablations —
e.g. semantic vs random codebook, dimension sweep, mean-centering on/off —
measured numbers only, never filled from memory). Le Chat AI-use breakdown →
A.0 (needs Emma's ground truth).

## 🌐 Merged queue — from the Neural WebAssembly (`WASM/`) repo

> Items merged from `EmmaLeonhart/neural-webassembly` when subtreed into `WASM/`
> (2026-06-06, full history). Completed WASM items live in `WASM/devlog.md` +
> that repo's git log. Long-horizon WASM items: merged agenda atop `todo.md`.
> Overview: `docs/neural-webassembly.md`.

- [ ] **ISO-5 remaining** (the substrate WASM machine core is built + Turing-complete,
  21 opcodes, CI 30/30 `test_mini_wasm_machine.py`; see findings `2026-06-06-iso5-*`):
  (a) breadth — the other ~23 opcodes (same blended dispatch; DIV/REM, shifts, stack
  ops); (b) a SCALABLE RAM device for the 10MB linear memory (host RAM-list doesn't
  scale); (c) ground-truth `.txt` build — BLOCKED locally (`uv`/`clang` missing;
  `iso_equiv.sh` uses WSL), route through CI like the oracle item below.
  Open idea for per-tick dispatch: one-hot opcode masks carried as loop state
  (avoids the measured literal-vs-loop-state `==` defuzz-false blocker, finding
  `2026-06-06-iso5-full-machine-handedit-and-dispatch-blocker.md`).
- [ ] **Pruned-transformer 6-program byte-for-byte oracle** (the one open step; the
  reduced core is built + locally verified output-identical 8/8 random inputs).
  Emma's decision 2026-06-06: generate the 6 programs' `.wasm` + token-prefix +
  `_ref.txt` fixtures ONCE on a clang-equipped path — preferred a GitHub Actions job
  (runners have clang/llvm) running `ensure_data()` + `generate_all()` and committing
  the fixtures back — then verify the pruned core reproduces all 6 byte-for-byte
  (decoded == ref, MEASURED — not "ran"). Local submodule branch for model edits
  (don't push to Percepta). HARD RAIL: "still works" means decoded output == reference.
- [ ] **E3 — integrate a native `i32.sat_add_u` opcode (spec done; impl remaining).**
  Spec `WASM/notes/e3_native_opcode_spec.md`. The build (own session): add to
  `OPCODES`/`STACK_DELTA`, `result_byte`/`result_carry`, `reference.py` + both
  isomorphs, `compile_wasm.py`, a test program; rebuild weights (MILP solves);
  end-to-end vs reference; no regression on 6 programs; re-run `iso_equiv.sh`.
  On a local submodule branch (don't push to Percepta).
- [ ] **Optional — hull Python path.** `apt install python3-dev`, then
  `uv run wasm-eval --hull` / `pytest -m "not slow"`; quantify hull (O(log n)) vs
  `--nohull` to substantiate the attention-scaling claim.
- [ ] **Yantra OS integration** — forward goal; design in
  `WASM/notes/yantra_integration.md`; phased P0–P6 in the merged `todo.md` agenda.

## RAM inline `await` — one blocked remainder

The inline surface (`ramRead`/`ramWrite` + `await` in async fns + the recur read
head) is shipped + guarded (`test_ntm_ram.py` 11/11). Remaining:

- [ ] **`await` inside a non-async `recur`** — BLOCKED on the await→while_loop
  lowering phase (promises.md); hits `CodegenNotSupported`. The synchronous-
  `ramRead`-in-`recur` form already gives the read head functionally. Do NOT hack
  the desugar without settling that semantics. (Follow-ups in todo.md: the
  lowering itself; model-free hash-keyed-role axon for the mailbox dim cost.)

## W2C / corpus (not active work)

Corpus at 7200 programs (submodule `corpus/` + HF mirror, consistency-guarded).
The official baseline model is PUBLISHED (Emma greenlit 2026-06-12): `corpus/model/`
carries checkpoint + vocab + substrate eval (exact 0.811 / IO 0.826), on GitHub
(`7dfb660a`) + HF (`fbf07a2d`). The coefficient wall stands measured (structure
transfers ~1.0; coefficient families drag — data-bound at least partially). Scale
further = one-flag bump on `experiments/weight_to_code_corpus.py` → push submodule →
HF mirror → bump pointer. Loose end (low priority, default leave): 5760 old-layout
flat CSV orphans on HF — if tidying, precise explicit-path delete (NOT a `*.csv`
wildcard) + harden `mirror_corpus_to_hf.py` to prune stale files.

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

## Pinned tail (always present — bracket every session)

Per the autonomous-loop skill lifecycle: a fresh session starts the crons up
front; the tail ensures they're still running + summarizes. Not consumed
between fires.

- **A. Ensure the crons run** (`CronList`; re-create work-loop :03,
  auto-flush :15, status-report :42, AskUserQuestion blocker-sweep :50 if
  missing; `durable: false`).
- **B. End-of-session status report** (reporting only, no commits): what
  advanced (shas + one-line), queue state, how the rails held, blockers,
  test health.

## Parked / longer-horizon (in todo.md)

C → Sutra transpiler (`sdk/sutra-from-c/`, parked, keep in tree); Promises
Stage-3 / container-method-dispatch / multi-statement try-catch; TS
transpiler closeout; website visual remake; Yantra migration tail (dim-audit
`examples/*.su`; migrated-demo docs/headers; lessons-learned writeup);
NTM/attention-on-RAM breadth backlog (trainable-query `.su`; composed-network
end-to-end training; more parse tasks; multi-head comparison — track closed
by Emma 2026-06-08, breadth only).

## Pointers

- Substrate-leak catalogue: `Audit.md`. Longer-horizon: `todo.md`.
- Findings (dated): `planning/findings/`. Open design questions:
  `planning/open-questions/`. Devlog: `DEVLOG.md`.
- Corpus repo: `github.com/EmmaLeonhart/sutra-w2c-corpus` (submodule
  `corpus/`) + `huggingface.co/datasets/EmmaLeonhart/sutra-w2c-corpus`.
- Yantra (downstream OS): `../Yantra/`.
