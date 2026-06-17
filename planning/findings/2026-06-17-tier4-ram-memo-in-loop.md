# Tier-4 general memoization: the RAM device works as a loop-carried memo table

**Date:** 2026-06-17
**What:** the feasibility question for tier-4's GENERAL form (recursion beyond the linear-recurrence
family — multi-arg DP, arbitrary single-index DP, irregular recursion): how is a true **memo table**
(not the scalar rolling window) realized as state that persists across a substrate `while_loop`?
Measured two candidates.

## Measured

| memo realization | result |
|---|---|
| **`dict<int,int>` as `while_loop` slot state** (`slot dict<int,int> _m = m;`) | **FAILS** — `RuntimeError: expand(... {[256]}, size=[]): number of sizes (0) must be >= dimensions (1)`. The loop's recurrent state carries SCALAR slots; a dict slot crashes. |
| **RAM device** (`ramRead`/`ramWrite`) used as the memo inside a `while_loop` | **WORKS** — a bottom-up RAM-memo `fib` (`ramWrite(0,0); ramWrite(1,1);` then loop `ramWrite(i, ramRead(i-1)+ramRead(i-2))`) runs on the substrate and returns `fib(8) = 21`. |

So a dict cannot be loop-carried state, **but the RAM device can serve as the memo table** — it is
*external* persistent host-attached memory (the same mechanism the JVM/WASM substrate cores used for
their RAM), so it survives the loop's recurrent iterations and is indexable by an arbitrary integer
key. (`--run` lazily allocates the RAM buffer on first `ramWrite`, so no device pre-attach is needed.)

## Consequence for tier 4

The general memoization form is **NOT blocked** — it is realized with a **RAM-backed memo table**,
not a dict-slot:

- **Linear recurrences** (fib/Pell/Lucas/tribonacci, identity/literal base) → the scalar
  **rolling-window** `while_loop` (already shipped, `tabulate.py`; cheapest, no RAM).
- **General single-index DP** (`f(n)` depending on `f(k)` for arbitrary `k < n`, not just a fixed
  window) → a **bottom-up RAM-memo loop**: seed `ramWrite(j, base(j))` for `j < K`, loop
  `ramWrite(i, combine(ramRead(i - offset_k)))` for `i` in `[K, n]`, return `ramRead(n)`.
- **Multi-arg DP** (e.g. `C(n,k) = C(n-1,k-1) + C(n-1,k)`) → a RAM-memo with a flattened index
  (`ramRead(base + n*stride + k)`) filled by a nested loop.
- **Irregular / unbounded-agenda recursion** → a RAM-backed explicit agenda stack + a RAM-memo (the
  general work-stack loop), still a `while_loop`. (The cases the chat noted gain nothing from
  memoization stay correct but expensive — or fall to tier-5 WASM.)

So "memoize everything → native" is realizable on the substrate via the RAM device. This corrects
the tier-4 scoping doc, which had assumed a dict/agenda memo without verifying it; the dict-slot path
is dead, the RAM-memo path is live.

## Next

Build the RAM-memo synthesis for general single-index DP (the next `tabulate.py` increment), then
multi-arg, then the explicit-agenda form. Each compile-AND-run-verified against ground truth on the
substrate, as the rolling-window family was.
