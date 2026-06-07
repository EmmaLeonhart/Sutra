# Phase 2 feasibility: substrate-pure Sutra functions ARE differentiable graphs; readout is a gradient wall

**Date:** 2026-06-07
**Context:** Substrate-purity → fused-NN overhaul, Phase 2 (the target: compile to
an actual fused neural network / weight file). Script:
`experiments/fused_nn/differentiable_substrate.py`.

## Result (measured)

A substrate-pure Sutra function `f(a,b) = a*b + a` (vectors throughout, zero
`.real()`), compiled by the PyTorch codegen, is **end-to-end differentiable**:

- `f(3,4) = 15` (real axis), correct.
- `∂(out)/∂a = 5` (= b+1) and `∂(out)/∂b = 3` (= a) — the exact chain-rule
  gradients flow from the output back to both inputs. The compiled program is one
  connected autograd graph.

The **same** computation routed through `.real()` (the old breach pattern,
`p = make_real((a*b).real())`) severs the graph:

- `∂/∂a = 1` (only the surviving `+a` path) and `∂/∂b = 0` — a **gradient wall**.
  `.real()` returns a host float (`.item()`), which detaches autograd, so the
  `a*b` contribution's gradient is lost.

## Why it matters

This is the concrete justification for the whole overhaul, and for the
percepta-ntm "trainable seed" claim:

- "Sutra compiles to a differentiable neural network you can train" is **true for
  substrate-pure functions** — gradients flow root→leaf with correct values.
- Every host readout (`.item()`/`.real()`) is a gradient wall that makes the
  claim false. Removing readout is not hygiene — it is the **precondition** for
  the fused-NN / weight-file target to be real.

## Scope / not yet done

This shows a single function is a connected differentiable graph. It does NOT yet
show: (a) fusing a whole multi-function program + its `loop`/RAM recurrence into
ONE graph (torch.fx/trace; the RAM device is host-mutable state that needs
re-representation as a tensor to be traced/exported); (b) exporting a real weight
file. Those are the remaining Phase-2 build. But the foundational property —
differentiability of substrate-pure code — holds, measured.

Ollama-free (pure make_real/arithmetic; no embeddings). Self-asserting script.
