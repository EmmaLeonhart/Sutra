# 2026-06-12 — Non-tail recursion: approach 2 (CPS) + the two-approach comparison

Closes the core of queue #6 (aggressively try CPS + Tree RNNs for non-tail recursion and
compare on the substrate). Approach 1 (Tree RNN) finding:
`2026-06-11-non-tail-recursion-approach1-tree-rnn.md`. This adds approach 2 (CPS +
trampolining) and the head-to-head comparison + recommendation.

## Approach 2 — CPS + trampolining (built + measured)

The raw non-tail factorial `fact n = n * fact (n-1)` has pending work (`n *`) on the call
stack; Sutra's if/then/else is a defuzz BLEND (both branches, no stack), so it never halts
— the OCaml frontend lowers it to **UNSUPPORTED** (measured).

The CPS / accumulator rewrite `fact n acc = if n=0 then acc else fact (n-1) (acc*n)` makes
the recursion tail-recursive, **reifying the continuation as `acc`**. The frontend lowers it
to a Sutra `while_loop` — the **trampoline**, a top-level loop that bounces the `(n, acc)`
state until `n = 0`. Measured on the real substrate (`sutrac --run`): `fact 5 1 = 120` =
host `5!`. Artifacts `experiments/non_tail_recursion/{cps_factorial.ml, cps_factorial_raw.ml,
cps_eval.py}`; guard `test_cps_factorial_runs_raw_is_unsupported`.

**Key point + boundary.** For linear arithmetic recursion the continuation **collapses to a
scalar accumulator**, so CPS = the tail-accumulator transform and the trampoline = the
existing substrate `while_loop`. This is exactly Emma's "the stack becomes a data structure"
— here the structure degenerates to one carried number. The GENERAL case — where the pending
work is NOT a simple fold and the continuation can't collapse to an accumulator — needs the
continuation reified as a first-class value (a closure / explicit continuation object). Sutra
has no first-class function values yet (`todo.md` "First-class function values"), so general
CPS is the open piece; the arithmetic/foldable case runs today.

## Comparison — Tree RNN vs CPS (the #6 deliverable)

| Approach | Handles | Substrate status | Stack? | Halts/correct (measured) | Open piece |
|---|---|---|---|---|---|
| **Tree RNN** | recursion whose **structure is fixed** ahead of time (a node depends on fully-computed children) | bottom-up combine, one pass; combine is an ordinary substrate op | none | ✓ `f(f(1,2),f(3,4))`=18, 8-leaf=90, [2,0,0,0]=8 (non-assoc., == host) | dynamic tree shape needs a reified stack |
| **CPS + trampoline** | **sequential** non-tail recursion (`f(x)=g(x, f(x-1))`) | CPS→tail accumulator → `while_loop` trampoline | reified as carried state | ✓ `fact 5`=120 (== host); raw non-tail = UNSUPPORTED | non-foldable continuations need first-class fns |

**Recommendation.** They are complementary, not competitors — pick by recursion shape:
- **Fixed-structure / tree-shaped** reductions → **Tree RNN**: cheapest, no stack, exact,
  works today; the right default when the topology is known (parse trees, fixed folds).
- **Sequential / chain** recursion → **CPS→accumulator trampoline**: works today for the
  foldable (arithmetic-like) case via the existing `while_loop`; a mechanical CPS transform
  in the OCaml frontend would let raw non-tail `let rec` of this shape compile (currently
  UNSUPPORTED) — a concrete, bounded next step.

**Shared frontier (genuinely unsolved, per the design doc + Emma).** Recursion whose
*structure is decided dynamically at runtime* needs an external/reified call stack the network
reads & writes (NTM / stack-RNN) — no clean differentiable solution. Out of scope here;
overlaps the NTM/RAM track (`ram-pointers.md`).

## Next (bounded, not blocking)

- A mechanical **CPS/accumulator transform pass** in `sdk/sutra-from-ocaml` so raw
  foldable non-tail `let rec` compiles (auto-derive the accumulator) instead of UNSUPPORTED.
- First-class function values → general (non-foldable) CPS continuations.
- The dynamic-structure stack machine (frontier; NTM/RAM track).

## Cross-links

- Design: `planning/exploratory/non-tail-recursion-on-the-substrate.md`.
- Approach 1: `planning/findings/2026-06-11-non-tail-recursion-approach1-tree-rnn.md`.
- Artifacts: `experiments/non_tail_recursion/`.
