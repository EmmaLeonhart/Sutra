"""Tests for the `sutrac repl` interactive evaluator (sutra_compiler/repl.py).

Driven non-interactively via run_repl(lines, out). These use ONLY `make_real`
number expressions so they need no embedding backend (no Ollama / no model
download) and run anywhere torch is importable.
"""
from __future__ import annotations

import io

import pytest

torch = pytest.importorskip("torch")

from sutra_compiler.repl import run_repl


def _drive(lines):
    out = io.StringIO()
    run_repl(lines, out, runtime_dim=64, banner=False)
    return out.getvalue()


def test_number_expression_shows_real_value():
    out = _drive(["make_real(2.0) + make_real(3.0)", ":quit"])
    assert "= 5" in out


def test_declaration_then_use():
    out = _drive([
        "vector a = make_real(10.0);",
        "a + make_real(5.0)",
        ":quit",
    ])
    assert "(added)" in out
    assert "= 15" in out


def test_decls_and_reset():
    out = _drive([
        "vector a = make_real(1.0);",
        ":decls",
        ":reset",
        ":decls",
        ":quit",
    ])
    assert "vector a = make_real(1.0);" in out
    assert "(session cleared)" in out
    assert "(no declarations)" in out


def test_error_does_not_kill_the_loop():
    out = _drive([
        "this is not valid sutra @@@",   # error
        "make_real(7.0)",                # still evaluates afterward
        ":quit",
    ])
    assert "error" in out.lower()
    assert "= 7" in out


def test_bad_declaration_is_rejected_not_kept():
    out = _drive([
        "vector b = nonexistent_builtin(1);",  # ends in ; -> declaration, but invalid
        "make_real(4.0)",                       # session not poisoned
        ":quit",
    ])
    assert "= 4" in out


def test_help_command():
    out = _drive([":help", ":quit"])
    assert "Sutra REPL help" in out


def test_bare_string_literal_steers_to_embed_not_typeerror():
    # The vector-typed eval wrapper can't evaluate a bare string yet
    # (queue.md item 1). Until the real fix, the REPL must steer to embed(...)
    # instead of leaking the internal `TypeError: can't multiply sequence...`.
    out = _drive(['"hello"', ":quit"])
    assert "TypeError" not in out
    assert "can't multiply sequence" not in out
    assert "embed(" in out and '"hello"' in out


def test_scalar_tensor_result_shows_clean_number_not_repr():
    # With real embed() vectors on CUDA, similarity/dot/norm reductions land in
    # _decode_result as a 0-d tensor; before 2026-07-04 that fell through to
    # torch's raw `tensor(0.68, device='cuda:0')` repr, leaking CUDA/dtype
    # internals to a newcomer. Test the decode directly with a 0-d tensor
    # (model-free + device-independent) so the regression guard is deterministic.
    from sutra_compiler.repl import _decode_result

    class _Mod:  # no _VSA: the scalar branch must fire regardless
        pass

    out = _decode_result(_Mod(), torch.tensor(0.6812))
    assert "tensor(" not in out and "device=" not in out
    assert out == "= 0.6812"
