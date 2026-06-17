"""The Yantra CLI calculator: type an expression, get the EXACT answer.

Drives `apps/calc.Calculator` with a battery of expressions and asserts
each result is exact. The arithmetic runs on real Sutra `.su` services
through the kernel; the text parsing is host orchestration. This is the
Meta-demo's "text parsing + reliable math" proof (planning/22): where
NCCLIGen would *generate* a plausible terminal frame for `5 * 10 =`,
Yantra *computes* 50 — exactly, every time.

Torch-gated like the other real-Sutra tests.
"""
from __future__ import annotations

import pathlib
import random
import sys
from fractions import Fraction

import pytest

torch = pytest.importorskip("torch", reason="calc runs through real Sutra")

sys.path.insert(
    0, str(pathlib.Path(__file__).resolve().parent.parent / "apps" / "calc")
)
from calc import Calculator  # noqa: E402


@pytest.fixture(scope="module")
def calc() -> Calculator:
    return Calculator()


@pytest.mark.parametrize(
    "expr,expected",
    [
        ("5 * 10 =", 50),     # the headline
        ("5 * 10", 50),       # trailing '=' optional
        ("12 + 30", 42),
        ("100 - 7", 93),
        ("9 * 9", 81),
        ("0 * 9999", 0),
        ("123 + 877", 1000),
        ("1000 - 1000", 0),
        ("-4 * 6", -24),
        ("  7   +   8  =", 15),  # whitespace tolerance
        ("2 * 2", 4),
        ("4096 * 4096", 16777216),  # 2**24, top of the float32-exact range
    ],
)
def test_calc_is_exact(calc: Calculator, expr: str, expected: int) -> None:
    assert calc.evaluate(expr) == expected


def test_calc_rejects_unparseable(calc: Calculator) -> None:
    with pytest.raises(ValueError):
        calc.evaluate("not an expression")


@pytest.mark.parametrize(
    "expr,expected",
    [
        ("10 / 2 =", 5),
        ("100 / 4", 25),
        ("81 / 9", 9),
        ("9 / 3", 3),
        ("-12 / 4", -3),
        ("7 / 2", 3.5),  # exact binary fraction -> float
    ],
)
def test_calc_division_exact(calc: Calculator, expr: str, expected) -> None:
    """Division (Sutra complex_div) returns exact quotients."""
    assert calc.evaluate(expr) == expected


@pytest.mark.parametrize("expr", ["10 / 3", "1 / 3", "22 / 7"])
def test_calc_division_refuses_inexact(calc: Calculator, expr: str) -> None:
    """Non-terminating quotients are refused, never approximated."""
    with pytest.raises(ValueError):
        calc.evaluate(expr)


def test_calc_division_by_zero(calc: Calculator) -> None:
    """Division by zero errors, never returns inf/nan."""
    with pytest.raises(ValueError):
        calc.evaluate("5 / 0")


@pytest.mark.parametrize(
    "expr,expected",
    [
        ("2 + 3 * 4", 14),            # precedence: * before +
        ("2 * 3 + 4", 10),
        ("100 - 5 * 4", 80),
        ("(10 - 2) * 5", 40),         # parentheses
        ("(2 + 3) * (4 + 1)", 25),
        ("2 * 3 + 4 * 5", 26),
        ("1 + 2 + 3 + 4 + 5", 15),
        ("10 - 2 - 3", 5),            # left-associative
        ("100 / 10 / 2", 5),          # left-associative division
        ("3 + -2", 1),                # unary minus on a literal
        ("-(2 + 3)", -5),             # unary minus on a sub-expression
        ("7 / 2 + 1", 4.5),           # fractional intermediate, exact
        ("(7 - 3) / 2", 2),
        ("2 * 2 * 2 * 2 =", 16),      # trailing '=' still optional
    ],
)
def test_calc_multiterm_exact(calc: Calculator, expr: str, expected) -> None:
    """Multi-term expressions: precedence, parens, unary minus — each
    binary op computed on the substrate, composed to the exact result."""
    assert calc.evaluate(expr) == expected


@pytest.mark.parametrize(
    "expr", ["10 / 3 + 1", "1 + 10 / 3", "99999999 * 99999999 + 1", "5 / 0 + 1"]
)
def test_calc_multiterm_refuses_when_any_step_inexact(
    calc: Calculator, expr: str
) -> None:
    """If any sub-operation can't be computed exactly, the whole
    expression is refused — never a partially-wrong answer."""
    with pytest.raises(ValueError):
        calc.evaluate(expr)


