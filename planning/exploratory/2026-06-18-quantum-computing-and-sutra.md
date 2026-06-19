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
- **Q#** — accessible + RUN (`experiments/quantum/qsharp_fp_native.py`, via the `qsharp`
  pip package / Azure QDK sparse simulator). Bell and a 3-qubit **GHZ** both give the correct
  entangled distribution (only |00⟩/|11⟩, only |000⟩/|111⟩). Q# is the most FP-native of the set
  (strong typing, immutable mid-circuit state, operations as values). Caveat: the `qsharp`
  package warns it is superseded by `qdk` — `import qsharp` still works.
- **Silq** — NOT pip-installable (confirmed: not on PyPI). It ships as a standalone compiler
  binary / VS Code extension (D-language toolchain, ETH Zurich), so it was not exercised — the
  documented blocker per "as long as the software is accessible."

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
The interesting, testable direction is whether Sutra's complex-axis machinery
(`AXIS_REAL`/`AXIS_IMAG`, the eigenrotation primitives) can express a small unitary /
VQE-shaped circuit on its own substrate and train it the same way — i.e. compile a
variational circuit *to Sutra* rather than to `default.qubit`. **Done 2026-06-19**
(`experiments/quantum/vqe_to_sutra.py`): the single-qubit `RY(θ)|0>`/`<Z>` circuit is
expressed on the substrate by packing the amplitudes `(α, β)` as one complex number
`z = α + iβ` on `AXIS_REAL`/`AXIS_IMAG`; `RY(θ)` is the substrate eigenrotation
`cexp(i·θ/2)` acting on `z₀ = 1+0i`, and `<Z> = |α|² − |β|² = Re(z²)` via `complex_mul`
+ `_re`. With `θ` a torch parameter, gradient descent (start 0.1, 40 steps, stepsize
0.4 — the same schedule as the PennyLane run) trains it to PennyLane's fixed point.
Measured on the real `_TorchVSA` substrate:

- `<Z>(0.5)` = **0.877473** (cos 0.5 = 0.877583; ~1e-4).
- `d<Z>/dθ(0.5)` = **−0.479424** (−sin 0.5 = −0.479426; ~1e-6 — the eigenrotation
  gradient is essentially exact, flowing through the `_cos0`/`_sin0` trig leaves).
- trained `θ → 3.1411` (π = 3.1416), `<Z> → −0.999895` (−1).

So Sutra's substrate can **express and train** a VQE-shaped differentiable graph to the
same trained parameter and expectation as PennyLane's `default.qubit`. This is the
direct confirmation of the "quantum circuit = constrained differentiable graph = Sutra
forward pass" parallel — measured, not hand-waved. **Still NOT claimed:** that Sutra is
a quantum computer or that its ops are unitary (bundling is lossy); and only the
single-qubit, non-entangling toy — multi-qubit entangling circuits are out of scope.

## Status of the exploration tasks

- **Q1 emulator sweep** — DONE (PennyLane/Qiskit/Cirq accessible + verified).
- **Q2 differentiable circuit + training** — DONE (PennyLane, measured above).
- **Q3 Q# / Silq** — Q# DONE (Bell + GHZ run via the `qsharp` pkg); Silq not accessible (no pip).
- **Q4 writeup** — this doc (first pass; extend as Q3 + the "VQE-to-Sutra" experiment land).
- **Q5 VQE-to-Sutra** — DONE 2026-06-19 (`experiments/quantum/vqe_to_sutra.py`): expressed
  + trained the `RY(θ)|0>`/`<Z>` circuit on Sutra's own complex substrate (eigenrotation +
  AXIS_REAL/IMAG), reaching PennyLane's fixed point (θ→π, `<Z>`→−1; value/gradient match the
  closed form to ~1e-4 / ~1e-6). The genuinely novel test of the parallel — see the measured
  results in the §"Sutra angle" section above.
