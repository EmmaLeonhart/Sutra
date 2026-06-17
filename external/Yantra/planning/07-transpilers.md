# Transpilers

Yantra leans on transpilation for the parts where it is genuinely
useful and writes natively for everything else. The language story
is **not** "transpile the world into Sutra"; it is "transpile where
existing code is the well-tested asset, write natively where it is
not."

One transpiler is in scope:

1. **JS / TS → Sutra** — **GUI/browser layer only.** The user-facing
   stack is HTML5 + CSS + JavaScript + WebGL/Three.js; component
   logic ships as idiomatic TypeScript and is AOT-transpiled at
   page load. Outside the browser layer this transpiler is not used.

There is **no C → Sutra transpiler** (decision 2026-05-23): Yantra
is not copying the Linux kernel or C apps, userspace is written
natively in Sutra, and the bootloader + orchestrator are written
natively in Rust. See "C → Sutra — not planned" below.

Explicitly **deferred — eventually, but not soon** (decision 2026-05-14):

- **WASM → Sutra.** WASM is *eventually* in scope but
  **not now and not for a long time** — it is not a v0 target, not a
  v0.1 target, not on any near-term roadmap. WASM's linear-memory
  and threading model is alien to Sutra's substrate; the edge-case
  engineering would be a sink relative to its near-term payoff. The
  v0 GUI stack is JS/TS-only; web bundles that ship only as WASM
  either re-ship as JS or don't run on Yantra v0. When WASM does
  land it will be a deliberate later-phase project, not a free
  fall-out.

What is **written natively in Sutra** (no transpiler involved):

- **The Yantra kernel** — the connectome manager that decides what
  runs on the GPU vs sits in RAM cold-store vs on disk. The CPU-side
  orchestrator wrapper around it is **Rust** (see `01-architecture.md`).
- **Userspace utilities** (cat, ls, grep, awk, sed, etc.) — see
  `todo.md` § 2 for the Q-list. GNU coreutils / util-linux behaviour
  is the conceptual reference for these native rewrites.

## JS / TS → Sutra

**Scope: browser/GUI specifically.** TS→Sutra is on the critical
path *for the browser layer* — Yantra commits to "everything is a
browser" for the GUI, and that choice only works if real JS/TS
bundles compile to Sutra without a human rewrite. Outside the
browser layer, TS→Sutra is not used: the kernel is native Sutra,
userspace utilities are native Sutra rewrites, and there is no
general-purpose "JS apps run on Yantra" promise.

Status: **shipped as Sutra v0.3.2** (released 2026-05-14). The CLI
(`python -m sutra_from_ts input.ts`) reads `.ts` / `.js`, lowers
through `lower.py` (~1500 lines covering functions, classes,
async/await, discriminated unions, etc.), writes valid `.su`. 17
fixtures pass through end-to-end; 4 new CLI smoke tests lock the
wire-up. `pip install sutra-dev[ts]` pulls in the transpiler
alongside the compiler — recommended install for browser/GUI dev
is `pip install sutra-dev[runtime,ts]`.

Coverage caveat: TS-completeness is not "done." 17 fixtures is a
floor, not a ceiling — real-world bundles will hit constructs
that need additional lowering rules. The transpiler is **shippable
as a foundation for browser-layer work**, not a guarantee that any
arbitrary npm package will compile.

What it does well:

- Closures, higher-order functions, immutable patterns — these compile
  cleanly because they are already close to Sutra's functional core.
- Reactive UI frameworks (React-style components, Solid-style signals,
  Svelte-style stores) — these push JS toward the dataflow shape Sutra
  wants. Idiomatic React-ish code compiles surprisingly well.
- Tail-recursive loops, when written that way, lower directly to Sutra's
  soft-halt RNN cells.

What is hard, and where we have to impose conventions:

- **Mutation.** `obj.prop = x` is technically legal but semantically a
  mess in a fixed-state model. The transpiler treats it as SSA (every
  assignment is a fresh name) and threads the new value through the
  rest of the function.
- **Async / promises / event listeners.** These dissolve into axon
  channels: an event listener is a process that consumes an axon stream
  from the input router; a promise is a "wait until this role is
  bound" pattern. The translation works, but the patterns idiomatic JS
  programmers reach for sometimes need a small re-shape.
