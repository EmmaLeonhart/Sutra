"""Regression guard for the substrate RAM-state WASM stack machine
(`experiments/iso5_substrate_dispatch/mini_wasm_machine.su`).

The machine runs entirely on the Sutra substrate: all state (pc, sp, halted,
program, stack) lives in the host-attached RAM device (`ramRead`/`ramWrite`),
the host drives one `step()` per instruction (the autoregressive model), opcode
dispatch reads the opcode fresh from RAM each step, and side effects are single
blended writes to fixed cells. This test compiles the machine via the PyTorch
codegen, attaches a RAM device, loads programs as DATA, runs them, and asserts
the decoded results — the "compile AND run AND produce the expected output" bar.

Opcodes: 0=HALT 1=CONST(imm) 2=ADD 3=SUB 4=MUL 5=AND(bitwise) 6=BR_IF(abs target).
"""

from __future__ import annotations

import pathlib
import sys

import pytest


def _machine_ns():
    pytest.importorskip("torch")
    repo = pathlib.Path(__file__).resolve().parents[3]
    su_path = repo / "experiments" / "iso5_substrate_dispatch" / "mini_wasm_machine.su"
    compiler_src = repo / "sdk" / "sutra-compiler"
    if str(compiler_src) not in sys.path:
        sys.path.insert(0, str(compiler_src))
    from sutra_compiler.lexer import Lexer
    from sutra_compiler.parser import Parser
    from sutra_compiler.codegen_pytorch import translate_module

    src = su_path.read_text(encoding="utf-8")
    lx = Lexer(src, file="<machine>")
    ast = Parser(lx.tokenize(), file="<machine>", diagnostics=lx.diagnostics).parse_module()
    assert not lx.diagnostics.has_errors(), list(lx.diagnostics)
    ns: dict = {}
    exec(translate_module(ast, llm_model="none", runtime_dim=2), ns)
    return ns


def _run(ns, prog, steps=12, addr=100):
    """Load `prog` (list of (opcode, immediate)) into RAM at the program base
    (10), run `steps` host-driven ticks, return the decoded RAM[addr]
    (the stack base 100 by default; a data cell for LOAD/STORE/loop cases)."""
    v = ns["_VSA"]
    ram = [v.zero_vector() for _ in range(512)]
    ram[0] = v.make_real(10.0)   # pc
    ram[1] = v.make_real(0.0)    # sp
    ram[2] = v.make_real(0.0)    # halted
    for k, (op, imm) in enumerate(prog):
        ram[10 + 2 * k] = v.make_real(float(op))
        ram[11 + 2 * k] = v.make_real(float(imm))
    v.ram = ram
    for _ in range(steps):
        ns["step"](0.0)
    return round(float(v.real(ram[addr])))


# Counter@200, acc@201 loop: each iter acc++, counter--, br_if back to LOOP(22).
# Runs N iterations -> acc == N. Demonstrates a backward-branch memory loop
# (Turing-complete: memory + conditional + loop on the substrate).
_LOOP = [
    (1, 200), (1, 3), (8, 0), (1, 201), (1, 0), (8, 0),        # ram[200]=3, ram[201]=0
    (1, 201), (1, 201), (7, 0), (1, 1), (2, 0), (8, 0),        # ram[201] = acc + 1
    (1, 200), (1, 200), (7, 0), (1, 1), (3, 0), (8, 0),        # ram[200] = counter - 1
    (1, 200), (7, 0), (6, 22), (0, 0),                         # if counter != 0 -> LOOP(22)
]

# (program, expected, steps, result_addr). Opcodes per the module docstring.
_CASES = [
    ([(1, 3), (1, 4), (2, 0), (0, 0)], 7, 12, 100),            # const 3; const 4; add
    ([(1, 10), (1, 3), (3, 0), (0, 0)], 7, 12, 100),           # 10 - 3
    ([(1, 6), (1, 7), (4, 0), (0, 0)], 42, 12, 100),           # 6 * 7
    ([(1, 12), (1, 10), (5, 0), (0, 0)], 8, 12, 100),          # 12 AND 10 (bitwise)
    ([(1, 5), (1, 6), (4, 0), (1, 2), (3, 0), (0, 0)], 28, 12, 100),  # 5*6 - 2
    ([(1, 1), (6, 18), (1, 100), (0, 0), (1, 7), (0, 0)], 7, 12, 100),    # br_if TAKEN
    ([(1, 0), (6, 18), (1, 100), (0, 0), (1, 7), (0, 0)], 100, 12, 100),  # br_if NOT taken
    ([(1, 200), (1, 42), (8, 0), (1, 200), (7, 0), (0, 0)], 42, 8, 100),  # STORE 42@200; LOAD
    ([(1, 3), (1, 5), (10, 0), (0, 0)], 1, 12, 100),          # 3 < 5  -> 1
    ([(1, 5), (1, 3), (10, 0), (0, 0)], 0, 12, 100),          # 5 < 3  -> 0
    ([(1, 7), (1, 7), (9, 0), (0, 0)], 1, 12, 100),           # 7 == 7 -> 1
    ([(1, 7), (1, 8), (9, 0), (0, 0)], 0, 12, 100),           # 7 == 8 -> 0
    (_LOOP, 3, 60, 201),                                       # memory loop, 3 iterations -> acc 3
]


@pytest.mark.parametrize("prog,expected,steps,addr", _CASES)
def test_mini_wasm_machine_runs_on_substrate(prog, expected, steps, addr):
    ns = _machine_ns()
    got = _run(ns, prog, steps=steps, addr=addr)
    assert got == expected, f"program {prog} -> {got}, expected {expected}"
