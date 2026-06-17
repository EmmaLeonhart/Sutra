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
- **GUI work is on a SEPARATE branch now (Emma 2026-06-16); GUI is OUT of main's queue.**
  The Adam-RLHF GUI demo + its paper (`paper/gui-steering/`) stay built/merged on main, but
  all GUI *agenda* (clawRxiv loop, extensions, paper passes) moved to Emma's own GUI branch
  and was removed from this queue. On **main**, barrel the transpiler / ACTIVE-DIRECTIVE
  track. Do NOT re-add GUI items here.

## 🔥 ACTIVE DIRECTIVE (Emma 2026-06-14 21:06, RE-ORDERED 22:05) — Erlang → FV ACCEPT → rest → FV-expand → ACCEPT

> **GUI MOVED TO ITS OWN BRANCH (Emma 2026-06-16) — this is now the TOP active work on
> main.** GUI agenda was removed from this queue; it lives on Emma's separate GUI branch.
> On main: barrel the transpiler / ACTIVE-DIRECTIVE track below. Do NOT re-add GUI here.

Barrel through these phases IN THIS ORDER (Emma's 22:05 correction — the FV clawRxiv
loop comes RIGHT AFTER Erlang, BEFORE the rest of the transpiler backlog). No stopping
to ask ("barrel through … until you've gotten a strong acceptance").

- **Phase 1 — Erlang frontend. ✅ DONE 2026-06-14** (`sutra-from-erlang`, suite 12/12).
- **Phase 2 — FV-paper → SUBSTANTIVE SCOPE WORK (Emma 2026-06-14 blocker-sweep decision).**
  The clawRxiv ping-pong ran 4 cycles (v64–v71): all FIXABLE cons resolved (hallucinated
  citation, capacity-vs-exactness, self-containment, tone, termination/bit-exact framing,
  Lean-composition roadmap) and randomized-PIT scalability became a credited PRO. Rating
  oscillated Reject↔Weak-Reject — the REMAINING cons are fundamental/philosophical (Kleene
  fragment too narrow; small-scale demos; frozen-substrate trust; bit-exact "brittleness")
  and won't flip by prose edits. Emma's call: **attack the fundamentals with REAL WORK, not
  more framing cycles.** Two concrete substantive moves:
  1. **Prove the GENERAL Lean gadget-composition lemma** (`fv-lean/`): the sum of
     strictly-minimized penalty terms over a shared spin register is itself strictly
     minimized at the consistent joint assignment → a circuit of verified gadgets has its
     correct output as the strict global energy minimum, machine-checked in general (not
     just the 2×2-multiplier instance). Converts §7's stated roadmap into a theorem;
     directly answers the "micro-proofs don't compose" con. Then a multi-gate worked
     instance (e.g. a 2-bit or wider adder/multiplier) checked via the lemma.
  2. **Verify a LARGER program end-to-end** through the framework to answer "demos too
     small / fragment too narrow": push the FV obligation checker / composition past the
     11-expression calc — a non-trivial composed Kleene/arithmetic program with the
     obligations discharged + measured.
  **✅ PHASE 2 COMPLETE — FV PAPER ACCEPTED (clawRxiv v75 = Accept, 2026-06-15).** The
  substantive work landed: general composition lemma + worked two-gate circuit (both
  CI-green; proper-penalty/Ising fix); arithmetic-fragment expansion + compiler-optimization-
  equivalence verification; randomized-PIT scalability — all now credited PROS. Rating went
  Reject↔Weak-Reject → **Accept** (residual cons are acknowledged fundamentals). **Emma
  2026-06-15 blocker-sweep: BANK THE ACCEPT, stop the FV clawRxiv loop, MOVE TO PHASE 3.**
  (The mathlib mixing-rate proof remains available as fill-in if ever wanted, but is no
  longer the active driver.)
- **Phase 3 — the rest of the transpiler backlog + integration (🔥 ACTIVE NOW, Emma
  2026-06-15: gate met, bank the Accept).** Drain the active transpiler increments
  (F#/Elixir/Clojure/Haskell/Rust data-structure tier + remaining shapes — see the
  "Active — transpiler track" section below), then integrate Erlang + all the frontends
  into the architecture docs (`CLAUDE.md`, `AGENTS.md`, `planning/sutra-spec/`, READMEs)
  AND the main Sutra paper (`paper/paper.md`) — measured/accurate, no overclaim.
  Integration DONE 2026-06-15: architecture docs (AGENTS.md, CLAUDE.md) + new spec
  doc `planning/sutra-spec/transpiler-frontends.md` + main paper `paper/paper.md`
  "Source-language frontends" subsection (§ The Sutra Compiler). Spec doc REFRESHED
  2026-06-16 to reflect the sprint's pattern-destructuring tier + multi-clause/guarded
  recursion (maturity table + shared-shapes table re-grounded against the counted
  fixtures). Remaining Phase 3: the long-tail transpiler increments in the "Active —
  transpiler track" section below (lower priority than the integration capstone). The
  main paper (`paper/paper.md` § frontends) is the next doc surface to refresh if the
  frontend story becomes a paper emphasis.
