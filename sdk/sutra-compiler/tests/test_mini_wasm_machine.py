"""Regression guard for the substrate RAM-state WASM stack machine
(`experiments/iso5_substrate_dispatch/mini_wasm_machine.su`).

The machine runs entirely on the Sutra substrate: all state (pc, sp, halted,
program, stack) lives in the host-attached RAM device (`ramRead`/`ramWrite`),
the host drives one `step()` per instruction (the autoregressive model), opcode
dispatch reads the opcode fresh from RAM each step, and side effects are single
blended writes to fixed cells. This test compiles the machine via the PyTorch
codegen, attaches a RAM device, loads programs as DATA, runs them, and asserts
the decoded results — the "compile AND run AND produce the expected output" bar.

Opcodes: 0=HALT 1=CONST(imm) 2=ADD 3=SUB 4=MUL 5=AND(bitwise) 6=BR_IF(abs target)
7=LOAD 8=STORE 9=EQ 10=LT 11=OUTPUT 12=OR(bitwise) 13=XOR(bitwise) 14=DUP 15=SWAP
16=DROP 17=GT 18=GE 19=LE 20=NE 21=NEG(unary negate top, net sp 0)
22=MIN(binary min(top2,top1), net sp -1) 23=MAX(binary max(top2,top1), net sp -1)
24=OVER(push copy of second-from-top, net sp +1) 25=ABS(unary |top|, net sp 0)
26=SQR(unary top*top, net sp 0) 27=NIP(drop second-from-top, net sp -1)
28=ROT([a b c]->[b c a], rotate top three, net sp 0).
"""

from __future__ import annotations

import pathlib
import sys

import pytest

def _rv(_vsa, _vec):
    # Host-side terminal-boundary read of a number-vector's real axis
    # (the `real()` runtime method was removed — no number accessor). This
    # is the sanctioned external verification read, done by direct indexing.
    return float(_vec[_vsa.semantic_dim + _vsa.AXIS_REAL])


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
    return round(float(_rv(v, ram[addr])))


# Counter@200, acc@201 loop: each iter acc++, counter--, br_if back to LOOP(22).
# Runs N iterations -> acc == N. Demonstrates a backward-branch memory loop
# (Turing-complete: memory + conditional + loop on the substrate).
_LOOP = [
    (1, 200), (1, 3), (8, 0), (1, 201), (1, 0), (8, 0),        # ram[200]=3, ram[201]=0
    (1, 201), (1, 201), (7, 0), (1, 1), (2, 0), (8, 0),        # ram[201] = acc + 1
    (1, 200), (1, 200), (7, 0), (1, 1), (3, 0), (8, 0),        # ram[200] = counter - 1
    (1, 200), (7, 0), (6, 22), (0, 0),                         # if counter != 0 -> LOOP(22)
]

