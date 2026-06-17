# Phase 5 — WASM `call` + a call-frame stack on the substrate: scoping (step 5)

**Date:** 2026-06-17
**Status:** scoping / spec. The final step of the real-WASM-bytecode core
(`experiments/iso5_substrate_dispatch/wasm_core.su`), and the enabler for queue Phase 5.5-B
(tree recursion → WASM). Steps 1–4 (arithmetic, locals, comparisons, structured control, a real
factorial byte-for-byte) are done. **No JVM template exists** — the JVM core ran single methods and
never did calls — so unlike steps 1–4 this is genuinely new machinery. No code yet; this decomposes
it before building, as the JVM/WASM scoping docs did.

## The goal

A recursive `fib(n) = fib(n-1) + fib(n-2)` lowers to WASM and runs on the substrate machine, with
its **call stack living in RAM** (the DNC memory), not a host stack — proving the Phase-5.5-B claim
("multiple/tree recursion → represent as WebAssembly"). Opcode: `call`(0x10, +unsigned LEB128 func
index). WASM `call_indirect` is out of scope for the minimal core.

## Why this is a machine REDESIGN (not an additive opcode)

Steps 1–4 assumed a SINGLE frame: the operand stack at a FIXED base (RAM 100) and locals at FIXED
cells (RAM 200+idx). Recursion needs each call to have its OWN locals + operand stack, to arbitrary
depth. So the addressing must become **frame-relative**: a frame pointer `fp`, locals at `fp+idx`,
the operand stack relative to `fp+nlocals`. That touches every existing read/write (`100+sp`,
`98+sp`, `99+sp`, `200+idx`) — they all become `fp`-relative. This is the substantive work.

## New state (RAM cells)

