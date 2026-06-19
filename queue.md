# Sutra — Work Queue

**This file is a queue, not a state snapshot.** It lists what is being worked on now
and what is next, in execution order — barrel it top to bottom. **Finished work is
REMOVED from this file in the same commit it ships** (history lives in `git log`,
`DEVLOG.md`, and `planning/findings/`). If you catch yourself writing "✅ DONE /
SHIPPED / STEP N DONE" in this file, stop — delete the item instead. Leaving
completed work here as status markers is the bloat that destroys the queue's job as
an ordered execution list (Emma 2026-06-17). `todo.md` is longer-horizon; items
migrate `todo.md` → `queue.md` → deleted on completion.

---

## Context (read first, do not work on)

- **`paper/paper.md` is UNFROZEN** (Emma 2026-06-07) — live revision target. The `paper/neurips/`
  edit-freeze was **RETIRED 2026-06-18** (Emma: "give up on the NeurIPS freeze") — it is now editable
  for factual fixes; the immutable record is git commit `ea6f8a01`. Measured numbers only; no overclaiming.
- **NEVER use `Math.mod`** (worst-implemented; measured vector-collapse/NaN). Use complex
  rotation for wrap/periodic (finding `2026-06-12-rotation-mod-vector-collapse-…`).
- **GUI is on Emma's SEPARATE branch** — OUT of this queue. The Adam-RLHF GUI demo + paper
  stay built on main, but no GUI *agenda* here. Do NOT re-add GUI items.
- **Promise/await is fit-to-spec** (verified; `test_await_substrate_pure.py` 4/4), guarded by
  the watchdogs below.

---

## 2. Phase 5 — real-WASM-bytecode core (COMPLETE; only follow-ups remain)

WebAssembly is the VM direction (Emma 2026-06-17; JVM done + parked).
`experiments/iso5_substrate_dispatch/wasm_core.su` is a complete real-WASM-bytecode core (real
opcode values + encoding so `wat→wasm` runs unmodified) on the RAM-state blended-dispatch DNC stack
machine. Implemented + substrate-verified (`test_wasm_core.py`): i32 arithmetic + signed LEB128,
indexed locals, the comparison family, structured control (`block`/`loop`/`if`/`else`/`br`/`br_if`/
`end` via a load-time pre-resolved target table), `call`/`return` with a frame-relative call stack
(frame pointer + control/return stack + host-built function table, args-in-place), a real iterative
**factorial** byte-for-byte (`fact(0..5)`), and **recursive `fib(0..6)=0,1,1,2,3,5,8`** (tree
recursion with the call stack in RAM/DNC memory — the Phase-5.5-B substrate demonstration). Only
follow-ups remain:
- [ ] **wat2wasm cross-check:** the factorial bytes were HAND-ASSEMBLED to the WASM spec encoding
  (`wat2wasm`/`wasm-tools` absent here). When a toolchain is available (CI), assemble the same `.wat`
  with real `wat2wasm` and assert the function-body bytes are byte-identical to `_WASM_FACT`.
  (Still blocked locally — no toolchain; a CI-only item.)
  - [ ] **3+ byte LEB128** (deferred): the substrate decode + host `_ilen` now handle 2-byte
    (14-bit) operands; a 3rd continuation byte is asserted-against, not decoded. Needs a substrate
    loop (or fixed 3/4-byte unroll) for full 32-bit operands — low value (no fixture needs it yet).

## 3. Phase 5.5 — recursion lowering (per the recursion-execution-model spec)

The recursion philosophy was distilled from Emma's reference chat into
**`planning/sutra-spec/recursion-execution-model.md`** (the settled design) — a five-tier hierarchy.
It REFINES the old two-bucket framing: multiple recursion does NOT all go to WASM; most stays native
via pre-evaluation or memoization, and WASM shrinks to a tier-5 fallback for genuinely imperative /
`eval` code. Apply across ALL frontends. Comes before the §4 long tail. Build order = the spec's.

