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

- **`paper/paper.md` is UNFROZEN** (Emma 2026-06-07) — live revision target. `paper/neurips/`
  stays **permanently frozen** (do NOT touch). Measured numbers only; no overclaiming.
- **NEVER use `Math.mod`** (worst-implemented; measured vector-collapse/NaN). Use complex
  rotation for wrap/periodic (finding `2026-06-12-rotation-mod-vector-collapse-…`).
- **GUI is on Emma's SEPARATE branch** — OUT of this queue. The Adam-RLHF GUI demo + paper
  stay built on main, but no GUI *agenda* here. Do NOT re-add GUI items.
- **Promise/await is fit-to-spec** (verified; `test_await_substrate_pure.py` 4/4), guarded by
  the watchdogs below.

---

## 1. Daily substrate-honesty audit (recurring — discharge then delete)

Auto-prepended by `.github/workflows/daily-audit.yml`. First action of the next autonomous
session: review every commit since the previous daily audit against CLAUDE.md §"Subtler
substrate breaches": (a) `.su`/compile-path commits — `runtime_dim` matches what the `.su`
needs (count `basis_vector` calls; none → tiny dim); (b) any "recurrent"/"RNN"/"substrate-pure"/
"verified" claim — checked against measurement, not earlier framing; (c) any substrate classifier/
decision function — measured `gap = min(positive) − max(negative)` is in the commit or a planning
doc. If anything is amiss, write a finding + a fix item here BEFORE other work, then delete this.

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
- [ ] **Multi-byte LEB128** (deferred from step 1): when a fixture needs a constant/index > 127,
  decode continuation-byte LEB128 (operand length becomes data-dependent → affects pc advance).

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

## 4. Phase 6 — transpiler long-tail (LAST of the active phases)

Per-frontend remaining edge cases. Each: fixture-tested + RUN on the substrate against ground
truth. New frontends model on `sutra-from-ocaml` (the reference). `transpilers-ci.yml` runs all 9
frontend suites on push/PR to `sdk/sutra-from-**`; keep it green.

- [ ] **F#** (`sutra-from-fsharp/`): ~~nested TUPLE + RECORD patterns (`let (a,(b,c))=t`,
  `let {inner={v}}=r`)~~ DONE 2026-06-17 (nested-axon construction via `_lower_field_value` hoist +
  an `Axon` temp per non-leaf prefix via shared `_emit_nested_reads` so reads dispatch as `axon_item`;
  `nested_tuple_destructure`=16, `nested_record_destructure`=13 on the substrate). ~~Nullary variant
  as a direct function RETURN (`let f () = North`)~~ DONE 2026-06-17 (body-is-a-DU-variant → return
  type `Axon` + `{_tag}` axon; zero-arg call `f ()` drops the unit arg; `nullary_variant_return`=10
  on the substrate). ~~Record-update from a LET-BOUND (non-param) source (`let q = {b with …}`)~~
  DONE 2026-06-17 (`_infer_record_type` recovers the type from the literal's field set; a let-bound
  record registers into `_PARAM_RECORD_TYPE`; `record_update_let`=17 on the substrate). ~~Variant in
  a blended `if` branch (`if c then North else South`)~~ DONE 2026-06-17 (branches hoist to `{_tag}`
  axon temps via `_lower_field_value`; the blend cleanly selects the matched axon at `f=±1`; ret→Axon
  via `_if_returns_variant`; `variant_if_branch`=10 [North]/20 [South] on the substrate). ~~Mixed
  tuple-in-record / record-in-tuple nesting~~ DONE 2026-06-18 (a shared `_collect_element_paths`
  dispatcher lets the tuple- and record-path collectors cross-call; `record_in_tuple`=16,
  `tuple_in_record`=16 on the substrate). **F# item fully drained** — only general breadth remains.
