"""Regression guard for the first trainable MATRIX through the compiled
Sutra graph (experiments/trainable_matrix_adjustment.py).

A `matrix`-typed parameter flows through the compiled program

    function vector apply(matrix M, vector x) { return Tensor.MatrixMul(M, x); }

`Tensor.MatrixMul` lowers to `_VSA.matmul` == `torch.matmul`, so the
forward runs on the substrate. M is a leaf tensor with requires_grad;
gradient descent must reach it through the compiled matmul, and the
trained matrix must bake back into a `matrix_literal(...)` .su.

These are fast (K=4, MSE, few epochs) deterministic checks -- the full
multi-seed CE-vs-MSE measurement lives in the experiment.
"""
from __future__ import annotations

import unittest

import torch
import torch.nn.functional as F

from sutra_compiler.codegen_pytorch import translate_module as torch_translate
from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser


APPLY_SU = (
    "function vector apply(matrix M, vector x) {\n"
    "    return Tensor.MatrixMul(M, x);\n"
    "}\n"
    'function string main() { return "ok"; }\n'
)


def _compile(src: str, runtime_dim: int):
    lx = Lexer(src, file="<test>")
    toks = lx.tokenize()
    ast = Parser(toks, file="<test>", diagnostics=lx.diagnostics).parse_module()
    assert not lx.diagnostics.has_errors(), list(lx.diagnostics)
    py = torch_translate(ast, runtime_dim=runtime_dim, runtime_seed=42)
    ns: dict = {}
    exec(py, ns)
    return ns, py


class TestTrainableMatrix(unittest.TestCase):
    def setUp(self):
        self.K = 4
        self.ns, self.py = _compile(APPLY_SU, runtime_dim=self.K)
        self.vsa = self.ns["_VSA"]
        self.dtype = self.vsa.dtype
        self.device = self.vsa.device
        self.es = [torch.eye(self.K, dtype=self.dtype, device=self.device)[i]
                   for i in range(self.K)]

    def test_matmul_runs_on_substrate(self):
        # The op the program runs IS torch.matmul, not a host shim.
        self.assertIn("_torch.matmul", self.py)

    def test_matrix_param_autograd_reaches_M(self):
        # A matrix parameter through the compiled matmul must receive grad.
        M = torch.randn(self.K, self.K, dtype=self.dtype, device=self.device,
                        requires_grad=True)
        y = self.ns["apply"](M, self.es[0])
        self.assertTrue(y.requires_grad)
        y.sum().backward()
        self.assertIsNotNone(M.grad)
        self.assertGreater(float(M.grad.norm()), 0.0)

    def test_mse_trains_M_to_target_permutation(self):
        # Init at cyclic shift-by-1; train (MSE) to shift-by-2.
        K = self.K
        init = torch.zeros(K, K, dtype=self.dtype, device=self.device)
        for i in range(K):
            init[(i + 1) % K, i] = 1.0
        perm = [(i + 2) % K for i in range(K)]
        target = torch.zeros(K, K, dtype=self.dtype, device=self.device)
        for i in range(K):
            target[perm[i], i] = 1.0
        target_onehots = torch.stack([self.es[perm[i]] for i in range(K)])

        M = init.clone().detach().requires_grad_(True)
        opt = torch.optim.Adam([M], lr=0.05)
        fro_before = float((M.detach() - target).norm())
        for _ in range(300):
            opt.zero_grad()
            outs = torch.stack([self.ns["apply"](M, e) for e in self.es])
            loss = F.mse_loss(outs, target_onehots)
            loss.backward()
            opt.step()
        fro_after = float((M.detach() - target).norm())

        # Learned the permutation exactly + converged to the canonical matrix.
        self.assertLess(fro_after, fro_before)
        self.assertLess(fro_after, 0.05)
        for i, e in enumerate(self.es):
            with torch.no_grad():
                self.assertEqual(int(self.ns["apply"](M, e).argmax()), perm[i])

    def test_ce_plus_ortho_pulls_frobenius_down_not_up(self):
        # Plain CE learns the permutation FUNCTION but lets entries grow
        # unboundedly (Frobenius to the canonical 0/1 matrix RISES above the
        # start). A soft orthogonality penalty ||MᵀM − I||² keeps M bounded
        # on the orthogonal manifold: the function stays exact (argmax) AND
        # Frobenius FALLS below the start (the discriminating claim vs plain
        # CE). It reaches the EXACT canonical matrix for a nearby target
        # (K=8 shift3 -> ~0.01) but, for a distant target, an orthogonal
        # matrix in the correct argmax class (Frobenius down, not to 0) --
        # so we assert the fall + exact function, not near-zero.
        # (Experiment: trainable_matrix_adjustment.py --loss ce --ortho.)
        K = self.K
        init = torch.zeros(K, K, dtype=self.dtype, device=self.device)
        for i in range(K):
            init[(i + 1) % K, i] = 1.0
        perm = [(i + 2) % K for i in range(K)]
        target = torch.zeros(K, K, dtype=self.dtype, device=self.device)
        for i in range(K):
            target[perm[i], i] = 1.0
        y_idx = torch.tensor(perm, device=self.device)
        eye = torch.eye(K, dtype=self.dtype, device=self.device)

        M = init.clone().detach().requires_grad_(True)
        opt = torch.optim.Adam([M], lr=0.05)
        fro_before = float((M.detach() - target).norm())
        for _ in range(400):
            opt.zero_grad()
            outs = torch.stack([self.ns["apply"](M, e) for e in self.es])
            loss = F.cross_entropy(outs * 5.0, y_idx)
            loss = loss + ((M.t() @ M - eye) ** 2).sum()  # ortho penalty
            loss.backward()
            opt.step()
        fro_after = float((M.detach() - target).norm())

        self.assertLess(fro_after, fro_before)  # ortho pulls it DOWN
        for i, e in enumerate(self.es):          # function still exact
            with torch.no_grad():
                self.assertEqual(int(self.ns["apply"](M, e).argmax()), perm[i])

    def test_trained_matrix_bakes_back_to_matrix_literal(self):
        # A trained matrix re-expressed as a matrix_literal .su reproduces
        # the same transform (weight -> legible Sutra source).
        K = self.K
        M = torch.randn(K, K, dtype=self.dtype, device=self.device)
        rows = ",\n".join(
            "vector_literal(" + ", ".join(f"{v:.8f}" for v in r.tolist()) + ")"
            for r in M
        )
        baked_su = (
            "function vector apply_baked(vector x) {\n"
            f"    matrix M = matrix_literal(\n{rows});\n"
            "    return Tensor.MatrixMul(M, x);\n"
            "}\n"
            'function string main() { return "ok"; }\n'
        )
        bns, _ = _compile(baked_su, runtime_dim=K)
        for e in self.es:
            a = self.ns["apply"](M, e)
            b = bns["apply_baked"](e)
            self.assertLess(float((a - b).abs().max()), 1e-4)


if __name__ == "__main__":
    unittest.main()
