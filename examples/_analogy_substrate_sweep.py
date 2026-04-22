"""Run the capital-country analogy on three substrates via the
@embedding directive.

Exercises the per-program embedding-space override (STATUS #1,
landed 2026-04-22). The harness compiles three different .su files,
each of which declares its substrate in a `// @embedding:` directive
at the top of the source. No Python-side substrate override needed;
the directive is parsed by `_su_harness.compile_to_module`.

Each program runs the same 5-pair capital-country associative memory
and queries `country_of(paris)`, `country_of(tokyo)`, etc. Report
the winner per substrate.

The point: one can write a .su program that declares its target
substrate at the top, and the harness respects that without any
configuration. The three files are:

- `examples/analogy.su`         (no directive -> default: nomic-embed-text)
- `examples/analogy_mxbai.su`   (@embedding: mxbai-embed-large)
- `examples/analogy_minilm.su`  (@embedding: all-minilm)

Usage: python examples/_analogy_substrate_sweep.py
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _su_harness import compile_to_module  # noqa: E402


def run_one(path: str, label: str) -> int:
    queries = [
        ("paris",  "france"),
        ("tokyo",  "japan"),
        ("london", "uk"),
        ("rome",   "italy"),
        ("cairo",  "egypt"),
    ]
    print("-" * 72)
    print(f"{label}  [{os.path.basename(path)}]")
    print("-" * 72)
    mod = compile_to_module(path)
    correct = 0
    for city, expected in queries:
        v = getattr(mod, city)
        got = mod.country_of(v)
        mark = "OK" if got == expected else "FAIL"
        print(f"  country_of({city:<6}) expected={expected:<7} got={got:<8} {mark}")
        correct += int(got == expected)
    print(f"  {correct}/5 correct")
    return correct


def main() -> int:
    print("=" * 72)
    print("Capital-country analogy across substrates (via @embedding directive)")
    print("=" * 72)

    programs = [
        ("examples/analogy.su",       "nomic-embed-text (default, no directive)"),
        ("examples/analogy_mxbai.su", "mxbai-embed-large (@embedding directive)"),
        ("examples/analogy_minilm.su", "all-minilm (@embedding directive)"),
    ]
    results = []
    for rel, label in programs:
        path = os.path.join(os.path.dirname(HERE), rel)
        correct = run_one(path, label)
        results.append((label, correct))

    print()
    print("=" * 72)
    print("Summary")
    print("=" * 72)
    for label, correct in results:
        print(f"  {correct}/5   {label}")
    return 0 if all(c == 5 for _, c in results) else 1


if __name__ == "__main__":
    sys.exit(main())
