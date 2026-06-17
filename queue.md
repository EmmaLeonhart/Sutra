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

## 3. Recursion philosophy — analyze the references chat → plan + docs (Emma 2026-06-17)

**AFTER the WASM core (§2), BEFORE the transpiler long tail (§5).** Emma added a Claude chat to
the references that gives a more fundamental, analytical discussion of how recursion is to be run
in the language — the philosophy of how Sutra handles this. Source:
`references/Converting single recursion to tail recursion - Claude.html` (re-download per the
references policy if the cache is empty). Task: read that chat in full, then put together a
concrete implementation plan + documentation + planning docs for how Sutra runs recursion
(grounding/refining the Phase-5.5 strategy below). Deliverable: a planning/spec doc capturing the
philosophy and the implementation plan it implies. Do NOT invent its contents — read it first.

## 4. Phase 5.5 — recursion lowering: single→tail (compiler), multiple→WASM (Emma 2026-06-17)

Two-part strategy for NON-TAIL recursion, applied across ALL language frontends. Both come before
the §5 long tail; Part B depends on the §2 WASM core. (Will be grounded/refined by §3.)

- [ ] **(A) Single (linear) non-tail recursion → tail recursion — a compiler transform.** A single
  linear recursive call not in tail position (e.g. `fact(n)=n*fact(n-1)`) is turned into tail
  recursion by the frontend lowering. Tail recursion lowers to a substrate `loop` (state ← R·state)
  → stackless, stays a real RNN/fused graph. Apply uniformly in every frontend. Independent of WASM.
  Verify per frontend: a linear non-tail recursive fixture compiles to a `loop` and runs ==
  reference on the substrate.
- [ ] **(B) Multiple (tree) recursion → represent as WebAssembly.** Tree recursion (multiple
  recursive calls, e.g. `fib(n)=fib(n-1)+fib(n-2)`) genuinely needs a stack; lower it to WASM
  bytecode and run on the §2 substrate WASM machine (call frames live in RAM/DNC memory). WASM
  becomes a fundamental fallback runtime. Emma: "a big workaround… but the only way I can really
  see it working." Supersedes the OCaml Tree-RNN for genuine tree recursion. Depends on §2 step 5.
  Verify: a tree-recursive fixture (fib) lowers to WASM, runs on the substrate, decodes == reference.
  (Follow-on analysis item at the end of `todo.md`: when the WASM compatibility layer is needed
  vs lower directly, per-language/per-context.)

## 5. Phase 6 — transpiler long-tail (LAST of the active phases)

Per-frontend remaining edge cases. Each: fixture-tested + RUN on the substrate against ground
truth. New frontends model on `sutra-from-ocaml` (the reference). `transpilers-ci.yml` runs all 9
frontend suites on push/PR to `sdk/sutra-from-**`; keep it green.

- [ ] **F#** (`sutra-from-fsharp/`): nested tuple/record patterns (`let (a,(b,c))=t`); nullary
  variant as a direct function RETURN (`let f () = North`); record-update from a LET-BOUND
  (non-param) source (`let q = {b with …}`, needs literal-type inference).
- [ ] **Scala** (`sutra-from-scala/`): nested patterns; case-class pattern PARAMS (`def f(Point(x,y))`).
- [ ] **Elixir** (`sutra-from-elixir/`): multi-clause/guarded bodies with `=` bindings; >2-clause
  recursion (2-clause base+rec only now); `is_integer`-style type-test guards.
- [ ] **Erlang** (`sutra-from-erlang/`): map PATTERN params (`#{x := X}` in a head); multi-clause
  bodies with `=` bindings; >2-clause recursion; list comprehensions; `div`/`rem` via complex
  rotation (NOT `Math.mod`).
- [ ] **Clojure** (`sutra-from-clojure/`): symbol map keys (needs symbol-as-value rep); maps/vectors
  in recursive bodies; nested destructuring (`[[a b] c]`); multi-arity `defn`; `case` symbol/keyword
  members (needs keyword-as-value rep).
- [ ] **Haskell** (`sutra-from-haskell/`): >2-guard guarded recursion; multi-equation guarded
  recursion (`f 0 acc | …; f n acc | …`); mutually-recursive/forward `where`/`let`; nested/
  non-variable constructor `case` patterns; nested tuple/constructor `let` patterns; `case` in
  non-tail expression position. (Laziness out of scope.)
- [ ] **Rust** (`sutra-from-rust/`): nested match inside a tail-match arm; nested tuple patterns
  (`let (a,(b,c))=t`); enum/`Some(x)`-pattern `let` destructuring. (Loop bounds need strict `<`/`>`;
  `<=` drops the boundary iteration — finding `2026-06-13-while-loop-le-boundary-equality-defuzz`.)
- [ ] **OCaml arrays — scalable RAM device for the 10MB linear memory.** `Bytes.make` / loop-carried
  arrays use the global RAM list, which doesn't scale to 10MB. Also: non-zero `Array.make` fill for
  int-dict arrays (slots start at 0 — documented limit, not a bug).
- [ ] **TS follow-on (low priority):** per-variable interface typing so field-type lookup is exact
  when two interfaces share a field name with different types.
- [ ] **WASM source frontend** — the `WASM/`-subtree-tied source→Sutra path (Phase 3 in `todo.md`;
  distinct from the §2 wasm_core VM).

## 6. Python via Pyodide/Wasm (future leg, after the §2 WASM core)

No direct CPython VM (a trap — pure CPython bytecode is useless without C extensions). Python rides
the WASM leg via **Pyodide** (CPython + NumPy/SciPy/pandas compiled to Wasm) → the WASM frontend →
substrate. Standout research angle once WASM/thrml is solid: **physical-entropy NumPy** — wire
NumPy's random draws to the thermodynamic substrate's native sampling entropy (not a PRNG) for
genuinely physical randomness, unifying Sutra's randomness story. (Verbatim rationale in git
history of this file, pre-2026-06-17 cleanup.)

## 7. Merged WASM-repo items (`WASM/` subtree)

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

## 8. RAM inline `await` — blocked remainder

- [ ] **`await` inside a non-async `recur`** — BLOCKED on the await→while_loop lowering
  (promises.md); hits `CodegenNotSupported`. The synchronous-`ramRead`-in-`recur` form already gives
  the read head. Do NOT hack the desugar without settling the semantics.

## 9. FV fill-in — full mixing-rate proof (lowest priority)

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