- **Phase 4 — expand the FV paper to all of them + clawRxiv loop AGAIN → ACCEPT. 🔥 NOW
  ACTIVE (Emma 2026-06-17 AskUserQuestion).** The transpiler high-value tiers are done
  across all 9 frontends (pattern-destructuring + multi-clause/guarded recursion + full DU
  support this session). **Emma's framing decision (2026-06-17): expand
  `paper/formal-verification/paper.md` with a CLEARLY-DELINEATED section that frames the
  frontends as EMPIRICAL substrate-verification (compile-AND-run vs ground truth) — kept
  DISTINCT from the Lean-FORMAL gadget proofs. Do NOT conflate the two verification
  notions.** **✅ FV CYCLES DONE 2026-06-17 — banked at Weak Reject; moved to Phase 5.** The §8
  empirical-frontend section shipped + ran 3 clawRxiv cycles (v76 Reject → v77 Weak Reject → v78
  Weak Reject, all Gemini-3-Flash — a different reviewer model than v75's ACCEPT). The
  §8-specific con (over-breadth / "AI-generated breadth" / nine-language / 184-fixture inventory)
  was DRIVEN OUT by the cycle-3 structural trim — absent from v78's cons. The residual v78 cons
  are all FUNDAMENTAL (frozen-substrate "garbage-in formal-proof-out", bit-exact skepticism,
  termination-by-construction, formal-semantics depth) — the class Emma ruled in Phase 2 "won't
  flip by prose edits; attack with real work", and which v75's ACCEPT reviewer accepted. Per
  Emma 2026-06-17 "a few cycles then bytecode" + "a weak reject isn't something we're concerned
  with": banked, NOT chasing the fundamentals with more prose.
- **Phase 5 — bytecode / VM targets (🔥 NOW ACTIVE, Emma 2026-06-17: after FV cycles, before the
  long tail).** Neural-VM legs: WASM machine breadth + JS / JVM bytecode interpreters on the
  substrate (Python rides WASM via Pyodide). **Verified-spec research DONE 2026-06-17 —
  `planning/exploratory/2026-06-17-phase5-bytecode-vm-spec-research.md`.** Findings: WASM is the
  proven, already-built leg (extend `WASM/` — cheapest substrate-verifiable next progress); JVM
  has mature verified specs to specify against (Jinja/JinjaThreads in Isabelle/HOL, Bicolano in
  Coq, ACL2-JVM); CPython has NO verified spec (bytecode is a version-drifting DSL in
  `bytecodes.c`) → confirms Emma's "ride Pyodide/Wasm, no direct CPython VM"; JS lowest priority.
  **Grounded order: (1) extend the WASM machine [substrate-verifiable now]; (2) JVM core specified
  against Jinja's small-step rules, opcode by opcode; (3) Python via WASM+Pyodide; (4) JS.**
  Concrete WASM-leg open items are in the merged WASM queue section below; full plan in the
  raised "Phase 5 — VM/bytecode targets" section below.
- **Phase 6 — transpiler long-tail (Emma 2026-06-17: LAST, after bytecode).** The remaining
  per-frontend edge cases (nested patterns / OCaml RAM device / mutual recursion / multi-arity
  / let-bound `with` source — see "Active — transpiler track" + the per-frontend increment
  sections). Lowest priority of the active phases.
- **Fill-in — full mathlib mixing rate.** When nothing above is immediately actionable,
  do the full t→∞ mixing-rate proof (see the FV section below). (Reachable as fill-in; the
  JS/JVM/Pyodide-Python VM targets are now Phase 5, not "eventually".)

## ✅ COMPLETE — Sutra → thrml (Extropic): submodule + compilation target (Emma 2026-06-13)

Emma's direction (2026-06-13): vendor Extropic's **`thrml`**
(<https://github.com/extropic-ai/thrml>) as a git submodule and make it a Sutra
**compilation target** — a thermodynamic / energy-based backend alongside the
canonical PyTorch one. This is the second task in the queue (after the in-flight
transpiler increment) and a multi-step track to expand as it goes.

**⚠️ NON-DESTRUCTIVE / ADDITIVE-ONLY (Emma 2026-06-13).** The existing neural-
network pipeline is a SEPARATE thing and must stay exactly as it is. thrml is an
**additive command-line OPTION** — a new compile target selected by a flag (e.g.
`--target thrml` / `--emit-thrml` / `--run-thrml`), with the default staying the
PyTorch path. It does NOT rewire, replace, or alter `codegen_pytorch.py`, the
`--emit`/`--run` behavior, or any existing test. If a change to the thrml backend
would touch the shared pipeline destructively, that is NOT what Emma asked — stop
and reconsider. The existing pipeline + all its tests stay green throughout.

What thrml is (researched 2026-06-13): a **JAX** library for GPU block-Gibbs
sampling of **energy-based models** on sparse heterogeneous graphs — Ising/spin
nodes, factor graphs; public API `SpinNode` / `Block` / `SamplingSchedule` /
`IsingEBM` / `IsingSamplingProgram` / `sample_states()`. It is Extropic's
prototyping platform for their **thermodynamic sampling hardware (TSU)**. The
resonance: Sutra is fuzzy-by-default (uncertainty IS ground truth); a
thermodynamic sampler is a physical realization of fuzzy computation.

**This is an EXPLORATION LOOP (Emma 2026-06-13):** "I do not have a massive
preconceived notion of how this works. Try various ways until we can get our
computation to actually work on this hardware … a giant loop of constantly trying
different ways until it actually works." So each work-loop tick = one attempt:
pick an approach, RUN it on thrml, MEASURE, log it in the attempt log
(`planning/open-questions/2026-06-13-sutra-to-thrml-mapping.md`), iterate. We can
change anything that doesn't work. Locked encoding interpretation: a Sutra value
= an N-bit spin register (each bit a `SpinNode`).

- [x] **0. Vendor + study — DONE 2026-06-13.** `external/thrml` submodule pinned
  `db629a0`; API studied + README example RUN on JAX-CPU. Facts:
  `planning/findings/2026-06-13-thrml-api-study.md`. JAX/equinox backend-only.
- [x] **1–5 first-cut attempts — ALL WORK (2026-06-13).** Full measured log in
  `planning/open-questions/2026-06-13-sutra-to-thrml-mapping.md`: associative
  memory (96.8% vs 0%), clamped retrieval (99.2% vs 50%), bind/unbind (100% via
  3-body factor), addition (100% via sample-and-verify, after refuting min-energy
  & weight-ratio), composed kv-query program (100% vs 0% raw). Value=bit-register,
  ops=factors, results-by-sample(+verify) — the mapping runs real Sutra compute.

### thrml — APPROACHES TO TRY (Emma 2026-06-14): implement each, then compare

> The first-cut used hand-built factors + per-op decode. Emma wants the *distinct
> systems* I suggested each implemented and MEASURED, then compared head-to-head.
> Each is its own attempt (RUN + measured + logged in the attempt log). Barrel
> through them top to bottom.

- [ ] **A. Sample-and-verify as the general method.** Generalize the validated
  #4c pattern beyond addition: encode 2–3 more ops as constraint factors
  (equality/compare, select/mux, small multiply) → sample → verify → select.
  Establish "constraint-program → sample-and-verify" as a general compilation
  strategy; measure fidelity + samples needed per op.
- [ ] **B. Ground-state encoding + annealing.** The contrast to A: design proper
  penalty gadgets (e.g. full-adder with an auxiliary spin) so the answer is the
  STRICT global min, and reach it with an annealing β-schedule (staged sampling)
  — target ~100% with a plain modal/min-energy decode, NO verifier. Compare cost
  + fidelity vs A.
- [ ] **C. Trainable couplings (the constrain-train link).** Instead of
  hand-deriving factor weights, LEARN them with thrml's `IsingTrainingSpec` /
  `estimate_kl_grad` (KL-gradient moment matching) so the model reproduces a
  target op's I/O distribution. Ties thrml to Sutra's constrain-train vision;
  measure learned-vs-handbuilt fidelity.
- [ ] **D. Categorical-node encoding.** Represent a Sutra value as a thrml
  `CategoricalNode` (k-state) instead of an N-bit spin register; redo a couple of
  ops; compare fidelity, spin/dim cost, and which ops are cleaner.
- [ ] **E. Joint-EBM composition.** Compose a multi-op program (the kv-query, or
  bind→cleanup) as ONE energy model with competing factors + a single sampling
  run, vs the staged host-handoff of #5; compare fidelity + whether it removes the
  readout boundary.
- [ ] **F. Denser / structured codes.** Push associative-memory capacity beyond
  the measured ~0.14·N Hopfield wall with structured codes (block/ECC-style);
  measure the capacity gain vs random ±1 registers.
- [x] **G. codegen_thrml backend — DONE through op-graphs (2026-06-14).** Additive
  `--emit-thrml` flag + `codegen_thrml.translate_thrml` (non-destructive:
  `codegen_pytorch.py` / `--emit` / `--run` untouched, guarded by tests). Lowers a
  `main` body of `vector tmp = bind/unbind(x,y);` intermediates + `return …` over
  `basis_vector` atoms to a self-verifying thrml program: value = 16-bit spin
  register, bind/unbind = the 3-body product factor, atoms clamped,
  intermediates+result sampled jointly. `examples/thrml_bind.su` (1 op) and
  `thrml_roundtrip.su` (`unbind(bind(a,b),a)=b`, 2 factors) compile AND sample =
  **1.000** per-bit. `tests/test_codegen_thrml.py` 4/4. Unsupported constructs raise
  `ThrmlCodegenNotSupported` (no silent mislowering). Future extension (not
  blocking H): `bundle` + `unbind`+cleanup (the kv-query) need a codebook-cleanup
  decode; `==`/AND need the gadget lowering — open design points, deferred.
- [x] **H. COMPARE ALL — DONE 2026-06-14.** Head-to-head of A–G (measured table +
  cross-cutting trade-offs + recommendation) in
  `planning/findings/2026-06-14-thrml-approaches-comparison.md`. Standardize on:
  bit-registers + sample-and-verify (A) as the default lowering (general, robust,
  what G targets); ground-state decode (B) as the verifier-free fast path for
  sign-correct gadgets; categorical (D) for small-domain maps; structured codes
  (F) + trainable couplings (C) for associative-memory capacity; staged
  composition by default, joint-EBM (E) only for readout-purity. Optional
  follow-up: a human-facing `docs/` page (the capability is website-worthy).
- [x] **Hardware-alignment notes — DONE 2026-06-14.**
  `planning/findings/2026-06-14-thrml-hardware-alignment.md`. Grounded in the
  Extropic TSU paper (vendored): chip = sparse, locally-connected, **pairwise**
  p-bit grid sampling via two-color block Gibbs; **host programs weights + reads
  the result** (matches our host-side verifier/decode/compositor). Non-obvious
  finding: our **AND + carry gadgets are already pairwise → TSU-native**;
  bind/XOR/parity (3-/4-body) need a local auxiliary-spin reduction; dense Hopfield
  memory (all-to-all) is the LEAST chip-aligned (a prototyping-layer strength).
  Refined recommendation: keep graphs sparse + 2-body for the chip; the
  gate-circuit + sample-and-verify path is the most TSU-aligned compute path.

**⟹ The Sutra→thrml track (A–H + codegen + hardware notes) is COMPLETE.** Next
queue item is the FV-in-Lean section below, then the a1 demo.

HARD RAILS: every op runs on the (sampling) substrate; no faked results; RUN +
MEASURE every attempt (gap vs baseline, never asserted); read thrml's ACTUAL API
(NO MATH SHORTCUTS / no invented primitives). Failed attempts are logged as
negative results, not hidden.

## Active — transpiler track (source -> Sutra) — continues (now second to the thrml track)

### 🔍 Daily substrate-honesty audit — 2026-06-17

Auto-prepended by .github/workflows/daily-audit.yml. The next autonomous-loop session should, as its first action: review every commit landed since the previous daily audit against CLAUDE.md § "Subtler substrate breaches — measurement-required": (a) for each commit touching a .su or its compile path, verify runtime_dim matches what the .su actually needs (count basis_vector calls; no basis_vector → tiny dim); (b) for any commit that frames work as "recurrent" / "RNN" / "substrate-pure" / "verified", verify the claim against measurement, not against earlier session framing; (c) for any commit shipping a substrate classifier or decision function, verify the measured gap = min(positive_class) - max(negative_class) is in the commit or planning doc. If anything is amiss, write a finding under planning/findings/ and a fix item under queue.md BEFORE doing other queue work. Then delete this item.

> New-language frontends are the loop's active track (Emma roadmap order:
> Scala → F# → Elixir/Erlang → Clojure → Haskell → Rust → WASM). Each models on
> `sutra-from-ocaml` (the reference frontend; OCaml `let rec` incl. non-tail
> recursion is done — foldable CPS transform + Tree RNN, see DEVLOG/findings).
> Roadmap: todo.md §"Multi-language transpiler frontends".

- [ ] **F# next increments** (`sdk/sutra-from-fsharp/`; through tuples `(a, b)` →
  positional-key axons (`int * int` param → Axon, `fst`/`snd` → `_0`/`_1`, let-bound
  construction) + `let (a, b) = t` tuple-pattern destructuring shipped 2026-06-16,
  suite 28/28): nested tuple/record patterns (`let (a, (b, c)) = t`); nullary variant as a
  direct function RETURN (`let f () = North` — arg + let-value positions done, return needs the
  prelude+return shape); record-update from a LET-BOUND (non-param) source (`let q = {b with …}`
  where b is a record literal — needs literal-type inference; param-typed source done). [`let {
  x = a } = p` record-pattern + `let (Circle r) = s` DU-case-pattern destructuring + record
  functional-update `{ p with x = 9 }` (param-typed source: override + copy non-overridden) +
  tuple/record/DU construction DIRECTLY in ARGUMENT position (arg-hoist parity) + nullary DU
  variants in value
  position (`code South` → `{_tag}` axon) shipped 2026-06-16, suite 38/38.] Measured grammar
  quirk: parenthesize call operands under infix. [Scala 24/24 — `val (a, b) = t` tuple-pattern (1-based keys) + `val Point(a, b)
  = p` case-class-pattern destructuring done 2026-06-16; remaining Scala: nested patterns,
  case-class pattern PARAMS (`def f(Point(x, y))`).]
- [ ] **Elixir next increments** (`sdk/sutra-from-elixir/`; through tuples `{a, b}` →
  positional-key axons + `elem(t, i)` access + `{a, b}` tuple-PATTERN + `%{x: a}` map-PATTERN
  + `%Name{x: a}` struct-PATTERN params + do-block `=` pattern-match destructure (`{a, b} = t`)
  + multi-clause recursion — SINGLE-PARAM (`def fac(0)/fac(n)`), MULTI-PARAM tail (`def
  sum(0, acc)/sum(n, acc)`), AND GUARDED-base (`def fac(n) when n == 0/def fac(n)`) shipped
  2026-06-16, suite 42/42): multi-clause/guarded bodies with `=` bindings (single-clause only
  now); >2-clause recursion (2-clause base+rec only now); `is_integer`-style type-test guards
  (`and`/`or` chains already lower via `_OP_MAP`). (Erlang is its own frontend — port the
  guarded-base recursion there next.)
  > **F# RECORDS → axons SHIPPED 2026-06-16.** All prereqs done: (a) typed-param
  > extraction (`(p: Point)`); (b) let-SEQUENCE bodies; (c) a let-bound construction
  > hoist — `_PRELUDE` accumulator emits record `{ x = a }` literals as `Axon q;
  > q.add("x", a);` statements before the return, `_AXON_VARS` tracks axon-typed names
  > so `p.x` dispatches to `realvec(p.item("x"))`, `_RECORD_TYPES` (prepass on
  > `record_type_defn`) types `(p: Point)` params as `Axon`. Fixture `record_axon`
  > runs on substrate → 13. NEXT for F#: DU variants → tagged axons (the dedicated
  > "F# next increments" bullet above now covers it).
