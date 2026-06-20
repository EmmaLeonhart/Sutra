"""Substrate parsing for the calculator — calc step-d, first verified piece.

planning/23 ("the correct design — parse + switch, all on the substrate")
calls for the host to do I/O only and the *parse* to run on the Sutra
substrate. `apps/calc/parse_int2.su` is the first real piece: it turns a 1-or-2
digit string into its integer value using only substrate ops (string_char_at
gives codepoints; place value by arithmetic; make_real lifts the result onto
the real axis). This test compiles the real .su and checks the decoded value —
no host parsing in the path, ground-truth compared, real delta reported.

Why this exists (CLAUDE.md §"fake-substrate-work"): the calc's host parser is a
known purity gap. Before wiring a substrate parser into calc.py, the mechanism
has to actually work on the substrate — this test is that proof at the 2-digit
cap scope. Torch-gated like the other real-Sutra tests.
"""
from __future__ import annotations

import pathlib

import pytest

torch = pytest.importorskip("torch", reason="parse_int2 runs through real Sutra")

from sutra_compiler.codegen_pytorch import translate_module as torch_translate
from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser

APPS_CALC = pathlib.Path(__file__).resolve().parent.parent / "apps" / "calc"


@pytest.fixture(scope="module")
def parse_int2():
    """Compile apps/calc/parse_int2.su and return (fn, vsa)."""
    src = (APPS_CALC / "parse_int2.su").read_text(encoding="utf-8")
    lexer = Lexer(src, file="parse_int2.su")
    toks = lexer.tokenize()
    parser = Parser(toks, file="parse_int2.su", diagnostics=lexer.diagnostics)
    module = parser.parse_module()
    assert not lexer.diagnostics.has_errors(), list(lexer.diagnostics)
    py = torch_translate(module, llm_model="unused-no-basis-vectors", runtime_dim=8)
    ns: dict = {}
    exec(compile(py, "parse_int2.su", "exec"), ns)
    return ns["parse_int2"], ns["_VSA"]


def test_parse_int2_exact_over_1_and_2_digits(parse_int2) -> None:
    """Every 1- and 2-digit non-negative integer parses to its exact value on
    the substrate. Exhaustive over 0..99 (both '0'..'9' and '00'..'99' forms)."""
    fn, vsa = parse_int2
    bad: list[str] = []
    # 1-digit: "0".."9"
    for d in range(10):
        got = float(vsa._re(fn(vsa.make_string(str(d)))))
        if abs(got - d) > 1e-9:
            bad.append(f"{d!r}->{got} (exp {d})")
    # 2-digit: "00".."99" (covers leading zeros like "07")
    for v in range(100):
        s = f"{v:02d}"
        got = float(vsa._re(fn(vsa.make_string(s))))
        if abs(got - v) > 1e-9:
            bad.append(f"{s!r}->{got} (exp {v})")
    assert not bad, f"substrate parse mismatches ({len(bad)}): {bad[:8]}"


def test_parse_int2_is_real_sutra_not_a_host_stub(parse_int2) -> None:
    """Guard that the value came through real Sutra: the compiled module has a
    _VSA and parse_int2 is a generated function, not a Python stand-in."""
    fn, vsa = parse_int2
    assert callable(fn)
    # make_string + the parse run on the substrate dtype (a torch tensor).
    out = fn(vsa.make_string("42"))
    assert torch.is_tensor(out)
    assert abs(float(vsa._re(out)) - 42.0) < 1e-9


@pytest.fixture(scope="module")
def op_code():
    """Compile apps/calc/parse_op.su and return (fn, vsa)."""
    src = (APPS_CALC / "parse_op.su").read_text(encoding="utf-8")
    lexer = Lexer(src, file="parse_op.su")
    toks = lexer.tokenize()
    parser = Parser(toks, file="parse_op.su", diagnostics=lexer.diagnostics)
    module = parser.parse_module()
    assert not lexer.diagnostics.has_errors(), list(lexer.diagnostics)
    py = torch_translate(module, llm_model="unused-no-basis-vectors", runtime_dim=8)
    ns: dict = {}
    exec(compile(py, "parse_op.su", "exec"), ns)
    return ns["op_code"], ns["_VSA"]


def test_op_code_maps_operator_chars_on_substrate(op_code) -> None:
    """Operator char -> op-code, decided ON THE SUBSTRATE (select+saturation),
    matching calc.py's CODE map: '+'=0, '-'=1, '*'=2, '/'=3. This is the host
    CODE[op] dictionary moved onto the substrate (calc step d)."""
    fn, vsa = op_code
    for ch, expect in (("+", 0.0), ("-", 1.0), ("*", 2.0), ("/", 3.0)):
        got = float(vsa._re(fn(vsa.make_string(ch))))
        assert abs(got - expect) < 1e-9, f"op_code({ch!r})={got}, expected {expect}"
