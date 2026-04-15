# Sutra — Work Queue

**This file is a queue, not a state snapshot.** When an item is done, delete it. Finished work lives in `git log` and `planning/findings/`. Strategic direction lives in `claw4s-scope.md`.

## Queued work (do in order)

1. **Documentation sweep — reposition toward "real programming language," away from fly-brain.** The repo still has lots of fly-brain-first framing in README, paper abstracts, CLAUDE.md, the Sutra spec preamble, and planning docs. User: fly-brain was the wrong substrate; Sutra is a real compiler targeting matrix substrates (numpy today, PyTorch next). Sweep documentation to make that the primary framing. Fly-brain stays mentioned but segregated — not the headline, not the demo, not the load-bearing claim.
2. **Repo cleanup + README.** README with one-paragraph "what this is," install command, single command to run both examples (`python examples/_smoke_test.py` works today). License. No dead TODOs in paths the README hits. Fresh-clone reproducibility test.
3. **Paper assembly.** Pull `sutra-paper/` material into the `claw4s-scope.md` structure (abstract / background / language / runtime / demonstrations / discussion / limitations / repro appendix). No rewrite, just assembly. Demonstrations section points at `examples/_smoke_test.py` output.
4. **Honesty pass.** Red-pen the paper for brain-execution claims, latent-space-execution claims, and citations that don't exist. Fix paper IDs (clawRxiv `2604.01127`). "Preprinted" not "published."
5. **Submit.** Push triggers `papers-ci.yml` → clawRxiv. Buffer day Apr 20.

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
