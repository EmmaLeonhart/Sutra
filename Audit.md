# Substrate-leak audit

> **READ THIS BEFORE CLAIMING ANY OPERATION IS SUBSTRATE-PURE.**
>
> Sutra's #1 safety rule (CLAUDE.md intro): every operation runs on
> the substrate; no host wrappers around substrate ops; no prose
> asserting purity the code does not have. This file is the running
> catalogue of where the runtime still leaks the substrate, triaged
> by severity, with `file:line` anchors. `todo.md` points at the top
> of this file. Work the **REAL LEAK** section first.

**Opened:** 2026-05-15, after the transcendental/modulus substrate
leak (a host `float()`/`if`/`raise` sandwich that had been *labelled*
"substrate-pure" in code comments and a finding). Fixed in commit
`21a9ff77` — see `planning/findings/2026-05-15-transcendental-
substrate-leak-fixed.md`. That fix is the model: one `_st()`
host→substrate boundary, every step a tensor op, 0-d tensor return,
no host `float()`/`if`/`raise`/`for`-over-scalars, out-of-range
saturates instead of raising.

Method of this audit: `grep` of the emitted runtime prelude in
`sdk/sutra-compiler/sutra_compiler/codegen_pytorch.py` for the leak
signatures (`float(...)`, `.item()`, host `if` on a scalar, host
`for ... range`, `%`/`_math.` on host scalars). Line numbers are
codegen emission sites (the `self._emit("…")` line), not the
generated module. `experiments/substrate_leak_sweep.py` is the
complementary CI-gate that sweeps *user .su programs'* emitted
Python; wire it into the test suite so new binary-operator leaks
get caught at PR time (queue.md item 4 carried this open).

The numpy/host-CPU `codegen.py` backend is deprecated and being
retired; this audit targets the canonical `codegen_pytorch.py`.

## Current status — 2026-05-28

