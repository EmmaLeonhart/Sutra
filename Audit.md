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
   `examples/_smoke_test.py` PASS (11/11). The numpy/host
   `codegen.py` backend is deprecated and out of scope.

2. **`defuzzify_trit` / `sign_polarize`** —
   `codegen_pytorch.py:1989-2002`:
   `x = float(v[…AXIS_TRUTH].item())`, `b = float(beta)`,
   `for _ in range(int(iters)): …`, `out[…] = float(x)`. The
   β-sharpening polarizer runs its whole iteration as a host scalar
   loop. `defuzzy` (the cosine-eq loop) is already pure Sutra in
   `stdlib/logic.su`; this trit variant is not. Fix: tensor-native
   polynomial polarization, unrolled like `defuzzy`.

3. **Promise await loop** — `codegen_pytorch.py:808`:
   `for _ in range(100):` — `Promise.await_value` spins a host
   Python loop with a 100-iteration cap instead of the substrate
   `while_loop` two-channel halt vector the spec describes
   (`planning/sutra-spec/promises.md`). Known (queue.md item 1
   phase 6) — recorded here so it is counted as a leak, not a
   "shipped" feature.

4. **Generic loop runtime** — `codegen_pytorch.py:2213`:
   `for _t in range(max_iters):` — the iteration mechanism that
   `loop`/`while` lower to is a host `for`. Spec says loops are
   `state ← R·state` on the substrate (control-flow.md). The host
   loop is the loop-runtime leak surface; bound it to the
   eigenrotation primitive once (1) lands.

5. **String ops as host codepoint loops** —
   `codegen_pytorch.py:1753-1774` (length/index: `for k in
   range(…)`, `if v[…].item() != 0.0`, `return int(…item())`),
   `1952-1975` (concat: `for k in range(la)` / `range(lb)`,
   `chr(int(…item()))`). Strings are spec'd as synthetic-axis
   codepoint arrays (`strings.md`); the ops walk them on the host.
   Vectorize over the axis block.

6. **`complex_div` NaN/zero guard** — `codegen_pytorch.py:1907`:
   `if r != r or r == 0.0:` — host NaN+zero branch. The 2026-05-13
   pass-2 finding called complex_div "substrate-pure"; this host
   `if` says otherwise. Replace with a tensor-masked closed form
   (the eps-guarded divide pattern `x/(‖·‖+eps)` already used in
   `normalize`).

7. **`select` / softmax-gate zero-norm guard** —
   `codegen_pytorch.py:2288`: `if float(q_norm) == 0:`. Host
   branch inside `select`/`argmax_cosine`. Use the same
   eps-guarded tensor form.

8. **Slot store / array-from-literal** —
   `codegen_pytorch.py:996` (`s = int(slot_idx) % n_planes` — host
   int modulo), `1005` (`new[i] = float(scalar)`), `1030-1033`
   (`arr[…] = float(len/ v)` + host `for`). Literal lift is a
   defensible boundary, but the host `%`/`for` here are doing
   substrate-shaped work on the host.

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
- **Source-level beta reduction for `math.su`/`modulus.su`** — the
  ideal form is Sutra method *bodies* so the substitution is the
  source itself. Blocked: the stdlib inliner does not resolve
  intra-`Math` member calls inside a class-bodied static method
  body (`NameError: name 'Math' is not defined` at codegen). This
  is the **top item**: fixing the inliner makes the `.su` files the
  literal executable beta reduction, which is the whole point of
  the language's philosophy. Until then the methods are `intrinsic`
  routing to the (now substrate-pure) `_VSA.*`.
- **`Math.round` ties-to-even vs JS half-up** — semantic, not a
  purity issue; logged for completeness.
- **Wire `experiments/substrate_leak_sweep.py` into the test
  suite** — so the next binary-operator leak in a user `.su`
  program is caught at PR time, not by a user hitting it.
- **Dangling `examples/todo.md` references** in dated findings
  (`planning/findings/2026-04-15-llm-substrate-role-name-collision.md`,
  `2026-05-10-spec-implementation-audit.md`, `planning/sutra-
  spec/README.md`) — the file was merged into root `todo.md`
  2026-05-15. Findings are point-in-time records; the spec README
  ref is the only one worth repointing.
