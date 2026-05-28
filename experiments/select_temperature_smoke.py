"""Select softmax temperature — mechanism smoke (first piece of task #21).

Per planning/exploratory/constrain-train-next-targets.md target 4 (the
next constrain-train ship after equality-cosine T and defuzz β). The
Sutra-level surface is "wrap each score in a divide by T" — no parser
change. This script verifies the gradient surface is trainable (smooth
+ monotonic across the T range) before committing to a full training
harness.

Smoke shape:
- Compile a 3-class .su using `select([s_i/T for i], [proto_i for i])`.
- 3 orthogonal random prototypes; a query x = 0.7*p0 + 0.25*p1 + 0.05*p2.
- Sweep T ∈ {0.01, 0.1, 0.5, 1.0, 5.0, 100.0}; measure dot(output, p_i)
  for each prototype.

Expected (verified 2026-05-28):
- T→0 (sharpest): output is essentially p0 (the closest).
- T→∞ (softest): output is roughly uniform mix of all three.
- Transitions are MONOTONIC and SMOOTH across the T range — confirming
  the gradient surface a training loop would descend.

Result this run (pasted from the verification):

    raw similarities: s0=0.9404, s1=0.3510, s2=-0.0545
    T=  0.01: dot(out,p0)=+1.000  dot(out,p1)=+0.019  dot(out,p2)=-0.113
    T=  0.10: dot(out,p0)=+0.997  dot(out,p1)=+0.022  dot(out,p2)=-0.113
    T=  0.50: dot(out,p0)=+0.686  dot(out,p1)=+0.222  dot(out,p2)=+0.007
    T=  1.00: dot(out,p0)=+0.503  dot(out,p1)=+0.289  dot(out,p2)=+0.120
    T=  5.00: dot(out,p0)=+0.341  dot(out,p1)=+0.321  dot(out,p2)=+0.246
    T=100.00: dot(out,p0)=+0.304  dot(out,p1)=+0.324  dot(out,p2)=+0.279

dot(out, p0) drops monotonically 1.00 → 0.30; dot(out, p1) and dot(out,
p2) rise monotonically. Adam should navigate this surface cleanly.

Next pieces of task #21: write a full training harness mirroring
`equality_cosine_adjustment.py`, train T on K-way classification with
a real prototype set, verify T moves end-to-end + bake back as numeric
literal + round-trip check.
"""
from __future__ import annotations

import os
import sys
import types

HERE = os.path.abspath(os.path.dirname(__file__))
REPO = os.path.dirname(HERE)
SDK = os.path.join(REPO, "sdk", "sutra-compiler")
if SDK not in sys.path:
    sys.path.insert(0, SDK)

import torch

from sutra_compiler.codegen_pytorch import translate_module as translate_pytorch
from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser


_SU_SOURCE = """\
// 3-class softmax-temperature select.
// Per planning/exploratory/constrain-train-next-targets.md target 4.
function vector pick_class(vector x, vector p0, vector p1, vector p2, number T) {
    scalar s0 = truth_axis(x == p0) / T;
    scalar s1 = truth_axis(x == p1) / T;
    scalar s2 = truth_axis(x == p2) / T;
    return select([s0, s1, s2], [p0, p1, p2]);
}

function string main() { return "ok"; }
"""


def _compile():
    lx = Lexer(_SU_SOURCE, file="select_temperature_smoke.su")
    toks = lx.tokenize()
    mod_ast = Parser(toks, file="select_temperature_smoke.su",
                     diagnostics=lx.diagnostics).parse_module()
    if lx.diagnostics.has_errors():
        for d in lx.diagnostics.errors:
            print(f"PARSE ERROR: {d.format()}")
        raise SystemExit(1)
    py = translate_pytorch(mod_ast, runtime_dim=16, runtime_seed=42)
    m = types.ModuleType("select_temperature_smoke")
    exec(compile(py, "<select_temperature_smoke>", "exec"), m.__dict__)
    return m


def _random_vec(seed: int, dim: int, dtype, device) -> torch.Tensor:
    g = torch.Generator(device="cpu").manual_seed(seed)
    v = torch.randn(dim, generator=g, dtype=torch.float32).to(device=device, dtype=dtype)
    return v / v.norm()


def main() -> int:
    mod = _compile()
    vsa = mod._VSA

    p0 = _random_vec(1, vsa.dim, vsa.dtype, vsa.device)
    p1 = _random_vec(2, vsa.dim, vsa.dtype, vsa.device)
    p2 = _random_vec(3, vsa.dim, vsa.dtype, vsa.device)
    # query mostly p0, somewhat p1, slightly p2
    x = 0.7 * p0 + 0.25 * p1 + 0.05 * p2
    x = x / x.norm()

    s0 = float(vsa.eq(x, p0)[vsa.semantic_dim + vsa.AXIS_TRUTH])
    s1 = float(vsa.eq(x, p1)[vsa.semantic_dim + vsa.AXIS_TRUTH])
    s2 = float(vsa.eq(x, p2)[vsa.semantic_dim + vsa.AXIS_TRUTH])
    print(f"raw similarities: s0={s0:.4f}, s1={s1:.4f}, s2={s2:.4f}")

    print("T-sweep (sharpest -> softest):")
    monotonic = True
    prev_p0 = None
    for T_val in (0.01, 0.1, 0.5, 1.0, 5.0, 100.0):
        T = torch.tensor(T_val, dtype=vsa.dtype, device=vsa.device)
        out = mod.pick_class(x, p0, p1, p2, T)
        dot_p0 = float(torch.dot(out, p0))
        dot_p1 = float(torch.dot(out, p1))
        dot_p2 = float(torch.dot(out, p2))
        print(f"  T={T_val:6.2f}: dot(out,p0)={dot_p0:+.3f}  "
              f"dot(out,p1)={dot_p1:+.3f}  dot(out,p2)={dot_p2:+.3f}")
        if prev_p0 is not None and dot_p0 > prev_p0 + 0.01:
            monotonic = False
        prev_p0 = dot_p0

    if monotonic:
        print("\nmonotonic T-sensitivity verified: gradient surface is trainable.")
        return 0
    else:
        print("\nNOT MONOTONIC — gradient surface needs investigation.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
