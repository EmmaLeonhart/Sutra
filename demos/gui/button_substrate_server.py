"""Y1 — stdin/stdout substrate server for the trainable button (Yantra-spawnable bridge).

Mirrors `counter_substrate_server.py`: a host painter — Yantra's Rust GUI / orchestrator
surface (apps/gui-button, Y2) — spawns this process, sends one-line text commands on stdin, and
reads substrate-rendered button frames + state on stdout. The button design, its render, and
the owner×CTR steering are the Sutra side (`ButtonAdam` over `render_button_torch`, reused via
`ButtonBridge`); the host does the window, the clicks, and the painting.

Protocol (text commands in; responses out):
  "I"        init/current  — FRAME of the current button
  "V"        variant       — FRAME of the proposed variant
  "PA"/"PB"  owner prefers current(A)/variant(B) — one ButtonAdam step + re-propose → "OK <round>\n"
  "CA"/"CB"  visitor click on current/variant — tally (+ live-ctr learning) → "OK\n"
  "S"        state         — "STATE <json>\n" (round, clicks, impressions, ctr, copy, theta)
  "Q"        quit          — handler returns None

FRAME response (binary, like counter_substrate_server):
  header  b"FRAME <round> <size>\n"
  body    size*size*3 float64 little-endian — the RGB button frame, row-major (the substrate
          render clamped to the displayed [0,1]).

Usage (normally launched by the Yantra surface, not by hand):
    python demos/gui/button_substrate_server.py --size 64 --live-ctr
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import sys

_DIR = pathlib.Path(__file__).resolve().parent


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, _DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class ButtonSubstrateServer:
    """Wraps a `ButtonBridge` with a one-line-command protocol over substrate-rendered button
    frames. `handle(cmd)` is pure (returns the bytes to write, or None on quit) so it is
    testable without pipes; `run()` is the stdin/stdout loop for the spawned-subprocess case."""

    def __init__(self, size: int = 64, seed: int = 0, alpha: float = 0.5,
                 live_ctr: bool = False):
        srv = _load("gui_button_server", "button_server.py")
        self.bridge = srv.ButtonBridge(alpha=alpha, size=size, seed=seed, live_ctr=live_ctr)
        self.size = int(size)

    def _frame_bytes(self, theta: dict) -> bytes:
        """Render `theta` on the substrate and encode it: FRAME header + float64 RGB body."""
        frame = self.bridge.ctl.wf.render_button_torch(self.size, theta).clamp(0.0, 1.0)
        arr = frame.detach().to("cpu").numpy()
        header = ("FRAME %d %d\n" % (self.bridge.round, self.size)).encode()
        return header + arr.astype("<f8").tobytes()

    def _state_bytes(self) -> bytes:
        st = self.bridge.state()
        compact = {
            "round": st["round"], "clicks": st["clicks"],
            "impressions": st["impressions"], "ctr_observed": st["ctr_observed"],
            "copy": self.bridge.ctl.current_copy(),
            "theta": self.bridge.ctl.current_theta(),
        }
        return b"STATE " + json.dumps(compact).encode() + b"\n"

    def handle(self, line: str):
        """Process one command line. Returns the bytes to write back, or None to quit."""
        cmd = line.strip().upper()
        if cmd == "Q" or cmd == "":
            return None if cmd == "Q" else b""
        if cmd == "I":
            cur_t, _ = self.bridge.ctl.pending_thetas()
            return self._frame_bytes(cur_t)
        if cmd == "V":
            _, var_t = self.bridge.ctl.pending_thetas()
            return self._frame_bytes(var_t)
        if cmd in ("PA", "PB"):
            self.bridge.prefer(prefer_variant=(cmd == "PB"))
            return ("OK %d\n" % self.bridge.round).encode()
        if cmd in ("CA", "CB"):
            self.bridge.click("variant" if cmd == "CB" else "current")
            return b"OK\n"
        if cmd == "S":
            return self._state_bytes()
        raise ValueError(f"unknown command: {line!r}")


def _binary_stdout():
    """Binary stdout, defeating Windows newline translation that would corrupt the float body."""
    try:
        import msvcrt
        import os
        msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
    except (ImportError, OSError):
        pass
    return sys.stdout.buffer


def main() -> None:
    ap = argparse.ArgumentParser(description="Sutra substrate server for the trainable button (Yantra bridge).")
    ap.add_argument("--size", type=int, default=64)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--alpha", type=float, default=0.5, help="owner-vs-CTR blend (1=owner, 0=CTR)")
    ap.add_argument("--live-ctr", action="store_true", help="learn CTR from real clicks (B7/B9)")
    args = ap.parse_args()

    server = ButtonSubstrateServer(size=args.size, seed=args.seed,
                                   alpha=args.alpha, live_ctr=args.live_ctr)
    out = _binary_stdout()
    while True:
        line = sys.stdin.readline()
        if not line:
            break                                 # EOF: host closed the pipe
        resp = server.handle(line)
        if resp is None:
            break                                 # quit
        out.write(resp)
        out.flush()


if __name__ == "__main__":
    main()
