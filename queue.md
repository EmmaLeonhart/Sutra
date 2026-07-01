# Sutra — Work Queue

**This file is a queue, not a state snapshot.** It lists what is being worked on now and
what is next, in execution order — barrel it top to bottom. **Finished work is REMOVED in the
same commit it ships** (history lives in `git log`, `DEVLOG.md`, `planning/findings/`).
`todo.md` is the longer-horizon backlog; items migrate `todo.md` → here → deleted on completion.

**⭐ CLEARING the queue is the SAFE default (Emma 2026-06-21).** When an item is done, DELETE the
line — **version control + `DEVLOG.md` already hold the entire history, so nothing is ever lost by
removing it.** Deleting a finished item is NEVER the risky move; the git log is the safety net.
The UNSAFE thing is letting done work accumulate — a "Recently shipped" pointer block,
`~~struck-through~~` lines, "DONE"/"✓" markers, or a paragraph summarizing what shipped. That bloat
buries the open work and is exactly what keeps re-growing this file. The queue holds ONLY
not-yet-done work; the moment something ships, it leaves. **Do not defer work to a clock time either**
— if nothing else is in flight, just do it now (no "do this at 2pm" scheduling).

**Owned + autonomous (Emma 2026-06-20):** the agent organises this queue itself — pulls items from
`todo.md`/findings/specs, orders by value, decomposes into concrete steps, prunes done work, and
executes top-to-bottom WITHOUT asking. Report via commits + DEVLOG, not questions.

---

## ⭐⭐ FIRST — FV-Lean handoff (hub session, 2026-06-29; do this before anything else)

**Read `FV-LEAN-HANDOFF-2026-06-29.md` (repo root) top to bottom before touching `fv-lean/`
or the FV paper.** It records a multi-session collision and a set of real findings: the mathlib
layer is not in CI, `GibbsMultiState.lean` was committed without compiling, the mathlib cache was
corrupted (now re-fetched by the hub), and the FV paper swung to a Strong Reject whose cons match
the known doc-drift. Then:

1. Run **AskUserQuestion** on any issue in that doc that is genuinely Emma's call (she is likely
   out — it sends a phone notification; plain chat does not).
2. **Restart the KILLED cron** the doc documents (§6a: the 1 PM comprehensive work-through
   `fb3dfaa1`, which the hub cancelled — its work belongs on this session). Re-create it here via
   `CronCreate`. Do NOT recreate the hub's own watchdog/closeout crons — those run in the hub.
3. Work the doc's action list (§7): confirm/fix the mathlib layer compiling, wire the mathlib
   layer into CI, build the `Sutra.Convergence` Z-transform/spectral unification, and fix the FV
   paper (`bit-exact → p-bit-exact`, expose the Lean proof structure, single spine) — **commit +
   push every paper edit** (the push triggers the clawRxiv review).
4. **Check each item off in the doc's §8 checklist** as you finish it — but **remove THIS queue
   item only when the whole handoff is genuinely done** (the 17:00 closeout cron verifies and then
   deletes the doc). Do not claim anything proven that `lean` has not accepted.

---

## Context (read first, do not work on)

- **`paper/paper.md` is UNFROZEN** (Emma 2026-06-07); `paper/neurips/` freeze RETIRED 2026-06-18.
  Measured numbers only; no overclaiming. Editing `paper/formal-verification/paper.md` or
  `paper/paper.md` triggers a clawRxiv resubmit CI — intended for real updates, not churn.
- **NEVER use `Math.mod`** (measured vector-collapse/NaN). Use complex rotation for wrap/periodic.
- **GUI is on Emma's SEPARATE branch** — OUT of this queue. Do NOT re-add GUI items.
- **Substrate purity is non-negotiable**: every op runs on the substrate, NO host readout
  (`.item()`/`float(tensor)`) inside operations.
- **Multi-clone**: editable `sutra_compiler` install points at the sibling `Github\Sutra`; verify
  changes here via `PYTHONPATH=sdk/sutra-compiler`. CI uses this repo's compiler.
