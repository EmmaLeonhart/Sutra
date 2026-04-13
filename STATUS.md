# Sutra — Current State

**Read this at the start of every session.** It is the truth table, not the docs. Update it when state changes. Keep it under one screen.

## What this is right now

A **quantitative biology / programming-languages paper**, submitted to Claw4S 2026 (April 20 deadline), iterating on clawRxiv via `papers-ci.yml`. Not medicine. Not a physical device. A computational model with the real hemibrain graph as the substrate graph of the simulation. Physical deployment (patient neurons, neuromorphic chip, Neuralink-style interface) is Y-Combinator-tier future work, explicitly out of scope for the paper. **Lives are still at stake because the paper is load-bearing for that downstream pipeline** — faked numbers here propagate. See CLAUDE.md safety banner.

## Built / Works

- **Tier-3 on real hemibrain wiring** — PN→KC sparse projection, APL-enforced ~7.8% sparsity, Jaccard prototype match. This is genuinely on the connectome.
- **Conditional branching** — 16/16 and 80/80 across 5 hemibrain seeds via fuzzy weighted superposition (`fly-brain/fuzzy_conditional.py`). 4/4 distinct program mappings.
- **Bounded loops `loop[N]`** — unrolled at compile time into flat algebraic expressions. No runtime iteration. No eigenrotation. Works.
- **Eigenrotation loops (scaled eval)** — 20/20 across 5 hemibrain seeds (`fly-brain/scale_eval_loop.py`): convergence@3, counting to 3, counting to 6, ordering-first-EARLY all 5/5. Convergence iters σ=0.
- **Tier-2 bundle/bind/rotate on synthetic-weight spiking circuits** (`fly-brain/neural_vsa.py`) — Brian2 LIF, Givens R as synapse weights. Cos 0.94–0.99 vs numpy reference. Rotation R is chosen by us, not by biology.
- **Tier-2 bundle on real FlyWire wiring** (`fly-brain/neural_vsa_flywire.py`) — cos 0.94 vs W·v reference.
- **I/O rate coding** — centered rate encoding of hypervectors as PN currents, linear MBON readout via ridge regression. Works.
- **Compiler pipeline** — `sdk/sutra-compiler/` emits Python that calls `fly-brain/vsa_operations.py`. `.su` programs (e.g. `permutation_conditional.su`) compile through it.
- **End-to-end fuzzy conditional compile** — `fly-brain/fuzzy_conditional.su` → codegen → live MB simulation, 16/16 pass, 4/4 distinct program mappings (`fly-brain/test_codegen_e2e_fuzzy.py`).

## Conditional branching — FIXED

**Spec-aligned 4-way fuzzy weighted superposition hits 16/16 on toy substrate and 80/80 across 5 independent seeds on the real hemibrain (100%, σ=0).** New file: `fly-brain/fuzzy_conditional.py`. The deprecated `permutation_conditional.py` used `sign_flip(NOT_key, query)` as semantic NOT — that's a category error (a random ±1 pattern has no relationship to the "other polarity" of a feature axis), which is why Programs B/C/D averaged ~50%. Per spec 03-control-flow.md: `result = Σ w_i · branch_i` with weights from clipped cosine scores against the 4 joint prototypes. 4 programs differ only in the prototype-to-behavior map; decision pipeline is identical.

## CI pipeline state

Reverted from branch+PR to direct-master-push (commit 211bd92). The branch+PR approach failed because `GITHUB_TOKEN` cannot modify workflow files regardless of permissions config. Push-retry-with-rebase loop handles the race conditions that motivated the PR flow. Preserved the `detect-changed` full-push-range fix from bd85ce0. Cron verified working (competition-cron run 24320014564 succeeded).

## Open / Known Gaps

Currently active top-priority gap (real progress 2026-04-12):

