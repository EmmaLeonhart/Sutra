# Quantum-computing exploration

Serious-but-exploratory hands-on with quantum emulators and the Sutra angle
(differentiable circuits / VQE). Started 2026-06-18 from Emma's queue braindump.

The conceptual writeup (FP↔quantum, the Sutra parallel, scope limits) lives in
`planning/exploratory/2026-06-18-quantum-computing-and-sutra.md`. This directory holds
the runnable code.

## Install (Py 3.13 / Windows, all pip-installable)

```
python -m pip install pennylane qiskit qiskit-aer cirq
```

Verified versions: PennyLane 0.45.0, Qiskit 2.4.2, Cirq 1.6.1.

## Scripts

- `emulator_sweep.py` — runs the same Bell state on PennyLane, Qiskit (Aer), and Cirq;
  the accessibility check. All three give a correct ~50/50 |00⟩/|11⟩ distribution.
- `pennylane_differentiable.py` — the Sutra-relevant part: a parameterized circuit whose
  expectation `<Z>(θ)=cos θ` has an exact analytic gradient `-sin θ`, trained by gradient
  descent (θ→π, `<Z>`→−1). The variational/VQE paradigm = Sutra's differentiable forward
  pass, on a unitarity-constrained graph.
- `vqe_to_sutra.py` (Q5, the genuinely novel test) — expresses + trains the SAME
  `RY(θ)|0>`/`<Z>` circuit on Sutra's OWN complex substrate (amplitudes packed on
  `AXIS_REAL`/`AXIS_IMAG`; `RY` = the substrate eigenrotation `cexp(i·θ/2)`; `<Z> = Re(z²)`
  via `complex_mul`). Trains to PennyLane's fixed point (θ→π, `<Z>`→−1; value/gradient match
  the closed form to ~1e-4 / ~1e-6). Scope: Sutra can express+train a VQE-shaped graph — NOT
  a claim it is a quantum computer or that its ops are unitary; single-qubit toy only.

Run any script directly: `python experiments/quantum/<name>.py`.