- **Version: 0.9.1** (Emma 2026-06-21) — `pyproject.toml` + `__init__.py` bumped to a fresh `0.9.1` (a clean
  patch past the `v0.9.0` milestone tag, rather than forcing the package to exactly match the old tag).
  Publish via a `sutra-dev-v0.9.1` tag (trusted-publisher → PyPI `sutra-dev`). **v1.0.0 is deferred** until
  codegen/stdlib go a stretch with NO source-breaking changes (Emma's call — too soon right after this
  week's arithmetic-semantics changes). No hard blocker; it's a source-compat-stability commitment.

## ⭐ FV PAPER RE-SPINE — narrow + probabilistic (Emma 2026-06-27)

**Why.** `paper/formal-verification/paper.md` drifted into an AI-generated grand framing —
title "…Verifying the Non-Learned Trusted Base of a **Neuro-Symbolic Substrate**", with
**bit-exact formal arithmetic** foregrounded as a headline result (§3.4 digit-array carry,
§4.3 bit-exact dispatch + a 3-paragraph GPU-determinism essay). That is **not the paper**.
Emma's intent: the paper is **narrow** — formally verify **Sutra-the-language as an execution
environment / instruction-set architecture running on a *probabilistic* substrate**. The
substrate is probabilistic; the verification should be probabilistic too. Bit-exact arithmetic
fights the substrate's nature (it's bought by routing through synthetic axes and *avoiding* the
probabilistic semantic codebook). Recurring project failure mode = **overambition**; keep this
one narrow.