- **Dynamic object shapes.** Objects whose shape changes at runtime are
  hostile to a fixed-width state model. The transpiler refuses them and
  emits a clear error. TS programs avoid this naturally; pure JS
  programs sometimes need to be cleaned up.
- **`eval`, `new Function`, runtime `import()` of remote URLs.** Refused.
  Documented limitation.

### The "flow object" pruning pass

A real wart that surfaced in practice: tail-recursive loops, after
SSA-ification, generate "flow objects" that carry the loop's free
variables across iterations. The naive lowering captures everything in
scope, including variables that are never read on the next iteration.
That bloats GPU memory and degrades crosstalk margins.

The transpiler needs a liveness pass that, for each loop, computes the
set of variables actually consumed on the next iteration and trims the
flow object down to that set. This is straightforward static analysis
but the current transpiler does not do it well enough yet.

### What ships in the minimal viable subset

To get a usable userspace fast, we draw a line at:

- ES2017-style core (let/const, classes, async/await, spread, destructure)
- TS structural types (narrowed enough that the transpiler can statically
  size axons)
- Reactive primitives that the runtime understands natively (a small
  signals library, similar in spirit to Solid)
- The `fetch` / `WebSocket` / DOM subset documented in `06-gui-stack.md`

Anything beyond this still works if it does, but is not promised.

## C → Sutra — not planned

The C→Sutra transpiler is **not planned** (decision 2026-05-23). An
earlier draft listed it as "priority but deferred" with a stubbed
`sdk/sutra-from-c/`; that direction is dropped. The reasoning:

- Sutra is a systems language for a GPU-native architecture, a poor
  fit for C's mutable-memory + pointer model. Yantra is not trying to
  copy the Linux kernel or bring across C userspace.
- Userspace utilities are written **natively in Sutra**. The
  bootloader and the CPU-side orchestrator are written **natively in
  Rust** — not produced by transpiling C. (Sutra pairs naturally with
  Rust for the systems layer; it does not pair with C.)
- The only code Yantra needs to *bring across* rather than rewrite is
  JavaScript/TypeScript, because the GUI layer is "everything is a
  browser." That is the TS→Sutra transpiler's job, above.

The kernel is, and remains, native Sutra — C-transpiling it would
have defeated the verification-surface argument in `paper/paper.md`
§ 4 regardless. C→Sutra may be revisited far down the road, but it is
not on any roadmap and should not be treated as planned work.

## WASM → Sutra — deferred (eventually, but not soon)

WASM is **eventually** in scope but **not now and not for a long
time** (decision 2026-05-14).

The reasoning for the deferral:

- WASM's linear-memory + threading model is alien to Sutra's
  fixed-width-state substrate. The edge-case engineering to map
  WASM semantics onto Sutra would dominate the integration cost
  in the near term and produce code that is correct, slow, and
  brittle.
- The expected near-term payoff (web apps that ship only as WASM
  bundles Just Work) does not match what v0 GUI work needs
  (idiomatic TypeScript components transpiled at page load — the
  WASM-bundle case is an edge that does not justify its weight at
  v0).
- WASM is not a v0 target, not a v0.1 target, and not on any
  near-term roadmap. When it does land it will be a deliberate
  later-phase project, not a free fall-out of the C transpiler.

This section is preserved as the decision record so future work
doesn't independently re-derive the WASM target before its time.

## What we do *not* transpile

- The Sutra compiler itself.
- The runtime.
- The kernel (it's written directly in Sutra).
- Userspace utilities we author from scratch (file manager, settings,
  terminal-as-HTML, etc.).

Transpilation is the on-ramp, not the destination.

## Open questions

- **Source maps.** Debugging a transpiled program by reading the Sutra
  intermediate is awful. We need source maps that survive transpilation
  + Sutra compilation, so the GUI debugger can show JS line numbers.
- **Incremental transpilation.** AOT compile-on-page-load means an app
  install can take a while. A cache that survives across launches and
  invalidates on the bundle hash should pay for itself quickly.
- **Coverage of the JS standard library.** We don't have to support
  every weird `Array.prototype` method, but we have to support enough
  that real frameworks work. The current coverage is adequate for
  reactive UI but spotty on the data-manipulation side.
