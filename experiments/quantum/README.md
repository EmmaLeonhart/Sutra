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

Run any script directly: `python experiments/quantum/<name>.py`.
