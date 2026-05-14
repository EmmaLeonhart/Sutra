"""CLI entry point for the TypeScript → Sutra transpiler.

Reads a `.ts` / `.js` (treated as untyped TS) source file, lowers it
through `lower.py` (~1500 lines: functions, classes, async/await,
discriminated unions, while/for/do-while loops, etc.), and writes
the resulting `.su` source to disk.

Default output path is the input filename with the TypeScript / JS
extension replaced by `.su`. Override with `-o`.

Example:

    $ python -m sutra_from_ts examples/array_sum.ts
    wrote examples/array_sum.su
"""

from __future__ import annotations

import argparse
import pathlib
import sys

from . import __version__


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="ts2su",
        description=(
            "Transpile a typed core of TypeScript (and JavaScript-as-"
            "untyped-TS) into Sutra (.su) source."
        ),
    )
    p.add_argument(
        "input",
        help="Path to a .ts or .js source file.",
    )
    p.add_argument(
        "-o", "--output",
        help="Path to write the .su output. Defaults to <input>.su.",
        default=None,
    )
    p.add_argument(
        "--version",
        action="version",
        version=f"ts2su {__version__}",
    )
    args = p.parse_args(argv)

    try:
        with open(args.input, "r", encoding="utf-8") as f:
            source = f.read()
    except OSError as e:
        print(f"ts2su: cannot read {args.input}: {e}", file=sys.stderr)
        return 2

    from .lower import lower
    # Pass source_path so relative imports resolve against the input
    # file's directory. Single-file inputs with no imports are
    # unaffected.
    sutra_source = lower(source, source_path=pathlib.Path(args.input))

    if args.output is None:
        # Default: replace .ts/.js extension with .su
        base = args.input
        for ext in (".ts", ".tsx", ".js", ".jsx", ".mjs"):
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
