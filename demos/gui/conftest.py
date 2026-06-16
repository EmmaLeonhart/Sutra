"""Pytest fixtures for the GUI demos' tests.

Same shape as demos/font/conftest.py: ship a codebook fixture and redirect
XDG_CACHE_HOME for the session so Sutra's on-disk codebook cache finds it
without needing a running ollama daemon.

Most GUI demos (count.su, frame.su, toggle.su, the θ hero) use only make_real
+ arithmetic + select — no basis_vector calls — so the codebook isn't read at
runtime; the d108 fixture is here for consistency and to keep the cache-load
path quiet. The EXCEPTION is the substrate glyph banner
(test_headline_banner_is_exactly_the_substrate_glyphs), which renders text via
demos/font's render_glyph (font_bound_antipodal.su, 63 basis_vector calls
compiling to runtime_dim=256, codebook cached at d356). The
nomic-embed-text-d356.pt fixture ships those `font_bound_antipodal_p_*` keys so
that test runs on CI without ollama. (The font demo's own d356 fixture holds the
DIFFERENT non-antipodal `font_bound_p_*` keys, hence a separate copy here.)
"""
from __future__ import annotations

import os
import pathlib
import shutil

import pytest

_FIXTURE_DIR = pathlib.Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session", autouse=True)
def _sutra_embedding_cache(tmp_path_factory):
    fixtures = sorted(_FIXTURE_DIR.glob("nomic-embed-text-d*.pt"))
    if not fixtures:
        yield
        return

    cache_home = tmp_path_factory.mktemp("sutra_xdg_cache_gui_demo")
    cache_dir = cache_home / "sutra" / "embeddings"
    cache_dir.mkdir(parents=True)
    for fx in fixtures:
        shutil.copy2(fx, cache_dir / fx.name)

    prev = os.environ.get("XDG_CACHE_HOME")
    os.environ["XDG_CACHE_HOME"] = str(cache_home)
    try:
        yield
    finally:
        if prev is None:
            os.environ.pop("XDG_CACHE_HOME", None)
        else:
            os.environ["XDG_CACHE_HOME"] = prev
