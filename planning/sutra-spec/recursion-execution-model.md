# Recursion execution model

**Status:** design settled (Emma 2026-06-17), partially implemented. This is the philosophy of how
Sutra runs recursion — distilled from the reference chat *"Converting single recursion to tail
recursion"* (`references/Converting single recursion to tail recursion - Claude.html`). It refines
and supersedes the earlier two-bucket framing in `queue.md` Phase 5.5 (single→tail, multiple→WASM):
multiple recursion is NOT uniformly routed to WebAssembly — most of it stays native via
pre-evaluation or memoization, and WASM shrinks to a small, principled fallback.

## The core claim

The overwhelming majority of "scary" recursion is **single (linear) recursion**, and single
recursion can **always** be converted to tail recursion (and from there to a loop). The
transformation carries the "work still to do" as an accumulator parameter instead of leaving it on
the call stack:

```
factorial(n)         = n * factorial(n-1)          -- non-tail: multiply AFTER the call returns
factorial(n, acc=1)  = if n==0 then acc else factorial(n-1, n*acc)   -- tail: accumulator carries it
```

Only **multiple recursion** (two+ recursive calls whose results are combined — Fibonacci, tree
traversal, merge sort) genuinely branches, and that branching has to live somewhere. Multiple
recursion is **relatively rare** in everyday programming. So: make the common case (linear) free,
which makes the rare case (branching) visible.

## Sutra's framing

Sutra is, in practice, an **instruction-set architecture for functional languages** — most users
will write Haskell/etc. that compiles *to* Sutra, not Sutra directly. Sutra's whole model is a
function from input to output (or a **stateful recurrent loop** where previous outputs feed back as
inputs — time-series). Even a "no external input" program (a Fibonacci-sequence emitter) has an
input: its own starting state. *The state is the input.* This is not a violation of the model — it
is the model working correctly, and it is what makes the recurrent-loop substrate the natural home
for recursion.

The load-bearing property: **referential transparency** (no side effects). A pure function *is* its
input→output mapping, so (a) the compiler may evaluate it at compile time when inputs are known, and
(b) its results may be cached without ever being wrong. Both pre-evaluation and memoization are
therefore **universally safe and automatic** — no annotations, no programmer burden. In an impure
language neither is safe; in Sutra both are free.

## The execution hierarchy (five tiers)

In order of preference — each tier is more general and more expensive than the one above:

1. **Tail recursion / loops → recurrent neurons (the native fast path).** All loops ARE tail
   recursion; an imperative-style loop compiles to tail recursion. Tail recursion lowers to a
   substrate `loop` (`state ← R·state`) on recurrent neurons — constant stack space, stays a real
   fused/differentiable graph. *(Status: this is Sutra's existing looping mechanism.)*

2. **Single (linear) non-tail recursion → tail recursion (compiler transform).** The compiler
   rewrites a single non-tail recursive call into accumulator-passing tail form, which then lowers
   as tier 1. Applies in every frontend's lowering pass. *(Status: the OCaml reference frontend has
   a foldable-CPS transform; generalizing it across frontends is queue Phase 5.5-A.)*

3. **Fixed-depth / statically-known-depth multiple recursion → compile-time pre-evaluation.** If the
   recursion's depth is known at compile time, the compiler unrolls / partially-evaluates it to
   straight-line code — no runtime cost. Referential transparency makes running the function at
   compile time safe. Same machinery as loop unrolling (which Sutra is already good at). A
   **maximum pre-evaluation depth** caps this; the default should be **empirically tested** and live
   as a **compilation argument** (always present in the project `.toml`, the IDE may auto-fill it).
   *(Status: not yet implemented; "leverages existing loop optimization", expected tractable.)*

4. **Dynamic multiple recursion (pure) → automatic memoization (stays native).** When the depth
   isn't static, memoize. Because functions are pure, the compiler memoizes **everything** by
   default — it's the execution environment, not an opt-in. Crucially, the memo store is **not a
   stack**: it is a **lazy lookup table / DAG** that grows as the computation progresses. The tree
   of recursive calls flattens into a DAG — nodes that would be recomputed instead point back to
   already-computed results (naive Fibonacci's exponential blowup becomes linear, automatically).
   The memo table is implemented via **recurrent neurons** and is itself just *a value* — pure data
   that accumulates over time, which fits Sutra's stateful-program-as-time-series model exactly (the
   memo table is the state, growing as new inputs arrive). For genuinely non-overlapping tree
   recursion, memoization doesn't improve complexity but still keeps the computation **native**
   (no jump to WASM). *(Status: not yet implemented; Sutra has no memoization yet but "very much
   can have this".)*

5. **Genuinely imperative / `eval` / no functional representation → Neural WebAssembly fallback.**
   The universal fallback — "almost every language can go into WebAssembly." Once tiers 3–4 absorb
   most multiple recursion, WASM stops being "the fallback for multiple recursion" and becomes the
   fallback for things that are **conceptually imperative** (or dynamic `eval`). This makes the
   Sutra↔WASM boundary a **semantic boundary, not just a performance boundary** — you jump to WASM
   when the computation is fundamentally imperative, not merely when it's hard to optimize. A much
   smaller, more principled category. *(Status: the real-WASM-bytecode core
   `experiments/iso5_substrate_dispatch/wasm_core.su` is COMPLETE — it runs real WASM byte-for-byte
   incl. recursive `fib` with its call stack in RAM; see DEVLOG 2026-06-17. This is the tier-5
   substrate. Tiers 3–4 will shrink how often it's reached.)*

## Implementation order (Emma's)

1. **Neural WASM — DONE (interim covers everything).** The `wasm_core` substrate VM can run any
   multiple recursion via tier 5 right now, so nothing is blocked while tiers 3–4 are built.
2. **Compile-time pre-evaluation (tier 3)** — next; leverages the existing loop-optimization /
   unrolling machinery. The depth cap is a compilation argument with an empirically-tested default.
3. **Automatic memoization (tier 4)** — then; replaces the WASM path for most multiple recursion.
   Pure functions make it safe + automatic; realize the memo table as recurrent-neuron state.

After tiers 3–4 land, WASM (tier 5) is reserved for genuinely imperative / `eval` constructs.

## Open problems

- **When NOT to pre-evaluate.** There are cases where you'd defer evaluation to runtime even when
  you technically could evaluate at compile time (binary size, startup time, runtime flexibility).
  Deciding this is **currently unsolved in Sutra** and worth a dedicated design pass before building
  tier 3's policy.
- **Overlap detection is undecidable in general.** Emma's resolution: don't try to detect overlap —
  **memoize everything** (it's the execution environment), and let the fixed-depth tier handle the
  cases where unrolling is clearly better. So tier 4 is the default for all dynamic multiple
  recursion; tier 3 is the optimization for the statically-bounded subset.
- **The pre-evaluation depth limit.** Pick the default empirically; expose it as a `.toml`
  compilation argument.

## Relationship to the rest of the spec / queue

- Tier 1 = Sutra's existing recurrent-neuron looping. Tier 2 = `queue.md` Phase 5.5-A (single→tail,
  all frontends). Tiers 3–4 are the refinement this doc adds (they were folded into "multiple→WASM"
  before; now most multiple recursion stays native). Tier 5 = the completed `wasm_core` (Phase 5).
- The `todo.md` end item *"Analyse the WebAssembly compatibility-layer approach"* is answered in
  spirit here: WASM is needed far less than "all multiple recursion" — only tier 5 (imperative/eval)
  and the not-yet-built-tiers interim. The per-language/per-context routing it asks about is exactly
  the tier-3/4/5 selection above.
