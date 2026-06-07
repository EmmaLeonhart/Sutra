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

# Audited 2026-06-07: started at 26 `.item()` host-readout calls in the generated
# runtime. 2026-06-07: removed the 6 dead accessors (imag/truth/component/
# semantic/synthetic, −5 .item(); norm, −1 float-readout) → 21.
# Remaining categories: `real` (next target), array_length, ram_read/ram_write
# address decode (I/O wire decision), is_char/is_string, js_strict_neq/
# js_loose_neq, _js_str_cmp, string_to_python. GOAL: 0. Only ever lower this.
BASELINE_ITEM_READOUTS = 21


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


# ── Loop emission: the STEP must be readout-free; the halt-read lives in the
# ──             driver (the legitimate orchestrator boundary, Emma 2026-06-07).
# An unbounded substrate loop (do_while / while_loop) now compiles to a PURE
# nested `_step(...)` (one tick: condition + body + soft-halt, all substrate, NO
# host readout) plus a thin in-module DRIVER that calls it and reads
# `float(_halted)` to break. Per Emma's orchestrator model
# ([[project_orchestrator_model]], planning/exploratory/fused-compile-target.md),
# that halt-read is the legitimate terminal/orchestrator boundary, NOT an in-graph
# violation. So the invariant is NOT "0 float(_halted) anywhere" — it is:
#   (1) the `_step` graph contains ZERO host readout (it is the fusable/exportable
#       weight artifact), and
#   (2) the single `float(_halted)` stays in the driver, never inside `_step`.
# (Supersedes the prior "fix = bounded-N, goal 0" framing — codegen restructured
# so the step is separable; see the loop-emission-host-readout finding.)
BASELINE_DRIVER_HALTED_READOUTS = 1  # one driver read per loop in do_while_adder.su


def _loop_program_source() -> str:
    import pathlib as _pl
    repo = _pl.Path(__file__).resolve().parents[3]
    src = (repo / "examples" / "do_while_adder.su").read_text(encoding="utf-8")
    sys.path  # ensure import path set by _generated_runtime_source caller
    repo_compiler = repo / "sdk" / "sutra-compiler"
    if str(repo_compiler) not in sys.path:
        sys.path.insert(0, str(repo_compiler))
    from sutra_compiler.lexer import Lexer
    from sutra_compiler.parser import Parser
    from sutra_compiler.codegen_pytorch import translate_module
    lx = Lexer(src, file="<loopgate>")
    ast = Parser(lx.tokenize(), file="<loopgate>", diagnostics=lx.diagnostics).parse_module()
    return translate_module(ast, llm_model="none", runtime_dim=16)


def _step_blocks(code: str) -> list[str]:
    """Extract the body of every nested `def _step(...):` from generated code
    (the per-tick loop step). Returns one joined-source string per block."""
    lines = code.splitlines()
    blocks: list[str] = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.strip().startswith("def _step("):
            def_indent = len(ln) - len(ln.lstrip())
            body: list[str] = []
            j = i + 1
            while j < len(lines):
                bl = lines[j]
                if bl.strip() == "":
                    body.append(bl)
                    j += 1
                    continue
                indent = len(bl) - len(bl.lstrip())
                if indent <= def_indent:
                    break
                body.append(bl)
                j += 1
            blocks.append("\n".join(body))
            i = j
        else:
            i += 1
    return blocks


def test_step_graph_is_readout_free():
    """The core overhaul invariant: the per-tick `_step` (the fusable/exportable
    weight graph) contains NO host readout — no `float(`, no `.item()`."""
    pytest.importorskip("torch")
    code = _loop_program_source()
    blocks = _step_blocks(code)
    assert blocks, "expected at least one `def _step(` in a compiled loop program"
    for blk in blocks:
        for bad in ("float(", ".item()"):
            # exclude the docstring/comment lines that merely mention it
            offenders = [
                ln for ln in blk.splitlines()
                if bad in ln and not ln.strip().startswith("#")
                and '"""' not in ln
            ]
            assert not offenders, (
                f"the pure loop STEP graph contains a host readout `{bad}` "
                f"(must live in the driver, not the step): {offenders}"
            )


def test_driver_halt_read_does_not_increase():
    """The halt-read `float(_halted)` is the legitimate orchestrator boundary; it
    must stay in the driver and not multiply (one per loop)."""
    pytest.importorskip("torch")
    code = _loop_program_source()
    n = code.count("float(_halted")
    assert n <= BASELINE_DRIVER_HALTED_READOUTS, (
        f"driver halt-read `float(_halted...)` count rose to {n} "
        f"(baseline {BASELINE_DRIVER_HALTED_READOUTS}). One driver read per loop; "
        f"do not multiply it, and do not let it leak into `_step`."
    )


def test_driver_halt_read_baseline_is_tight():
    pytest.importorskip("torch")
    code = _loop_program_source()
    n = code.count("float(_halted")
    assert n == BASELINE_DRIVER_HALTED_READOUTS, (
        f"driver halt-read count is {n} but BASELINE is "
        f"{BASELINE_DRIVER_HALTED_READOUTS}. Adjust BASELINE_DRIVER_HALTED_READOUTS "
        f"in the same commit that changed it."
    )
