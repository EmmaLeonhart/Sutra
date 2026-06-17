# Phase 5 — JVM bytecode core on the substrate: scoping

**Date:** 2026-06-17
**Status:** scoping / spec (the second Phase-5 leg per
`2026-06-17-phase5-bytecode-vm-spec-research.md`; the WASM leg — the mini RAM-state machine — is
underway and reached 28 opcodes). No code yet; this decomposes the JVM leg into bounded,
substrate-verifiable steps so the implementation isn't started without a plan.

## The key reuse: the mini WASM machine IS the template

`experiments/iso5_substrate_dispatch/mini_wasm_machine.su` is already a **generic RAM-state stack
machine**: state (pc, sp, halted, operand stack, data) lives in the host RAM device
(`ramRead`/`ramWrite`); the host drives one `step()` per instruction (autoregressive); opcode
dispatch is `truth_axis(defuzzy(op == N))`; side effects are blended writes to fixed cells. The
JVM is *also* a stack machine (operand stack + locals + a flat bytecode array). So the JVM core
is **not a new execution model** — it is the same blended-dispatch RAM-state machine with (a)
JVM opcode numbers/semantics, (b) a `locals` region in RAM, (c) the JVM bytecode layout. Build it
as a parallel `.su` (`jvm_core.su`) mirroring `mini_wasm_machine.su`'s structure, not from scratch.

## Reference (verified spec to check against)

Jinja / JinjaThreads (Isabelle/HOL) gives a machine-checked small-step semantics for a JVM-bytecode
subset (operand stack, locals, the arithmetic/stack/branch instructions) plus a verified
source→bytecode compiler. Each Sutra opcode's effect is specified to match Jinja's transition rule
for that instruction — the same way the WASM machine was specified against the WASM small-step
spec. (Bicolano (Coq) is the fuller-instruction-set alternative if needed later.)

## Scope of the MINIMAL core (deliberately excludes the heavy JVM machinery)

- **No constant pool, no class file, no object model, no method resolution.** The minimal core is
  a single method's bytecode as a flat array of int opcodes in RAM, an operand stack, and a locals
  array — exactly the WASM-machine shape. (The class-file/constant-pool front is a later leg; like
  Python-via-Pyodide, it's not the verification-relevant part.)
- **No `idiv`/`irem`** — division/modulo are excluded (the `Math.mod` ban; same as the WASM leg).
- Integers only (the `i*` instruction family); no longs/floats/refs in the minimal core.

## Bounded, substrate-verified steps (each a compile-AND-run increment, Jinja-checked)

Use the **real JVM opcode values** so eventual `javac` output could run unmodified (and so the
semantics match Jinja exactly). Key minimal-core opcodes (decimal):
`iconst_0..5` = 3..8, `bipush` = 16, `iload_0..3` = 26..29, `istore_0..3` = 59..62,
`iadd` = 96, `isub` = 100, `imul` = 104, `ineg` = 116, `dup` = 89, `pop` = 87, `swap` = 95,
`if_icmpeq` = 159 / `if_icmpne` = 160 / `goto` = 167, `ireturn` = 172.

1. **Arithmetic core** — `bipush`/`iconst_N` (push), `iadd`/`isub`/`imul`, `ineg`, `ireturn`.
   The exact WASM-machine pattern with JVM opcode numbers + the JVM 2-slot-ish layout (bipush
   takes a 1-byte operand). Verify e.g. `bipush 3; bipush 4; iadd; ireturn` → 7 on the substrate.
2. **Locals** — `iload_N`/`istore_N` against a `locals` RAM region (the WASM LOAD/STORE shape,
   fixed local slots). Verify `bipush 5; istore_0; iload_0; iload_0; iadd; ireturn` → 10.
3. **Stack ops** — `dup`/`pop`/`swap` (the WASM DUP/DROP/SWAP analogs, identical chains).
4. **Branches** — `if_icmpeq`/`if_icmpne`/`goto` (the WASM BR_IF analog; relative offsets per the
   JVM, vs the WASM machine's absolute target — the one real encoding difference to handle).
5. **A real method end-to-end** — e.g. an iterative factorial compiled from a tiny Java method by
   `javac` (or hand-assembled), run byte-for-byte, decoded == reference. (Mirrors the WASM leg's
   oracle goal.) Locals + branch + arithmetic together → Turing-complete on the JVM subset.

## Open design points (resolve when each step is built, not now)

- **Branch offsets:** JVM branches are 2-byte signed RELATIVE offsets; the WASM mini-machine used
  an absolute target. Decide: relative `pc += offset` (faithful) vs absolute (simpler). Lean
  faithful (relative) so real bytecode runs.
- **bipush operand sign:** `bipush` takes a signed byte; the substrate negate is verified
  (2026-06-17), so signed immediates are fine.
- **Same-machine vs separate `.su`:** a separate `jvm_core.su` is cleaner than overloading the WASM
  machine (different opcode numbers/encodings); shared structure is copied, not abstracted, to keep
  each machine a self-contained substrate artifact.

## Why this ordering

WASM is the proven leg (extend it for breadth + Python-via-Pyodide). JVM is the highest-value NEW
leg because it has a mature verified spec (Jinja) to specify against and the largest compile-to-it
language ecosystem. The minimal arithmetic→locals→stack→branch→real-method ladder mirrors exactly
how the WASM machine was grown, so each step is a known-shape, substrate-verified increment.
