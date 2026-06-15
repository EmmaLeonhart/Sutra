"""Steering evaluation for the a1 hero demo (queue item 1d).

A scripted warmer/colder SOAK over `demos/gui/hero_steering.HeroSteering`, the
host-side-SPSA-over-substrate-render loop. It measures the two properties the demo
must have:

  (1) **No NaN/blank frames across a long session.** Every frame is rendered on the
      substrate and guarded (`HeroSteering.frame` raises on non-finite or all-zero
      pixels), so a clean N-press run means N/N good frames.
  (2) **Directionally-consistent morphing.** A *consistent* rater (always prefers
      brighter, or always prefers darker) should move the steered parameter
      monotonically in the rewarded direction. We report the Pearson correlation of
      the running-best brightness against the batch index and the net change; a
      consistent rater should give a strong-signed correlation and a clear delta.

This is the measurement behind paper §7 / task P7. Honesty (a1 spec): the render is
substrate (colour channels + glyph pixels); the optimizer and the warmer/colder
bookkeeping are host-side. This is steering of substrate-rendered output by a
(here synthetic) rater — NOT substrate-native training, NOT learning from traffic.

    python experiments/gui_steering_eval.py                 # default 100-press soak
    python experiments/gui_steering_eval.py --presses 200   # longer
    python experiments/gui_steering_eval.py --no-headline   # skip the glyph overlay
"""
from __future__ import annotations

import argparse
import importlib.util
import pathlib

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parent.parent
_DEMO_GUI = _REPO / "demos" / "gui"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _pearson(x, y) -> float:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if x.std() < 1e-12 or y.std() < 1e-12:
        return 0.0
    return float(np.corrcoef(x, y)[0, 1])


def run_soak(presses: int = 100, size: int = 48, seed: int = 0,
             headline: bool = True, prefer: str = "brighter") -> dict:
    """Run a `presses`-press soak with a consistent rater. Returns a metrics dict:
    frames rendered, NaN/blank counts (0 if the guard never tripped), the
    best-brightness trajectory, its Pearson correlation vs batch index, and the net
    brightness change. `prefer` is 'brighter' or 'darker'."""
    steer = _load("gui_hero_steering_eval", _DEMO_GUI / "hero_steering.py")
    ctl = steer.HeroSteering(size=size, seed=seed, render_headline=headline)

    sign = 1.0 if prefer == "brighter" else -1.0
    frames = 0
    nan_count = 0
    blank_count = 0
    traj = [ctl.best_theta()["bright"]]

    # Confirm the first frame is clean (frame() raises on NaN/blank; we count
    # instead of crashing so a bad run is reported, not hidden).
    try:
        img, _ = ctl.frame()
        frames += 1
        if not np.all(np.isfinite(img)):
            nan_count += 1
        if float(np.abs(img).max()) <= 0.0:
            blank_count += 1
    except (FloatingPointError, ValueError):
        nan_count += 1

    for _ in range(presses):
        # Consistent rater: reward warmer when the shown perturbation is brighter
        # (or darker, if prefer='darker') than the running best — a pure, stable
        # brightness preference expressed on the rendered θ being shown.
        shown = ctl.current_theta()["bright"]
        ref = ctl.best_theta()["bright"]
        warmer = (shown >= ref) if sign > 0 else (shown <= ref)
        try:
            img, _ = ctl.press(steer.WARMER if warmer else steer.COLDER)
            frames += 1
            if not np.all(np.isfinite(img)):
                nan_count += 1
            if float(np.abs(img).max()) <= 0.0:
                blank_count += 1
        except (FloatingPointError, ValueError):
            nan_count += 1
        traj.append(ctl.best_theta()["bright"])

    idx = list(range(len(traj)))
    corr = _pearson(idx, traj)
    return {
        "presses": presses, "frames_rendered": frames,
        "nan_count": nan_count, "blank_count": blank_count,
        "prefer": prefer, "bright_start": traj[0], "bright_final": traj[-1],
        "bright_delta": traj[-1] - traj[0], "trend_corr": corr,
        "trajectory": traj,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="a1 hero steering soak (item 1d).")
    ap.add_argument("--presses", type=int, default=100)
    ap.add_argument("--size", type=int, default=48)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--no-headline", action="store_true",
                    help="skip the substrate glyph headline overlay (faster)")
    args = ap.parse_args()
    headline = not args.no_headline

    print(f"a1 steering soak: presses={args.presses} size={args.size} "
          f"headline={'on' if headline else 'off'}")
    for prefer in ("brighter", "darker"):
        m = run_soak(args.presses, args.size, args.seed, headline, prefer)
        print(f"\n[rater prefers {prefer}]")
        print(f"  frames rendered : {m['frames_rendered']}")
        print(f"  NaN frames      : {m['nan_count']}")
        print(f"  blank frames    : {m['blank_count']}")
        print(f"  bright start    : {m['bright_start']:.3f}")
        print(f"  bright final    : {m['bright_final']:.3f}")
        print(f"  bright delta    : {m['bright_delta']:+.3f}")
        print(f"  trend corr      : {m['trend_corr']:+.3f}  "
              f"(batch index vs running-best brightness)")


if __name__ == "__main__":
    main()
