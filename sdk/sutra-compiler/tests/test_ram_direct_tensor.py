"""Direct-RAM rework regression guard (finding 2026-06-19-ram-device-scaling-limit).

The lazily-allocated RAM (no external orchestrator: Bytes.make / OCaml arrays / the
attn number-tape) is a DIRECT 1D torch tensor of real-axis scalars, not a Python
list of d-vectors. This scales to a large linear memory (one scalar per cell, grown
by doubling) instead of pre-growing a list of per-cell d-vectors. The EXTERNAL
orchestrator-attached path (iso5 / ntm_ram attach + index `self.ram` as a list of
vectors) is unchanged. These tests pin both paths.
"""
from __future__ import annotations

import types

import pytest

torch = pytest.importorskip("torch")

from sutra_compiler.codegen_pytorch import translate_module  # noqa: E402
from sutra_compiler.lexer import Lexer  # noqa: E402
from sutra_compiler.parser import Parser  # noqa: E402


def _vsa(runtime_dim: int = 8):
    src = "function int main() { return 0; }"
    lx = Lexer(src, file="t.su")
    ps = Parser(lx.tokenize(), file="t.su", diagnostics=lx.diagnostics)
    py = translate_module(ps.parse_module(), llm_model="none", runtime_dim=runtime_dim)
    m = types.ModuleType("t")
    exec(compile(py, "t.su", "exec"), m.__dict__)
    return m._VSA


def test_lazy_ram_is_a_direct_tensor_not_a_list():
    v = _vsa()
    v.ram_write(2.0, 77.0)
    assert torch.is_tensor(v.ram), type(v.ram)
    assert not isinstance(v.ram, list)


def test_lazy_ram_scalar_roundtrip_and_unwritten_zero():
    v = _vsa()
    v.ram_write(2.0, 77.0)
    v.ram_write(0.0, 10.0)
    assert abs(float(v._re(v.ram_read(2.0))) - 77.0) < 1e-4
    assert abs(float(v._re(v.ram_read(0.0))) - 10.0) < 1e-4
    assert abs(float(v._re(v.ram_read(3.0)))) < 1e-4          # unwritten reads zero


def test_lazy_ram_scales_to_high_address_without_oom():
    v = _vsa()
    v.ram_write(5_000_000.0, 42.0)
    assert torch.is_tensor(v.ram)
    assert v.ram.ndim == 1 and v.ram.shape[0] >= 5_000_001   # 1D scalar memory
    assert abs(float(v._re(v.ram_read(5_000_000.0))) - 42.0) < 1e-4
    # A 1D float32 tensor for 5M cells is ~20 MB, not ~17 GB of d-vectors.
    assert v.ram.element_size() * v.ram.nelement() < 64_000_000


def test_lazy_ram_number_vector_roundtrip_via_real_component():
    # The attn number-tape writes computed number-VECTORS (dot/sum results); the
    # device stores their real-axis scalar and reconstructs on read.
    v = _vsa()
    v.ram_write(4.0, v.make_real(7.0))
    v.ram_write(9.0, v.make_real(3.0) + v.make_real(5.0))     # = 8 on the real axis
    assert abs(float(v._re(v.ram_read(4.0))) - 7.0) < 1e-4
    assert abs(float(v._re(v.ram_read(9.0))) - 8.0) < 1e-4


def test_orchestrator_attached_list_path_unchanged():
    # iso5 / ntm_ram attach self.ram as a list of vectors and index it directly.
    v = _vsa()
    v.ram = [v.zero_vector() for _ in range(8)]
    v.ram_write(3.0, 55.0)
    assert isinstance(v.ram, list)                            # stays a list
    assert abs(float(v._re(v.ram_read(3.0))) - 55.0) < 1e-4
    assert abs(float(v._re(v.ram[3])) - 55.0) < 1e-4          # direct index still works
