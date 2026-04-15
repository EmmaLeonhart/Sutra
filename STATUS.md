# Sutra — Work Queue

**This file is a queue, not a state snapshot.** When an item is done, delete it. Finished work lives in `git log` and `planning/findings/`. Strategic direction lives in `claw4s-scope.md` — read that first for what we're building toward.

## Queued work (do in order)

_Empty — pull the next target from `claw4s-scope.md`'s Apr 14–20 timeline._

## Pinned semantic corrections (I keep dropping these)

1. **`loop[N]` unrolls at compile time. Zero runtime iteration. No eigenrotation.** Only `loop(condition)` with data-dependent termination eigenrotates. Spec: `planning/sutra-spec/03-control-flow.md`.
2. **No loop counters live on the host at runtime.** The "counter" for `loop(condition)` IS the angular position on the helix R^i·v₀ in the substrate.
3. **"Rotation on neurons" has two meanings. Don't conflate:**
   - Synthetic R (Givens) as Brian2 synapse weights → works.
   - Real FlyWire weight matrix AS the rotation → does not rotate (compressive projection). Paper must say which every time.
4. **Permute → sign_flip rename.** The op does `a * sign(role)`, not dimension permutation. Spec's `permute` means shuffle. Aliases preserved.

## Pointers

- Strategic scope & Apr 20 build list: `claw4s-scope.md`.
- Formal Sutra grammar (EBNF): `planning/sutra-spec/grammar.md`.
- Spec: `planning/sutra-spec/{02-operations,03-control-flow,04-defuzzification,11-vsa-math,19-substrate-candidates}.md`.
- Findings (dated): `planning/findings/`.
- Open design questions: `planning/open-questions/`.
