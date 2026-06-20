"""Dimension-audit sweep — the build-time version of the per-program
"codebook unused, large dim is pure cost" warning.

CLAUDE.md "Subtler substrate breaches" #1 (the breach class the 2026-06-02
retrospective flagged as having the WEAKEST automation — it cost Yantra a silent
96× cost for weeks): a `.su` that calls NO `basis_vector`/`embed` and binds NO
axon string-keys does not use the LLM semantic subspace at all, so an LLM-sized
`semantic_dim` is paid for nothing (every rotation/codebook matrix scales as
dim²). `codegen_pytorch` already warns about this PER PROGRAM at compile time;
this sweep promotes it to a corpus-wide audit a reviewer / CI can run, using the
SAME signal (`collect_basis_vector_strings` covers basis_vector + embed,
`collect_axon_keys` covers axon string-keys — all three empty ⇒ codebook unused).

It is a STATIC analysis (parse only, no compile / no torch), so it is fast and
dependency-light.

**Advisory, not a hard gate (deliberate).** Using the default dim in a tutorial
or example is a legitimate choice, not a bug — so the sweep REPORTS the
codebook-free programs (the dimension-reducible set) and exits 0 by default. Pass
`--strict` to exit non-zero when any codebook-free program is found (for a
pipeline that wants to force an explicit dim choice). This avoids the
"hard gate blocks legitimate work" trap while still surfacing the breach class.

Run from `sdk/sutra-compiler/`:

    python ../../experiments/dimension_audit_sweep.py [--strict]
"""
from __future__ import annotations

import glob
import os
import sys

from sutra_compiler.axon_keys import collect_axon_keys
from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser
from sutra_compiler.simplify import collect_basis_vector_strings


def _uses_codebook(module) -> bool:
    """True iff the program touches the LLM semantic subspace — same signal the
    compile-time dimension warning uses."""
    strings = collect_basis_vector_strings(module)
    bound, read = collect_axon_keys(module)
    return bool(strings or bound or read)


def main() -> int:
    strict = "--strict" in sys.argv[1:]
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.dirname(here)
    patterns = [
        os.path.join(repo, "sdk", "sutra-compiler", "tests", "corpus", "valid", "*.su"),
        os.path.join(repo, "examples", "*.su"),
        os.path.join(repo, "examples", "**", "*.su"),
        os.path.join(repo, "demos", "**", "*.su"),
    ]
    files: list[str] = []
    for p in patterns:
        files.extend(glob.glob(p, recursive=True))
    files = sorted(set(files))

    parsed = 0
    skipped = 0
    programs_free: list[str] = []   # examples/ + demos/ — real programs
    fixtures_free: list[str] = []   # tests/corpus — language-feature fixtures
    for path in files:
        try:
            with open(path, encoding="utf-8") as f:
                src = f.read()
            lexer = Lexer(src, file=path)
            parser = Parser(lexer.tokenize(), file=path, diagnostics=lexer.diagnostics)
            module = parser.parse_module()
            if lexer.diagnostics.has_errors():
                skipped += 1
                continue
        except Exception:
            skipped += 1
            continue
        parsed += 1
        if _uses_codebook(module):
            continue
        rel = os.path.relpath(path, repo)
        if os.path.join("tests", "corpus") in rel:
            fixtures_free.append(rel)
        else:
            programs_free.append(rel)

    # The actionable signal: real programs (examples/demos) with no codebook —
    # if any of these is DEPLOYED at a large runtime_dim, it pays dim² for
    # nothing (the compile-time warning fires at that call site). Corpus
    # fixtures are language-feature unit tests, expected to be codebook-free —
    # reported separately as a count so they don't bury the signal.
    if programs_free:
        print("Dimension-reducible PROGRAMS (no codebook — if deployed at a "
              "large runtime_dim, that dim is pure cost; prefer a small dim):")
        for rel in programs_free:
            print(f"  {rel}")
    else:
        print("No codebook-free programs under examples/ or demos/.")
    print(f"\nDimension audit — {parsed} parsed, {skipped} skipped: "
          f"{len(programs_free)} codebook-free program(s) [actionable], "
          f"{len(fixtures_free)} codebook-free corpus fixture(s) [expected].")
    if programs_free and strict:
        print("--strict: failing because codebook-free programs were found.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
