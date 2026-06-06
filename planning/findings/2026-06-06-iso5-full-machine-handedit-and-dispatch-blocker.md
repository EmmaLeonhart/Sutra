# ISO-5 full-machine hand-edit attempt: the substrate loop-dispatch blocker

**Date:** 2026-06-06 (11:30 milestone — full end-to-end attempt)
**Goal:** transpile the complete WASM OCaml machine (`WASM/iso/ocaml/bin/main.ml`,
189 lines) to Sutra and hand-edit it until it runs on the substrate and reproduces
the OCaml reference output for the simplest program.

## Outcome (measured, not faked)

The full machine **cannot be hand-finished to run on Sutra in this window** — for
structural reasons that no amount of hand-editing fixes without new substrate
primitives. Below is exactly what transpiled, what is blocked, and one substrate
*dispatch* blocker discovered while hand-writing a minimal fetch-execute loop.

### 1. What the transpiler produces on the full machine

`PYTHONPATH=sdk/sutra-from-ocaml python -m sutra_from_ocaml WASM/iso/ocaml/bin/main.ml`
lowers with **28 `UNSUPPORTED-*` markers**: 16 EXPR (lists, array-get, `try`,
expression-position options, complex `let`), 7 LOCAL-FN (closures capturing `stack`/
`pc`/…), 2 WHILE (the fetch-execute loops — bodies use arrays/try), 1 OP (a bitwise
op), 1 MATCH (expression-position option), 1 LET (a complex value binding).

### 2. Structural blockers (no Sutra primitive exists)

The machine is a **stack machine**: an instruction array, a value stack, a 256-int
`locals` array, and a 10 MB `Bytes` linear memory. Realizing it needs:

- **Substrate arrays** — `dict<int,int>` (the substrate-faithful candidate) is broken
  (scalar keys not lifted to vectors; finding
  `2026-06-06-dict-int-keys-broken-blocks-arrays.md`). `list<T>` is a Python host
  list (not substrate). So stack/locals/memory have no substrate carrier.
- **Byte / bitwise ops** — `land 0xff`, `lsl 8`, `lor` pervade the byte arithmetic.
  Sutra has no bitwise operator (`&`/`|` are fuzzy-logical: `12 & 10` = 7149 not 8;
  `<<`/`>>` don't parse). Needs a substrate bitwise stdlib.
- **Exceptions** — `raise Exit` breaks the fetch-execute loop (the `halt` opcode);
  `failwith` for error paths. Sutra has no exceptions.

### 3. Ground truth could not be run locally

The reference test programs live in the `transformer-vm` submodule
(`replication_target/transformer-vm/transformer_vm/data/*.txt`), which is not
initialized in this checkout — so the OCaml machine could not be executed here for a
byte-exact comparison. (Expected outputs from `WASM/FINDINGS.md`: hello →
`Hello World!`, addition → `19134`, fibonacci → `55`.) Running it needs
`git submodule update --init` + `dune build`.

### 4. The substrate dispatch blocker (the load-bearing new result)

Even setting arrays aside, I hand-wrote a minimal substrate fetch-execute loop for
the tiny program `[i32.const 3 ; i32.const 4 ; i32.add]` (stack = 2 scalar slots,
opcode dispatch = defuzz blend on `pc`, state carried across `while_loop` ticks). It
returned **4, not 7**. Debugging it (measured, `experiments/iso5_substrate_dispatch/`):

| Test (inside the loop body, over ticks pc=0,1,2) | Expected | Measured |
|---|---|---|
| `acc + pc` (arithmetic on loop state) | 0+1+2 = 3 | **3** ✓ |
| final `pc` after loop | 3 | **3** ✓ |
| `acc + truth(pc == pc)` (state vs itself) | +3 | **+3** ✓ |
| `acc + truth(pc == 2)` (state vs **literal**) | -1 | **-3** ✗ |
| `acc + truth(pc >= 2)` (state vs literal) | -1 | **-2** (fuzzy) |
| `pc == 2` in straight-line code (pc a plain local) | +1 at pc=2 | **+1** ✓ |

**Conclusion:** a loop-carried state variable's *arithmetic* is exact and
`state == state` holds, but **comparing loop-carried state against a literal
constant does not defuzz correctly** — `pc == 2` reads false even when pc = 2, and
`pc >= 2` goes fuzzy at the boundary. The loop carries `pc` as a slot-rotated
substrate vector whose real component is exact but whose full vector differs from a
freshly-built literal, so equality/threshold dispatch against a literal misfires.
(The loop *condition* `pc < 3` works — it halts at 3 ticks — so the condition path is
handled differently from a body comparison.)

This is the precise substrate reason the WASM machine is hard: its core is **per-tick
opcode dispatch — compare the loop-carried `pc`/opcode against literal opcode values
each tick** — which is exactly the operation that misfires. It rhymes with the
option-match finding (an axon field read had to be bound to an `int` local before
`== 1` defuzzed correctly): equality dispatch on a non-freshly-constructed value is
fragile on the substrate.

### 5. Largest cleanly-running fragment

The machine's pure-arithmetic helper `to_signed` (no arrays, no dispatch) transpiles
and runs: `to_signed(100)` = **100.0** on the substrate.

## What this means for ISO-5

ISO-5 (the WASM machine in Sutra) is blocked on three substrate primitives —
**arrays**, **bitwise ops**, **exceptions** — and on a **loop-dispatch** issue
(literal-vs-loop-state comparison) that must be solved before a fetch-execute loop
can dispatch opcodes. The transpiler can lower the surface; the machine cannot *run*
until these land. Recorded as a negative result; the hand-edit resumes when those
primitives exist (or via a dispatch encoding that avoids literal comparison on loop
state — e.g. one-hot opcode masks carried as state).
