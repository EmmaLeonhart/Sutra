"""`ProcessPoolRuntime` — genuine multi-process Sutra (separate OS processes).

`MultiProcessRuntime` runs N programs in ONE process (GIL-bound; the tick_all
finding showed no speedup). `ProcessPoolRuntime` runs them across W worker OS
processes — separate GILs, the real throughput lever. This pins the CORRECTNESS
gate that makes the design legitimate: each worker rebuilds its `_VSA` caches
independently (deterministic from key strings + seed — the §1B finding), so

  - two workers running the SAME program on the SAME input produce BIT-IDENTICAL
    output (cross-process determinism), and
  - that output decodes to the correct semantic values (the path is correct, not
    just consistent).

See planning/sutra-spec/multi-process-runtime.md. Uses a `make_real`-only program
so the test needs no Ollama/codebook and is fully deterministic.
"""
from __future__ import annotations

import pytest

torch = pytest.importorskip("torch")

from sutra_compiler.multi_process import (  # noqa: E402
    MultiProcessRuntime, ProcessPoolRuntime, ProgramSpec)

_PROG = """
function vector on_axon(vector input_axon) {
    Axon a;
    a.add("x", make_real(5.0));
    a.add("y", make_real(8.0));
    return a;
}
"""

_DIM = 64  # no codebook (make_real only), so the semantic dim can be small


def _write(tmp_path, name):
    p = tmp_path / ("%s.su" % name)
    p.write_text(_PROG, encoding="utf-8")
    return p


def test_process_pool_cross_process_determinism_and_decode(tmp_path):
    src = _write(tmp_path, "rec")
    # Same program admitted under two names → round-robin to two workers.
    specs = [ProgramSpec(name="p_a", source_path=src),
             ProgramSpec(name="p_b", source_path=src)]

    # Reference single-process runtime: builds the input + decodes the output.
    ref = MultiProcessRuntime([ProgramSpec(name="ref", source_path=src)],
                              runtime_dim=_DIM)
    v = ref.vsa()
    inp = v.zero_vector()

    with ProcessPoolRuntime(specs, num_workers=2, runtime_dim=_DIM) as pool:
        assert pool.admitted() == ["p_a", "p_b"]
        outs = pool.tick_all({"p_a": inp, "p_b": inp})

    # Cross-process determinism: two separate OS processes, same program + input
    # → BIT-IDENTICAL output (both workers forced to CPU; exact comparison).
    assert torch.equal(outs["p_a"], outs["p_b"]), \
        "cross-process outputs differ — rebuild-per-process is not deterministic"

    # Decode correctness: the output axon reads back x=5, y=8.
    out = outs["p_a"].to(v.device)
    gx = float(torch.dot(v.axon_item(out, "x"), v.make_real(1.0)))
    gy = float(torch.dot(v.axon_item(out, "y"), v.make_real(1.0)))
    assert gx == pytest.approx(5.0, abs=1e-2), "decoded x=%r != 5" % gx
    assert gy == pytest.approx(8.0, abs=1e-2), "decoded y=%r != 8" % gy


def test_process_pool_tick_single_and_validation(tmp_path):
    src = _write(tmp_path, "rec2")
    with ProcessPoolRuntime([ProgramSpec(name="only", source_path=src)],
                            num_workers=1, runtime_dim=_DIM) as pool:
        ref = MultiProcessRuntime([ProgramSpec(name="r", source_path=src)],
                                  runtime_dim=_DIM)
        v = ref.vsa()
        out = pool.tick("only", v.zero_vector())
        assert out.shape[0] == v.dim
        # Unknown program name is refused.
        with pytest.raises(KeyError):
            pool.tick("nope", v.zero_vector())


def test_process_pool_rejects_duplicate_names(tmp_path):
    src = _write(tmp_path, "rec3")
    with pytest.raises(ValueError):
        ProcessPoolRuntime([ProgramSpec(name="d", source_path=src),
                            ProgramSpec(name="d", source_path=src)],
                           num_workers=1, runtime_dim=_DIM)
