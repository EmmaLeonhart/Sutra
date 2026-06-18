"""Differentiable quantum circuit + gradient training (queue: quantum exploration, Q2).

This is the Sutra-relevant angle Emma flagged: a parameterized quantum circuit is a
DIFFERENTIABLE program — its measured expectation value has an exact analytic gradient
w.r.t. the circuit parameters, so you can train it by gradient descent. That is the
variational / VQE paradigm, and it is structurally the same move Sutra makes: a forward
pass over a tensor graph that is differentiable end-to-end.

Measured 2026-06-18 (PennyLane 0.45.0, default.qubit):
  - <Z>(theta) = cos(theta), exact.
  - d<Z>/dtheta = -sin(theta), exact (parameter-shift / autograd).
  - Gradient descent from theta=0.1 converges to theta=pi (<Z> -> -1, i.e. |1>).

Run: python experiments/quantum/pennylane_differentiable.py
"""
from __future__ import annotations

import math

import pennylane as qml
from pennylane import numpy as np

dev = qml.device("default.qubit", wires=1)


@qml.qnode(dev)
def circuit(theta):
    """RY(theta) then measure <Z>.  <Z> = cos(theta)."""
    qml.RY(theta, wires=0)
    return qml.expval(qml.PauliZ(0))


def main():
    # 1) Value + analytic gradient match the closed form.
    th = np.array(0.5, requires_grad=True)
    val = float(circuit(th))
    grad = float(qml.grad(circuit)(th))
    print(f"<Z>(0.5)      = {val:.6f}   (cos 0.5  = {math.cos(0.5):.6f})")
    print(f"d<Z>/dth(0.5) = {grad:.6f}  (-sin 0.5 = {-math.sin(0.5):.6f})")
    assert abs(val - math.cos(0.5)) < 1e-5
    assert abs(grad - (-math.sin(0.5))) < 1e-5

    # 2) Train the parameter by gradient descent to minimize <Z> (target |1>, <Z>=-1).
    opt = qml.GradientDescentOptimizer(stepsize=0.4)
    t = np.array(0.1, requires_grad=True)
    for _ in range(40):
        t = opt.step(circuit, t)
    print(f"trained theta -> {float(t):.4f} (target pi = {math.pi:.4f}); "
          f"<Z> -> {float(circuit(t)):.6f} (target -1)")
    assert abs(float(circuit(t)) + 1.0) < 1e-3


if __name__ == "__main__":
    main()
