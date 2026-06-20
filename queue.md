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

### Elixir / Erlang — multi-arg non-tail multibase recursion

Open item from `planning/wasm-fallback-edge-cases.md` § Elixir/Erlang. >2-clause non-tail
multibase (single-arg CPS fold) is DONE; the residual is the MULTI-ARG non-tail multibase
(a non-tail recursive fn with >1 parameter that bottoms out at multiple bases).

Steps:
1. Inspect the existing Elixir/Erlang multibase fixtures + lowering to see how the single-arg CPS
   fold picks its base seed, and where the multi-arg case diverges.
2. Add a fixture exercising a multi-arg non-tail multibase; lower + substrate-run; measure.
3. If a clean native lowering is in budget, ship it (fixture RUN == ground truth, regression test).
4. If not clean in budget, record the assessment in the edge-case doc and move on.

---

## Pointers

- Edge-case catalogue: `planning/wasm-fallback-edge-cases.md` (the source of this branch's work).
- Frontends: `sdk/sutra-from-{haskell,rust,ocaml,fsharp,scala,elixir,erlang,clojure}/`.
- Findings: `planning/findings/`. Devlog: `DEVLOG.md`.
