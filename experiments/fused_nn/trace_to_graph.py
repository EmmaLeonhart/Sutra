"""Phase-2: fuse a compiled substrate-pure Sutra function into ONE TorchScript
graph and save it to a file (the weight-file direction).

Differentiability is already shown (differentiable_substrate.py). This shows the
next step: the emitted op-sequence traces into a single connected graph that can
be saved to disk, reloaded, and run — i.e. a Sutra function compiles to a fused
graph artifact, not just a host-orchestrated sequence of calls. A thin Python
loader connects to the saved graph (per Emma: the orchestrator may exist only as
a connector to the weight file, no computation).

Verifies, with measurements:
  (1) torch.jit.trace turns the compiled function into a single ScriptFunction;
  (2) saved to disk + reloaded, it produces output IDENTICAL to the eager run;
  (3) the reloaded graph is still differentiable (gradients flow).

Ollama-free (pure make_real/arithmetic). Self-asserting.
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


def _compile_fn(src: str, fn: str):
    lx = Lexer(src, file="<fuse>")
    ast = Parser(lx.tokenize(), file="<fuse>", diagnostics=lx.diagnostics).parse_module()
    assert not lx.diagnostics.has_errors(), list(lx.diagnostics)
    ns: dict = {}
    exec(translate_module(ast, llm_model="none", runtime_dim=4), ns)
    return ns[fn], ns["_VSA"]


def main() -> int:
    src = (
        "function int f(int a, int b){ int p = a * b; int s = p + a; return s; }\n"
        'function string main(){ return "ok"; }'
    )
    assert ".real()" not in src
    f, v = _compile_fn(src, "f")
    real = v.semantic_dim + v.AXIS_REAL

    a = v.make_real(3.0)
    b = v.make_real(4.0)
    eager = f(a, b)
    eager_val = float(eager[real])

    # (1) trace into a single fused graph. The exec'd function has no __module__,
    # which torch.jit needs for a qualified name — wrap it in a named local.
    def fused(a, b):
        return f(a, b)

    traced = torch.jit.trace(fused, (a, b), check_trace=False)
    n_nodes = sum(1 for _ in traced.graph.nodes())
    print(f"traced into a single ScriptFunction graph ({n_nodes} graph nodes)")

    # (2) save -> reload -> run; output must be identical to eager
    with tempfile.TemporaryDirectory() as d:
        path = pathlib.Path(d) / "f.fused.pt"
        torch.jit.save(traced, str(path))
        size = path.stat().st_size
        reloaded = torch.jit.load(str(path))
        a2 = v.make_real(6.0)
        b2 = v.make_real(7.0)
        reloaded_val = float(reloaded(a2, b2)[real])
        eager_val2 = float(f(a2, b2)[real])
        print(f"saved fused graph to disk ({size} bytes), reloaded")
        print(f"f(3,4) eager = {eager_val} (want 15)")
        print(f"reloaded f(6,7) = {reloaded_val}  vs eager {eager_val2} (want 48)")
        ok_match = abs(reloaded_val - eager_val2) < 1e-4 and abs(reloaded_val - 48) < 1e-4

        # (3) reloaded graph still differentiable
        a3 = v.make_real(3.0).clone().detach().requires_grad_(True)
        b3 = v.make_real(4.0).clone().detach().requires_grad_(True)
        reloaded(a3, b3)[real].backward()
        da = float(a3.grad[real])
        db = float(b3.grad[real])
        print(f"reloaded graph gradients: d/da={da} (want 5), d/db={db} (want 3)")
        ok_grad = abs(da - 5) < 1e-4 and abs(db - 3) < 1e-4

    if not (abs(eager_val - 15) < 1e-4 and ok_match and ok_grad):
        print("FAIL: fused-graph round-trip or differentiability mismatch")
        return 1
    print("PASS: a substrate-pure Sutra function compiles to a single fused "
          "TorchScript graph, saved to a file, reloaded, and run with identical "
          "output AND intact gradients. The weight-file compile target is reachable "
          "for pure functions; RAM/loop recurrence is the remaining piece.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
