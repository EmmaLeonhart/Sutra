"""Tests for the pytorch codegen: GPU-capable backend.

String-only tests (no exec, no torch import at test time), following
the same pattern as test_codegen.py. An end-to-end run that actually
hits torch / CUDA lives in examples/_smoke_test_pytorch.py.
"""
from __future__ import annotations

import unittest

from sutra_compiler.codegen_pytorch import translate_module
from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser


def _compile(src: str) -> str:
    lexer = Lexer(src, file="<test>")
    tokens = lexer.tokenize()
    parser = Parser(tokens, file="<test>", diagnostics=lexer.diagnostics)
    module = parser.parse_module()
    assert not lexer.diagnostics.has_errors(), list(lexer.diagnostics)
    py_src = translate_module(module)
    compile(py_src, "<generated>", "exec")
    return py_src


class TestPyTorchPrelude(unittest.TestCase):
    """The emitted module picks a torch device at import and defines
    `_TorchVSA` operating on tensors. Same extended-state layout and
    canonical-axis allocation as the numpy backend."""

    def test_imports_torch_not_numpy(self):
        src = "function vector main() { return basis_vector(\"x\"); }\n"
        py = _compile(src)
        self.assertIn("import torch as _torch", py)
        # numpy only appears as a bridge inside _rotation_for and
        # make_random_rotation (for seeded Haar draws) — not at the
        # module top level. Check that the top-level imports don't
        # pull numpy in. Look at the lines before `class _TorchVSA:`.
        head = py.split("class _TorchVSA:")[0]
        self.assertNotIn("import numpy", head)
        # The _np_bridge inside _rotation_for is imported lazily inside
        # the method body — it's fine to find it in the rest of the
        # module, but not at module top-level.
        self.assertIn("import numpy as _np_bridge", py)

    def test_picks_cuda_when_available(self):
        src = "function vector main() { return basis_vector(\"x\"); }\n"
        py = _compile(src)
        self.assertIn(
            "_DEVICE = _torch.device('cuda' if _torch.cuda.is_available() else 'cpu')",
            py,
        )
        self.assertIn("_DTYPE = _torch.float32", py)

    def test_runtime_class_is_torch_vsa(self):
        src = "function vector main() { return basis_vector(\"x\"); }\n"
        py = _compile(src)
        self.assertIn("class _TorchVSA:", py)
        self.assertIn("_VSA = _TorchVSA(", py)
        self.assertIn("semantic_dim=768", py)
        self.assertIn("synthetic_dim=100", py)

    def test_cache_uses_pt_extension(self):
        src = "function vector main() { return basis_vector(\"x\"); }\n"
        py = _compile(src)
        # Torch cache uses .pt so it doesn't collide with the numpy
        # backend's .npz. Keyed by (model, total dim).
        self.assertIn("f'{_safe_model}-d{self.dim}.pt'", py)

    def test_rotation_is_block_diagonal(self):
        src = "function vector main() { return basis_vector(\"x\"); }\n"
        py = _compile(src)
        # Haar draw on semantic block (via numpy for reproducible Haar-
        # uniformity), identity fill of full dim, Q_sem in top-left.
        self.assertIn("A = rng.randn(self.semantic_dim, self.semantic_dim)", py)
        self.assertIn("Q = _torch.eye(self.dim, dtype=self.dtype, device=self.device)", py)
        self.assertIn("Q[:self.semantic_dim, :self.semantic_dim] = Q_sem", py)


