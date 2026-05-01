"""Profile what PyTorch dispatches when the emitted hello_world runs.

Two passes:
  1) Module import (codebook embed, mean-center/norm, rotation prewarm)
  2) main() — argmax_cosine over the 3 candidate vectors

Each pass is wrapped in torch.profiler so we get the ATen-op call list
plus the CUDA kernel-launch times. Output goes to stdout and a Chrome-
trace JSON for inspection in chrome://tracing or perfetto.
"""
from __future__ import annotations
import importlib.util
import os
import sys
from pathlib import Path

import torch
from torch.profiler import profile, ProfilerActivity, record_function

EMITTED = Path(__file__).parent / "hello_world_emitted.py"
TRACE_OUT = Path(__file__).parent / "hello_world_trace.json"


def load_emitted_module() -> object:
    spec = importlib.util.spec_from_file_location("hello_world_emitted", EMITTED)
    mod = importlib.util.module_from_spec(spec)
    with record_function("emitted_module_import"):
        spec.loader.exec_module(mod)
    return mod


def main() -> int:
    if not EMITTED.exists():
        print(f"missing {EMITTED} — run --emit first", file=sys.stderr)
        return 1

    activities = [ProfilerActivity.CPU]
    if torch.cuda.is_available():
        activities.append(ProfilerActivity.CUDA)

    # Pass 1: profile import (codebook embed, normalize, rotation prewarm).
    with profile(activities=activities, record_shapes=True) as prof_import:
        mod = load_emitted_module()
        if torch.cuda.is_available():
            torch.cuda.synchronize()

    # Warmup: discard cold-cache effects on the first main() call.
    _ = mod.main()
    if torch.cuda.is_available():
        torch.cuda.synchronize()

    # Pass 2: profile a clean main() call, repeated so per-op times average.
    with profile(activities=activities, record_shapes=True) as prof_main:
        for _ in range(20):
            with record_function("main_call"):
                result = mod.main()
        if torch.cuda.is_available():
            torch.cuda.synchronize()

    print(f"main() returned: {result!r}\n")

    sort_key = "cuda_time_total" if torch.cuda.is_available() else "cpu_time_total"

    print("=" * 78)
    print("PASS 1 — module import (one-shot init: embed, normalize, prewarm)")
    print("=" * 78)
    print(prof_import.key_averages().table(sort_by=sort_key, row_limit=20))

    print("=" * 78)
    print("PASS 2 — main() hot path (20 calls, post-warmup)")
    print("=" * 78)
    print(prof_main.key_averages().table(sort_by=sort_key, row_limit=20))

    prof_main.export_chrome_trace(str(TRACE_OUT))
    print(f"\nchrome trace (main hot path) -> {TRACE_OUT}")
    print("open in chrome://tracing or https://ui.perfetto.dev")
    return 0


if __name__ == "__main__":
    sys.exit(main())
