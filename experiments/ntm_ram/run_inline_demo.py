"""Demo: read text from RAM via the INLINE ramRead surface.

planning/sutra-spec/ram-pointers.md. Companion to run_demo.py (which uses
the external orchestrator harness). Here the .su read head calls the
inline `ramRead(cur)` builtin against a host-attached `_VSA.ram` device —
the step-2 inline surface. The host lays the text out in `_VSA.ram`,
drives the recur ticks, and decodes each returned value to a char. Same
observable result as the orchestrator-harness scan ("HELLO, RAM!").

Run: python experiments/ntm_ram/run_inline_demo.py
"""
from __future__ import annotations

import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(REPO, "sdk", "sutra-compiler"))
sys.path.insert(0, os.path.dirname(__file__))

from run_demo import compile_su   # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    text = "HELLO, RAM!"
    ns = compile_su(os.path.join(HERE, "text_scan_inline.su"), semantic_dim=2)
    vsa = ns["_VSA"]
    print(f"runtime layout: semantic_dim={vsa.semantic_dim} dim={vsa.dim}  (model-free)")

    # Host attaches the external RAM device and lays the text out, one
    # codepoint per cell. This is the orchestrator's host-side role; the
    # program reads it inline via ramRead.
    size = 32
    vsa.ram = [vsa.make_real(float(ord(c))) for c in text] \
        + [vsa.zero_vector() for _ in range(size - len(text))]

    # Drive the ticks (host loop); the program reads RAM inline each tick.
    out = []
    for _ in range(len(text)):
        val = ns["read_step"](0.0)
        out.append(chr(int(round(vsa.real(val)))))
    decoded = "".join(out)

    print(f"ground truth : {text!r}")
    print(f"decoded      : {decoded!r}")
    match = decoded == text
    print(f"exact match  : {match}")
    return 0 if match else 1


if __name__ == "__main__":
    sys.exit(main())
