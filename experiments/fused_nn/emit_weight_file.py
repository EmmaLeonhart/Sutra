"""Phase-2: emit the two compile artifacts for a substrate-pure Sutra function —
a network WEIGHT FILE + a tiny standalone orchestrator that runs it.

This is the first concrete realization of planning/exploratory/fused-compile-target.md
for the simple (straight-line / bounded-loop) case. Given a substrate-pure `.su`
function, it:
  (1) compiles + traces it into one tensor-op graph,
  (2) saves that graph as a real weight file `network.pt` (torch.jit.save),
  (3) generates `run.py` — a TINY orchestrator that imports ONLY torch, loads
      `network.pt`, builds the input vector, runs the network, and prints the
      output. No Sutra runtime, no computation — a pure connector to the weights.
Then it RUNS the generated orchestrator as a subprocess and verifies the printed
output matches the eager result.

So "Sutra compiles to a real weight file + a tiny orchestrator" is realized
end-to-end for this case. Recurrence/RAM/unbounded-loop cases are the remaining
build (fused-compile-target.md). Ollama-free, self-asserting.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str((REPO / "sdk" / "sutra-compiler").resolve()))

import torch  # noqa: E402

from sutra_compiler.lexer import Lexer  # noqa: E402
from sutra_compiler.parser import Parser  # noqa: E402
from sutra_compiler.codegen_pytorch import translate_module  # noqa: E402

_ORCHESTRATOR_TEMPLATE = '''\
"""Tiny orchestrator for a Sutra-compiled network. Imports ONLY torch; loads the
weight file and runs it. No computation here — a connector to the weights."""
import sys, torch
DIM, REAL = {dim}, {real_idx}
def make_real(x):
    v = torch.zeros(DIM, dtype=torch.float32)
    v[REAL] = float(x)
    return v
net = torch.jit.load("{network_path}")
x = float(sys.argv[1]) if len(sys.argv) > 1 else {default_in}
out = net(make_real(x))          # run the network (the weights)
print(float(out[REAL]))          # read + print output (terminal boundary)
'''


def main() -> int:
    src = (
        "function int f(int x){ int y = x * 2 + 1; return y; }\n"
        'function string main(){ return "ok"; }'
    )
    assert ".real()" not in src
    lx = Lexer(src, file="<emit>")
    ast = Parser(lx.tokenize(), file="<emit>", diagnostics=lx.diagnostics).parse_module()
    assert not lx.diagnostics.has_errors(), list(lx.diagnostics)
    ns: dict = {}
    exec(translate_module(ast, llm_model="none", runtime_dim=4), ns)
    f, v = ns["f"], ns["_VSA"]
    real_idx = v.semantic_dim + v.AXIS_REAL
    dim = v.dim

    eager = float(f(v.make_real(9.0))[real_idx])  # 9*2+1 = 19

    with tempfile.TemporaryDirectory() as d:
        d = pathlib.Path(d)
        net_path = d / "network.pt"

        def net_fn(x):
            return f(x)

        traced = torch.jit.trace(net_fn, (v.make_real(1.0),), check_trace=False)
        torch.jit.save(traced, str(net_path))
        size = net_path.stat().st_size

        run_py = d / "run.py"
        run_py.write_text(_ORCHESTRATOR_TEMPLATE.format(
            dim=dim, real_idx=real_idx,
            network_path=str(net_path).replace("\\", "\\\\"), default_in=9.0,
        ), encoding="utf-8")

        # Run the standalone orchestrator (fresh process; it imports only torch).
        proc = subprocess.run([sys.executable, str(run_py), "9"],
                              capture_output=True, text=True, cwd=str(d))
        printed = proc.stdout.strip()
        orchestrator_imports_compiler = "sutra_compiler" in run_py.read_text(encoding="utf-8")

    print(f"emitted network.pt ({size} bytes) + a {len(_ORCHESTRATOR_TEMPLATE.splitlines())}-line orchestrator")
    print(f"orchestrator imports the Sutra compiler: {orchestrator_imports_compiler} (want False — it only loads weights)")
    print(f"eager f(9) = {eager} (want 19);  orchestrator subprocess printed: {printed!r}")

    if proc.returncode != 0:
        print("FAIL: orchestrator subprocess errored:\n" + proc.stderr[-500:])
        return 1
    ok = (not orchestrator_imports_compiler) and abs(eager - 19.0) < 1e-4 \
        and abs(float(printed) - 19.0) < 1e-4
    if not ok:
        print("FAIL: artifact emission / orchestrator output mismatch")
        return 1
    print("PASS: a substrate-pure Sutra function emitted a network WEIGHT FILE + a "
          "tiny torch-only orchestrator; the orchestrator (no compiler, no computation) "
          "loaded the weights and reproduced the result. Weight-file compile target "
          "realized for the simple case.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