**Tier 1 (tail/loops → recurrent neurons) and Tier 2 (single non-tail → tail) are DONE** — tier 2 is
the `_try_lower_foldable_nontail` transform present in all 8 functional frontends with a `nontail_fact`
fixture each, verified 2026-06-17 to compile AND run == reference on the substrate (OCaml/Haskell/Rust
sampled locally; all 9 gated by `transpilers-ci`). **Tier 3 (fixed-depth multiple → compile-time
pre-evaluation) is also DONE** — `sutra_compiler/preeval.py` (folds a constant-arg bounded-pure-recursive
call to a literal + prunes the now-dead self-recursive fn; `test_preeval.py` 12/12 on the substrate).
Emma 2026-06-17: pre-eval runs by DEFAULT at a SHALLOW depth (**default 3**, not 0 — "should not be
zero but around 2-3"; it only fires on detectably-precalculable constant-arg calls, uncommon, so
cheap); `--preeval` raises to a deep cap (128), `--max-preeval-depth N` sets it (0 disables). So tier
3 is complete. **Tier 4 (NATIVE recursion via memoization) is DONE for everything that runs on the
substrate** — single-index DP (rolling-window + RAM-memo) AND multi-arg DP (binomial, AUTO-SYNTHESIZED
by `tabulate.py::detect_2arg_dp` + `synthesize_2arg_dp_source`, default-on) all run natively ==
ground truth (see `DEVLOG.md` 2026-06-17). The ONLY un-landed piece is **genuinely irregular
(non-grid, stack-based) recursion**: the branchless RAM-stack trampoline is algorithm-correct (Python
mirror) but does NOT execute practically on the substrate (times out / GPU-pinned — finding
`2026-06-17-tier4-irregular-recursion-trampoline-substrate-too-slow.md`). Per Emma 2026-06-17 it is
**deferred to `todo.md`** (later work) and runs meanwhile via the tier-5 WASM fallback. Nothing
actionable here this session — irregular needs substrate-perf root-causing, not a queue step.

- Tier 5 (`wasm_core`, §2) is the fallback ONLY for non-tabulable / irregular / genuinely imperative
  / `eval` / FFI recursion — NOT for the DP family (which is native).
  (The `wasm_core` running recursive `fib` was the interim proof; tier 4 makes the fib-family native.)

## 4. Phase 6 — transpiler long-tail (after §0)

Per-frontend remaining OPEN edge cases (completed items are deleted, not crossed off — see
CLAUDE.md). Each: fixture-tested + RUN on the substrate against ground truth; model on
`sutra-from-ocaml` (the reference); keep `transpilers-ci.yml` green. The nested + MIXED
destructure sweep is complete for all 5 ML-family frontends; what's left:

- [ ] **F# / Scala** — nested/mixed destructure + string literals (`"…"` → Sutra string, `==`/`=`
  via eq_synthetic; fixtures `string_eq` RUN == 30) done; general breadth remains (closures,
  generics, traits/instance classes, more String ops), modelled on OCaml as needs arise.
- **Haskell** (`sutra-from-haskell/`): native-recursion surface DONE 2026-06-18 (tail, non-tail
  CPS fold, >2-guard multibase, explicit-condition recursive guard — `otherwise` or `| n>1 = f…`).
  The few remaining native-lowering edge cases are MOVED to the bottom of the queue (they run via the
  tier-5 WASM fallback per Emma, so not urgent) — see the LAST section.
