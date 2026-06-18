"""Quantum-emulator accessibility sweep (queue: quantum-computing exploration, Q1).

Runs the same Bell state (the canonical entanglement + measurement check) on every
Python quantum emulator that is installable on this machine (Py 3.13 / Windows), so
we know which substrates are actually accessible for the deeper Sutra-angle work.

Measured 2026-06-18 — all three install cleanly via pip and produce a correct Bell
distribution (~50% |00>, ~50% |11>, ~0% |01>/|10>):
  PennyLane 0.45.0  Qiskit 2.4.2 (+ qiskit-aer)  Cirq 1.6.1

Run: python experiments/quantum/emulator_sweep.py
"""
from __future__ import annotations


def pennylane_bell():
    import pennylane as qml
    dev = qml.device("default.qubit", wires=2)

    @qml.qnode(dev)
    def bell():
        qml.Hadamard(wires=0)
        qml.CNOT(wires=[0, 1])
        return qml.probs(wires=[0, 1])

    p = [round(float(x), 3) for x in bell()]
    return {"|00>": p[0], "|01>": p[1], "|10>": p[2], "|11>": p[3]}


def qiskit_bell(shots: int = 2000):
    from qiskit import QuantumCircuit
    from qiskit_aer import AerSimulator
    qc = QuantumCircuit(2, 2)
    qc.h(0)
    qc.cx(0, 1)
    qc.measure([0, 1], [0, 1])
    return dict(AerSimulator().run(qc, shots=shots).result().get_counts())


def cirq_bell(shots: int = 2000):
    import cirq
    q0, q1 = cirq.LineQubit.range(2)
    circ = cirq.Circuit([cirq.H(q0), cirq.CNOT(q0, q1),
                         cirq.measure(q0, q1, key="m")])
    hist = cirq.Simulator().run(circ, repetitions=shots).histogram(key="m")
    # key 0 == |00>, key 3 == |11>
    return {"|00>": hist.get(0, 0), "|11>": hist.get(3, 0),
            "|01>": hist.get(1, 0), "|10>": hist.get(2, 0)}


def main():
    for name, fn in [("PennyLane", pennylane_bell),
                     ("Qiskit (Aer)", qiskit_bell),
                     ("Cirq", cirq_bell)]:
        try:
            print(f"{name:14} Bell:", fn())
        except Exception as e:  # noqa: BLE001 — report accessibility, don't crash the sweep
            print(f"{name:14} NOT ACCESSIBLE: {e!r}")


if __name__ == "__main__":
    main()
