"""Phase-2: a BOUNDED substrate recurrence (loop(N)) fuses into ONE differentiable
graph, with gradients flowing through every step.

differentiable_substrate.py / trace_to_graph.py showed straight-line functions
fuse + differentiate. This extends it to RECURRENCE — the core of "the machine is
a fused recurrent network". `loop (N) { body }` with literal N is a compile-time
unroll (control-flow.md §"loop[N]"): N body copies, no host break, no float
readout — so it is fully substrate and traceable.

Verifies, with measurements, for `loop(3){ x = x*2 + 1 }` (f(x) = 8x + 7):
  (1) correct unrolled value;
  (2) gradient flows through all 3 recurrence steps (d/dx = 2^3 = 8);
  (3) it traces into a single graph that round-trips through save/reload.

NOTE the boundary: this is the BOUNDED (literal-N) loop, which is fusable today.
Data-dependent unbounded loops emit a host early-exit (`if float(_halted) >= ...:
break`) that severs the graph — see
planning/findings/2026-06-07-loop-emission-host-readout-blocks-fusion.md. And the
WASM machine's multi-state recurrence additionally needs the v1 one-slot-recur
limit lifted. Ollama-free, self-asserting.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str((REPO / "sdk" / "sutra-compiler").resolve()))

import torch  # noqa: E402

from sutra_compiler.lexer import Lexer  # noqa: E402
from sutra_compiler.parser import Parser  # noqa: E402
from sutra_compiler.codegen_pytorch import translate_module  # noqa: E402


def main() -> int:
    src = (
        "function int f(int x){ loop (3) { x = x * 2 + 1; } return x; }\n"
        'function string main(){ return "ok"; }'
    )
    assert ".real()" not in src
    lx = Lexer(src, file="<rec>")
    ast = Parser(lx.tokenize(), file="<rec>", diagnostics=lx.diagnostics).parse_module()
    assert not lx.diagnostics.has_errors(), list(lx.diagnostics)
    ns: dict = {}
    exec(translate_module(ast, llm_model="none", runtime_dim=4), ns)
    f, v = ns["f"], ns["_VSA"]
    real = v.semantic_dim + v.AXIS_REAL

    # (1) + (2): value and gradient through all 3 steps.
    x = v.make_real(5.0).clone().detach().requires_grad_(True)
    out = f(x)
    val = float(out[real])
    out[real].backward()
    g = float(x.grad[real])
    print(f"f(5), loop(3) x<-2x+1 = {val} (want 8*5+7 = 47)")
    print(f"d(out)/d(x) = {g} (want 2^3 = 8 -- gradient through all 3 steps)")

    # (3) trace -> save -> reload -> run.
    def fused(x):
        return f(x)

    traced = torch.jit.trace(fused, (v.make_real(5.0),), check_trace=False)
    n_nodes = sum(1 for _ in traced.graph.nodes())
    with tempfile.TemporaryDirectory() as d:
        path = pathlib.Path(d) / "recurrence.pt"
        torch.jit.save(traced, str(path))
        reloaded = torch.jit.load(str(path))
        rval = float(reloaded(v.make_real(9.0))[real])
    print(f"traced recurrence into single graph ({n_nodes} nodes); reloaded f(9) = {rval} (want 79)")

    if not (abs(val - 47) < 1e-4 and abs(g - 8) < 1e-4 and abs(rval - 79) < 1e-4):
        return 1
    print("PASS: a bounded substrate recurrence (loop(N)) fuses into one "
          "differentiable graph, gradients flow through every step, and it "
          "round-trips through save/reload. Recurrence fusion holds for the "
          "bounded case; unbounded loops + multi-state recur are the remaining work.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
