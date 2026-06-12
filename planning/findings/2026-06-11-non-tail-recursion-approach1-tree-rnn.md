# 2026-06-11 — Non-tail recursion, approach 1 (Tree RNN): works on the substrate

Part of queue #6 (aggressively build & compare CPS + Tree RNNs for non-tail recursion).
This is **approach 1 of 2: Tree RNNs**. Approach 2 (CPS + trampolining) is next.

## What was built

`experiments/non_tail_recursion/tree_combine.su` — the combine step `f(l, r) = 2*l + r`
(non-associative on purpose). `tree_rnn_eval.py` — folds a fixed balanced binary tree
bottom-up, calling `combine` on the substrate at each internal node; the host knows the
tree shape and walks it level by level. Guard: `test_non_tail_recursion.py`.

## Result (measured)

| leaves | substrate root | host root | match |
|---|---|---|---|
| [1,2,3,4] | 18.0 | 18.0 | ✓ (`f(f(1,2),f(3,4))=f(4,10)=18`) |
| [1..8] (depth 3) | 90.0 | 90.0 | ✓ |
| [2,0,0,0] | 8.0 | 8.0 | ✓ (the 2 is doubled twice by its tree position) |

Sanity: `combine(3,4)=10` via `sutrac --run`. The non-associative combine means the result
depends on the **tree bracketing**, so matching the host fold confirms the substrate computes
the actual tree-structured (non-tail-in-structure) reduction, not a flat reduce.

## Reading

Non-tail recursion *in structure* — a node's value depends on fully-computed children — is
**tractable with no call stack when the tree topology is fixed**: you evaluate bottom-up in
a single pass. On Sutra the combine is an ordinary substrate op; the host walks the known
tree level by level (the "fixed structure" case from the design doc). This is the easy,
solved end of the non-tail spectrum — it works because *when* to recurse is known ahead of
time; only *how to combine* is computed.

What this does NOT cover (by design, this approach):
- **Dynamic structure** — the tree shape decided at runtime — still needs a reified/external
  stack (the genuinely-unsolved-differentiably frontier; see the design doc).
- **Sequential non-tail recursion** (`f(x)=1+f(x-1)`) where the "tree" is a degenerate chain
  with pending work per level — that's the **CPS + trampolining** case (approach 2, next):
  turn the pending work into a carried continuation and bounce a top-level loop.

## Cross-links

- Design: `planning/exploratory/non-tail-recursion-on-the-substrate.md`.
- Artifacts: `experiments/non_tail_recursion/{tree_combine.su, tree_rnn_eval.py,
  test_non_tail_recursion.py}`.
