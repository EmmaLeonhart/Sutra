"""Substrate-purity leak sweep.

Compiles every `.su` program under `tests/corpus/valid/` and
`examples/`, then greps the emitted Python for raw operators that
could be Sutra-typed at runtime. Catches the class of bug that
the 2026-04-30 audit missed (binary operators outside the
transcendental scope) — `%` slipped through for 33 days because no
corpus program used it; we want CI to notice the next one before
it lands.

Patterns flagged:

  ` ** `     power (no Sutra operator, so any occurrence in codegen
             is suspicious)
  ` // `     floor division (same)
  ` % `      modulus — should always be `_VSA.fmod` now
  ` << `     bit-shift left (lexed-but-not-parsed)
  ` >> `     bit-shift right (lexed-but-not-parsed)
  ` & `      bitwise and (lexed-but-not-parsed; ` && ` is fine)
  ` | `      bitwise or  (lexed-but-not-parsed; ` || ` is fine)
  ` ^ `      bitwise xor (lexed-but-not-parsed)

Exclusions: comments, docstrings, anything inside the runtime
`_VSA` class definition (those `%` / `**` are legitimate Python on
substrate tensors), and lines that mention `_VSA.` directly
(already routed).

Run from `sdk/sutra-compiler/`:

    python ../../experiments/substrate_leak_sweep.py

Exit code 0 = no leaks. Non-zero = at least one suspicious pattern
found. Suitable for CI gating once the corpus is fully clean.
"""
from __future__ import annotations

import glob
import os
import sys

from sutra_compiler.codegen_pytorch import translate_module as torch_translate
from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser


SUSPICIOUS = [
    (" ** ",  "power — no Sutra operator should emit this"),
    (" // ",  "floor-division — no Sutra operator should emit this"),
    (" % ",   "modulus — should route through _VSA.fmod"),
    (" << ",  "bit-shift left — token reserved, not parsed"),
    (" >> ",  "bit-shift right — token reserved, not parsed"),
    (" & ",   "bitwise and — token reserved, not parsed"),
    (" | ",   "bitwise or — token reserved, not parsed"),
    (" ^ ",   "bitwise xor — token reserved, not parsed"),
]


def _is_inside_vsa_class(lines: list[str], idx: int) -> bool:
    """Walk backwards looking for `class _TorchVSA` or `class _VSA` —
    if we hit one before hitting an unindented `def ` / `class ` at
    column 0, the line is inside the runtime class body. The runtime
    class IS substrate, so raw operators there are legitimate."""
    for j in range(idx - 1, -1, -1):
        s = lines[j]
        if not s.strip():
            continue
        if s.startswith("class _TorchVSA") or s.startswith("class _VSA"):
            return True
        if (s.startswith("class ") or s.startswith("def ")
                or (s and not s[0].isspace() and not s.startswith("#"))):
            if s.startswith("class _"):
                continue
            return False
    return False


def _check_emitted(path: str, py: str) -> list[tuple[int, str, str]]:
    leaks: list[tuple[int, str, str]] = []
    lines = py.split("\n")
    for i, line in enumerate(lines):
        # Skip comments, docstrings, blank, and lines inside the
        # _VSA runtime class.
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith('"""') or stripped.startswith("'''"):
            continue
        if "_VSA." in line:
            continue
        if _is_inside_vsa_class(lines, i):
            continue
        for pat, why in SUSPICIOUS:
            if pat in line:
                leaks.append((i + 1, pat.strip(), why))
                break
    return leaks


def main() -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.dirname(here)
    patterns = [
        os.path.join(repo, "sdk", "sutra-compiler", "tests", "corpus",
                     "valid", "*.su"),
        os.path.join(repo, "examples", "*.su"),
    ]
    files: list[str] = []
    for p in patterns:
        files.extend(sorted(glob.glob(p)))

    total_leaks = 0
    skipped = 0
    compiled = 0
    for path in files:
        with open(path, encoding="utf-8") as f:
            src = f.read()
        lexer = Lexer(src, file=path)
        tokens = lexer.tokenize()
        parser = Parser(tokens, file=path, diagnostics=lexer.diagnostics)
        try:
            module = parser.parse_module()
        except Exception:
            skipped += 1
            continue
        if lexer.diagnostics.has_errors():
            skipped += 1
            continue
        try:
            py = torch_translate(module)
        except Exception:
            skipped += 1
            continue
        compiled += 1
        leaks = _check_emitted(path, py)
        if leaks:
            print(f"\n{os.path.basename(path)}:")
            for lineno, pat, why in leaks:
                print(f"  line {lineno}  [{pat}]  {why}")
            total_leaks += len(leaks)

    print(f"\nSweep complete — {compiled} compiled, {skipped} skipped, "
          f"{total_leaks} leak(s) found.")
    return 1 if total_leaks > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
