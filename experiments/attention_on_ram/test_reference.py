"""Guard for the attention-on-RAM Python reference oracle.

Locks the cross-language test set (design doc §5): the OCaml port and the
Sutra-substrate version must reproduce exactly these outputs.
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import reference  # noqa: E402


def test_reference_oracle_passes_exactly():
    assert reference.run_test_set(verbose=False)


def test_dot_tape_is_linear_regression():
    # y_hat = w . x evaluated by linear attention over RAM.
    assert reference.dot_tape([10.0, 20.0, 30.0], [0.1, 0.2, 0.3]) == 14.0


def test_select_field_is_location_read():
    for j, expected in [(0, 11.0), (1, 22.0), (2, 33.0)]:
        assert reference.select_field([11.0, 22.0, 33.0], j) == expected


def test_evaluate_and_learn_agree():
    """Emma's 'do all of them, compare': evaluating a constructed linear model and
    LEARNING one by SGD realize the SAME linear regression over memory."""
    import pytest
    pytest.importorskip("torch")
    import compare_variants
    r = compare_variants.run_comparison(verbose=False)
    assert r["constructed_tasks_ok"]
    assert r["eval_max_err"] < 1e-9          # constructed evaluation is exact
    assert r["learn_lossN"] < 1e-3           # SGD fit converges
    assert r["learn_coeff_err"] < 1e-2       # recovers the true coefficients
    assert r["learn_grad0"] > 1e-3           # gradients flow (differentiable)
    assert r["eval_vs_learn_agreement"] < 1e-2  # same operator, both routes
