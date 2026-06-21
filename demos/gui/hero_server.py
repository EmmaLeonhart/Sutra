"""Web bridge for the warmer/colder self-morphing hero (a1 demo, step 5: the URL).

Puts the existing headless `hero_steering.HeroSteering` controller behind a real
browser page: the substrate-rendered hero is served as a PNG, and two real HTML
buttons (WARMER / COLDER) POST a scalar reward that drives one side of the
host-side SPSA batch. Every two presses complete one SPSA step and the hero
visibly morphs toward what the rater prefers. This is the "live page at a URL"
piece the a1 spec (business/gtm/a1-implementation-spec.md, step 5) left as the
only missing infrastructure; the controller and its tests already exist
(test_hero_steering.py) and the browser-bridge pattern is proven by
button_server.py.

Honesty (same rails as the controller): the frame is a substrate render (colour
channels + glyph headline); the optimizer and warmer/colder bookkeeping are
host-side. This is steering of substrate-rendered output by a present rater, not
substrate-native training and not learning from real visitor traffic (that is A2).

The PNG encoding (`frame_to_png`) is a pure function and is covered in
test_hero_server.py. The HTTP serving + the HTML page are I/O and are NOT
exercised in CI (no browser on the runner); the steering logic underneath is
covered headless by test_hero_steering.py. Do NOT claim the live page works
without running it in a browser.

    python demos/gui/hero_server.py                 # serve on http://127.0.0.1:8771/
    python demos/gui/hero_server.py --size 48 --scale 9
"""
from __future__ import annotations

import argparse
import importlib.util
import io
import json
import os
import pathlib
import threading

import numpy as np

_DIR = pathlib.Path(__file__).resolve().parent


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, _DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def frame_to_png(img: np.ndarray, scale: int = 9) -> bytes:
    """Pure: clamp a substrate frame to [0,1], scale to 8-bit RGB, upscale NEAREST
    for crisp pixels, and encode as PNG bytes. The part CI can check without a
    browser or the substrate."""
    from PIL import Image

    arr = (np.clip(np.asarray(img, dtype=float), 0.0, 1.0) * 255.0).astype(np.uint8)
    if arr.ndim != 3 or arr.shape[2] != 3:
        raise ValueError(f"expected (H,W,3) RGB frame, got shape {arr.shape}")
    im = Image.fromarray(arr)
    if scale and scale > 1:
        im = im.resize((arr.shape[1] * scale, arr.shape[0] * scale), Image.NEAREST)
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


WARMER = 1.0
COLDER = -1.0


class HeroBridge:
    """Stateful bridge wrapping a HeroSteering controller: caches the current
    substrate frame (rendering is expensive, so each press renders exactly once),
    serves it as PNG, and routes warmer/colder presses. The HTTP handler is a thin
    shell over these methods."""

    def __init__(self, size: int = 48, seed: int = 0, scale: int = 9,
                 render_headline: bool = True):
        steer = _load("gui_hero_steering_web", "hero_steering.py")
        self.ctl = steer.HeroSteering(size=size, seed=seed,
                                      render_headline=render_headline)
        self.scale = int(scale)
        self.presses = 0
        self._img, self._headline = self.ctl.frame()   # prime the first frame

    def frame_png(self) -> bytes:
        return frame_to_png(self._img, self.scale)

    def state(self) -> dict:
        # phase 0 = showing the + perturbation (first press of the batch scores it);
        # phase 1 = showing the - perturbation (second press completes the SPSA step).
        return {
            "headline": self._headline,
            "spsa_steps": int(self.ctl.batches_done),
            "presses": int(self.presses),
            "phase": int(self.ctl._phase),
        }

    def press(self, reward: float) -> dict:
        r = float(reward)
        if r not in (WARMER, COLDER):
            raise ValueError(f"reward must be +1 (warmer) or -1 (colder), got {r}")
        self._img, self._headline = self.ctl.press(r)
        self.presses += 1
        return self.state()


# The bridge is built in a BACKGROUND thread (the first substrate render compiles
# and can be slow on a small cloud CPU) so the HTTP server binds immediately and a
# host's health check sees an open port. Until it is ready, endpoints report
# {"warming": true} (503); a build failure reports {"error": ...} (500).
_BRIDGE = None
_BRIDGE_ERR = None
_BRIDGE_LOCK = threading.Lock()


