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

## The fix (path, not yet built)

The host early-exit is only an *efficiency* optimization — the soft-halt blend
already no-ops post-halt iterations. Replace `while True: … if float(_halted) >=
0.99: break` with a **fixed maximum iteration count** (unrolled or a bounded
`for`), no host readout. The result is identical (extra iterations are frozen
no-ops) but fully substrate and traceable/differentiable — the precondition for
fusing the recurrence. Cost: a bound must be chosen (max iterations); the spec
already frames loops as "bounded soft-halt recurrence," so a bound is in-spec.

This is the next real Phase-2 step for recurrence fusion. Multi-state recurrence
(the WASM machine) additionally needs the v1 one-slot-`recur` limit lifted.

## Substrate-purity note

Investigation is reading emitted code + running compiled functions (torch, off any
Sutra runtime hot path). Ollama-free.
