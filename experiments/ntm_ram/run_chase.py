"""Demo: data-dependent addressing (pointer-chase) over RAM.

planning/sutra-spec/ram-pointers.md. Companion to run_demo.py (sequential
scan). Here the string is stored as a LINKED LIST across non-sequential
RAM cells — each cell is a complex number (real = codepoint, imag = next
address). The reader follows the links: the next address comes from RAM,
through the substrate, not from a host counter. The visited address
sequence being non-sequential is the proof the head is following
pointers, not scanning.

Run: python experiments/ntm_ram/run_chase.py
"""
from __future__ import annotations

import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(REPO, "sdk", "sutra-compiler"))
sys.path.insert(0, os.path.dirname(__file__))

from ram_device import RamDevice                  # noqa: E402
from orchestrator import Orchestrator             # noqa: E402
from run_demo import compile_su                   # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    text = "WORLD"
    # Deliberately non-sequential addresses: if the reader recovers the
    # string in order, it followed the imag-part links through RAM.
    addrs = [0, 5, 2, 9, 4]
    terminator = 63

    ns = compile_su(os.path.join(HERE, "chase.su"), semantic_dim=2)
    vsa = ns["_VSA"]
    print(f"runtime layout: semantic_dim={vsa.semantic_dim} "
          f"synthetic_dim={vsa.synthetic_dim} dim={vsa.dim}  (model-free)")

    ram = RamDevice(vsa, size=64)
    start = ram.load_linked_text(text, addrs, terminator_addr=terminator)
    print(f"linked-list layout (addr->char,next): "
          f"{[(addrs[i], text[i], addrs[i+1] if i+1 < len(text) else terminator) for i in range(len(text))]}")

    orch = Orchestrator(vsa, ram, ns["chase"])
    trace = orch.run_pointer_chase(start_addr=start, max_steps=64)
    decoded = orch.chase_text(trace)

    visited = [a for a, _c, _n in trace]
    print(f"visited address chain: {visited}  (non-sequential => followed links)")
    print(f"ground truth : {text!r}")
    print(f"decoded      : {decoded!r}")
    match = decoded == text and visited == addrs
    print(f"exact match  : {match}  (text and visited-order both correct)")
    if not match:
        print(f"delta: text {text!r} vs {decoded!r}; visited {visited} vs {addrs}")
    return 0 if match else 1


if __name__ == "__main__":
    sys.exit(main())
