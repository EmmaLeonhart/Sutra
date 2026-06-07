"""Phase-2 #7: emit a RECURRENT (unbounded-loop) Sutra program as a real weight
file + a tiny orchestrator that drives the recurrence.

emit_weight_file.py did this for the straight-line case. This extends it to the
hard case — an UNBOUNDED loop (`while_loop`), which is the shape the WASM machine
needs. Per Emma's orchestrator model (project_orchestrator_model,
planning/exploratory/fused-compile-target.md) and the #6/#7 codegen split:

  - the compiler now emits the loop's per-tick computation as a MODULE-LEVEL pure
    function `_step_loop_<name>(...)` (condition + body + soft-halt; zero host
    readout) — the fusable, exportable weight graph;
  - the driver is a thin orchestrator that calls the step and reads `float(_halted)`.

This demo:
  (1) compiles `while_loop countup(n < 5, int n){ pass n+1; }`,
  (2) grabs the module-level step `_step_loop_countup` and traces it into ONE graph,
  (3) saves it as a real weight file `step.pt` (torch.jit.save),
  (4) confirms the step graph is host-readout-free (no aten::item),
  (5) generates `run.py` — a TINY torch-only orchestrator that loads step.pt, drives
      the recurrence (call step, read halt, repeat), and prints the output,
  (6) runs it as a fresh subprocess and checks it reproduces the loop result (n=5),
      cross-checked against the eager compiled driver.

So "a recurrent Sutra program compiles to a real weight file (the step) + a tiny
orchestrator (the driver)" is realized end-to-end. Ollama-free, self-asserting.
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
"""Tiny orchestrator for a Sutra-compiled RECURRENT program. Imports ONLY torch;
loads the per-tick STEP weight file and drives the recurrence. The halt-read and
output-read live here (the terminal boundary), never inside the step graph."""
import torch
DIM, REAL = {dim}, {real_idx}
def make_real(x):
    v = torch.zeros(DIM, dtype=torch.float32)
    v[REAL] = float(x)
    return v
step = torch.jit.load("{step_path}")          # the network (the weights)
n = make_real({init})
init_n = make_real({init})
for _t in range({max_steps}):                 # drive the recurrence
    n, halted = step(n, init_n)               # run the step (one tick)
    if float(halted) >= 0.99:                 # halt-read: orchestrator boundary
        break
print(float(n[REAL]))                         # output-read: terminal boundary
'''


def main() -> int:
    src = (
        "while_loop countup(n < 5, int n) { pass n + 1; }\n"
        "function int main() { slot int n = 0; loop countup(n < 5, n); return n; }\n"
    )
    assert ".real()" not in src
    lx = Lexer(src, file="<emit-loop>")
    ast = Parser(lx.tokenize(), file="<emit-loop>", diagnostics=lx.diagnostics).parse_module()
    assert not lx.diagnostics.has_errors(), list(lx.diagnostics)
    ns: dict = {}
    # Build + trace on CPU. The mechanism is device-agnostic; we pin CPU because
    # `torch.jit.trace` records a comparison literal as a CPU constant on a CUDA
    # box (eager runs fine on cuda — verified), so tracing a comparison-using
    # step on GPU hits a cuda/cpu mismatch. Exporting on GPU is a separate
    # trace-device follow-up; CPU is the right scope for proving export+drive.
    _orig_cuda = torch.cuda.is_available
    torch.cuda.is_available = lambda: False
    try:
        exec(translate_module(ast, llm_model="none", runtime_dim=4), ns)
    finally:
        torch.cuda.is_available = _orig_cuda
    v = ns["_VSA"]
    step = ns["_step_loop_countup"]      # the module-level pure step (the network)
    driver = ns["_loop_countup"]         # the eager in-module driver (cross-check)
    real_idx = v.semantic_dim + v.AXIS_REAL
    dim = v.dim

    # Eager cross-check: run the compiled driver directly.
    eager_tuple = driver(v.make_real(0.0))
    eager = float(eager_tuple[0][real_idx])   # (n, halted) -> n

    with tempfile.TemporaryDirectory() as d:
        d = pathlib.Path(d)
        step_path = d / "step.pt"

        # Trace the STEP into one graph. _t is unused by a while_loop step, so
        # fix it at 0; the recurrence is driven by re-feeding n. _init_n is the
        # capture slot (unused here) but part of the step signature.
        def step_fn(n, init_n):
            return step(0, n, init_n)

        traced = torch.jit.trace(
            step_fn, (v.make_real(0.0), v.make_real(0.0)), check_trace=False
        )
        torch.jit.save(traced, str(step_path))
        size = step_path.stat().st_size

        graph_str = str(traced.graph)
        no_readout = "aten::item" not in graph_str and "aten::Float" not in graph_str

        run_py = d / "run.py"
        run_py.write_text(_ORCHESTRATOR_TEMPLATE.format(
            dim=dim, real_idx=real_idx,
            step_path=str(step_path).replace("\\", "\\\\"),
            init=0.0, max_steps=1000,
        ), encoding="utf-8")

        proc = subprocess.run([sys.executable, str(run_py)],
                              capture_output=True, text=True, cwd=str(d))
        printed = proc.stdout.strip()
        orch_imports_compiler = "sutra_compiler" in run_py.read_text(encoding="utf-8")

    print(f"emitted step.pt ({size} bytes) + a {len(_ORCHESTRATOR_TEMPLATE.splitlines())}-line orchestrator")
    print(f"step graph host-readout-free (no aten::item/Float): {no_readout}")
    print(f"orchestrator imports the Sutra compiler: {orch_imports_compiler} (want False)")
    print(f"eager driver n = {eager} (want 5);  orchestrator subprocess printed: {printed!r}")

    if proc.returncode != 0:
        print("FAIL: orchestrator subprocess errored:\n" + proc.stderr[-800:])
        return 1
    ok = (no_readout and not orch_imports_compiler
          and abs(eager - 5.0) < 1e-4
          and printed != "" and abs(float(printed) - 5.0) < 1e-4)
    if not ok:
        print("FAIL: recurrent weight-file emission / orchestrator output mismatch")
        return 1
    print("PASS: an UNBOUNDED-loop Sutra program emitted a per-tick STEP weight file "
          "(host-readout-free) + a tiny torch-only orchestrator; the orchestrator drove "
          "the recurrence (call step, read halt) and reproduced the loop result. The "
          "recurrent weight-file compile target is realized end-to-end.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
