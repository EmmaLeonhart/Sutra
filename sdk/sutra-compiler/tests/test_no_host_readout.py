"""Enforcement gate for the substrate-purity overhaul (Emma 2026-06-07).

Sutra has NO readout/log/monitor/debug by design. A compiled program must be a
connected substrate (torch) computation; every `.item()` is a host readout that
severs substrate-purity AND detaches the autograd graph (a gradient wall, which
is why "Sutra compiles to one differentiable neural network" is not yet true).

This gate counts the `.item()` host-readouts the codegen emits into the runtime
and asserts the count never INCREASES. The baseline is the audited starting point
(`planning/findings/2026-06-07-codegen-host-readout-audit.md`); the goal is **0**.
Lower BASELINE as readouts are removed — never raise it.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

# Audited 2026-06-07: 26 `.item()` host-readout calls in the generated runtime.
# Categories (see the audit finding): pure accessors (real/imag/truth/component/
# semantic/synthetic), array_length, ram_read/ram_write address decode (I/O wire),
# is_char/is_string, js_strict_neq/js_loose_neq, _js_str_cmp, string_to_python.
# GOAL: 0. This number must only go DOWN.
BASELINE_ITEM_READOUTS = 26


def _generated_runtime_source() -> str:
    repo = pathlib.Path(__file__).resolve().parents[3]
    compiler_src = repo / "sdk" / "sutra-compiler"
    if str(compiler_src) not in sys.path:
        sys.path.insert(0, str(compiler_src))
    from sutra_compiler.lexer import Lexer
    from sutra_compiler.parser import Parser
    from sutra_compiler.codegen_pytorch import translate_module

    src = 'function string main(){return "ok";}'
    lx = Lexer(src, file="<gate>")
    ast = Parser(lx.tokenize(), file="<gate>", diagnostics=lx.diagnostics).parse_module()
    return translate_module(ast, llm_model="none", runtime_dim=2)


def _count_item_readouts(code: str) -> int:
    """Count `.item()` calls in real code lines, excluding comments and the
    docstring/comment notes that merely MENTION .item() (e.g. 'no .item()')."""
    n = 0
    for ln in code.splitlines():
        s = ln.strip()
        if s.startswith("#"):
            continue
        if ("no .item()" in s or "was " in s or "AT that boundary" in s
                or ".item()/float()" in s or ".item() /" in s):
            continue
        n += s.count(".item()")
    return n


def test_host_readout_does_not_increase():
    pytest.importorskip("torch")
    code = _generated_runtime_source()
    count = _count_item_readouts(code)
    assert count <= BASELINE_ITEM_READOUTS, (
        f"host-readout `.item()` count rose to {count} (baseline "
        f"{BASELINE_ITEM_READOUTS}). The language has no readout by design — "
        f"remove the new `.item()`/host extraction, do not raise the baseline."
    )


def test_baseline_is_tight():
    """If readouts were removed, the baseline must be lowered to match (keeps the
    gate honest — it can't silently stop shrinking)."""
    pytest.importorskip("torch")
    code = _generated_runtime_source()
    count = _count_item_readouts(code)
    assert count == BASELINE_ITEM_READOUTS, (
        f"host-readout count is {count} but BASELINE is "
        f"{BASELINE_ITEM_READOUTS}. Lower BASELINE_ITEM_READOUTS to {count} "
        f"(progress toward 0) in the same commit that removed the readout."
    )
