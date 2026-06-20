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

### Haskell — >2-guard NON-tail multibase recursion

Open item from `planning/wasm-fallback-edge-cases.md` § Haskell. The multibase TAIL recursion is
done (`multibase_tailsum`, `multibase_explicit_rec`); the residual is the >2-guard NON-tail
multibase, where the CPS fold must pick its seed from which base the recursion bottoms out at.
The Elixir/Erlang non-tail multibase fold (just shipped) is the family reference.

Steps:
1. Inspect the Haskell multibase lowering + the just-shipped Elixir/Erlang non-tail multibase fold.
2. Add a fixture exercising a >2-guard non-tail multibase; lower + substrate-run; measure.
3. If a clean native lowering is in budget, ship it (fixture RUN == ground truth, regression test).
4. If not clean in budget, record the assessment in the edge-case doc and move on.

---

## Pointers

- Edge-case catalogue: `planning/wasm-fallback-edge-cases.md` (the source of this branch's work).
- Frontends: `sdk/sutra-from-{haskell,rust,ocaml,fsharp,scala,elixir,erlang,clojure}/`.
- Findings: `planning/findings/`. Devlog: `DEVLOG.md`.
