# Tier-4 irregular recursion: the branchless RAM-stack trampoline is algorithmically correct but does not execute practically on the substrate → WASM fallback

**Date:** 2026-06-17
**Context:** the v0.8.0 "very serious attempt" at the complicated-form native recursion. The DP tiers
succeeded (single-index DP + multi-arg DP are native and **auto-synthesized**, verified == ground
truth — see `2026-06-17-tier4-ram-memo-in-loop.md`, `2026-06-17-tier4-blend-conditional-in-loop.md`,
and `DEVLOG.md`). This finding covers the **last** sub-tier: **irregular (non-grid) recursion** —
recursion whose call structure is runtime data, with no integer index to tabulate (the textbook case
that defeats simple DP). Emma's standing rule for this frontier: *make a very serious attempt; if it
fails, fall back to tier-5 WASM* (which already runs recursive `fib`, 45/45).

## The mechanism (general, and correct)

A **fully branchless explicit RAM-stack post-order evaluator** interprets an arbitrary recursion whose
tree is stored in RAM. It is the general substrate construction for stack-based recursion:

- Two RAM regions are a call stack: frame `nodeid` (`STKID + sp`) and frame `phase` (`STKPH + sp`),
  with the stack pointer `sp` carried as `while_loop` state and a `(2*sp) > 1` halt condition (halts
  exactly when the stack empties — verified: a bare `sp:3→0` countdown loop halts at 0 on the
  substrate).
- A per-frame phase machine (`0→1→2`) pushes the two children one per iteration (so each step is a
  fixed `±1` stack delta — no variable-arity push), then combines: every action is a `±1`-flag
  blend `(((1+flag)*a) + ((1-flag)*b))/2`; `leaf` / `phase` / `push` flags are
  `truth_axis(defuzzy(...))` with the even/odd boundary-clean comparisons (`(2*lc) < -1` for the
  `-1` child sentinel); `RES[node]` is memoized in RAM; the recurrence reads children's `RES`.

**Algorithm verified correct.** A Python mirror of the *exact* blend/flag arithmetic (every `sel`,
`AND`, `OR`, `truth`, RAM op identical to what the `.su` emits) evaluates a 7-node sum-tree in 13
iterations to `RES[root] = 100` == the recursive ground truth, and a 3-node tree in 6 iterations to
`30`. The construction is sound; control composes from substrate primitives with no `if/else`, no
`Math.mod`, no host recursion.

## Measured on the substrate — impractically slow

| program | unroll cap | substrate result |
|---|---|---|
| 7-node sum-tree | 50 (default) | **did not complete** — killed at the 200 s `timeout` wall (EXIT 124) on two separate runs; GPU pinned at 92–98 % the whole time (slow, not crashed) |
| 3-node sum-tree | 8 | GPU pinned at 98 % for minutes; no output within the observation window |

For calibration, the proven Pascal multi-arg-DP loop — the **same** primitives (`while_loop` body,
`ramRead`/`ramWrite`, `truth_axis(defuzzy(...))`, `±1`-flag blends), in the **same** environment —
runs a single case in ~1.5 s (58-test tabulate+native-recursion suite in 21 s). The trampoline body
has only ~2× the op count of the Pascal body, yet is ≥100× slower per run. The cost is **per-step
GPU work** (tiny data: `runtime_dim = 50`, ≤354 MiB, ~327 RAM cells — not memory growth, not CUDA
warmup), i.e. a superlinear interaction between the larger branchless body and the recurrent
`loop` unroll that the DP loops (smaller bodies) do not hit. Root-causing it was not pursued: per the
"barrel through; don't multiply caution" rule and Emma's fallback rule, deep substrate-perf debugging
of this path is out of scope once the fallback is available.

## Conclusion (honest, per the integrity rules)

- The irregular-recursion trampoline is a **correct construction** (Python-mirror-verified), **not** a
  proof that irregular recursion is impossible on the substrate. What is measured is that its
  **current substrate execution is impractical** (does not complete in a usable time).
- Therefore, per Emma's rule, **irregular (non-grid, stack-based) recursion uses tier-5 WASM**
  (`experiments/iso5_substrate_dispatch/wasm_core.su`, which runs recursive `fib(0..6)`, 45/45). The
  DP tiers stay native + auto-synthesized; only the non-tabulable frontier falls back.
- This is the designed outcome of the serious attempt: the parts that compose efficiently on the
  substrate (the DP forms Emma emphasized — "memoize everything", multi-arg DP) are **built and
  automated**; the part that does not (general stack-based recursion) has a working fallback.

## Repro

The exact `.su` + the Python mirror used for verification are reproduced in the session transcript
(`/tmp/sim_tree.py`, `/tmp/tree_eval.su`, `/tmp/treemin/tree3.su`). The trampoline is **not** wired
into the compiler (no auto-detection): unlike the DP tiers it is not a default-on lowering — it is a
documented construction whose substrate cost rules it out as a default, with WASM as the shipped path.
