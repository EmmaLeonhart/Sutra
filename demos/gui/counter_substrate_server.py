"""Substrate server for the Rust GUI counter (apps/gui-rust).

Emma's subprocess-bridge architecture (2026-05-25): the Rust process owns the
window, the clicks, and the painting; THIS process is the Sutra substrate it
calls. Rust sends one-letter commands on stdin; for each, we run the counter ON
THE SUBSTRATE (count.su) and write the resulting field back on stdout as raw
float64 for the Rust side to paint.

The point of the split: the count (+1) and the pixel field are SUBSTRATE
computations (count.su's step / pixel); Rust does only window + event + paint.
Same "host is I/O, substrate computes" rule as the Python GUIs — just with Rust
as the host. Rust does NOT redo the arithmetic; it asks the substrate.

Protocol (stdout is written in binary so the float body is not mangled):
    Rust -> us (stdin, text lines):
        "I\n"  init  — send the current frame (no increment)
        "C\n"  click — step(n)=n+1 ON THE SUBSTRATE, then send the new frame
        "Q\n"  quit
    us -> Rust (stdout, binary):
        header  b"FRAME <count> <size>\n"
        body    size*size float64 little-endian — the substrate field
                pixel(x, y, n) for the current count, row-major (y outer).

Usage (normally launched by the Rust GUI, not by hand):
    python apps/gui/counter_substrate_server.py --size 64
"""
from __future__ import annotations

import argparse
import pathlib
import sys

# Reuse the compiled count.su (substrate step + pixel) via counter_demo.
DEMO_GUI = pathlib.Path(__file__).resolve().parent
if str(DEMO_GUI) not in sys.path:
    sys.path.insert(0, str(DEMO_GUI))
import counter_demo as cd  # noqa: E402
from _display import read_real  # noqa: E402  (display/output boundary helper)


def _binary_stdout():
    """Return a binary stdout stream, defeating Windows \\n -> \\r\\n text-mode
    translation that would corrupt the float64 body."""
    try:
        import msvcrt
        import os
        msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
    except (ImportError, OSError):
        pass
    return sys.stdout.buffer


def main() -> None:
    ap = argparse.ArgumentParser(description="Sutra substrate server for the Rust GUI counter")
    ap.add_argument("--size", type=int, default=64)
    args = ap.parse_args()

    ns = cd._compile("count.su")
    step, vsa = ns["step"], ns["_VSA"]
    state = 0.0

    out = _binary_stdout()

    def send_frame(n: float) -> None:
        field = cd.render_field(n, args.size)  # SUBSTRATE field for this count
        out.write(b"FRAME %d %d\n" % (round(n), args.size))
        out.write(field.astype("<f8").tobytes())
        out.flush()

    while True:
        line = sys.stdin.readline()
        if not line:
            break  # EOF: Rust closed the pipe
        cmd = line.strip()[:1].upper()
        if cmd == "C":
            state = read_real(vsa, step(state))  # SUBSTRATE +1, decoded at the display boundary
            send_frame(state)
        elif cmd == "I":
            send_frame(state)
        elif cmd == "Q":
            break


if __name__ == "__main__":
    main()
