"""Shared fixtures for the learned-ops experiment tests.

Runs inside the transformer-vm submodule's uv venv (which has torch +
transformer_vm installed); this conftest puts the repo `src/` on sys.path so
`import learned_ops` works.
"""
import os
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2]          # .../src
REPO = SRC.parent                                   # repo root
VM_DATA = REPO / "replication_target" / "transformer-vm" / "transformer_vm" / "data"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture(scope="session")
def built_model():
    """The universal analytic transformer (built via MILP, ~few seconds)."""
    from transformer_vm.build import build

    model, all_tokens, tok_to_idx_map = build()  # no plan_path -> MILP -> universal
    model.eval()
    return model, all_tokens, tok_to_idx_map


@pytest.fixture(scope="session")
def load_program_idx():
    """Loader: program name -> list of token ids for its compiled .txt prefix."""
    def _load(name, tok_to_idx_map):
        path = VM_DATA / f"{name}.txt"
        with open(path) as f:
            tokens = f.read().split()
        return [tok_to_idx_map[t] for t in tokens]

    return _load
