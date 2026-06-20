# Sutra — Work Queue (branch: wasm-fallback-edge-cases-native)

**This branch is OFF the main big-leg queue.** Emma 2026-06-19: separate exploratory
branch. Mission: walk `planning/wasm-fallback-edge-cases.md` ONE edge case at a time —
pull it into this queue, attempt a NATIVE lowering within a few-cycles budget, and:

- If it lowers natively (new fixture lands, RUN == ground truth): delete it from the
  edge-case doc, add a fixture/regression test, append to `DEVLOG.md`, commit+push.
- If it is NOT clean in a few cycles: leave it on the WASM fallback, record the
  assessment in the edge-case doc (dated), commit+push, move to the next one.

**NEVER fake / never loosen a test** to make one "pass" (edge-case doc policy).

---

## Active edge case

### F# / Scala — a concrete missing String op (modelled on OCaml)

Open item from `planning/wasm-fallback-edge-cases.md` § F#/Scala "general breadth (… more String
ops), modelled on OCaml as needs arise." The OCaml frontend is the reference; F#/Scala lag on some
String ops. Pick ONE concrete, common String op OCaml supports that F#/Scala don't, attempt it.

Steps:
1. Compare the OCaml frontend's String-op support to F#/Scala (length, indexing, concat, slice,
   `String.length`/`.Length`, etc.); find one concrete op F#/Scala miss.
2. Add a fixture exercising it; lower + substrate-run; measure.
3. If a clean native lowering is in budget, ship it (fixture RUN == ground truth, regression test).
4. If not clean in budget, record the assessment in the edge-case doc and move on.

(After this: the discrete actionable WASM-fallback edge cases are largely worked through — remaining
items are open-ended breadth, assessed-stays (OCaml Array.make fill), or Emma-dropped (Rust). If this
drains, report back rather than manufacturing vague tasks.)

---

## Pointers

- Edge-case catalogue: `planning/wasm-fallback-edge-cases.md` (the source of this branch's work).
- Frontends: `sdk/sutra-from-{haskell,rust,ocaml,fsharp,scala,elixir,erlang,clojure}/`.
- Findings: `planning/findings/`. Devlog: `DEVLOG.md`.