@pytest.mark.parametrize(
    "expr", ["2 +", "(2 + 3", "2 3", "2 ** 3", ")", ""]
)
def test_calc_rejects_malformed(calc: Calculator, expr: str) -> None:
    """Malformed expressions raise rather than producing a result."""
    with pytest.raises(ValueError):
        calc.evaluate(expr)


def _random_expr(rng: random.Random, depth: int):
    """Return (expr_string, exact_value): value is a Fraction, or None if
    the expression divides by zero. Fully parenthesised so the string's
    evaluation order matches the computed value exactly."""
    if depth <= 0 or rng.random() < 0.4:
        n = rng.randint(-50, 50)
        return (f"({n})" if n < 0 else str(n)), Fraction(n)
    op = rng.choice("+-*/")
    ls, lv = _random_expr(rng, depth - 1)
    rs, rv = _random_expr(rng, depth - 1)
    if lv is None or rv is None:
        val = None
    elif op == "+":
        val = lv + rv
    elif op == "-":
        val = lv - rv
    elif op == "*":
        val = lv * rv
    else:
        val = None if rv == 0 else lv / rv
    return f"({ls} {op} {rs})", val


def test_calc_never_returns_a_wrong_answer_fuzz(calc: Calculator) -> None:
    """Property test: across many random expressions the calculator NEVER
    returns a wrong answer — it returns the exact value or refuses.

    This is the whole pitch versus a model that hallucinates. The oracle
    is exact rational arithmetic; a refusal (ValueError) is always
    acceptable, but a *returned* value must equal the oracle exactly.
    """
    rng = random.Random(20260524)
    wrong: list[tuple[str, object, object]] = []
    for _ in range(100):
        expr, exact = _random_expr(rng, depth=rng.randint(1, 3))
        try:
            got = calc.evaluate(expr)
        except (ValueError, RuntimeError):
            continue  # refused — always allowed
        if exact is None or Fraction(got) != exact:
            wrong.append((expr, got, exact))
    assert not wrong, (
        f"calculator returned WRONG answers (must be exact or refused): "
        f"{wrong[:5]}"
    )


@pytest.mark.parametrize(
    "expr", ["99999999 * 99999999", "123456789 * 123456789", "94906267 * 94906267"]
)
def test_calc_refuses_out_of_exact_range(calc: Calculator, expr: str) -> None:
    """A result not exactly representable on the substrate is refused.

    The substrate runs in float64 (Sutra v0.6.2 `runtime_dtype`), so exact
    integers hold to 2**53 (~9.007e15). Each result here is *past* 2**53 and
    not exactly representable, so the substrate returns an off-by-some value;
    the exactness gate verifies against a host oracle and raises rather than
    printing a wrong answer — the "never a wrong answer" guarantee, now at the
    float64 ceiling. (Values within 2**53, even big ones, are returned — see
    test_calc_returns_large_exact_values.)
    """
    with pytest.raises(ValueError):
        calc.evaluate(expr)


@pytest.mark.parametrize(
    "expr,expected",
    [
        ("5000 * 5000", 25_000_000),
        ("4729 * 8831", 41_761_799),          # was refused under float32
        ("99999 * 99999", 9_999_800_001),     # ~1e10, exact in float64
        ("12345679 * 9", 111_111_111),
        ("94906265 * 94906265", 9_007_199_136_250_225),  # just under 2**53
    ],
)
def test_calc_returns_large_exact_values(
    calc: Calculator, expr: str, expected: int
) -> None:
    """Large-but-exactly-representable results are returned. float64
    (Sutra v0.6.2) makes products exact through ~9.007e15 — substrate-pure,
    no host carries; products that were refused under float32 now return."""
    assert calc.evaluate(expr) == expected


def test_calc_demo_transcript_is_exact(calc: Calculator) -> None:
    """The runnable demo (apps/calc/demo.py) prints exact results."""
    from demo import run_demo

    lines = run_demo(calc)
    expected_prefix = [
        "5 * 10 = 50",
        "12 + 30 = 42",
        "100 - 7 = 93",
        "10 / 2 = 5",
        "2 + 3 * 4 = 14",
        "9 * 9 = 81",
        "123 + 877 = 1000",
        "-4 * 6 = -24",
        "4096 * 4096 = 16777216",
        "4729 * 8831 = 41761799",      # exact in float64 (refused under float32)
        "99999 * 99999 = 9999800001",  # ~1e10, exact in float64
    ]
    assert lines[: len(expected_prefix)] == expected_prefix
    assert any(line.startswith("10 / 3 = (refused") for line in lines)
    assert any(
        line.startswith("99999999 * 99999999 = (refused") for line in lines
    )
