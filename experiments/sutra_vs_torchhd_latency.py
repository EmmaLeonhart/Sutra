"""Quantitative latency comparison: Sutra (compiled) vs TorchHD (library).

Why this experiment exists:
    Reviewers across posts 2191, 2193, 2195, 2197, 2198 have
    repeatedly asked for quantitative benchmarks against
    established neuro-symbolic baselines (Scallop, DeepProbLog).
    Scallop is not pip-installable (Rust source build, hours);
    DeepProbLog and Logic Tensor Networks are probabilistic logic
    programming systems that take *neural facts* and run logical
    inference, which is a different workload than Sutra's VSA
    record encode/decode. The closest apples-to-apples baseline is
    TorchHD, which is also VSA-on-PyTorch. This experiment runs
    the *same* role-filler record encode + decode task in both
    systems and measures mean per-call latency.

    The expected result: Sutra's steady-state latency should be
    lower than TorchHD's per-call latency because Sutra compiles
    the program once into a fused tensor-op graph, while TorchHD
    re-dispatches each library call from Python every time. The
    absolute numbers depend on hardware; the *relative* number
    (Sutra/TorchHD ratio) is the meaningful figure.

What this measures:
    Task: build a 3-field record (name, color, shape), bundle the
    bind(role, filler) terms into one vector, then decode one
    field by unbinding and argmax-cosining against a 6-entry
    filler codebook. Same task as examples/role_filler_record.su
    and experiments/role_filler_record_torchhd.py.

    Both systems use 768-dim hypervectors; rotation binding
    (Sutra) vs Hadamard binding (TorchHD's MAP-VSA default).
    We measure first-call latency (cold) and mean steady-state
    latency over 1000 calls.

Reproducible: seeded RNG, fixed dims, deterministic substrates.

Usage:
    pip install torch torchhd
    python experiments/sutra_vs_torchhd_latency.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torchhd

DIM = 768
N_WARMUP = 50
N_TRIALS = 1000


# ---------------------------------------------------------------------
# TorchHD implementation — library style, host-side control flow
# ---------------------------------------------------------------------

def torchhd_setup():
    torch.manual_seed(42)
    role_names = ["name", "color", "shape"]
    filler_names = ["alice", "bob", "red", "blue", "circle", "square"]
    roles = {n: torchhd.random(1, DIM, vsa="MAP") for n in role_names}
    fillers = {n: torchhd.random(1, DIM, vsa="MAP") for n in filler_names}
    codebook = torch.cat([fillers[n] for n in filler_names], dim=0)
    return roles, fillers, codebook, filler_names


def torchhd_decode(roles, fillers, codebook, filler_names) -> str:
    """One full encode + decode call. Same shape as the .su program."""
    bound_name = torchhd.bind(roles["name"], fillers["alice"])
    bound_color = torchhd.bind(roles["color"], fillers["red"])
    bound_shape = torchhd.bind(roles["shape"], fillers["circle"])
    record = torchhd.bundle(bound_name,
                            torchhd.bundle(bound_color, bound_shape))
    recovered = torchhd.bind(record, torchhd.inverse(roles["color"]))
    sims = torchhd.cosine_similarity(recovered, codebook)
    return filler_names[int(torch.argmax(sims))]


# ---------------------------------------------------------------------
# Sutra implementation — compile the .su once, then call repeatedly
# ---------------------------------------------------------------------

def sutra_setup():
    """Compile the .su program to an in-memory Python module."""
    sutra_compiler_dir = Path(__file__).resolve().parent.parent / "sdk" / "sutra-compiler"
    sys.path.insert(0, str(sutra_compiler_dir))
    examples_dir = Path(__file__).resolve().parent.parent / "examples"
    sys.path.insert(0, str(examples_dir))

    from _su_harness import compile_to_module  # noqa: E402
    src_path = examples_dir / "role_filler_record.su"
    t_compile_start = time.monotonic()
    mod = compile_to_module(str(src_path))
    t_compile_end = time.monotonic()
    return mod, t_compile_end - t_compile_start


def sutra_decode(mod) -> str:
    return mod.main()


# ---------------------------------------------------------------------
# Timing harness
# ---------------------------------------------------------------------

def time_calls(fn, args, n_warmup, n_trials):
    """Returns (cold_first_call_us, mean_steady_us, std_steady_us)."""
    # Cold first call (includes first-call overhead).
    t0 = time.monotonic_ns()
    fn(*args)
    cold = (time.monotonic_ns() - t0) / 1e3  # microseconds

    # Warmup.
    for _ in range(n_warmup):
        fn(*args)

    # Steady-state timed.
    timings = []
    for _ in range(n_trials):
        t0 = time.monotonic_ns()
        fn(*args)
        timings.append((time.monotonic_ns() - t0) / 1e3)
    arr = np.array(timings)
    return cold, float(arr.mean()), float(arr.std())


def main() -> int:
    print("=" * 78)
    print("Sutra vs TorchHD latency comparison")
    print(f"task: 3-field role-filler record encode + decode")
    print(f"dim: {DIM}, warmup: {N_WARMUP}, trials: {N_TRIALS}")
    print("=" * 78)

    # Sutra: compile once, then time.
    print("\n[Sutra]")
    print("  compiling examples/role_filler_record.su ...")
    mod, compile_s = sutra_setup()
    print(f"  compile time: {compile_s * 1000:.1f} ms (one-time cost)")
    # Sanity check: does the compiled program produce the right answer?
    result = sutra_decode(mod)
    print(f"  sanity: decode color field -> {result!r}")
    assert result == "red", f"Sutra returned {result!r}"
    sutra_cold, sutra_mean, sutra_std = time_calls(
        sutra_decode, (mod,), N_WARMUP, N_TRIALS
    )
    print(f"  cold first call:    {sutra_cold:>9.1f} us")
    print(f"  steady-state mean:  {sutra_mean:>9.1f} us  (std {sutra_std:.1f})")

    # TorchHD: setup, then time.
    print("\n[TorchHD]")
    roles, fillers, codebook, filler_names = torchhd_setup()
    result = torchhd_decode(roles, fillers, codebook, filler_names)
    print(f"  sanity: decode color field -> {result!r}")
    assert result == "red", f"TorchHD returned {result!r}"
    torchhd_cold, torchhd_mean, torchhd_std = time_calls(
        torchhd_decode,
        (roles, fillers, codebook, filler_names),
        N_WARMUP, N_TRIALS,
    )
    print(f"  cold first call:    {torchhd_cold:>9.1f} us")
    print(f"  steady-state mean:  {torchhd_mean:>9.1f} us  (std {torchhd_std:.1f})")

    # Comparison.
    print("\n" + "=" * 78)
    print("SUMMARY")
    print("=" * 78)
    speedup = torchhd_mean / sutra_mean if sutra_mean > 0 else float("inf")
    print(f"  steady-state Sutra / TorchHD ratio: "
          f"{sutra_mean / torchhd_mean:.3f}x")
    print(f"  steady-state speedup (TorchHD / Sutra): {speedup:.2f}x")
    print(f"  Sutra compile cost: {compile_s * 1000:.1f} ms (amortized once)")
    print(f"  Sutra break-even after "
          f"{int(compile_s * 1e6 / max(torchhd_mean - sutra_mean, 1e-6))} calls "
          f"(if Sutra is faster steady-state)")

    # Persist for the paper.
    out_path = Path(__file__).resolve().parent / "sutra_vs_torchhd_latency_results.json"
    out_path.write_text(json.dumps({
        "dim": DIM,
        "warmup": N_WARMUP,
        "trials": N_TRIALS,
        "sutra": {
            "compile_ms": compile_s * 1000,
            "cold_us": sutra_cold,
            "steady_mean_us": sutra_mean,
            "steady_std_us": sutra_std,
        },
        "torchhd": {
            "cold_us": torchhd_cold,
            "steady_mean_us": torchhd_mean,
            "steady_std_us": torchhd_std,
        },
        "speedup_steady": speedup,
    }, indent=2), encoding="utf-8")
    print(f"\nResults written to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
