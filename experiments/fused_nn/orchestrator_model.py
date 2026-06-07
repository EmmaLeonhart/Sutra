"""Phase-2: the orchestrator model (Emma 2026-06-07) — weights = the STEP, a tiny
Python driver runs the recurrence and reads the halt signal.

Emma's architecture for "Sutra compiles to a real weight file": the fused
weight-graph is the loop BODY / STEP (a pure tensor function), and a TINY Python
orchestrator loads + runs it, drives the recurrence, reads the HALT signal to stop,
and reads OUTPUT to print. The halt/output read lives in the orchestrator (the
legitimate terminal boundary), NOT inside the step graph — so the step graph has
ZERO host readout.

This demonstrates exactly that shape with a real COMPILED Sutra step:
  - `step(x) = x * 2` compiled by the PyTorch codegen, traced into one graph;
  - the traced STEP graph contains NO host readout (no aten::item);
  - a ~10-line Python orchestrator drives `x ← step(x)` until a halt condition,
    reading x's real axis (the terminal boundary) only in the orchestrator.

Result: the recurrence runs as `step` (the network) + a tiny driver (the
orchestrator). Ollama-free, self-asserting.
"""

from __future__ import annotations

import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str((REPO / "sdk" / "sutra-compiler").resolve()))

import torch  # noqa: E402

from sutra_compiler.lexer import Lexer  # noqa: E402
from sutra_compiler.parser import Parser  # noqa: E402
from sutra_compiler.codegen_pytorch import translate_module  # noqa: E402


def main() -> int:
    # The STEP (loop body) — a pure substrate function. This is the network.
    src = (
        "function int step(int x){ return x * 2; }\n"
        'function string main(){ return "ok"; }'
    )
    assert ".real()" not in src
    lx = Lexer(src, file="<orch>")
    ast = Parser(lx.tokenize(), file="<orch>", diagnostics=lx.diagnostics).parse_module()
    assert not lx.diagnostics.has_errors(), list(lx.diagnostics)
    ns: dict = {}
    exec(translate_module(ast, llm_model="none", runtime_dim=4), ns)
    step, v = ns["step"], ns["_VSA"]
    real = v.semantic_dim + v.AXIS_REAL

    # Trace the STEP into a single fused graph (the exportable weight artifact).
    def step_fn(x):
        return step(x)

    step_graph = torch.jit.trace(step_fn, (v.make_real(1.0),), check_trace=False)

    # The step graph must contain NO host readout — that belongs in the orchestrator.
    graph_str = str(step_graph.graph)
    no_readout = "aten::item" not in graph_str and "aten::Float" not in graph_str
    print(f"step graph host-readout-free (no aten::item/Float): {no_readout}")

    # ── The TINY orchestrator (this is the whole driver) ──────────────────────
    # Loads/runs the step graph, drives the recurrence, reads the halt signal,
    # reads output. The ONLY host reads (float(...)) are here, at the boundary.
    def orchestrator(step_graph, x0, halt_at, max_steps=64):
        x = x0
        for n in range(max_steps):
            if float(x[real]) > halt_at:        # HALT read — orchestrator boundary
                return float(x[real]), n        # OUTPUT read — orchestrator boundary
            x = step_graph(x)                   # run the network one step
        return float(x[real]), max_steps
    # ──────────────────────────────────────────────────────────────────────────

    out, steps = orchestrator(step_graph, v.make_real(1.0), halt_at=100.0)
    print(f"orchestrator drove step (x<-2x) from 1 until >100: x={out} after {steps} steps "
          f"(want 128 after 7 steps)")

    ok = no_readout and abs(out - 128.0) < 1e-4 and steps == 7
    if not ok:
        print("FAIL: orchestrator-model demo mismatch")
        return 1
    print("PASS: the compiled STEP is a host-readout-free fused graph (the network); "
          "a ~10-line Python orchestrator drives the recurrence and reads halt+output "
          "at the terminal boundary. This is Emma's weight-file + tiny-orchestrator shape.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
