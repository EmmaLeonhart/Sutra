"""Regression guard for the FV end-to-end worked example.

`experiments/fv_worked_example.py` carries one named program (a NAND gate in De
Morgan form) through the whole obligation pipeline — function-correctness (graph
equivalence to its contract), branch-range soundness, and a substrate cross-check
against the NAND truth table. This pins its verdicts so a regression in any FV
check (or in the compiler's lowering of `&&`/`||`/`!`) fails loudly here, and the
artifact the FV paper references stays true.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

pytest.importorskip("torch", reason="substrate cross-check runs on torch")
pytest.importorskip("sympy", reason="FV checks need sympy (sutra-dev[fv])")

# experiments/ lives at the repo root: tests → sutra-compiler → sdk → root.
_ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from experiments.fv_worked_example import run  # noqa: E402


def test_fv_worked_example_all_obligations_discharged():
    r = run()
    # Obligation 1 — the De Morgan impl computes EXACTLY the contract's NAND.
    assert r["function_correct"] is True
    # ...and a NOR implementation is correctly rejected (not vacuous).
    assert r["wrong_rejected"] is True
    # Obligation 2 — range-sound, exact range within the truth domain.
    assert r["range_sound"] is True
    assert r["exact_range"][2] is True
    # Obligation 3 — the compiled program reproduces NAND on the substrate.
    assert r["substrate_worst_err"] < 1e-5, \
        "compiled NAND deviates from the truth table: %g" % r["substrate_worst_err"]
