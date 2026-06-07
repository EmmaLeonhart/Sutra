"""Phase-2 building block: RAM as a single VRAM tensor, accessed by gather/scatter
(no host list, no host int index) — traceable + differentiable + readout-free.

The mini_wasm_machine keeps state in the RAM device: a Python *list* of cell
vectors, indexed by a host int `int(round(ptr[AXIS_REAL]))`. The cells are already
in VRAM, but the list-container + host-int indexing are not traceable tensor ops,
so the machine's step can't yet be one fused exportable graph
(fused-compile-target.md). The fix is to make RAM a single `(N, dim)` tensor and
the access a tensor gather/scatter with a tensor index.

This validates that representation as the building block for the machine-fusion
codegen change. It mirrors the runtime's AXIS layout (real axis carries values).
Measured here:
  (1) a step that reads cell[addr] (gather), increments its real axis, writes it
      back (scatter) is pure tensor ops — no `.item()`, no host int;
  (2) it traces into a graph with NO host readout (no aten::item);
  (3) it is differentiable: gradient flows from the written cell back to the input
      RAM tensor;
  (4) it computes correctly (cell[addr] real axis += 1).

This is the building block, NOT yet Sutra-compiled output — the codegen change
(emit ram_read/ram_write as gather/scatter over a threaded RAM tensor) is the
follow-on. Ollama-free, self-asserting.
"""

from __future__ import annotations

import torch

DIM = 8
N = 16
AXIS_REAL = 0  # mirrors the runtime: value on the real axis of each cell


def make_real(x: float) -> torch.Tensor:
    v = torch.zeros(DIM, dtype=torch.float64)
    v[AXIS_REAL] = x
    return v


def ram_read(ram: torch.Tensor, ptr: torch.Tensor) -> torch.Tensor:
    """Gather cell[addr] where addr = round(ptr's real axis). Tensor index, no host int."""
    idx = torch.round(ptr[AXIS_REAL]).long().clamp_(0, N - 1).reshape(1)
    return ram.index_select(0, idx).reshape(DIM)


def ram_write(ram: torch.Tensor, ptr: torch.Tensor, value: torch.Tensor) -> torch.Tensor:
    """Return a new RAM tensor with cell[addr] = value (scatter). No in-place host index."""
    idx = torch.round(ptr[AXIS_REAL]).long().clamp_(0, N - 1).reshape(1)
    return ram.index_copy(0, idx, value.reshape(1, DIM))


def step(ram: torch.Tensor, ptr: torch.Tensor) -> torch.Tensor:
    """One pure-tensor RAM step: cell[addr] real axis += 1."""
    cell = ram_read(ram, ptr)
    new_cell = cell + make_real(1.0)
    return ram_write(ram, ptr, new_cell)


def main() -> int:
    ram = torch.zeros(N, DIM, dtype=torch.float64)
    ram[3, AXIS_REAL] = 41.0
    ptr = make_real(3.0)

    # (1)+(4): correctness — cell 3 goes 41 -> 42.
    out = step(ram, ptr)
    val = float(out[3, AXIS_REAL])
    print(f"step: ram[3].real 41 -> {val} (want 42)")

    # (2): trace into a graph; assert no host readout.
    traced = torch.jit.trace(step, (ram, ptr), check_trace=False)
    g = str(traced.graph)
    no_readout = "aten::item" not in g
    print(f"traced step graph host-readout-free (no aten::item): {no_readout}")

    # (3): differentiable — gradient flows from the written cell back into ram.
    ram_g = torch.zeros(N, DIM, dtype=torch.float64, requires_grad=True)
    out_g = step(ram_g, make_real(3.0))
    out_g[3, AXIS_REAL].backward()
    # d(out[3].real)/d(ram[3].real) = 1 (cell read, +1, written back).
    grad_33 = float(ram_g.grad[3, AXIS_REAL])
    print(f"gradient d(out[3].real)/d(ram[3].real) = {grad_33} (want 1.0)")

    ok = abs(val - 42.0) < 1e-9 and no_readout and abs(grad_33 - 1.0) < 1e-9
    if not ok:
        print("FAIL: RAM-tensor step mismatch")
        return 1
    print("PASS: RAM as a single VRAM tensor with gather/scatter access is "
          "readout-free, traceable into one graph, and differentiable. This is the "
          "representation the machine-fusion codegen change targets (ram_read/write "
          "-> index_select/index_copy over a threaded RAM tensor).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
