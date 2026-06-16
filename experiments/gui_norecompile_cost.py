"""Measure the no-recompile property of runtime-parameter substrate rendering.

The whole-frame hero render (`demos/gui/frame_hero.su`) is compiled ONCE; the
parameter vector theta is supplied as per-call broadcast buffers, so an optimizer
morphs the picture by changing call arguments, not code. This script quantifies
that claim — the basis for the "uniformity / no recompilation" argument in the
gui-steering paper:

  - the one-time compile cost,
  - the mean per-frame substrate-render cost over many DISTINCT theta values,
  - the number of recompiles incurred while theta changes (must be 0).

A steering session of N presses renders ~N frames at distinct theta; this shows
the compile cost is paid once and amortizes away, while each theta update is a
plain substrate render. Host-side timing of a host-side property (compilation and
call dispatch) — not a substrate operation; reported as such.

    python experiments/gui_norecompile_cost.py --frames 200 --size 64
"""
from __future__ import annotations

import argparse
import pathlib
import random
import sys
import time

_REPO = pathlib.Path(__file__).resolve().parent.parent
_GUI = _REPO / "demos" / "gui"
if str(_GUI) not in sys.path:
    sys.path.insert(0, str(_GUI))


def main() -> None:
    ap = argparse.ArgumentParser(description="no-recompile cost of runtime-parameter rendering")
    ap.add_argument("--frames", type=int, default=200)
    ap.add_argument("--size", type=int, default=64)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    import whole_frame as wf

    # 1) one-time compile cost (first _hero_module() call compiles + caches).
    t0 = time.perf_counter()
    wf._hero_module()
    t_compile = time.perf_counter() - t0

    # Warm one render so kernel-build cost is not charged to the loop below.
    wf.render_hero(args.size, {"bright": 1.0})

    # 2) many renders with DISTINCT theta; track the compiled-module identity to
    #    prove no recompilation happens as theta changes.
    rng = random.Random(args.seed)
    module_ids = set()
    t0 = time.perf_counter()
    for _ in range(args.frames):
        theta = {
            "bright": 0.2 + 1.6 * rng.random(),
            "cx": rng.uniform(-0.5, 0.5),
            "cy": rng.uniform(-0.5, 0.5),
            "radius": rng.uniform(0.1, 0.5),
        }
        wf.render_hero(args.size, theta)
        module_ids.add(id(wf._hero_module()))
    t_render = time.perf_counter() - t0

    n = args.frames
    recompiles = len(module_ids) - 1
    print(f"no-recompile cost ({args.size}x{args.size}, {n} distinct-theta frames)\n")
    print(f"  compile-once                : {t_compile * 1000:8.1f} ms")
    print(f"  mean per-frame render       : {t_render / n * 1000:8.2f} ms")
    print(f"  total render ({n} frames)    : {t_render * 1000:8.1f} ms")
    print(f"  recompiles while theta moved: {recompiles:8d}   (0 == compile paid once)")
    print(f"  distinct compiled modules   : {len(module_ids):8d}")


if __name__ == "__main__":
    main()
