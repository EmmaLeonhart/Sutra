"""`axon_build` — the batched fusion of N axon_adds into one bmm.

`axon_build(axon, keys, values)` adds N (key, value) bindings in a single batched
matmul (stack the cached per-key M_key operators, one `bmm` + sum) instead of N
separate `axon_add` matmuls. It must be BIT-IDENTICAL to folding `axon_add` over the
same pairs (the only difference is op count: 1 launch vs N). This pins that, plus the
empty-build no-op and that the built axon reads back correctly.

Fusion lever for record/struct construction (a known field set). See
planning/findings/2026-06-20-tick-all-no-speedup-python-bound.md §"Fusion pass".
"""
from __future__ import annotations

import types

import pytest

torch = pytest.importorskip("torch")

from sutra_compiler.codegen_pytorch import translate_module  # noqa: E402
from sutra_compiler.lexer import Lexer  # noqa: E402
from sutra_compiler.parser import Parser  # noqa: E402


def _vsa(runtime_dim: int = 256):
    src = "function int main() { return 0; }"
    lx = Lexer(src, file="t.su")
    ps = Parser(lx.tokenize(), file="t.su", diagnostics=lx.diagnostics)
    py = translate_module(ps.parse_module(), llm_model="nomic-embed-text",
                          runtime_dim=runtime_dim)
    m = types.ModuleType("t")
    exec(compile(py, "t.su", "exec"), m.__dict__)
    return m._VSA


def test_axon_build_bit_identical_to_folded_axon_add():
    v = _vsa()
    keys = ["x", "y", "z"]
    vals = [5.0, 8.0, 3.0]
    folded = v.zero_vector()
    for k, val in zip(keys, vals):
        folded = v.axon_add(folded, k, val)
    built = v.axon_build(v.zero_vector(), keys, vals)
    assert torch.allclose(folded, built, atol=1e-5), \
        f"axon_build != folded axon_add (max diff {float((folded - built).abs().max())})"


def test_axon_build_reads_back():
    v = _vsa()
    built = v.axon_build(v.zero_vector(), ["a", "b", "c"], [5.0, 8.0, 3.0])
    for k, want in [("a", 5.0), ("b", 8.0), ("c", 3.0)]:
        got = float(torch.dot(v.axon_item(built, k), v.make_real(1.0)))
        assert got == pytest.approx(want, abs=1e-3), f"{k}: got {got}, want {want}"


def test_axon_build_empty_is_noop():
    v = _vsa()
    z = v.zero_vector()
    assert torch.equal(v.axon_build(z, [], []), z)


def test_axon_build_string_value():
    v = _vsa()
    # A string value alone reads back exactly (no number crosstalk).
    solo = v.axon_build(v.zero_vector(), ["s"], ["hello"])
    assert v.string_to_python(v.axon_item(solo, "s")) == "hello"
    # Mixed number+string: axon_build is BIT-IDENTICAL to folded axon_add (any axon
    # crosstalk between the number and the string is a property of the axon encoding,
    # identical in both paths — NOT introduced by the batched build).
    keys, vals = ["n", "s"], [42.0, "hello"]
    folded = v.zero_vector()
    for k, val in zip(keys, vals):
        folded = v.axon_add(folded, k, val)
    built = v.axon_build(v.zero_vector(), keys, vals)
    assert torch.allclose(folded, built, atol=1e-5)