- [ ] **Elixir / Erlang** — multi-literal-base TAIL recursion + GUARDED RECURSIVE clause (Mode C:
  `f(N,Acc) when N>0 -> f(...); f(_,Acc) -> Acc`) DONE 2026-06-18 (both; fixtures `multibase_tailsum`
  / `guarded_rec_clause` RUN == 105 / 15). String surface complete: literal + `==` eq_synthetic
  (`string_eq` RUN == 30) and `<>` concat (`<>`-operand params inferred String; `string_concat`
  RUN == 100) DONE 2026-06-18. Erlang string surface DONE 2026-06-18: literal + case string
  pattern (`string_case` RUN == 60) and `++` charlist concat (`++`-operand params inferred String;
  `string_concat` RUN == 100). >2-clause NON-tail multibase (CPS fold) DONE 2026-06-19 for BOTH
  Elixir and Erlang (`_try_lower_multibase_multiclause_recursion` non-tail branch + shared
  `_foldable_step`; fixtures `multibase_nontail_fact` RUN == 600 each). Elixir MIXED literal +
  `when`-guard >2-clause multibase (tail) DONE 2026-06-19 for BOTH Elixir and Erlang (generalised the
  multibase parse to source-ordered lit/guard bases; continue = compound `&&` halt with a guard `<=`
  term — verified to fire on the substrate; fixtures `guarded_multibase` RUN == 9114 each). Remaining:
  Erlang list comprehensions; multi-arg non-tail multibase (stays on WASM fallback).
- [ ] **Clojure** — map/vector literal in a TAIL-recursive base DONE 2026-06-18 (`_hoist_maps`
  threaded into `_try_lower_tail_recursive` + `Axon` return type; fixtures `map_in_recursion` RUN
  == 3, `vec_in_recursion` RUN == 60). The `.item()`-on-call-result residual (inline `(:k (f …))`
  reads) is RESOLVED 2026-06-19 by the COMPILER fix (`_translate_call` routes `.item(key)` on a
  non-identifier receiver to `axon_item`; finding `2026-06-18-axon-item-on-call-result-...` marked
  RESOLVED; `tests/test_axon_item_call_result.py`). A Clojure end-to-end `(:k (f …))` fixture is
  deferred — the local Clojure grammar DLL won't build (MSVC error) on this clone, so add+verify it
  on a clone where the grammar builds (CI exercises the path via the repo compiler). (Symbol/keyword-
  as-value rep is §0.5.)
- [ ] **OCaml** (`sutra-from-ocaml/`, reference): `option`/variant payload is DONE 2026-06-19 — all
  five gaps from finding `2026-06-19-ocaml-option-payload-five-gaps.md` (now marked RESOLVED) fixed +
  substrate-verified; scalar AND aggregate payload, annotated or not, works end-to-end (fixtures
  `option_some_{inline,unannotated,tuple,record,thunk}` + `variant_arg_unannotated`; OCaml suite
  152/152). Remaining OCaml work is unrelated to payloads: **scalable RAM device for the 10MB linear
  memory** — root-caused 2026-06-19 in finding `2026-06-19-ram-device-scaling-limit.md` (the runtime
  `self.ram` Python list pre-grows to the max address AND stores a full d-dim vector per cell → ~35GB
  for 10M cells; fix needs lazy/sparse alloc + compact per-cell scalar storage WITHOUT breaking the
  attention-on-RAM vector path). A deliberate, safety-critical session on the shared RAM device — do
  NOT rearchitect autonomously without a green light. Plus non-zero `Array.make` fill (slots start at
  0 — documented limit, not a bug).
- [ ] **TS follow-on (low priority):** per-variable interface typing DONE 2026-06-19 — a member
  access `x.field` now resolves the field type in the variable's OWN interface map
  (`interface_field_types` + `var_interfaces`), exact even when two interfaces share a field name
  with conflicting types (which collapsed the merged map to "JavaScriptObject" and denied a numeric
  field its `realvec`). Fixture `interface_field_collision` (A.v number → realvec, B.v string → raw;
  RUN == 6). Falls back to the global map for non-identifier receivers (nested chains). (Nested-
  interface support shipped 2026-06-18.)
- [ ] **WASM source frontend** — the `WASM/`-subtree-tied source→Sutra path (Phase 3 in `todo.md`;
  distinct from the §2 wasm_core VM).

## 5. Python via Pyodide/Wasm (future leg, after the §2 WASM core)

No direct CPython VM (a trap — pure CPython bytecode is useless without C extensions). Python rides
the WASM leg via **Pyodide** (CPython + NumPy/SciPy/pandas compiled to Wasm) → the WASM frontend →
substrate. Standout research angle once WASM/thrml is solid: **physical-entropy NumPy** — wire
NumPy's random draws to the thermodynamic substrate's native sampling entropy (not a PRNG) for
genuinely physical randomness, unifying Sutra's randomness story. (Verbatim rationale in git
history of this file, pre-2026-06-17 cleanup.)

