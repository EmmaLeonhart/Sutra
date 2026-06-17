"""Substrate digit-string output for the calculator (apps/calc/digits.su).

Emma's product decision for calc step c (2026-05-25): rather than return a host
``Fraction`` behind a host-oracle gate, decompose the integer result into its
1000s / 100s / 10s / 1s digits ON THE SUBSTRATE via the Fourier-series
eigenrotation modulus + integer division (digits.su), and return a string.

Two things are guarded here:
  1. digits.su's ``digit(n, place)`` extracts each decimal digit exactly across
     every digit-boundary case (multiples of 10/100/1000 — the branch-cut cases
     that the naive telescoping modulus got wrong), measured, not assumed.
  2. ``Calculator.result_string`` assembles the substrate digits into the right
     string and composes with ``evaluate``.

Torch-gated like the other real-Sutra calc tests.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

torch = pytest.importorskip("torch", reason="digits.su runs through real Sutra")

REPO = pathlib.Path(__file__).resolve().parent.parent
APPS_CALC = REPO / "apps" / "calc"


def _load_calc():
    spec = importlib.util.spec_from_file_location("calc", APPS_CALC / "calc.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def calc():
    return _load_calc().Calculator()


def _digit_fn():
    """Compile digits.su standalone and return (digit, vsa)."""
    calc_mod = _load_calc()
    ns = calc_mod._compile_su(APPS_CALC / "digits.su")
    return ns["digit"], ns["_VSA"]


def test_digit_extraction_exact_over_boundaries() -> None:
    """digit(n, place) returns the exact decimal digit for every value,
    including the multiples-of-10/100/1000 branch-cut cases that broke the
    naive (mod(n,10p)-mod(n,p))/p telescoping form."""
    digit, vsa = _digit_fn()

    def digits(n: int) -> tuple[int, int, int, int]:
        return tuple(
            round(float(vsa.real(digit(float(n), float(pl)))))
            for pl in (1000, 100, 10, 1)
        )

    # Heavy on the digit boundaries (multiples) where rotation_mod's branch cut
    # bites, plus a spread of general values.
    cases = set(range(0, 100))
    cases |= set(range(100, 1000, 10))   # tens/hundreds boundaries
    cases |= set(range(0, 10000, 100))   # hundreds boundaries
    cases |= set(range(0, 10000, 1000))  # thousands boundaries
    cases |= {999, 1000, 1001, 1234, 5050, 5678, 9999, 9990, 9099, 9009, 7000}

    for n in sorted(cases):
        d3, d2, d1, d0 = digits(n)
        assert all(0 <= d <= 9 for d in (d3, d2, d1, d0)), f"n={n} non-digit: {(d3,d2,d1,d0)}"
        recon = d3 * 1000 + d2 * 100 + d1 * 10 + d0
        assert recon == n, f"n={n} digits {(d3,d2,d1,d0)} reconstruct to {recon}"


def test_result_string_samples(calc) -> None:
    """result_string returns the substrate-decomposed digit string."""
    expected = {
        0: "0", 5: "5", 9: "9", 10: "10", 50: "50", 99: "99",
        100: "100", 101: "101", 500: "500", 999: "999",
        1000: "1000", 1234: "1234", 5050: "5050", 9999: "9999",
        -42: "-42", -1000: "-1000",
    }
    for value, want in expected.items():
        assert calc.result_string(value) == want, f"result_string({value})"


def test_result_string_composes_with_evaluate(calc) -> None:
    """The end-to-end demo path: evaluate on the substrate, then the digit
    string off the substrate, matches the true answer's digits."""
    cases = [("99 * 99 =", "9801"), ("50 * 10 =", "500"),
             ("2 + 3 * 4 =", "14"), ("(10 - 2) * 5 =", "40"),
             ("1000 - 1 =", "999"), ("123 + 877 =", "1000")]
    for line, want in cases:
        value = calc.evaluate(line)
        assert isinstance(value, int)
        assert calc.result_string(value) == want, f"{line} -> {want}"


def test_result_string_refuses_out_of_scope(calc) -> None:
    """Non-integer and out-of-4-digit-range results are refused, not guessed."""
    with pytest.raises(ValueError, match="integer-only"):
        calc.result_string(3.5)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="4-digit"):
        calc.result_string(10000)
    with pytest.raises(ValueError, match="4-digit"):
        calc.result_string(-10000)
