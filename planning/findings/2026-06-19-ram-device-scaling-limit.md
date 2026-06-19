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

## What a fix needs — DIRECT RAM, not Python (Emma 2026-06-19)

**The RAM device cannot be a Python container.** A first cut tried a sparse Python `dict` storing
host floats for scalar cells — rejected: that is still Python host storage (a host `dict` of host
`float`s), the exact thing RAM must not be. Emma's direction: **RAM needs to be a DIRECT memory
device — a flat tensor as real linear memory, WASM-backed if necessary** — not a `list`/`dict` of
per-cell vectors. The per-cell-d-vector list AND the dict-of-floats are both wrong; the linear
memory should be one contiguous tensor (or a WASM linear-memory region) addressed directly.

This is no longer a localized frontend/runtime tweak: it is part of the **comprehensive substrate
audit** Emma scoped (2026-06-19), which runs **after the FV paper review**. The audit must settle how
RAM/linear-memory is represented as a direct substrate object, reconciled with: the external
orchestrator contract (iso5 / ntm_ram attach `self.ram` and index it — see `test_ntm_ram.py`), the
attention-on-RAM VRAM-vector path, and the WASM linear-memory model. Getting it wrong silently
corrupts either the byte-buffer or the VRAM-vector path, so it ships with substrate-to-substrate
verification on BOTH — and it is NOT to be rearchitected autonomously as a Python container.

Related: the separate `non-zero Array.make fill` item (slots start at 0) is a documented limit, not a
bug, and orthogonal to this scaling rework.