## 6. Merged WASM-repo items (`WASM/` subtree)

Completed WASM items live in `WASM/devlog.md`. Overview `docs/neural-webassembly.md`.

- [ ] **ISO-5 remaining:** (a) breadth — the other ~23 opcodes (DIV/REM, shifts, stack ops, same
  blended dispatch); (b) a SCALABLE RAM device for the 10MB linear memory; (c) ground-truth `.txt`
  build — BLOCKED locally (`uv`/`clang` missing), route through CI. Open idea: one-hot opcode masks
  as loop state (avoids the literal-vs-loop-state `==` defuzz blocker, finding `2026-06-06-iso5-…`).
- [ ] **Pruned-transformer 6-program byte-for-byte oracle:** the reduced core is built + locally
  output-identical 8/8 random inputs. Generate the 6 programs' `.wasm`+token-prefix+`_ref.txt`
  fixtures ONCE on a clang-equipped CI job, commit them, then verify the pruned core reproduces all
  6 byte-for-byte (decoded == ref). Local submodule branch (don't push to Percepta).
- [ ] **E3 — native `i32.sat_add_u` opcode** (spec `WASM/notes/e3_native_opcode_spec.md`; impl
  remaining): add to OPCODES/STACK_DELTA, result_byte/result_carry, `reference.py` + both isomorphs,
  `compile_wasm.py`, a test program; rebuild weights; end-to-end vs reference; no regression on the 6
  programs; re-run `iso_equiv.sh`. Local submodule branch.
- [ ] **Optional — hull Python path:** `apt install python3-dev`, then `uv run wasm-eval --hull`;
  quantify hull (O(log n)) vs `--nohull` to substantiate the attention-scaling claim.
- [ ] **Yantra OS integration** — forward goal; design `WASM/notes/yantra_integration.md` (P0–P6).

## 7. RAM inline `await` — blocked remainder

- [ ] **`await` inside a non-async `recur`** — BLOCKED on the await→while_loop lowering
  (promises.md); hits `CodegenNotSupported`. The synchronous-`ramRead`-in-`recur` form already gives
  the read head. Do NOT hack the desugar without settling the semantics.

## 8. FV fill-in — full mixing-rate proof (lowest priority)

- [ ] **Sampler-convergence full t→∞ mixing RATE / spectral-gap** in `fv-lean/mathlib/` (mid-size
  step done: `GibbsMathlib.lean` machine-checks reversibility⟹stationarity + the gadget kernel +
  2-state uniqueness, `lake build` green). Do the spectral-gap contraction to the Gibbs measure for
  the gadget chain. Fill-in only — when nothing above is actionable. Local-verified (heavy toolchain).

---

## 9. Quantum computing × Sutra — LOWEST priority, exploratory (Emma 2026-06-18)

**Bottom of the queue on purpose** (Emma's explicit placement): do this ONLY after all the
functional-programming / transpiler long-tail (§4) and every other deferred item above is done.
Exploratory, not a priority. Q1–Q3 were done early by misreading the placement; the rest waits.

Emma's braindump (quantum ↔ FP, emulators worth trying, the Sutra differentiable-circuit
angle) is organized here as executable tasks; the conceptual content + measured results live
in `planning/exploratory/2026-06-18-quantum-computing-and-sutra.md` and runnable code in
`experiments/quantum/`. All of Q1–Q5 are DONE (Q1 emulator sweep, Q2 PennyLane differentiable training, Q3 Q# Bell/GHZ,
Q4 writeup, all 2026-06-18; **Q5 VQE-to-Sutra DONE 2026-06-19**). Q5
(`experiments/quantum/vqe_to_sutra.py`) — the genuinely novel test — expressed + trained the
`RY(θ)|0>`/`<Z>` circuit on Sutra's OWN complex substrate (amplitudes on `AXIS_REAL`/`AXIS_IMAG`;
`RY` = the eigenrotation `cexp(i·θ/2)`; `<Z> = Re(z²)` via `complex_mul`), reaching PennyLane's
fixed point (θ→π, `<Z>`→−1; value/gradient match the closed form to ~1e-4 / ~1e-6). Scope held:
Sutra can express+train a VQE-shaped graph — NOT a claim it is a quantum computer or that its ops
are unitary; single-qubit toy only. Nothing actionable remains in this section.

