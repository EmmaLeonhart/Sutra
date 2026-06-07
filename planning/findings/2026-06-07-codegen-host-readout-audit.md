# Codegen host-readout audit — every `.item()`/`float(tensor)` leak in the runtime

**Date:** 2026-06-07
**Why:** Emma's directive — Sutra has no readout/log/monitor/debug by design;
remove it. This is the inventory of every host-readout the PyTorch codegen emits
(`sdk/sutra-compiler/sutra_compiler/codegen_pytorch.py`). Each is a point where a
value crosses from the GPU tensor world to a host Python scalar — breaking
substrate-purity AND detaching the autograd graph (a gradient wall, which is why
"the program is one differentiable neural network" is not currently true).

33 `.item()`/`float(tensor)` occurrences. Categorized:

## A. Pure accessors — REMOVE (Emma's direct target)
All are `return float(v[...axis...].item())`:
- `real` (1867), `imag` (1872), `truth` (1877)
- `component` (1832), `semantic` (1846), `synthetic` (1860)
- `norm` (1801) — `float(torch.linalg.norm(v))`

These exist only to hand a host scalar back. No operation may use them. Remove
from runtime + parser/codegen surface. All `.su` and transpiler output that calls
them must be reworked (scope grep: 17 in mini_wasm_machine, 1 in math.su, 3 in GUI
demos, and the C/OCaml/TS transpilers EMIT them — see §E).

## B. Control-flow readouts — rework to substrate
- `isFulfilled` (841) / `isRejected` (847) — `float(promise flag)`. Await/promise
  control reads the flag to the host. Needs substrate-native promise resolution.
- `array_length` (1160) — `int(arr[0].item())`. Array length to host int.

## C. RAM address decode — the "I/O wire" (DECISION NEEDED)
- `ram_read` (1902) / `ram_write` (1921) — `int(round(ptr[AXIS_REAL].item()))` to
  index the host RAM list. Emma's earlier `ram-pointers` finding framed address
  decode as the legitimate I/O boundary. But it IS a host readout. Decision: is
  the device-address decode an allowed boundary (I/O wire) or must addressing also
  be substrate (content-addressable memory, no host index)?

## D. JS-interop carve-out — host-crossing BY DESIGN (DECISION NEEDED)
CLAUDE.md has an explicit carve-out for JS-compat shims. These cross to host to
mimic JavaScript semantics:
- `is_char` (2116) / `is_string` (2192) — `bool(flag.item() >= 0.5)` dispatch.
- `js_strict_eq` (2304) `float(norm)`, `js_strict_neq` (2318) / `js_loose_neq`
  (2359) `-float(eq[...].item())`.
- `_js_str_cmp` (2382-2388) — multiple `int(...item())`.
- `string_to_python` (2564-2569) — `int(...item())`, explicitly "AT the terminal
  boundary" (converting a String to a Python str for program output).
Decision: does "no introspection" override the JS carve-out, or is JS-interop a
separately ring-fenced impurity (it inherently needs host values to match JS)?

## E. Transpiler-emitted `.real()` — the breach is GENERATED
The C / OCaml / TS → Sutra transpilers emit `.real()` in their output (visible in
every `*/tests/fixtures/*/expected.su`). So every program they lower inherits the
breach. Removing the accessors requires changing what the three transpilers emit.

## Already-clean (the right pattern exists)
`_e_real` (1354), `defuzzify_trit` (2584), `digit_array_add` (2661), `eq` (2773,
scatters cos into the truth axis, no `.item()`), `eq_synthetic`/`gt` (numeric
comparison, tensor-only). These prove substrate-pure ops are achievable — and that
the leak was piecemeal discipline, not a hard rule.

## The fix is enforcement, not one-off deletion
1. Remove §A accessors (runtime + surface) and rework all consumers + the 3
   transpilers' emitted output.
2. Resolve §C (I/O wire) and §D (JS carve-out) with Emma — these are design calls,
   not obvious deletes.
3. Rework §B to substrate-native control.
4. **CI grep-gate**: fail the build on any new `.item()` / `float(<tensor>)` inside
   an operation. Without enforcement the leaks return (a prior audit blessed them).
5. Open question this forces: substrate-to-substrate VERIFICATION — tests cannot
   `.real()` a result. How does a no-readout language get verified? (Compare output
   vector to expected vector via a substrate op; the pass/fail boundary is the one
   unavoidable terminal readout — or it isn't, and that needs design.)

## Honest status of the compilation target
The core ops are real torch tensor ops on CUDA (measured: vector +/*,
eq_synthetic, gt, bind/bundle). But a compiled program is **host-Python-orchestrated
sequential torch calls**, not one fused graph, and the §A–D readouts sever the
autograd graph. "Sutra compiles to one differentiable neural network" is therefore
aspirational today; purging readout is the precondition for it to become true, and
fusing the orchestration into one graph (trace/`torch.compile`) is a second,
separate step.
