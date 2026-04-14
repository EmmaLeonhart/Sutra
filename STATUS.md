# Sutra — Current State

**Read this at the start of every session.** Truth table, not docs.
Lean — tracks what's left to do. Finished work lives in `git log` and
`planning/findings/`.

## Meta Instructions

quickly execute through the things in this document in order and remove them as you do so. Unforunately contrary to expectations, claude has not been clearely through this document like expected, and it is as a bit cruddy. We have a working queue that might just be entirely done, and we have the scope thing at the end of this document which is the real pivot direction. Most of the stuff in this document is likely outdated because Claude was not clearing it like expected.

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

## Pivot (2026-04-14): build our own connectionist computer, treat fly-brain as a downstream target

Decision after a hard look at the project state with the user:

**The fly-brain was the wrong primary substrate.** It is an *edge-computing* problem — a fixed anatomy with non-negotiable wiring — and we were attempting it before establishing what the operations even look like on an *ideal* substrate. The negative results we kept hitting (rotation doesn't loop on EPG-only W, bind doesn't role-discriminate, conditional branching gated by random-seed codebook collisions) read in retrospect as "this particular anatomy is restrictive," not "VSA on connectomes doesn't work." We could not tell those apart because we did not have an unconstrained substrate to compare against.

**The new primary substrate: a connectionist computer of our own design.** A spiking population (LIF or similar) where we choose the connectivity to match what each Sutra operation needs. This is still connectionist (still no traditional control flow, still substrate-resident operations, still GPU-runnable as sparse matmuls), but the wiring is a *parameter*, not a constraint. If sign-flip binding needs a particular topology to discriminate roles, we wire it that way. If `loop (cond)` needs a working ring attractor, we instantiate a Δ7+PEN+EPG+R-equivalent without arguing about whether FlyWire's actual EPG slice rings.

**Fly-brain becomes a downstream target, not the primary one.** Once we know what an operation needs in an ideal substrate, mapping that requirement onto the fly connectome is a separate (interesting, possibly hard, possibly impossible) compatibility question. "Run Sutra on a fly brain" is then the same kind of claim as "run C on a 6502" — empirical, scoped, and not load-bearing for the language. The fly-brain failures we've collected are useful data for that mapping, not refutations of the language.

**What the language actually is.** Sutra is a control-flow-free programming language whose programs compile to substrate-resident vector operations: bind, bundle, similarity, snap, plus `select` (softmax-weighted blend) and `gate` (defuzz + commit) as the only control primitives. With the substrate under our control, this is plausibly *Turing-complete on a GPU with no CPU branching* — every primitive is a matmul, sum, or cosine. That is a defensible technical claim, distinct from the AGI/fly-brain framing that has been overclaimed. Whether it's *novel* (people have built control-flow-free GPU compute before) is a literature question we haven't audited yet.

**Concrete consequences:**

1. The paper currently in `sutra-paper/` has been retitled and trimmed to its actual contribution: an empirical characterization of which VSA operations work on frozen LLM embeddings (sign-flip binding 14/14, etc.). It is not the language paper. It is the embedding-operations paper. Any future "language paper" should be written separately, against the connectionist-computer-of-our-own-design substrate, once that substrate exists.
2. `fly-brain-paper/` should be similarly trimmed to what it can defend honestly — bundle + snap + conditional-branching on real FlyWire W — and stop reaching for "Sutra on a connectome." Edits not yet made; flagged.
3. Forcing operations onto Shiu (the policy in CLAUDE.md "The real substrate is the Shiu whole-brain LIF model") is downgraded. Shiu is *one* substrate, useful for the fly-as-target work; the new primary surface is a substrate we wire ourselves. CLAUDE.md will be updated to reflect this once the connectionist-computer scaffolding lands.

The fly-brain failures were valuable data and are not retracted as findings (the EPG-no-recurrence result, the SCC analysis, the bind role-discrimination negative). What changes is what we *conclude* from them: not "VSA doesn't work on this connectome" but "this connectome is one constrained instance of what we should be characterizing on a free substrate first."

Related: `planning/open-questions/project-kind-connectome-vs-embedding.md` is the manifest-level version of this split; it now extends to a third project kind, "general-connectionist," which becomes the default.

## Pointers

- Formal Sutra grammar (EBNF): `planning/sutra-spec/grammar.md`.
- Spec: `planning/sutra-spec/{02-operations,03-control-flow,04-defuzzification,11-vsa-math,19-substrate-candidates}.md`.
- Findings: `planning/findings/` (dated, per CLAUDE.md).
- Open design questions: `planning/open-questions/`.

## Final thing to do
- Read through this file "claw4s-scope.md" and it explains exactly what we are limiting our scope to doing