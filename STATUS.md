# Sutra — Current State

**Read this at the start of every session.** Truth table, not docs.
Lean — tracks what's left to do. Finished work lives in `git log` and
`planning/findings/`.

## What this is

Quantitative biology / PL paper, submitted to Claw4S 2026 (April 20
deadline) via `papers-ci.yml` auto-push to clawRxiv. Model with the
real hemibrain graph as substrate. Physical deployment is out of scope
for the paper but the paper is load-bearing for a downstream biomedical
pipeline — **faked numbers here propagate to lives**. See CLAUDE.md
safety banner.

## Open gaps (limitations, not queue items)

- **Conditional branching on remote substrate.** Final argmax over 4
  behavior candidates + outer loop driver run in host Python. Readout,
  not branching. Design doc: `planning/open-questions/conditional-branching-on-remote.md`.
- **Intrinsic temporal dynamics.** `for i in range(max_iters)` runs in
  host Python. No substrate-intrinsic trajectory. User: skip for this paper.
- **Dimensionality.** 140-PN I/O is narrow vs standard VSA (1k–10k).
  KC-promotion to 1,882-D planned but not urgent.
- **Biological learning rule.** MBON readout is ridge regression, not
  dopamine-gated plasticity.

## Backlog (after paper)

- **Codegen V1 feature coverage.** 6/13 illustrative `.su` files hit
  `CodegenNotSupported` on method/operator decls, `EmbedExpr`,
  `DefuzzyExpr`, `UnsafeCastExpr`. Paper-cited programs all compile.
  Breakdown: `planning/open-questions/codegen-v1-feature-coverage.md`.

## Out of scope (don't touch unless user opens it)

- Physical deployment, in-vivo execution, neuromorphic bridge, BCI.
- Intrinsic temporal dynamics / host-free run loop.
- `foreach` loops (not yet in spec).

## Pinned semantic corrections (I keep dropping these)

1. **`loop[N]` unrolls at compile time. Zero runtime iteration. No
   eigenrotation.** Only `loop(condition)` with data-dependent
   termination eigenrotates. Spec: `planning/sutra-spec/03-control-flow.md`.
2. **No loop counters live on the host at runtime.** The "counter" for
   `loop(condition)` IS the angular position on the helix R^i·v₀ in the
   substrate.
3. **"Rotation on neurons" has two meanings. Don't conflate:**
   - Synthetic R (Givens) as Brian2 synapse weights → works.
   - Real FlyWire weight matrix AS the rotation → does not rotate
     (compressive projection). Paper must say which every time.
4. **Compile target is patient neurons / neuromorphic chip with FlyWire
   topology.** Brian2 is dev-time simulator only. Deployment out of
   scope for this paper.
5. **Rotation in biology is fixed by anatomy.** You do not pick R.
   Compile within the patient's eigenstructure.
6. **Permute → sign_flip rename.** The op does `a * sign(role)`, not
   dimension permutation. Spec's `permute` means shuffle. Aliases
   preserved.

## Paper state

- `fly-brain-paper/paper.md` — two-pipeline restructure shipped
  2026-04-13; pipeline A (substrate-only) + pipeline B (numpy rot +
  MB-Jaccard) reported side-by-side. SIM_MS sweep added.
- `sutra-paper/paper.md` — tier framing stripped; not yet restructured
  around the two-pipeline result.

## Workflow reminders

- **Push triggers papers-CI** → new clawRxiv submission + review. Every
  push is a version. Edit aggressively.
- **Never mention "Claw4S 2026"** in paper body — reviewer flags as
  hallucinated citation. Reference companion papers by clawRxiv post
  number only.
- `git pull --rebase` before every push.
- Merge / PR guidance: `planning/merge-help.md`.
- One `todo.md` (repo root), one `STATUS.md` (this file). `fly-brain/todo.md`
  and `sutraDB/TODO.md` are consolidated in; do not recreate them.
  STATUS = now-work, todo = long-term agenda.

## Pointers

- Formal Sutra grammar (EBNF): `planning/sutra-spec/grammar.md`.
- Spec: `planning/sutra-spec/{02-operations,03-control-flow,04-defuzzification,11-vsa-math,19-substrate-candidates}.md`.
- Findings: `planning/findings/` (dated, per CLAUDE.md).
- Open design questions: `planning/open-questions/`.
