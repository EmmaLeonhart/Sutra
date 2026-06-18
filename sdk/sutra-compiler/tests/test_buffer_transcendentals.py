"""Elementwise-buffer transcendentals: `sin_buf` / `cos_buf`.

The scalar `Math.sin`/`Math.cos` act on the canonical d-dim complex NUMBER (one
angle in, one number out) and raise a dim-mismatch when applied to a length-N
activation buffer — see `planning/findings/2026-06-17-substrate-transcendentals-
canonical-only.md`. `sin_buf`/`cos_buf` (Emma 2026-06-17 "Make the compiler
primitive") are the buffer counterparts: the SAME substrate-pure table readout
the scalar trig uses (wrap to (-π,π] then a triangular soft-index crosstalk
matmul against the cached sin/cos table), BROADCAST over the N elements.

These tests confirm the primitive (a) compiles + runs through the PyTorch
backend, (b) matches `math.sin`/`math.cos` elementwise within the float32 +
N=4096 trig-table precision INCLUDING arguments far outside [-π, π] (3.0, 10.0,
25.0 — the high-frequency Fourier-band range a polynomial encoding could not
cover, the whole reason a table-readout primitive was needed), and (c) is
end-to-end differentiable on the substrate (d/dx sin = cos) — the property that
unblocks SIREN-style sin-activations.
"""
from __future__ import annotations

import math
import unittest

from sutra_compiler.codegen_pytorch import translate_module as torch_translate
from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser

# Includes deliberately out-of-[-π, π] values: the periodic table readout must
# stay accurate there (a polynomial sin/cos diverges — the blocked path).
_VALS = [0.5, 3.0, 10.0, 25.0, -2.0, -7.0]
_TOL = 1e-3  # float32 + N=4096 trig-table precision (matches test_transcendentals)


def _compile_run(fn_name: str, src: str):
    lexer = Lexer(src, file="<test>")
    tokens = lexer.tokenize()
    parser = Parser(tokens, file="<test>", diagnostics=lexer.diagnostics)
    module = parser.parse_module()
    assert not lexer.diagnostics.has_errors(), list(lexer.diagnostics)
    ns: dict = {}
    exec(torch_translate(module), ns)
    return ns, ns[fn_name]()


def _literal(vals):
    return "vector_literal(" + ", ".join(f"{v}" for v in vals) + ")"


class TestBufferTranscendentals(unittest.TestCase):
    def test_sin_buf_matches_math_sin_elementwise(self):
        _ns, out = _compile_run("f", f"function vector f() {{ return sin_buf({_literal(_VALS)}); }}\n")
        got = [float(out[i]) for i in range(len(_VALS))]
        for v, g in zip(_VALS, got):
            self.assertAlmostEqual(g, math.sin(v), delta=_TOL,
                                   msg=f"sin_buf({v}) = {g}, want {math.sin(v)}")

    def test_cos_buf_matches_math_cos_elementwise(self):
        _ns, out = _compile_run("g", f"function vector g() {{ return cos_buf({_literal(_VALS)}); }}\n")
        got = [float(out[i]) for i in range(len(_VALS))]
        for v, g in zip(_VALS, got):
            self.assertAlmostEqual(g, math.cos(v), delta=_TOL,
                                   msg=f"cos_buf({v}) = {g}, want {math.cos(v)}")

    def test_sin_buf_is_accurate_far_outside_principal_range(self):
        """The reason this primitive exists rather than a polynomial encoding: it
        stays accurate for the high-frequency Fourier-band argument range."""
        big = [12.5, 31.4, -47.1, 100.0]
        _ns, out = _compile_run("h", f"function vector h() {{ return sin_buf({_literal(big)}); }}\n")
        for i, v in enumerate(big):
            self.assertAlmostEqual(float(out[i]), math.sin(v), delta=_TOL,
                                   msg=f"sin_buf diverged at {v}")

    def test_preserves_buffer_length(self):
        _ns, out = _compile_run("f", f"function vector f() {{ return sin_buf({_literal(_VALS)}); }}\n")
        self.assertEqual(int(out.shape[0]), len(_VALS))

    def test_sin_buf_is_differentiable_on_the_substrate(self):
        """Autograd flows through the table readout: d/dx sin_buf = cos_buf,
        the property that makes SIREN-style sin-activations trainable."""
        import torch
        ns, _ = _compile_run("f", f"function vector f() {{ return sin_buf({_literal(_VALS)}); }}\n")
        vsa = ns["_VSA"]
        x = torch.tensor(_VALS, dtype=vsa.dtype, device=vsa.device, requires_grad=True)
        y = vsa.sin_buf(x)
        self.assertTrue(y.requires_grad, "sin_buf detached the autograd graph")
        y.sum().backward()
        for i, v in enumerate(_VALS):
            self.assertAlmostEqual(float(x.grad[i]), math.cos(v), delta=5e-3,
                                   msg=f"d/dx sin_buf({v}) = {float(x.grad[i])}, want cos = {math.cos(v)}")


if __name__ == "__main__":
    unittest.main()
