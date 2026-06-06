# ISO-5 capstone: a RAM-state WASM stack machine runs on the Sutra substrate

**Date:** 2026-06-06 (barreling the deferred-primitives list)
**Result:** a small WASM-style stack machine, with all state in RAM, executes
arbitrary programs on the Sutra substrate and produces correct results.

## What runs

`experiments/iso5_substrate_dispatch/mini_wasm_machine.su` — a `step()` function;
driver `run_mini_machine.py` loads a program into the RAM device and calls `step()`
once per instruction (the autoregressive model). Opcodes: 0=HALT, 1=CONST(imm),
2=ADD, 3=SUB, 4=MUL, 5=AND (bitwise — `Bits.band`), 6=BR_IF (conditional branch),
7=LOAD (pop addr, push ram[addr]), 8=STORE (pop value+addr, ram[addr]=value).

Measured (program-as-data — same machine, different RAM contents):

| Program | Result | Expected |
|---|---|---|
| const 3; const 4; add | **7** | 7 |
| const 5; const 6; add | **11** | 11 |
| const 9; const 9; add | **18** | 18 |
| const 100; const 23; add | **123** | 123 |
| const 1; const 2; add; const 3; add | **6** | 6 |
| const 10; const 3; sub | **7** | 7 |
| const 6; const 7; mul | **42** | 42 |
| const 12; const 10; **and** (bitwise) | **8** | 8 |
| const 5; const 6; mul; const 2; sub | **28** | 28 |
| const 1; br_if 18; const 100; halt; const 7 (TAKEN) | **7** | 7 |
| const 0; br_if 18; const 100 (NOT taken) | **100** | 100 |
| store 42@200; load 200 | **42** | 42 |
| **memory loop** (counter@200=N, acc@201; acc++/counter--/br_if back), N=1/3/5 | **1/3/5** | 1/3/5 |

It is a genuine interpreter: the program lives in RAM as data, not in the code. With
LOAD/STORE + a backward BR_IF the machine is **Turing-complete on the substrate** — a
memory-counter loop (counter@200, acc@201) runs N iterations to acc=N (N=1/3/5
verified). CI-guarded: `sdk/sutra-compiler/tests/test_mini_wasm_machine.py` (9/9).

## How the substrate tensions were resolved

1. **Memory = RAM** (Emma's design): pc, sp, halted, the program, and the stack are
   all RAM cells (`ramRead`/`ramWrite`). No Sutra array; the broken `dict<int,int>`
   is irrelevant.
2. **Opcode dispatch** reads the opcode FRESH each step (`ramRead(pc).real() == tag`).
   A fresh read dispatches cleanly against a literal — sidestepping the 11:30
   loop-carried-state-vs-literal blocker.
3. **Multi-state loop limit** (spec `non-halting-loop.md`: v1 `recur` has one slot)
   is sidestepped by keeping ALL state in RAM and host-driving the steps (one
   `step()` call per instruction = the transformer-vm's own autoregressive model).
   No multi-slot recur needed.
4. **Side-effect vs. fuzzy-blend tension**: a fuzzy substrate can't hard-branch, so
   per-opcode side effects can't be "selected." Resolved by writing each FIXED cell
   a single blended value — its new value if its opcode matched, else its existing
   value (a no-op rewrite). No address blending. `new_sp`/`new_pc` are likewise
   blends; HALT makes `step()` idempotent (post-halt steps don't corrupt state).

## Primitives this composes (all shipped 2026-06-06)

- substrate bitwise `band/bor/bxor` (`stdlib/bitwise.su`) — the AND opcode calls
  `Bits.band` on the raw ramRead VECTORS (not the `.real()` scalars) inside the
  machine: `12 & 10 = 8` measured. Bitwise composes inside the running machine.
- OCaml arrays → RAM lowering + RAM-device hardening (scalar-address decode,
  value-coercion to number-vector).
- RAM-based fetch-execute dispatch (this finding).

## Scope / what's not claimed

This is a 9-opcode (HALT/CONST/ADD/SUB/MUL/AND/BR_IF/LOAD/STORE) hand-written machine demonstrating the
mechanism end-to-end, NOT the full 35-opcode transformer-vm. The full machine adds
the remaining opcodes (typed loads/stores, call/return, br_table — more of the same; the machine is now Turing-complete: memory loop via LOAD/STORE + backward BR_IF verified blended
dispatch + RAM), byte/bitwise arithmetic (bitwise stdlib ready), and a larger
linear-memory region (the host RAM-list doesn't scale to 10 MB — a scalable RAM
device is the follow-on). The hard substrate questions (memory model, dispatch,
state, side effects) are answered; remaining work is breadth, not feasibility.
