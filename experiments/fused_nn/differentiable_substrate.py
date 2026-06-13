"""Phase-2 feasibility: a substrate-pure Sutra function is a connected
differentiable graph.

Emma's target (2026-06-07): Sutra must compile to an ACTUAL fused neural network
/ real weight file — not a host-orchestrated approximation. The precondition is
that a compiled program be ONE connected tensor graph with no gradient walls.
Every `.item()`/`.real()` host readout detaches autograd — a gradient wall —
which is why "Sutra is a differentiable neural network" was not true while the
language had readout.

This demonstrates, with measurements, that a substrate-pure function
`f(a,b) = a*b + a` (vectors throughout, zero `.real()`) is end-to-end
differentiable: gradients flow to BOTH inputs with the correct chain-rule values
(d/da = b+1, d/db = a). So removing readout is exactly what makes the compiled
program a trainable network. Ollama-free (no embeddings — pure
make_real/arithmetic). Self-asserting.

Note (2026-06-13): the original demo had a second leg routing the same
computation through `.real()` to show it severs autograd. `.real()` was removed
from the language entirely in the no-introspection purge (it now raises
`CodegenNotSupported` at compile time — the breach is prevented structurally, not
just observable at runtime), so that leg can no longer compile and was dropped
(Emma's call). The structural prevention is asserted directly by
`tests/test_no_readout_accessors` / the codegen `_REMOVED_SCALAR_ACCESSORS` gate.
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

    if not ok_pure:
        print("FAIL: substrate-pure function is not correctly differentiable")
        return 1
    print("PASS: substrate-pure Sutra function is end-to-end differentiable with "
          "correct chain-rule gradients (d/da = b+1, d/db = a). Removing readout "
          "is the precondition for the fused-NN / weight-file target; `.real()` is "
          "now a compile-time error, so the gradient wall cannot be reintroduced.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
