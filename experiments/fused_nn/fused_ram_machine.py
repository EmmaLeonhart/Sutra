"""Phase-2 #2: the WASM RAM-state machine as ONE fused recurrent step over a single
RAM tensor — exported as a real weight file.

This is the payoff of Emma's substrate insight (2026-06-07): the machine's host
leaks were not isolated bugs — the RAM substrate was improperly done. The device
decoded every address with `int(round(float(ptr.item())))` (a HOST readout per
memory access) and mutated a Python list. That (a) severed autograd, (b) made the
step un-fusable, and (c) was slow (a host round-trip per access).

The fix (proper substrate): RAM is ONE `(N, dim)` tensor; `ramRead`/`ramWrite`
gather/scatter it with a round->long TENSOR index (no `.item()`), functionally
threading the tensor. With that, the SAME compiled machine step
(`mini_wasm_machine.su`, unchanged) becomes a single fused graph over the RAM
tensor — and #3 ("carry multiple state pieces") is SUBSUMED: pc, sp, stack, and
data are all rows of the one tensor, so the recurrence carries exactly one thing.

This demo:
  (1) compiles `mini_wasm_machine.su` (unchanged) and runs it in TENSOR-RAM mode,
  (2) traces the step over the RAM tensor into ONE graph; asserts it is
      host-readout-free (no aten::item / _local_scalar_dense),
  (3) saves it as a real weight file `machine_step.pt`,
  (4) drives the traced step (the fused network) to run two real programs end to
      end: a backward-branch counter loop (acc=N) and factorial(3)=6,
  (5) generates a tiny torch-only orchestrator, runs it in a FRESH subprocess, and
      checks it reproduces the counter-loop result.

Verified substrate-to-substrate against the reference machine's measured outputs
(test_mini_wasm_machine: counter loop -> N, factorial(3) -> 6). Ollama-free,
self-asserting. CPU-pinned for the trace (the cuda torch.jit.trace device quirk;
eager runs on cuda — see fused-compile-target.md).
"""

from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str((REPO / "sdk" / "sutra-compiler").resolve()))

import torch  # noqa: E402

# Counter loop: ram[200]=counter=N, ram[201]=acc; each iter acc++/counter--,
# branch back while counter != 0. Backward branch + memory => Turing-complete.
_LOOP = [(1, 200), (1, 3), (8, 0), (1, 201), (1, 0), (8, 0),
         (1, 201), (1, 201), (7, 0), (1, 1), (2, 0), (8, 0),
         (1, 200), (1, 200), (7, 0), (1, 1), (3, 0), (8, 0),
         (1, 200), (7, 0), (6, 22), (0, 0)]
# factorial(3): ram[201]=acc=1; loop acc*=counter, counter--, branch back -> 6.
_FACT = [(1, 200), (1, 3), (8, 0), (1, 201), (1, 1), (8, 0),
         (1, 201), (1, 201), (7, 0), (1, 200), (7, 0), (4, 0), (8, 0),
         (1, 200), (1, 200), (7, 0), (1, 1), (3, 0), (8, 0),
         (1, 200), (7, 0), (6, 22), (0, 0)]


def _compile_machine():
    # CPU build+trace: torch.jit.trace records a comparison literal as a CPU
    # constant on a CUDA box (eager is fine on cuda). The machine is device-
    # agnostic; pin CPU for the export. See fused-compile-target.md.
    torch.cuda.is_available = lambda: False
    from sutra_compiler.lexer import Lexer
    from sutra_compiler.parser import Parser
    from sutra_compiler.codegen_pytorch import translate_module
    su = (REPO / "experiments" / "iso5_substrate_dispatch"
          / "mini_wasm_machine.su").read_text(encoding="utf-8")
    lx = Lexer(su, file="<machine>")
    ast = Parser(lx.tokenize(), file="<machine>", diagnostics=lx.diagnostics).parse_module()
    assert not lx.diagnostics.has_errors(), list(lx.diagnostics)
    ns: dict = {}
    exec(translate_module(ast, llm_model="none", runtime_dim=2), ns)
    return ns


def _init_ram(v, prog, n_cells=512):
    ram = torch.zeros(n_cells, v.dim, dtype=v.dtype, device=v.device)
    ram[0] = v.make_real(10.0)   # pc -> program base
    ram[1] = v.make_real(0.0)    # sp
    ram[2] = v.make_real(0.0)    # halted
    for k, (op, imm) in enumerate(prog):
        ram[10 + 2 * k] = v.make_real(float(op))
        ram[11 + 2 * k] = v.make_real(float(imm))
    return ram


