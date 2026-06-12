"""Guards for the non-tail-recursion approaches (queue #6). Approach 1: Tree RNN.
Torch-gated (runs the combine on the real substrate)."""
from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest

pytest.importorskip("torch", reason="runs the combine on the real Sutra substrate")

HERE = pathlib.Path(__file__).resolve().parent


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_tree_rnn_fold_matches_host_bottom_up() -> None:
    """Fixed-topology tree fold (non-tail in structure) computed bottom-up with the
    combine on the substrate == the host fold. Non-associative combine, so this checks
    the actual tree-structured reduction, not a flat reduce."""
    ev = _load("tree_rnn_eval", "tree_rnn_eval.py")
    for leaves in ([1.0, 2.0, 3.0, 4.0],
                   [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0],
                   [2.0, 0.0, 0.0, 0.0]):
        got = ev.fold_substrate(leaves)
        want = ev._fold_host(leaves)
        assert abs(got - want) < 1e-5, f"{leaves}: substrate {got} != host {want}"


def test_cps_factorial_runs_raw_is_unsupported() -> None:
    """Approach 2 (CPS + trampolining): the raw non-tail factorial lowers to
    UNSUPPORTED; the CPS/accumulator rewrite lowers to a while_loop (trampoline) and
    runs on the substrate to the host factorial."""
    ev = _load("cps_eval", "cps_eval.py")
    assert ev.raw_is_unsupported()
    assert abs(ev.run_cps_on_substrate() - 120.0) < 1e-5
