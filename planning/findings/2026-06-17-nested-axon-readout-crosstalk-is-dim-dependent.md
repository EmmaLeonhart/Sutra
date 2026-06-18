# Nested-axon field reads cross-talk at low `runtime_dim` — dimension-dependent, key-dependent

**Date:** 2026-06-17
**Context:** the Phase-6 frontend work shipped NESTED tuple/record/struct destructure for F# and Rust
(`let (a, (b, c)) = t`, `let { inner = { v = vv } } = r`, `let Outer { a, inner: Inner { v } } = o`),
each reading a nested axon through an `Axon` temp per non-leaf prefix
(`Axon _np0 = t.item("_1"); … _np0.item("_0")`). Porting the same lowering to Scala surfaced a
substrate-correctness problem that the F#/Rust fixtures had hidden by luck of their key set.

## Measured

The SAME nested-axon program — an outer 2-axon holding an inner 2-axon, read back through one `Axon`
temp — gives different answers depending ONLY on the axon key names and `runtime_dim`. Hand-written
`.su`, values 5 / (8, 3), expected `5 + 8 + 3 = 16`:

| keys (outer = inner) | `runtime_dim` | result |
|---|---|---|
| `_0`, `_1` | 50 (CLI default) | **16** (clean) |
| `_1`, `_2` | 50 (CLI default) | **24** (WRONG — `a = t._1` reads `5 + 8`: the inner axon's `_1`=8, bound under the outer `_2`, leaks into the outer `_1` read) |
| `_1`, `_2` | 100 | 16 (clean) |
| `_1`, `_2` | 200 | 16 (clean) |
| `_1`, `_2` | 400 | 16 (clean) |

So: nested axons that **reuse key names across levels** need enough dimension to separate the bundled
`bind(role, value)` terms. At `runtime_dim = 50` the `_0`/`_1` roles happen to be near-orthogonal
enough to read cleanly, but `_1`/`_2` are not — the inner level's component leaks into the same-named
outer read. By `runtime_dim ≥ 100` both key sets are clean. This is the bundling-capacity wall
(VSA superposition cross-talk), exposed by key reuse + a low default dimension — NOT a lowering bug
(the generated `axon_item`/`Axon`-temp code is correct; the substrate readout is the failure).

## Consequences

- **Scala nested tuples are BLOCKED at the default dim.** Scala tuple selectors are 1-based (`t._1`,
  `t._2`), i.e. exactly the leaky `_1`/`_2` set. The Scala nested-tuple lowering was written and is
  correct, but it compiles to a program that returns 24 (not 16) at `runtime_dim = 50`, so it was
  NOT shipped (reverted to `UNSUPPORTED`) rather than ship a wrong-running fixture. It needs either
  `runtime_dim ≥ 100` or distinct nested keys.
- **The shipped F#/Rust nested fixtures pass, but marginally.** They use `_0`/`_1` (tuples) or
  distinct field names across levels (records/structs), which read clean at `runtime_dim = 50` — and
  they are measured == ground truth and CI-green. But the margin is thin; a deeper nesting or a
  different key set could cross-talk at dim 50. They are correct for the cases shipped, not a general
  guarantee of nested-axon robustness.

## Options (not yet chosen — a per-fixture-dim or distinct-key decision)

1. **Run nested-axon fixtures at the dimension the task needs** (`runtime_dim ≥ 128`), per the
   CLAUDE.md dimension-audit rule ("pick the smallest `runtime_dim` the task needs" — nested axons
   need more than flat ones). Requires the frontend test harnesses to support a per-fixture dim.
2. **Distinct nested keys** — have the destructure/construction disambiguate levels (e.g. depth-
   prefixed keys) so no role is reused across nesting. A deeper lowering change; keeps dim low.
3. **Accept the default-dim limit** and document nested-axon destructure as a `runtime_dim ≥ 128`
   capability.

Repro: `/tmp/nax_01.su` (keys `_0`/`_1`) and `/tmp/nax_12.su` (keys `_1`/`_2`) in the session
transcript; `python -m sutra_compiler --run [--runtime-dim N] <file>`.
