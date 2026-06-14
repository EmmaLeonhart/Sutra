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

## 🔥 NEXT MAJOR TRACK — Sutra → thrml (Extropic): submodule + compilation target (Emma 2026-06-13)

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

> New-language frontends are the loop's active track (Emma roadmap order:
> Scala → F# → Elixir/Erlang → Clojure → Haskell → Rust → WASM). Each models on
> `sutra-from-ocaml` (the reference frontend; OCaml `let rec` incl. non-tail
> recursion is done — foldable CPS transform + Tree RNN, see DEVLOG/findings).
> Roadmap: todo.md §"Multi-language transpiler frontends".

- [ ] **F# next increments** (`sdk/sutra-from-fsharp/`; through name-binding
  `match` patterns shipped 2026-06-13, suite 14/14): type annotations;
  variant/record `match` patterns; records/DUs → axons (needs the infra in the
  dedicated item below). Measured grammar quirk: parenthesize call operands under
  infix. [Scala's named roadmap set is COMPLETE 2026-06-12, 18/18.]
- [ ] **Elixir next increments** (`sdk/sutra-from-elixir/`; through multi-clause
  `def` heads shipped 2026-06-13, suite 14/14): maps/structs → axons; guards on
  clause heads; pipe operator; multi-clause heads with recursion (currently
  `UNSUPPORTED-RECURSION`). (Erlang proper is a separate later frontend.)
- [ ] **F# records/DUs → axons — needs F# infrastructure first.** Records port
  the OCaml pattern conceptually, but F# lacks the prerequisites: (a) typed-param
  extraction (`(p: Point)` is a `typed_pattern`, the current param loop only
  handles bare/unit); (b) let-SEQUENCE function bodies (a `let a = … ; expr` body
  is nested `declaration_expression`s; `_lower_expr` currently takes only the
  first child); (c) a construction hoist (F# has none — needed for brace
  construction in argument position) OR let-bound-only construction (needs (b)).
  Field access `p.x` is a dotted `long_identifier`, not a `field_expression`.
  Build (a)+(b)+the hoist first, then records are straightforward.
- [ ] **Clojure next increments** (`sdk/sutra-from-clojure/`; through `case` →
  nested equality blend shipped 2026-06-14, suite 18/18): maps → axons;
  destructuring binds; multi-arity `defn`; `case` multi-constant test lists.
- [ ] **Haskell next increments** (`sdk/sutra-from-haskell/`; through pattern
  equations + guards shipped 2026-06-13, suite 12/12; laziness out of scope):
  where/let bindings; `data` ADTs → tagged axons; guarded/multi-equation
  recursion (currently `UNSUPPORTED-RECURSION`); non-integer literal patterns.
- [ ] **Rust next increments** (`sdk/sutra-from-rust/`; through compound assignment
  shipped 2026-06-13, suite 18/18): unbounded `loop { … break }` (halt-flag
  transform); nested/non-tail `match`; field-init shorthand / `..base`. (Loop
  bounds need strict `<`/`>` — `<=` drops the boundary iteration, finding
  `2026-06-13-while-loop-le-boundary-equality-defuzz`.)
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
- [ ] **Cross-cutting:** extend OCaml's compile-AND-run `_RUNNABLE_FIXTURES` bar to
  every frontend; consider a `transpilers-ci.yml` running all `sutra-from-*` suites
  (scope decision — not auto-started).

## FV paper §7 — bridge the framework TO thrml (Emma 2026-06-14 blocker-sweep)

`paper/formal-verification/paper.md` is the live FV paper (paper/neurips/ frozen;
this one is not). clawRxiv v64 (Reject) credited the §7 Lean gadget proofs but
called §7 "disconnected / trivial 3-var gates." Emma's call: **tighten the
connection, but bridge the OTHER material TO thrml — "thrml is the more important
part."** So reframe so the energy-based / thrml compile target reads as central,
not bolted-on: add a bridge connecting the PIT-reduction / tensor-op verification
framework to the thrml energy-gadget verification, positioning thrml as the more
important direction (honestly — no overclaim; thrml is the additive backend, the
gadgets are 3-var, the convergence floor is finite). NOT a wholesale thesis
rewrite in one tick; a real bridge + emphasis shift. Push triggers fv-paper-ci →
clawRxiv loop (real content change, legitimate resubmit).

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

## Future transpiler frontends — backlog (Emma 2026-06-13, bottom of queue)

Added to the bottom of the queue after the core roadmap pass (Scala/F#/Elixir/
Clojure/Haskell/Rust all have functions + if/match→blend + tail rec→while_loop +
foldable non-tail→CPS as of 2026-06-13). Lower priority than the thrml track and
the existing frontends' data-structure tier.

- [ ] **Erlang** — its own frontend (Elixir is done on the BEAM, but Erlang's own
  syntax/grammar is separate). Model on `sutra-from-ocaml`; reuse the shared
  shapes (multi-clause function heads with guards map to the dispatch blend).

## Formal verification of thrml gadgets in Lean + clawRxiv loop (Emma 2026-06-14)

**NOT parked — just LAST in the queue, to be done AUTONOMOUSLY after the thrml
A–H approaches** (Emma 2026-06-14: "the fv and a1 are not parked, they are just
last in the queue after the other things; they should be automatically done after
other stuff"). The work-loop reaches it in order and does it like any other item;
no waiting for Emma. Comes BEFORE the a1 GUI demo below.

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
- [ ] **Sampler-convergence — MID-SIZE mathlib step (Emma 2026-06-14 blocker-sweep).**
  The BOUNDED floor is DONE: `fv-lean/GibbsChain.lean` machine-checks the single-
  gadget Glauber chain is `irreducible` + `aperiodic` (no axioms) + `and_gibbs_
  unique_mode` (`[propext, Quot.sound]`), no sorry, CI-green. Emma's call: go to a
  **mid-size mathlib step**, NOT the full t→∞ TV-mixing theorem. Scope: install
  mathlib (as its own step — `lake` project + `lake exe cache get` for prebuilt
  oleans, pin a mathlib commit compatible with Lean v4.30.0) and prove **detailed
  balance** `π(s)P(s,t)=π(t)P(t,s)` for the gadget Gibbs kernel + **finite-chain
  stationary uniqueness** (Perron–Frobenius on the gadget) — short of full mixing.
  This needs the real-valued transition probabilities + `exp` (why it needs
  mathlib). Set up the mathlib project under `fv-lean/` (separate Lake target so the
  core-only files keep their no-mathlib CI path).

Ties into the existing FV track (`planning/sutra-spec/formal-verification.md`,
`paper/formal-verification/paper.md`, the clawRxiv loop). Scope is settled by
Emma's clarification above (verify the gadgets in Lean + run the clawRxiv loop);
just do it when the loop reaches it.

## Demo — warmer/colder self-morphing hero (Emma 2026-06-14, last in queue)

**NOT parked — just LAST in the queue, done AUTONOMOUSLY after the FV item above**
(Emma 2026-06-14). The build is ASSEMBLY of parts that already exist —
runtime-parameter whole-frame rendering (`demos/gui/whole_frame.py`,
`frame_moving.su`; params are per-call broadcast buffers, no recompile) + a
batched SPSA optimizer + warmer/colder controls — into one recordable interactive
demo. No new substrate research. (Emma records it herself once built; building is
autonomous.)

- [ ] **Warmer/colder steering demo.** A substrate-rendered hero (headline glyphs
  via the 36-glyph renderer + accent glow/ring + a CTA block) whose
  layout/scale/color/spacing/headline-choice form a parameter vector θ ∈ R^8–16;
  WARMER / COLDER buttons emit scalar reward (+1 / −1, smoothed); a batched SPSA
  step updates θ with [-1,1]^d clamping; the hero visibly morphs. Local window
  first (screen-recordable), optional web wrapper later. Done = a stranger
  steering it sees directionally-consistent morphing within seconds, with no
  NaN/blank frames across a 100-press session. Full build spec (5 steps, ~4–5
  days, with the SPSA port source) lives in the private founder hub:
  `../emmas-gstack/business/gtm/2026-06-13-a1-shortest-path.md` (+ the detailed
  `business/gtm/a1-implementation-spec.md`). Honest rails for the artifact:
  composition is host-side and the optimizer is host-side SPSA over
  substrate-rendered output — do not over-claim "one substrate program" or
  substrate-native training.

## Pointers

- Substrate-leak catalogue: `Audit.md`. Longer-horizon: `todo.md`.
- Findings (dated): `planning/findings/`. Open design questions:
  `planning/open-questions/`. Devlog: `DEVLOG.md`.
- Corpus repo: `github.com/EmmaLeonhart/sutra-w2c-corpus` (submodule
  `corpus/`) + `huggingface.co/datasets/EmmaLeonhart/sutra-w2c-corpus`.
- Yantra (downstream OS): `../Yantra/`.
