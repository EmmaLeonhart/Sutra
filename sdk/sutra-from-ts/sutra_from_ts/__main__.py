"""CLI entry point for the TypeScript → Sutra transpiler.

Skeleton: argument parsing wires up, but no transpilation logic exists
yet. Calling the CLI prints a not-yet-implemented message pointing at
DESIGN.md and exits non-zero.
"""

from __future__ import annotations

import argparse
import sys

from . import __version__


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="ts2su",
        description=(
            "Transpile a typed core of TypeScript (and JavaScript-as-"
            "untyped-TS) into Sutra (.su) source. Skeleton stage — see "
            "sdk/sutra-from-ts/DESIGN.md."
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

    print(
        f"ts2su: not yet implemented. The transpiler is at the skeleton "
        f"stage — see sdk/sutra-from-ts/DESIGN.md for the planned "
        f"approach and the open questions blocking implementation. "
        f"Input was: {args.input}",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
