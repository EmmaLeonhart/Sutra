# MLP-backed attractor search for king - man + woman on nomic

**Date:** 2026-04-22.
**Status:** Implemented and run. First real attractor-dynamics
result for Sutra on a frozen LLM substrate. Closes the
"Monte-Carlo attractor search" item the user flagged earlier in
this session — the deferred timing was pushed to same-day per
2026-04-22 direction. Companion to
`2026-04-22-king-queen-across-substrates.md`.

## What was done

`examples/_king_queen_mlp_attractor.py` trains a residual MLP
`f(x) = x + r(x)` with `r` a 2-layer tanh net (768 → 512 → 512 →
768), zero-initialized final layer so `f` starts as identity. The
training objective: for each of 14 codebook vectors (king, queen,
man, woman, prince, princess, boy, girl, ruler, monarch, husband,
wife, father, mother) on nomic-embed-text, the MLP should map
`c + eps*n` back to `c` for random `eps ∈ [0.05, 0.40]` and random
unit-direction `n`. 7000 training pairs total, 3000 epochs Adam at
lr=1e-3, ~30s on GPU.

After training, each codebook vector is a fixed point: `||f(c) -
c|| ≈ 0.014` across all 14 entries, cleanly below the ~0.3-0.7
inter-codebook distances.

The starting vector is the naive analogy:
`v0 = bundle(displacement(king, man), woman)`
on the same nomic substrate used for
`examples/king_queen_naive.su`. Baseline `argmax_cosine(v0,
codebook)` returns `queen` with cos=0.788 (king 2nd at 0.748) —
the queen-wins-narrowly result from the cross-substrate sweep.

## Trajectory result

Iterating `f(v0)` for 30 steps:

| Step | Nearest codebook | Cosine | Step size |
|------|------------------|--------|-----------|
| 0    | queen            | +0.788 | —         |
| 1    | queen            | +0.797 | 0.067     |
| 2    | queen            | +0.797 | 0.009     |
| 3    | queen            | +0.797 | 0.008     |
| 10   | queen            | +0.794 | 0.008     |
| 30   | queen            | +0.773 | 0.007     |

Every step stays in queen's basin. After one step the cosine to
queen rises to 0.797 (the attractor pulls v0 *toward* queen), then
slowly drifts as trajectory continues. Step size decays to ~0.007
per step — the dynamics have essentially converged to a neighborhood
of queen.

**Result: on nomic, queen IS the basin of attraction for v0.** The
attractor MLP agrees with the naive argmax.

## Monte-Carlo basin sweep

200 trajectories per noise-level, starting from `v0 + noise_std *
gaussian`, iterated 30 steps, snap to nearest codebook.

| Noise std | Queen basin | King basin | Scattered |
|-----------|-------------|------------|-----------|
| 0.00      | 200 (100%)  | 0          | 0         |
| 0.05      | 161 (80.5%) | 39 (19.5%) | 0         |
| 0.15      | 82 (41%)    | 72 (36%)   | 46 (23%)  |
| 0.30      | 40 (20%)    | 43 (21.5%) | 117 (58.5%)|

**The queen/king basin boundary is close to v0.** At 0.05 noise, 1
in 5 trajectories flips to king. At 0.15 noise, queen and king are
near-tied — v0 is effectively *on* the boundary in a geometric
sense. At 0.30 noise, the sweep scatters broadly (king leads but
queen is essentially at chance level, plus woman, ruler, princess,
monarch, mother, wife, girl, boy, husband, father, man all have
residual mass).

## What this tells us about the nomic analogy

The cross-substrate sweep
(`2026-04-22-king-queen-across-substrates.md`) showed queen winning
naively only on nomic, with a +0.040 margin over king (0.788 vs
0.748). The attractor-MC result is the **geometric interpretation
of that thin margin**:

- v0 lies inside queen's basin on nomic. Attractor dynamics confirm
  this without any input-exclusion trick.
