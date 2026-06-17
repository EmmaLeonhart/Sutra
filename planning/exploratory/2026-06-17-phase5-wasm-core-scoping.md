# Phase 5 — real WebAssembly bytecode core on the substrate: scoping

**Date:** 2026-06-17
**Status:** scoping / spec. WebAssembly is now THE VM direction (Emma 2026-06-17 — JVM done +
parked; see `project_jvm_parked_wasm_is_the_vm_direction` memory and DEVLOG). The existing
`mini_wasm_machine.su` is a CUSTOM-opcode stack machine (op 1 = const, 2 = add, …) — a breadth
playground, not real `.wasm`. This doc scopes a **real-WASM-bytecode** core (`wasm_core.su`,
parallel to `jvm_core.su`) that uses REAL WebAssembly opcode values + encoding, so eventual
`wat→wasm` output runs unmodified. No code yet; this decomposes the leg into bounded,
substrate-verifiable steps before building, exactly as the JVM scoping doc did
(`2026-06-17-phase5-jvm-core-scoping.md`).

## The key reuse: the JVM core IS the template

`jvm_core.su` is a generic RAM-state blended-dispatch DNC stack machine: state (pc, sp, operand
stack, locals) lives in the RAM device as vectors carried across recurrent `step()` calls; dispatch
is `truth_axis(defuzzy(op == N))`; side effects are blended writes to fixed cells; the only host
readout is hard address-decode. WASM is also a stack machine (operand stack + locals + a flat
function-body bytecode array). So `wasm_core.su` is **not a new execution model** — it is the same
machine with (a) real WASM opcode numbers, (b) the WASM operand encoding, (c) WASM's structured
control flow. Copy `jvm_core.su`'s structure; do not abstract (each machine stays a self-contained
substrate artifact, per the JVM scoping doc's rationale).

## What we deliberately EXCLUDE from the minimal core

- **No binary module parse.** No magic number, no `type`/`function`/`export` sections, no LEB128
  section sizes. The minimal core loads a single function's **body bytecode** as a flat byte array
  in RAM — exactly as `jvm_core.su` loaded just the method's Code, not the class file. (Module-format
  parsing is host-side and not verification-relevant — same call as "ride Pyodide, don't build a
  CPython VM.")
- **No `i32.div_s`/`i32.rem_s`** — division/modulo excluded (the `Math.mod` ban; same as JVM/the
  custom machine).
- **i32 only.** No i64/f32/f64/v128, no memory load/store ops, no tables in the minimal core.

## Reference (verified spec to check against)

The official W3C WebAssembly spec gives a formal small-step reduction semantics for the whole
instruction set, and there are mechanized versions (WasmCert-Isabelle / the spec's reference
interpreter) — the same kind of machine-checked oracle the JVM leg used (Jinja). Each `wasm_core.su`
opcode's effect is specified to match the WASM spec's reduction rule for that instruction.

## Real WASM opcodes for the minimal core (hex / decimal)

```
i32.const   0x41 / 65   (operand: signed LEB128)
local.get   0x20 / 32   (operand: unsigned LEB128 local index)
local.set   0x21 / 33   (operand: unsigned LEB128 local index)
local.tee   0x22 / 34   (like local.set but leaves the value on the stack)
i32.add     0x6a / 106     i32.sub  0x6b / 107     i32.mul  0x6c / 108
i32.eqz     0x45 / 69
i32.eq      0x46 / 70      i32.ne   0x47 / 71
i32.lt_s    0x48 / 72      i32.gt_s 0x4a / 74
i32.le_s    0x4c / 76      i32.ge_s 0x4e / 78
block       0x02 / 2       loop     0x03 / 3       if   0x04 / 4    (each + a blocktype byte)
br          0x0c / 12      br_if    0x0d / 13       (operand: unsigned LEB128 label index)
else        0x05 / 5       end      0x0b / 11
return      0x0f / 15      call     0x10 / 16       (operand: unsigned LEB128 func index)
```

## The TWO real encoding differences from JVM (the whole substance of this leg)

1. **LEB128 variable-length integer operands.** WASM immediates (`i32.const` value, local/label/
   func indices) are LEB128, not fixed-width. For the minimal core, handle the **single-byte** case
   first: a byte `b < 0x80` is a complete LEB128. Unsigned value = `b`. Signed value = `b − 128·sign`
   where `sign = 1 − ((2·b) < 127)` — the SAME even/odd clean-comparison trick the JVM branch-offset
   sign-extension used (`2b` even, `127` odd → never equal → no equality-boundary case, no gate).
   Single-byte covers values in `[−64, 63]` (signed) / `[0, 127]` (unsigned), enough for small
   constants and low indices (iterative factorial fits). **Multi-byte LEB128 (continuation bit
   0x80) is a later step** — it makes operand length data-dependent, which complicates pc
   advancement; defer it.