_ORCH = '''\
"""Tiny orchestrator for the fused WASM machine. Imports ONLY torch; loads the
per-step weight file and drives the recurrence over the RAM tensor. The only host
reads (loading the program, reading the result) are at the terminal boundary."""
import torch
DIM, REAL, N = {dim}, {real_idx}, {n_cells}
PROG = {prog}
def make_real(x):
    v = torch.zeros(DIM, dtype=torch.float32); v[REAL] = float(x); return v
ram = torch.zeros(N, DIM, dtype=torch.float32)
ram[0] = make_real(10.0); ram[1] = make_real(0.0); ram[2] = make_real(0.0)
for k, (op, imm) in enumerate(PROG):
    ram[10 + 2*k] = make_real(op); ram[11 + 2*k] = make_real(imm)
step = torch.jit.load("{step_path}")     # the fused machine step (the weights)
for _t in range({steps}):                # drive the recurrence
    ram = step(ram)                      # one instruction, all on the tensor
print(round(float(ram[{result_addr}][REAL])))   # read result (terminal boundary)
'''


def main() -> int:
    ns = _compile_machine()
    v, step = ns["_VSA"], ns["step"]
    real = v.semantic_dim + v.AXIS_REAL

    def step_fn(ram):
        v.ram = ram
        step(0.0)
        return v.ram

    # Eager (tensor-RAM) cross-check.
    v.ram = _init_ram(v, _LOOP)
    for _ in range(60):
        step(0.0)
    eager_loop = round(float(v.ram[201][real]))

    with tempfile.TemporaryDirectory() as d:
        d = pathlib.Path(d)
        step_path = d / "machine_step.pt"

        traced = torch.jit.trace(step_fn, (_init_ram(v, _LOOP),), check_trace=False)
        g = str(traced.graph)
        no_readout = ("aten::item" not in g) and ("_local_scalar_dense" not in g)
        torch.jit.save(traced, str(step_path))
        size = step_path.stat().st_size

        # Drive the TRACED step (the fused network) on both programs.
        ram = _init_ram(v, _LOOP)
        for _ in range(60):
            ram = traced(ram)
        traced_loop = round(float(ram[201][real]))

        ram = _init_ram(v, _FACT)
        for _ in range(70):
            ram = traced(ram)
        traced_fact = round(float(ram[201][real]))

        # Fresh-subprocess orchestrator (torch-only, no Sutra compiler).
        run_py = d / "run.py"
        run_py.write_text(_ORCH.format(
            dim=v.dim, real_idx=real, n_cells=512, prog=repr(_LOOP),
            step_path=str(step_path).replace("\\", "\\\\"), steps=60, result_addr=201,
        ), encoding="utf-8")
        proc = subprocess.run([sys.executable, str(run_py)],
                              capture_output=True, text=True, cwd=str(d))
        printed = proc.stdout.strip()
        orch_imports_compiler = "sutra_compiler" in run_py.read_text(encoding="utf-8")

    print(f"machine step traced to ONE graph; host-readout-free (no aten::item): {no_readout}")
    print(f"emitted machine_step.pt ({size} bytes)")
    print(f"eager tensor-RAM counter loop = {eager_loop} (want 3)")
    print(f"traced-step counter loop = {traced_loop} (want 3);  factorial(3) = {traced_fact} (want 6)")
    print(f"orchestrator imports compiler: {orch_imports_compiler} (want False); subprocess printed {printed!r}")

    if proc.returncode != 0:
        print("FAIL: orchestrator subprocess errored:\n" + proc.stderr[-800:])
        return 1
    ok = (no_readout and not orch_imports_compiler
          and eager_loop == 3 and traced_loop == 3 and traced_fact == 6
          and printed != "" and int(printed) == 3)
    if not ok:
        print("FAIL: fused RAM machine mismatch")
        return 1
    print("PASS: the WASM RAM-state machine compiles to ONE fused, host-readout-free "
          "step graph over a single RAM tensor (state #2 done; multi-state #3 subsumed), "
          "saved as a real weight file; a tiny torch-only orchestrator drove it to run a "
          "backward-branch counter loop and factorial end-to-end on the substrate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
