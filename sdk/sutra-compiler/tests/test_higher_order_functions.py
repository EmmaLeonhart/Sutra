"""Higher-order functions over a collection, ON THE SUBSTRATE — the payoff of
first-class function values (named + arrow) composed with `foreach`.

Guards `examples/higher_order_functions.su`: one `reduce` folds an array of
number-vectors with whatever binary function is passed in. The result is a
SUBSTRATE vector (not a host scalar) — verified by checking the return is a torch
tensor and decoding it off the real axis vs ground truth. The `vector`/`make_real`
typing is deliberate: an `int` version would fold on the host (Python arithmetic),
not the substrate (see the example's note + DEVLOG 2026-06-20).
"""
from __future__ import annotations

import pathlib
import types

import pytest

torch = pytest.importorskip("torch")

from sutra_compiler.codegen_pytorch import translate_module  # noqa: E402
from sutra_compiler.lexer import Lexer  # noqa: E402
from sutra_compiler.parser import Parser  # noqa: E402

_SRC = (pathlib.Path(__file__).resolve().parents[3]
        / "examples" / "higher_order_functions.su").read_text(encoding="utf-8")


def _module():
    lx = Lexer(_SRC, file="hof")
    ps = Parser(lx.tokenize(), file="hof", diagnostics=lx.diagnostics)
    module = ps.parse_module()
    assert not lx.diagnostics.has_errors(), [str(d) for d in lx.diagnostics]
    py = translate_module(module, runtime_dim=64)
    m = types.ModuleType("hof")
    exec(compile(py, "hof", "exec"), m.__dict__)
    return m


def _decode(m, fn) -> float:
    r = getattr(m, fn)()
    # The result MUST be a substrate vector (tensor), not a host scalar — that is
    # the whole point (an int fold would compute on the host).
    assert hasattr(r, "shape"), f"{fn} returned a host {type(r).__name__}, not a substrate vector"
    return float(torch.dot(r, m._VSA.make_real(1.0)))


def test_fold_named_function_on_substrate():
    m = _module()
    assert _decode(m, "total") == pytest.approx(6.0, abs=2e-2)  # vadd over 1,2,3


def test_fold_inline_arrow_on_substrate():
    m = _module()
    # reduce((a, b) => a + b + b, 0) over [1,2,3] = 2*(1+2+3) = 12
    assert _decode(m, "total_dbl") == pytest.approx(12.0, abs=3e-2)


def test_main_runs_on_substrate():
    m = _module()
    assert _decode(m, "main") == pytest.approx(6.0, abs=2e-2)