---

## LAST — do these ONLY after every section above is cleared

**This is the literal bottom of the queue (Emma's strict ordering).** The work-loop reaches
this section ONLY when §2 through §9 are fully drained — it is not "skip," it is "do dead last."
Work top-to-bottom; do not reorder.

- **W2C/corpus:** 7200 programs (submodule `corpus/` + HF mirror); baseline model PUBLISHED
  (exact 0.811 / IO 0.826). Scale = one-flag bump → push submodule → HF mirror → bump pointer.
  Loose end (low priority): 5760 old-layout flat-CSV orphans on HF — precise explicit-path delete
  if ever tidying (NOT a `*.csv` wildcard).
- **Watchdogs (verification, not new work):** hourly local cron (`test_await_substrate_pure.py` +
  `await_value` leak grep); daily remote spec-audit (claude.ai); daily substrate-honesty audit (§1).
- **Doc audit (end-of-queue standing, Emma 2026-06-16):** Sutra is a BUSINESS — comprehensive audit
  + rework of ALL docs (website `docs/`, `README.md`, `AGENTS.md`, `CLAUDE.md`, `paper/` framing,
  `sdk/*/README.md`, `planning/sutra-spec/`): contradictions, stale claims, dead website refs,
  business framing, undocumented capabilities. Plan into per-surface steps when reached; grep, don't
  trust memory. Do NOT start until the phases above are clear unless Emma re-prioritizes.
- **Transpiler edge cases on the WASM fallback (catalogue: `planning/wasm-fallback-edge-cases.md`):**
  per-frontend constructs that don't lower natively yet but run via tier-5 WASM (Haskell non-tail
  multibase / mutual `where`-`let` / variant-case-in-expr; OCaml option-match aggregate; Clojure
  maps-in-recursion; Elixir/Erlang non-tail/guarded multibase; F# no-paren application; etc.).
  Low value — **few cycles each**, leave on WASM if not clean; do these LAST (todo.md tail).
- **Parked / longer-horizon (in `todo.md`):** C→Sutra transpiler (parked, keep in tree); Promises
  Stage-3 / container-method-dispatch / multi-statement try-catch; TS transpiler closeout; website
  visual remake; Yantra migration tail; NTM/attention-on-RAM breadth backlog.

## Papers — add a Background section at the beginning (Emma 2026-06-18)

- [ ] Add a **Background** section to the BEGINNING of the papers (lead-in before the main body):
  `paper/paper.md` (live, unfrozen) and `paper/formal-verification/paper.md` (live). Do **NOT** touch
  the FROZEN `paper/neurips/` snapshot. Keep the integrity + writing discipline (measured numbers
  only, no overclaiming, no "honest"-style buzzwords, no em-dashes). Requested across all Sutra
  checkouts; this is the canonical Sutra repo queue, so it propagates to the vendored copies on sync.

## Pinned tail (always present — bracket every session)

- **A. Ensure the crons run** (`CronList`; re-create work-loop :03, auto-flush :15, status-report
  :42, AskUserQuestion blocker-sweep :50 if missing; `durable: false`).
- **B. End-of-session status report** (reporting only, no commits): what advanced (shas +
  one-line), queue state, how the rails held, blockers, test health.

## Pointers

- Substrate-leak catalogue: `Audit.md`. Longer-horizon: `todo.md`. Findings: `planning/findings/`.
  Open design questions: `planning/open-questions/`. Devlog: `DEVLOG.md`.
- Corpus: `github.com/EmmaLeonhart/sutra-w2c-corpus` (submodule `corpus/`) + HF mirror.
- Yantra (downstream OS): vendored in-tree at `external/Yantra/`.
