"""Compile + execute examples/gui_window.su and open a real OS window
from the returned Window value via tkinter.

What this proves:

  Sutra source declares a `Window` class with `title`, `width`,
  `height` fields. The compiled program returns one such Window
  vector. This harness reads its fields back through the substrate-
  pure runtime accessors and opens an actual OS window with the
  declared dimensions and title.

  No new Sutra runtime intrinsic was added for "open a window" —
  the rendering happens on the host side, in the same factoring as
  the formal-verification paper's "compile to a graph, runtime
  executes the graph" framing: here the Sutra-produced graph is
  the Window declaration; the host runtime (this script) is the
  renderer.

Usage:
    python examples/_gui_runner.py
    python examples/_gui_runner.py --no-window    # smoke only

Exits with code 0 on success (window opened or smoke-passed).
"""
from __future__ import annotations

import argparse
import io
import os
import sys
import types

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(REPO, "sdk", "sutra-compiler"))

from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser
from sutra_compiler.codegen_pytorch import translate_module


def _compile(su_path: str) -> types.ModuleType:
    with open(su_path, encoding="utf-8") as f:
        src = f.read()
    py = translate_module(Parser(Lexer(src).tokenize()).parse_module())
    m = types.ModuleType("_gui_window")
    m.__file__ = su_path
    exec(compile(py, su_path, "exec"), m.__dict__)
    return m


def _strip_trailing_nuls(s: str) -> str:
    """The Sutra String runtime decode walks the whole axis block
    and returns trailing zero codepoints as NULs (\x00). For host
    display purposes the title ends at the first NUL — C-strlen
    semantics. (Codepoints past that may carry rotation-binding
    noise from other class fields stored on the same vector; safe
    to drop for display.)"""
    nul = s.find("\x00")
    return s if nul < 0 else s[:nul]


def read_window(m: types.ModuleType):
    """Run main() and decode the returned Window vector into a plain
    Python dict {title, width, height}."""
    w = m.main()
    vsa = m._VSA
    title_raw = vsa.string_to_python(vsa.axon_item(w, "title"))
    title = _strip_trailing_nuls(title_raw)
    width = int(round(vsa.real(vsa.axon_item(w, "width"))))
    height = int(round(vsa.real(vsa.axon_item(w, "height"))))
    return {"title": title, "width": width, "height": height}


def open_window(spec: dict) -> None:
    """Open an OS window from the {title, width, height} spec."""
    import tkinter as tk

    root = tk.Tk()
    root.title(spec["title"])
    root.geometry(f"{spec['width']}x{spec['height']}")
    label = tk.Label(
        root,
        text=(
            f"Sutra GUI demo\n\n"
            f"This window was declared in examples/gui_window.su\n"
            f"as a Sutra class with title/width/height fields.\n"
            f"This Python harness compiled the .su, executed it,\n"
            f"read the returned vector's fields back through the\n"
            f"substrate-pure runtime accessors, and opened this\n"
            f"OS window with those values.\n\n"
            f"title  = {spec['title']!r}\n"
            f"width  = {spec['width']}\n"
            f"height = {spec['height']}"
        ),
        justify="left",
        padx=20,
        pady=20,
        font=("TkDefaultFont", 10),
    )
    label.pack(expand=True, fill="both")
    root.mainloop()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--su", default=os.path.join(HERE, "gui_window.su"),
                    help="path to the .su to compile + execute")
    ap.add_argument("--no-window", action="store_true",
                    help="smoke only: compile + execute + print, do not open OS window")
    a = ap.parse_args()

    print(f"compiling {a.su} ...")
    m = _compile(a.su)
    print("ok; executing main() ...")
    spec = read_window(m)
    print(f"  title  = {spec['title']!r}")
    print(f"  width  = {spec['width']}")
    print(f"  height = {spec['height']}")

    if a.no_window:
        print("--no-window: smoke complete, not opening OS window")
        return 0

    print("opening OS window via tkinter ...")
    open_window(spec)
    return 0


if __name__ == "__main__":
    sys.exit(main())
