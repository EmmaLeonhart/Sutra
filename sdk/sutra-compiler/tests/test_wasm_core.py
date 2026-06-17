"""Regression guard for the real-WebAssembly-bytecode core
(`experiments/iso5_substrate_dispatch/wasm_core.su`) — Phase 5, step 1a.

Same RAM-state blended-dispatch DNC model as the JVM core, but with REAL WASM opcode
values and the WASM operand encoding (single-byte signed LEB128 for i32.const). The
machine runs entirely on the Sutra substrate: state (pc, sp, operand stack) lives in
the host RAM device, the host drives one `step()` per instruction, dispatch reads the
opcode fresh from RAM, side effects are blended writes to fixed cells. This test
compiles the machine via the PyTorch codegen, attaches a RAM device, loads a function
body as raw WASM bytes, runs it, and asserts the decoded operand-stack result.

Opcodes (real WASM byte values): 0x41/65=i32.const (signed single-byte LEB128)
0x20/32=local.get 0x21/33=local.set 0x22/34=local.tee (unsigned single-byte LEB128
index; local lives at RAM 200+idx) 0x6a/106=i32.add 0x6b/107=i32.sub 0x6c/108=i32.mul
0x45/69=i32.eqz 0x46/70=i32.eq 0x47/71=i32.ne 0x48/72=i32.lt_s 0x4a/74=i32.gt_s
0x4c/76=i32.le_s 0x4e/78=i32.ge_s 0x0b/11=end 0x0f/15=return (end/return keep pc ->
idle with the result on top).
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
    su_path = repo / "experiments" / "iso5_substrate_dispatch" / "wasm_core.su"
    compiler_src = repo / "sdk" / "sutra-compiler"
    if str(compiler_src) not in sys.path:
        sys.path.insert(0, str(compiler_src))
    from sutra_compiler.lexer import Lexer
    from sutra_compiler.parser import Parser
    from sutra_compiler.codegen_pytorch import translate_module

    src = su_path.read_text(encoding="utf-8")
    lx = Lexer(src, file="<wasm>")
    ast = Parser(lx.tokenize(), file="<wasm>", diagnostics=lx.diagnostics).parse_module()
    assert not lx.diagnostics.has_errors(), list(lx.diagnostics)
    ns: dict = {}
    exec(translate_module(ast, llm_model="none", runtime_dim=2), ns)
    return ns


def _run(ns, body, steps=10, addr=100):
    """Load `body` (a flat list of WASM function-body bytes) into RAM at the code base
    (10), run `steps` host-driven ticks, return the decoded RAM[addr] (operand-stack
    base 100 by default — where the final result lands)."""
    v = ns["_VSA"]
    ram = [v.zero_vector() for _ in range(512)]
    ram[0] = v.make_real(10.0)   # pc
    ram[1] = v.make_real(0.0)    # sp
    for i, b in enumerate(body):
        ram[10 + i] = v.make_real(float(b))
    v.ram = ram
    for _ in range(steps):
        ns["step"](0.0)
    return round(float(_rv(v, ram[addr])))


# (body, expected, steps, result_addr). Real WASM byte values; signed LEB128 for
# i32.const (e.g. -5 encodes as 0x7b = 123).
_CASES = [
    ([65, 3, 65, 4, 106, 11], 7, 10, 100),       # i32.const 3; i32.const 4; i32.add; end -> 7
    ([65, 10, 65, 3, 107, 11], 7, 10, 100),       # i32.const 10; i32.const 3; i32.sub -> 7
    ([65, 6, 65, 7, 108, 11], 42, 10, 100),       # i32.const 6; i32.const 7; i32.mul -> 42
    ([65, 123, 15], -5, 10, 100),                 # i32.const -5 (LEB 0x7b); return -> -5
    ([65, 123, 65, 123, 108, 11], 25, 10, 100),   # (-5) * (-5) -> 25 (signed LEB + neg arithmetic)
    ([65, 3, 65, 4, 106, 65, 2, 108, 11], 14, 12, 100),  # (3+4)*2 -> 14
    ([65, 63, 11], 63, 10, 100),                  # i32.const 63 (max single-byte positive) -> 63
    ([65, 64, 11], -64, 10, 100),                 # i32.const -64 (LEB 0x40, min single-byte) -> -64
    # indexed locals (local lives at RAM 200+idx):
    # i32.const 5; local.set 0; local.get 0; local.get 0; i32.add -> 10
    ([65, 5, 33, 0, 32, 0, 32, 0, 106, 11], 10, 12, 100),
    # local.tee leaves the value on the stack: i32.const 7; local.tee 1; local.get 1; i32.add -> 14
    ([65, 7, 34, 1, 32, 1, 106, 11], 14, 10, 100),
    # two locals: local1=7; local0=3; local.get 1; local.get 0; i32.sub -> 7-3 = 4
    ([65, 7, 33, 1, 65, 3, 33, 0, 32, 1, 32, 0, 107, 11], 4, 14, 100),
    # local round-trip: i32.const 9; local.set 2; local.get 2; return -> 9
    ([65, 9, 33, 2, 32, 2, 15], 9, 10, 100),
    # comparisons (push 0/1; value1=top2 deeper, value2=top1 top):
    ([65, 5, 65, 5, 70, 11], 1, 12, 100),    # i32.eq 5==5 -> 1
    ([65, 5, 65, 3, 70, 11], 0, 12, 100),    # i32.eq 5==3 -> 0
    ([65, 5, 65, 3, 71, 11], 1, 12, 100),    # i32.ne 5!=3 -> 1
    ([65, 3, 65, 5, 72, 11], 1, 12, 100),    # i32.lt_s 3<5 -> 1
    ([65, 5, 65, 3, 72, 11], 0, 12, 100),    # i32.lt_s 5<3 -> 0
    ([65, 5, 65, 3, 74, 11], 1, 12, 100),    # i32.gt_s 5>3 -> 1
    ([65, 5, 65, 5, 78, 11], 1, 12, 100),    # i32.ge_s 5>=5 (equality boundary) -> 1
    ([65, 5, 65, 5, 76, 11], 1, 12, 100),    # i32.le_s 5<=5 (equality boundary) -> 1
    ([65, 5, 65, 3, 76, 11], 0, 12, 100),    # i32.le_s 5<=3 -> 0
    ([65, 0, 69, 11], 1, 10, 100),           # i32.eqz 0 -> 1
    ([65, 5, 69, 11], 0, 10, 100),           # i32.eqz 5 -> 0
    ([65, 123, 65, 3, 72, 11], 1, 12, 100),  # i32.lt_s -5<3 (signed) -> 1
]


@pytest.mark.parametrize("body,expected,steps,addr", _CASES,
                         ids=[str(c[0]) for c in _CASES])
def test_wasm_core_runs_on_substrate(body, expected, steps, addr):
    ns = _machine_ns()
    got = _run(ns, body, steps=steps, addr=addr)
    assert got == expected, f"body {body} -> {got}, expected {expected}"