2. **Structured control flow instead of goto-offsets.** WASM has no arbitrary jumps. `block`/`loop`/
   `if` open a region terminated by `end`; `br k` / `br_if k` target the `k`-th enclosing label
   (for a `block`, the label is its `end`; for a `loop`, the label is the `loop` *header* — so `br`
   to a loop = backward jump = iteration). This is the part tree recursion (queue Phase 5.5-B)
   relies on. Two implementable strategies:
   - **(pre-resolved target table, RECOMMENDED first):** at load time (host-side, compile-time —
     allowed, it's not runtime substrate work) scan the body once and precompute, for every `br`/
     `br_if`/`block`/`loop`/`if`/`end`, the absolute target pc, storing the table in RAM. Then the
     substrate `step()` does the SAME thing the JVM machine did — a (possibly conditional) jump to a
     resolved absolute/relative target — and the structured-control complexity stays at the
     boundary, not on the hot path. This keeps step (3) below close to the JVM branch step.
   - **(runtime label stack):** maintain a label-depth stack in RAM and pop `k+1` frames on `br k`.
     More faithful but more substrate machinery; defer unless the pre-resolved table proves
     insufficient.

## Bounded, substrate-verified steps (each a compile-AND-run increment, spec-checked)

1. **Arithmetic + locals + single-byte LEB128.** `i32.const` (signed single-byte LEB128),
   `local.get`/`local.set`/`local.tee` (unsigned single-byte LEB128 index), `i32.add`/`sub`/`mul`,
   `end`, `return`. Mirror `jvm_core.su` step 1–2a with WASM opcodes + the LEB128 decode. Verify a
   hand-assembled body, e.g. `(i32.const 3)(i32.const 4)(i32.add)(end)` → 7 on the substrate.
   (NOTE: reuse the JVM iconst fix — push constants as real-axis vectors `N·one`, never bare
   scalars; the literal-broadcast finding `2026-06-17-iconst-literal-broadcast-breaks-equality.md`
   applies identically here.)
2. **Comparisons.** `i32.eqz`, `i32.eq`/`ne`/`lt_s`/`gt_s`/`le_s`/`ge_s` — copies of the JVM
   `v_eq`/`v_lt`/`v_gt`/`v_ge`/`v_le` gated idiom (boundary-correct).
3. **Structured control (pre-resolved targets).** `block`/`loop`/`if`/`else`/`end` + `br`/`br_if`
   with the load-time target table. Verify a `loop`+`br_if` countdown-sum (the WASM analog of the
   JVM countdown loop) on the substrate.
4. **A real `wat→wasm` function body byte-for-byte.** Compile a tiny iterative factorial from `.wat`
   with `wasm-tools`/`wat2wasm`, extract the function body bytes, load them, decode == reference
   (the JVM-factorial oracle, in WASM). `fact(0..5) = 1,1,2,6,24,120`.
5. **(Phase 5.5-B) tree recursion via WASM.** `call` (and a call-frame stack in RAM) so a
   tree-recursive `fib` lowers to WASM and runs on the substrate machine — the queue Phase 5.5-B
   payoff (the stack the tree recursion needs lives in RAM/DNC memory, not a host stack).

## Open design points (resolve when each step is built, not now)

- **Multi-byte LEB128.** Single-byte first; multi-byte makes operand length data-dependent (pc
  advancement must count continuation bytes). Decide the substrate decode (a small fixed-max-length
  unrolled loop reading continuation bits) when a fixture needs a constant/index > 127.
- **Structured control: pre-resolved table vs runtime label stack.** Lean pre-resolved table first
  (keeps the hot path JVM-shaped); escalate to a runtime label stack only if needed (e.g. for
  `call`/return frames in step 5).
- **`blocktype` byte.** `block`/`loop`/`if` carry a blocktype (0x40 = empty, or a value type). The
  minimal i32 core can treat it as a 1-byte operand to skip (validation is host-side).
- **Where the body bytes come from.** Like JVM (`javac` + `javap`), use a real toolchain
  (`wat2wasm` / `wasm-tools`) to get authentic bytes; check the tool is available, else hand-assemble
  exact spec-layout bytes (the JVM leg confirmed Temurin `javac` is present; verify `wabt`/
  `wasm-tools` before relying on it).

## Why this ordering

WASM is THE direction (Emma). The minimal arithmetic→comparisons→control→real-function→tree-recursion
ladder mirrors exactly how the JVM core was grown — each step a known-shape, substrate-verified
increment — and step 5 is the concrete enabler for the recursion-lowering strategy's hard half
(queue Phase 5.5-B: multiple/tree recursion represented as WebAssembly).