- `[0]=pc`  `[1]=sp` (operand count in the CURRENT frame)  `[2]=fp` (current frame base)
  `[3]=nloc` (current frame's local count)  `[4]=csp` (control-stack pointer).
- Bytecode at 10+. Branch-target table at 400+ (unchanged; per-function, the host builder runs over
  each function body). **Frame arena** at e.g. 600+ (frames grow upward). **Control stack** at e.g.
  1500+ (grows by 4 cells/call). **Function table** at e.g. 2000+ (built host-side).
- A frame at base `fp`: locals occupy `fp .. fp+nloc-1`; the operand stack occupies `fp+nloc ..`
  (operand k at `fp+nloc+k`; top at `fp+nloc+sp-1`). So in the `.su`, every `100+sp` becomes
  `fp+nloc+sp`, `200+idx` becomes `fp+idx`, etc.

## Function table (host-side compilation, allowed)

For each function: `(start_pc, nargs, nlocals)`. Built by the test harness from the (multi-function)
body layout — the same kind of load-time compilation as the branch-target table. Stored at
`2000 + func_idx*3`. (Real WASM keeps this in the type/function/code sections; we precompute it
host-side and load it, exactly as we did for branch targets.)

## `call func_idx` — the in-place-args design (NO copy loop)

A per-step machine can't run a variable-length arg-copy loop in one instruction. Avoid copying:
place the callee's frame so its locals `0..nargs-1` **ARE** the caller's top `nargs` operands, in
place. So:

- `new_fp = fp + nloc + sp - nargs`  (the caller's operand stack base is `fp+nloc`; its top `nargs`
  operands start at `fp+nloc+sp-nargs`). The callee's locals `0..nargs-1` alias those operands.
- Callee locals `nargs..nlocals-1`: above the args; assume set-before-read (WASM zero-inits locals;
  document the limit, or zero them — a small fixed-max zeroing, deferred).
- Push a control entry (4 cells at `csp`): `(return_pc = pc+2, saved_fp = fp, saved_nloc = nloc,
  saved_sp = sp - nargs)`. `saved_sp` is the caller's operand count AFTER the args are consumed.
- Set `fp = new_fp`, `nloc = callee.nlocals`, `sp = 0` (callee operand stack empty),
  `pc = callee.start_pc`, `csp += 4`.

## `return` / function-final `end` — pop the frame

- Return value `rv = ramRead(fp + nloc + sp - 1)` (top of the callee operand stack).
- Pop the control entry (read the 4 cells at `csp-4`): restore `fp = saved_fp`, `nloc = saved_nloc`,
  `pc = return_pc`, `csp -= 4`.
- Push `rv` onto the RESTORED caller frame: write `ramWrite(fp + nloc + saved_sp, rv)` and set
  `sp = saved_sp + 1`. (`fp+nloc+saved_sp` is exactly `new_fp` of the call — where the args were —
  so the return value lands where the args came from. Stack discipline: `-nargs +1`.)
- **Top-level termination:** when `csp == 0` (no caller), `end`/`return` halts (the machine idles),
  and the result is the top of frame 0's operand stack — the existing step-1..4 behavior, recovered
  as the `csp==0` case. (The branch-target table's "function-final end → halt" must compose with
  this: an `end` halts iff it's the outermost frame's end.)

## All of this on the substrate (the hard part)

Every frame-relative address (`fp+idx`, `fp+nloc+sp`, `csp±k`, `2000+func_idx*3`) decodes at the
device boundary (hard addressing — sanctioned, it's the memory-access boundary, not value compute).
The call/return arithmetic (`new_fp`, `saved_sp`, `rv` placement) is ordinary substrate tensor ops
on the number-vectors. The only host readouts are address decodes. `nargs`/`nlocals`/`start_pc` are
read from the function table (RAM values), not host constants. **Caution:** this is exactly the
class where a subtle frame-math bug silently corrupts a sibling frame — so each sub-step ships with a
measured substrate test, never "it ran."

## Bounded sub-steps (each compile-AND-run, verified == reference)

1. **5a — frame-relative refactor (no `call` yet).** Introduce `fp`/`nloc`, rewrite the existing
   `100+sp`/`98+sp`/`99+sp`/`200+idx` reads/writes to `fp`-relative; set `fp` = (frame arena base),
   `nloc` = (the single function's local count) at load. Re-verify ALL existing step-1..4 tests pass
   unchanged (same outputs, now frame-relative). This is the risky refactor; isolate it.
2. **5b — function table + non-recursive `call`/`return`.** Two functions: `main` calls a leaf
   `add(a,b)`. Implement `call` (push control frame, set up callee frame in place) and `return`/`end`
   (pop, push rv). Verify `main` calling `add(3,4)` → 7 on the substrate.
3. **5c — recursion (the payoff).** Verify recursive `fib(n)` on the substrate
   (`fib(0..6)=0,1,1,2,3,5,8`), the call stack living in the RAM arena. This is Phase-5.5-B's
   substrate demonstration.
4. **5d — frame-overflow + locals-zeroing notes.** Document the arena size limit and the
   set-before-read locals assumption; add fixed-max locals-zeroing only if a fixture needs it.

## Open design points (resolve when building, not now)

- **`saved_sp` vs recomputation:** save it (4-cell control entry) rather than recompute — simpler and
  robust. Confirm the 4-cell entry math on the substrate.
- **Where the halt lives:** the `csp==0` end-halts case must compose with the branch-target table.
  Likely: `end` consults `csp` (>0 → pop/return; ==0 → halt). Decide the exact blend at 5b.
- **Operand-stack/frame arena sizing:** pick arena base + per-frame stride so deep recursion
  (fib(6) ~ depth 6, ~25 calls) fits in the 1024-cell RAM (bump RAM if needed; log the cap, no
  silent truncation).
- **`nloc` for args-in-place:** the callee's `nlocals` counts its params too, so locals `0..nargs-1`
  (the in-place args) are within `0..nlocals-1`; the operand stack starts at `fp+nlocals`. Verify the
  off-by-one against a 2-arg leaf at 5b before recursion.

## Why scope before coding

This is the one WASM step with no JVM precedent and the only one that redesigns the machine's
addressing. A half-built frame machine silently corrupts sibling frames (the measurement-required
breach class). Decomposing 5a (refactor) → 5b (call/return) → 5c (recursion) keeps each a known-shape,
substrate-verified increment, with the risky frame-relative refactor isolated and regression-gated by
the existing 34 tests.
