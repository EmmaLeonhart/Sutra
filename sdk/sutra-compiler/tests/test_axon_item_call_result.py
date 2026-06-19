"""`.item("key")` on a non-identifier receiver (a call result or a nested read)
is an axon field read, not the tensor `.item()`.

Regression for finding `2026-06-18-axon-item-on-call-result-not-supported.md`: the
codegen routed `a.item(k)` to the runtime `axon_item` only when the receiver was an
Axon-typed VARIABLE. A call-result receiver (`mk().item("x")`) fell through to a
literal `.item(x)` that dispatches as PyTorch's tensor `.item()` (no args) and crashes
at runtime. The fix routes `.item(<key>)` on any non-identifier receiver to
`axon_item`. This affects every Axon-returning function whose result is field-read
inline, across all frontends (e.g. the Clojure keyword accessor `(:k (f args))`).
"""
from __future__ import annotations

import types

from sutra_compiler.codegen_pytorch import translate_module
from sutra_compiler.lexer import Lexer
from sutra_compiler.parser import Parser


def _compile(src: str, file: str = "<test>") -> types.ModuleType:
    lexer = Lexer(src, file=file)
    tokens = lexer.tokenize()
    parser = Parser(tokens, file=file, diagnostics=lexer.diagnostics)
    module = parser.parse_module()
    py_src = translate_module(module, llm_model="nomic-embed-text", runtime_dim=256)
    mod = types.ModuleType(file)
    exec(compile(py_src, file, "exec"), mod.__dict__)
    return mod


def _run_number(mod) -> float:
    """Call main() and decode its number-vector result to the real-axis scalar,
    the same terminal-boundary decode the CLI uses (`_decode_terminal_result`)."""
    result = mod.main()
    vsa = mod._VSA
    return float(result[vsa.semantic_dim + vsa.AXIS_REAL])


def test_item_on_call_result_reads_axon_field() -> None:
    """`realvec(mk().item("x"))` reads the field off the returned axon."""
    src = (
        'function Axon mk() { Axon a; a.add("x", 1); a.add("y", 2); return a; }\n'
        'function number main() { return realvec(mk().item("x")); }\n'
    )
    mod = _compile(src, file="item_call.su")
    assert abs(_run_number(mod) - 1.0) < 0.5


def test_item_on_nested_item_read() -> None:
    """A chained `box.item("_val").item("_0")` descends a nested payload axon — the
    receiver of the second `.item` is a call result, not an identifier."""
    src = (
        'function Axon mkpair() { Axon v; v.add("_0", 5); v.add("_1", 8); return v; }\n'
        'function Axon mkbox() { Axon a; a.add("_tag", 1); a.add("_val", mkpair());'
        ' return a; }\n'
        'function number main() {\n'
        '    Axon box = mkbox();\n'
        '    return realvec(box.item("_val").item("_0"));\n'
        '}\n'
    )
    mod = _compile(src, file="item_nested.su")
    assert abs(_run_number(mod) - 5.0) < 0.5
