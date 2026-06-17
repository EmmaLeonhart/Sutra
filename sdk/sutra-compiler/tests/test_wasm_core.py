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
0x4c/76=i32.le_s 0x4e/78=i32.ge_s 0x02/2=block 0x03/3=loop 0x04/4=if 0x05/5=else
0x0c/12=br 0x0d/13=br_if 0x0b/11=end 0x0f/15=return. Structured control uses a load-time
pre-resolved branch-target table (built by `_build_targets`, loaded at RAM 400+); the
substrate reads it and jumps.
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


# 2-byte WASM opcodes (opcode + 1 operand byte): i32.const, local.get/set/tee,
# block, loop, if, br, br_if. Everything else in this core is 1 byte.
_LEN2 = {65, 32, 33, 34, 2, 3, 4, 12, 13}


def _ilen(op):
    return 2 if op in _LEN2 else 1


def _build_targets(body):
    """Host-side compilation (load-time, allowed): resolve WASM structured control to a
    pre-resolved branch-target table {code_offset: target_code_offset}. Default target is
    the sequential next offset; the function-final `end` targets ITSELF (halt); `br k`/
    `br_if k` target the k-th enclosing label (loop header for a loop, after-`end` for a
    block/if). The substrate reads RAM[400+offset] = 10 + target_offset and jumps there."""
    n = len(body)
    instrs = []          # (offset, opcode, length)
    tgt = {}
    off = 0
    while off < n:
        op = body[off]
        L = _ilen(op)
        instrs.append((off, op, L))
        tgt[off] = off + L   # default: sequential next
        off += L
    # Pass A: match block/loop/if opens to their `end`s; record each if's `else`.
    frames_by_open = {}
    stack = []
    for (off, op, L) in instrs:
        if op in (2, 3, 4):          # block / loop / if
            f = {"kind": {2: "block", 3: "loop", 4: "if"}[op],
                 "header": off + 2, "end": None, "else_off": None}
            stack.append(f)
            frames_by_open[off] = f
        elif op == 5:                # else (belongs to the innermost open if)
            stack[-1]["else_off"] = off
        elif op == 11:               # end
            if stack:
                stack.pop()["end"] = off
    # if false-target = else+1 (or end+1 if no else); else -> matching end+1.
    for open_off, f in frames_by_open.items():
        if f["kind"] == "if":
            tgt[open_off] = (f["else_off"] + 1) if f["else_off"] is not None else (f["end"] + 1)
            if f["else_off"] is not None:
                tgt[f["else_off"]] = f["end"] + 1
    # Pass B: resolve br/br_if targets + the function-final end (depth 0) -> halt.
    stack = []
    for (off, op, L) in instrs:
        if op in (2, 3, 4):
            stack.append(frames_by_open[off])
        elif op == 11:
            if stack:
                stack.pop()
            else:
                tgt[off] = off       # function-final end -> halt (jump to self)
        elif op in (12, 13):         # br / br_if
            k = body[off + 1]
            f = stack[-(k + 1)]
            tgt[off] = f["header"] if f["kind"] == "loop" else f["end"] + 1
    return tgt


# Frame-relative layout (step 5a): the single frame lives in the arena at FP_BASE; its
# locals occupy FP_BASE..FP_BASE+NLOC-1 and its operand stack starts at FP_BASE+NLOC.
# NLOC=4 covers locals 0..3 (the most any current fixture uses). The lone final result
# sits at the operand base (FP_BASE+NLOC) when the machine halts with sp=1.
FP_BASE = 600
NLOC = 4


