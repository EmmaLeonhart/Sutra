"""Regression guards for the tick-3 substrate-grounded eval harness.

CI-safe: does NOT need the gitignored model.pt / data/. Exercises the harness's
pure functions plus an end-to-end substrate compile+run on a tiny inline .su
program with hand-computed IO. If THIS breaks, eval_substrate.py's correctness
claim (substrate IO-reproduction 216/240 = 0.900, 2026-05-30) is no longer
trustworthy.
"""
from __future__ import annotations

import os
import sys
import tempfile

import pytest

pytest.importorskip("torch", reason="eval harness requires torch")
import torch  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from eval_substrate import (  # noqa: E402
    write_weight_csvs,
    resubstitute,
    compile_su,
    check_io,
    canonicalize_source,
    substitute_coeffs,
)
from prepare import COEFF_CLASSES  # noqa: E402


def test_substitute_coeffs_overwrites_present_slots_only():
    # COEFF_CLASSES = [0.5, 1.0, 1.5, 2.0, 3.0]; class 3 -> 2.0, class 0 -> 0.5.
    src = "1.5 * Tensor.MatrixMul(M0, x) + 3.0 * x"
    # both slots present: 1st literal -> a, 2nd -> b
    out = substitute_coeffs(src, pred_a=3, pred_b=0, has_a=True, has_b=True)
    assert out == "2.0 * Tensor.MatrixMul(M0, x) + 0.5 * x"
    # only slot a present: 2nd literal untouched
    out = substitute_coeffs(src, pred_a=4, pred_b=0, has_a=True, has_b=False)
    assert out == "3.0 * Tensor.MatrixMul(M0, x) + 3.0 * x"
    # no slots: source unchanged (fixed-coeff families never touched)
    assert substitute_coeffs(src, 0, 0, has_a=False, has_b=False) == src
    # no coefficient literal to find: unchanged even if a slot is claimed
    assert substitute_coeffs("Tensor.MatrixMul(M0, x)", 3, 0, True, False) \
        == "Tensor.MatrixMul(M0, x)"


def test_canonicalize_drops_unit_coeff_keeps_others():
    # `1.0 * EXPR` -> `EXPR` (multiplicative identity), both terms.
    assert (canonicalize_source("1.0 * Tensor.MatrixMul(M0, x) + 1.0 * x")
            == "Tensor.MatrixMul(M0, x) + x")
    # non-unit coefficients are behaviorally meaningful — untouched.
    for s in ("0.5 * Tensor.MatrixMul(M0, x) + 0.5 * x",
              "2.0 * Tensor.MatrixMul(M0, x)",
              "1.5 * Tensor.MatrixMul(M0, x) - 3.0 * x"):
        assert canonicalize_source(s) == s
    # a correct simplification compares equal to the redundant reference.
    assert (canonicalize_source("Tensor.MatrixMul(M0, x) + x")
            == canonicalize_source("1.0 * Tensor.MatrixMul(M0, x) + x"))

# A tiny model-free program: apply(x) = M0 @ x.
_SRC = (
    "function vector apply(vector x) {\n"
    '    matrix M0 = load_matrix("M0");\n'
    "    return Tensor.MatrixMul(M0, x);\n"
    "}\n"
    'function string main() { return "ok"; }\n'
)


def test_resubstitute_maps_known_keeps_unknown():
    src = 'load_matrix("M0") load_matrix("M1") load_matrix("M9")'
    out = resubstitute(src, {"M0": "/tmp/a.csv", "M1": "/tmp/b.csv"})
    assert 'load_matrix("/tmp/a.csv")' in out
    assert 'load_matrix("/tmp/b.csv")' in out
    assert 'load_matrix("M9")' in out  # unknown ref untouched


def test_write_weight_csvs_names_and_count():
    with tempfile.TemporaryDirectory() as td:
        paths = write_weight_csvs([[[1.0, 2.0]], [[3.0, 4.0]]], td)
        assert set(paths) == {"M0", "M1"}
        for p in paths.values():
            assert os.path.exists(p)


def test_end_to_end_substrate_identity_reproduces_io():
    # M0 = identity -> apply(x) == x. Proves write_csv -> load_matrix ->
    # compile -> run-on-substrate -> compare end to end.
    ident = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    io_pairs = [{"input": [0.5, -1.0, 2.0], "output": [0.5, -1.0, 2.0]}]
    with tempfile.TemporaryDirectory() as td:
        paths = write_weight_csvs([ident], td)
        ns = compile_su(resubstitute(_SRC, paths), runtime_dim=3)
        ok, detail = check_io(ns["apply"], ns["_VSA"], io_pairs)
    assert ok, detail


def test_end_to_end_substrate_detects_wrong_output():
    ident = [[1.0, 0.0], [0.0, 1.0]]
    io_pairs = [{"input": [1.0, 2.0], "output": [9.0, 9.0]}]  # deliberately wrong
    with tempfile.TemporaryDirectory() as td:
        paths = write_weight_csvs([ident], td)
        ns = compile_su(resubstitute(_SRC, paths), runtime_dim=2)
        ok, _ = check_io(ns["apply"], ns["_VSA"], io_pairs)
    assert ok is False


def test_end_to_end_substrate_matmul_matches_hand_value():
    # M0 = [[2,0],[0,3]] -> apply([1,1]) == [2,3].
    m = [[2.0, 0.0], [0.0, 3.0]]
    io_pairs = [{"input": [1.0, 1.0], "output": [2.0, 3.0]}]
    with tempfile.TemporaryDirectory() as td:
        paths = write_weight_csvs([m], td)
        ns = compile_su(resubstitute(_SRC, paths), runtime_dim=2)
        ok, detail = check_io(ns["apply"], ns["_VSA"], io_pairs)
    assert ok, detail
