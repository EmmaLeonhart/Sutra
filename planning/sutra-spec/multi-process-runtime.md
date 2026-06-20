# Genuine multi-process Sutra runtime — design (Emma greenlit 2026-06-20)

**Status: design settling, first step decomposed into `queue.md`. Unsettled forks are flagged inline.**

## Why this exists

The current `MultiProcessRuntime` (`sdk/sutra-compiler/sutra_compiler/multi_process.py`) is **misnamed**:
it runs N Sutra programs in **one** Python process over a shared `_VSA`. Its `tick_all` launches each
program's `on_axon` on a separate CUDA stream, but the measured result
(`planning/findings/2026-06-20-tick-all-no-speedup-python-bound.md`) is that this delivers **no speedup**
— a program's per-tick cost is ~98% GIL-bound Python orchestration and only ~2% GPU kernel time, and CUDA
streams overlap only the kernels. After the fusion pass shrank per-tick work (~3× sequential), `tick_all`
got *more* net-negative (0.4–0.6×): the fixed stream overhead now dwarfs the tiny compute.

The finding's conclusion, and Emma's 2026-06-20 choice: **real multi-process throughput needs genuine
parallelism — separate OS processes (each with its own GIL) or GIL release.** Separate OS processes also
deliver what queue §1C asked for (per-process GPU memory isolation, so admitted programs don't all share
one allocation pool). So the two converge: *one mechanism — separate processes — gives both isolation and
throughput.* That is what we build.

## What we keep from the current runtime

- **`ProgramSpec`** (name, source_path, entry_point) — the admission descriptor, unchanged.
- **Deterministic caches.** Every `_VSA` cache (`_codebook`, `_rot_cache`, `_perm_cache`, `_axon_op_cache`)
  is a deterministic function of key strings + seed (established by the §1B serialisation finding:
  "caches are key-deterministic, not state"). **This is load-bearing for multi-process:** each worker
  process can rebuild its caches lazily from the same seed and get bit-identical rotations/codebook — so
  cross-process cache *sharing* is a memory optimisation, never a correctness requirement.
- **The `tick` / `tick_all` API shape** stays as the in-process path; the genuine multi-process runtime is
  a *new* sibling (working name `ProcessPoolRuntime`), not a rewrite — the single-process runtime remains
  correct and useful where N is small or the GIL isn't the bottleneck.

## Design forks (unsettled — resolve as the prototype measures)

**Fork 1 — process model.** *Process-per-program* (one OS process per admitted program; simplest mapping
to Yantra's per-service admission, but N Python interpreters = N× interpreter + codebook memory) vs
*worker pool* (W worker processes, programs assigned round-robin; scales past N≫W, amortises interpreter
cost, but needs a scheduler). **Leaning: worker pool** — it subsumes process-per-program (set W=N) and is
the only shape that scales. First prototype can hardcode W and round-robin.

**Fork 2 — codebook / cache sharing.** *Rebuild-per-process* (each worker builds its own caches lazily;
zero IPC, simplest, correct by determinism; cost = the codebook tensor duplicated in each process's GPU
memory, ~vocab×dim×dtype) vs *CUDA IPC shared codebook* (one codebook tensor, shared read-only across
processes via `cudaIpcGetMemHandle`; saves the duplication but is complex and **Linux-mostly — CUDA IPC is
not supported on Windows**). **Leaning: rebuild-per-process first** (correct everywhere, no platform gate),
add IPC sharing only if codebook memory becomes the constraint and only on Linux/CI.

**Fork 3 — axon passing across the process boundary.** Today axons cross as in-memory torch tensors (same
process). Across processes: *CPU-serialise* (tensor → `cpu().numpy().tobytes()` + dtype/shape → pipe →
reconstruct; simple, portable, but pays a GPU→CPU→GPU round trip per hop) vs *CUDA IPC tensor handles*
(share the GPU tensor across processes; fast, but Linux-mostly and lifetime-fragile). **Leaning:
CPU-serialise first** — portable (works on this Windows clone), and the per-hop CPU cost is measurable;
IPC is a later optimisation gated on it being the bottleneck.

**Fork 4 — platform.** This clone is **Windows**: `multiprocessing` uses *spawn* (re-imports the module
per worker — slow startup, must be import-safe under `if __name__ == "__main__"`), and **CUDA IPC is
unsupported**. So the portable prototype is: worker pool + rebuild-per-process caches + CPU-serialised
axons. The CUDA-IPC optimisations (Forks 2/3) are **CI/Linux-only** follow-ons. The GIL-escape throughput
win is testable on Windows on **CPU tensors** (genuine parallelism, no CUDA needed) and with per-process
CUDA contexts (each worker its own context — more GPU memory, but genuinely parallel launch).

## Verification plan (integrity rules — measure, don't assert)

1. **Throughput — the finding's prediction, tested.** Wall-clock a round of N independent program ticks
   via the worker pool (W processes) vs the single-process sequential `tick` ×N. The finding predicts the
   pool **beats 1.0×** once W>1 and the GIL is no longer serialising orchestration (the opposite of
   `tick_all`'s 0.4–0.95×). Report the real number including the spawn/serialise overhead — if the
   round-trip cost eats the GIL-escape win at small per-program work, that is a negative result to record,
   not hide.
2. **Bit-identical results.** Each worker rebuilds its caches deterministically, so a program's output via
   the pool MUST equal its single-process `tick` output (same seed → same Haar rotations → same graph).
   Pin this — it is the correctness gate that makes rebuild-per-process legitimate.
3. **Isolation.** Confirm one worker's GPU allocations are not visible to another (separate CUDA contexts /
   processes) — the §1C isolation property, measured via `torch.cuda.memory_stats` per process where CUDA
   is available.

## Bounded FIRST step (decomposed into `queue.md`)

A `ProcessPoolRuntime` prototype: spawn W worker processes; each worker compiles its assigned `ProgramSpec`s
(rebuild-per-process caches) and serves ticks; the orchestrator dispatches `(program_name, axon_bytes)` over
a `multiprocessing` queue and collects `axon_bytes` back; CPU-serialised axons; import-safe for spawn. Then
the throughput + bit-identical measurement (verification 1 & 2) on CPU tensors (portable). CUDA-context
isolation and CUDA-IPC sharing are explicit later steps, CI/Linux-gated.

This is deliberately the portable, measurable core — it tests Emma's premise (separate processes escape the
GIL → real throughput) on the machine we have, before any platform-gated IPC work.