- [ ] **Scala** (`sutra-from-scala/`): ~~nested tuple patterns (`val (a,(b,c))=t`)~~ DONE 2026-06-17
  (`_collect_scala_tuple_paths` + shared `_emit_scala_nested_reads`, 1-based keys; `nested_tuple_destructure`=16
  but ONLY at `runtime_dim ≥ 100` — Scala's `_1`/`_2` keys cross-talk at the default dim 50, finding
  `2026-06-17-nested-axon-readout-crosstalk-is-dim-dependent.md`; the harness now runs it at dim 128 via a
  per-fixture `(expected, dim)` value); ~~case-class MATCH patterns (`case Point(a, b) => …`)~~ DONE
  2026-06-17 (irrefutable positional destructure to declared fields via `realvec(scrut.item("x"))`,
  mirroring the `val Point(a,b)=p` path; `caseclass_match`=13 on the substrate; multi-VARIANT
  case-class match needing `_tag` tests is a later item); ~~nested case-class patterns
  (`val Outer(Inner(a, b), c) = o`)~~ DONE 2026-06-18 (`_collect_caseclass_paths` recurses into nested
  case_class_pattern elements over declared field names + shared `_emit_scala_nested_reads`;
  `nested_caseclass_destructure`=16 on the substrate — distinct field keys clean at dim 50). **Scala
  item drained** — only general breadth remains.
  - [ ] **(cross-cutting) nested-axon cross-talk** — F#/Rust nested fixtures pass at the default dim 50 by
    luck of their `_0`/`_1`/field-name keys; for robustness consider running ALL nested-axon fixtures at
    `runtime_dim ≥ 128`, or use distinct depth-prefixed nested keys. Decision pending (see the finding's
    options). Not blocking — shipped fixtures are measured-correct + CI-green.
- [ ] **Elixir** (`sutra-from-elixir/`): ~~multi-clause/guarded bodies with `=` bindings~~ DONE
  2026-06-17 (`_lower_def_clauses` now threads each clause's leading `=` destructure bindings via
  `_apply_match_binding`, typing the destructured param `Axon`; `multiclause_bind_body`=13 on the
  substrate); ~~string-key arrow-map (`%{"x" => a}`) PATTERN params~~ DONE 2026-06-18 (reuse
  `_map_fields`, which already handles both atom-shorthand and string-key arrow forms, + an
  identifier-local check; `string_map_param`=13 on the substrate); >2-clause recursion with multiple
  LITERAL bases (hits the single-condition-halt blocker, finding
  `2026-06-17-while-loop-halt-is-single-condition-only.md`); `is_integer`-style type-test guards
  (dubious on the substrate — everything is a vector; needs a design call).
- [ ] **Erlang** (`sutra-from-erlang/`): ~~map PATTERN params (`#{x := X}` in a head)~~ DONE 2026-06-17
  (`map_expr` param case: each `map_field` binds its `var` to `realvec(_ai.item("key"))`, the
  `maps:get` projection; `map_param`=13 on the substrate); ~~multi-clause bodies with `=` bindings~~
  DONE 2026-06-17 (the clause dispatch threads each clause's leading `=` destructure bindings via
  `_apply_match_binding`, typing the destructured param `Axon`; `multiclause_bind_body`=13 on the
  substrate); >2-clause recursion (NOTE: multi-literal-base >2-clause recursion hits the
  single-condition-halt blocker, finding `2026-06-17-while-loop-halt-is-single-condition-only.md`);
  list comprehensions; `div`/`rem` via complex rotation (NOT `Math.mod`).
- [ ] **Clojure** (`sutra-from-clojure/`): symbol map keys (needs symbol-as-value rep); maps/vectors
  in recursive bodies; ~~nested destructuring (`[[a b] c]`)~~ DONE 2026-06-17 (`_collect_clj_vec_paths`
  + a `_DESTRUCTURE_PRELUDE` accumulator for the `Axon` temps [Clojure's let is substitution-only, so
  the temps go in a function-level prelude]; vector-destructured params typed `Axon`;
  `nested_vec_destructure`=16 on the substrate — `_0`/`_1` keys clean at dim 50); ~~multi-arity `defn`~~
  DONE 2026-06-18 (a prepass registers multi-arity names in `_MULTI_ARITY`; each arity emits a mangled
  `name__{arity}` function; call sites dispatch by arg count; same-arity self-recursion in a clause
  surfaces UNSUPPORTED; `multi_arity`=17 on the substrate); `case` symbol/keyword members (needs
  keyword-as-value rep).
