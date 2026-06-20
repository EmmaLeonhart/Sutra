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

### Erlang — list comprehensions

Open item from `planning/wasm-fallback-edge-cases.md` § Elixir/Erlang. Erlang list comprehensions
(`[ X*2 || X <- L ]`). The doc notes this "needs a list abstraction the substrate lacks" — so the
likely outcome is an assessment that it stays on the WASM fallback, not a native lowering.

Steps:
1. Check what list abstraction the substrate/compiler currently offers (axon as positional store?
   `dict<int,int>`? any iteration primitive?).
2. Try a minimal list-comprehension fixture; lower; measure.
3. If a clean bounded lowering is genuinely in budget, ship it; OTHERWISE record the assessment
   (what the substrate is missing, why it stays on the fallback) in the edge-case doc and move on.

---

## Pointers

- Edge-case catalogue: `planning/wasm-fallback-edge-cases.md` (the source of this branch's work).
- Frontends: `sdk/sutra-from-{haskell,rust,ocaml,fsharp,scala,elixir,erlang,clojure}/`.
- Findings: `planning/findings/`. Devlog: `DEVLOG.md`.
