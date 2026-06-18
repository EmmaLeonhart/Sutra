# Quantum computing × Sutra — exploration (grounded in what actually ran)

**Date:** 2026-06-18. Started from Emma's queue braindump (quantum + functional
programming, emulators worth trying, the Sutra angle). This doc records what was
*measured*, not the speculation — every claim below has a runnable script under
`experiments/quantum/`.

## What's accessible (measured)

All three major Python emulators install cleanly on Py 3.13 / Windows via pip and
produce a correct Bell state (`experiments/quantum/emulator_sweep.py`):

| emulator | version | Bell result |
|---|---|---|
| **PennyLane** | 0.45.0 | `default.qubit`: P(\|00⟩)=P(\|11⟩)=0.5, P(\|01⟩)=P(\|10⟩)=0 |
| **Qiskit** (+ `qiskit-aer`) | 2.4.2 | Aer: ~50/50 over \|00⟩/\|11⟩, none on \|01⟩/\|10⟩ |
| **Cirq** | 1.6.1 | statevector: ~50/50 over \|00⟩/\|11⟩ |

- **Quirk** is browser-only (visual circuit builder) — not scriptable here; noted, not run.
- **Q# / Silq**: `dotnet 9.0.203` IS present, so Q# is plausible via the `qsharp`
  Python package or the .NET Q# SDK. Not yet exercised (Q3). Silq has its own toolchain
  (assess accessibility separately).

## The FP ↔ quantum relationship (Emma's framing, confirmed against what ran)

**Natural fits** — quantum circuits compose unitary transformations, which maps onto
function composition; quantum state has no side effects *until measurement*, resonating
with pure FP. The Bell circuit above is literally `CNOT ∘ (H ⊗ I)` applied to |00⟩.

**Tensions** — measurement collapses state irreversibly (a side effect; not
referentially transparent), and the no-cloning theorem breaks the FP assumption that
values are freely copyable. Both are real and show up immediately: the Bell `measure`
is where determinism ends and you only get a *distribution*.

## The Sutra angle — measured, not hand-waved

The part of Emma's note that matters for Sutra: **a parameterized quantum circuit is a
differentiable program.** `experiments/quantum/pennylane_differentiable.py` shows it
end-to-end on the substrate of `default.qubit`:

- `<Z>(θ)` for `RY(θ)|0⟩` is `cos θ` — exact (measured 0.877583 at θ=0.5).
- `d<Z>/dθ = -sin θ` — exact analytic gradient via parameter-shift / autograd
  (measured -0.479426 at θ=0.5).
- **Gradient descent trains the circuit**: from θ=0.1, 40 steps converge to θ=π,
  driving `<Z> → -1` (the qubit to |1⟩). This is the **variational / VQE paradigm**.

This is structurally the *same move Sutra makes*: a forward pass over a tensor graph
that is differentiable end-to-end, trained by gradient descent. A quantum circuit is a
very *constrained* such graph — every gate is a unitary (norm-preserving) matrix, and
the "loss" is an expectation value of an observable. Sutra's graph is unconstrained
real/complex tensor ops on the frozen-LLM semantic subspace; the quantum graph is
unitaries on a 2^n-dim complex Hilbert space. The differentiability and the
gradient-trained-parameters story are the shared spine; the constraint (unitarity,
no-cloning, measurement collapse) is what's quantum-specific.

**Honest scope:** this is a conceptual + structural parallel, demonstrated on toy
circuits. It is NOT a claim that Sutra *is* a quantum system or that Sutra ops are
unitary (they are not — bundling is lossy superposition, not a reversible unitary).
The interesting, testable direction (not yet done) is whether Sutra's complex-axis
machinery (`AXIS_REAL`/`AXIS_IMAG`, the eigenrotation primitives) can express a small
unitary / VQE-shaped circuit on its own substrate and train it the same way — i.e.
compile a variational circuit *to Sutra* rather than to `default.qubit`. That is the
next genuine experiment, listed as a queue task.

## Status of the exploration tasks

- **Q1 emulator sweep** — DONE (PennyLane/Qiskit/Cirq accessible + verified).
- **Q2 differentiable circuit + training** — DONE (PennyLane, measured above).
- **Q3 Q# / Silq** — open (dotnet present; assess `qsharp` pkg / Silq).
- **Q4 writeup** — this doc (first pass; extend as Q3 + the "VQE-to-Sutra" experiment land).
- **Q5 (proposed) VQE-to-Sutra** — express + train a 1–2 parameter variational circuit on
  Sutra's own complex substrate (eigenrotation + AXIS_REAL/IMAG), compare to PennyLane.
  The genuinely novel test of the parallel; only worth claiming once it runs.
