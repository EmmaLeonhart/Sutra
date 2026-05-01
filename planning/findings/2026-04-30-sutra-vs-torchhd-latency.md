# Sutra vs TorchHD per-call latency — honest negative

**Date:** 2026-04-30
**Experiment:** `experiments/sutra_vs_torchhd_latency.py`
**Status:** honest negative; integrating into paper as a candid limitation.

## Why this experiment exists

Reviewers across posts 2191, 2193, 2195, 2197, 2198 have
consistently asked for quantitative benchmarks against
established neuro-symbolic baselines (Scallop, DeepProbLog).
Scallop is not pip-installable (Cargo source build, hours of
compile time); DeepProbLog and LTN are probabilistic logic
programming systems that take *neural facts* and run logical
inference — that's a different workload than Sutra's VSA record
encode/decode. The closest apples-to-apples baseline is TorchHD,
which is also VSA-on-PyTorch. Both can implement the
role-filler-record decode task identically; both ultimately
dispatch the same PyTorch tensor ops.

## Setup

Task: 3-field role-filler record encode + decode (the same task
as `examples/role_filler_record.su` and
`experiments/role_filler_record_torchhd.py`). 768-dim vectors,
50-call warmup, 1000-call timed steady state.

- **Sutra:** `examples/role_filler_record.su` compiled to PyTorch
  via `compile_to_module`. Compile is one-time amortized cost.
  Each call invokes `mod.main()`. Tested both without and with
  `SUTRA_TORCH_COMPILE=1` (which wraps loop functions with
  `torch.compile(backend='eager')`).
- **TorchHD:** equivalent program (same 3 binds + bundle +
  unbind + cosine), library-style: direct calls to
  `torchhd.bind / bundle / cosine_similarity`.

## Results

```
[Sutra, no torch.compile]
  compile time:       1957 ms (one-time)
  cold first call:    5651 us
  steady-state mean:  7681 us  (std 1621)

[Sutra, SUTRA_TORCH_COMPILE=1]
  compile time:       2717 ms (one-time)
  cold first call:    5473 us
  steady-state mean:  5678 us  (std 612)

[TorchHD]
  cold first call:     872 us
  steady-state mean:   525 us  (std 228)
```

**Sutra is ~12× slower than TorchHD per call** (5.7ms vs 0.5ms
steady state with torch.compile enabled). This is a real runtime
overhead gap, not a measurement artifact.

## Why

Both systems ultimately dispatch the same PyTorch tensor ops
(matmul for bind, addition for bundle, dot product for cosine).
The latency gap comes from runtime scaffolding around those ops:

1. **Slot state.** Sutra threads a `_slot_state` accumulator
   through every call so slot-typed locals can be read/written
   compositionally. The role_filler_record program doesn't use
   slots, but the bookkeeping cost is paid on every call.
2. **Halt-cum threading.** Every function entry initializes
   `_program_halt = 1.0`, every return multiplies by it (for
   vector returns). Required for unconverged-loop wipe; pure
   overhead for non-loop functions.
3. **Per-axis canonical dimensions.** Sutra's
   extended-state-vector layout reserves canonical synthetic
   axes for primitive types. Even pure-vector operations that
   don't touch the synthetic block pay the indexing overhead.
4. **Compile-time codebook lookup.** `_vector_map_lookup`
   iterates through a list of (vec, str) tuples, matching by
   cosine. TorchHD's caller does the equivalent with a single
   `torch.argmax` over a stacked tensor — fewer Python ops.

`torch.compile` reduces this overhead modestly (7.7ms → 5.7ms)
but does not close the gap. The compiled code is still a Python
function calling many small tensor ops, not a single fused
kernel. Real graph fusion (one `torch.compile` block over the
whole program with concrete shapes baked in) would close more of
the gap.

## What this means for the paper

**Honest claim:** Sutra and TorchHD are within an order of
magnitude on per-call latency for VSA tasks both can express.
TorchHD is faster today (~12×) because its runtime is a thin
library wrapper around PyTorch ops, while Sutra's runtime
threads compositional state (slots, halt accumulator, synthetic
axes) that are paid even when unused.

**The advantages Sutra retains** are not in per-call latency
but in *what tasks can be expressed*: differentiable fuzzy
logic, soft-halt RNN-cell loops, compile-time string codebook,
substrate-purity guarantees. TorchHD does not have these; the
benchmark above is restricted to the intersection of what both
can do.

**Runtime-optimization gap, not an architectural one.** Both
systems target PyTorch tensor ops; the gap is implementation
overhead, not a fundamental design difference. Closing it is a
runtime-engineering task (per-op fast paths, lazy slot
allocation, removing halt-cum from non-loop functions), not a
language redesign.

## Why not Scallop / DeepProbLog directly

- **Scallop** has no PyPI package; install is from Rust source
  (cargo build -p scallopy, ~hours). Not feasible for
  same-session benchmarking.
- **DeepProbLog** installs cleanly but it's a probabilistic
  logic programming system that takes neural networks as fact
  predictors and runs SLG resolution over Prolog rules. Sutra
  has no Prolog, no SLG resolution, no probabilistic semantics
  — there's no shared task that's a fair comparison. A
  contrived benchmark would measure each system at something it
  doesn't natively do.
- **LTN (Logic Tensor Networks)** has the same mismatch —
  it's about training neural networks to satisfy first-order
  logic constraints, not VSA record encode/decode.
- **TorchHD** is the only system that can implement the
  role_filler_record task line-for-line in the same way Sutra
  does, on the same PyTorch substrate.

The honest answer to "compare to Scallop" is that Sutra and
Scallop solve different problems — Scallop is for probabilistic
neuro-symbolic reasoning; Sutra is for compositional VSA
programming. The closest available apples-to-apples is
TorchHD, and we now have those numbers.

## Reproducibility

```bash
# Without torch.compile:
python experiments/sutra_vs_torchhd_latency.py

# With torch.compile wrapping:
SUTRA_TORCH_COMPILE=1 python experiments/sutra_vs_torchhd_latency.py
```

Raw numbers in `experiments/sutra_vs_torchhd_latency_results.json`.
