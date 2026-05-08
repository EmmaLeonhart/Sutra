"""Fixture-driven tests for the TS / JS → Sutra lowering pass.

Each fixture is a directory under `tests/fixtures/` containing:
  - `input.ts` or `input.js`  — the TypeScript / JavaScript source.
  - `expected.su`             — the expected lowered Sutra source.

The test normalizes both `lower(input)` output and `expected.su` by
stripping `//` comment lines and collapsing internal whitespace, then
compares. This lets `expected.su` carry human-written documentation
comments without forcing the lowering to reproduce them verbatim.
"""

from __future__ import annotations

import pathlib
import re

import pytest

from sutra_from_ts.lower import lower


FIXTURE_DIR = pathlib.Path(__file__).parent / "fixtures"


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
def test_fixture(name, input_path, expected_path):
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
