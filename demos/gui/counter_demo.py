"""Yantra GUI counter — click to count 0, 1, 2, 3, ... via per-click substrate dispatch.

Current shape: host-state-shuttle (the count lives as a Python variable
between clicks; each click feeds it through step() on the substrate, the
incremented count comes back, host stores it as the next state). The +1 IS
a substrate op, not a host ``n += 1``. But the recurrence (state across
clicks) lives in the host, not on the substrate — by CLAUDE.md "Subtler
substrate breaches" #2, this is host-state-shuttle, NOT a substrate RNN.
See planning/findings/2026-05-28-demos-gui-substrate-audit.md.

Target shape (queued, design picked Emma 2026-05-28): rewrite count.su to
use `loop (cond)` with the hidden state as a substrate vector that
survives across iterations — see queue.md item D.6.

Two substrate computations drive the per-click path (count.su):
  - step(n) = n + 1  — substrate increment.
  - pixel(x, y, n)   — the displayed glow, centred at position n.

The window title shows the current count, decoded from the substrate.

Usage:
    python apps/gui/counter_demo.py                 # open the window; click to count
    python apps/gui/counter_demo.py --render out     # save out_0.png .. out_9.png
    python apps/gui/counter_demo.py --size 64

Like the toggle demo, the live window + click can't be checked headlessly;
--render verifies the substrate-positioned frames. The counter does NOT wrap
after 9 (Emma: we don't care past the count) — n keeps rising and the glow
exits the right edge.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

import numpy as np

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
# Migrated to Sutra 2026-05-28; _REPO_ROOT is Sutra root, not Yantra.
_SUTRA_SDK = _REPO_ROOT / "sdk" / "sutra-compiler"
if str(_SUTRA_SDK) not in sys.path:
    sys.path.insert(0, str(_SUTRA_SDK))

DEMO_GUI = pathlib.Path(__file__).resolve().parent

# In-process memo: count.su's compiled module is reused across clicks. The
# disk cache from sutra_compiler.compile_su skips codegen across PROCESS
# restarts; this dict additionally skips the small exec() cost between
# calls within one process. The field re-renders every click, so reusing
# the compile (not per click) matters.
_COMPILED: dict = {}


def _compile(su_name: str) -> dict:
    """Compile a .su under apps/gui and return its namespace (functions + _VSA).

    Returns a dict view on the compiled module (source-compat with the
    prior `ns["pixel"]` access pattern). Caching is two-tier: the
    in-process `_COMPILED` memo plus `sutra_compiler.compile_su`'s
    disk-resident codegen cache (skips translate_module across restarts).
    """
    cached = _COMPILED.get(su_name)
    if cached is not None:
        return cached
    from sutra_compiler import compile_su
    # runtime_dim=8 is enough: count.su uses only make_real + arithmetic, no
    # basis_vector calls, so the LLM codebook is never touched and 766 of 768
    # dims were dead weight. Measured exact at dim=8 (2026-05-27 audit, see
    # planning/27-substrate-honesty-audit-2026-05-27.md). llm_model still
    # required by the API but unused at runtime.
    mod = compile_su(DEMO_GUI / su_name,
                     llm_model="unused-no-basis-vectors", runtime_dim=8,
                     verbose=False)
    ns = mod.__dict__
    _COMPILED[su_name] = ns
    return ns


def render_field(n: float, size: int = 64) -> np.ndarray:
    """(size, size) brightness field for count ``n``; each cell is a substrate
    ``pixel(x, y, n)`` call — a glow centred at the substrate-chosen x = f(n)."""
    ns = _compile("count.su")
    pixel, vsa = ns["pixel"], ns["_VSA"]
    field = np.empty((size, size), dtype=np.float64)
    for j in range(size):
        cy = 2.0 * j / (size - 1) - 1.0
        for i in range(size):
            cx = 2.0 * i / (size - 1) - 1.0
            field[j, i] = float(vsa.real(pixel(cx, cy, float(n))))  # SUBSTRATE value
    return field


def colormap(field: np.ndarray) -> np.ndarray:
    """Brightness field -> green glow (uint8 RGB). Display only; the values are
    the substrate's. Clamp to [0, 1], then a black -> green -> white ramp."""
    v = np.clip(field, 0.0, 1.0)
    g = np.clip(2.0 * v, 0, 1)
    rb = np.clip(2.0 * v - 1.0, 0, 1)
    return (np.stack([rb, g, rb], axis=-1) * 255).astype(np.uint8)


class _Counter:
    """Substrate-backed integer counter: each click is count.su's step() on the
    substrate. The host holds the decoded value and feeds it back (the register
    in Emma's recurrent loop); the +1 is a substrate computation, not a host
    increment."""

    def __init__(self) -> None:
        ns = _compile("count.su")
        self._step, self._vsa = ns["step"], ns["_VSA"]
        self.state = 0.0

    def click(self) -> float:
        self.state = float(self._vsa.real(self._step(self.state)))  # SUBSTRATE +1
        return self.state


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Yantra GUI counter (click counts on the substrate)")
    ap.add_argument("--render", metavar="PREFIX",
                    help="save PREFIX_0.png .. PREFIX_9.png and exit")
    ap.add_argument("--size", type=int, default=64)
    args = ap.parse_args()

    if args.render:
        from PIL import Image
        for n in range(10):
            field = render_field(float(n), args.size)
            img = Image.fromarray(colormap(field)).resize(
                (args.size * 8, args.size * 8), Image.NEAREST)
            img.save(f"{args.render}_{n}.png")
            print(f"[gui] saved {args.render}_{n}.png (count={n})")
        return

    import tkinter as tk
    from PIL import Image, ImageTk

    counter = _Counter()

    def make_photo(n: float):
        field = render_field(n, args.size)
        img = Image.fromarray(colormap(field)).resize(
            (args.size * 8, args.size * 8), Image.NEAREST)
        return ImageTk.PhotoImage(img)

    root = tk.Tk()
    root.title("Yantra — count = 0 (click to count on the substrate)")
    photo0 = make_photo(counter.state)
    label = tk.Label(root, image=photo0)
    label.image = photo0  # keep a ref
    label.pack()
    status = tk.Label(
        root,
        text="click anywhere — step(n)=n+1 runs on the Sutra substrate; the glow steps across")
    status.pack()

    def on_click(_event):
        n = counter.click()  # substrate +1
        photo = make_photo(n)
        label.configure(image=photo)
        label.image = photo  # keep a ref
        count = round(float(n))
        root.title(f"Yantra — count = {count} (incremented on the substrate)")
        status.configure(
            text=f"count = {count} — step(n)=n+1 on the substrate; glow at x=f({count})")
        print(f"[gui] click -> substrate step -> count {count}", flush=True)

    # Bind ONCE on the toplevel (a click anywhere fires it exactly once — see the
    # toggle demo's note on the double-fire bug from binding both label + root).
    root.bind("<Button-1>", on_click)
    root.mainloop()


if __name__ == "__main__":
    main()
