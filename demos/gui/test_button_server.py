"""B4 — the live-button bridge LOGIC (no browser).

`button_server.ButtonBridge` is the testable core behind the live HTML/JS button: it maps the
controller's θ to a CSS-ready style, applies the owner's A/B preference as one ButtonAdam
step, and tallies visitor clicks. These tests exercise that logic directly (no browser, no
socket) so CI can verify it; the HTML page and HTTP serving are I/O and stay un-smoked here.
"""
from __future__ import annotations

import importlib.util
import pathlib
import re

import pytest

_DIR = pathlib.Path(__file__).resolve().parent


def _server():
    spec = importlib.util.spec_from_file_location("gui_button_server", _DIR / "button_server.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_RGB = re.compile(r"^rgb\((\d{1,3}), (\d{1,3}), (\d{1,3})\)$")


def test_theta_to_style_is_valid_css():
    srv = _server()
    theta = {"cx": 0.1, "cy": -0.2, "inv_w": 1.7, "inv_h": 3.5,
             "pr": 0.95, "pg": 0.95, "pb": 0.95, "fr": 0.2, "fg": 0.45, "fb": 0.9}
    s = srv.theta_to_style(theta, "Buy now")
    for key in ("fill", "page"):
        m = _RGB.match(s[key])
        assert m, f"{key} not rgb(): {s[key]}"
        assert all(0 <= int(g) <= 255 for g in m.groups()), f"{key} channel out of range: {s[key]}"
    assert s["width_px"] > 0 and s["height_px"] > 0, f"non-positive size: {s}"
    assert s["text"] == "Buy now"


def test_bridge_state_has_pair_and_counters():
    pytest.importorskip("torch")
    srv = _server()
    b = srv.ButtonBridge(alpha=0.5, size=16, seed=0)
    st = b.state()
    assert set(("round", "clicks", "impressions", "ctr_observed", "current", "variant")) <= set(st)
    assert st["current"]["text"] in ("Buy now", "Get started", "Learn more")
    assert st["impressions"] >= 1
    # both styles present and well-formed
    assert _RGB.match(st["current"]["fill"]) and _RGB.match(st["variant"]["fill"])


def test_click_tallies_observed_ctr():
    pytest.importorskip("torch")
    srv = _server()
    b = srv.ButtonBridge(alpha=0.5, size=16, seed=0)
    b.state()                                   # one impression
    c0 = b.clicks
    r = b.click("variant")
    assert b.clicks == c0 + 1, "click not tallied"
    assert r["ctr_observed"] == b.clicks / b.impressions
    with pytest.raises(ValueError):
        b.click("nonsense")


def test_prefer_advances_round_and_steps_controller():
    """Owner A/B preferences must advance the round AND actually move the controller: an owner
    that consistently prefers the bluer button drives the fill blue up."""
    pytest.importorskip("torch")
    srv = _server()
    # size=24 / 50 rounds is the regime B3 verified robust for owner steering (a smaller grid
    # / fewer rounds under-trains the head and the relative-blue objective can collapse).
    b = srv.ButtonBridge(alpha=1.0, size=24, seed=0)   # alpha=1: pure owner taste

    def fill_blueness(t):
        # how blue the button fill is — what the owner head reads off the rendered frame
        return t["fb"] - 0.5 * (t["fr"] + t["fg"])

    fb0 = b.ctl.current_theta()["fb"]
    r0 = b.round
    for _ in range(50):
        cur_t, var_t = b.ctl.pending_thetas()
        b.prefer(prefer_variant=(fill_blueness(var_t) > fill_blueness(cur_t)))  # owner prefers the bluer button
    assert b.round == r0 + 50, "rounds did not advance"
    assert b.ctl.current_theta()["fb"] > fb0 + 0.1, \
        f"owner-prefers-blue did not raise fill blue: {fb0:.3f} -> {b.ctl.current_theta()['fb']:.3f}"
