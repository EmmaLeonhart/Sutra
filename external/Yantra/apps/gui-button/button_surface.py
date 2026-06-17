"""Y2 — Yantra `gui-button` host surface over the Sutra trainable-button substrate.

A Yantra orchestration surface (host I/O) that SPAWNS the Sutra button substrate-server
(`demos/gui/button_substrate_server.py`, Y1) as a subprocess and drives it: it asks the
substrate for the current/proposed button frames, forwards the owner's A/B preference and the
visitor's clicks, and reads back state. The button DESIGN, its RENDER, and the owner×CTR
STEERING are the Sutra side; this surface is window/clicks/orchestration only — the same
"host is I/O, substrate computes" split as Yantra's `gui-rust` (which spawns
`counter_substrate_server.py`) and the calc/terminal Python host surfaces.

This is the Python host surface (headless-drivable). A native Rust `minifb` window over the
same protocol is a later refinement (mirroring `apps/gui-rust`); the protocol is identical, so
the Rust window would speak the same FRAME/PA/PB/CA/CB/S/Q commands.

    python apps/gui-button/button_surface.py        # drive a short scripted session, print state
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import numpy as np

# Yantra is vendored in-tree under Sutra at external/Yantra/, so the Sutra root is parents[4]
# of this file (gui-button -> apps -> Yantra -> external -> Sutra).
_SUTRA_ROOT = pathlib.Path(__file__).resolve().parents[4]
_SUBSTRATE_SERVER = _SUTRA_ROOT / "demos" / "gui" / "button_substrate_server.py"


class YantraButtonSurface:
    """Host surface that spawns and drives the Sutra button substrate-server."""

    def __init__(self, size: int = 64, seed: int = 0, alpha: float = 0.5, live_ctr: bool = False):
        if not _SUBSTRATE_SERVER.is_file():
            raise FileNotFoundError(f"button substrate-server not found: {_SUBSTRATE_SERVER}")
        self.size = int(size)
        cmd = [sys.executable, str(_SUBSTRATE_SERVER), "--size", str(self.size),
               "--seed", str(seed), "--alpha", str(alpha)]
        if live_ctr:
            cmd.append("--live-ctr")
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE)

    # --- low-level protocol I/O ---
    def _send(self, line: str) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.write((line + "\n").encode())
        self.proc.stdin.flush()

    def _readline(self) -> bytes:
        assert self.proc.stdout is not None
        return self.proc.stdout.readline()

    def _read_frame(self) -> np.ndarray:
        header = self._readline().decode().split()
        assert header and header[0] == "FRAME", f"expected FRAME header, got {header}"
        size = int(header[2])
        n = size * size * 3 * 8                       # float64 RGB body
        assert self.proc.stdout is not None
        buf = self.proc.stdout.read(n)
        return np.frombuffer(buf, dtype="<f8").reshape(size, size, 3)

    # --- surface API the window / orchestrator uses ---
    def frame(self, which: str = "current") -> np.ndarray:
        """The substrate-rendered current ('current') or proposed ('variant') button."""
        self._send("V" if which == "variant" else "I")
        return self._read_frame()

    def prefer(self, variant: bool) -> int:
        """Owner prefers the variant (True) or current (False); returns the new round."""
        self._send("PB" if variant else "PA")
        return int(self._readline().decode().split()[1])

    def click(self, which: str = "variant") -> None:
        """Forward a visitor click on the current/variant button."""
        self._send("CB" if which == "variant" else "CA")
        self._readline()                              # "OK\n"

    def state(self) -> dict:
        self._send("S")
        line = self._readline().decode()
        return json.loads(line[len("STATE "):])

    def close(self) -> None:
        if self.proc.poll() is None:
            try:
                self._send("Q")
            except (BrokenPipeError, OSError):
                pass
            self.proc.wait(timeout=10)

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()


def main() -> None:
    """Scripted headless session: render, click the variant a few times, prefer it, print state.
    Stands in for the eventual Rust window / orchestrator surface driving the same protocol."""
    with YantraButtonSurface(size=32, live_ctr=True) as s:
        cur = s.frame("current")
        print(f"current button frame {cur.shape}, mean rgb "
              f"({cur[...,0].mean():.2f},{cur[...,1].mean():.2f},{cur[...,2].mean():.2f})")
        for _ in range(5):
            s.click("variant")
            s.prefer(variant=True)
        st = s.state()
        print(f"after 5 rounds: round={st['round']} clicks={st['clicks']} "
              f"ctr_observed={st['ctr_observed']:.3f} copy={st['copy']}")


if __name__ == "__main__":
    main()
