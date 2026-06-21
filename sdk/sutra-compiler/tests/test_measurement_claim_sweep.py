"""Regression guard for the measurement-claim sweep's detection logic.

`experiments/measurement_claim_sweep.py` enforces the claim->measurement linkage
for the two weakest-automated breach checks (CLAUDE.md § "Subtler substrate
breaches" #2 state-locus and #3 signal-separation): every `.su` carrying a
`// @fv-claim: rnn|classifier test=<path>` annotation must link a measurement
that actually verifies the claim on the substrate.

These tests pin the checker so it can't silently go vacuous:
  - a clean rnn/classifier claim verifies (no problems);
  - a missing/absent linked test is caught;
  - an rnn claim with a host accessor (the per-tick extraction breach) is caught;
  - an rnn claim with no `recurring`+`recur` state is caught;
  - a classifier claim whose linked measurement computes no gap is caught;
  - the real repo currently has >=1 verified claim and ZERO broken claims.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

_ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from experiments.measurement_claim_sweep import (  # noqa: E402
    check_classifier_claim,
    check_rnn_claim,
    scan,
)

_REPO = str(_ROOT)

# A minimal substrate-RNN body: recurring vector through recur, no accessor.
_GOOD_RNN = (
    "function vector step() {\n"
    "    recurring vector state = make_real(0.0);\n"
    "    vector next_state = state + make_real(1.0);\n"
    "    recur(next_state);\n"
    "    return(next_state);\n"
    "}\n"
)


def test_clean_rnn_claim_verifies():
    # Linked test exists (this very file's directory is on disk); use a real path.
    problems = check_rnn_claim(_GOOD_RNN, "demos/gui/test_gui_counter.py", _REPO)
    assert problems == [], problems


def test_rnn_claim_missing_test_linkage_is_caught():
    problems = check_rnn_claim(_GOOD_RNN, None, _REPO)
    assert any("missing" in p for p in problems)


def test_rnn_claim_absent_test_file_is_caught():
    problems = check_rnn_claim(_GOOD_RNN, "demos/gui/no_such_test.py", _REPO)
    assert any("not found" in p for p in problems)


def test_rnn_claim_with_host_accessor_is_caught():
    # The breach: state round-trips through a host scalar via real(...).
    breach = (
        "function vector step() {\n"
        "    recurring vector state = make_real(0.0);\n"
        "    number n = real(state);\n"
        "    vector next_state = make_real(n + 1.0);\n"
        "    recur(next_state);\n"
        "    return(next_state);\n"
        "}\n"
    )
    problems = check_rnn_claim(breach, "demos/gui/test_gui_counter.py", _REPO)
    assert any("accessor" in p for p in problems)


def test_make_real_does_not_trip_the_accessor_check():
    # `make_real(` must NOT match the real/imag/truth/component accessor regex.
    problems = check_rnn_claim(_GOOD_RNN, "demos/gui/test_gui_counter.py", _REPO)
    assert not any("accessor" in p for p in problems)


def test_rnn_claim_without_recurrence_is_caught():
    no_state = "function vector step() { return make_real(1.0); }\n"
    problems = check_rnn_claim(no_state, "demos/gui/test_gui_counter.py", _REPO)
    assert any("state-locus" in p for p in problems)


def test_clean_classifier_claim_verifies():
    # measure_select_gap.py computes a `gap = min(...) - max(...)` table.
    problems = check_classifier_claim("demos/calc/measure_select_gap.py", _REPO)
    assert problems == [], problems


def test_classifier_claim_without_gap_table_is_caught():
    # A test file that exists but computes no measured gap — point at a source
    # file with no gap/min/max (this very module's __init__-free sibling).
    problems = check_classifier_claim(
        "demos/gui/count.su", _REPO  # a .su, definitely no `gap`+min/max
    )
    assert any("no measured gap" in p for p in problems)


def test_repo_has_verified_claims_and_zero_broken():
    verified, broken, _prog_free, _fix_free = scan(_REPO)
    assert broken == [], f"broken measurement claims on main: {broken}"
    assert len(verified) >= 1


def test_strict_exit_code_is_zero_on_clean_repo():
    # The real repo has 0 broken claims, so --strict must still exit 0.
    proc = subprocess.run(
        [sys.executable, "experiments/measurement_claim_sweep.py", "--strict"],
        cwd=_REPO,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
