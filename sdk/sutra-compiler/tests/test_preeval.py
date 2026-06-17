"""Compile-time pre-evaluation of bounded pure recursion (Phase 5.5 tier 3, step 3a).

`sutra_compiler.preeval.preeval_bounded_recursion` folds a compile-time-constant call to a bounded
pure recursive function into a literal (host-side, pure — the same category as the existing
arithmetic constant-folding, NOT runtime substrate execution), then prunes the now-dead recursive
function. The correctness bar: the FOLDED program, compiled + run on the real substrate, produces
the same value as the recursion's ground truth (and the recursive function is gone). The pass is
OPT-IN — invoked explicitly here; the default compile pipeline does not run it.
"""
from __future__ import annotations

import pathlib
import sys

import pytest


def _compiler_ns():
    pytest.importorskip("torch")
    repo = pathlib.Path(__file__).resolve().parents[3]
    compiler_src = repo / "sdk" / "sutra-compiler"
    if str(compiler_src) not in sys.path:
        sys.path.insert(0, str(compiler_src))


def _gt_fib(n):
    return n if n < 2 else _gt_fib(n - 1) + _gt_fib(n - 2)


def _gt_fac(n):
    return 1 if n == 0 else n * _gt_fac(n - 1)


_PRELUDE = (
    "function int fib(int n) { if (n < 2) { return n; } return fib(n-1) + fib(n-2); }\n"
    "function int fac(int n) { if (n == 0) { return 1; } return n * fac(n-1); }\n"
)


def _build(call):
    from sutra_compiler.lexer import Lexer
    from sutra_compiler.parser import Parser
    src = _PRELUDE + f"function int main() {{ return {call}; }}"
    lx = Lexer(src, file="<preeval>")
    ast = Parser(lx.tokenize(), file="<preeval>", diagnostics=lx.diagnostics).parse_module()
    assert not lx.diagnostics.has_errors(), list(lx.diagnostics)
    return ast


def _decode(out, v):
    try:
        return round(float(out[v.semantic_dim + v.AXIS_REAL]))
    except (TypeError, IndexError):
        return round(float(out))   # a folded `return <literal>` emits a host scalar


def _func_names(module):
    return [it.name for it in module.items if type(it).__name__ == "FunctionDecl"]


def _run_on_substrate(module):
    from sutra_compiler.codegen_pytorch import translate_module
    ns: dict = {}
    exec(translate_module(module, llm_model="none", runtime_dim=2), ns)
    return _decode(ns["main"](), ns["_VSA"])


@pytest.mark.parametrize("call,recfn,expected", [
    ("fib(8)", "fib", _gt_fib(8)),     # 21
    ("fac(6)", "fac", _gt_fac(6)),     # 720
    ("fib(10)", "fib", _gt_fib(10)),   # 55
    ("fac(0)", "fac", _gt_fac(0)),     # 1 (base case)
    ("fib(1)", "fib", _gt_fib(1)),     # 1 (base case)
])
def test_preeval_folds_bounded_recursion_and_runs_on_substrate(call, recfn, expected):
    """A constant-argument call to a bounded pure recursive function folds to its literal, the
    recursive function is pruned away, and the folded program runs == ground truth on the substrate."""
    _compiler_ns()
    from sutra_compiler.preeval import preeval_bounded_recursion
    module = _build(call)
    preeval_bounded_recursion(module, max_depth=256)
    assert recfn not in _func_names(module), f"{recfn} should be folded away + pruned"
    got = _run_on_substrate(module)
    assert got == expected, f"{call} -> {got}, expected {expected}"


def test_preeval_folds_calls_inside_a_larger_expression():
    """Calls embedded in a bigger expression fold their sub-results; the program stays correct."""
    _compiler_ns()
    from sutra_compiler.preeval import preeval_bounded_recursion
    module = _build("fib(10) + fac(5)")
    preeval_bounded_recursion(module, max_depth=256)
    # both recursive functions folded away -> pruned to just main
    assert _func_names(module) == ["main"]
    assert _run_on_substrate(module) == _gt_fib(10) + _gt_fac(5)   # 55 + 120 = 175