- [ ] **Clojure next increments** (`sdk/sutra-from-clojure/`; through data vectors `[a b]`
  → positional-key axons + `(nth v i)` access + `(let [[a b] v] …)` vector + `{:keys [..]}` /
  `{a :x}` map destructuring shipped 2026-06-16, suite 36/36; `_collect_binding_vecs` +
  `_mark_binding_pattern` keep binding vectors/maps AND nested patterns from being hoisted as
  data): symbol map keys (needs a symbol-as-value rep); maps/vectors in recursive bodies;
  nested destructuring patterns (`[[a b] c]`); multi-arity `defn`; `case` symbol/keyword test
  members (needs a keyword-as-value rep).
- [ ] **Haskell next increments** (`sdk/sutra-from-haskell/`; through tuples `(a, b)` →
  positional-key axons (`(Int,Int)` sig → Axon, `fst`/`snd` → `_0`/`_1`, arg-position hoist)
  + `let (a, b) = t` tuple-pattern + `let (Wrap a b) = w` single-constructor-pattern
  destructuring + multi-equation recursion — both SINGLE-PARAM (`fac 0/fac n`) AND MULTI-PARAM
  tail (`sum 0 acc = acc; sum n acc = sum (n-1) (acc+n)`, base-equation var renaming) +
  GUARDED recursion — single-param (`fac n | n == 0 = 1 | otherwise = n*fac (n-1)`) AND
  multi-param tail (`sumTo n acc | n == 0 = acc | otherwise = sumTo (n-1) (acc+n)`) shipped
  2026-06-16, suite 34/34; laziness out of scope): >2-guard guarded recursion (2-guard
  cond+otherwise only now); multi-equation guarded recursion (`f 0 acc | … ; f n acc | …`);
  mutually-recursive/forward `where`/`let` bindings; nested/non-variable constructor `case`
  patterns; nested tuple/constructor `let` patterns; `case` in non-tail expression position.
