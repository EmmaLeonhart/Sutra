# gui-rust — Yantra Rust GUI counter (orchestrator front-end)

The first GUI with a **Rust** orchestrator. Emma's direction (2026-05-25): the
orchestrator should be Rust, and Rust can own a real OS window — so this crate
owns the window, the mouse clicks, and the painting, while the **Sutra
substrate** does the actual compute.

## Architecture — subprocess bridge

```
Rust process (this crate, minifb window)
  ── opens the window, reads clicks, paints pixels
        │  "I" init / "C" click / "Q" quit   (child stdin)
        ▼
Python child = the Sutra substrate
  (apps/gui/counter_substrate_server.py + count.su)
  ── step(n)=n+1  and  pixel(x,y,n)   ON THE SUBSTRATE
        │  "FRAME <count> <size>\n" + size*size f64   (child stdout)
        ▲
  Rust clamps + colours + blits what the substrate computed
```

The count (`+1`) and the pixel field are **substrate** computations — Rust does
**not** redo the arithmetic, it asks the substrate for each frame. This is the
host/substrate split the Python GUIs use (`apps/gui/`), now with Rust as the
host. Doing the math in Rust would be the "host fakes the substrate" trap the
project forbids; the bridge keeps it honest.

Why a subprocess (not PyO3 / in-process)? Sutra runs in Python today (it
compiles to PyTorch); a child process is the simplest honest bridge and adds no
Python-linking complexity. PyO3 (embed Python in Rust) is a possible future
tightening. Chosen by Emma 2026-05-25.

## Run

```bash
# from anywhere (the server path is resolved relative to this crate):
cargo run --release --manifest-path apps/gui-rust/Cargo.toml
# or the repo-root launcher:
!runGUIrust.bat
```

Click anywhere to count `0, 1, 2, 3, ...`; the glow steps left→right as the
count rises (its position is chosen from the count on the substrate), and the
title shows the live count. Esc or closing the window quits. It does not wrap
after 9 (we don't care past the count). Needs `cargo` and `python` on PATH.

```bash
cargo run --manifest-path apps/gui-rust/Cargo.toml -- --check
```

`--check` is a **headless** self-test: it spawns the substrate, requests init +
3 clicks, and asserts the count increments on the substrate and the frames come
back sized — verifying the whole bridge without a screen. (The live window
itself is verified by hand, like the other GUIs.)

This is a host-side dev/demo crate (std + one GUI dependency, `minifb`),
distinct from the `no_std`, no-dependency `orchestrator/` crate.
