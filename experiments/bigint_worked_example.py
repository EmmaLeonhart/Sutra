"""BigInt worked example — `add_bigint("99999", "1") = "100000"` via the
new substrate intrinsics.

Per planning/sutra-spec/arbitrary-precision.md "Implementation plan" step 5
("Worked example test: `add_bigint("99999", "1") = "100000"` showing carry
propagation step-by-step"). This script ships that test.

Demonstrates end-to-end:
- The compiled .su uses `digit_array_add(a, b, 10)` on substrate vectors
  whose first `max_digits` slots hold the radix-10 digits (little-endian:
  digits[0] = ones, digits[1] = tens, ...).
- Host parses "99999" → digit tensor → calls into compiled Sutra → reads
  the resulting digit tensor → formats back to "100000".
- No host-side arithmetic on the digit values; the host only does parse
  (string → tensor) and format (tensor → string) at the boundaries.

Usage:
    python experiments/bigint_worked_example.py

Exit 0 on all cases passing; non-zero otherwise. Suitable as a regression
gate once wired into the test suite.
"""
from __future__ import annotations

import os
import sys
import types

HERE = os.path.abspath(os.path.dirname(__file__))
REPO = os.path.dirname(HERE)
SDK = os.path.join(REPO, "sdk", "sutra-compiler")
if SDK not in sys.path:
    sys.path.insert(0, SDK)

import torch

from sutra_compiler.codegen_pytorch import translate_module as translate_pytorch
from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser


_SU_SOURCE = """\
// Worked example for planning/sutra-spec/arbitrary-precision.md step 5.
// Uses the digit_array_add substrate intrinsic on two N-digit arrays
// packed as 1-d substrate vectors. Returns the resulting digit array
// without unpacking.
function vector add_bigint_digits(vector a, vector b) {
    return digit_array_add(a, b, 10);
}

function string main() { return "ok"; }
"""


def _compile():
    lx = Lexer(_SU_SOURCE, file="bigint_worked.su")
    toks = lx.tokenize()
    if lx.diagnostics.has_errors():
        for d in lx.diagnostics.errors:
            print(f"LEX/PARSE ERROR: {d.format()}")
        raise SystemExit(1)
    mod_ast = Parser(toks, file="bigint_worked.su",
                     diagnostics=lx.diagnostics).parse_module()
    if lx.diagnostics.has_errors():
        for d in lx.diagnostics.errors:
            print(f"PARSE ERROR: {d.format()}")
        raise SystemExit(1)
    py = translate_pytorch(mod_ast, runtime_dim=16, runtime_seed=42)
    m = types.ModuleType("bigint_worked")
    exec(compile(py, "<bigint_worked>", "exec"), m.__dict__)
    return m


def parse_to_digits(s: str, max_digits: int, vsa) -> torch.Tensor:
    """Parse a non-negative decimal string into a digit tensor of length
    max_digits. Little-endian: digits[0] is ones, digits[1] is tens.
    Raises ValueError if the string has too many digits to fit."""
    if not s or not s.isdigit():
        raise ValueError(f"not a non-negative decimal string: {s!r}")
    if len(s) > max_digits:
        raise ValueError(f"{s!r} too wide for max_digits={max_digits}")
    digits = [0] * max_digits
    for i, ch in enumerate(reversed(s)):
        digits[i] = int(ch)
    return torch.tensor(digits, dtype=vsa.dtype, device=vsa.device)


def digits_to_str(digits: torch.Tensor) -> str:
    """Format a little-endian digit tensor as a decimal string, stripping
    leading zeros."""
    rounded = [int(round(float(d))) for d in digits]
    # Strip trailing zeros (which are leading zeros in big-endian view)
    while len(rounded) > 1 and rounded[-1] == 0:
        rounded.pop()
    return "".join(str(d) for d in reversed(rounded))


def add_bigint(mod, a: str, b: str, max_digits: int = 16) -> str:
    vsa = mod._VSA
    da = parse_to_digits(a, max_digits, vsa)
    db = parse_to_digits(b, max_digits, vsa)
    out = mod.add_bigint_digits(da, db)
    return digits_to_str(out)


def main() -> int:
    mod = _compile()
    # (a, b, expected, max_digits) — max_digits controls digit array width.
    # When a+b overflows max_digits, the spec documents saturate-by-drop
    # (top-digit carry-out is silently lost); the overflow case below
    # exercises that behavior explicitly.
    cases = [
        ("99999", "1", "100000", 16),       # the spec's worked example
        ("47", "53", "100", 16),
        ("999", "1", "1000", 16),
        ("123", "456", "579", 16),
        ("12345678", "87654321", "99999999", 16),    # no carry, 8 digits
        ("1", "9999999999999999", "10000000000000000", 20),  # cascade past 16
        ("0", "0", "0", 16),
        ("5000000000000", "5000000000000", "10000000000000", 16),  # mid-width cascade
        # Overflow: a+b needs 17 digits but max_digits=16; top carry dropped.
        ("1", "9999999999999999", "0", 16),
    ]
    print("BigInt worked example — add_bigint via substrate intrinsics")
    print(f"{'a':>20} + {'b':>20} -> {'expected':>20} | {'got':>20}  status")
    all_ok = True
    for case in cases:
        a, b, expected, max_digits = case
        got = add_bigint(mod, a, b, max_digits=max_digits)
        ok = (got == expected)
        all_ok = all_ok and ok
        status = "[OK]" if ok else "[FAIL]"
        print(f"{a:>20} + {b:>20} -> {expected:>20} | {got:>20}  {status}")
    print(f"\nall OK: {all_ok}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
