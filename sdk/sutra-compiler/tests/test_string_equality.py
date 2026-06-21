"""Regression: `==` on `String`/`Character`-typed values routes through
eq_synthetic (Euclidean), not cosine `eq`.

The capitalised class spellings `String`/`Character` are the user-facing
types; they were missing from `_SYNTHETIC_AXIS_TYPES`, so a var explicitly
typed `String` fell to the cosine `eq` path — which cannot separate two short
strings (measured cos("foo","bar")=0.998), so string equality silently
mis-blended. Discovered while building the Clojure keyword-as-value rep
(planning/findings/2026-06-18-clojure-symbol-keyword-as-value-rep.md, "latent
issue"). This RUNS the program on the substrate and checks the decoded value.
"""
from __future__ import annotations

import pytest

from sutra_compiler.codegen_pytorch import translate_module
from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser


def _run_main(src: str, dim: int = 256):
    pytest.importorskip("torch", reason="substrate run needs torch")
    lexer = Lexer(src, file="<test>")
    tokens = lexer.tokenize()
    parser = Parser(tokens, file="<test>", diagnostics=lexer.diagnostics)
    module = parser.parse_module()
    assert not lexer.diagnostics.has_errors(), [
        d.format() for d in lexer.diagnostics.errors
    ]
    py = translate_module(module, runtime_dim=dim)
    ns: dict = {}
    exec(py, ns)
    result = ns["main"]()
    # Terminal/output boundary decode (mirrors __main__._decode_terminal_result).
    # queue §C "all numbers on the substrate": the arithmetic in `classify`
    # (`1 + w`, `* 10`, `/ 2`, and `classify(...) + classify(...)`) runs on the
    # number axis and returns a d-dim number-vector (value on AXIS_REAL), not a
    # 0-d scalar. Read AXIS_REAL here — the same projection the CLI display edge
    # does; a 0-d / host scalar passes straight through.
    vsa = ns.get("_VSA")
    if (vsa is not None and hasattr(result, "ndim")
            and getattr(result, "ndim", None) == 1
            and result.shape[0] == vsa.dim):
        return float(result[vsa.semantic_dim + vsa.AXIS_REAL])
    return float(result)


# classify("foo")=10 (k == "foo" true), classify("bar")=20; sum = 30.
# With the bug (cosine eq) classify("bar") also reads ~equal → returns 10 → 20.
_STRING_EQ = """
function number classify(String k) {
    number w = truth_axis(defuzzy(k == "foo"));
    return (((1 + w) * 10) + ((1 - w) * 20)) / 2;
}
function number main() { return classify("foo") + classify("bar"); }
"""


def test_string_typed_equality_uses_eq_synthetic():
    assert abs(_run_main(_STRING_EQ) - 30.0) < 0.5
