"""Pytest fixtures shared by the whole Yantra test suite.

The big one: ship a pre-warmed Sutra codebook so the suite doesn't need a
running ollama daemon. Sutra caches frozen-LLM embeddings to
``$XDG_CACHE_HOME/sutra/embeddings/<model>-d<dim>.pt`` on first fetch; once
populated, the codebook lookup never imports ollama (it's inside the cache-miss
branch in ``codegen_pytorch.py``). So the simplest reliable CI fix is to start
the suite with the cache already warm.

We do this **without touching the user's real ``~/.cache``**: redirect
``XDG_CACHE_HOME`` to a per-session tmp dir, copy the fixture in, and let the
tests run against that. If a future test introduces a key not in the fixture,
Sutra falls through to the cache-miss branch and the test fails with
``ModuleNotFoundError: ollama`` (in CI) — that's the clear signal to regenerate
the fixture, not a flaky test.

Regenerating: on any machine with an ollama daemon + the model pulled, run the
suite once (which populates ``~/.cache/sutra/embeddings/nomic-embed-text-d868.pt``)
and copy that file over the fixture.
"""
from __future__ import annotations

import os
import pathlib
import shutil

import pytest

# Sutra names its on-disk cache ``nomic-embed-text-d<dim>.pt`` where
# dim = semantic_dim + synthetic_dim. The default build is d868 (semantic
# 768 + synthetic 100); the 2026-05-27 audit shrunk substrate apps to
# smaller dims (calc/gui/font at semantic=8 -> d108; echo + kernel-test
# shared services at semantic=16 -> d116). Every fixture present in
# tests/fixtures/ at any of those dims is copied to the test-session cache.
# Run tools/regenerate_codebook_fixtures.py to add a new dim.
_FIXTURE_DIR = pathlib.Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session", autouse=True)
def _sutra_embedding_cache(tmp_path_factory):
    """Point Sutra's on-disk codebook cache at the committed pre-warmed fixtures
    for the whole test session, so tests don't need ollama to be installed or
    a daemon running. The user's real ``~/.cache`` is left alone.

    Copies every fixture matching ``nomic-embed-text-d*.pt`` into the test-session
    cache dir; Sutra picks the right one by filename based on whatever runtime_dim
    the test happens to use. If a test introduces a key not in any of the
    fixtures (or a dim not represented), Sutra falls through to the cache-miss
    branch and the test fails with ``ModuleNotFoundError: ollama`` (in CI) — the
    clear signal to regenerate the fixtures, not a flaky test.
    """
    fixtures = sorted(_FIXTURE_DIR.glob("nomic-embed-text-d*.pt"))
    if not fixtures:
        yield
        return

    cache_home = tmp_path_factory.mktemp("sutra_xdg_cache")
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
