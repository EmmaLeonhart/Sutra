"""Tests for the hero web bridge's pure core (hero_server.frame_to_png).

The HeroSteering controller is covered by test_hero_steering.py and the substrate
render is slow, so CI exercises only the pure, browser-free part here: turning a
substrate frame into PNG bytes. The HTTP serving + the live page are I/O and are
verified by running the server in a browser, not in CI.
"""
import importlib.util
import pathlib

import numpy as np

_DIR = pathlib.Path(__file__).resolve().parent


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, _DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


hero_server = _load("gui_hero_server", "hero_server.py")


def _is_png(b: bytes) -> bool:
    return b[:8] == b"\x89PNG\r\n\x1a\n"


def test_frame_to_png_returns_png_bytes():
    img = np.zeros((8, 8, 3), dtype=float)
    img[2:6, 2:6, 0] = 1.0  # a red square
    png = hero_server.frame_to_png(img, scale=4)
    assert _is_png(png)
    assert len(png) > 0


def test_frame_to_png_scale_upscales_dimensions():
    from PIL import Image
    import io

    img = np.zeros((6, 10, 3), dtype=float)
    png = hero_server.frame_to_png(img, scale=5)
    w, h = Image.open(io.BytesIO(png)).size
    assert (w, h) == (10 * 5, 6 * 5)  # (W*scale, H*scale)


def test_frame_to_png_clamps_out_of_range():
    # values outside [0,1] must not crash or wrap; they clamp.
    img = np.full((4, 4, 3), 5.0, dtype=float)
    img[0, 0, :] = -3.0
    png = hero_server.frame_to_png(img, scale=1)
    assert _is_png(png)


def test_frame_to_png_rejects_non_rgb():
    try:
        hero_server.frame_to_png(np.zeros((4, 4), dtype=float))
    except ValueError:
        return
    raise AssertionError("expected ValueError for non-(H,W,3) input")
