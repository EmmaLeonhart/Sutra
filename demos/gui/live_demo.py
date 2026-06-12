"""Live window event loop — animation + clicks driving substrate state, in real time.

The real-window milestone for the whole-frame GUI track: a tkinter window whose
picture is recomputed on the substrate every timer tick, with mouse clicks toggling
substrate state between ticks. live_frame.su owns ALL the widget's state:

  - the glow centre's phase is a complex number in step()'s recur slot, advanced by a
    fixed rotation each tick (z' = z·e^{iπ/8} — the rotation IS the wrap, the centre
    Re(z) sweeps [-1, 1] smoothly forever);
  - the click gate is a 0/1 state in flip()'s recur slot, toggled per click;
  - each tick is ONE substrate call (frame) whose returned vector IS the frame.

The host owns only the event loop plumbing: tkinter's timer (`root.after`) and click
binding, the coordinate-grid geometry, the display-boundary reads that broadcast the
two states into per-pixel buffers, and the paint. The recurrences never round-trip
through host variables (the recur slots are the truth; `LiveFrame.gate` is a display
cache, the _Counter/_Flip pattern).

Usage:
    python demos/gui/live_demo.py                  # open the live window
    python demos/gui/live_demo.py --fps 10 --size 64
    python demos/gui/live_demo.py --render out     # save a simulated tick/click strip
    python demos/gui/live_demo.py --bench          # measure per-tick latency, headless

The mainloop itself can't be checked headlessly; --render / --bench and
test_gui_live.py verify everything beneath it (LiveFrame is tkinter-free).
"""
from __future__ import annotations

import argparse
import pathlib
import sys
import time

import numpy as np

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
_SUTRA_SDK = _REPO_ROOT / "sdk" / "sutra-compiler"
if str(_SUTRA_SDK) not in sys.path:
    sys.path.insert(0, str(_SUTRA_SDK))

DEMO_GUI = pathlib.Path(__file__).resolve().parent
if str(DEMO_GUI) not in sys.path:
    sys.path.insert(0, str(DEMO_GUI))
from _display import read_real  # noqa: E402  (display/output boundary helper)

_COMPILED: dict = {}


def _compile_live():
    """Compile live_frame.su (in-process memo + compile_su's disk cache)."""
    ns = _COMPILED.get("live_frame.su")
    if ns is not None:
        return ns
    from sutra_compiler import compile_su
    # dim=8 — live_frame.su uses only make_real, a complex literal, hadamard and
    # arithmetic; zero basis_vector calls, so the LLM codebook is never touched.
    mod = compile_su(DEMO_GUI / "live_frame.su",
                     llm_model="unused-no-basis-vectors", runtime_dim=8,
                     verbose=False)
    ns = mod.__dict__
    _COMPILED["live_frame.su"] = ns
    return ns


def colormap(field: np.ndarray) -> np.ndarray:
    """Brightness -> heat ramp (black -> red -> yellow -> white), uint8 RGB.
    Display assembly only; the brightness values are the substrate's."""
    v = np.clip(field, 0.0, 1.0)
    r = np.clip(3.0 * v, 0, 1)
    g = np.clip(3.0 * v - 1.0, 0, 1)
    b = np.clip(3.0 * v - 2.0, 0, 1)
    return (np.stack([r, g, b], axis=-1) * 255).astype(np.uint8)


class LiveFrame:
    """The live window's substrate side, tkinter-free so tests drive it headless.

    Both states live ON THE SUBSTRATE in live_frame.su's recur slots
    (`_step__z_state` — the complex animation phase; `_flip__state_state` — the
    click gate). tick() and click() invoke the RNN functions with NO host arg;
    the host reads the returned vectors only at the display boundary, to broadcast
    them into the per-pixel buffers for the one-op frame render and to label the
    window. `self.centre` / `self.gate` are display caches, never fed back.
    """

    def __init__(self, size: int = 64) -> None:
        import torch

        ns = _compile_live()
        self._step, self._flip, self._frame = ns["step"], ns["flip"], ns["frame"]
        self._vsa = ns["_VSA"]
        # Fresh substrate state per instance (the compiled module is memoized,
        # so without this a second LiveFrame would inherit the first's slots).
        ns["_step__z_state"] = None
        ns["_flip__state_state"] = None

        self.size = size
        dt, dev = self._vsa.dtype, self._vsa.device
        xs, ys = [], []
        for j in range(size):          # row -> y
            cy = 2.0 * j / (size - 1) - 1.0
            for i in range(size):      # col -> x
                cx = 2.0 * i / (size - 1) - 1.0
                xs.append(cx)
                ys.append(cy)
        self._X = torch.tensor(xs, dtype=dt, device=dev)
        self._Y = torch.tensor(ys, dtype=dt, device=dev)
        self._ones = torch.ones(size * size, dtype=dt, device=dev)
        # Display caches (NOT state — the recur slots are the truth).
        self.centre = 1.0   # Re(z) starts at 1+0i before the first tick
        self.gate = 0.0     # flip() starts at 0; the first click lights the glow

    def tick(self) -> np.ndarray:
        """One animation tick: advance the phase on the substrate, render the whole
        frame in one substrate op, return the (N, N) brightness field."""
        import torch

        z = self._step()                              # substrate-RNN advance
        self.centre = read_real(self._vsa, z)         # display boundary: Re(z)
        n2 = self.size * self.size
        cx_buf = torch.full((n2,), self.centre,
                            dtype=self._vsa.dtype, device=self._vsa.device)
        gate_buf = torch.full((n2,), self.gate,
                              dtype=self._vsa.dtype, device=self._vsa.device)
        buf = self._frame(self._X, self._Y, self._ones, cx_buf, gate_buf)
        buf = buf.real if buf.is_complex() else buf   # display boundary
        return buf.reshape(self.size, self.size).detach().to("cpu").numpy()

    def click(self) -> float:
        """One click: toggle the gate on the substrate; cache the decoded value
        for display/broadcast (never fed back into flip())."""
        st = self._flip()                             # substrate-state toggle
        self.gate = read_real(self._vsa, st)
        return self.gate


