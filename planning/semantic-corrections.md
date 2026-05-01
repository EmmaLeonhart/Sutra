# Pinned semantic corrections

Load-bearing reminders that have been dropped/forgotten across sessions.
Re-read when working on the compiler, runtime, or spec.

1. **`loop(N)` literal N unrolls at compile time. Zero runtime
   iteration.** The four function-declaration loop kinds (`do_while`,
   `while_loop`, `iterative_loop`, `foreach_loop`) are the runtime
   data-dependent forms.
2. **No loop counters live on the host at runtime.** The "counter"
   for substrate iteration IS the soft-mask cumulative halt in a
   fixed-T tensor-op unroll. The `for _t in range(50)` in the
   emitted Python is meta-iteration, not a runtime counter — the
   substrate sees T inline cell evaluations regardless.
3. **Rotation runs in the synthetic subspace, not on connectome
   weights.** Real FlyWire weight matrices do not function as
   rotation operators (they're compressive projections). Synthetic
   Givens rotations on the dedicated subspace are what the language
   compiles to today.
4. **Semantic roles are learned matrices; semantic `bind` is
   `R @ filler`.** Not random vectors (HRR), not sign-flip. A
   *semantic* role is a matrix fit to the substrate.
   See `planning/sutra-spec/binding.md` §"Semantic binding".
   **Implementation status: deferred.**
5. **Sutra has two binding kinds: semantic (learned-matrix) and
   rotation.** Rotation binding works today; semantic binding is
   deferred.
6. **Sign-flip binding is retired** (from the codegen as of
   2026-04-22). Rotation is the current `bind` implementation.
7. **Truth is designed as a canonical axis in the synthetic
   subspace.** `synthetic[AXIS_TRUTH=2]`.
8. **PyTorch is the compiler's runtime target.** `codegen_pytorch.py`
   emits torch modules picking CUDA at module init. The numpy
   backend (`codegen.py`) is deprecated.
9. **Defuzzification polarizes, never binarizes.** `is_true` and
   `defuzzify` keep the result fuzzy and differentiable. No commit
   primitive exists; `select` does all branching. Don't reintroduce
   `gate`.
10. **`bool` is a subclass of `fuzzy`, not crisp.**
11. **Sutra's "arrays" are binding-based, not heap-allocated.** A
    binding-array is a substrate vector with `arr[0] = length` and
    `arr[1..length] = elements`. Built on `array_from_literal` /
    `array_length` / `array_get` runtime methods.
12. **Canonical synthetic axis allocation:** `synthetic[0]=AXIS_REAL`,
    `[1]=AXIS_IMAG`, `[2]=AXIS_TRUTH`, `[3]=AXIS_CHAR_FLAG`,
    `[4]=AXIS_LOOP_DONE`, `[5+]=SLOT_BASE` (47 disjoint 2D Givens
    slots at default `synthetic_dim=100`).
13. **Loops are first-class declared functions.**
    `<kind> NAME(condition_or_array_or_count, type state, ...) { body; pass values; }`.
    Body uses `pass <exprs>` OR `return NAME(args)` (tail-recursive
    yield, one value per state param; `replace` keyword keeps an
    input value in the `pass` form). Call site is `loop NAME(...)`
    and mutates caller variables by reference. Loop functions have
    NO outer-scope access — pure functions over their declared
    parameters only. The four kinds: `do_while` (body runs once +
    while-style continuation), `while_loop` (body skipped if cond
    false at start), `iterative_loop` (runs N times; body sees
    `iterator` keyword), `foreach_loop` (walks binding-array; body
    sees `element` keyword). Substrate execution: T fixed cell
    steps with soft-halt sigmoid + monotone cumulative + soft-mux
    freeze. AXIS_LOOP_DONE marks completion.
14. **Idiomatic-loop cleanup is queued for later.** Today's
    by-reference call shape is acknowledged non-idiomatic; the
    cleanup direction (return tuples, no by-ref mutation) is in
    `todo.md` § "Make loops idiomatic." Don't touch the design
    until a few real programs have exercised the by-ref form.
15. **SutraDB is the embedded codebook.** Every embedded string in
    a Sutra program goes into SutraDB at compile time via
    `_VSA.populate_sutradb()`. `_VSA.nearest_string(query)` decodes
    any vector back to the nearest string label. `SUTRA_DB_PATH`
    env var configures persistent .sdb across runs. Build prereq:
    `cd sutraDB && cargo build --release -p sutra-ffi`.
16. **Rotation cache is pre-warmed at compile time.** Every
    codebook entry gets its rotation matrix computed in
    `_VSA.prewarm_rotation_cache()` at module init, after
    embed_batch + populate_sutradb. The runtime never pays QR cost
    on the hot path.
