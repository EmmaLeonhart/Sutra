"""Regression guard for the substrate JVM-bytecode core
(`experiments/iso5_substrate_dispatch/jvm_core.su`) — Phase 5 leg 2.

Same RAM-state blended-dispatch model as the mini WASM machine, but with REAL JVM
opcode values and the JVM's variable-length bytecode layout (one byte per cell;
bipush carries a 1-byte operand). The machine runs entirely on the Sutra
substrate: state (pc, sp, operand stack) lives in the host RAM device, the host
drives one `step()` per instruction, dispatch reads the opcode fresh from RAM,
side effects are blended writes to fixed cells. This test compiles the machine via
the PyTorch codegen, attaches a RAM device, loads bytecode as raw bytes, runs it,
and asserts the decoded operand-stack result — the compile-AND-run bar.

Opcodes (real JVM decimal values): 16=bipush 96=iadd 100=isub 104=imul 116=ineg
172=ireturn (keeps pc -> idle with the result on top) 26..29=iload_0..3
59..62=istore_0..3 (locals 0..3 at RAM 200..203). op 0 = nop.
"""
from __future__ import annotations

import pathlib
import sys

import pytest


def _rv(_vsa, _vec):
    # External terminal-boundary read of a number-vector's real axis (sanctioned
    # verification read; the machine itself does no host readout).
    return float(_vec[_vsa.semantic_dim + _vsa.AXIS_REAL])


def _machine_ns():
    pytest.importorskip("torch")
    repo = pathlib.Path(__file__).resolve().parents[3]
    su_path = repo / "experiments" / "iso5_substrate_dispatch" / "jvm_core.su"
    compiler_src = repo / "sdk" / "sutra-compiler"
    if str(compiler_src) not in sys.path:
        sys.path.insert(0, str(compiler_src))
    from sutra_compiler.lexer import Lexer
    from sutra_compiler.parser import Parser
    from sutra_compiler.codegen_pytorch import translate_module

    src = su_path.read_text(encoding="utf-8")
    lx = Lexer(src, file="<jvm>")
    ast = Parser(lx.tokenize(), file="<jvm>", diagnostics=lx.diagnostics).parse_module()
    assert not lx.diagnostics.has_errors(), list(lx.diagnostics)
    ns: dict = {}
    exec(translate_module(ast, llm_model="none", runtime_dim=2), ns)
    return ns


def _run(ns, bytecode, steps=10, addr=100):
    """Load `bytecode` (a flat list of JVM bytes) into RAM at the code base (10),
    run `steps` host-driven ticks, return the decoded RAM[addr] (operand-stack
    base 100 by default — where the final result lands)."""
    v = ns["_VSA"]
    ram = [v.zero_vector() for _ in range(512)]
    ram[0] = v.make_real(10.0)   # pc
    ram[1] = v.make_real(0.0)    # sp
    for i, b in enumerate(bytecode):
        ram[10 + i] = v.make_real(float(b))
    v.ram = ram
    for _ in range(steps):
        ns["step"](0.0)
    return round(float(_rv(v, ram[addr])))


# (bytecode, expected, steps, result_addr). JVM decimal opcodes.
_CASES = [
    ([16, 3, 16, 4, 96, 172], 7, 10, 100),    # bipush 3; bipush 4; iadd; ireturn -> 7
    ([16, 10, 16, 3, 100, 172], 7, 10, 100),  # bipush 10; bipush 3; isub -> 10-3 = 7
    ([16, 6, 16, 7, 104, 172], 42, 10, 100),  # bipush 6; bipush 7; imul -> 42
    ([16, 5, 116, 172], -5, 10, 100),         # bipush 5; ineg -> -5
    ([16, 5, 116, 116, 172], 5, 10, 100),     # bipush 5; ineg; ineg -> 5
    ([16, 5, 16, 6, 104, 16, 2, 100, 172], 28, 12, 100),  # 5*6 - 2 = 28
    ([16, 3, 16, 4, 96, 116, 172], -7, 10, 100),          # (3+4); ineg -> -7
    # locals: store 5 in local 0, load it twice, add -> 10
    ([16, 5, 59, 26, 26, 96, 172], 10, 12, 100),          # bipush 5; istore_0; iload_0; iload_0; iadd
    # two locals: local1=7, local0=3; iload_0; iload_1; isub -> 3-7 = -4
    ([16, 7, 60, 16, 3, 59, 26, 27, 100, 172], -4, 14, 100),
    # local2 round-trip: bipush 9; istore_2; iload_2; ireturn -> 9
    ([16, 9, 61, 28, 172], 9, 10, 100),
]


@pytest.mark.parametrize("bytecode,expected,steps,addr", _CASES,
                         ids=[str(c[0]) for c in _CASES])
def test_jvm_core_runs_on_substrate(bytecode, expected, steps, addr):
    ns = _machine_ns()
    got = _run(ns, bytecode, steps=steps, addr=addr)
    assert got == expected, f"bytecode {bytecode} -> {got}, expected {expected}"
