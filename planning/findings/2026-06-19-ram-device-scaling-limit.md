# RAM device does not scale to a 10MB linear memory — two compounding costs

**Date:** 2026-06-19
**Status:** root-caused, NOT fixed — a deliberate, safety-critical rework of the shared
runtime RAM device, deprioritized by Emma this session (she greenlit Q5 over it). Logged so
a future dedicated session starts from the precise costs rather than "doesn't scale."

## Symptom

The OCaml frontend routes `Bytes.make` (raw linear memory) and loop-carried arrays to the
global RAM device (`_RAM_ARRAYS`, base spaced by `_RAM_STRIDE = 4096`; `a.(i)` → `ramRead(base+i)`,
`a.(i) <- v` → `ramWrite`). A `Bytes.make` of the 10MB linear-memory shape the WASM/attention
work wants does not fit.

## The two compounding costs (measured against the runtime in `codegen_pytorch.py`)

The RAM device is `self.ram`, a **Python list of number-VECTORS**. `ram_write(ptr, value)`
(`codegen_pytorch.py` ~2019) decodes the address and does:

```python
while len(self.ram) <= addr:
    self.ram.append(self.zero_vector())   # pre-grow to the max address
self.ram[addr] = val_vec
```

`ram_read` returns `self.ram[addr]` (the stored vector), or `zero_vector()` OOB.

1. **Pre-grow to the max address.** Writing address `N` grows the list to `N+1` entries, each a
   `zero_vector()`. A `Bytes.make(10_000_000)` (or a write at a high `base+i`) pre-allocates 10M+
   entries before storing anything.
2. **A full d-dim vector per cell.** Each cell is a d-dim `torch.Tensor` (default `runtime_dim`
   ~868). 10M cells × 868 floats × 4 bytes ≈ **35 GB**. A linear-memory byte buffer holds *bytes*
   (0–255 scalars), so all but the real axis is wasted — the value is carried only on `AXIS_REAL`.

Either cost alone makes a 10MB buffer infeasible; together they are ~35 GB + a 10M-element Python
list.

## What a fix needs (and why it is not a few-cycles edit)

- **Compact per-cell storage for scalar cells.** A `Bytes`/numeric RAM cell is one scalar; store a
  flat real-axis tensor (1 float/cell → ~40 MB for 10M) and reconstruct `make_real(scalar)` on read,
  instead of a d-vector per cell. BUT the attention-on-RAM path stores genuine VRAM *vectors* in RAM
  (number-vectors with content beyond the real axis), so the device cannot blanket-assume scalar
  cells — it needs a per-cell or per-region representation discriminator.
- **Lazy/sparse allocation.** Replace pre-grow-to-`addr` with a sparse map or a sized-on-declare
  tensor, so a high base address does not pre-allocate everything below it.

This is a careful change to the **shared, safety-critical** RAM device (every program with RAM uses
it, including the "hard attention-on-RAM parsers" the OCaml comment flags). Getting the
representation discriminator wrong silently corrupts either the byte-buffer or the VRAM-vector path.
Per the integrity rules (substrate correctness is non-negotiable), this is a deliberate session with
substrate-to-substrate verification on BOTH the byte-buffer and attention-on-RAM cases — not a
work-loop tick, and not to be rearchitected autonomously without a green light.

Related: the separate `non-zero Array.make fill` item (slots start at 0) is a documented limit, not a
bug, and orthogonal to this scaling rework.