**All REAL LEAK entries (#1–#10) are FIXED.** Every site catalogued in
the REAL LEAK section has either been resolved (with the fixing commit
hash inline) or reclassified to a defensible boundary (#4 generic loop
runtime, recorded as NOT A LEAK after rereading the loop body). #9
(`eq`/`eq_synthetic`) was added later 2026-05-28 after the defuzz β
grad-broken investigation surfaced it; same shape as #2, separate site.
#10 (`_select_softmax` scores `as_tensor` autograd-detachment) was added
later 2026-05-28 after the select-T training BLOCKED first iteration of
the 3-seed K=5 run surfaced it; same shape as #9, in the same emitted-
helper region. The `experiments/substrate_leak_sweep.py` CI-gate is
wired in (`sdk/sutra-compiler/tests/test_substrate_leak_sweep.py`); it
sweeps 67 user `.su` programs and asserts 0 operator leaks per run.

**BORDERLINE entries are documented boundaries**, not leaks — each is
the host↔substrate entry/exit edge per CLAUDE.md's monitoring/literal-
lift carve-outs. They are kept here so a future session does not
re-flag them as leaks without reading the rationale.

**Cross-cutting follow-on still open:** `atan2` in `rotation_mod` is a
tensor op but libm-shaped; an eigenrotation/lookup decomposition is the
natural extension of the 2026-05-15 transcendental fix. Low priority —
not a current substrate leak (it dispatches as a tensor op), just a
candidate for a more-substrate-native shape.

**Composes with the 2026-05-28 measurement-required checks**
(CLAUDE.md "Subtler substrate breaches"; FV paper §4.4): dispatch-level
cleanliness (this file's grep) is *necessary, not sufficient*. The
dimension audit, state-locus audit, and signal-separation audit are
the sufficient set. Future entries adding to this file should reference
which of the four (dispatch + the three measurement audits) a given
breach falls under.

---

## REAL LEAK — host scalar arithmetic / control flow inside a runtime op

These are operations whose *definition* extracts a host scalar,
branches/loops on it in Python, or calls host libm, then packs the
result back. Fix shape: take tensors, stay tensors, return tensors;
replace host `if`/`for` with tensor masking / vectorized reductions;
saturate instead of raise.

1. **`rotate_slot` / Givens-rotation primitive** — ✅ FIXED
   2026-05-15 (autonomous queue run). Was
   `c, s = _math.cos(float(angle)), _math.sin(float(angle))` +
   `xi, xj = float(state[i]), float(state[j])` — host libm trig +
   host scalar extraction inside the rotation `loop(cond)` lowers
   to (the worst leak: the eigenrotation is the substrate's
   defining op). Now: `c = self.cos(angle)` / `s = self.sin(angle)`
   (verified substrate-pure 0-d tensors), `xi/xj = state[i]/state[j]`
   (0-d tensor element views, no `float()`), plane update is tensor
   arithmetic + scatter. `i, j` are structural layout indices (like
   `AXIS_REAL`), not data. Verified: 0 leak signatures in emitted
   code; loop runtime suites (`test_branchless_loop`,
   `test_loop_function_decl`) 33 passed/20 subtests;
   `examples/_smoke_test.py` PASS (10/10). The numpy/host
   `codegen.py` backend is deprecated and out of scope.

2. **`defuzzify_trit` / `sign_polarize`** — ✅ FIXED 2026-05-15
   (autonomous queue run). Was `x = float(v[…AXIS_TRUTH].item())`,
   `b = float(beta)`, `for _ in range(int(iters))`, `_math.exp`×3,
   `out[…] = float(x)`. Now: truth axis read as a 0-d tensor view
   `x = v[idx]` (no `.item()`/`float()`); `b = self._st(beta)`; the
   spec-fixed 10-step β-sharpening is unrolled at codegen time into
   a straight-line tensor-op chain (like `defuzzy`'s `loop(10)` —
   no runtime host `for`), each step three substrate-pure
   `self.exp` readouts; scatter back `out[idx] = x` (0-d tensor,
   no `float()`). `i`/`idx` are structural layout indices, not
   data. Verified: 0 code leak signatures; substrate output
   matches the documented host algorithm to ≤1.4e-4 across 9
   inputs (the residual is substrate exp-table precision vs host
   libm — the real cost; polarization decisions identical:
   -0.6→-1, -0.4→0, +0.6→+1); `examples/_smoke_test.py` PASS;
   `test_corpus`+`test_transcendentals` 6 passed/103 subtests.

3. **Promise await loop** — ✅ FIXED 2026-05-17 (both backends).
   `Promise.await_value` was a host bounded poll loop with a host
   branch on the pending predicate (the forbidden host
   control-flow-on-a-value pattern; every `await x` lowers to
   `Promise.await_value(x)`, so it was on the live path).
   **Resolution = the exact algebraic reduction of the spec-2
   lowering, not a workaround:** `planning/sutra-spec/promises.md`
   Stage 2 makes a `Promise<T>` a `while_loop` with a two-channel
   halt fed by an input axon. In the current runtime the halt
   channels are set only by `resolve`/`reject` at construction
   (synchronous); no external axon producer mutates `p` mid-spin
   (no Yantra I/O wired). So `while_loop spin(isPending, slot p){
   pass p; }` has an empty body yielding `p` unchanged each tick →
   it terminates with `p` at its initial value → its terminal read
   is exactly `value(p)` for every input. `await_value(p)` is now
   `return self.value(p)` (pure tensor ops: clone + zero two axes;
   no host scalar, no branch). Verified: 0 leak signatures in the
   emitted runtime both backends; `async_promise_runtime.su`
   end-to-end semantics preserved (`main()` = 3.0 both backends);
   gate 227 passed/83 subtests + smoke. Finding:
   `planning/findings/2026-05-17-await-substrate-pure.md`. When
   Yantra wires an external axon producer the gate becomes a real
   substrate while_loop on the slot-arrival flag (promises.md
   Stage 2 / axon-io.md) — a future extension, deliberately NOT a
   no-op loop added now to mimic the shape.

   **Separate, broader observation (NOT #3, recorded not silently
   expanded):** `isPending`/`isFulfilled`/`isRejected` still read
   the promise axes via host `float()` and return host scalars.
   They are surface `Promise.is*` accessors; after this fix none
   is on the `await` runtime-op path. Whether a `Promise.isPending`
   used inside a Sutra expression should be substrate-pure is its
   own question (predicate-accessor boundary), tracked here as an
   observation, not folded into #3.

4. **Generic loop runtime — NOT A LEAK (reclassified 2026-05-17,
   Emma).** `codegen_pytorch.py` `_TorchVSA.loop` /
   `for _t in range(max_iters):`. Earlier catalogued as a "host
   `for` leak"; that was wrong and is corrected here. Reading the
   code: it is a **fixed-T unroll of the eigenrotation** —
   `max_iters` is a structural parameter (default 50), every step
   is `self._step` (= `R @ state`, normalize, `dot`, sigmoid
   soft-halt, branchless gate), `halted`/`iters_active` stay
   tensors, and there is **no `.item()`/`float()`, no `if`/`break`
   on data** anywhere in the loop. Nothing branches on a host
   scalar. That is exactly the spec's substrate loop
   (`state ← R·state`, T-step unroll, soft halt; control-flow.md) —
   the same "structural index, not data" / "T-step unroll" category
   the accepted #1 and #2 fixes established. Whether the fixed-T
   unroll is spelled as a runtime `range()` or hoisted to a
   straight-line codegen unroll is a **compile-time optimization /
   style choice, not a substrate-purity question**. The mistake was
   carrying this label without reading the loop body. No fix is
   owed; "fixing" it would risk regressing the working
   autograd-friendly differentiable loop. (Original mis-citation
   referenced line 2213; the construct is `_TorchVSA.loop`.)

5. **String ops as host codepoint loops** — ✅ FIXED 2026-05-16
   (commit `0e363b96`). Was `string_length`/`string_char_at`/
   `string_concat` with host `for k in range`, `.item()`, `int()`,
   host `if`/`raise`. Now substrate-pure via the VSA/permutation
   approach Emma specified: a cached constant `_str_axes()` index
   tensor (compile-time, same class as the lookup tables);
   `string_length` = `(arange(1..n) * (cps!=0)).max()` over the
   gathered codepoint block; `string_char_at` = gather + OOB mask
   (saturate, no host branch); `string_concat` = shift b right by
   `len(a)` via a permuted gather index + add (overflow falls off
   the mask = saturate, no raise). `make_string` raise→truncate;
   its enumerate is the documented host-literal→substrate ENTRY
   boundary (make_real/_st analogue). `string_to_python` is the
   substrate→host MONITORING/decode boundary (CLAUDE.md-allowed);
   `is_string` is the host dispatch predicate (JS-interop carve-
   out) — neither is an op-internal leak. Verified: ground-truth
   correct + substrate-tensor returns; corpus+codegen_pytorch+
   transcendentals+inliner 39 passed/103 subtests; TS string
   fixtures 2 passed; `examples/_smoke_test.py` PASS 10/10 (real
   string decode/retrieval). Zero regression.

6. **`complex_div` NaN/zero guard** — ✅ ALREADY RESOLVED (stale
   citation). Current `complex_div` (codegen_pytorch.py ~1637-1655)
   is the pass-2 closed form `num / denom_vec` with NO host `if` —
   verified this run: 0 leak signatures in the method code, 3
   ground-truth division cases correct including the formerly-`inf`
   `(5+5i)/(2+0i) = 2.5+2.5i`. The cited line 1907 now points at
   `js_truthy` (a string/NaN/zero dispatch), which is JS-interop
   coercion under the CLAUDE.md carve-out — see the BORDERLINE
   §"JS-interop equality/promotion" entry, not a `complex_div`
   leak. No action needed; line ref was pre-rewrite.

7. **`select` / softmax-gate zero-norm guard** — ✅ FIXED
   2026-05-15 (autonomous queue run). Was `q_norm =
   _torch.linalg.norm(q); if float(q_norm) == 0: return
   candidates[0]` in `_argmax_cosine` — a data-dependent host
   branch. Now eps-guarded the same way the sibling `row_norms`
   already is: `safe_qn = _torch.where(q_norm > 0, q_norm,
   ones_like)`, `scores = (M@q)/(safe_rn*safe_qn)`. Zero query →
   zero score vector → argmax picks index 0 → `candidates[0]`,
   exactly the old behaviour, no host branch. Verified: 0 host
   `if float(q_norm)` in emitted code; `examples/_smoke_test.py`
   PASS (10/10, exercises real argmax_cosine retrieval);
   `test_corpus` 3 passed/83 subtests. (The terminal
   `int(argmax(...).item())` is the program-terminal commit edge —
   BORDERLINE/output boundary, intentionally left.)

8. **Slot store / array-from-literal** — ✅ slot_store FIXED
   2026-05-15; the other two cited sites are legitimate boundaries.
   - `slot_store` `new[i] = float(scalar)` was a substrate→host
     extraction (when `scalar` is a 0-d tensor). Now
     `new[i] = self._st(scalar)` / `new[j] = self._st(0.0)` — the
     `_st()` boundary (no-op view on an already-tensor value; the
     literal entry boundary for a host literal). Verified: 0 code
     leak signatures; loop runtime suites 30 passed;
     `examples/_smoke_test.py` PASS.
   - `_slot_plane` `s = int(slot_idx) % n_planes`: `slot_idx` is a
     **structural** slot index (which slot the compiler assigned),
     like `semantic_dim + AXIS_REAL` — not a runtime data value.
     Host int arithmetic on a layout index is legitimate (same
     class as the LEGITIMATE compile-time-constant axis indices).
     The `if n_planes <= 0: raise` is a layout-config invariant
     (the synthetic subspace is too small to hold any slot), not
     data-dependent control flow. No action.
   - `array_from_literal` (`arr[0]=float(len(values))`,
     `arr[1+i]=float(v)`): literal lift — the host→substrate entry
     boundary for a source-level `[1,2,3]` array literal, the
     `make_real`/`_st` analogue. Defensible boundary per this
     section's own BORDERLINE rule. No action.

   (original citation continued:)
   `codegen_pytorch.py:996` (`s = int(slot_idx) % n_planes` — host
   int modulo), `1005` (`new[i] = float(scalar)`), `1030-1033`
   (`arr[…] = float(len/ v)` + host `for`). Literal lift is a
   defensible boundary, but the host `%`/`for` here are doing
   substrate-shaped work on the host.

9. **`eq` / `eq_synthetic` — `make_truth(float(cos.item()))`** —
   ✅ FIXED 2026-05-28 in commit `e2b8ee7a` (defuzz β grad
   investigation; SutraBarrel session). Was
   `return self.make_truth(float(cos.item()))` (and
   `make_truth(float(truth.item()))` in `eq_synthetic`) at
   `codegen_pytorch.py:2414` / `:2429`. `cos` / `truth` is a 0-d
   tensor with a `grad_fn`; `.item()` extracts a Python scalar
   (severing the autograd chain) and `float(...)` rewraps it,
   then `make_truth` builds a fresh vector with the scalar
   written into the truth axis. The numerical value is identical
   to a direct scatter, but the gradient connection is lost
   AND it's a host scalar extraction inside the op (the exact
   pattern fixed for `defuzzify_trit` in #2). Now: scatter the
   0-d tensor directly — `out = _torch.zeros(self.dim, …); out[
   self.semantic_dim + self.AXIS_TRUTH] = cos; return out`
   (preserves grad via `index_put_`; substrate-pure; semantic
   identity with the previous form Δ=0.00e+00). Verified:
   `defuzz_gain_adjustment.py --smoke` PASS (Δ=0); direct
   autograd test (`gain.grad is not None: True`,
   `out.requires_grad: True`); compiler suite 402 passed / 7
   skipped / 116 subtests / 0 failed; substrate-leak-sweep
   `tests/test_substrate_leak_sweep.py` 1 passed in 1288s
   (67 user .su, 0 operator leaks). Surfaced by the defuzz β
   training BLOCKED finding (`c6a8470d`); root-caused +
   fixed in the follow-up finding
   `planning/findings/2026-05-28-defuzz-gain-grad-fixed-eq-
   substrate-leak.md`. Survived the broader audit because the
   substrate-leak-sweep gate greps user .su programs' emitted
   Python — it does NOT grep the runtime-prelude `_TorchVSA`
   class itself, where this leak lived. Follow-on (separate
   tick): extend the sweep to cover the runtime prelude.

10. **`_select_softmax` scores `as_tensor` autograd-detachment** —
    ✅ FIXED 2026-05-28 in the SutraBarrel work-loop tick that shipped
    `experiments/select_temperature_adjustment.py` (task #21 / constrain-
    train target 4). Was
    `s = _torch.as_tensor(scores, dtype=_DTYPE, device=_DEVICE)` at
    `codegen_pytorch.py:67`. When `scores` is a Python list of 0-d
    grad-tracked tensors (the typical shape: `[similarity(x, p_0)/T,
    similarity(x, p_1)/T, ...]` with `T` a trainable param),
    `_torch.as_tensor(list_of_grad_tensors)` silently detaches by
    forcing each element through scalar conversion (PyTorch emits
    the warning `Converting a tensor with requires_grad=True to a
    scalar may lead to unexpected behavior`). The downstream softmax
    is mathematically correct but disconnected from the autograd
    graph — `.backward()` raises `RuntimeError: element 0 of tensors
    does not require grad`. Now: when scores carries tensors,
    `_torch.stack([sc.to(dtype=_DTYPE, device=_DEVICE) for sc in
    scores])` (preserves grad via `StackBackward0`); raw-number
    scores still go through `_torch.as_tensor`. Verified: select-T
    smoke (`experiments/select_temperature_smoke.py`) monotonic
    across T ∈ {0.01..100}; select-T training (`experiments/
    select_temperature_adjustment.py`) K=3 per-class=3 epochs=10
    smoke trains T*=0.0185 from baseline 1.0, baseline margin
    +0.0039 → trained +0.2796 (71.6× ratio), round-trip max|Δ|
    = 2.50e-06. Same shape as #9 (host scalar extraction inside a
    runtime op; semantically identical to the substrate-pure form
    but autograd-broken). Surfaced by the select-T training
    BLOCKED first iteration of the 3-seed K=5 run, root-caused by
    a 2-line autograd check + minimal fix. Now also covered by
    the runtime-prelude scan extension (`c270acc0`).

## BORDERLINE — entry/exit boundary or commit, justify-or-fix

Defensible as a host↔substrate boundary, but each needs an explicit
decision (and a comment) rather than being silently host:

- **`make_real`/`make_complex`/`make_truth`/`make_char`** —
  `1518,1525-1526,1667,1735,1661,2025,2125`: write a host literal
  into an axis slot. This is the literal→substrate entry boundary
  (the `_st()` analogue). Decide: should they also accept an
  already-substrate tensor without round-tripping through `float`?
- **`similarity`/`dot` returning `float`** — `1109,1136`:
  `return float(_torch.dot(…))`. `similarity` is a spec operation
  (operations.md) used *inside* `argmax_cosine`. Returning a host
  float is fine if it is the final monitored read; it is a leak if
  another substrate op consumes it. Audit call sites.
- **`argmax_cosine`/`select` returning a host index** —
  `2294-2296,2327-2329`: `float('-inf')` sentinel +
  `int(argmax(...).item())`. This is the cleanup/commit edge (the
  program's terminal discrete choice) — legitimately a boundary
  per the output-semantics open question, but document it as the
  *intended* commit, not an accident.
- **Promise state inspectors** — `752,758,767-768`:
  `isFulfilled`/`isRejected`/`isPending` return host bools. Fine
  as monitoring; a leak if the await machinery branches on them in
  Python (it does — see REAL LEAK #3).
- **JS-interop equality/promotion** — `1801-1802,1830,1844,1866-
  1872,1885,2086,2101`: `.item()` + `float(...).is_integer()` host
  checks in `js_strict_eq`/loose-eq/number-string promotion. This
  is intentional-compatibility code (CLAUDE.md carve-out) absorbing
  JS's coercion rules; still, the truth-axis writes should be
  tensor ops even if the type dispatch is host.

## LEGITIMATE — not leaks (recorded so they are not re-flagged)

- **Compile-time constants**: `296-297` `self.PI/TAU = float(_math.pi)`
  — built once at init, not on the runtime path.
- **Monitoring/debugging accessors** (CLAUDE.md explicitly allows
  these — they don't sit inside another op's definition):
  `component` `1467`, `semantic` `1481`, slot read `1495`, `real`
  `1502`, `imag` `1507`, `truth` `1512`, standalone `norm` `1436`.
- **Embedding disk-cache / Ollama bootstrap**: host I/O at the
  compile/boot boundary, never on the op hot path.

---

## Cross-cutting follow-ons (named in the 2026-05-15 fix, tracked here)

- **`atan2` in `rotation_mod`** — still `torch.atan2` (a tensor op,
  but libm-shaped). Its own eigenrotation/lookup decomposition is
  the natural follow-on to the transcendental fix.
- **Source-level beta reduction for `math.su`/`modulus.su`** —
  RESOLVED 2026-05-19. The inliner already handles namespaced
  `Math.foo(...)` calls AND intra-`Math` sibling calls; the
  "blocked on inliner" comments were stale. Literate beta-reduction
  bodies in math.su (pow / sqrt / tan / sinh / cosh / tanh / cexp)
  ARE the executable source — verified end-to-end:
  `Math.pow(2,3) ≈ 8.0` via `exp(y*log(x))`. `mod` promoted from
  intrinsic to literate body `{ return rotation_mod(x, m); }`
  (verified `Math.mod(-0.1, 1) = 0.9`). The remaining intrinsic
  leaves — realExp / imaginaryExp / exp / log / cos / sin / ccos /
  rotation_mod / fmod / sawtooth_mod — stay intrinsic because each
  is a single substrate primitive (lookup or eigenrotation), not a
  substitution onto siblings.
- **`Math.round` ties-to-even vs JS half-up** — semantic, not a
  purity issue; logged for completeness.
- **Wire `experiments/substrate_leak_sweep.py` into the test
  suite** — ✅ DONE 2026-05-15.
  `sdk/sutra-compiler/tests/test_substrate_leak_sweep.py` imports
  the sweep and asserts rc==0; observed green (`1 passed in
  1738.41s` — 67 programs compiled, 0 operator leaks). Caveat:
  ~29 min runtime → make it slow/nightly or compile-once-reuse
  for per-PR use (speed refinement, not correctness; the gate is
  real and clean today).
- **Dangling `examples/todo.md` references — RESOLVED 2026-05-19**
  (commit `4f604520`). The `planning/sutra-spec/README.md` pointer
  was repointed to root `todo.md` with a historical note ("merged
  from the old `examples/todo.md` 2026-05-15"). The dated-findings
  references in `planning/findings/2026-04-15-llm-substrate-role-
  name-collision.md` and `2026-05-10-spec-implementation-audit.md`
  intentionally remain as point-in-time records of what was true at
  the time the finding was written, per the cross-cutting framing
  above. Kept here as resolution evidence; no further action needed.
