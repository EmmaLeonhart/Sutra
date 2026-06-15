"""Render-fidelity table for the a1 GUI paper (queue item P6).

For each whole-frame render mode, measure the maximum absolute difference between
the ONE-substrate-op render and a per-pixel host oracle. Every render here runs on
the substrate (frame_*.su / frame_hero.su); the oracle is plain host arithmetic.
The point of the table is that the substrate computes the intended field to within
a tiny numerical tolerance — i.e. the geometry really is the substrate's, not the
host's. The glyph banner is checked for EXACT equality to the concatenated
substrate glyph fields (no host font table).

This produces the §6 numbers in `paper/gui-steering/paper.md` (cite the measured
maxima, not the regression threshold).

    python experiments/gui_render_fidelity.py            # default size 24
    python experiments/gui_render_fidelity.py --size 32
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


def _grid(size):
    xs = np.array([[2.0 * i / (size - 1) - 1.0 for i in range(size)] for _ in range(size)])
    ys = np.array([[2.0 * j / (size - 1) - 1.0 for _ in range(size)] for j in range(size)])
    return xs, ys


def measure(size: int = 24) -> list:
    """Return a list of (mode, max_abs_error) rows."""
    wf = _load("gui_whole_frame_fid", _DEMO_GUI / "whole_frame.py")
    x, y = _grid(size)
    R = 0.5
    rows = []

    def err(got, ref):
        return float(np.abs(np.asarray(got) - np.asarray(ref)).max())

    # whole: 1 - x^2 - y^2
    rows.append(("whole (1-x^2-y^2)", err(wf.render_field_whole(size), 1.0 - x * x - y * y)))
    # moving glow centred at cx=0.3
    cx = 0.3
    rows.append(("moving glow", err(wf.render_field_moving(size, cx),
                                    1.0 - (x - cx) ** 2 - y * y)))
    # ring: 1 - (x^2+y^2-R)^2
    rows.append(("ring", err(wf.render_field_ring(size, R),
                             1.0 - (x * x + y * y - R) ** 2)))
    # diagonal ramp
    rows.append(("diag", err(wf.render_diag(size), 0.5 * (1.0 + 0.5 * (x + y)))))
    # region layout: glow on the left, ring on the right
    lay = wf.render_layout(size, R)
    lay_ref = np.where(x < 0.0, 1.0 - x * x - y * y, 1.0 - (x * x + y * y - R) ** 2)
    rows.append(("layout (glow|ring)", err(lay, lay_ref)))
    # RGB channels: R=glow, G=ring, B=(x+1)/2
    img = wf.render_rgb(size, R)
    rgb_ref = np.stack([1.0 - x * x - y * y, 1.0 - (x * x + y * y - R) ** 2,
                        (x + 1.0) / 2.0], axis=-1)
    rows.append(("rgb (3 channels)", err(img, rgb_ref)))
    # theta hero (a non-default theta) vs the bg+bright*glow+accent*ring oracle
    th = {"cx": 0.2, "cy": -0.1, "invs": 1.3, "bright": 0.9, "radius": 0.4,
          "accent": 0.4, "bg": 0.1, "cr": 0.8, "cg": 0.5, "cb": 0.3}
    glow = 1.0 - th["invs"] * ((x - th["cx"]) ** 2 + (y - th["cy"]) ** 2)
    ring = 1.0 - (x * x + y * y - th["radius"]) ** 2
    mono = th["bg"] + th["bright"] * glow + th["accent"] * ring
    rows.append(("hero (theta)", err(wf.render_hero(size, th), mono)))
    # theta hero RGB: mono * per-channel tint
    himg = wf.render_hero_rgb(size, th)
    hrgb_ref = np.stack([mono * th["cr"], mono * th["cg"], mono * th["cb"]], axis=-1)
    rows.append(("hero rgb (theta)", err(himg, hrgb_ref)))
    # glyph banner: EXACT equality to concatenated substrate glyph fields
    font = _load("gui_font_demo_fid", _REPO / "demos" / "font" / "font_demo.py")
    banner = wf.render_headline_banner("SU")
    banner_ref = np.concatenate([font.render_glyph(float(ord("S"))),
                                 font.render_glyph(float(ord("U")))], axis=1)
    rows.append(("glyph banner 'SU' (exact)", err(banner, banner_ref)))
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description="a1 render-fidelity table (item P6).")
    ap.add_argument("--size", type=int, default=24)
    args = ap.parse_args()
    rows = measure(args.size)
    print(f"render-fidelity (size {args.size}x{args.size}); "
          f"max |substrate - host oracle| per mode\n")
    width = max(len(m) for m, _ in rows)
    for mode, e in rows:
        print(f"  {mode:<{width}} : {e:.2e}")
    print(f"\n  overall max: {max(e for _, e in rows):.2e}")


if __name__ == "__main__":
    main()
