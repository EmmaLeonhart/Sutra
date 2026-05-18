# 2026-05-17 — Implicit tail-recursive loop desugar: `loop(expr){body}` works

**What.** The bare `loop(expr){ body }` form (Emma's invented
implicit-tail-recursion sugar) — previously *parsed-but-rejected*
(`CodegenNotSupported`) — now compiles and runs correctly on both
backends. It desugars, before codegen, into the existing
tail-recursive loop-function machinery.

**The model (Emma's, verified correct).** The loop's **implicit
axon** = the variables the body mutates, plus the loop bound's free
variables (threaded invariant). `loop(x){ n1=n1+1; n2=n2+2; }`
becomes a synthesized `iterative_loop` loop-function over state
`(n1, n2, x)` with `pass n1, n2, replace` (x invariant), called
with x as the count.

**How (the build, units, all gated + pushed).**
- `loop_capture.captured_state(body)` — body-mutated names minus
  body-declared names, first-mutation order (unit 1, `b1fabdb6`).
- `loop_capture.free_identifiers(expr)` — the bound's value-position
  identifiers, Call callees excluded (step 3a, `9fb05a8e`).
- `loop_desugar.desugar_implicit_loops(module)` — for each
  `LoopStmt` with `count is None`: compute `mutated + bound`,
  **flip each captured/bound var's `VarDecl` to `is_slot=True`**,
  synthesize an `iterative_loop` `LoopFunctionDecl` (+ `PassStmt`:
  new values for mutated, `ReplaceMarker` for invariant bound) and
  a `LoopCallStmt`, insert the decl into `module.items` before the
  caller. Wired into both `translate_module`s after
  `desugar_promises`, before `inline_stdlib_calls`.

**Why the slot-flip is correct, not a hack.** Slot storage is
transparently routed by the *existing* codegen everywhere — reads
(`codegen_base.py:2620-2624`), writes (`:1937-1945`), decl
(`:800-819`), loop-call thread (`:1628-1664`). Flipping the
*declaration* makes every use of that var consistent by
construction. Inside the emitted loop function `_slot_vars` is
reset (`:1081`) so the state params are plain locals there, and the
`iterative_loop` count expression (`:1422`, e.g. bare `x`) resolves
to the in-scope state local — which is exactly why the bound's free
vars MUST be threaded as state. The earlier plan to register slots
at the codegen reject site was found to MISCOMPILE (the var was
already emitted as a plain local) and was rejected before any code.

**Ground truth (measured, both backends).** `loop(x){i=i+1}` x=5 →
5; `loop(x){n1+=1;n2+=2}` x=5 → 15; literal `loop(3){s=s+1}` → 3
(untouched — `count != None` dispatches to the compile-time unroll
before the pass). Gate: `test_implicit_loop_desugar` (8) +
`test_loop_capture` (11) + branchless_loop + loop_function_decl +
codegen + parser + corpus = 186 passed / 83 subtests, exit 0;
codegen_pytorch + inliner + transcendentals 38 passed / 33
subtests; `examples/_smoke_test.py` PASS. No regression anywhere.

**Frank scope — what is NOT done (tracked, not faked):**
- Only the **count / `iterative_loop`** form (Emma's examples). A
  boolean-condition `loop(cond){body}` → `while_loop` is the next
  kind.
- **Top-level `FunctionDecl` bodies + nested blocks within them.**
  Class-method bodies are a follow-on.
- A captured/bound name must be a locally-declared `VarDecl` with
  an explicit type; a parameter-captured or `var`-inferred name
  raises a clear `CodegenNotSupported` (fail-safe — verified by
  test, never a miscompile). Scope-shadowing uses first-decl-wins
  (no scope analysis yet).
- **await-as-minimal-instance (#3)** — Emma's "await is a loop with
  a 1-slot axon + flag" — is the next unit on top of this; not
  attempted here.

This is a real, gated win on a control-flow-wide change. The tag
`v0.5.0` (`84b5ca45`) is the revert point if a later issue surfaces.
