"""Two ways to render a glyph's pixels (Emma 2026-06-01).

planning/sutra-spec/ram-pointers.md § "The experiment Emma wants".

Same output (a 5x5 glyph bitmap), two architectures:

  (a) "pure neural network thing" — demos/font/font.su `glyph_pixel(x,y,code)`
      COMPUTES each pixel on the substrate via a 36-way x 25-way
      defuzzified-`select` cascade (the font is baked into the program's
      logic; no external memory is read).

  (b) NTM / RAM lookup — the glyph bitmap is stored in the external host
      RAM device; a Sutra read head emits a program-controlled pointer
      per cell and the orchestrator serves RAM[pointer]. The font lives
      in addressable, mutable external memory, fetched by pointer.

Both are checked against the independent ground truth
(demos/font/font_data.FONT_5x5). The point is the architectural
contrast: substrate *computation* vs external-memory *lookup* — not that
one is more correct.

Run: python experiments/ntm_ram/run_font_compare.py
"""
from __future__ import annotations

import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(REPO, "sdk", "sutra-compiler"))
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(REPO, "demos", "font"))

from sutra_compiler import compile_su as pkg_compile_su   # noqa: E402
from font_data import FONT_5x5, bits_for                  # noqa: E402

from ram_device import RamDevice                          # noqa: E402
from orchestrator import Orchestrator                     # noqa: E402
from run_demo import compile_su as compile_su_path        # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_SU = os.path.join(REPO, "demos", "font", "font.su")
TEST_GLYPHS = ["A", "7"]


def ascii_render(bits) -> list:
    """25 row-major bits -> 5 rows of '#'/'.'."""
    return ["".join("#" if bits[y * 5 + x] > 0.5 else "." for x in range(5))
            for y in range(5)]


def nn_render(glyph_pixel, vsa, code: int):
    """Pure-NN render: glyph_pixel computes each cell on the substrate."""
    bits = []
    for pos in range(25):
        x, y = pos % 5, pos // 5
        bits.append(round(float(vsa.real(glyph_pixel(float(x), float(y), float(code))))))
    return bits


def ram_render(scan_ns, ground_bits):
    """RAM-lookup render: store the bitmap in RAM, then a Sutra read head
    emits one pointer per cell and the orchestrator serves RAM[pointer]."""
    vsa = scan_ns["_VSA"]
    ram = RamDevice(vsa, size=32)
    for pos, b in enumerate(ground_bits):
        ram.write_number(pos, float(b))
    # Fresh cursor each glyph: reset the read head's recurring slot.
    scan_ns["_read_head__cursor_state"] = None
    orch = Orchestrator(vsa, ram, scan_ns["read_head"])
    # Fixed 25-cell fetch — 0 bits are valid pixels, so do NOT stop on the
    # zero-vector sentinel.
    trace = orch.run_read_scan(max_steps=25, stop_on_sentinel=False)
    return [round(float(vsa.real(served))) for _addr, served in trace]


def main():
    # NN renderer: font.su at runtime_dim=8 (model-free; matches the font
    # demo's own compile). RAM read head: text_scan.su at the same dim so
    # the number layout is identical.
    font_mod = pkg_compile_su(FONT_SU, llm_model="none", runtime_dim=8)
    fns = font_mod.__dict__
    glyph_pixel, font_vsa = fns["glyph_pixel"], fns["_VSA"]
    scan_ns = compile_su_path(os.path.join(HERE, "text_scan.su"), semantic_dim=8)

    print(f"NN renderer (font.su glyph_pixel): dim={font_vsa.dim} "
          f"(semantic={font_vsa.semantic_dim}, model-free select cascade)")
    print(f"RAM renderer (read head + orchestrator): dim={scan_ns['_VSA'].dim}\n")

    all_ok = True
    for ch in TEST_GLYPHS:
        code = ord(ch)
        ground = bits_for(ch)
        nn = nn_render(glyph_pixel, font_vsa, code)
        ram = ram_render(scan_ns, ground)
        nn_ok = nn == [round(b) for b in ground]
        ram_ok = ram == [round(b) for b in ground]
        all_ok = all_ok and nn_ok and ram_ok

        gr, nr, rr = ascii_render(ground), ascii_render(nn), ascii_render(ram)
        print(f"glyph {ch!r} (code {code}):   ground       NN-compute   RAM-lookup")
        for i in range(5):
            print(f"               {gr[i]}        {nr[i]}        {rr[i]}")
        print(f"  NN==ground: {nn_ok}   RAM==ground: {ram_ok}   "
              f"NN==RAM: {nn == ram}\n")

    print(f"ALL glyphs, both architectures match ground truth: {all_ok}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
