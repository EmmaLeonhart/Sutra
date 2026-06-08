# Attention-on-RAM parser runs on the substrate (3 parse tasks, exact)

**Date:** 2026-06-08
**Context:** NTM-archetype track build step (b)+(c) — the design doc
`planning/exploratory/codable-attention-on-ram-parser.md` taken from Python
reference to OCaml to the Sutra substrate. Resolves the doc's open questions
O1 and O2 with measurements.

## Result (measured)

One **constructed-weight (untrained)** attention head reading a RAM tape, rendered
as imperative OCaml and transpiled (`sdk/sutra-from-ocaml/`) to `.su`, runs on the
real substrate (`sutrac --run`, PyTorch codegen) and reproduces the Python reference
oracle (`experiments/attention_on_ram/reference.py`) **exactly** on all three parse
tasks:

| fixture | task | substrate result | oracle |
|---|---|---|---|
| `attn_sum_tape` | `sum_tape([1;2;3;4])` (q=ones → Σ tape) | **10.0** | 10.0 |
| `attn_dot_tape` | `dot_tape([1;2;3],[1;0;-1])` (Σ wᵢxᵢ = linear regression over memory) | **-2.0** | -2.0 |
| `attn_select_field` | `select_field([11;22;33],1)` (hard location read) | **22.0** | 22.0 |

CI-guarded as runnable fixtures in `sdk/sutra-from-ocaml/tests/test_lower_fixtures.py`
(`_RUNNABLE_FIXTURES`); the Python oracle is guarded by
`experiments/attention_on_ram/test_reference.py` (10/10 exact). OCaml suite 88 passed.

This is the first concrete instance of Emma's reframed vision: an imperative
RAM-editing computation (linear regression over memory) represented as a constructed
attention read and **landed on the substrate** as a sibling of `mini_wasm_machine.su`.

## O1 — soft vs hard attention on the substrate (resolved)

- **Linear (no-softmax) regime** (`sum_tape`, `dot_tape`): the attention output is a
  plain weighted sum `Σ aᵢ vᵢ`. On the substrate this is a loop-reduction of
  `ramRead` cells — exact integer arithmetic, no approximation. The linear-regression
  framing needs *only* this regime.
- **Hard location-addressing** (`select_field`): the math reference uses a hardmax
  over location scores to pick cell `j`; in the imperative rendering that IS an
  indexed RAM read (`ramRead(base + j)`) — exact. No softmax primitive was needed for
  these tasks. (A genuine on-substrate softmax remains future work for content-based,
  non-location attention; not required for the first step.)

## O2 — the aggregate as a substrate `loop` (resolved, with a constraint)

The substrate `while`→`loop` recurrence carries **scalar slots** (`slot_store` writes
a single state-plane cell; `slot_load` returns a 0-dim scalar). `ramRead`, by design,
returns a number-**vector** (the I/O boundary, ram-pointers.md). So the OCaml-idiomatic
accumulator `let acc = ref 0` **does not compose** with a RAM read inside the loop:
`acc + ramRead(i)` is a dim-N vector and storing it into a scalar slot raises
`expand([N], size=[])`. Measured directly (the naive form fails at `slot_store`).

**The substrate-correct shape** (the one the `mini_wasm_machine` already uses): keep
the **accumulator in a RAM cell** (vector space — `acc.(0)`, updated by
`ramWrite(acc, ramRead(acc) + …)` each iteration) and carry **only the scalar index**
`i` as a loop slot. The loop body's `ramWrite` side-effect persists across iterations
(confirming the bounded `loop` host-drives the steps, so RAM mutation per tick is
visible to the next tick — the orchestrator-model boundary). All three fixtures use
this shape; the fixture comments document why.

**Implication:** "aggregate over RAM" on the substrate is *accumulator-in-RAM +
scalar-control-in-slot*, not *accumulator-in-slot*. A future vector-carrying loop
primitive would let the idiomatic `ref` accumulator work, but is not needed for the
attention-on-RAM parser. This is a constraint to honour in the reduction work, not a
blocker.

## Supporting runtime/transpiler changes (this session)

1. **RAM lazily allocated for a standalone run** (`codegen_pytorch.py` `ram_write`).
   `self.ram` defaulted to `None`, so a standalone `.su` that does `Array.make`
   (→ `ramWrite`) had no device — writes were no-ops and reads returned zero
   (`select_field` returned 0 before the fix). Now `ram_write` lazily allocates the
   host buffer and grows it to cover the address; the CLI `--run` is the default
   orchestrator. A separate orchestrator can still pre-attach `self.ram` (the
   `mini_wasm_machine`/`ntm_ram` path is unchanged — `ram` is already attached there,
   so the lazy branch is never taken). No new host readout (`.item()` gate unchanged).
2. **OCaml `sign_expression` lowered** (`sutra-from-ocaml/lower.py`). `(-1)` parses as
   `sign_expression(sign_operator, operand)`, distinct from the `!r` `prefix_expression`;
   it now lowers `-` to arithmetic negation `-(operand)`. Needed for the negative
   coefficient in `dot_tape`.

## Substrate-purity note

The Python reference is constructed-weight torch analysis OFF any Sutra runtime hot
path (compile/monitor, allowed). The substrate `.su` runs are genuine Sutra programs;
the only host reads are the sanctioned RAM-address-decode I/O wire (ram-pointers.md)
and the terminal result decode (the external orchestrator boundary). No `.real()`,
no in-language readout.

## Scope / not claimed

This is the linear (first-step) attention-on-RAM, three small parse tasks, integer
tapes. NOT claimed: a trained/SGD head (constructed only); content-based softmax
attention (only linear + hard-location here); large tapes (the RAM-stride spacing and
host buffer are demo-scale). Next: the reduction study (smallest dim/head count that
still passes the oracle) and growing the example set, per the design doc §5.
