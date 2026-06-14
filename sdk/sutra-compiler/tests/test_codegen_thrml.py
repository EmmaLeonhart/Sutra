"""Tests for the ADDITIVE thrml backend (queue.md approach G).

Two guarantees:
1. Non-destructive: `--emit-thrml` is separate from the PyTorch `--emit`/`--run`
   path; an unsupported construct gives a clean `thrml-codegen:` diagnostic (exit
   2), never a traceback, never a silent mislowering; the PyTorch path still runs.
2. Compile-AND-sample (the integrity bar): the emitted thrml program actually RUNS
   on the substrate and its sampled output matches ground truth — measured, not
   "it emitted". Skipped when jax/thrml are unavailable.
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys

import pytest

_REPO = pathlib.Path(__file__).resolve().parents[3]
_FIX = _REPO / "examples" / "thrml_bind.su"


def _emit_thrml(su_path):
    return subprocess.run(
        [sys.executable, "-m", "sutra_compiler", "--emit-thrml", str(su_path)],
        capture_output=True, text=True, cwd=str(_REPO),
        env={**__import__("os").environ,
             "PYTHONPATH": str(_REPO / "sdk" / "sutra-compiler"),
             "PYTHONIOENCODING": "utf-8"},
    )


def test_emit_thrml_unsupported_is_a_clean_diagnostic():
    """An unsupported program -> `thrml-codegen:` on stderr, exit 2, no traceback."""
    proc = _emit_thrml(_REPO / "examples" / "hello_world.su")
    assert proc.returncode == 2, (proc.stdout, proc.stderr)
    assert "thrml-codegen:" in proc.stderr
    assert "Traceback" not in proc.stderr


def test_pytorch_path_unaffected_by_thrml_backend():
    """The PyTorch --run path still compiles+runs the same fixture (non-destructive)."""
    pytest.importorskip("torch", reason="PyTorch path needs torch")
    proc = subprocess.run(
        [sys.executable, "-m", "sutra_compiler", "--run", str(_FIX)],
        capture_output=True, text=True, cwd=str(_REPO),
        env={**__import__("os").environ,
             "PYTHONPATH": str(_REPO / "sdk" / "sutra-compiler"),
             "PYTHONIOENCODING": "utf-8"},
    )
    assert proc.returncode == 0, (proc.stdout, proc.stderr)


@pytest.mark.parametrize("fixture", ["thrml_bind.su", "thrml_roundtrip.su"])
def test_emit_thrml_compiles_and_samples(tmp_path, fixture):
    """G.1–G.3: bind / bind→unbind op-graphs lower to a thrml program that SAMPLES
    on the substrate and matches ground truth (measured). thrml_roundtrip.su is
    the canonical VSA identity unbind(bind(a,b),a)=b (a 2-factor program)."""
    pytest.importorskip("jax", reason="thrml backend needs jax")
    pytest.importorskip("thrml", reason="thrml backend needs the thrml package")
    proc = _emit_thrml(_REPO / "examples" / fixture)
    assert proc.returncode == 0, (proc.stdout, proc.stderr)
    prog = tmp_path / "emitted.py"
    prog.write_text(proc.stdout, encoding="utf-8")
    run = subprocess.run([sys.executable, str(prog)], capture_output=True, text=True,
                         env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"})
    assert run.returncode == 0, (run.stdout, run.stderr)
    m = re.search(r"per-bit\s*=\s*([0-9.]+)", run.stdout)
    assert m, f"no per-bit number in: {run.stdout}"
    assert float(m.group(1)) >= 0.95, f"bind sampled poorly: {run.stdout}"