- [ ] **Rust next increments** (`sdk/sutra-from-rust/`; through tuples `(a, b)` →
  positional-key axons + `p.0`/`p.1` access + `let (a, b) = t` tuple-pattern + `let Point
  { x, y } = p` struct-pattern destructuring + nullary-variant values (`Dir::South` → `{_tag}`
  axon, scoped match patterns guarded from the value-hoist via `.parent`) shipped 2026-06-16,
  + nullary-variant `let` value (`let d = Dir::South` → Axon-typed local) shipped 2026-06-16,
  suite 36/36): nested match inside a tail-match arm; nested tuple patterns (`let (a, (b, c)) =
  t`); enum/`Some(x)`-pattern `let` destructuring.
  (Loop bounds need strict `<`/`>` — `<=` drops the boundary iteration, finding
  `2026-06-13-while-loop-le-boundary-equality-defuzz`; same caveat applies to the negated
  *break* condition, so write `if i >= n { break; }`.)
- [ ] **WASM** — Phase 3 (todo.md), tied to the `WASM/` subtree.
- [ ] **OCaml arrays — RAM device for the 10MB linear memory.** `Bytes.make` and
  loop-carried arrays use the global RAM list, which doesn't scale to 10MB. A
  scalable RAM device is the remaining array work (the ordinary-array →
  int-dict split shipped 2026-06-13; see below). Also: non-zero `Array.make`
  fill value for int-dict arrays (slots start at 0; straight-line arrays write
  before read, so this is a documented limit, not a bug).
