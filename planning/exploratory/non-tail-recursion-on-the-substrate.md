# Non-tail recursion on the substrate — aggressively try CPS and Tree RNNs

**Status:** exploratory design for the back-of-queue non-tail-recursion task
(Emma 2026-06-11: aggressively try **two** approaches — **CPS** and **Tree RNNs** —
with a very large amount of effort, and compare). Executes at the END OF THE QUEUE,
after the GUI block, ahead of the todo-end new-language frontends.

## The problem

Sutra's `if/then/else` is a defuzz **blend** that evaluates BOTH branches
unconditionally, and there is no call stack. A naive non-tail self-call —
`f(x) = 1 + f(x-1)` — never halts on the substrate: the `1 +` is *pending work* that, in
a normal language, sits on the call stack waiting for `f(x-1)` to return. Tail recursion
already works (it lowers to a substrate `while_loop`) precisely because it has no pending
work. **An RNN is tail-recursive by construction** — each step needs only the current
hidden state, no pending computation, stack depth always 1. Non-tail recursion is exactly
the case that breaks that.

## The two approaches to build (Emma's, verbatim framing)

### 1. CPS (Continuation-Passing Style) + trampolining

Normal recursion has pending work on the stack:

```
f(x) = 1 + f(x-1)     # the `1 +` waits for f(x-1) to return
```

CPS makes the pending work explicit by passing a **continuation** — a function
representing "what to do next":

```
f(x, k) = f(x-1, λresult. k(1 + result))
```

Now the recursion is **tail-recursive** — but you've built a **chain of lambdas instead
of a call stack**. The stack is now a *data structure* (the continuation closure) rather
than implicit. A network could in principle manipulate this as an explicit object.

**Trampolining** is the runtime partner: instead of actually recursing, return a **thunk**
(a deferred computation); a loop at the top level keeps **bouncing** until it gets a real
value. No stack overflow — just iteration over lazy steps.

On Sutra: the continuation chain / thunk must be a **substrate value the loop carries**,
and the trampoline is the existing `while_loop`. The open piece is representing the
continuation — either via first-class function values (`todo.md` "First-class function
values") or as an explicit reified continuation structure.

### 2. Tree RNNs

Instead of processing a sequence, process a **tree**. At each internal node, combine the
representations of the children:

```
h(node) = f(h(left_child), h(right_child))
```

This is non-tail **in structure** — a node's value depends on fully-computed subtree
values. But crucially the **tree topology is fixed ahead of time**: you're not learning
*when* to recurse, only *how to combine*. So it computes **bottom-up in a single forward
pass, no actual stack needed**. This is the tractable, fixed-structure case.

## The spine: fixed vs dynamic recursion structure

- **Fixed structure** → tractable. Topology known ahead → evaluate children-first,
  bottom-up, single pass, no stack (Tree RNN; and a CPS chain of known length is finite).
- **Dynamic structure** (the network decides the recursion structure at runtime) → the
  **hard** case. Requires an external stack, or **reifying the call stack as explicit
  memory the network reads/writes** (NTM / stack-RNN). Emma: "genuinely unsolved in a
  clean differentiable way." Out of scope for the first cut; noted as the frontier the
  two approaches above stop short of. (Overlaps the NTM/RAM track, `ram-pointers.md`.)

## Comparison protocol (measure, don't claim)

- Targets: a non-tail arithmetic recursion (`factorial`, `1 + f(x-1)`-shape) for **CPS**;
  a fixed-topology **tree fold** (`h(node) = f(h(left), h(right))`) for **Tree RNN**.
- For each: build it, RUN on the substrate (`sutrac --run`), compare decoded output to
  ground truth. Record: halts? correct? to what depth before degrading? substrate-pure
  (no host control flow / no readout inside the op)? differentiable end-to-end?
- Deliverable: a finding with a per-approach table + which to promote. An approach that
  doesn't work is marked NEGATIVE with the measured reason (required by the integrity rules).

## Why aggressively try both

Emma's call: put a very large amount of effort into building both CPS and Tree RNNs and
comparing, rather than committing to one prematurely. They span the space — CPS turns the
stack into carried data (general, needs continuations), Tree RNN exploits fixed structure
(special, single-pass). The right Sutra encoding is an empirical question.

## Cross-links

- `planning/sutra-spec/control-flow.md` (the defuzz blend, loops), `non-halting-loop.md`
  (recur / substrate-RNN — the tail-recursive base both build on).
- `todo.md` "First-class function values" (CPS continuations as values).
- The dynamic-structure hard case → NTM/stack-RNN track + `ram-pointers.md` (reified stack).
