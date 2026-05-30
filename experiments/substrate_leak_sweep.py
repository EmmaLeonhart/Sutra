"""Substrate-purity leak sweep.

Compiles every `.su` program under `tests/corpus/valid/` and
`examples/`, then greps the emitted Python for raw operators that
could be Sutra-typed at runtime. Catches the class of bug that
the 2026-04-30 audit missed (binary operators outside the
transcendental scope) — `%` slipped through for 33 days because no
corpus program used it; we want CI to notice the next one before
it lands.

Patterns flagged (user-program scope):

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

**Prelude scope (added 2026-05-28 per Audit.md #9):** the runtime
`_TorchVSA` class itself is ALSO scanned, with a different pattern set
keyed to host-extraction leak signatures (`.item()` outside an
allowlisted boundary method). This catches the class of leak that
`eq()` / `eq_synthetic()` had until `e2b8ee7a` — `make_truth(float(
cos.item()))` host-extraction inside what should be a substrate-pure
op. The user-program sweep cannot catch this because it excludes
the prelude (those `%` / `**` patterns ARE legitimate on substrate
tensors); the prelude sweep uses a method-level allowlist instead.

Run from `sdk/sutra-compiler/`:

    python ../../experiments/substrate_leak_sweep.py

Exit code 0 = no leaks. Non-zero = at least one suspicious pattern
found. Suitable for CI gating once the corpus is fully clean.
"""
from __future__ import annotations

import glob
import os
import re
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


# Methods inside `_TorchVSA` where host-extraction (`float()`, `.item()`)
# is the legitimate purpose — accessors / output edges / entry boundaries.
# Lines inside these methods are EXEMPT from the prelude leak scan.
# Sourced from Audit.md's LEGITIMATE + BORDERLINE entries plus the
# 2026-05-28 calibration pass against the actual codegen prelude.
_PRELUDE_LEAK_EXEMPT_METHODS = {
    # __init__: compile-time constants (PI/TAU = float(_math.pi))
    "__init__",
    # Literal-lift entry boundary (host literal → substrate vector)
    "make_real", "make_complex", "make_truth", "make_char",
    "make_string", "make_trit", "_st", "array_from_literal",
    "basis_vector", "load_matrix",
    # Coercion helpers — host Python value → substrate vector at entry.
    # These call `float()` on host scalars (the canonical entry boundary
    # form) and are documented Python-host-interop dispatch surfaces.
    "_as_any_vector", "_as_complex_vector", "_as_truth_vector",
    "_cnum",
    # Axon construction — accepts host Python int/str values and lifts
    # them via make_real / make_string (entry-boundary dispatch).
    "axon_add",
    # Array accessors — return host int / 0-d tensor; used as Python
    # for-loop bound and array indexing (host-output edge).
    "array_length", "array_get",
    # Monitoring/debugging accessors (CLAUDE.md-allowed)
    "component", "semantic", "synthetic", "slot", "real", "imag",
    "truth", "norm", "slot_read",
    # Output/commit edges (final extraction to host)
    "similarity", "dot", "argmax_cosine", "_argmax_cosine", "select",
    "string_to_python", "is_string", "is_char", "string_length",
    "string_char_at", "value", "await_value",
    # Promise state inspectors (host bool by design, monitoring scope)
    "isFulfilled", "isRejected", "isPending",
    # JS-interop coercion (intentional-compatibility carve-out)
    "js_strict_eq", "js_loose_eq", "js_strict_neq", "js_loose_neq",
    "_js_str_cmp", "js_add", "js_truthy", "js_to_number",
    "js_to_string", "js_to_boolean",
    # Embedding bootstrap / disk-cache (boot boundary, not op hot path)
    "embed", "embed_batch", "populate_sutradb", "prewarm_rotation_cache",
    "nearest_string",
    # Loop machinery — output gating extracts iters_active for telemetry
    "_step",
}

