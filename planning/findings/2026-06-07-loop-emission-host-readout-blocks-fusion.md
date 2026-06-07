# Loop emission has a host-readout early-exit (`float(_halted)` + `break`) — a leak the gate missed and the obstacle to recurrence fusion

**Date:** 2026-06-07
**Context:** Substrate-purity → fused-NN overhaul. Investigating Phase-2 fusion of
the substrate `loop` recurrence (toward fusing the machine's stepwise recurrence
into one graph). Read the codegen's emitted loop body for `examples/do_while_adder.su`.

## What the loop emits (read from generated code)

```
x = (x + 1)                                  # do_while body once
while True:
    _pre_x = x
    _cond = _VSA.gt(11, x)                    # substrate
    _cond_truth = _VSA.truth_axis(_cond)      # substrate (0-dim tensor)
    _keep = _VSA.heaviside(_cond_truth)       # substrate
    _halt_term = 1.0 - _keep
    _halted = _VSA.saturate_unit(_halted + _halt_term)   # substrate accumulation
    x = (x + 1)
    x = (1.0 - _halted) * x + _halted * _pre_x           # substrate soft-halt blend
    if float(_halted) >= 0.99:                # <-- HOST READOUT + host control flow
        break
```

## The finding

- The soft-halt **math** is substrate: `gt`, `truth_axis`, `heaviside`,
  `saturate_unit`, and the blend `x = (1−_halted)·x + _halted·x_pre` are all
  tensor ops. Once `_halted` saturates to ~1, the blend freezes `x` — so further
  iterations are no-ops on the substrate.
- But the emission adds a **host early-exit**: `if float(_halted) >= 0.99: break`.
  `float(_halted)` converts a tensor to a host scalar (a `.item()`-class readout
  that **detaches autograd**), and `break` is host control flow. This is a
  substrate-purity leak.

## Two consequences

1. **Audit gap.** The `test_no_host_readout` gate scans the runtime *prelude*
   (the `_VSA` class methods); this leak is in **user-function loop emission**, so
   the gate never saw it. The host-readout audit must also cover emitted loop/`if`
   bodies, not just runtime methods.
2. **Fusion blocker.** A host `break` is not traceable into one graph and the
   `float()` severs the gradient — so the recurrence cannot be fused or
   backpropagated through as emitted. This is the concrete obstacle to making the
   loop (and thus the machine's recurrence) a single differentiable graph.

## The fix (RESOLVED 2026-06-07 — step/driver split, NOT bounded-N)

The original fix proposed here (replace the host break with a fixed max-iteration
bound) was **superseded by Emma's orchestrator model** (2026-06-07,
[[project_orchestrator_model]]). Under that model the `float(_halted)` halt-read
is the *legitimate terminal/orchestrator boundary* — it does not need to be
eliminated, it needs to live in the **driver** (the thin orchestrator), not in the
fusable **step graph**. Bounding the iteration count would have been the wrong fix:
it forces an arbitrary cap and still fuses driver-and-step together.

**What shipped:** `_translate_loop_function_decl` in `codegen_base.py` now emits the
per-tick computation as a nested **pure `_step(...)`** (condition + body + soft-halt
blend, all substrate, returning `(state..., _halted)` — ZERO host readout), and a
thin **driver** that calls `_step` and does the single `float(_halted) >= 0.99:
break`. Generated shape for `do_while_adder.su`:

```
def _loop_addNumber(_init_x):
    x = _init_x
    def _step(_t, x):                         # <-- PURE, exportable step graph
        _halted = 0.0
        _pre_x = x
        _cond = _VSA.gt(11, x); _cond_truth = _VSA.truth_axis(_cond)
        _keep = _VSA.heaviside(_cond_truth)
        _halted = _VSA.saturate_unit(_halted + (1.0 - _keep))
        x = (x + 1)
        x = (1.0 - _halted) * x + _halted * _pre_x
        return (x, _halted,)
    x = (x + 1)                               # do_while: body once
    _t = 0
    while True:                               # <-- thin in-module orchestrator
        x, _halted = _step(_t, x)
        _t += 1
        if float(_halted) >= 0.99:            # halt-read: orchestrator boundary
            break
    return (x, _halted,)
```

Behaviour is identical (the driver breaks on the first saturating tick, so the
per-call `_halted` matches the old cross-tick accumulation). Verified: loop +
await suites green (59 passed), and the reframed `test_no_host_readout` now asserts
**(1)** `_step` is readout-free (`test_step_graph_is_readout_free`) and **(2)** the
single `float(_halted)` stays in the driver (`test_driver_halt_read_*`).

This satisfies overhaul Phase-2 item #6 (relocate the halt-read to the orchestrator;
make the step separable/fusable). **Remaining (#7):** the step is nested inside the
loop function, so the export path can't yet pull it out as a standalone weight
file — hoisting `_step` to a module-level `_step_<name>` (closing over only `_VSA`
+ the array param) is the next bounded step to realize the loop weight-file export.
Multi-state recurrence (the WASM machine) additionally needs the v1 one-slot-`recur`
limit lifted.

## Substrate-purity note

Investigation is reading emitted code + running compiled functions (torch, off any
Sutra runtime hot path). Ollama-free.
