# Tier-4 complicated form: blend conditionals work in a while_loop body (with the even/odd boundary fix)

**Date:** 2026-06-17
**Context:** the v0.8.0 "very serious attempt" at the complicated-form native recursion (multi-arg DP
/ irregular). These need per-cell **base-case conditionals** and **index management** inside a
`while_loop` body — but the V1 codegen rejects `if/else` and `Math.mod` is banned. The question:
can a loop body do a blend-based conditional cleanly?

## Measured

A `while_loop` body computing `acc += (i < 3 ? i : 0)` via a substrate blend
(`flag = truth_axis(defuzzy(cond)); contrib = ((1+flag)*i + (1-flag)*0)/2`):

| condition form | result (Σ i for i<3 over i=0..4) |
|---|---|
| `defuzzy(i < 3)` (naive strict `<`) | **4** (WRONG) — at `i==3` the strict `<` defuzzes ~0.5, leaking a fractional `1.5` contribution |
| `defuzzy((2*i) < 5)` (even/odd trick: `i<3` ≡ `2i<5`, even vs odd → never equal at the boundary) | **3** (CORRECT) |

So **blend-based conditionals work in a `while_loop` body** (`truth_axis`/`defuzzy` on loop state +
the ±1-flag blend), and the strict-`<` boundary ambiguity (same one fixed in the WASM/JVM cores) is
removed by the **even/odd trick** — replace `i < K` with `(2*i) < (2K-1)`, `i > K` with
`(2*i) > (2K+1)`, etc. (even vs odd operands never collide), and use the crisp `==` for equalities.

## Consequence for the serious attempt

All building blocks for the complicated form are now verified-feasible — no hard blocker:
- **RAM-memo in a loop** ✓ (`2026-06-17-tier4-ram-memo-in-loop.md`).
- **Blend-based base-case conditionals in a loop body** ✓ (this finding), with boundary-clean
  comparisons via the even/odd trick.
- **Mod-free index management** ✓ — carry `(row, col)` as separate loop counters and wrap via a
  blend (`do_wrap = (2*col) > (2*row+1)` → `col = (1-do_wrap)*(col+1)`, `row = row + do_wrap`),
  no `Math.mod`, no flattened-index decode.

So multi-arg DP (e.g. `C(n,k) = C(n-1,k-1)+C(n-1,k)`, edges `=1`) is realizable as a single
RAM-memo `while_loop`: index `row*W + col`, edge cells via the `col==0 || col==row` blend, interior
via `ramRead((row-1)*W + col-1) + ramRead((row-1)*W + col)`, advance via the blend wrap. The serious
attempt continues by hand-writing C(n,k) this way (proving the full pattern on the substrate), then
auto-synthesizing it from a detected 2-arg shape. If that lands, the complicated form is native; if
it fails despite the feasible blocks, Emma's rule is to fall back to tier-5 WASM.
