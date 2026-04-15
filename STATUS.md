# Sutra — Work Queue

**This file is a queue, not a state snapshot.** When an item is done, delete it. Finished work lives in `git log` and `planning/findings/`. Strategic direction lives in `claw4s-scope.md`.

## Queued work (do in order)

1. **Concurrency spec-adjacent note.** Open-question doc is updated with "two or more paths through the vector space" framing. Consider a short sketch in `planning/sutra-spec/` if/when a concrete program needs it. Not a blocker.

**Hard stop:** if by end of Apr 17 the paper isn't in a submittable state, drop the Claw4S push (per `claw4s-scope.md`). Fellows Apr 26 is higher priority. Runtime is already past the hard-stop gate — two examples run end-to-end.

## Pinned semantic corrections (I keep dropping these)

1. **`loop[N]` unrolls at compile time. Zero runtime iteration. No eigenrotation.** Only `loop(condition)` with data-dependent termination eigenrotates. Spec: `planning/sutra-spec/03-control-flow.md`.
2. **No loop counters live on the host at runtime.** The "counter" for `loop(condition)` IS the angular position on the helix R^i·v₀ in the substrate.
3. **"Rotation on neurons" has two meanings. Don't conflate:**
   - Synthetic R (Givens) as Brian2 synapse weights → works.
   - Real FlyWire weight matrix AS the rotation → does not rotate (compressive projection). Paper must say which every time.
4. **Permute → sign_flip rename.** The op does `a * sign(role)`, not dimension permutation. Spec's `permute` means shuffle. Aliases preserved.
5. **Numpy is the demo substrate. Fly-brain is segregated.** The compiler has two backends: `codegen_numpy.py` (demo path, self-contained, no fly-brain imports) and `codegen_flybrain.py` (fly-brain-specific work, not the demo). PyTorch/GPU is a future refactor target.

## Pointers

- Strategic scope & Apr 20 build list: `claw4s-scope.md`.
- Formal Sutra grammar (EBNF): `planning/sutra-spec/grammar.md`.
- Spec: `planning/sutra-spec/{02-operations,03-control-flow,04-defuzzification,11-vsa-math,19-substrate-candidates}.md`.
- Findings (dated): `planning/findings/`.
- Open design questions: `planning/open-questions/`.
