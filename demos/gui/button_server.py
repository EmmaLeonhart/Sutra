"""B4 — live HTML/JS button bridge for the trainable-button demo.

A small HTTP bridge between a real browser `<button>` and the `ButtonAdam` controller (B3).
The browser is the host/I-O (it paints a real button styled from θ and reports clicks); the
controller's design and its substrate render stay on the Sutra side. This is the "everything
is a browser" GUI/JS layer the trainable-button vision targets.

Architecture (the testable core is `ButtonBridge`; the HTTP layer is a thin wrapper):
  GET  /          -> the HTML page (button_page.html)
  GET  /state     -> JSON: current + proposed button STYLES (θ → CSS), round, clicks,
                     impressions, observed CTR
  POST /prefer    -> body {"prefer_variant": bool}; the OWNER's A/B choice → one ButtonAdam
                     step (owner_pref), then a fresh proposal
  POST /click     -> body {"which": "current"|"variant"}; a real visitor click, tallied as the
                     observed click-through (impressions are counted as pairs are served)

What is wired vs tracked (honest): the OWNER channel drives the design through ButtonAdam's
existing owner-preference + simulated-audience reward; real visitor CLICKS are tallied and
surfaced as an observed CTR readout. Closing the training loop on real clicks (a learned
click-reward head replacing the simulated audience) is the follow-on — see DEVLOG.

This file's HTTP serving + the HTML page are I/O and are NOT exercised in CI (no browser on
the runner); the `ButtonBridge` logic below IS covered by test_button_server.py. Do NOT claim
the live browser button works without running it in a browser.

    python demos/gui/button_server.py            # serve on http://127.0.0.1:8770/
    python demos/gui/button_server.py --alpha 0  # pure-CTR demo  (--alpha 1 = pure owner)
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib

_DIR = pathlib.Path(__file__).resolve().parent


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, _DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _u8(v: float) -> int:
    """Clamp a [0,1] substrate colour component to an 8-bit CSS channel."""
    return max(0, min(255, int(round(float(v) * 255.0))))


# A canvas where the render's [-1, 1] axis maps to CANVAS_PX/2 each side.
CANVAS_PX = 360.0


def theta_to_style(theta: dict, copy_text: str) -> dict:
    """Map a button θ (substrate parameters) to a CSS-ready style dict for a real HTML
    button: fill/page colours as rgb(), pixel width/height from the inverse half-extents,
    centre offset from (cx, cy), and the copy text. Pure function — the heart of the bridge,
    and the part CI can check."""
    half_w = 1.0 / max(1e-6, float(theta["inv_w"]))      # half-width in [-1,1] units
    half_h = 1.0 / max(1e-6, float(theta["inv_h"]))
    return {
        "fill": f"rgb({_u8(theta['fr'])}, {_u8(theta['fg'])}, {_u8(theta['fb'])})",
        "page": f"rgb({_u8(theta['pr'])}, {_u8(theta['pg'])}, {_u8(theta['pb'])})",
        "width_px": round(2.0 * half_w * (CANVAS_PX / 2.0)),
        "height_px": round(2.0 * half_h * (CANVAS_PX / 2.0)),
        "left_px": round(float(theta["cx"]) * (CANVAS_PX / 2.0)),
        "top_px": round(float(theta["cy"]) * (CANVAS_PX / 2.0)),
        "text": copy_text,
    }


class ButtonBridge:
    """Stateful bridge wrapping a ButtonAdam: serves current/proposed button styles, applies
    the owner's A/B preference (one controller step), and tallies real visitor clicks. The
    HTTP handler is a thin shell over these methods; tests drive them directly."""

    def __init__(self, alpha: float = 0.5, size: int = 24, seed: int = 0,
                 live_ctr: bool = False):
        ba = _load("gui_button_adam", "button_adam.py")
        aud = _load("gui_button_audience", "button_audience.py")
        self._preset = aud.PRESET_COPY
        self.ctl = ba.ButtonAdam(size=size, seed=seed, alpha=alpha, live_ctr=live_ctr)
        self.round = 0
        self.clicks = 0
        self.impressions = 0
        self._round_clicked = False                       # did this owner-round get a click?
        if live_ctr:
            self.ctl.select_copy_ucb()                    # bandit picks the first copy to show
        self.ctl.propose()                                # prime the first pair

    def _styles(self):
        cur_t, var_t = self.ctl.pending_thetas()
        copy_text = self._preset[self.ctl.current_copy()]
        return theta_to_style(cur_t, copy_text), theta_to_style(var_t, copy_text)

    def state(self) -> dict:
        """Current + proposed button styles and the running tallies. Serving a pair counts as
        one impression (the visitor saw the buttons)."""
        self.impressions += 1
        cur, var = self._styles()
        return {
            "round": self.round,
            "clicks": self.clicks,
            "impressions": self.impressions,
            "ctr_observed": (self.clicks / self.impressions) if self.impressions else 0.0,
            "current": cur,
            "variant": var,
        }

    def prefer(self, prefer_variant: bool) -> dict:
        """The owner's A/B choice → one ButtonAdam step, then a fresh proposal. In live mode an
        owner-round is also one copy-bandit impression: record whether the shown copy was
        clicked this round, then let the bandit pick the next copy to show."""
        if self.ctl.live_ctr:
            self.ctl.record_copy_outcome(self._round_clicked)
            self._round_clicked = False
        self.ctl.choose(prefer_variant=bool(prefer_variant))
        self.round += 1
        if self.ctl.live_ctr:
            self.ctl.select_copy_ucb()
        self.ctl.propose()
        return self.state()

    def click(self, which: str = "variant") -> dict:
        """Tally a real visitor click on the current/variant button (observed CTR). In live-CTR
        mode the click also trains the learned CTR reward head (a click is a preference for the
        clicked button's clickability); the design advances on `prefer` using that head."""
        if which not in ("current", "variant"):
            raise ValueError(f"click 'which' must be current|variant, got {which!r}")
        self.clicks += 1
        if self.ctl.live_ctr and self.ctl._pending is not None:
            self.ctl.record_click(prefer_variant=(which == "variant"))
            self._round_clicked = True                    # the shown copy got a click this round
        return {"clicks": self.clicks, "impressions": self.impressions,
                "ctr_observed": (self.clicks / self.impressions) if self.impressions else 0.0}


def _make_handler(bridge: ButtonBridge):
    from http.server import BaseHTTPRequestHandler

    page = (_DIR / "button_page.html").read_text(encoding="utf-8")

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code, body, ctype="application/json"):
            data = body if isinstance(body, bytes) else body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _json_body(self):
            n = int(self.headers.get("Content-Length", 0))
            return json.loads(self.rfile.read(n) or b"{}") if n else {}

        def do_GET(self):
            if self.path == "/" or self.path.startswith("/index"):
                self._send(200, page, "text/html; charset=utf-8")
            elif self.path.startswith("/state"):
                self._send(200, json.dumps(bridge.state()))
            else:
                self._send(404, "{}")

        def do_POST(self):
            try:
                if self.path.startswith("/prefer"):
                    self._send(200, json.dumps(bridge.prefer(bool(self._json_body().get("prefer_variant")))))
                elif self.path.startswith("/click"):
                    self._send(200, json.dumps(bridge.click(self._json_body().get("which", "variant"))))
                else:
                    self._send(404, "{}")
            except Exception as e:  # noqa: BLE001 — report bridge errors to the page
                self._send(400, json.dumps({"error": str(e)}))

        def log_message(self, *_args):
            pass  # quiet

    return Handler


def main() -> None:
    ap = argparse.ArgumentParser(description="Live HTML/JS button bridge (trainable button).")
    ap.add_argument("--port", type=int, default=8770)
    ap.add_argument("--alpha", type=float, default=0.5, help="owner-vs-CTR blend (1=owner, 0=CTR)")
    ap.add_argument("--size", type=int, default=24)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--live-ctr", action="store_true",
                    help="learn the CTR reward from real clicks (B7) instead of the simulated audience")
    args = ap.parse_args()

    from http.server import HTTPServer
    bridge = ButtonBridge(alpha=args.alpha, size=args.size, seed=args.seed, live_ctr=args.live_ctr)
    httpd = HTTPServer(("127.0.0.1", args.port), _make_handler(bridge))
    print(f"trainable-button demo on http://127.0.0.1:{args.port}/  (alpha={args.alpha})")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
