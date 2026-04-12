# Sutra — Current State

**Read this at the start of every session.** It is the truth table, not the docs. Update it when state changes. Keep it under one screen.

## What this is right now

A **quantitative biology / programming-languages paper**, submitted to Claw4S 2026 (April 20 deadline), iterating on clawRxiv via `papers-ci.yml`. Not medicine. Not a physical device. A computational model with the real hemibrain graph as the substrate graph of the simulation. Physical deployment (patient neurons, neuromorphic chip, Neuralink-style interface) is Y-Combinator-tier future work, explicitly out of scope for the paper. **Lives are still at stake because the paper is load-bearing for that downstream pipeline** — faked numbers here propagate. See CLAUDE.md safety banner.

## Built / Works

- **Tier-3 on real hemibrain wiring** — PN→KC sparse projection, APL-enforced ~7.8% sparsity, Jaccard prototype match. This is genuinely on the connectome.
- **Conditional branching** — 13/16 on four-way permutation program, 4/4 distinct mappings. Fuzzy weighted superposition works.
- **Bounded loops `loop[N]`** — unrolled at compile time into flat algebraic expressions. No runtime iteration. No eigenrotation. Works.
- **Tier-2 bundle/bind/rotate on synthetic-weight spiking circuits** (`fly-brain/neural_vsa.py`) — Brian2 LIF, Givens R as synapse weights. Cos 0.94–0.99 vs numpy reference. Rotation R is chosen by us, not by biology.
- **Tier-2 bundle on real FlyWire wiring** (`fly-brain/neural_vsa_flywire.py`) — cos 0.94 vs W·v reference.
- **I/O rate coding** — centered rate encoding of hypervectors as PN currents, linear MBON readout via ridge regression. Works.
- **Compiler pipeline** — `sdk/sutra-compiler/` emits Python that calls `fly-brain/vsa_operations.py`. `.su` programs (e.g. `permutation_conditional.su`) compile through it.

## Open / Known Gaps

- **Rotation from real wiring** — ALPN→LHLN is rank 415, cond 1e16, compressive, NOT near-orthogonal. Real-wire R is not a rotation. Only bites `loop(condition)` with data-dependent termination. Open work: find a connectome motif with adequate near-orthogonality, or distribute across multiple projections. `_exploratory_cx_ring_attractor.py` tried CX and got corr 0.97 between left/right drive — not directional.
- **Intrinsic temporal dynamics** — the `for i in range(max_iters)` that threads ops together runs in host Python. No substrate-intrinsic trajectory yet. (User: don't need to address for this paper.)
- **Dimensionality** — 140-PN I/O is narrow vs standard VSA (1k–10k). Likely contributor to 13/16 branching accuracy. KC-promotion to 1,882-D is planned.
- **Eval size** — 16 branching trials, 3 iteration trials. Proof-of-substrate, not statistical robustness.
- **Biological learning rule** — MBON readout is ridge regression, not dopamine-gated plasticity. Planned.

## Out of Scope (don't touch unless user opens it)

- Physical deployment, in-vivo execution, neuromorphic hardware bridge, BCI interface design.
- Intrinsic temporal dynamics / host-free run loop (user explicitly said skip).
- `foreach` loops (not yet in spec; if added, would unroll like `loop[N]`, no eigenrotation).

## Pinned semantic corrections (I keep dropping these)

1. **`loop[N]` unrolls at compile time. Zero runtime iteration. No eigenrotation.** Only `loop(condition)` with data-dependent termination eigenrotates. See `planning/sutra-spec/03-control-flow.md`. The eigenrotation gap is a narrow slice of the language surface, not the common case.
2. **No loop counters live on the host at runtime.** The "counter" for `loop(condition)` IS the angular position on the helix R^i·v₀ in the substrate. Corkscrew geometry. Not an integer.
3. **"Rotation on neurons" has two meanings, don't conflate:**
   - Synthetic R (Givens composition) realized as Brian2 synapse weights → works (`neural_vsa.py`).
   - Real FlyWire weight matrix AS the rotation → does not rotate (compressive projection).
   Paper must say which is which every time.
4. **Compile target is patient neurons / neuromorphic chip with FlyWire topology.** Brian2 is dev-time simulator only. Simulation wall-clock latency is irrelevant to deployment — but deployment itself is out of scope for this paper.
5. **Rotation in biology is fixed by anatomy.** You do not pick R. You compile within the eigenstructure the patient's connectome provides.
6. **Permute → sign_flip rename.** The op does sign-flip binding (`a * sign(role)`), not dimension permutation. Spec's `permute` means shuffle. Class aliases preserved for back-compat.

## Current paper state

- `fly-brain-paper/paper.md` — latest push a2b90c1, awaiting v18 review from papers-CI.
- Last review: **v17 Strong Reject** (Gemini 3 Flash, 2026-04-12). Cons addressed in latest pushes: (a) softened Turing-complete claim to engineering-sense finite-FSM; (b) added Honest Limits section with real-wire rotation negative result; (c) referenced `planning/sutra-spec/` and `sdk/sutra-compiler/` to counter "ad-hoc/hallucinated" claim; (d) acknowledged 140-PN narrowness, small eval, ridge readout; (e) scope-of-work clarified as computational model, not deployment.
- Pending reviewer threads if v18 still rejects: unclear what else to pull.

## Workflow reminders

- **Incremental paper edits only.** One sentence/paragraph/table, show diff, get approval, commit, push. Big rewrites have historically turned Strong Accept into Reject. See CLAUDE.md.
- **Push triggers papers-CI** → new clawRxiv submission + new review. Every push is a version.
- **Never mention "Claw4S 2026"** in paper body — reviewer flags as hallucinated citation. Reference companion papers by clawRxiv post number only.
- `git pull --rebase` before every push is still wise (human collaborators, pages.yml, etc.), but papers-CI and competition-cron no longer push to master — they open PRs on branches `papers-ci/<paper_dir>/run-<id>` and `competition-cron/run-<id>`. Merge PRs by hand until auto-merge is wired up.