class TestPyTorchFusedOps(unittest.TestCase):
    """The GPU-shaped fused primitives — bundle_of_binds as one einsum,
    argmax_cosine as one matmul — survive the inheritance from the
    CPU `Codegen` class and are emitted with torch APIs."""

    def test_bundle_of_binds_fuses_to_torch_einsum(self):
        src = (
            "vector r1 = basis_vector(\"r1\");\n"
            "vector r2 = basis_vector(\"r2\");\n"
            "vector f1 = basis_vector(\"f1\");\n"
            "vector f2 = basis_vector(\"f2\");\n"
            "function vector main() {\n"
            "  return bundle(bind(r1, f1), bind(r2, f2));\n"
            "}\n"
        )
        py = _compile(src)
        self.assertIn("_VSA.bundle_of_binds((r1, f1), (r2, f2))", py)
        self.assertIn("_torch.einsum('nij,nj->ni'", py)

    def test_argmax_cosine_is_torch_matmul(self):
        src = (
            "vector a = basis_vector(\"a\");\n"
            "vector b = basis_vector(\"b\");\n"
            "vector q = basis_vector(\"q\");\n"
            "function vector main() {\n"
            "  return argmax_cosine(q, [a, b]);\n"
            "}\n"
        )
        py = _compile(src)
        # Post Audit-REAL-LEAK-#7 fix: the zero-query-norm guard is the
        # eps-guarded tensor form `safe_qn = where(q_norm > 0, ...)`,
        # NOT the old `if float(q_norm) == 0: return candidates[0]` host
        # branch. The test's intent (argmax_cosine is a torch matmul,
        # not a host loop) is strengthened by that change.
        self.assertIn("scores = (M @ q) / (safe_rn * safe_qn)", py)
        # The zero-query guard is the eps-guarded tensor form, not a
        # host branch. (Asserting the positive tensor form rather than
        # the absence of the old `if float(q_norm)` string, because
        # that string also appears in the explanatory code comment.)
        self.assertIn(
            "safe_qn = _torch.where(q_norm > 0, q_norm, "
            "_torch.ones_like(q_norm))", py)
        self.assertIn("_torch.argmax(scores)", py)
        self.assertIn("_torch.as_tensor(c, dtype=_DTYPE, device=_DEVICE)", py)


class TestPyTorchExtendedState(unittest.TestCase):
    """Same extended-state-vector layout as the numpy backend — tensors
    are `[semantic | synthetic]`, synthetic block preserved through
    block-diagonal rotation."""

    def test_embed_appends_synthetic_zero_block(self):
        src = "function vector main() { return basis_vector(\"x\"); }\n"
        py = _compile(src)
        self.assertIn(
            "syn = _torch.zeros(self.synthetic_dim, dtype=self.dtype, device=self.device)",
            py,
        )
        self.assertIn("v = _torch.cat([v, syn])", py)

    def test_canonical_axes_defined(self):
        src = "function vector main() { return basis_vector(\"x\"); }\n"
        py = _compile(src)
        self.assertIn("AXIS_REAL = 0", py)
        self.assertIn("AXIS_IMAG = 1", py)
        self.assertIn("AXIS_TRUTH = 2", py)
        # Constructors at the torch layer write into the same axes.
        self.assertIn("def make_real(self, x):", py)
        self.assertIn("def make_complex(self, re, im):", py)
        self.assertIn("def make_truth(self, t):", py)


class TestPyTorchVectorAccessors(unittest.TestCase):
    """Vector-accessor methods (.component / .semantic / .synthetic /
    .real / .imag / .truth) lower to _VSA.<name>(v, args...) exactly
    like in the numpy backend. The emitted runtime returns Python
    floats via .item() so tensors never leak out."""

    def test_component_accessor_lowers(self):
        src = (
            "vector x = basis_vector(\"x\");\n"
            "function fuzzy main() { return x.component(0); }\n"
        )
        py = _compile(src)
        self.assertIn("_VSA.component(x, 0)", py)

    def test_real_imag_truth_accessors_defined(self):
        src = "function vector main() { return basis_vector(\"x\"); }\n"
        py = _compile(src)
        self.assertIn("def component(self, v, i):", py)
        self.assertIn("def real(self, v):", py)
        self.assertIn("def imag(self, v):", py)
        self.assertIn("def truth(self, v):", py)
        # Scalar marshalling uses .item() so Python-side consumers see
        # a float, not a tensor.
        self.assertIn("float(v[int(i)].item())", py)


if __name__ == "__main__":
    unittest.main()