- v0 is **near the basin boundary with king**. A small Gaussian
  perturbation (5% of vector norm) flips 1 in 5 trajectories to the
  king basin. At 15%, it's a coin flip.

So the "nomic passes naive analogy" signal is real but fragile. It
correctly identifies queen, but the geometry is such that small
substrate noise or slight vocabulary changes would tip the balance.
This is consistent with the 0.040 cosine margin — a thin margin
geometrically has a proximal basin boundary.

**Important caveat**: at 0.15+ noise the sweep scatters into other
attractors (woman, ruler, princess, monarch, mother, wife, girl,
boy, husband, father, man all have residual mass). Some of that is
meaningful (princess, monarch are genuinely close semantic
neighbors of queen) and some reflects the 14-dim codebook's
limitations. A richer codebook would change the MC distribution.

## Design notes

- **Skip connection is load-bearing.** Without `f(x) = x + r(x)`, a
  random-init MLP output has arbitrary magnitude; iterating pulls
  trajectories off the embedding manifold immediately. The
  residual form + zero-init final layer makes `f` start as identity
  and learn small corrections — trajectories stay close to the
  manifold.
- **Tanh activations** keep the residual bounded, which helps
  stability under repeated iteration. ReLU-family activations
  tested briefly gave less stable long-time behavior.
- **14 attractors is a toy codebook.** This is proof-of-mechanism;
  the same setup scaled to 1K-10K codebook entries would be a
  meaningful concept-memory. Future work.
- **The MLP sees nomic-specific vectors only.** It does not
  generalize to other substrates; training is per-substrate.

## Relation to the TransE/VSA unification

One of this session's earlier findings
(`2026-04-22-king-queen-across-substrates.md`) noted that the naive
analogy formula `h + r ≈ t` is literally the rank-0 case of Sutra's
learned-matrix binding — TransE and VSA are the same thing at
different rank. The attractor MLP here is yet another lens: treat
the codebook as fixed points of a trained dynamical system, and ask
"which attractor does v0 fall into." That's a *third* way to frame
the same question, and all three (argmax-cosine, TransE-style
translation, attractor basin membership) give the same answer
on nomic for king - man + woman. When they disagree — on weaker
substrates, richer codebooks, harder analogies — the disagreements
are the data.

## What remains (todo.md / queue.md)

- **Cross-substrate attractor comparison.** Train separate MLPs on
  each of nomic / mxbai / minilm and compare basin maps. Do the
  attractors that nomic learns look qualitatively different from
  the ones mxbai or minilm can learn? Expected: mxbai and minilm
  can still produce valid attractors (the MLP will overfit to any
  14 points), but the basin of v0 will differ because the substrate
  places (king - man + woman) in a different geometric spot.
- **Larger codebooks.** 14 words is proof-of-mechanism. Scaling to
  thousands of codebook entries and training the MLP as a learned
  concept-memory would make this a real building block for Sutra
  semantic memory.
- **Attractor-MLP as a Sutra builtin.** Currently only accessible
  from Python. A language-level declaration (`attractor M =
  learn_attractor(codebook)`) would let .su programs use attractor
  dynamics natively.
- **Capacity characterization.** Standard associative-memory
  capacity metrics (how many attractors fit; retrieval degradation
  as capacity saturates) would contextualize the toy-scale result
  here against the classical Hopfield/Krotov literature.

## Prior-art audit pending

Attractor-based associative memory is decades-old (Hopfield 1982,
Kanerva SDM, plus the modern Hopfield / energy-based reformulation
in Ramsauer et al. 2020). Using a trained MLP as the attractor
function rather than a hand-designed energy landscape is adjacent
to work by Krotov and Hopfield on modern/dense associative memories.
The specific combination used here — train an MLP to denoise
codebook vectors, iterate as attractor dynamics, use basin
membership as a semantic-memory lookup on LLM embeddings — may be
underexplored but needs a real search before publication. See
todo.md "prior-art audit" items.