- [ ] **TS follow-on (low priority):** per-variable interface typing so field-type
  lookup is exact when two interfaces share a field name with different types
  (current global map marks collisions non-numeric to stay safe; no fixture needs it).
  > **`transpilers-ci.yml` SHIPPED 2026-06-16 (Emma greenlit "full CI including
  > F#/Erlang/Clojure" via AskUserQuestion).** Runs all 9 frontend suites
  > (compile-AND-run on the substrate) on push/PR to `sdk/sutra-from-**`: pip-installs
  > the 6 wheel grammars + torch + the compiler, and gcc-builds the F#/Erlang/Clojure
  > tree-sitter grammars into `.so` on the Linux runner (the loaders are now
  > platform-aware: `.dll` on win32, `.so` elsewhere). Verify the run goes green and
  > iterate if a grammar build / ABI mismatch shows up. (The compile-AND-run bar is
  > already met by each frontend's own harness.)

## Next-venue paper polish (UNFROZEN — active)

`paper/paper.md`: ablation table for the §3.7 weighted-Equals training is DONE
(2026-06-13, measured: full/prototypes-only/gain-only — prototypes carry the
separation, the gain is co-adapted not load-bearing;
`experiments/differentiable_training_ablation.py`). Remaining optional polish:
a capacity-style ablation (mean-centering on/off, dimension sweep) if wanted —
measured numbers only, never from memory.

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

## Erlang frontend — next increments (MVP shipped 2026-06-14, suite 12/12)

`sdk/sutra-from-erlang/` is built: grammar DLL via `build_grammar.py` (WhatsApp
tree-sitter-erlang, parser.c+scanner.c → `_grammar/erlang.dll`); lowering covers
functions/calls/binary-ops, `if`/`case` → blend, multi-clause heads + `when` guards →
dispatch blend, `if`-based tail rec → `while_loop`, foldable non-tail → CPS. Remaining:

- [ ] **Erlang increments** (through records `#name{f=v}` → named-field axons +
  `R#name.f` access + `{A, B}` tuple-PATTERN + `#point{x=X}` record-PATTERN params + body
  `=` match destructure (`{A, B} = P`) + multi-clause recursion — SINGLE-PARAM (`fac(0)/fac(N)`),
  MULTI-PARAM tail (`sum(0, Acc) -> Acc; sum(N, Acc) -> sum(N-1, Acc+N)`, base-clause var
  renaming), AND GUARDED-base (`fac(N) when N == 0 -> 1; fac(N) -> …`) shipped 2026-06-16, suite
  30/30; the `-record` decl is skipped, name dropped): map PATTERN params (`#{x := X}` in a head);
  multi-clause bodies with `=` bindings (single-clause only now); >2-clause recursion (2-clause
  base+rec only now); list comprehensions; `div`/`rem` via complex rotation (not `Math.mod`).

## Formal verification of thrml gadgets in Lean + clawRxiv loop (Emma 2026-06-14)

Per the ACTIVE DIRECTIVE at the top: the FV-paper research loop (respond to
critiques + expand toward a Strong Accept) is **Phase 3**, after Erlang + the
transpiler backlog (Phase 1) and the architecture/paper integration (Phase 2). The
gadget Lean proofs + mid-size mathlib are done; what remains here is the clawRxiv
loop toward Strong Accept (Phase 3) and the full mixing-rate mathlib (fill-in).

Emma's direction (clarifying her 2026-06-14 queue seed): take the energy-based
gadgets validated in
`planning/open-questions/2026-06-13-sutra-to-thrml-mapping.md` and **formally
verify them in Lean** — i.e. prove the things currently shown only by measurement:
the correct answer is the strict global energy minimum (AND/adder/multiplier
gadgets), and the sampler converges to it. Then **run the autonomous clawRxiv
research loop** on the writeup. **"stochastic ODEs"** is Emma's hint for the
convergence theory — the continuous-time limit of block-Gibbs / Langevin dynamics
is a stochastic ODE/SDE, the natural frame for a proof that the thermodynamic
sampler reaches the ground state.

**STARTED 2026-06-14.** Lean4 (via elan, core only — no mathlib) installed.
`fv-lean/AndGadget.lean`: the **AND gadget ground-state is machine-checked** —
`and_gadget_min` (correct output attains the min) + `and_gadget_strict` (every
wrong output strictly higher → unique minimiser), axioms `[propext, Quot.sound]`,
NO sorry. Runner `scripts/check_fv_lean.sh`. So what A2 measured (100%) and C
re-learned is now formally correct. `fv-lean/XorGadget.lean` (the 3-body XOR — pins
the correct sign that the 2026-06-14 bug got wrong) and `fv-lean/FullAdder.lean`
(sum=parity + carry=majority → addition's ground state is provably the correct
(s,cout)) are also machine-checked, no sorry. The 2×2 multiplier is these gates
composed, so its correctness follows. The gadget-FV result is recorded in the
authoritative FV spec (`planning/sutra-spec/formal-verification.md` § "thrml
compile-target"). Remaining:
- [x] **clawRxiv writeup — DONE 2026-06-14.** Added §7 "A second compile target"
  to `paper/formal-verification/paper.md` (gadget ground-states machine-checked in
  Lean; honest "what this does not yet prove" on convergence) + abstract clause +
  conclusion road-ahead; Conclusion renumbered §7→§8. The push auto-submits via
  `fv-paper-ci.yml` → runs the clawRxiv loop (review lands under `paper/reviews/`).
- [ ] **Sampler-convergence — full t→∞ mixing RATE (GREENLIT by Emma 2026-06-14 21:06
  as fill-in work — "do the full mathlib" when nothing else is pending).** The
  mid-size step is DONE: `fv-lean/mathlib/GibbsMathlib.lean` (isolated Lake project,
  mathlib v4.30.0) machine-checks `stationary_of_detailedBalance` (reversibility ⟹
  stationarity, general finite chain), `gibbsKernel_detailedBalance` +
  `gibbsKernel_stationary` (the gadget's real-`exp` Gibbs kernel is reversible → the
  Gibbs measure is stationary), and `stationary_unique_two_state` (2-state
  Perron–Frobenius uniqueness) — all `[propext, Classical.choice, Quot.sound]`, no
  sorry, `lake build` green. Combined with the core-only irreducibility/aperiodicity:
  positive + irreducible + reversible finite chain ⟹ unique stationary = Gibbs. NOW
  DO: the t→∞ **mixing rate** / spectral-gap (full TV-mixing convergence) in the same
  `fv-lean/mathlib/` project — the spectral gap of the reversible kernel / contraction
  to the Gibbs measure. Mathlib has finite-Markov / spectral infrastructure; scope to
  the gadget chain. Fill-in priority: do when the Erlang + integration + FV-loop work
  below has no immediately-actionable item. Local-verified (heavy toolchain, not CI).

Ties into the existing FV track (`planning/sutra-spec/formal-verification.md`,
`paper/formal-verification/paper.md`, the clawRxiv loop). Scope is settled by
Emma's clarification above (verify the gadgets in Lean + run the clawRxiv loop);
just do it when the loop reaches it.

## Phase 5 — VM/bytecode targets for maximum imperative functionality (Emma 2026-06-14 21:17; priority RAISED 2026-06-17)

**PRIORITY RAISED (Emma 2026-06-17): this is now Phase 5 — runs right after the FV-paper
clawRxiv cycles (Phase 4), BEFORE the transpiler long-tail (Phase 6). No longer "very end of
the queue." The plan below is unchanged; only its position moved up.**

Emma's framing: implementing **JS + WASM + CPython + JVM** as bytecode/VM targets in
Sutra would, taken together, be the best comprehensive route to **maximum imperative
functionality** in Sutra — "even though all of it is a bit weird." This is the
neural-VM direction (the same shape as the already-built Neural WebAssembly machine in
the `WASM/` subtree, which is the WASM leg): build a substrate program that interprets
each VM's bytecode, so any language compiling to that bytecode runs on Sutra.

**Update (Emma 2026-06-14 21:26): CPython folds into WASM** (CPython-direct is a trap;
Python rides Pyodide/Wasm Python through the existing WASM frontend — see the dedicated
leg below). So the effective legs are **WASM (+ Python via Pyodide), JS, JVM**.

The legs:
- **WASM** — already underway: the substrate WASM machine (`WASM/`, Turing-complete,
  21 opcodes, ISO-5; see the merged WASM queue section above). This is the proof the
  approach works; the others generalize it.
- **JS** — a JavaScript engine/bytecode target. (Distinct from the existing
  `sutra-from-ts` *transpiler*, which lowers TS source to Sutra — this would be a JS
  VM, the imperative-runtime route.) Weirdest of the four; scope TBD.
- **CPython bytecode — TRAP; do NOT implement directly (Emma 2026-06-14 21:26).** A
  standalone CPython VM is a dead end: nobody writes pure CPython bytecode, real
  Python immediately reaches for C extensions, so a bare VM breaks on ~90% of code.
  The correct route is **Pyodide/Wasm Python** → the existing WASM frontend (see the
  dedicated leg below). So Python is folded into the WASM leg, not its own VM.
- **JVM bytecode** — a JVM (interpret JVM bytecode on the substrate).

### Python via Pyodide/Wasm — the correct route (Emma 2026-06-14 21:26)

Emma's decision (chatbot info recorded verbatim for grounding — verify before relying):

> Exactly right — CPython without its ecosystem is basically useless. Nobody writes
> pure CPython bytecode, everything immediately reaches for extensions. It's a trap
> because you'd implement the VM and then discover 90% of real Python code immediately
> breaks on missing C extensions.
>
> **Wasm Python (Pyodide essentially) is the correct approach** because:
> - CPython itself compiled to Wasm
> - NumPy, SciPy, pandas etc. compiled to Wasm
> - The whole thing is self-contained and portable
> - You get the actual ecosystem not just the interpreter
>
> So the path would be:
>
>     Python source
>         ↓
>     Pyodide/Wasm Python runtime (self-contained)
>         ↓
>     Sutra via your existing Wasm frontend
>         ↓
>     Thermodynamic hardware
>
> And since you already have Wasm working, Python basically comes for free if someone
> has already done the Pyodide-style compilation work — which they have, it's open
> source.
>
> The interesting research question then becomes what happens to **stochastic Python** —
> like if NumPy random draws from the thermodynamic substrate's natural entropy rather
> than a PRNG, you get genuinely physical randomness essentially for free, which closes
> the loop back to your randomness unification problem.
>
> That's actually a really clean story for a paper or pitch — "we ran Python's ML
> ecosystem on thermodynamic hardware and replaced synthetic randomness with physical
> entropy."

So: **no direct CPython VM**; Python rides the WASM leg via Pyodide. The standout
research angle to chase once the WASM/thrml path is solid: **physical-entropy NumPy** —
wire NumPy's random draws to the thermodynamic substrate's native sampling entropy
(not a PRNG), giving genuinely physical randomness for free and unifying Sutra's
randomness story. The pitch: Python's ML ecosystem on thermodynamic hardware with
synthetic randomness replaced by physical entropy. (Ties to the thrml track: the
sampler IS an entropy source.)

Licensing / specs (info a chatbot gave Emma, recorded verbatim for grounding — verify
before relying):

> Yes, both are open source:
>
> **CPython** — Python Software Foundation License (PSF), essentially BSD-style
> permissive. The full source is on GitHub. So the bytecode spec, the VM
> implementation, everything is available to study.
>
> **JVM** — more complicated:
> - The spec itself is openly documented (the Java Virtual Machine Specification is a
>   public document)
> - OpenJDK is the open source reference implementation, GPL v2 with Classpath Exception
> - Oracle's JDK is proprietary but OpenJDK is what most people use now
>
> For your purposes the JVM spec is actually the most useful artifact — it's a formal
> document describing the bytecode instruction set, type verifier, class file format
> etc. People have built alternative JVM implementations (GraalVM, Azul) from it.
>
> The practical question is whether anyone has done formal verification work on either
> that you could build on the way you did with Wasm. My guess:
> - **JVM** — probably some academic work, it's been around long enough and is
>   important enough
> - **CPython bytecode** — less likely, it's less formally specified and changes
>   between Python versions
>
> Worth searching before committing to implementing either from scratch.

**First step when this is picked up:** search for existing *verified* specs / formal
semantics for the JVM bytecode and CPython bytecode (as was leveraged for WASM) before
implementing either from scratch — a verified spec to build on changes the cost
dramatically. The JVM spec (formal bytecode instruction set + type verifier + class
file format) is the most useful single artifact; CPython is less formally specified and
drifts across versions, so pin a CPython version. Licenses (PSF for CPython, JVM spec
public + OpenJDK GPLv2+Classpath) are permissive enough to study and build on.

## 📚 Comprehensive Sutra documentation audit + rework (Emma 2026-06-16, very-end-of-queue)

**End-of-queue standing item.** Sutra is a **business**, not a research project — the docs
should read like a product/business's docs, coherent and current. Do a comprehensive
audit and rework of ALL Sutra documentation: the website (`docs/`), `README.md`,
`AGENTS.md`, `CLAUDE.md`, `paper/` framing, the `sdk/*/README.md` set, and
`planning/sutra-spec/`. Check for: contradictions between surfaces, stale claims, dead
internal refs on the website (humans-read-the-site rule), the right business framing, and
gaps where a real capability is undocumented. Plan it into concrete per-surface steps when
reached; verify against the codebase (grep, don't trust memory). Do NOT start until the
GUI rebuild + the ACTIVE DIRECTIVE phases ahead of it are clear, unless Emma re-prioritizes.

## Pointers

- Substrate-leak catalogue: `Audit.md`. Longer-horizon: `todo.md`.
- GUI: demos `demos/gui/`, experiments `experiments/gui_*.py`, paper
  `paper/gui-steering/`, page `docs/gui.md`. Agenda: `todo.md` §"GUI".
- Findings (dated): `planning/findings/`. Open design questions:
  `planning/open-questions/`. Devlog: `DEVLOG.md`.
- Corpus repo: `github.com/EmmaLeonhart/sutra-w2c-corpus` (submodule
  `corpus/`) + `huggingface.co/datasets/EmmaLeonhart/sutra-w2c-corpus`.
- Yantra (downstream OS): `../Yantra/`.
