"""Test the antipodal-filler bound-vector encoding (demos/font/font_bound_antipodal.su).

After the bind(p,LIT)/(p,UNLIT) encoding failed (planning/26 § negative
table) and the sparse-only-LIT encoding worked at runtime_dim=384, the
third encoding tries: every cell bound, lit with +LIT, unlit with -LIT.
The crosstalk from non-target bindings partially cancels (some +LIT, some
-LIT) instead of all-pushing-toward-LIT as sparse-only does — so the
encoding should work at a smaller dim.

Measured 2026-05-28: works at runtime_dim ≥ 256, threshold 0.0 — 36/36
glyphs pixel-exact at 93 ms/render. Compared to sparse-only-LIT's dim≥384:
1.5× lower dim threshold, same wall-clock speed (dispatch-bound, not
tensor-bound).

Codebook fixture is at demos/font/fixtures/nomic-embed-text-d356.pt
(semantic 256 + synthetic 100). 63 antipodal-namespaced keys
(``font_bound_antipodal_p_00..p_24``, ``font_bound_antipodal_LIT``,
``font_bound_antipodal_UNLIT``, ``font_bound_antipodal_c_A..c_9``).
Distinct from the sparse-only encoding's ``font_bound_*`` namespace so
the two variants don't share embeddings.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

torch = pytest.importorskip("torch", reason="font_bound_antipodal.su runs through real Sutra")

DEMO_FONT = pathlib.Path(__file__).resolve().parent
SUTRA_ROOT = DEMO_FONT.parent.parent

sys.path.insert(0, str(DEMO_FONT))
from font_data import CHARS_ORDER, bits_for  # noqa: E402
from _display import read_real  # noqa: E402  (display/output boundary helper)

_RUNTIME_DIM = 256
_THRESHOLD = 0.0  # Antipodal: lit cosines positive, unlit negative; midpoint is 0.


@pytest.fixture(scope="module")
def font_bound_antipodal_mod():
    sutra_sdk = SUTRA_ROOT / "sdk" / "sutra-compiler"
    sys.path.insert(0, str(sutra_sdk))
    from sutra_compiler import compile_su

    try:
        mod = compile_su(
            DEMO_FONT / "font_bound_antipodal.su",
            llm_model="nomic-embed-text",
            runtime_dim=_RUNTIME_DIM,
        )
    except ImportError as e:
        if "ollama" in str(e):
            pytest.skip(
                "font_bound_antipodal.su needs basis_vector embeddings for 63 "
                "antipodal-namespaced keys at runtime_dim={}; expected fixture is "
                "demos/font/fixtures/nomic-embed-text-d356.pt".format(_RUNTIME_DIM)
            )
        raise
    return mod


def test_antipodal_recovers_every_glyph_pixel_exact(font_bound_antipodal_mod) -> None:
    """Every cell of every glyph: cosine to LIT lands on the correct side of 0.
    900 cells across 36 glyphs, no fudge, no allowed misses.
    """
    vsa = font_bound_antipodal_mod._VSA
    glyph_pixel_antipodal = font_bound_antipodal_mod.glyph_pixel_antipodal

    mismatches: list[str] = []
    for ch in CHARS_ORDER:
        bits = bits_for(ch)
        for y in range(5):
            for x in range(5):
                sim = read_real(vsa, glyph_pixel_antipodal(float(x), float(y), float(ord(ch))))
                got = 1.0 if sim > _THRESHOLD else 0.0
                want = bits[y * 5 + x]
                if got != want:
                    mismatches.append(
                        f"{ch!r} at ({x},{y}): sim={sim:+.3f}, threshold={_THRESHOLD}, "
                        f"-> {got}, oracle says {want}"
                    )
    assert not mismatches, (
        f"{len(mismatches)} cells mismatched at runtime_dim={_RUNTIME_DIM}, "
        f"threshold={_THRESHOLD}:\n  " + "\n  ".join(mismatches[:10])
    )


def test_antipodal_cosine_separation_holds(font_bound_antipodal_mod) -> None:
    """Lit-cell cosines should be positive, unlit-cell cosines negative.
    A non-zero gap confirms the antipodal-filler design is doing what
    sparse-only-LIT can't at this dim.
    """
    vsa = font_bound_antipodal_mod._VSA
    glyph_pixel_antipodal = font_bound_antipodal_mod.glyph_pixel_antipodal

    lit_sims: list[float] = []
    unlit_sims: list[float] = []
    for ch in CHARS_ORDER:
        bits = bits_for(ch)
        for y in range(5):
            for x in range(5):
                sim = read_real(vsa, glyph_pixel_antipodal(float(x), float(y), float(ord(ch))))
                (lit_sims if bits[y * 5 + x] > 0.5 else unlit_sims).append(sim)

    lit_min = min(lit_sims)
    unlit_max = max(unlit_sims)
    gap = lit_min - unlit_max
    # Measured at dim=256: lit_min=+0.028, unlit_max=-0.024, gap=+0.052.
    assert gap > 0.0, (
        f"lit/unlit overlap at runtime_dim={_RUNTIME_DIM}: "
        f"lit_min={lit_min:+.3f}, unlit_max={unlit_max:+.3f}, gap={gap:+.3f}"
    )
    assert lit_min > 0.0, f"lit_min={lit_min:+.3f} not strictly positive"
    assert unlit_max < 0.0, f"unlit_max={unlit_max:+.3f} not strictly negative"
