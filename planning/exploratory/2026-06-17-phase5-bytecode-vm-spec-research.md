# Phase 5 — bytecode / VM targets: verified-spec research (kickoff)

**Date:** 2026-06-17
**Status:** research / scoping (the directive's stated first step: "search for existing verified
bytecode specs — as was leveraged for WASM — before implementing"). No code yet; this grounds
the implementation order.
**Driver:** ACTIVE DIRECTIVE Phase 5 (Emma 2026-06-17: do this after the FV-paper cycles, before
the transpiler long-tail). The neural-VM legs — build a substrate program that interprets a VM's
bytecode so any language compiling to that bytecode runs on Sutra (the same shape as the
already-built Neural WebAssembly machine in `WASM/`).

## The three legs and what verified specs exist to leverage

**WASM — the proven leg, already built.** The substrate WASM machine (`WASM/` subtree,
Turing-complete, 21 opcodes, ISO-5; `test_mini_wasm_machine.py`) is the existence proof. WASM
*has* a formal small-step spec (the W3C standard + the mechanized WasmCert / Isabelle and Coq
models the original work leveraged). **Implication: WASM is the cheapest next bytecode progress —
extend the existing machine (remaining ISO-5 opcodes; the pruned-transformer oracle), not a new
VM from scratch.** This is also the leg Python rides (Pyodide/Wasm Python), per the dedicated
queue section.

**JVM — rich verified-spec landscape; the most leverageable NEW leg.** Mechanized formal
semantics of JVM bytecode exist and are mature:
- **Jinja / JinjaThreads** (Isabelle/HOL) — a unified, type-safe model of Java *source and
  bytecode*, with a verified compiler between them and a verified bytecode verifier in Kildall's
  style. The single most directly-usable artifact: an executable, machine-checked small-step
  bytecode semantics.
- **Bicolano** (Coq) — a formalization of the *full* JVM instruction set and its semantics,
  organized by how each instruction touches threads/stack/heap.
- **ACL2 JVM (Kestrel)** — a provably-correct-implementation line for the bytecode verifier.
Matches Emma's note (2026-06-14): "the JVM spec is the most useful single artifact — a formal
bytecode instruction set + type verifier + class-file format." **Implication: a Sutra JVM-bytecode
interpreter can be specified against Jinja's small-step rules (the same way the WASM machine was
specified against the WASM spec), opcode by opcode, each verified compile-AND-run on the
substrate.**

**CPython — NO formal verified spec; stays folded into WASM (do NOT build a direct VM).** Search
confirms there is no mechanized/verified CPython bytecode semantics. CPython's bytecode is defined
operationally by a DSL in `Python/bytecodes.c` (consumed by `Tools/cases_generator`) — a
semi-formal "interpreter definition," not a verification artifact — and it **drifts across Python
versions** (a known instability). This directly validates Emma's 2026-06-14 ruling: a standalone
CPython VM is a trap (nobody writes pure CPython bytecode; real code reaches for C extensions), so
**Python rides Pyodide/Wasm Python through the existing WASM leg**, not a bespoke CPython VM. If a
CPython-bytecode subset is ever attempted directly, **pin a specific CPython version** (the
bytecode is not stable across versions).

## Recommended Phase-5 implementation order (grounded by the above)

1. **WASM first** — extend the proven `WASM/` machine (remaining ISO-5 opcodes; the
   6-program byte-for-byte oracle). Cheapest substrate-verifiable progress; also unblocks Python
   via Pyodide. Concrete open items already live in the merged WASM queue section.
2. **JVM next** — specify a Sutra JVM-bytecode interpreter against **Jinja's** small-step
   semantics, opcode by opcode, each verified compile-AND-run on the substrate. Start with a
   minimal arithmetic/stack/branch core (the WASM-machine playbook), expand by opcode.
3. **Python = WASM + Pyodide** — no direct CPython VM. The standout research angle (Emma
   2026-06-14): physical-entropy NumPy — wire NumPy's RNG to the substrate's native sampling
   entropy once the WASM/thrml path is solid.
4. **JS** — a JS engine/bytecode target; weirdest of the four, scope TBD; lowest priority of the
   VM legs. (Distinct from the existing `sutra-from-ts` *transpiler*.)

## Licensing (verify before relying; recorded from Emma's 2026-06-14 chatbot grounding + this search)

- **JVM spec** — public document; **OpenJDK** is GPLv2+Classpath. Jinja/Bicolano are academic
  formalizations (check each project's license before vendoring any artifact).
- **CPython** — PSF license (BSD-style permissive).
- Per repo policy: do NOT vendor third-party spec PDFs; re-fetch from source each session.

## Sources

- JVM verified semantics: Jinja/JinjaThreads (Isabelle/HOL), Bicolano (Coq), Kestrel ACL2 JVM —
  see the Springer/IRIT/Kestrel/Leroy "Mechanized semantics" references found 2026-06-17.
- CPython bytecode DSL: `python/cpython` `Python/bytecodes.c` + `Tools/cases_generator/
  interpreter_definition.md`; `InternalDocs/interpreter.md`.
