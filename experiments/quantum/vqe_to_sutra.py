"""Q5: VQE-to-Sutra — express + train a variational circuit on Sutra's OWN complex
substrate (eigenrotation + AXIS_REAL/AXIS_IMAG), compared to PennyLane.

The circuit (the same one `pennylane_differentiable.py` runs on `default.qubit`):
`RY(theta)|0>` then measure `<Z>`. `<Z>(theta) = cos(theta)`; minimizing it trains
the qubit toward `|1>` (`<Z> -> -1`, theta -> pi).

The Sutra-side mapping (why this is a real substrate run, not a host reimplementation):
pack the single-qubit amplitudes (alpha, beta) as ONE complex number `z = alpha +
i*beta` laid out on the substrate's `AXIS_REAL`/`AXIS_IMAG`. `|0>` is `z0 = 1 + 0i`.
`RY(theta)` rotates the amplitude 2-vector (alpha, beta) by `theta/2` — which is exactly
the substrate EIGENROTATION `cexp(i*theta/2)` acting on `z0`:
    z = cexp(i*theta/2) * z0 = cos(theta/2) + i*sin(theta/2)     (so alpha, beta)
and the observable is
    <Z> = |alpha|^2 - |beta|^2 = Re(z^2).
Every step here is a REAL `_TorchVSA` substrate op — `cexp` (the documented
eigenrotation keystone, built from the `_cos0`/`_sin0` rotation leaves), `complex_mul`
(the d-dim canonical complex product), and `_re` (dot with the real one-hot). `theta` is
a torch parameter; the whole graph is differentiable, so we train it by gradient descent
exactly as PennyLane trains `default.qubit`.

HONEST SCOPE (matches `planning/exploratory/2026-06-18-quantum-computing-and-sutra.md`):
this demonstrates that Sutra can EXPRESS and TRAIN a VQE-shaped differentiable graph on
its complex substrate, reaching the same trained parameter and expectation as PennyLane.
It is NOT a claim that Sutra is a quantum computer or that its ops are unitary — bundling
is lossy superposition, not a reversible unitary. The single-qubit `RY`/`<Z>` graph is
the toy where the "quantum circuit = constrained differentiable graph = Sutra forward
pass" parallel is directly testable. Multi-qubit entangling circuits are NOT claimed.

Run: python experiments/quantum/vqe_to_sutra.py
"""
from __future__ import annotations

import math
import pathlib
import sys
import types

_REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "sdk" / "sutra-compiler"))

import torch  # noqa: E402
from sutra_compiler.codegen_pytorch import translate_module  # noqa: E402
from sutra_compiler.lexer import Lexer  # noqa: E402
from sutra_compiler.parser import Parser  # noqa: E402


def _substrate():
    """Compile a minimal `.su` to obtain a real `_TorchVSA` substrate instance — the
    same runtime any compiled Sutra program executes on."""
    src = "function int main() { return 0; }"
    lexer = Lexer(src, file="vqe.su")
    parser = Parser(lexer.tokenize(), file="vqe.su", diagnostics=lexer.diagnostics)
    py_src = translate_module(parser.parse_module(),
                              llm_model="nomic-embed-text", runtime_dim=64)
    mod = types.ModuleType("vqe")
    exec(compile(py_src, "vqe.su", "exec"), mod.__dict__)
    return mod._VSA


def expval_Z(vsa, theta):
    """`<Z>` for `RY(theta)|0>`, computed on the substrate:
    `z = cexp(i*theta/2) * (1 + 0i)`, then `<Z> = Re(z^2)`."""
    half = theta / 2.0
    zero = torch.zeros((), dtype=vsa.dtype, device=vsa.device)
    one = torch.ones((), dtype=vsa.dtype, device=vsa.device)
    rot = vsa.cexp(vsa._mk(zero, half))          # eigenrotation e^{i*theta/2}
    z0 = vsa._mk(one, zero)                       # |0>  ->  amplitude 1 + 0i
    z = vsa.complex_mul(rot, z0)                  # alpha + i*beta
    z2 = vsa.complex_mul(z, z)
    return vsa._re(z2)                            # |alpha|^2 - |beta|^2 = cos(theta)


def main():
    vsa = _substrate()

    def th(x):
        return torch.tensor(float(x), dtype=vsa.dtype, device=vsa.device,
                            requires_grad=True)

    # 1) Value + gradient on the substrate vs the closed form.
    t = th(0.5)
    val = expval_Z(vsa, t)
    val.backward()
    val_f = float(val.detach())
    print(f"<Z>(0.5) substrate = {val_f:.6f}   (cos 0.5  = {math.cos(0.5):.6f})")
    print(f"d<Z>/dth substrate = {float(t.grad):.6f}  (-sin 0.5 = {-math.sin(0.5):.6f})")
    assert abs(val_f - math.cos(0.5)) < 5e-3, val_f
    assert abs(float(t.grad) - (-math.sin(0.5))) < 5e-2, float(t.grad)

    # 2) Train theta by gradient descent to minimize <Z> (target |1>, <Z> = -1),
    #    same schedule as the PennyLane run (start 0.1, 40 steps, stepsize 0.4).
    t = th(0.1)
    lr = 0.4
    for _ in range(40):
        loss = expval_Z(vsa, t)
        if t.grad is not None:
            t.grad = None
        loss.backward()
        with torch.no_grad():
            t -= lr * t.grad
        t.requires_grad_(True)
    final = float(expval_Z(vsa, t).detach())
    print(f"trained theta -> {float(t.detach()):.4f} (target pi = {math.pi:.4f}); "
          f"<Z> -> {final:.6f} (target -1)")
    # PennyLane reaches theta=pi, <Z>=-1; the substrate uses piecewise-linear
    # trig-table leaves, so allow table-resolution slack.
    assert abs(final + 1.0) < 1e-2, final
    assert abs(float(t.detach()) - math.pi) < 1e-1, float(t.detach())
    print("OK: Sutra substrate expressed + trained the VQE to PennyLane's fixed point "
          "(theta=pi, <Z>=-1).")


if __name__ == "__main__":
    main()
