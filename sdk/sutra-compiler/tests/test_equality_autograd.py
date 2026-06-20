"""The equality surface stays ON the autograd graph (Audit.md REAL LEAK #9, #11).

`eq`, `eq_synthetic`, and `js_strict_eq` all write a truth value derived from the
inputs. The leak both #9 and #11 had was computing that truth via a host readout
(`float(cos.item())` / `float(torch.linalg.norm(...))`) and a host transcendental,
which detaches autograd and severs the gradient chain when `==` / `===` is composed
inside a trainable surface. The fix keeps the value as a 0-d tensor and scatters it
onto the truth axis. These tests pin that the methods produce ON-GRAPH output and
that a gradient flows back to the inputs, so a future regression to a host readout is
caught here (the static `.item()` counter in test_no_host_readout.py does not catch a
`float(...)` readout).
"""
from __future__ import annotations

import types

import pytest

torch = pytest.importorskip("torch")

from sutra_compiler.codegen_pytorch import translate_module  # noqa: E402
from sutra_compiler.lexer import Lexer  # noqa: E402
from sutra_compiler.parser import Parser  # noqa: E402


def _vsa(runtime_dim: int = 16):
    src = "function int main() { return 0; }"
    lx = Lexer(src, file="t.su")
    ps = Parser(lx.tokenize(), file="t.su", diagnostics=lx.diagnostics)
    py = translate_module(ps.parse_module(), llm_model="none", runtime_dim=runtime_dim)
    m = types.ModuleType("t")
    exec(compile(py, "t.su", "exec"), m.__dict__)
    return m._VSA


def _truth(v, out):
    return float(out[v.semantic_dim + v.AXIS_TRUTH].detach())


@pytest.mark.parametrize("method", ["eq", "eq_synthetic", "js_strict_eq"])
def test_equality_output_is_on_graph(method):
    v = _vsa()
    a = v.make_real(5.0).clone().requires_grad_(True)
    b = v.make_real(5.0).clone().requires_grad_(True)
    out = getattr(v, method)(a, b)
    assert torch.is_tensor(out)
    assert out.grad_fn is not None, f"{method} output is detached (host-readout leak)"


@pytest.mark.parametrize("method", ["eq", "eq_synthetic", "js_strict_eq"])
def test_equality_gradient_flows_to_inputs(method):
    v = _vsa()
    # A small, non-saturated difference so the gradient is non-zero.
    a = v.make_real(5.00).clone().requires_grad_(True)
    b = v.make_real(5.02).clone().requires_grad_(True)
    out = getattr(v, method)(a, b)
    out[v.semantic_dim + v.AXIS_TRUTH].backward()
    assert a.grad is not None and bool((a.grad != 0).any()), \
        f"{method}: no gradient flows to inputs (autograd severed)"


def test_js_strict_eq_correctness_preserved():
    v = _vsa()
    eq = v.js_strict_eq(v.make_real(5.0), v.make_real(5.0))
    ne = v.js_strict_eq(v.make_real(5.0), v.make_real(6.0))
    assert _truth(v, eq) > 0.9    # 5 === 5  -> ~ +1
    assert _truth(v, ne) < -0.9   # 5 === 6  -> ~ -1
