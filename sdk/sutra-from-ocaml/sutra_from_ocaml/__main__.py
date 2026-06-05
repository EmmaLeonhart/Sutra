"""CLI entry point for the OCaml → Sutra transpiler.

Reads an `.ml` source file, lowers it through `lower.py`, and writes the
resulting `.su` source to disk. Default output path is the input
filename with `.ml` replaced by `.su`; override with `-o`.

Example:

    $ python -m sutra_from_ocaml examples/add.ml
    wrote examples/add.su
"""

from __future__ import annotations

import argparse
import pathlib
import sys

from . import __version__


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="ocaml2su",
        description="Transpile a functional core of OCaml into Sutra (.su) source.",
    )
    p.add_argument("input", help="Path to a .ml source file.")
    p.add_argument(
        "-o", "--output",
        help="Path to write the .su output. Defaults to <input>.su.",
        default=None,
    )
    p.add_argument(
        "--version",
        action="version",
        version=f"ocaml2su {__version__}",
    )
    args = p.parse_args(argv)

    try:
        with open(args.input, "r", encoding="utf-8") as f:
            source = f.read()
    except OSError as e:
        print(f"ocaml2su: cannot read {args.input}: {e}", file=sys.stderr)
        return 2

    from .lower import lower
    sutra_source = lower(source, source_path=pathlib.Path(args.input))

    if args.output is None:
        base = args.input
        for ext in (".ml", ".mli"):
            if base.endswith(ext):
                base = base[:-len(ext)]
                break
        out_path = base + ".su"
    else:
        out_path = args.output

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(sutra_source)
    print(f"wrote {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