def bench(size: int = 64, ticks: int = 50) -> dict:
    """Measure per-tick latency headlessly: `ticks` full tick() calls (substrate
    advance + one-op whole-frame render + display read). Returns ms stats."""
    live = LiveFrame(size=size)
    live.click()                       # gate on, so the render isn't all-zeros
    live.tick()                        # warm-up (first call pays kernel setup)
    times = []
    for _ in range(ticks):
        t0 = time.perf_counter()
        live.tick()
        times.append((time.perf_counter() - t0) * 1000.0)
    times.sort()
    return {
        "ticks": ticks,
        "mean_ms": sum(times) / len(times),
        "p95_ms": times[int(0.95 * (len(times) - 1))],
        "max_ms": times[-1],
    }


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Live substrate window: timer-driven animation + click-gated glow")
    ap.add_argument("--size", type=int, default=64, help="grid resolution")
    ap.add_argument("--fps", type=float, default=10.0, help="animation ticks/second")
    ap.add_argument("--render", metavar="PREFIX",
                    help="headless: save a simulated tick/click strip and exit")
    ap.add_argument("--bench", action="store_true",
                    help="headless: measure per-tick latency and exit")
    args = ap.parse_args()

    if args.bench:
        stats = bench(size=args.size)
        print(f"[live] {stats['ticks']} ticks at size={args.size}: "
              f"mean {stats['mean_ms']:.1f} ms, p95 {stats['p95_ms']:.1f} ms, "
              f"max {stats['max_ms']:.1f} ms")
        return

    if args.render:
        from PIL import Image

        live = LiveFrame(size=args.size)
        live.click()                   # light the glow
        seq = ["tick", "tick", "tick", "click", "tick", "click", "tick"]
        for k, action in enumerate(seq):
            if action == "click":
                g = live.click()
                print(f"[live] click -> gate {g:.0f} (toggled on the substrate)")
                continue
            field = live.tick()
            img = Image.fromarray(colormap(field)).resize(
                (args.size * 8, args.size * 8), Image.NEAREST)
            img.save(f"{args.render}_{k}.png")
            print(f"[live] saved {args.render}_{k}.png "
                  f"(centre={live.centre:+.3f}, gate={live.gate:.0f})")
        return

    import tkinter as tk
    from PIL import Image, ImageTk

    live = LiveFrame(size=args.size)
    live.click()  # programmatic first click so the window opens lit
    tick_ms = max(50, int(1000.0 / max(0.1, args.fps)))

    def make_photo(field: np.ndarray):
        img = Image.fromarray(colormap(field)).resize(
            (args.size * 8, args.size * 8), Image.NEAREST)
        return ImageTk.PhotoImage(img)

    root = tk.Tk()
    root.title("Sutra — live substrate window (click to gate the glow)")
    photo0 = make_photo(live.tick())
    label = tk.Label(root, image=photo0)
    label.image = photo0  # keep a ref
    label.pack()
    status = tk.Label(
        root,
        text="every tick is one substrate call; click anywhere to flip the gate")
    status.pack()

    def tick():
        field = live.tick()                       # substrate advance + one-op render
        photo = make_photo(field)
        label.configure(image=photo)
        label.image = photo
        root.title(f"Sutra — live substrate window "
                   f"(centre {live.centre:+.2f}, gate {live.gate:.0f})")
        root.after(tick_ms, tick)                 # re-arm the timer

    def on_click(_event):
        g = live.click()                          # substrate-state toggle
        status.configure(
            text=f"gate = {g:.0f} (flipped on the substrate) — click to flip again")
        print(f"[live] click -> substrate flip -> gate {g:.0f}", flush=True)

    # Bind ONCE on the toplevel (binding label + toplevel double-fires; see the
    # toggle demo's note).
    root.bind("<Button-1>", on_click)
    root.after(tick_ms, tick)
    root.mainloop()


if __name__ == "__main__":
    main()