# Patterns flagged inside the prelude — host scalar extraction.
# `.item()` is the canonical leak signature. `float(...)` is more
# false-positive-prone, so we only flag the `float(*.item())` combo
# pattern, which is unambiguously host extraction.
_PRELUDE_LEAK_PATTERNS = [
    (".item()", "host scalar extraction (.item())"),
    ("float(", "host scalar extraction (float() inside non-boundary method)"),
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


def _enclosing_prelude_method(lines: list[str], idx: int) -> str | None:
    """Walk backwards from `idx` to find the enclosing `def NAME(` inside
    the runtime prelude class. Returns the method name or None if the line
    is not inside any method body."""
    for j in range(idx - 1, -1, -1):
        s = lines[j]
        if not s.strip():
            continue
        # Hit a class line — out of method scope without finding a def
        if s.startswith("class "):
            return None
        # Method def with indentation
        m = re.match(r"^(\s+)def (\w+)\(", s)
        if m:
            return m.group(2)
        # Hit a non-indented def/class — out of class scope
        if not s[0].isspace() and (s.startswith("def ") or s.startswith("class ")):
            return None
    return None


def _check_runtime_prelude(py: str) -> list[tuple[int, str, str, str]]:
    """Scan the runtime `_TorchVSA` class for host-extraction leak signatures.

    Per Audit.md #9: the user-program sweep excludes the prelude, so a leak
    like `eq()`'s `make_truth(float(cos.item()))` can survive for weeks. This
    function fills that gap by scanning the prelude with a method-level
    allowlist of boundary methods where host extraction is the documented
    purpose. Anything else with `.item()` or `float(...)` (excluding numeric
    literals and `_math.` constants) is flagged.

    Returns: list of (lineno, method, pattern, reason).
    """
    leaks: list[tuple[int, str, str, str]] = []
    lines = py.split("\n")
    in_vsa = False
    in_docstring = False
    for i, line in enumerate(lines):
        s = line.rstrip()
        if s.startswith("class _TorchVSA") or s.startswith("class _VSA"):
            in_vsa = True
            continue
        # Exit when we hit a non-indented line that starts a new top-level
        # def/class.
        if in_vsa and s and not s[0].isspace():
            if s.startswith("def ") or s.startswith("class "):
                in_vsa = False
                continue
        if not in_vsa:
            continue
        stripped = s.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # Docstring tracking: skip the body of triple-quoted docstrings.
        # The OLD `.item()` / `float()` patterns are mentioned in many
        # docstrings explaining why a fix was made (e.g. eq()'s "was
        # float(cos.item())"). Without this, every such docstring is a
        # false positive.
        triple_count = stripped.count('"""') + stripped.count("'''")
        if in_docstring:
            if triple_count >= 1:
                in_docstring = False
            continue
        if triple_count >= 1:
            # Single-line `"""..."""` stays out-of-docstring; opener
            # `"""...` (no closer on same line) enters docstring.
            if triple_count == 1:
                in_docstring = True
            continue
        # `.item()` is the unambiguous leak signature.
        if ".item()" in stripped:
            method = _enclosing_prelude_method(lines, i) or "?"
            if method in _PRELUDE_LEAK_EXEMPT_METHODS:
                continue
            leaks.append((i + 1, method, ".item()",
                          "host scalar extraction"))
            continue
        # `float(...)` is leak-shaped, but `float(0.0)`, `float(-1.0)`,
        # `float(_math.pi)` are legitimate literals/constants. Skip those.
        if "float(" in stripped:
            m = re.search(r"float\(([^)]+)\)", stripped)
            if not m:
                continue
            arg = m.group(1).strip()
            # Pure numeric literal or _math constant — OK
            if re.match(r"^[+-]?\d+(\.\d+)?(e[+-]?\d+)?$", arg):
                continue
            if arg.startswith("_math."):
                continue
            method = _enclosing_prelude_method(lines, i) or "?"
            if method in _PRELUDE_LEAK_EXEMPT_METHODS:
                continue
            leaks.append((i + 1, method, "float(...)",
                          "host extraction inside non-boundary method"))
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
    first_py: str | None = None
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
        if first_py is None:
            first_py = py
        leaks = _check_emitted(path, py)
        if leaks:
            print(f"\n{os.path.basename(path)}:")
            for lineno, pat, why in leaks:
                print(f"  line {lineno}  [{pat}]  {why}")
            total_leaks += len(leaks)

    # Prelude scan — same for every compiled .py, so do it once.
    prelude_leaks: list[tuple[int, str, str, str]] = []
    if first_py is not None:
        prelude_leaks = _check_runtime_prelude(first_py)
        if prelude_leaks:
            print(f"\n_TorchVSA runtime prelude:")
            for lineno, method, pat, why in prelude_leaks:
                print(f"  line {lineno}  [{method}]  {pat}  {why}")

    print(f"\nSweep complete — {compiled} compiled, {skipped} skipped, "
          f"{total_leaks} user-program leak(s) found, "
          f"{len(prelude_leaks)} runtime-prelude leak(s) found.")
    return 1 if (total_leaks > 0 or len(prelude_leaks) > 0) else 0


if __name__ == "__main__":
    sys.exit(main())
