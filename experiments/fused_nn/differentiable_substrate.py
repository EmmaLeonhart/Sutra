"""Phase-2 feasibility: a substrate-pure Sutra function is a connected
differentiable graph; a host-readout (.real()) severs it.

Emma's target (2026-06-07): Sutra must compile to an ACTUAL fused neural network
/ real weight file — not a host-orchestrated approximation. The precondition is
that a compiled program be ONE connected tensor graph with no gradient walls.
Every `.item()`/`.real()` host readout detaches autograd — a gradient wall —
which is why "Sutra is a differentiable neural network" was not true while the
language had readout.

This demonstrates, with measurements:
  (1) a substrate-pure function `f(a,b) = a*b + a` (vectors throughout, zero
      `.real()`) is end-to-end differentiable: gradients flow to BOTH inputs with
      the correct chain-rule values (d/da = b+1, d/db = a);
  (2) the SAME computation routed through `.real()` (the old breach pattern)
      severs the graph — the a*b path's gradient is lost.

So removing readout is exactly what makes the compiled program a trainable
network. Ollama-free (no embeddings — pure make_real/arithmetic). Self-asserting.
"""

from __future__ import annotations

import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str((REPO / "sdk" / "sutra-compiler").resolve()))

import torch  # noqa: E402

from sutra_compiler.lexer import Lexer  # noqa: E402
from sutra_compiler.parser import Parser  # noqa: E402
from sutra_compiler.codegen_pytorch import translate_module  # noqa: E402


def _compile_fn(src: str, fn: str):
    lx = Lexer(src, file="<fused>")
    ast = Parser(lx.tokenize(), file="<fused>", diagnostics=lx.diagnostics).parse_module()
    assert not lx.diagnostics.has_errors(), list(lx.diagnostics)
    ns: dict = {}
    exec(translate_module(ast, llm_model="none", runtime_dim=4), ns)
    return ns[fn], ns["_VSA"]


def _real_axis(v, x):
    return x[v.semantic_dim + v.AXIS_REAL]


def main() -> int:
    # (1) Substrate-pure: vectors throughout, no .real().
    pure_src = (
        "function int f(int a, int b){ int p = a * b; int s = p + a; return s; }\n"
        'function string main(){ return "ok"; }'
    )
    assert ".real()" not in pure_src
    f, v = _compile_fn(pure_src, "f")
    a = v.make_real(3.0).clone().detach().requires_grad_(True)
    b = v.make_real(4.0).clone().detach().requires_grad_(True)
    out = f(a, b)
    val = float(_real_axis(v, out))
    _real_axis(v, out).backward()
    da = float(a.grad[v.semantic_dim + v.AXIS_REAL])
    db = float(b.grad[v.semantic_dim + v.AXIS_REAL])
    print(f"[pure]   f(3,4) = {val}  (want 15)")
    print(f"[pure]   d/da = {da} (want 5 = b+1),  d/db = {db} (want 3 = a)")
    ok_pure = abs(val - 15) < 1e-4 and abs(da - 5) < 1e-4 and abs(db - 3) < 1e-4

    # (2) Same computation through .real() — the host-readout breach. real()
    # returns a host float (detaches), so re-lifting via make_real starts a fresh
    # graph: the a*b contribution's gradient is severed.
    readout_src = (
        "function int g(int a, int b){ int p = make_real((a * b).real()); int s = p + a; return s; }\n"
        'function string main(){ return "ok"; }'
    )
    g, v2 = _compile_fn(readout_src, "g")
    a2 = v2.make_real(3.0).clone().detach().requires_grad_(True)
    b2 = v2.make_real(4.0).clone().detach().requires_grad_(True)
    out2 = g(a2, b2)
    _real_axis(v2, out2).backward()
    da2 = float(a2.grad[v2.semantic_dim + v2.AXIS_REAL])
    # b2 may get no grad at all (its only path was through a*b -> severed).
    db2 = float(b2.grad[v2.semantic_dim + v2.AXIS_REAL]) if b2.grad is not None else 0.0
    print(f"[readout] g(3,4) via .real():  d/da = {da2} (severed a*b path -> 1, not 5),  d/db = {db2} (want 0 -- gradient wall)")
    severed = abs(db2) < 1e-4 and abs(da2 - 1) < 1e-4  # only the +a path survives

    if not ok_pure:
        print("FAIL: substrate-pure function is not correctly differentiable")
        return 1
    if not severed:
        print("FAIL: .real() did not sever the gradient as expected")
        return 1
    print("PASS: substrate-pure Sutra function is end-to-end differentiable with "
          "correct chain-rule gradients; .real() is a gradient wall (severs autograd). "
          "Removing readout is the precondition for the fused-NN / weight-file target.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
