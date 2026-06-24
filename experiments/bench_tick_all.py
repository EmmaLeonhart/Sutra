"""Benchmark MultiProcessRuntime.tick_all (concurrent) vs sequential tick.

Measures whether the per-program CUDA-stream dispatch in `tick_all` actually
overlaps work on the GPU. Result (dev GPU, 2026-06-20): it does NOT — see
planning/findings/2026-06-20-tick-all-no-speedup-python-bound.md. The per-program
cost is ~98% GIL-bound Python orchestration (building + launching each program's
tensor-op graph) and only ~2% GPU kernel time, so streams (which overlap only the
GPU kernels) cannot speed up the GIL-serialized Python.

Run:  python experiments/bench_tick_all.py [N] [runtime_dim]
"""
from __future__ import annotations

import pathlib
import sys
import tempfile
import time

import torch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "sdk" / "sutra-compiler"))
from sutra_compiler.multi_process import MultiProcessRuntime, ProgramSpec  # noqa: E402

_PROG = (
    "function vector on_axon(vector input_axon) {\n"
    '    Axon a;\n    a.add("x", embed("dog"));\n'
    '    a.add("y", embed("cat"));\n    a.add("z", input_axon);\n'
    "    return a;\n}\n"
)


def _timed(fn, reps: int = 50) -> float:
    cuda = torch.cuda.is_available()
    if cuda:
        torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(reps):
        fn()
    if cuda:
        torch.cuda.synchronize()
    return (time.perf_counter() - t0) / reps * 1e3  # ms/round


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    dim = int(sys.argv[2]) if len(sys.argv) > 2 else 768
    tmp = pathlib.Path(tempfile.mkdtemp())
    specs = []
    for i in range(n):
        p = tmp / f"p{i}.su"
        p.write_text(_PROG, encoding="utf-8")
        specs.append(ProgramSpec(name=f"p{i}", source_path=p))
    rt = MultiProcessRuntime(specs, llm_model="nomic-embed-text", runtime_dim=dim)
    dev = rt.vsa().device
    inp = {f"p{i}": torch.zeros(rt.vsa().dim, device=dev) for i in range(n)}
    # Warm caches (embed dog/cat, build rotations + permutations).
    for i in range(n):
        rt.tick(f"p{i}", inp[f"p{i}"])
    if torch.cuda.is_available():
        torch.cuda.synchronize()

    seq = _timed(lambda: [rt.tick(f"p{i}", inp[f"p{i}"]) for i in range(n)])
    con = _timed(lambda: rt.tick_all(inp))
    # Python-launch-only (no GPU wait) isolates the GIL-bound orchestration cost.
    launch = _timed(lambda: [rt.tick(f"p{i}", inp[f"p{i}"]) for i in range(n)]) if not torch.cuda.is_available() else None
    if torch.cuda.is_available():
        t0 = time.perf_counter()
        for _ in range(50):
            for i in range(n):
                rt.tick(f"p{i}", inp[f"p{i}"])
        launch = (time.perf_counter() - t0) / 50 * 1e3

    print(f"device={'cuda' if torch.cuda.is_available() else 'cpu'} N={n} dim={rt.vsa().dim}")
    print(f"sequential tick:        {seq:.1f} ms/round")
    print(f"tick_all (concurrent):  {con:.1f} ms/round")
    print(f"speedup:                {seq / con:.2f}x")
    if launch is not None:
        print(f"python-launch-only:     {launch:.1f} ms/round "
              f"({launch / seq * 100:.0f}% of the round is GIL-bound Python)")


if __name__ == "__main__":
    main()