def test_preeval_is_conservative_on_unsupported_bodies():
    """A function whose body is outside the supported subset (here a local VarDecl) is NOT folded;
    its call is left for the runtime path and the function is retained. The program stays correct."""
    _compiler_ns()
    from sutra_compiler.lexer import Lexer
    from sutra_compiler.parser import Parser
    from sutra_compiler.preeval import preeval_bounded_recursion
    src = ("function int g(int n) { int x = n + 1; return x; }\n"
           "function int main() { return g(5); }")
    lx = Lexer(src, file="<preeval>")
    module = Parser(lx.tokenize(), file="<preeval>", diagnostics=lx.diagnostics).parse_module()
    assert not lx.diagnostics.has_errors(), list(lx.diagnostics)
    preeval_bounded_recursion(module, max_depth=256)
    # g could not be folded (VarDecl unsupported) -> the call remains -> g is retained
    assert "g" in _func_names(module)
    assert _run_on_substrate(module) == 6


def test_preeval_respects_max_depth():
    """When the recursion would exceed max_depth, the call is NOT folded (left for runtime), so the
    function is retained — the depth cap is honored rather than the evaluator running unbounded."""
    _compiler_ns()
    from sutra_compiler.preeval import preeval_bounded_recursion
    module = _build("fac(6)")
    preeval_bounded_recursion(module, max_depth=2)   # fac(6) needs depth 6 > 2
    assert "fac" in _func_names(module), "fac(6) must NOT fold under max_depth=2"


# ---- CLI wiring (step 3b): the `--preeval` flag + atman.toml `max_preeval_depth` ----

_FIB_SU = ("function int fib(int n) { if (n < 2) { return n; } return fib(n-1) + fib(n-2); }\n"
           "function int main() { return fib(8); }\n")


def test_cli_preeval_deep_flag_folds_deep_recursion(tmp_path):
    """`--preeval` (deep cap) folds the recursive fib(8) away so the program COMPILES; the SHALLOW
    default (depth 3) leaves fib(8) un-folded so its recursive if/else is rejected by the V1 codegen
    — proving --preeval raises the cap above the shallow default."""
    _compiler_ns()
    from sutra_compiler.__main__ import _compile_to_python
    from sutra_compiler.codegen_base import CodegenNotSupported
    p = tmp_path / "fib.su"
    p.write_text(_FIB_SU, encoding="utf-8")   # main returns fib(8); needs depth 8 > default 3
    src = _compile_to_python(str(p), runtime_dim=2, runtime_seed=42, preeval=True)
    assert src is not None and "def main" in src
    with pytest.raises(CodegenNotSupported):   # default depth 3 < 8 -> fib(8) not folded
        _compile_to_python(str(p), runtime_dim=2, runtime_seed=42, preeval=False)


def test_cli_shallow_default_folds_shallow_recursion(tmp_path, capsys):
    """Pre-eval is ON by DEFAULT at a shallow depth (Emma 2026-06-17: ~2-3, not 0): a shallow
    recursive call (fib(3), depth 3) folds + runs WITHOUT --preeval, printing 2 = fib(3)."""
    _compiler_ns()
    from sutra_compiler.__main__ import main
    p = tmp_path / "fib3.su"
    p.write_text("function int fib(int n) { if (n < 2) { return n; } return fib(n-1) + fib(n-2); }\n"
                 "function int main() { return fib(3); }\n", encoding="utf-8")
    rc = main(["--run", str(p)])   # NO --preeval -> shallow default depth 3 folds fib(3)
    out = capsys.readouterr().out.strip()
    assert rc == 0 and round(float(out)) == 2, f"shallow-default --run -> rc={rc}, out={out!r}"


def test_cli_preeval_run_outputs_correct_value(tmp_path, capsys):
    """End-to-end: `sutrac --run --preeval fib.su` folds fib(8) and prints 21."""
    _compiler_ns()
    from sutra_compiler.__main__ import main
    p = tmp_path / "fib.su"
    p.write_text(_FIB_SU, encoding="utf-8")
    rc = main(["--run", "--preeval", str(p)])
    out = capsys.readouterr().out.strip()
    assert rc == 0 and round(float(out)) == 21, f"--run --preeval -> rc={rc}, out={out!r}"


def test_atman_toml_max_preeval_depth_is_read(tmp_path):
    """`max_preeval_depth` is read from `[project.compile]` in the nearest atman.toml."""
    _compiler_ns()
    from sutra_compiler.__main__ import _read_atman_max_preeval_depth
    (tmp_path / "atman.toml").write_text(
        "[project.compile]\nmax_preeval_depth = 77\n", encoding="utf-8")
    p = tmp_path / "x.su"
    p.write_text("function int main() { return 1; }\n", encoding="utf-8")
    assert _read_atman_max_preeval_depth(str(p)) == 77