# factorial(N): counter@200=N, acc@201=1; loop acc*=counter, counter--, br_if back.
# A real multiply-accumulate algorithm (loop + memory + branch) -> acc = N!.
_FACT3 = [
    (1, 200), (1, 3), (8, 0), (1, 201), (1, 1), (8, 0),       # ram[200]=3, ram[201]=1
    (1, 201), (1, 201), (7, 0), (1, 200), (7, 0), (4, 0), (8, 0),  # ram[201] = acc * counter
    (1, 200), (1, 200), (7, 0), (1, 1), (3, 0), (8, 0),       # ram[200] = counter - 1
    (1, 200), (7, 0), (6, 22), (0, 0),                        # if counter != 0 -> LOOP(22)
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
    ([(1, 72), (11, 0), (1, 73), (11, 0), (0, 0)], 72, 10, 300),  # OUTPUT 72,73 -> buf[300]=72
    ([(1, 12), (1, 10), (12, 0), (0, 0)], 14, 12, 100),       # 12 OR 10 (bitwise) = 14
    ([(1, 12), (1, 10), (13, 0), (0, 0)], 6, 12, 100),        # 12 XOR 10 (bitwise) = 6
    ([(1, 5), (14, 0), (2, 0), (0, 0)], 10, 12, 100),         # CONST 5; DUP; ADD -> 10
    ([(1, 9), (1, 3), (16, 0), (0, 0)], 9, 12, 100),          # CONST 9; CONST 3; DROP -> top 9
    ([(1, 7), (1, 2), (15, 0), (3, 0), (0, 0)], -5, 12, 100), # 7,2; SWAP; SUB -> 2-7 = -5
    ([(1, 5), (1, 3), (17, 0), (0, 0)], 1, 12, 100),          # 5 > 3 -> 1
    ([(1, 3), (1, 5), (17, 0), (0, 0)], 0, 12, 100),          # 3 > 5 -> 0
    ([(1, 7), (1, 7), (18, 0), (0, 0)], 1, 12, 100),          # 7 >= 7 -> 1 (boundary)
    ([(1, 5), (1, 6), (18, 0), (0, 0)], 0, 12, 100),          # 5 >= 6 -> 0
    ([(1, 5), (1, 5), (19, 0), (0, 0)], 1, 12, 100),          # 5 <= 5 -> 1 (boundary)
    ([(1, 6), (1, 5), (19, 0), (0, 0)], 0, 12, 100),          # 6 <= 5 -> 0
    ([(1, 7), (1, 8), (20, 0), (0, 0)], 1, 12, 100),          # 7 != 8 -> 1
    ([(1, 7), (1, 7), (20, 0), (0, 0)], 0, 12, 100),          # 7 != 7 -> 0
    ([(1, 5), (21, 0), (0, 0)], -5, 12, 100),                 # CONST 5; NEG -> -5
    ([(1, 5), (21, 0), (1, 3), (2, 0), (0, 0)], -2, 12, 100), # 5; NEG; 3; ADD -> -5+3 = -2
    ([(1, 3), (1, 5), (22, 0), (0, 0)], 3, 12, 100),          # MIN(3, 5) -> 3
    ([(1, 5), (1, 3), (22, 0), (0, 0)], 3, 12, 100),          # MIN(5, 3) -> 3
    ([(1, 4), (1, 4), (22, 0), (0, 0)], 4, 12, 100),          # MIN(4, 4) -> 4 (equality boundary)
    ([(1, 3), (1, 5), (23, 0), (0, 0)], 5, 12, 100),          # MAX(3, 5) -> 5
    ([(1, 5), (1, 3), (23, 0), (0, 0)], 5, 12, 100),          # MAX(5, 3) -> 5
    ([(1, 4), (1, 4), (23, 0), (0, 0)], 4, 12, 100),          # MAX(4, 4) -> 4 (equality boundary)
    ([(1, 3), (1, 5), (24, 0), (0, 0)], 3, 12, 102),          # 3,5; OVER -> new top (copy of 2nd) = 3 @102
    ([(1, 3), (1, 5), (24, 0), (0, 0)], 5, 12, 101),          # ...original top 5 preserved @101
    ([(1, 3), (1, 5), (24, 0), (2, 0), (0, 0)], 8, 12, 101),  # 3,5; OVER; ADD -> 5+3 = 8 (usable stack)
    ([(1, 5), (25, 0), (0, 0)], 5, 12, 100),                  # ABS(5) -> 5 (positive unchanged)
    ([(1, 0), (25, 0), (0, 0)], 0, 12, 100),                  # ABS(0) -> 0 (boundary)
    ([(1, 5), (21, 0), (25, 0), (0, 0)], 5, 12, 100),         # 5; NEG; ABS -> |-5| = 5 (neg compare+negate)
    ([(1, 5), (21, 0), (1, 5), (21, 0), (4, 0), (0, 0)], 25, 12, 100),  # (-5)*(-5) = 25 (neg*neg, existing ops)
    ([(1, 6), (26, 0), (0, 0)], 36, 12, 100),                 # SQR(6) -> 36
    ([(1, 5), (21, 0), (26, 0), (0, 0)], 25, 12, 100),        # 5; NEG; SQR -> (-5)^2 = 25
    ([(1, 3), (1, 5), (27, 0), (0, 0)], 5, 12, 100),          # 3,5; NIP -> drop 3, keep 5
    ([(1, 3), (1, 5), (27, 0), (1, 2), (2, 0), (0, 0)], 7, 12, 100),  # 3,5; NIP; 2; ADD -> 5+2 = 7 (usable stack)
    ([(1, 1), (1, 2), (1, 3), (28, 0), (0, 0)], 1, 12, 102),  # [1,2,3]; ROT -> [2,3,1]; new top = 1
    ([(1, 1), (1, 2), (1, 3), (28, 0), (0, 0)], 2, 12, 100),  # ...new deepest = 2
    ([(1, 1), (1, 2), (1, 3), (28, 0), (2, 0), (0, 0)], 4, 12, 101),  # ROT then ADD -> 3+1 = 4 (usable stack)
    ([(1, 5), (1, 5), (10, 0), (0, 0)], 0, 12, 100),          # 5 < 5 -> 0 (LT equality boundary)
    ([(1, 5), (1, 5), (17, 0), (0, 0)], 0, 12, 100),          # 5 > 5 -> 0 (GT equality boundary)
    (_LOOP, 3, 60, 201),                                       # memory loop, 3 iterations -> acc 3
    (_FACT3, 6, 70, 201),                                      # factorial(3) = 6 (real algorithm)
]


@pytest.mark.parametrize("prog,expected,steps,addr", _CASES)
def test_mini_wasm_machine_runs_on_substrate(prog, expected, steps, addr):
    ns = _machine_ns()
    got = _run(ns, prog, steps=steps, addr=addr)
    assert got == expected, f"program {prog} -> {got}, expected {expected}"


def test_dispatch_gap():
    """Signal-separation guard (CLAUDE.md  "Subtler substrate breaches" #3).

    The opcode dispatch is a 21-way substrate classifier
    (is_X = truth_axis(defuzzy(op == X))). For the running opcode the selected
    indicator must sit well above every leaked one. Measured gap is +2.0 (selected
    +1, leaked -1) at every dim because opcodes are exact integers; guard with a
    generous floor so it fires only on a real regression. Fast (compiles a
    1-function probe), unlike the full machine runs above."""
    pytest.importorskip("torch")
    import importlib.util

    repo = pathlib.Path(__file__).resolve().parents[3]
    probe = repo / "experiments" / "iso5_substrate_dispatch" / "measure_dispatch_gap.py"
    spec = importlib.util.spec_from_file_location("measure_dispatch_gap", probe)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    r = mod.measure(runtime_dim=2)
    assert r["gap"] > 1.5, f"dispatch separation collapsed: gap={r['gap']:+.4f}"
    assert r["min_selected"] > 0.5, f"selected opcode under-fires: {r['min_selected']:+.4f}"
    assert r["max_leaked"] < 0.5, f"non-selected opcode leaks: {r['max_leaked']:+.4f}"
