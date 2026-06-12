"""Test the sparse-only-LIT bound-vector encoding (demos/font/font_bound.su).

Measured-working at runtime_dim=384, threshold 0.14 on the cosine output:
36/36 glyphs (A-Z + 0-9) pixel-exact vs the font oracle. See planning
docs (Yantra-side `planning/26-font-bound-vector-rewrite.md` carries the
full capacity-vs-dim table and the design history; the encoding moved
Sutra-side 2026-05-28 along with the rest of the font demo).

The encoding uses 63 basis_vector keys (``font_bound_p_00..p_24``,
``font_bound_LIT``, ``font_bound_UNLIT``, ``font_bound_c_A..c_9``). The
codebook fixture covering them at total dim 484 (semantic 384 + synthetic
100) ships in ``demos/font/fixtures/nomic-embed-text-d484.pt``, so this
test runs unconditionally on CI — no ollama needed.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

torch = pytest.importorskip("torch", reason="font_bound.su runs through real Sutra")

DEMO_FONT = pathlib.Path(__file__).resolve().parent
SUTRA_ROOT = DEMO_FONT.parent.parent

# font_data.py is the test-time oracle (sits in demos/font/).
sys.path.insert(0, str(DEMO_FONT))
from font_data import CHARS_ORDER, bits_for  # noqa: E402
from _display import read_real  # noqa: E402  (display/output boundary helper)

# The dim where the sparse-only-LIT encoding crosses no-overlap (per
# planning/26's measured table). Lower dims still produce mostly-correct
# fields but with edge-case overlap; raising this would make the test stricter.
_RUNTIME_DIM = 384

# The cosine threshold at which lit/unlit cleanly partition at the chosen dim.
# Measured 2026-05-28: at d=384, lit_min=0.182, unlit_max=0.106 across 900
# samples, so anything in (0.106, 0.182) works; 0.14 sits in the middle.
_THRESHOLD = 0.14


@pytest.fixture(scope="module")
def font_bound_mod():
    """Compile font_bound.su; skip the whole module if the codebook for
    its keys is not available (no ollama + no d484 fixture).

    A d484 fixture covering ``font_bound_*`` keys would let this run on CI
    unconditionally; it isn't committed yet (see planning/26 TODO).
    """
    sutra_sdk = SUTRA_ROOT / "sdk" / "sutra-compiler"
    sys.path.insert(0, str(sutra_sdk))
    from sutra_compiler import compile_su

    try:
        mod = compile_su(
            DEMO_FONT / "font_bound.su",
            llm_model="nomic-embed-text",
            runtime_dim=_RUNTIME_DIM,
        )
    except ImportError as e:
        # Catches both ModuleNotFoundError (no ollama installed) and the
        # simulated-CI ImportError that pytest plugins raise to block the
        # module. Either way, the codebook can't be populated for the 63
        # font_bound_* keys, so skip rather than fail-noisily.
        if "ollama" in str(e):
            pytest.skip(
                "font_bound.su needs basis_vector embeddings for 63 keys at "
                f"runtime_dim={_RUNTIME_DIM} (total d{_RUNTIME_DIM + 100}). "
                "No ollama installed + no d484 fixture covering font_bound_* "
                "keys committed yet — see planning/26 TODO."
            )
        raise
    return mod


def test_sparse_only_lit_recovers_every_glyph_pixel_exact(font_bound_mod) -> None:
    """Render every (char, x, y) cell through the substrate, threshold at 0.14,
    compare to the font oracle. All 900 cells across 36 glyphs must match —
    no per-glyph fudge, no allowed misses. If this fails, the encoding regressed
    or the threshold needs re-measurement, NOT a tolerance loosening.
    """
    vsa = font_bound_mod._VSA
    glyph_pixel_bound = font_bound_mod.glyph_pixel_bound

    mismatches: list[str] = []
    for ch in CHARS_ORDER:
        bits = bits_for(ch)
        for y in range(5):
            for x in range(5):
                sim = read_real(vsa, glyph_pixel_bound(float(x), float(y), float(ord(ch))))
                got = 1.0 if sim > _THRESHOLD else 0.0
                want = bits[y * 5 + x]
                if got != want:
                    mismatches.append(
                        f"{ch!r} at ({x},{y}): sim={sim:.3f}, threshold={_THRESHOLD}, "
                        f"-> {got}, oracle says {want}"
                    )
    assert not mismatches, (
        f"{len(mismatches)} cells mismatched at runtime_dim={_RUNTIME_DIM}, "
        f"threshold={_THRESHOLD}:\n  " + "\n  ".join(mismatches[:10])
    )


def test_lit_unlit_cosine_separation_holds(font_bound_mod) -> None:
    """Document the measured signal: lit-cell cosines should sit above the
    threshold, unlit-cell cosines below. Reports the actual extremes so a
    regression doesn't hide behind the per-glyph bit check above.
    """
    vsa = font_bound_mod._VSA
    glyph_pixel_bound = font_bound_mod.glyph_pixel_bound

    lit_sims: list[float] = []
    unlit_sims: list[float] = []
    for ch in CHARS_ORDER:
        bits = bits_for(ch)
        for y in range(5):
            for x in range(5):
                sim = read_real(vsa, glyph_pixel_bound(float(x), float(y), float(ord(ch))))
                (lit_sims if bits[y * 5 + x] > 0.5 else unlit_sims).append(sim)

    lit_min = min(lit_sims)
    unlit_max = max(unlit_sims)
    gap = lit_min - unlit_max
    # At runtime_dim=384 we measured lit_min=0.182, unlit_max=0.106 (gap=+0.076).
    # Require a non-negative gap and lit_min above the threshold by a margin —
    # if either tightens, the test signals the regression with the actual numbers.
    assert gap > 0.0, (
        f"lit/unlit cosines overlap at runtime_dim={_RUNTIME_DIM}: "
        f"lit_min={lit_min:.3f}, unlit_max={unlit_max:.3f}, gap={gap:.3f}"
    )
    assert lit_min > _THRESHOLD, (
        f"lit_min={lit_min:.3f} sits at-or-below threshold {_THRESHOLD} — "
        "encoding tightened, raise dim or pick a lower threshold"
    )
    assert unlit_max < _THRESHOLD, (
        f"unlit_max={unlit_max:.3f} sits at-or-above threshold {_THRESHOLD} — "
        "encoding noisier than measured, raise dim or pick a higher threshold"
    )
