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
          "orchestrator_model"]


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