**Trim pass DONE 2026-06-27** (this session, "trim now, re-spine next" — Emma): retitled away
from "neuro-symbolic substrate"; abstract cut 68→~30 lines; demoted bit-exactness to an
explicit "supporting precision measurement, not the paper's claim"; compressed §3.4 / the §4.3
GPU-determinism essay / the §4.4–4.5 audit war-stories; removed grandiosity ("the more
consequential direction… correctness at the level of the physics"); reframed §7 as "the
**probabilistic** substrate — the direction the work is moving" (no faked results). ~11.1k→9.3k
words. No paper/spec drift (kept every measured number).

**Z-transform loop-convergence criterion DONE 2026-06-27.** Built `fv_loop_convergence.py`
(`fv.analyze_loop_recurrence`) — analyses the loop's linear core `state ← R · state` as a
discrete-time LTI system via its Z-transform poles (eigenvalues of `R`), classifying
asymptotically-stable / marginally-stable / unstable off the unit circle. **Measured** on the
real emitted Haar bind rotation (dim 868): all 868 poles on the unit circle, spectral radius
1.00000000, `R` orthogonal ⟹ *marginally stable* — so termination is the halt gate's job, not
spectral decay (principled replacement for the ad-hoc "monotone halt" framing). `test_fv_loop_
convergence.py` 6/6 (classifier on known operators + substrate cross-check on the real rotation).
Wired into paper §3.3 + spec Pillar 3. (Env note: ran under pip-installed numpy+torch CPU here;
the substrate test needs a no-`embed` program to avoid the missing embed backend in this sandbox.)

**Continuous-time multi-state sampler convergence MEASURED 2026-06-27.** Built
`fv_sampler_convergence.py` (`fv.analyze_sampler_convergence`) — the continuous-time heat-bath
generator `Q` on the machine-checked AND-gadget energy `E4`; law obeys the master ODE
`dp/dt = Qᵀp` (the stochastic-ODE / Langevin distribution-level statement). **Measured** (β=1):
Gibbs π stationary (`‖πᵀQ‖∞=1.4e-17`), reversible (db-viol `4.2e-22`), real spectrum, full **8-state**
spectral gap `γ=0.0397`>0, and the master ODE's TV decay = `0.0397` = the gap to **ratio 1.0000**;
clamped mode = correct AND output ×4. `test_fv_sampler_convergence.py` 6/6. This fills the
multi-state + continuous-time piece `GibbsChain.lean`/§7 named as open (as a MEASUREMENT, marked
not-a-Lean-proof). Wired into paper §7/§9 + spec thrml section.

**RE-SPINE — remaining:**
1. **Machine-check the multi-state gap + continuous-SPACE Langevin (GATE LIFTED — Emma 2026-06-29:
   do the Lean unsupervised + confidently; Lean's `sorry`-free build IS the check; faking still barred).**
   **FOUNDATION DONE 2026-06-29** (`fv-lean/mathlib/GibbsMultiState.lean`, builds clean vs mathlib
   v4.30.0, `[propext, Classical.choice, Quot.sound]`, no `sorry`): general-finite-state
   reversibility ⟹ π-self-adjointness (`applyP_selfAdjoint`) + general-S stationarity
   (`applyP_stationary`) + `innerPi_comm` — the structural prerequisite that makes the multi-state
   gap real/well-defined, now for ANY finite S (not just 2-state). **SPECTRAL CAPSTONE DONE
   2026-06-30, CI-green** (`applyP_gap_contraction`, `Convergence.lean`, no `sorryAx`): scalar
   Dirichlet/Rayleigh gap ⇒ one-step L²(π) contraction `‖Pf‖²_π ≤ (1−γ)²‖f‖²_π` (numerical-radius =
   operator-norm, elementary — polarization + parallelogram + CS discriminant, NO finite-dim spectral
   theorem), feeding `geometric_convergence` ⇒ **gap ⇒ geometric decay fully closed in Lean**; measured
   `γ=0.0397` instantiates the scalar hypothesis. **Z-TRANSFORM UNIFICATION DONE 2026-06-30, CI-green**
   (`energy_gen_summable` + `energy_summable_of_contraction` + `loop_energy_gen_summable`,
   `Convergence.lean`, no `sorryAx`): the energy generating function `G(z)=Σₙ‖Pⁿf‖²_π zⁿ` has pole
   radius `1/r`, so **the Z-transform pole = the contraction rate `r`** — Gibbs (`r=(1−γ)²<1`, pole
   inside; `G(1)` finite, chain settles) and the deterministic loop (`r=1`, π-isometry `R`, pole ON the
   unit circle, marginal) are instances of ONE theorem (comparison with the geometric series, no
   spectral theorem). This is the "single spine" that answers the clawRxiv kitchen-sink con.
   **MEAN-ZERO COMPOSITION FIX + 2-STATE INSTANCE DONE 2026-06-30, CI-green** (`geometric_convergence_
   meanZero` + `iterP_piMean_zero` + `twoState_rayleigh_eq` + `twoState_geometric_decay`, no `sorryAx`):
   fixed a real gap (the capstone's contraction is mean-zero-only; `geometric_convergence` wanted all-h,
   false on the stationary direction) with the mean-zero iteration; and DISCHARGED the Rayleigh gap from
   matrix entries for a concrete reversible 2-state chain (`λ₂=1−P₀₁−P₁₀` computed, `‖Pⁿf‖²_π ≤ (λ₂²)ⁿ‖f‖²`,
   NO measured input) — the spine closing end-to-end on a concrete chain. **CONVERGENCE-TO-STATIONARITY
   LIMIT DONE 2026-06-30, CI-green** (`energy_summable_meanZero` + `meanZero_tendsto_zero` +
   `twoState_tendsto_zero`, no `sorryAx`): the deviation-energy `‖Pⁿf‖²_π → 0` (a genuine `Tendsto`
   limit, not just a rate bound), incl. the concrete 2-state chain reaching stationarity with no
   measured input. clawRxiv verdict progressed Strong Reject → Weak Reject after the Z-transform leg.
   **STILL OPEN:** the same
   discharge for the *8-state* kernel (a machine-checked `λ₂` bound on that larger operator; γ=0.0397
   still the measured input there); then continuous-space
   overdamped Langevin `dX=−∇U dt+√(2/β)dW` (the continuous-time master-ODE decay is the discrete
   `geometric_convergence`'s analogue — lower priority). **Spec for what's needed:
   `planning/findings/2026-06-29-lean-gap-audit.md`** (the L/S/M tiering + prioritized Lean TODO:
   multi-state spectral gap → continuous-time decay → continuous-space Langevin). Not-yet-built ⇒
   cite no numbers until measured/proved. **PREREQ:** the mathlib layer (`fv-lean/mathlib/`) is
   NOT cached locally — step 1 of that session is `cd fv-lean/mathlib && lake exe cache get`
   (~GB) before any spectral-theory formalization. Audit TODO #4 (heterogeneous composed-circuit
   instance, `half_adder_strict_min`) was DONE 2026-06-29 — mathlib-free, sound; only items 1-3
   (gap/ODE/Langevin) remain, all needing mathlib.

**Guardrails:** integrity rules bind — the SDE + Z-transform analyses are NOT built; cite only
measured numbers, build before claiming (no prose-only "results"). Keep it NARROW (per-contract,
non-learned trusted base, the ISA-on-probabilistic-substrate frame); do NOT re-grow "verify the
whole neuro-symbolic system". Each push to `paper/formal-verification/paper.md` triggers the
clawRxiv resubmit CI (`fv-paper-ci.yml`) — intended; reviews are signal, not verdicts.

---

## ACTIVE — barrel top to bottom

**Theme (Emma 2026-06-22/23): USABILITY.** Make Sutra easy for an outside person to install, run,
and learn. The backlog elsewhere is all substrate-correctness; none of it is usability. The
in-process-embedding change (drop the Ollama daemon) shipped 2026-06-22. Barrel these top to bottom;
delete each on completion + append to `DEVLOG.md` in the same commit.

_Batches 1–2 drained 2026-06-23 (in-process embeddings, first-run UX, package verify, semantic-FAQ +
tutorial 05, list-ops, `sutrac repl`; tutorial 01/04 fixes, stale-count sweep, onboarding polish).
History in `DEVLOG.md` / `git log`._

_Batch 3 (ALIAS + AFFORDANCE sweep) DONE 2026-06-23: `truth_value`/`complex_number`/`real_number` →
`make_*`; `basis_vector` → `embed` (builtin deleted, collect renamed); `unk` → `unknown`; `scalar` type
→ `number` (fully removed incl. the parser/static-method sites); `iff` → `xnor` (removed from BOTH lexer
AND parser tables). `embed`/`make_*`/`number`/`unknown`/`xnor` are the single canonical spellings. Other
logical-connective spellings stay (Emma). All verified (compiler 811, smoke PASS, demos 224). History in
DEVLOG + git log. CLAUDE.md § "Deprecate aliases aggressively" records the rules + carve-outs._

_Batch 4 (stale-reference cleanup from the post-alias audit) DONE 2026-06-23: stdlib comments
(`embed.su`/`vectors.su` block deleted/`axons.su`/`README`/`logic.su`), docs (`operators`/`capabilities`/
`logical-operations` — `iff` dropped/→`xnor`, `basis_vector` past-tense), codegen prose comments, and the
dead `basis_vector` branch in thrml `_basis_atoms` all cleaned. Verified: 62 tests pass, site builds.
A few trivial historical-prose mentions of "basis_vector"/"scalar" remain in internal codegen/egglog
comments (referencing the removed spelling as history) — not misleading, left as-is._

## Batch 5 — newcomer-usability audit (2026-06-23, post-alias)

Fresh readability/usability audit (onboarding + error messages + real-program reach). `iff` on the public
`docs/primitive-classes.md` page (a Batch-4 miss) was fixed inline.

_Batch 5 concrete items DRAINED 2026-06-24: the `snap` trap (M5 — SUT0151 validator warning + backend-
accurate codegen message + tutorial-03 future sidebar, all steering to `argmax_cosine`); the no-I/O
host-bridge concept page (M6 — `docs/host-bridge.md`, wired into tutorials 01/05 + index; a live-input
primitive FLAGGED as Emma's open call, not built); `dict<K,V>` discoverability (L11 — surface-syntax
section added to `docs/memory.md` + a keyed-collection link from `docs/list-operations.md`). History in
DEVLOG + git log. → Run the PINNED TAIL audit to refill._

> **H1 (unknown-type/function diagnostics) RECLASSIFIED 2026-06-24 → the deferred v0.2 name-resolution
> milestone, NOT a quick batch item.** `validator.py:21-29` EXPLICITLY defers name resolution to "v0.2+
> once we have a symbol table." A measured false-positive scan (`scratchpad/h1_recon.py`) confirms a naive
> diagnostic warns on EXISTING VALID code: `03_methods.su` (valid corpus) references undeclared `Animal`/
> `Cat` types; the arrow-fn examples call first-class function-valued LOCALS (`f`,`scale`) — both need the
> real symbol table + local-scope tracking, not an allowlist. (Also `float`/`function` are missing from
> `PRIMITIVE_TYPE_NAMES` — real gaps to fix WHEN the symbol table lands.) The newcomer gap is already
> mitigated at the doc level (Batch 5.1 tutorial-01 note: v0.1 doesn't do name resolution, on the roadmap).
> Building the v0.2 symbol table is Emma's call (language-direction; it tightens the deliberately-lenient
> validator). Finding: `planning/findings/2026-06-24-h1-name-resolution-is-deferred-v0.2.md`.

## Batch 6 — fresh readability/usability audit (2026-06-24, post-Batch-5)

Audit from an outsider trying to install, run, and read Sutra. Surfaced concrete gaps — barrel top
to bottom; delete each on completion + append to `DEVLOG.md` in the same commit.

_Done 2026-06-24 (history in DEVLOG): (docs accuracy) `docs/index.md` "string I/O" → string *operations* +
host-bridge pointer; (error messages) the CLI now catches `CodegenNotSupported` at the single
`_compile_to_python` choke point and prints a clean `file:line:col: codegen: <msg>` diagnostic (exit 1)
instead of an uncaught Python traceback — `--run`/`--emit` on `snap` verified, test_snap_diagnostic covers it._

_Done 2026-06-24 (Emma: "fix this"; history in DEVLOG): the `pip install` onboarding now actually runs a
program. ROOT FIX (semantics): a bare string-literal `main` return printed `104.0` ('h') because a String
is a `dim`-length tensor and `_decode_terminal_result` read the real axis (= the first codepoint) before
checking for a string — now it checks `is_string` first and decodes via `string_to_python`, so
`function string main() { return "hello world"; }` prints `hello world` (number returns still decode to
the real axis; test_terminal_string_decode covers both). With that, the landing page leads with a verified
pip-only first run (`pip install` → write a one-line `hello.su` → `sutrac --run`), and the docs are honest
that the `examples/…` programs ship in the SOURCE repo, not the wheel (tutorials 01/05 + index note: clone
or save the shown source). Did NOT ship examples in the wheel — unnecessary once inline programs run and the
docs are accurate, and it would need an awkward force-include/relocate (examples sit outside the package dir)._

_Done 2026-06-24 (history in DEVLOG): generalised the SUT0151 validator warning beyond `snap` to its
sibling unimplemented substrate builtins `make_rotation` / `compile_prototypes` / `geometric_loop` — they
warn early too, with an honest "no implemented substitute yet" hint (snap keeps the argmax_cosine steer)._

## Batch 7 — fresh usability audit (2026-06-25, error-messages + newcomer-mistakes pass)

Probed the diagnostics a newcomer trips on their first hour (`print`, wrong types, no `main`). Barrel top
to bottom; delete each on completion + append to `DEVLOG.md` in the same commit.

_Done 2026-06-25 (history in DEVLOG): `print`/host-builtin leak. `print("hi")` lowered to a raw Python
`print('hi')` and actually printed, breaking the no-I/O model + substrate purity. Validator now rejects a
bare call to a host-Python builtin denylist (`print`/`input`/`open`/`eval`/`exec`/`compile`/`__import__`)
with SUT0152 — `print`/`input` steer to `main()`'s return + the host bridge — unless a same-named function
is declared (shadowing). Verified: print/eval rejected, user-defined `print` still validates, corpus +
examples unaffected (no `.su` calls these); test_host_leak_builtins covers it._

_Done 2026-06-25 (history in DEVLOG): two `--run` error-UX fixes in `__main__._run_execute`. (a) Runtime
exceptions in the generated module (e.g. `int x = "hello"` → TypeError) now print a clean
`<file>: runtime error: <Type>: <msg>` to stderr and exit 1 instead of an uncaught Python traceback
(KeyboardInterrupt/SystemExit still propagate). (b) A file with no `main()` prints
`<file>: no main() found — nothing to run` instead of exiting silently. test_run_error_diagnostics covers both._

_Done 2026-06-25 (history in DEVLOG): model-load stdout noise. `SentenceTransformer(...)` printed framework
chatter (`<All keys matched successfully>`) to stdout, polluting `main()`'s output. `embedding._get_st_model`
now wraps the load in `redirect_stdout(sys.stderr)`. Verified: `sutrac --run` of an `embed`-using program
now emits only the program's output on stdout; the chatter is on stderr (where our load notice already is).
→ Batch 7 drained; run the PINNED TAIL audit to refill next._

---

## ⭐ PINNED TAIL — readability + usability audit → REFILL (self-perpetuating; Emma 2026-06-23)

**This item never gets deleted — it regrows the queue.** When items 1..N above are all done, run a fresh
**readability + usability audit** of Sutra from the perspective of an outsider trying to read, install,
run, and learn it, and **atomise the findings into 3–6 new concrete items at the TOP of this ACTIVE
list**, then keep barrelling. Repeat every time the concrete items drain. Audit surfaces, rotating:
- **Onboarding:** can a stranger `pip install` and run their first program in <5 min? Where do they get stuck?
- **Docs readability:** are the tutorials/concept pages clear, in order, free of repo-internal jargon and
  dead links? Does the website read well to a newcomer? (Website discipline: keep `docs/` free of
  `queue.md`/`todo.md`/`planning/...` references.)
- **Error messages:** are `SUT####` diagnostics + runtime errors actionable, pointing at the fix?
- **Language readability:** is `.su` source itself readable? Are the example programs idiomatic and
  well-commented? Is the stdlib surface discoverable?
- **Real-program reach:** what can't a newcomer build yet that they'd expect to? (stdlib gaps, missing
  ergonomics) — name precisely; don't fake reach.
- **Aliases + affordances (Emma 2026-06-23):** internal redundancy — two Sutra-native names for one op,
  legacy entry points, escape hatches that mislead the next agent. Deprecate aggressively toward one
  canonical spelling (CLAUDE.md § "Deprecate aliases aggressively"); exclude the foreign-ecosystem carve-out.

**THE GOAL IS V1, AND V1 IS EMMA'S MANUAL CALL — NOT THE LOOP'S.** Keep making Sutra more readable +
usable; do NOT bump the version to 1.0.0, do NOT declare "V1-ready," do NOT tag a v1 release. Emma
approves the V1 transition manually. The loop's job is to keep closing usability/readability gaps until
she says it's there. (Consistent with the v1.0.0-deferred note in Context above.)

## Session bracket — autonomous loop (self-timed)

- Run as the self-timed `ScheduleWakeup` loop (NOT the three-cron playbook). Each wake: SYNC
  (`git fetch` + ff/rebase) → WORK the top `queue.md` item → HARD RAILS (never fake/weaken a test; RUN +
  measure before claiming green; name hard things plainly) → COMMIT (delete done item + DEVLOG entry,
  same commit) + push → schedule the next wake. When items 1..N drain, run the PINNED TAIL audit to
  refill, then continue — the loop is self-sustaining toward V1 (Emma's manual gate). Report via commits
  + DEVLOG, not questions.

---

## PARKED — real but gated (cannot implement on this clone)

_2026-06-21 audit: these are real, not phantom-PR. The async/await Stage-1 item was RETIRED (its
"only-tail-position-works / model-blocked" premise is now false — mid-function await shipped 2026-06-20).
The rest are genuinely gated on resources this clone lacks._

- **await Stage-2 — full gated `while_loop` with a LIVE external producer — desktop-I/O-gated.**
  The await CORE shipped 2026-06-20 (mid-function lowering + Promises/A+ rejection propagation, substrate-
  pure; `test_await_midfunction.py` green). What remains is the poll loop spinning on a promise an EXTERNAL
  producer resolves over time — i.e. the I/O orchestrator (**Sutra for Windows**, the desktop-I/O layer
  vendored in-tree at `external/Yantra/`) writing the resolved value into the awaited axon. `await_value`
  stays the β-reduced no-producer form until there's a real producer to test against; awaits buried in
  nested control-flow still fall through to the codegen rejection. Resume when wiring the desktop-I/O promise
  producer. (The await *model* — Emma 2026-05-17's implicit-axon-input + arrival-flag vs `promises.md`'s
  gated-while-loop — is still unsettled in the spec, but only governs this unbuilt producer path, not the
  shipped core. The old "async/await Stage-1 desugar" item was retired here: mid-function await shipped, so
  its "only-tail-position-works" premise is false.)
- **§1C steps 3 & 4 — per-process CUDA isolation + CUDA-IPC codebook sharing.** Need a Linux/CUDA box;
  unverifiable on this Windows clone (no CUDA IPC). The portable core is done + validated. Resume when a
  CUDA environment is available; until then writing the code would ship unverified substrate work.
- **§1C ProcessPoolRuntime CUDA path** (`force_cpu=False`, per-process CUDA contexts) — part of the above.
- **§2 WASM source frontend.** Sibling-owned (its own work-loop / `:33` cron) and largely
  clang/uv/wat2wasm-blocked here. Coordinate via CI; do not collide with the subtree agent. Decompose
  from `todo.md` §"Phase 3 — WASM" only if it lands on this clone with a toolchain.

---

## Pointers

- Substrate-leak catalogue: `Audit.md`. Longer-horizon backlog: `todo.md`. Findings: `planning/findings/`.
  Open design questions: `planning/open-questions/`. Devlog: `DEVLOG.md`.
- Transpiler edge cases (low-value, leave-on-WASM-fallback): `planning/wasm-fallback-edge-cases.md`.
- Corpus: `github.com/EmmaLeonhart/sutra-w2c-corpus` (submodule `corpus/`) + HF mirror.
- Sutra for Windows (the desktop-I/O layer, formerly called "Yantra"): vendored in-tree at `external/Yantra/`
  (directory keeps the legacy name for now).

## Session bracket

- The autonomous loop is the self-timed `ScheduleWakeup` form (not the old three-cron playbook).
- Own the queue, barrel through, report via commits + DEVLOG — no questions.
