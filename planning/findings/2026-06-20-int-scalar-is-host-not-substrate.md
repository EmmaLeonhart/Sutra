# `int`/`scalar` values are HOST floats today, not substrate number-vectors (spec was self-contradictory) — 2026-06-20

## What was found

Building a higher-order substrate example (`examples/higher_order_functions.su`), an `int`-typed fold
decoded to a host `float`, not a `torch.Tensor`. Tracing it:

- `function int addp(int a, int b){ return a + b; }` emits `return ((a + b)) * _program_halt` and
  `addp(2, 3)` returns a host **`5.0`** (Python float), NOT a substrate tensor.
- `foreach (int x in [...]) { acc = f(acc, x); }` unrolls to `x = 1; acc = f(acc, x); …` with host int
  literals — the whole fold runs on the host.
- By contrast `make_real(2) + make_real(3)` returns a `torch.Tensor` — a genuine substrate add.

So: **a bare `int`/`scalar` is a host Python float in the current compiler; it becomes a substrate
number-vector only when explicitly lifted via `make_real`.**

## The spec was internally contradictory

`planning/sutra-spec/types.md` said two incompatible things:
- (top, numeric-types list) "At runtime … they are all **substrate vectors** … not host floats."
- (§"The number axis and the integer class") augmented assignment "emits Python's native `target op= value`
  form, which has identical semantics for **Python floats (what scalars are today)**…"

The top section stated the DESIGN TARGET (number-axis substrate vectors) as if it were current fact; the
number-axis section admits the reality (Python floats). Measurement confirms the latter. Per the integrity
rule ("if spec and implementation disagree, resolve it explicitly — fix the impl or update the spec"), the
spec was corrected to state the reality: int/scalar are host floats today; the substrate-vector number-axis
representation is the target, not yet implemented.

## Why this is NOT a substrate leak (important for auditors)

The "every Sutra operation runs on the substrate" rule governs the **VECTOR/VSA operations** —
bind, bundle, unbind, similarity, rotation, projection, the axon ops. Host scalar arithmetic on an
`int`/`scalar`-typed value (`a + b` where both are host floats) is **outside that operation set today**,
by the type design (the number axis is a target representation, not yet the runtime form). A substrate-leak
auditor (e.g. the daily-audit cron, or `experiments/substrate_leak_sweep.py`) should **NOT** flag `a + b`
on int-typed values as a host-readout leak on this basis. The genuine leaks are scalar EXTRACTION FROM A
VECTOR inside an operation (`v[AXIS_REAL]` / `.item()` / `float(tensor…)` mid-op), which is a different
thing.

## Consequence for higher-order / collection code

To compute over numbers **on the substrate**, use number-vectors (`make_real`, `vector`), not `int`. The
shipped example demonstrates both: the `int` fold computes on the host; the `vector` fold computes on the
substrate (returns a tensor, decoded off the real axis). The test asserts a tensor return so the host path
can't masquerade as substrate.

## Open (NOT chased here)

Whether `int`/`scalar` SHOULD be lifted to substrate number-vectors at runtime (closing the gap to the
design target) is a real but large change — every numeric op would route through the number axis. Tracked
as design-target work in `types.md` §"Future work on the integer class"; not a one-tick fix, and the
current host-float behavior is now honestly documented rather than contradicting the spec.
