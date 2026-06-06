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
_COMPILE_KNOWN_FAILURES: dict[str, str] = {
    # `async function` and `await` parse cleanly into the Sutra
    # surface today (queue.md item 1, phase 2 landed 2026-05-09)
    # but the codegen lowering pass is still phase 3 — the codegen
    # currently errors with a planning/sutra-spec/promises.md
    # pointer when it sees an async fn or await expr. Lifts as soon
    # as the lowering lands.
    "async_promise_basic": "lowering pass not implemented yet — see promises.md",
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
    # Pass input_path so module imports can resolve relative to the
    # fixture directory. Single-file fixtures with no `import`
    # statements behave identically — source_path is only consulted
    # when the lowerer encounters an import.
    got = lower(src, source_path=input_path)
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
    sutra_src = lower(src, source_path=input_path)
    _compile_with_sutra(sutra_src)


# Fixtures with a callable `main()` and a known ground-truth result, run
# end-to-end on the real Sutra substrate (compile AND run AND match), not
# just the parse/codegen syntax check above. The axon-field-read fixtures
# are here specifically so the `.real()` projection fix (2026-06-06) can't
# silently regress back to returning zeros.
_RUNNABLE_FIXTURES = {
    "interface_pass": 25.0,       # distance_squared({x:3, y:4})
    "discriminated_union": 25.0,  # area({kind:"circle", r:5})
}


def _extract_result(out: str) -> float:
    last = out.splitlines()[-1].strip() if out else ""
    m = re.search(r"tensor\(\s*(-?\d+\.?\d*)", last) or re.search(
        r"(-?\d+\.\d+|-?\d+)", last
    )
    if m is None:
        raise AssertionError(f"no numeric result in output:\n{out}")
    return float(m.group(1))


@pytest.mark.parametrize("fixture_name,expected", sorted(_RUNNABLE_FIXTURES.items()))
def test_fixture_runs_on_substrate(tmp_path, fixture_name, expected):
    """Transpile -> run on the real substrate via `sutrac --run` -> assert
    the decoded result. Skipped without torch so CI without the runtime
    stays green."""
    pytest.importorskip("torch")
    import subprocess

    fixture = sorted((FIXTURE_DIR / fixture_name).glob("input.*"))[0]
    sutra_src = lower(fixture.read_text(encoding="utf-8"), source_path=fixture)
    su_path = tmp_path / f"{fixture_name}.su"
    su_path.write_text(sutra_src, encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "-m", "sutra_compiler", "--run", str(su_path)],
        capture_output=True,
        text=True,
    )
    out = (proc.stdout + proc.stderr).strip()
    assert proc.returncode == 0, f"sutrac --run failed:\n{out}"
    got = _extract_result(out)
    assert abs(got - expected) < 0.5, (
        f"{fixture_name}: expected ~{expected}, got {got}\n{out}"
    )
