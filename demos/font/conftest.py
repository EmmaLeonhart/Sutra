"""Pytest fixtures for the font demo's tests.

Same shape as the Yantra/tests/conftest.py the migration came from: ship the
codebook fixture in ``demos/font/fixtures/`` and redirect XDG_CACHE_HOME for
the session so Sutra's on-disk codebook cache finds it without needing a
running ollama daemon. Each .pt fixture is named ``<model>-d<dim>.pt``
where ``dim = semantic_dim + synthetic_dim``; copy all of them.

The font app's own .su files have NO ``basis_vector`` calls (they use only
``make_real`` + arithmetic + ``select``), so the codebook isn't actually
read at runtime — but compile_su still NAMES a codebook file by dim, and
having the fixture present keeps the cache load path quiet. Where the
fixture matters is the bound-vector rewrite (font_bound.su), which DOES
use basis_vector for 63 keys; that fixture is the d484 file (not yet
committed — see planning/26 § TODO Yantra-side).
"""
from __future__ import annotations

import os
import pathlib
import shutil

import pytest

_FIXTURE_DIR = pathlib.Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session", autouse=True)
def _sutra_embedding_cache(tmp_path_factory):
    """Point Sutra's on-disk codebook cache at the per-demo committed
    fixtures; do not touch the user's real ``~/.cache``.
    """
    fixtures = sorted(_FIXTURE_DIR.glob("nomic-embed-text-d*.pt"))
    if not fixtures:
        yield
        return

    cache_home = tmp_path_factory.mktemp("sutra_xdg_cache_font_demo")
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
