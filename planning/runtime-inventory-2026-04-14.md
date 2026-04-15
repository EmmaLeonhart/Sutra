# Runtime inventory — 2026-04-14

Snapshot of what exists today vs. what `claw4s-scope.md` requires by Apr 20. Taken at the top of the queue rebuild; the gap list drives queue items 2–5.

## What exists

### Pipeline

`sdk/sutra-compiler/sutra_compiler/`
- `lexer.py` → `parser.py` → `validator.py` → `codegen_flybrain.py`
- Entry point: `python -m sutra_compiler --emit-flybrain file.su`
- Backend: emits **Python source code** targeting a `_FixedFrameFlyBrainVSA` class. The emitted Python imports `fly-brain/vsa_operations.py` + `fly-brain/spike_vsa_bridge.py` + `fly-brain/mushroom_body_model.py`.

### What the emitted Python actually runs on

- `bind`: `a * sign(b)` → numpy elementwise
- `bundle`: PN currents summed → numpy (or Brian2 EPSPs in fidelity mode)
- `similarity`: cosine → numpy
- `snap`: encode hypervector → run MB spiking circuit (Brian2, 300ms, APL feedback) → decode via learned linear MBON readout (ridge regression, 20 random training samples)

So: **VSA ops are numpy on CPU.** `snap` optionally goes through a Brian2 spiking simulator for fidelity. Neither is GPU. No GPU code path exists.

### End-to-end status of existing .su files

Compiles + test-harness-runs:
- `examples/workspace/corpus/main.su` — trivial (3 basis vectors + return)
- `examples/workspace/similarity/main.su` — trivial (basis_vector + similarity)
- `fly-brain/fuzzy_conditional.su` — 4 prototype table, 4 program variants, 4 inputs each → 16 decisions. `fly-brain/test_codegen_e2e_fuzzy.py` compiles it, execs the generated module, verifies all 16 outputs match a hardcoded expected table. In-process only, no captured output on disk.
- `fly-brain/geometric_loop.su` — rotation + prototype snap (loop body incomplete)

Compiles stub-fails (CodegenNotSupported):
- `examples/01-objects-and-methods.su` — method decl
- `examples/02-functions-vs-methods.su` — method decl
- `examples/03-types-and-casts.su` — `EmbedExpr`
- `examples/04-control-flow-and-errors.su` — `DefuzzyExpr`
- `examples/05-operators-and-strings.su` — operator decl
- `examples/06-executable-file.su` — `EmbedExpr`

### No existing CLI runner

`python -m sutra_compiler` **emits** Python to stdout/file; it does not exec. No single command takes `.su` → output. `test_codegen_e2e_fuzzy.py` does (compile + exec + compare) but it's a pytest, not a runner.

## Gap to claw4s-scope "two examples end-to-end"

1. **No CLI runner.** `sutra run file.su` doesn't exist. Must write a wrapper that emits Python to a temp file, execs it, captures stdout/return value.
2. **No committed expected output.** `fuzzy_conditional.su` has expected values hardcoded inside the test, not as a golden file next to the `.su`.
3. **Only one non-trivial example.** `fuzzy_conditional.su` is the one honest candidate today. Corpus/similarity are trivial. Need a second non-trivial `.su`.
4. **Codegen gaps.** If example 2 uses `EmbedExpr` or `DefuzzyExpr`, those need lowering. Method decls / operator decls / `UnsafeCastExpr` are out of scope — the chosen examples will route around them.
5. **Substrate honesty.** claw4s-scope says "executes as matrix operations on standard hardware." The numpy path satisfies this. The Brian2 path does **not** — it's a spiking simulator, not matrix ops. Paper must either (a) run examples through the pure-numpy code path and note Brian2 as a fidelity alternative, or (b) state clearly that `snap` goes through a spiking simulator in the demo. Option (a) is cleaner for the submission.

## Decisions driving queue items 2–5

- **Example 1 = `fuzzy_conditional.su`.** Already compiles, already has a reference output embedded in a test, non-trivial (fuzzy branching without control flow). Need to: extract expected output into a committed golden file, run via the new CLI.
- **Example 2 = TBD, to be written fresh.** Must exercise something `fuzzy_conditional` doesn't — candidates: (i) `loop(condition)` eigenrotation with data-dependent termination, (ii) a bind/unbind role-value round-trip, (iii) a bundle+cleanup fixed-point that isn't just classification. Pick whichever is both honest (works today or needs only small codegen work) and distinct from example 1.
- **Codegen work:** lower `EmbedExpr` and `DefuzzyExpr` iff example 2 needs them. Not otherwise.
- **Substrate claim in paper:** "VSA operations execute as numpy matrix operations on CPU; the same code path is GPU-trivial under PyTorch/JAX substitution (not demonstrated in this submission). A Brian2 spiking-substrate alternative exists for `snap` and is characterized in companion work; it is not the execution path for the demonstrations in this paper."

## Hard-stop check (per claw4s-scope)

If by end of Apr 17 one example isn't executing end-to-end from CLI, drop the submission. Fellows Apr 26 > late/broken Claw4S.
