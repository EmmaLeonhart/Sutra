"""Fixture-driven tests for the TS / JS → Sutra lowering pass.

Each fixture is a directory under `tests/fixtures/` containing:
  - `input.ts` or `input.js`  — the TypeScript / JavaScript source.
  - `expected.su`             — the expected lowered Sutra source.

There are two complementary tests per fixture:

1. **Lowering test** (`test_fixture_lowering`): compares
   `lower(input)` against `expected.su` after normalizing comments
   and whitespace. This locks the lowering output but does not check
   that the result is runnable Sutra.

2. **Compilation test** (`test_fixture_compiles`): feeds
   `lower(input)` through the Sutra compiler and asserts it produces
   parsable Python. Marked `xfail` for fixtures whose lowered output
   uses constructs Sutra hasn't fully wired (e.g. C-style inline
   `while` / `for` — they parse but the codegen prefers a declared-
   loop form). The xfail markers are listed in
   `_COMPILE_KNOWN_FAILURES` and should shrink as the transpiler
   adds the loop-hoisting transform that emits the declared form.
"""

from __future__ import annotations

import pathlib
import re
import sys

import pytest

from sutra_from_ts.lower import lower


FIXTURE_DIR = pathlib.Path(__file__).parent / "fixtures"

# Fixtures whose lowered output does not yet compile through the
# Sutra compiler. Each entry maps fixture name → reason. Loop-using
# fixtures land here because the transpiler emits C-style inline
# `while (cond) { body }` which the Sutra codegen rejects in favor
# of a `while_loop NAME(...)` declared-form. Lifting these requires
# variable-flow analysis to identify mutated/captured locals + a
# function-hoist + slot-decl pass; tracked as a follow-on task.
_COMPILE_KNOWN_FAILURES = {
    "untyped_js": "JavaScriptObject runtime not implemented; `JavaScriptObject.from(7)` lowers to Python with `from` as an attribute name (invalid Python syntax)",
}


def _normalize(text: str) -> str:
    out_lines = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped.startswith("//"):
            continue
        out_lines.append(re.sub(r"\s+", " ", stripped))
    return "\n".join(out_lines)


def _collect_cases():
    cases = []
    if not FIXTURE_DIR.exists():
        return cases
    for d in sorted(FIXTURE_DIR.iterdir()):
        if not d.is_dir():
            continue
        inputs = sorted(d.glob("input.*"))
        expected = d / "expected.su"
        if inputs and expected.exists():
            cases.append((d.name, inputs[0], expected))
    return cases


_CASES = _collect_cases()


@pytest.mark.parametrize(
    "name,input_path,expected_path",
    _CASES,
    ids=[c[0] for c in _CASES],
)
def test_fixture_lowering(name, input_path, expected_path):
    src = input_path.read_text(encoding="utf-8")
    got = lower(src)
    expected = expected_path.read_text(encoding="utf-8")
    got_norm = _normalize(got)
    exp_norm = _normalize(expected)
    if got_norm != exp_norm:
        msg = (
            f"\nFixture: {name}\n"
            f"\n--- got (normalized) ---\n{got_norm}\n"
            f"\n--- expected (normalized) ---\n{exp_norm}\n"
            f"\n--- got (raw) ---\n{got}\n"
        )
        raise AssertionError(msg)


def _compile_with_sutra(sutra_src: str):
    """Helper that lazy-imports the sister sutra_compiler package and
    runs the full pipeline (lex → parse → codegen). Returns the
    emitted Python source on success; raises on any compile failure
    (including parser/validator errors)."""
    repo_root = pathlib.Path(__file__).resolve().parents[3]
    compiler_src = repo_root / "sdk" / "sutra-compiler"
    if str(compiler_src) not in sys.path:
        sys.path.insert(0, str(compiler_src))
    from sutra_compiler.codegen import translate_module  # noqa: WPS433
    from sutra_compiler.lexer import Lexer  # noqa: WPS433
    from sutra_compiler.parser import Parser  # noqa: WPS433

    lexer = Lexer(sutra_src, file="<fixture>")
    tokens = lexer.tokenize()
    parser = Parser(tokens, file="<fixture>", diagnostics=lexer.diagnostics)
    module = parser.parse_module()
    if lexer.diagnostics.has_errors():
        errs = "\n".join(d.format() for d in lexer.diagnostics.errors)
        raise AssertionError(f"sutra parse/validate errors:\n{errs}")
    py_src = translate_module(module)
    compile(py_src, "<fixture>", "exec")
    return py_src


@pytest.mark.parametrize(
    "name,input_path,expected_path",
    _CASES,
    ids=[c[0] for c in _CASES],
)
def test_fixture_compiles(name, input_path, expected_path):
    if name in _COMPILE_KNOWN_FAILURES:
        pytest.xfail(_COMPILE_KNOWN_FAILURES[name])
    src = input_path.read_text(encoding="utf-8")
    sutra_src = lower(src)
    _compile_with_sutra(sutra_src)
