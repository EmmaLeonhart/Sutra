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


def test_parser_reduces_to_synthetic_axis_floor():
    """Reduction study (design doc §5): the parser carries no semantic content
    (0 basis_vector), so it runs at the synthetic-axis floor runtime_dim=3 and still
    reproduces the oracle — measured smallest passing dim."""
    import pytest
    pytest.importorskip("torch")
    import dim_sweep
    for name, expected in dim_sweep.CASES:
        su = (dim_sweep._FIXTURES / name / "expected.su").read_text(encoding="utf-8")
        got = dim_sweep.run_at_dim(su, 3)
        assert isinstance(got, float) and abs(got - expected) < 0.5, (
            f"{name} did not pass at runtime_dim=3: got {got!r}, expected {expected}")


def test_content_addressing_soft_learns_hard_inert():
    """Emma's distinction (2026-06-08), measured: content-based SOFT (softmax)
    addressing learns where to look — gradient flows through the addressing into the
    query; HARD (argmax) addressing is differentiable-on-paper but inert (zero
    gradient), so it cannot learn content-based retrieval."""
    import pytest
    pytest.importorskip("torch")
    import content_addressed_read as car
    r = car.run(verbose=False)
    soft, hard = r["soft"], r["hard"]
    assert soft["grad0"] > 1e-3                 # gradient flows through softmax address
    assert soft["lossN"] < 1e-2                 # learns to retrieve the target
    assert soft["weight_on_target"] > 0.9       # attends to the right row by content
    assert hard["grad0"] < 1e-9                 # argmax: zero gradient to the query
    assert hard["lossN"] > soft["lossN"]        # and so it does not learn


def test_substrate_select_content_read_is_differentiable():
    """Content-based addressing via the COMPILED substrate `select`+`similarity` is
    differentiable: a query trained through it learns directionally (gradient flows,
    read moves toward target); a hard argmax over the same scores is inert. Full one-hot
    sharpening is NOT claimed (select's fixed beta=1 keeps the read a diffuse blend)."""
    import pytest
    pytest.importorskip("torch")
    import substrate_content_read as scr
    r = scr.run(verbose=False)
    soft, hard = r["soft"], r["hard"]
    assert soft["grad0"] > 1e-4                       # gradient flows through substrate select
    assert soft["lossN"] < soft["loss0"]              # learns directionally
    assert soft["cos_to_target"] > 0.5
    assert hard["grad0"] < 1e-9                        # argmax: inert
    assert soft["cos_to_target"] > hard["cos_to_target"] + 0.3


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