- **Rotation from real wiring** 🟡 **FIRST POSITIVE RESULT** — surveyed 11 FlyWire motifs (`fly-brain/survey_rotation_candidates.py`). Winner: **CX EPG→EPG recurrent, 51 neurons, effective rank 49, off-diagonal fraction 0.508** — an order of magnitude closer to orthogonal than ALPN→LHLN. Polar decomposition (`fly-brain/real_rotation_epg.py`) yields Q = nearest orthogonal matrix to the real biological W, with Q^T Q = I to 1e-14, det Q = +1, norm preservation to machine precision. Adjacent-step cos ≈ -0.33 (eigenvalues on the unit circle at non-trivial angles), states are angularly distinct across iterations. Caveat: biological W is 98.3% Frobenius-distance from Q — the orthogonal operator is derived from W's SVD subspace, not equal to W. Honest framing: "rotation operator within the 51-D subspace spanned by the EPG recurrent projection, derived via polar decomposition from the real FlyWire weights." Not "the biology IS the rotation" — but not synthetic Givens either. Next: wire Q into a geometric loop test and measure whether it iterates cleanly for Sutra's `loop(condition)`.

Lower priority (still open, not blocking):

- **Conditional branching on remote substrate** — the final argmax over 4 behavior candidates and the outer loop sequencer run in host Python. Note: this is NOT the conditional branching itself; branching (choosing which of 4 prototypes matches the query) already runs on the MB via Jaccard on KC patterns. The host's job is a small 4-way readout and loop driver. Reviewer v22 conflated readout-on-host with branching-on-host; they are different. Design doc kept in `planning/open-questions/conditional-branching-on-remote.md` for when/if we want fully-autonomous execution, but not urgent.

Longer-term / lower-priority:

- **Intrinsic temporal dynamics** — the `for i in range(max_iters)` that threads ops together runs in host Python. No substrate-intrinsic trajectory yet. (User: don't need to address for this paper.)
- **Dimensionality** — 140-PN I/O is narrow vs standard VSA (1k–10k). Real limitation; KC-promotion to 1,882-D is planned but not urgent.
- **Eval size** — branching now 80/80 across 5 seeds, loops 20/20 across 5 seeds. Reviewer's residual objection is program-*template* variety (4 conditional templates, 3 loop-test types), which seeds don't buy. Open whether this matters — the paper is a primitive demonstration, not a program-library survey.
- **Biological learning rule** — MBON readout is ridge regression, not dopamine-gated plasticity. Planned, not urgent.

## Strategic notes

- **Conditional branching fully on the MB is likely paper-worthy in its own right.** `fuzzy_conditional.py` running 80/80 σ=0 on hemibrain — with the branching decision (snap + Jaccard prototype match) executed entirely on the substrate — is a standalone contribution. Probably not enough to *win* Claw4S on its own, but genuinely career-building. If the combined primitives paper doesn't land, a narrower branching-on-connectome paper is a credible fallback.
- **Reviewer v22 conflated readout with branching.** The host Python code does (a) read which of 4 behavior prototypes won a 4-way max, and (b) drive the outer loop iteration. Only (b) is real "control flow on host." (a) is readout — every biological system has readout. This distinction should be explicit in the next paper revision.

## Backlog (not urgent, pick up after paper)

Concrete work that is worth doing but not ordered into the queue. Different from `## Open / Known Gaps` (those are limitations of the current approach) and from `planning/open-questions/` (those are design decisions that need resolving before acting). Backlog items are ready to implement, just not yet prioritized.

- **Codegen V1 feature coverage** — lint sweep on 2026-04-12 found 7/13 `.su` files compile fine, 6/13 hit `CodegenNotSupported` on method decls / operator decls / `EmbedExpr` / `DefuzzyExpr` / `UnsafeCastExpr`. Paper-cited programs all compile; illustrative examples don't. Cheap wins: lower `EmbedExpr` → `basis_vector(name)`; lower `DefuzzyExpr` → `_VSA.is_true(...)` (needs matching runtime method). See `planning/open-questions/codegen-v1-feature-coverage.md` for the full breakdown and decision points.

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
