"""Regression guards for the Phase-2 fused-neural-network milestones.

The substrate-purity → fused-NN overhaul proved (Ollama-free, self-asserting):
  - differentiable_substrate.py: a substrate-pure Sutra function is end-to-end
    differentiable; `.real()` is a gradient wall.
  - trace_to_graph.py: a Sutra function compiles to ONE fused TorchScript graph,
    saved to a file, reloaded, run with identical output + intact gradients.
  - recurrence_fusion.py: a bounded substrate recurrence `loop(N)` fuses into one
    differentiable graph, gradients through every step.

These live as scripts under `experiments/fused_nn/`. This wires them into the
test suite so a regression (e.g. a reintroduced host readout that severs autograd,
or a fusion break) fails CI. Each demo's `main()` returns 0 on success, nonzero on
a measured mismatch.
"""

from __future__ import annotations

import importlib.util
import pathlib

import pytest

_DEMOS = ["differentiable_substrate", "trace_to_graph", "recurrence_fusion",
          "orchestrator_model", "emit_weight_file", "ram_tensor_step",
          "emit_loop_weight_file", "fused_ram_machine"]


def _load_main(name: str):
    repo = pathlib.Path(__file__).resolve().parents[3]
    path = repo / "experiments" / "fused_nn" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"fused_nn_{name}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.main


@pytest.mark.parametrize("name", _DEMOS)
def test_fused_nn_demo_passes(name):
    pytest.importorskip("torch")
    main = _load_main(name)
    assert main() == 0, f"fused-NN demo {name} reported a measured failure"


def test_runtime_functional_ram_ops():
    """The runtime provides functional tensor-RAM ops (ram_gather/ram_scatter) —
    substrate-pure (no readout), correct, and non-mutating (functional). These are
    the fusion-path RAM primitives (planning/exploratory/fused-compile-target.md)."""
    import torch
    pytest.importorskip("torch")
    repo = pathlib.Path(__file__).resolve().parents[3]
    csrc = repo / "sdk" / "sutra-compiler"
    import sys as _sys
    if str(csrc) not in _sys.path:
        _sys.path.insert(0, str(csrc))
    from sutra_compiler.lexer import Lexer
    from sutra_compiler.parser import Parser
    from sutra_compiler.codegen_pytorch import translate_module
    lx = Lexer('function string main(){return "ok";}', file="<ram>")
    ast = Parser(lx.tokenize(), file="<ram>", diagnostics=lx.diagnostics).parse_module()
    ns: dict = {}
    exec(translate_module(ast, llm_model="none", runtime_dim=8), ns)
    v = ns["_VSA"]
    real = v.semantic_dim + v.AXIS_REAL
    ram = torch.zeros(16, v.dim, dtype=v.dtype, device=v.device)
    ram[3] = v.make_real(41.0)
    cell = v.ram_gather(ram, v.make_real(3.0))
    assert abs(float(cell[real]) - 41.0) < 1e-9
    ram2 = v.ram_scatter(ram, v.make_real(3.0), cell + v.make_real(1.0))
    assert abs(float(ram2[3][real]) - 42.0) < 1e-9
    assert abs(float(ram[3][real]) - 41.0) < 1e-9  # functional: input unchanged
