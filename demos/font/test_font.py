"""Test the font demo's substrate dispatch (apps/font).

Emma's text-input demo: each keypress shows the typed character as a 5x5
pixel glyph computed on the substrate. The substrate computations are:

  glyph_pixel(x, y, char_code)
      36-way defuzzified select over A-Z + 0-9. The lit/unlit decision for
      the typed character at (x, y) is the substrate's, not a host font
      lookup.
  step(prev_state, x, y, char_code)
      Emma's recurrent step: ``prev*0 + glyph_pixel(...)`` -- explicit
      substrate forget-then-add.

These tests:
1. Compile font.su once (shared across tests via _compile()'s memo).
2. For each of 36 chars, verify the substrate returns the right 5x5 bit
   pattern, compared cell-by-cell against ``tools/font_data.FONT_5x5``
   (the test-time oracle; NOT used on the runtime path).
3. Verify ``step()`` honours the * 0: passing a non-zero prev_state still
   produces the same glyph (prev is discarded on the substrate).

The render_glyph host wrapper is exercised too (one substrate call per
cell, no host glyph table).
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest

torch = pytest.importorskip("torch", reason="font.su runs through real Sutra")

# Migrated from Yantra/tests/test_font.py 2026-05-28. Files live alongside
# the demo now (demos/font/), not in separate apps/ + tests/ + tools/ dirs.
DEMO_FONT = pathlib.Path(__file__).resolve().parent

# font_data.py is the test-time oracle for what each glyph SHOULD be.
sys.path.insert(0, str(DEMO_FONT))
from font_data import CHARS_ORDER, FONT_5x5, bits_for  # noqa: E402
from _display import read_real  # noqa: E402  (display/output boundary helper)


def _load_font_demo():
    """Load demos/font/font_demo.py (a script, not a package). The first call
    triggers the font.su compile + codebook fetch; subsequent test functions
    reuse it via the module-level _COMPILED memo."""
    spec = importlib.util.spec_from_file_location(
        "font_demo", DEMO_FONT / "font_demo.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def fontmod():
    return _load_font_demo()


@pytest.mark.parametrize("char", CHARS_ORDER)
def test_glyph_pixel_matches_font_data_on_substrate(char: str, fontmod) -> None:
    """For every cell of every char, glyph_pixel() returns the lit/unlit
    bit the font data says it should -- decided ON the substrate (defuzzified
    select over 36 letter codepoints + 25 positions per letter)."""
    ns = fontmod._compile()
    glyph_pixel, vsa = ns["glyph_pixel"], ns["_VSA"]

    expected = bits_for(char)  # 25 floats, row-major
    code = float(ord(char))

    for y in range(5):
        for x in range(5):
            got = read_real(vsa, glyph_pixel(float(x), float(y), code))
            want = expected[y * 5 + x]
            # The defuzzified-select trick makes off-branch weights exactly 0
            # (exp(-1000) underflows in both float32 and float64), so the
            # returned bit should be exactly 0.0 or 1.0 -- tight tolerance.
            assert abs(got - want) < 1e-9, (
                f"{char!r} at ({x},{y}): substrate returned {got!r}, "
                f"font data says {want!r}"
            )


def test_step_zeros_previous_state_on_substrate(fontmod) -> None:
    """Emma's recurrent step: prev*0 + glyph_pixel(...). A non-zero prev_state
    MUST still produce the right glyph -- the * 0 is the substrate's explicit
    forget, not a host clear."""
    ns = fontmod._compile()
    step, vsa = ns["step"], ns["_VSA"]
    # Pick a glyph with a clear pattern: 'I' (lit positions: 1, 2, 3, 7, 12, 17, 21, 22, 23 -- the centre bar)
    code = float(ord("I"))
    expected = bits_for("I")

    # Feed a wildly non-zero prev_state and check the substrate still discards it.
    for y in range(5):
        for x in range(5):
            for prev_val in (0.0, 1.0, 7.5, -3.0):
                prev = vsa.make_real(prev_val)
                got = read_real(vsa, step(prev, float(x), float(y), code))
                want = expected[y * 5 + x]
                assert abs(got - want) < 1e-9, (
                    f"step(prev={prev_val}) at ({x},{y}) for 'I': got {got}, "
                    f"want {want} -- prev*0 didn't fully zero on the substrate"
                )


def test_render_glyph_produces_5x5_field(fontmod) -> None:
    """The host wrapper render_glyph drives 25 substrate calls and assembles
    a (5, 5) field. Spot-check a couple of glyphs end-to-end."""
    import numpy as np

    for char in ("A", "Z", "0", "5"):
        field = fontmod.render_glyph(float(ord(char)))
        assert field.shape == (5, 5), f"{char!r}: shape {field.shape}"
        # Field cells should be ~0 or ~1; nothing in between (one-hot substrate).
        worst_drift = float(np.min(np.minimum(np.abs(field), np.abs(field - 1.0))))
        assert worst_drift < 1e-9, (
            f"{char!r}: a cell drifted from {{0, 1}} by {worst_drift:.2e} -- "
            f"defuzzified select didn't saturate")
        # And the pattern matches the font data.
        expected = bits_for(char)
        for y in range(5):
            for x in range(5):
                assert abs(field[y, x] - expected[y * 5 + x]) < 1e-9, (
                    f"{char!r} at ({x},{y}): field {field[y, x]}, "
                    f"font {expected[y * 5 + x]}")


def test_font_data_has_36_glyphs() -> None:
    """Sanity: the oracle covers exactly the 36 chars (A-Z + 0-9) the substrate
    knows about."""
    assert len(FONT_5x5) == 36
    assert set(FONT_5x5.keys()) == set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
    assert len(CHARS_ORDER) == 36
    # Each glyph is 5 rows of 5 chars.
    for char, rows in FONT_5x5.items():
        assert len(rows) == 5, f"{char!r}: {len(rows)} rows"
        for row in rows:
            assert len(row) == 5, f"{char!r}: row {row!r}"
            assert set(row) <= {".", "#"}, f"{char!r}: bad row {row!r}"
