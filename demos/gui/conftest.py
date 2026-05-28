"""Pytest fixtures for the GUI demos' tests.

Same shape as demos/font/conftest.py: ship a codebook fixture and redirect
XDG_CACHE_HOME for the session so Sutra's on-disk codebook cache finds it
without needing a running ollama daemon.

The GUI demos (count.su, frame.su, toggle.su) use only make_real +
arithmetic + select — no basis_vector calls — so the codebook isn't read
at runtime. The fixture is here for consistency with font/ and so the
cache-load path stays quiet.
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
