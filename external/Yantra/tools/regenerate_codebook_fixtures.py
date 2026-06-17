"""Regenerate Sutra codebook fixtures at the dims the test suite needs.

Background: tests/conftest.py points Sutra's on-disk codebook cache at a
committed fixture so the test suite doesn't need a running ollama daemon
in CI. Sutra names the cache file ``nomic-embed-text-d<dim>.pt`` where
``dim = semantic_dim + synthetic_dim``. Until 2026-05-27 the suite only
needed the default dim (semantic=768 + synthetic=100 = 868). The audit
that dropped substrate apps to smaller semantic dims (font dim=8, calc
dim=8, echo dim=16) means tests now need additional fixtures at total
dims 108 (8+100) and 116 (16+100).

This script regenerates the small-dim fixtures by:
1. Reading the canonical d868 fixture for the key list.
2. Re-embedding each key at the smaller dim via the same code path the
   runtime uses (calling ``_TorchVSA(semantic_dim=N).embed(name)`` once
   per key, which fetches the LLM embedding, mean-centres, normalises,
   slices to semantic_dim, pads to total_dim, normalises again).
3. Saving the resulting codebook to ``tests/fixtures/<name>-d<total>.pt``.

Requires a running ollama daemon with ``nomic-embed-text`` pulled.
Re-run any time the audit lands a new dim choice for an app or service.
"""
from __future__ import annotations

import pathlib
import shutil
import sys
import tempfile
import types

import torch

_REPO = pathlib.Path(__file__).resolve().parent.parent
_FIXTURES = _REPO / "tests" / "fixtures"
_CANONICAL = _FIXTURES / "nomic-embed-text-d868.pt"

# Each entry: (semantic_dim, synthetic_dim). The cache file name is
# nomic-embed-text-d(semantic+synthetic).pt. Synthetic is hardcoded at 100
# in the codegen prelude, so all entries here share synthetic=100; the
# semantic dim is what varies per app's choice (see planning/27).
TARGET_DIMS = [
    (8, 100),    # apps/calc (AXON_WIDTH=8), apps/gui/* (runtime_dim=8), apps/font (runtime_dim=8) -> d108
    (16, 100),   # apps/echo (axon_width=16), kernel test default (runtime_dim=16) -> d116
]


def _compile_minimal_su(semantic_dim: int) -> types.ModuleType:
    """Compile a one-liner .su at the target dim so we get a real _TorchVSA
    instance with the right embed() implementation. Cheaper than re-deriving
    the codegen pipeline by hand."""
    sutra_sdk = _REPO.parent.parent / "sdk" / "sutra-compiler"  # Yantra vendored in-tree under Sutra
    if str(sutra_sdk) not in sys.path:
        sys.path.insert(0, str(sutra_sdk))
    from sutra_compiler import compile_su

    # Minimal valid .su — the compile pass needs SOMETHING to translate.
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="sutra_fixture_")) / "stub.su"
    tmp.write_text(
        "function vector main() { return make_real(0.0); }\n",
        encoding="utf-8",
    )
    return compile_su(
        tmp,
        llm_model="nomic-embed-text",
        runtime_dim=semantic_dim,
    )


def regenerate(semantic_dim: int, synthetic_dim: int) -> pathlib.Path:
    total = semantic_dim + synthetic_dim
    fixture_path = _FIXTURES / f"nomic-embed-text-d{total}.pt"
    print(f"[regen] dim semantic={semantic_dim} synthetic={synthetic_dim} -> d{total}")

    # Get the canonical key list. Don't reuse the canonical values — they
    # were embedded at a different semantic_dim and slicing them to a
    # smaller dim would skip the mean-center + normalize re-pass.
    if not _CANONICAL.exists():
        raise FileNotFoundError(
            f"canonical fixture missing: {_CANONICAL} — cannot derive the key list"
        )
    canonical = torch.load(_CANONICAL, map_location="cpu", weights_only=False)
    keys = sorted(canonical.keys())
    print(f"[regen]   key count from canonical: {len(keys)}")

    mod = _compile_minimal_su(semantic_dim)
    vsa = mod._VSA

    # Use embed_batch for one Ollama round-trip per dim.
    vsa.embed_batch(keys)
    # vsa._codebook now has every key at shape (semantic+synthetic,).
    new = {k: v.detach().cpu() for k, v in vsa._codebook.items()}

    # Save in the same format Sutra writes (per the codegen _write_disk_cache).
    fixture_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(new, fixture_path)
    print(f"[regen]   wrote {fixture_path} ({len(new)} keys, dtype={next(iter(new.values())).dtype}, shape={next(iter(new.values())).shape})")
    return fixture_path


def main() -> None:
    if not _CANONICAL.exists():
        sys.exit(f"canonical fixture missing: {_CANONICAL}")
    for sem, syn in TARGET_DIMS:
        regenerate(sem, syn)
    print("[regen] done.")


if __name__ == "__main__":
    main()
