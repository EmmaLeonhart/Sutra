"""Demo: write to RAM via the axon mailbox (Emma 2026-06-01 decision).

planning/sutra-spec/ram-pointers.md § "Mailbox representation".

The write head emits an Axon{ptr, data} each tick; the orchestrator
reads the fields (axon_item = the substrate unbind), decodes the
pointer, and writes the data vector to host RAM. We then read RAM back
and compare to the program's intended (addr -> addr+100) map to confirm
substrate-generated values, addressed by program-chosen pointers, land
in host memory exactly.

Needs an embedding model (axon keys embed): runtime_dim=768.
Run: python experiments/ntm_ram/run_write.py
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
    n = 5
    ns = compile_su(os.path.join(HERE, "write_head.su"),
                    semantic_dim=768, llm_model="nomic-embed-text")
    vsa = ns["_VSA"]
    print(f"runtime layout: semantic_dim={vsa.semantic_dim} "
          f"synthetic_dim={vsa.synthetic_dim} dim={vsa.dim}  "
          f"(axon-mailbox keys embed -> 768)")

    ram = RamDevice(vsa, size=64)
    orch = Orchestrator(vsa, ram, ns["write_step"])
    written = orch.run_write_stream(n_steps=n)
    print(f"program wrote (addr -> data): {written}")

    # Read RAM back and compare to the intended addr -> addr+100 map.
    readback = [(addr, int(round(vsa.real(ram.read_vector(addr)))))
                for addr, _ in written]
    print(f"RAM readback (addr -> data) : {readback}")
    expected = [(i, i + 100) for i in range(n)]
    print(f"expected                    : {expected}")
    match = written == expected and readback == expected
    print(f"exact match : {match}")
    if not match:
        print(f"delta: written {written} | readback {readback} | expected {expected}")
    return 0 if match else 1


if __name__ == "__main__":
    sys.exit(main())