- [ ] **Haskell** (`sutra-from-haskell/`): >2-guard guarded recursion **— BLOCKED on the substrate
  loop's single-condition halt** (finding `2026-06-17-while-loop-halt-is-single-condition-only.md`:
  a compound `&&` continue condition is ignored past the first conjunct, so N base conditions can't
  gate one loop unless they algebraically merge to one comparison; the multibase transform was
  written, measured wrong [`f 0 3`→6 not 105], and reverted); multi-equation guarded recursion
  (`f 0 acc | …; f n acc | …`); mutually-recursive/forward `where`/`let`; nested/non-variable
  ~~nested constructor `case` patterns (`Outer (Inner a b) c -> …`)~~ DONE 2026-06-18 (the apply-arm
  in `_lower_case_stmts` reads nested payloads via `_collect_hs_ctor_paths` + an `Axon` temp per
  non-leaf prefix in the case prelude, outer tag test; `nested_ctor_case`=16 on the substrate, flat
  variant case unregressed); ~~nested tuple `let` patterns (`let (a, (b, c)) = t`)~~ DONE 2026-06-18
  (`_collect_hs_tuple_paths` + a `_DESTRUCTURE_PRELUDE` accumulator for the `Axon` temps [the let bind
  is substitution-only]; `nested_tuple_let`=16 on the substrate — `_0`/`_1` keys clean at dim 50);
  ~~nested CONSTRUCTOR `let` patterns (`let (Outer (Inner a b) c) = w`)~~ DONE 2026-06-18
  (`_collect_hs_ctor_paths` + shared `_emit_hs_nested_reads`; `nested_ctor_let`=16 on the substrate —
  `_val0`/`_val1` keys MEASURED clean at dim 50); ~~`case` in non-tail expression
  position~~ DONE 2026-06-17 for LITERAL cases (`_lower_expr` reuses `_lower_case_stmts`: a literal
  case has no `int _vtag` prelude so it inlines as a nested blend; `case_nontail`=101 on the substrate;
  a VARIANT case in expression position still needs an int-local an expression can't emit → later item).
  **Bool literal case `case b of True -> … | False -> …`** DONE 2026-06-18 (`(b == true)`/`(b == false)`
  blend, `True`/`False` values → `true`/`false`; `bool_case`=10 on the substrate). (Laziness out of scope.)
- [ ] **Rust** (`sutra-from-rust/`): ~~nested match inside a tail-match arm~~ DONE 2026-06-18 for a
  LITERAL inner match (`_lower_match_stmts` gains integer-literal patterns + only emits the `_vtag`
  prelude for VARIANT matches, so a literal match has no prelude and `_lower_expr` inlines it as a
  blend; `nested_match_tail_arm`=5 on the substrate; a VARIANT inner match still needs int-locals an
  expression can't emit → later item); ~~nested tuple AND struct
  patterns (`let (a,(b,c))=t`, `let Outer { a, inner: Inner { v } } = o`)~~ DONE 2026-06-17
  (`_collect_rust_tuple_paths` / `_collect_rust_struct_paths` + shared `_emit_rust_nested_reads`: an
  `Axon` temp per non-leaf prefix so reads dispatch as `axon_item`; `nested_tuple_destructure`=16,
  `nested_struct_destructure`=13 on the substrate); ~~enum `if let` destructuring
  (`if let E::V(x) = s { … } else { … }`)~~ DONE 2026-06-17 (function-tail form: `int _vtag =
  realvec(s.item("_tag"))` for a CRISP tag test [inline `realvec(...)==0` defuzzes to 50/50 at tag 0
  — measured 6.5 not 13; the int-local round-trip fixes it] + `_val{i}` payload binds in the THEN arm;
  `if_let_enum`=13 [Circle] / 0 [Square] on the substrate; NESTED if-let surfaces UNSUPPORTED — needs
  an int-local an expression can't emit). (Loop bounds need strict `<`/`>`; `<=` drops the boundary
  iteration — finding `2026-06-13-while-loop-le-boundary-equality-defuzz`.)
- [ ] **OCaml arrays — scalable RAM device for the 10MB linear memory.** `Bytes.make` / loop-carried
  arrays use the global RAM list, which doesn't scale to 10MB. Also: non-zero `Array.make` fill for
  int-dict arrays (slots start at 0 — documented limit, not a bug).
- [ ] **TS follow-on (low priority):** per-variable interface typing so field-type lookup is exact
  when two interfaces share a field name with different types.
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

## Background / not active work

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
- **Parked / longer-horizon (in `todo.md`):** C→Sutra transpiler (parked, keep in tree); Promises
  Stage-3 / container-method-dispatch / multi-statement try-catch; TS transpiler closeout; website
  visual remake; Yantra migration tail; NTM/attention-on-RAM breadth backlog.

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
