"""Figure generation for the a1 GUI paper (queue item P8).

Renders the paper's figures from the SAME substrate code paths the demo uses and
saves them as PNGs under `paper/gui-steering/figures/` (a build-artifact directory,
git-ignored — regenerate, do not commit). Figures:

  fig_hero_mono.png      the θ hero, single brightness field (frame_hero.su)
  fig_hero_rgb.png       the θ hero, RGB tinted (hero_channel x3)
  fig_banner.png         a substrate glyph headline banner
  fig_quad.png           the four-quadrant layout (glow/ring/diag/checker)
  fig_steer_before.png   the hero at the neutral start θ
  fig_steer_after.png    the hero after a brighter-preferring steering session

Every pixel in every figure is substrate output; the host only clamps to [0,1] and
writes the PNG (the display boundary).

    python experiments/gui_figures.py            # default size 96
    python experiments/gui_figures.py --size 128
"""
from __future__ import annotations

import argparse
import importlib.util
import pathlib

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parent.parent
_DEMO_GUI = _REPO / "demos" / "gui"
_OUT = _REPO / "paper" / "gui-steering" / "figures"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _save_gray(field, path):
    from PIL import Image
    v = np.clip(np.asarray(field, dtype=float), 0.0, 1.0)
    Image.fromarray((v * 255.0).astype(np.uint8)).save(path)   # 2D -> mode L inferred


def _save_rgb(img, path):
    from PIL import Image
    v = np.clip(np.asarray(img, dtype=float), 0.0, 1.0)
    Image.fromarray((v * 255.0).astype(np.uint8)).save(path)   # HxWx3 -> RGB inferred


def generate(size: int = 96) -> list:
    """Render and save all figures. Returns a list of (name, path, shape)."""
    wf = _load("gui_whole_frame_fig", _DEMO_GUI / "whole_frame.py")
    steer = _load("gui_hero_steering_fig", _DEMO_GUI / "hero_steering.py")
    _OUT.mkdir(parents=True, exist_ok=True)
    out = []

    # A photogenic, on-screen θ for the static hero figures.
    th = {"cx": -0.15, "cy": -0.1, "invs": 1.1, "bright": 1.2, "radius": 0.55,
          "accent": 0.45, "bg": 0.12, "cr": 1.0, "cg": 0.7, "cb": 0.35,
          "headline_w": [1.0, 0.0, 0.0, 0.0]}

    hero_mono, _ = wf.render_hero_with_headline(size, th)
    _save_gray(hero_mono, _OUT / "fig_hero_mono.png")
    out.append(("hero mono", _OUT / "fig_hero_mono.png", hero_mono.shape))

    hero_img, headline = wf.render_hero_full(size, th)
    _save_rgb(hero_img, _OUT / "fig_hero_rgb.png")
    out.append((f"hero rgb (headline {headline!r})", _OUT / "fig_hero_rgb.png", hero_img.shape))

    banner = wf.render_headline_banner("SUTRA")
    _save_gray(banner, _OUT / "fig_banner.png")
    out.append(("glyph banner 'SUTRA'", _OUT / "fig_banner.png", banner.shape))

    quad = wf.render_quad(size)
    _save_gray(quad, _OUT / "fig_quad.png")
    out.append(("four-quadrant layout", _OUT / "fig_quad.png", quad.shape))

    # Before/after a brighter-preferring steering session (the steering figure pair).
    ctl = steer.HeroSteering(size=size, seed=0, render_headline=True)
    before, _ = ctl.frame()
    _save_rgb(before, _OUT / "fig_steer_before.png")
    out.append(("steer before (neutral)", _OUT / "fig_steer_before.png", before.shape))
    for _ in range(120):
        shown = ctl.current_theta()["bright"]
        ref = ctl.best_theta()["bright"]
        ctl.press(steer.WARMER if shown >= ref else steer.COLDER)
    after, _ = wf.render_hero_full(size, ctl.best_theta())
    _save_rgb(after, _OUT / "fig_steer_after.png")
    out.append(("steer after (brighter)", _OUT / "fig_steer_after.png", after.shape))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="a1 paper figures (item P8).")
    ap.add_argument("--size", type=int, default=96)
    args = ap.parse_args()
    rows = generate(args.size)
    print(f"wrote {len(rows)} figures to {_OUT}:")
    for name, path, shape in rows:
        kb = path.stat().st_size / 1024.0
        print(f"  {name:<32} {path.name:<22} {str(shape):<14} {kb:.1f} KB")


if __name__ == "__main__":
    main()
