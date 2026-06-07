# The WASM machine as ONE fused recurrent step (#2 + #3)

**Status:** design (pre-build). Grounds the next deliberate session. Builds on the
#6/#7 loop step/driver split ([[project_orchestrator_model]],
`fused-compile-target.md`) and Emma's directive: the machine must be an ACTUAL
fused recurrent network exported as a weight file, not host-driven steps.

## UPDATE 2026-06-07: #2 DONE via option (A) hard addressing; #3 subsumed

Shipped: tensor-RAM mode (`ram_read`/`ram_write` gather/scatter a single `(N,dim)`
tensor, round->long tensor index, no host `.item()`, functional threading). The
SAME compiled `mini_wasm_machine.su` step traces to ONE fused, host-readout-free
graph (no `aten::item`), saved as `machine_step.pt`; a tiny torch-only orchestrator
drives it (counter loop=3, factorial(3)=6, fresh subprocess=3). Demo
`experiments/fused_nn/fused_ram_machine.py`, CI-guarded. #3 is SUBSUMED — all state
is rows of the one tensor, so the recurrence carries one thing.

**This used option (A) hard addressing.** The machine is now a fused recurrent
network in a weight file, BUT addressing is non-differentiable (gradients reach RAM
*contents*, not *addresses*). **Option (B) — soft "attention on RAM" — remains the
upgrade for the trainable-seed / differentiable vision** (below). The plumbing
(state = one tensor) is shared, so (B) is now an addressing-op swap, not a rebuild.

## Where we are

- #1 (export the loop step) — DONE. `_step_loop_<name>` is module-level; an
  unbounded `while_loop` exports to `step.pt` + a tiny orchestrator
  (`experiments/fused_nn/emit_loop_weight_file.py`).
- The WASM machine (`experiments/iso5_substrate_dispatch/mini_wasm_machine.su`)
  is **substrate-pure per step** (zero `.real()`, dispatch gap +2.0) BUT its
  state lives in a host **list** (`_VSA.ram`, a Python list of vectors) and a
  **host driver** calls `step()` once per instruction. So it is NOT one fused
  recurrent net yet — the container and the loop are host-side.

## Key realization: #2 SUBSUMES #3

#3 ("let the recurrence carry multiple state pieces") exists only because the
machine has several state pieces (pc, sp, halted, program, stack, data). If #2 is
done right — **all of them are rows of a single `(N, dim)` RAM tensor** — then the
recurrence carries exactly ONE thing: that tensor. The v1 "one-slot `recur`" limit
becomes irrelevant; there is one slot and it holds everything. So the build order
is: do #2 (single-tensor state), and #3 falls out.

## Target shape

```
step(ram) -> (ram', halted)        # pure tensor fn; ram is (N, dim)
```

- `ram` is the whole machine state: row 0 = pc, row 1 = sp, row 2 = halted,
  rows 10.. = program, rows 100.. = stack/data. Each row is a number-vector.
- One `step` call = execute one instruction: read opcode at pc, dispatch (the
  +2.0-gap truth-axis blend already proven), compute, write back the affected
  rows, advance pc/sp, set halted. All as tensor ops on `ram`.
- The recurrence (`ram' -> next ram`) is the substrate RNN: `loop`/orchestrator
  feeds `ram'` back. Halt = orchestrator reads the halted row's truth axis.
- Export: trace `step` -> `machine_step.pt`; the orchestrator drives the
  recurrence and reads halt + the OUTPUT region. This is the machine-as-weight-file.

## The ONE decision that determines the build: addressing

To read `ram[pc]` and write `ram[addr]` inside a pure step, the address comes from
a pointer *vector*. Two mechanisms, and Emma should pick:

**(A) Hard addressing — `ram_gather` / `ram_scatter` (already built).**
`idx = round(ptr.real).long()` (a TENSOR index — no `.item()`, no host int),
then `index_select` / `index_copy`. Substrate-pure and traceable (the
`emit_loop_weight_file` path works). BUT the address derivation (`round`) is
**non-differentiable**: gradients flow to RAM *contents* but not through the
*address*. Ships now; the machine becomes one fused tensor step today. It is a
fused recurrent net, just not differentiable-through-addressing.

**(B) Soft addressing — "attention on RAM" (Emma's stated goal). CHOSEN
2026-06-07: LINEAR REGRESSION OVER MEMORY.** Address weights from a *linear* map of
the query (no softmax): `w = addr_weights(query)` over the N rows; `read = w @ ram`
(a matmul); `write: ram' = ram + outer(w, (new_val - read))`. **Fully differentiable**
end-to-end (address included) — the read/write head as a linear regression over
memory, matching the percepta-ntm paper's "attention on RAM (first step: a simple
linear regression over memory)". Cost O(N·dim) per access vs O(dim) for hard.
(Emma picked this over softmax-temperature, straight-through one-hot, and content-
cosine addressing — AskUserQuestion 2026-06-07.)

**Why it's Emma's call, not mine:** (A) and (B) produce *different* machines —
(A) ships the fused step fastest; (B) is the actual differentiable "attention on
RAM" target and changes what the trainable-seed experiments would measure. Emma
has ground truth on the substrate + the attention-on-RAM intent. Picking wrong
silently overwrites her design. (CLAUDE.md: never invent a thing Emma implies
exists; implement Emma's algorithm.)

## Build steps once addressing is chosen

1. Rewrite `mini_wasm_machine` state from the host RAM list to a single `(N, dim)`
   tensor passed through `step(ram) -> (ram', halted)` (use `ram_gather`/
   `ram_scatter` for (A), or the attention matmul for (B)).
2. Make `step` a Sutra-level pure function (or hand-built step graph first to
   prove the mechanism, then push into the compiler) with no host list / host int.
3. Drive via the orchestrator (feed `ram'` back; read halted + output). Export
   `machine_step.pt` and verify a fresh-subprocess run reproduces the reference
   programs (counter loop, factorial) — decoded output == reference, measured.
4. THEN redo the experiments on the fused machine and report whether the numbers
   change (Emma's "redo the experimentation" — meaningful only after #2).

## Hard rail

Verify substrate-to-substrate (decoded output == reference programs), no faking.
"It traced" ≠ "it computes the machine" — compare to the eager 30/30 machine runs.
