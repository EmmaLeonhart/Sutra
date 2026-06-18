"""Tier-4 tabulation shape detector (Phase 5.5 step 4b part 1) — `detect_tabulable_recursion`."""
from __future__ import annotations

import pathlib
import sys

import pytest


def _detect(src):
    repo = pathlib.Path(__file__).resolve().parents[3]
    compiler_src = repo / "sdk" / "sutra-compiler"
    if str(compiler_src) not in sys.path:
        sys.path.insert(0, str(compiler_src))
    from sutra_compiler.lexer import Lexer
    from sutra_compiler.parser import Parser
    from sutra_compiler.tabulate import detect_tabulable_recursion
    lx = Lexer(src, file="<t>")
    module = Parser(lx.tokenize(), file="<t>", diagnostics=lx.diagnostics).parse_module()
    assert not lx.diagnostics.has_errors(), list(lx.diagnostics)
    fn = module.items[0]
    return detect_tabulable_recursion(fn)


def test_detects_fib():
    s = _detect("function int fib(int n) { if (n < 2) { return n; } return fib(n-1) + fib(n-2); }")
    assert s is not None
    assert s.param == "n" and s.base_op == "<" and s.base_k == 2 and s.offsets == (1, 2)
    assert s.coeffs == (1, 1)


def test_detects_coefficients():
    # Pell: P(n) = 2*P(n-1) + P(n-2)  (general linear recurrence with coefficients)
    s = _detect("function int pell(int n) { if (n < 2) { return n; } return 2*pell(n-1) + pell(n-2); }")
    assert s is not None and s.offsets == (1, 2) and s.coeffs == (2, 1)
    # coefficient on the right factor too: f(n-2) * 3
    s2 = _detect("function int g(int n) { if (n < 2) { return n; } return g(n-1) + g(n-2) * 3; }")
    assert s2 is not None and s2.offsets == (1, 2) and s2.coeffs == (1, 3)


def test_detects_tribonacci():
    s = _detect("function int trib(int n) { if (n < 3) { return n; } "
                "return trib(n-1) + trib(n-2) + trib(n-3); }")
    assert s is not None and s.offsets == (1, 2, 3)


def test_rejects_single_recursion():
    # factorial is single recursion (tier 2), not multiple -> not tabulable here
    assert _detect("function int fac(int n) { if (n == 0) { return 1; } return n * fac(n-1); }") is None


def test_rejects_non_recursive():
    assert _detect("function int g(int n) { if (n < 2) { return n; } return n + 1; }") is None


def test_rejects_non_constant_offset():
    # f(n - n) is not a constant positive offset
    assert _detect("function int h(int n) { if (n < 2) { return n; } return h(n-1) + h(n-n); }") is None


def test_rejects_extra_statements():
    # an intervening statement breaks the strict 2-statement shape (conservative)
    s = _detect("function int f(int n) { if (n < 2) { return n; } int x = n; return f(n-1) + f(n-2); }")
    assert s is None


# ---- 2-arg DP detector (`detect_2arg_dp`, the binomial/Pascal family) ----
def _detect2(src):
    repo = pathlib.Path(__file__).resolve().parents[3]
    compiler_src = repo / "sdk" / "sutra-compiler"
    if str(compiler_src) not in sys.path:
        sys.path.insert(0, str(compiler_src))
    from sutra_compiler.lexer import Lexer
    from sutra_compiler.parser import Parser
    from sutra_compiler.tabulate import detect_2arg_dp
    lx = Lexer(src, file="<t>")
    module = Parser(lx.tokenize(), file="<t>", diagnostics=lx.diagnostics).parse_module()
    assert not lx.diagnostics.has_errors(), list(lx.diagnostics)
    return detect_2arg_dp(module.items[0])


_BINOM = ("function int C(int n, int k) {"
          " if (k == 0) { return 1; }"
          " if (k == n) { return 1; }"
          " return C(n-1, k-1) + C(n-1, k); }")


def test_detects_binomial():
    s = _detect2(_BINOM)
    assert s is not None
    assert s.p0 == "n" and s.p1 == "k"
    assert s.coeffs == (1, 1) and s.offsets == ((1, 1), (1, 0))
    assert len(s.boundaries) == 2          # k==0 and k==n


def test_detects_binomial_with_k_lt_1_edge():
    # `k < 1` is the same col==0 edge expressed as a strict comparison
    s = _detect2(_BINOM.replace("k == 0", "k < 1"))
    assert s is not None and s.offsets == ((1, 1), (1, 0))


def test_detects_2arg_coefficients():
    # a weighted 2-arg recurrence: 2*f(n-1,k-1) + f(n-1,k)
    s = _detect2("function int f(int n, int k) {"
                 " if (k == 0) { return 1; } if (k == n) { return 1; }"
                 " return 2*f(n-1,k-1) + f(n-1,k); }")
    assert s is not None and s.coeffs == (2, 1) and s.offsets == ((1, 1), (1, 0))


def test_rejects_2arg_when_row_not_decreasing():
    # a term that does not decrease the first param (f(n,k-1)) makes the row-major fill ill-founded
    assert _detect2("function int f(int n, int k) {"
                    " if (k == 0) { return 1; } if (k == n) { return 1; }"
                    " return f(n-1,k-1) + f(n,k-1); }") is None


def test_rejects_2arg_no_boundary():
    # no base case -> nothing to seed -> reject
    assert _detect2("function int f(int n, int k) { return f(n-1,k-1) + f(n-1,k); }") is None


def test_rejects_2arg_non_recursive():
    assert _detect2("function int f(int n, int k) {"
                    " if (k == 0) { return 1; } if (k == n) { return 1; }"
                    " return n + k; }") is None