def _run(ns, body, steps=10, addr=100, locals0=None):
    """Load `body` (a flat list of WASM function-body bytes) into RAM at the code base
    (10), build + load the pre-resolved branch-target table at RAM 400+, set the frame
    pointer (fp=FP_BASE, nloc=NLOC), run `steps` host-driven ticks, return the decoded
    result from the frame's operand base. `locals0` seeds locals 0..N at fp+i — WASM
    passes function params in the low locals, so `(func (param i32) …)` reads it from
    local 0. (`addr` is retained for signature compat; the result is read frame-relative.)"""
    v = ns["_VSA"]
    ram = [v.zero_vector() for _ in range(1024)]
    ram[0] = v.make_real(10.0)        # pc
    ram[1] = v.make_real(0.0)         # sp (frame-relative operand count)
    ram[2] = v.make_real(float(FP_BASE))  # fp (current frame base)
    ram[3] = v.make_real(float(NLOC))     # nloc (current frame local count)
    for i, b in enumerate(body):
        ram[10 + i] = v.make_real(float(b))
    for off, target_off in _build_targets(body).items():
        ram[400 + off] = v.make_real(float(10 + target_off))  # absolute RAM target pc
    for i, val in enumerate(locals0 or []):
        ram[FP_BASE + i] = v.make_real(float(val))
    v.ram = ram
    for _ in range(steps):
        ns["step"](0.0)
    return round(float(_rv(v, ram[FP_BASE + NLOC])))


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
    # structured control (pre-resolved target table):
    # block + br 0 forward exit skips the unreachable i32.const 99 -> top = 7
    ([65, 7, 2, 64, 12, 0, 65, 99, 11, 11], 7, 8, 100),
    # countdown-sum loop 3+2+1 = 6 (block/loop/br_if 1 exit/br 0 repeat):
    #   local0=sum local1=i; loop { if i==0 br to block-end; sum+=i; i-=1; br to loop }
    ([65, 0, 33, 0, 65, 3, 33, 1, 2, 64, 3, 64, 32, 1, 69, 13, 1, 32, 0, 32, 1,
      106, 33, 0, 32, 1, 65, 1, 107, 33, 1, 12, 0, 11, 11, 32, 0, 11], 6, 80, 100),
    # if/else (blocktype i32 = 0x7f=127): const c; if (const 7) else (const 9); end
    ([65, 1, 4, 127, 65, 7, 5, 65, 9, 11, 11], 7, 12, 100),   # cond 1 -> then-arm -> 7
    ([65, 0, 4, 127, 65, 7, 5, 65, 9, 11, 11], 9, 12, 100),   # cond 0 -> else-arm -> 9
    # if WITHOUT else (blocktype empty = 0x40=64): local0=5; if (cond) { local0=9 }; get local0
    ([65, 5, 33, 0, 65, 0, 4, 64, 65, 9, 33, 0, 11, 32, 0, 11], 5, 14, 100),  # cond 0 -> skip -> 5
    ([65, 5, 33, 0, 65, 1, 4, 64, 65, 9, 33, 0, 11, 32, 0, 11], 9, 14, 100),  # cond 1 -> run  -> 9
]


@pytest.mark.parametrize("body,expected,steps,addr", _CASES,
                         ids=[str(c[0]) for c in _CASES])
def test_wasm_core_runs_on_substrate(body, expected, steps, addr):
    ns = _machine_ns()
    got = _run(ns, body, steps=steps, addr=addr)
    assert got == expected, f"body {body} -> {got}, expected {expected}"


# A REAL WebAssembly iterative-factorial function body, run byte-for-byte on the
# substrate (Phase 5, step 4 — the JVM-factorial oracle, in WASM). Source WAT:
#   (func (param i32) (result i32) (local i32 i32)   ;; n=local0, r=local1, i=local2
#     (i32.const 1)(local.set 1)  (i32.const 1)(local.set 2)
#     (block (loop
#       (local.get 2)(local.get 0)(i32.gt_s)(br_if 1)   ;; if i>n, exit
#       (local.get 1)(local.get 2)(i32.mul)(local.set 1) ;; r *= i
#       (local.get 2)(i32.const 1)(i32.add)(local.set 2) ;; i += 1
#       (br 0)))
#     (local.get 1))
# Bytes are hand-assembled to the WASM spec encoding (wat2wasm/wasm-tools is not
# available in this environment). The opcode + LEB128 encoding is deterministic from
# the spec, so these are byte-identical to what wat2wasm emits for the body expression
# (the module-binary wrapper — magic/sections/locals-decl — is host-side and not part of
# this minimal core, exactly as the JVM core loaded only the method's Code attribute).
# Follow-up: cross-check against actual wat2wasm output on a toolchain-equipped path (CI).
_WASM_FACT = [65, 1, 33, 1, 65, 1, 33, 2, 2, 64, 3, 64, 32, 2, 32, 0, 74, 13, 1,
              32, 1, 32, 2, 108, 33, 1, 32, 2, 65, 1, 106, 33, 2, 12, 0, 11, 11, 32, 1, 11]


@pytest.mark.parametrize("n,expected", [(0, 1), (1, 1), (4, 24), (5, 120)])
def test_wasm_core_runs_real_wasm_factorial(n, expected):
    """The real-WASM-encoded iterative-factorial body run byte-for-byte on the substrate;
    n is seeded into local 0 (WASM param convention). Decoded operand-stack top == n!."""
    ns = _machine_ns()
    got = _run(ns, _WASM_FACT, steps=200, addr=100, locals0=[n])
    assert got == expected, f"fact({n}) -> {got}, expected {expected}"