def _warm_bridge(size: int, seed: int, scale: int, render_headline: bool):
    global _BRIDGE, _BRIDGE_ERR
    try:
        b = HeroBridge(size=size, seed=seed, scale=scale, render_headline=render_headline)
        with _BRIDGE_LOCK:
            _BRIDGE = b
    except Exception as e:  # noqa: BLE001 — report a warm failure to the page
        with _BRIDGE_LOCK:
            _BRIDGE_ERR = repr(e)


def _make_handler():
    from http.server import BaseHTTPRequestHandler

    page = (_DIR / "hero_page.html").read_text(encoding="utf-8")

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code, body, ctype="application/json"):
            data = body if isinstance(body, bytes) else body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def _json_body(self):
            n = int(self.headers.get("Content-Length", 0))
            return json.loads(self.rfile.read(n) or b"{}") if n else {}

        def _bridge(self):
            """The ready bridge, or send a warming(503)/error(500) reply and None."""
            with _BRIDGE_LOCK:
                b, err = _BRIDGE, _BRIDGE_ERR
            if err is not None:
                self._send(500, json.dumps({"error": err}))
                return None
            if b is None:
                self._send(503, json.dumps({"warming": True}))
                return None
            return b

        def do_GET(self):
            if self.path == "/" or self.path.startswith("/index"):
                self._send(200, page, "text/html; charset=utf-8")
            elif self.path.startswith("/frame.png"):
                b = self._bridge()
                if b is not None:
                    self._send(200, b.frame_png(), "image/png")
            elif self.path.startswith("/state"):
                b = self._bridge()
                if b is not None:
                    self._send(200, json.dumps(b.state()))
            else:
                self._send(404, "{}")

        def do_POST(self):
            try:
                if self.path.startswith("/press"):
                    b = self._bridge()
                    if b is not None:
                        reward = float(self._json_body().get("reward", 0.0))
                        self._send(200, json.dumps(b.press(reward)))
                else:
                    self._send(404, "{}")
            except Exception as e:  # noqa: BLE001 — surface bridge errors to the page
                self._send(400, json.dumps({"error": str(e)}))

        def log_message(self, *_args):
            pass  # quiet

    return Handler


def main() -> None:
    ap = argparse.ArgumentParser(description="Web bridge for the warmer/colder substrate hero.")
    # Host/port default from env so a container platform can set them (HOST=0.0.0.0,
    # PORT=$PORT). Local default stays loopback for safety.
    ap.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8771")))
    ap.add_argument("--size", type=int, default=int(os.environ.get("HERO_SIZE", "48")),
                    help="substrate frame grid resolution")
    ap.add_argument("--scale", type=int, default=int(os.environ.get("HERO_SCALE", "9")),
                    help="upscale factor for the served PNG")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--no-headline", action="store_true",
                    help="skip the substrate glyph headline (the headline shows as text "
                         "instead). The glyph font is VSA-encoded and needs the embedding "
                         "backend (ollama); --no-headline keeps the demo dependency-free.")
    ap.add_argument("--warmup", action="store_true",
                    help="build the bridge (compiles + caches the substrate render) then "
                         "exit. Use at container BUILD time to bake the compile cache so "
                         "runtime startup is fast.")
    args = ap.parse_args()

    if args.warmup:
        # Build-time cache bake: compile synchronously, then exit.
        HeroBridge(size=args.size, seed=args.seed, scale=args.scale,
                   render_headline=not args.no_headline)
        print("warmup done (compile cache primed); exiting")
        return

    from http.server import HTTPServer

    # Warm the bridge in the background so the server binds immediately (the first
    # substrate render compiles and can be slow on a small CPU).
    threading.Thread(
        target=_warm_bridge,
        args=(args.size, args.seed, args.scale, not args.no_headline),
        daemon=True,
    ).start()

    httpd = HTTPServer((args.host, args.port), _make_handler())
    print(f"warmer/colder hero demo on http://{args.host}:{args.port}/ (warming...)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
