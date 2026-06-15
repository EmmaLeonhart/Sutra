"""Warmer/colder steering controller for the a1 hero demo (item 1c).

Ties the host-side SPSA optimizer (`hero_spsa.HeroSPSA`) to the substrate hero
render (`whole_frame.render_hero_full`) behind a two-button interface. It is
HEADLESS and display-free so the pipeline is testable without a window; the
tkinter shell in `steering_window.py` is a thin driver over this controller.

**Two-sided SPSA over a single button pair.** SPSA needs two scored evaluations
per step (θ+ck·delta and θ−ck·delta). With a human warmer/colder button we get one
scalar per shown frame, so a batch spans TWO presses: the controller shows the +
perturbation and the first press scores it (r₊); it then shows the − perturbation
and the second press scores it (r₋); it runs one `HeroSPSA.update(r₊, r₋)` and
begins the next batch. Reward is +1 (warmer) / −1 (colder).

Honesty (a1 spec): the render is substrate (colour channels + glyph pixels); the
optimizer and the warmer/colder bookkeeping are host-side. This is steering of
substrate-rendered output by a present rater — not substrate-native training, not
learning from real traffic.
"""
from __future__ import annotations

import importlib.util
import pathlib

import numpy as np

_DIR = pathlib.Path(__file__).resolve().parent


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, _DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


WARMER = 1.0
COLDER = -1.0


class HeroSteering:
    """Headless warmer/colder steering loop. Usage:

        ctl = HeroSteering(size=48)
        img, headline = ctl.frame()        # current frame to show (substrate render)
        img, headline = ctl.press(WARMER)  # rate it; returns the next frame
        ...

    `batches_done` counts completed SPSA steps (one per two presses)."""

    def __init__(self, size: int = 48, seed: int = 0, band: tuple = (0.08, 0.30),
                 render_headline: bool = True):
        self._wf = _load("gui_whole_frame_steer", "whole_frame.py")
        self._spsa = _load("hero_spsa_steer", "hero_spsa.py")
        self.size = int(size)
        self.band = band
        # The headline glyphs render on the substrate and re-rasterize when SPSA
        # flips the argmax headline; for a fast/headless steering loop the overlay
        # can be skipped (the colour hero still renders + steers). The live window
        # and the soak (1d) keep it on.
        self.render_headline = bool(render_headline)
        n_headlines = len(self._wf.HERO_HEADLINES)
        self.opt = self._spsa.HeroSPSA(n_headlines=n_headlines, seed=seed)
        self._pair = None        # (theta_plus, theta_minus) render dicts for this batch
        self._phase = 0          # 0 = showing +perturbation, 1 = showing -perturbation
        self._r_plus = None
        self.batches_done = 0
        self._begin_batch()

    def _begin_batch(self):
        self._pair = self.opt.propose()      # (theta+, theta-) render dicts
        self._phase = 0
        self._r_plus = None

    def current_theta(self) -> dict:
        return self._pair[self._phase]

    def frame(self):
        """Render the current frame on the substrate. Returns (rgb (H,W,3), headline).
        Guards against a NaN/blank frame (raises) so the soak (1d) can assert clean
        frames across a long session rather than silently painting garbage."""
        theta = self.current_theta()
        if self.render_headline:
            img, headline = self._wf.render_hero_full(self.size, theta, self.band)
        else:
            img = self._wf.render_hero_rgb(self.size, theta)
            headline = self._wf.select_headline(theta)
        if not np.all(np.isfinite(img)):
            raise FloatingPointError("hero frame has non-finite pixels")
        if float(np.abs(img).max()) <= 0.0:
            raise ValueError("hero frame is blank (all zero)")
        return img, headline

    def press(self, reward: float):
        """Apply a warmer (+1) / colder (-1) press to the CURRENT frame and return
        the next frame to show. Every two presses complete one SPSA batch."""
        r = float(reward)
        if self._phase == 0:
            self._r_plus = r
            self._phase = 1
        else:
            self.opt.update(self._r_plus, r)
            self.batches_done += 1
            self._begin_batch()
        return self.frame()

    def best_theta(self) -> dict:
        """The current best θ (the optimizer's running estimate), as a render dict —
        what a 'show the current best' button would paint between perturbations."""
        return self.opt.current_render_theta()
