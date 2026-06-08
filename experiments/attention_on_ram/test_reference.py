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
