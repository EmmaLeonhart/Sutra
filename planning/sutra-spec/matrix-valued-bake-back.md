# Matrix-valued bake-back — lean spec for matrix-valued constrain-train targets

**Status:** Draft 2026-05-26. Resolves the "matrix-literal spec decision" blocker from `todo.md` §"Agentic RAG for constrained-training design" via the leanest viable path (Emma 2026-05-26: "Lean").

## The question

The matrix-valued constrain-train targets — `is_X`, defuzz matrix, learned-matrix binding — were blocked on "matrix literals in `.su` don't exist yet; spec decision needed before scaffolding." The implied design space was first-class `matrix X = ...;` syntax with some literal form.

## Decision: defer first-class `matrix` literals; express matrix-valued bake-back as composition of existing primitives

The leanest viable design for matrix-valued bake-back avoids introducing matrix literals to the language at all. Rationale:

1. **A dense `dim × dim` matrix is too big for source-code legibility.** At 768-d, that's ~590k float literals per matrix — 3–6 MB of source per baked `is_X`. The Stage-B "trained model IS legible source" property breaks.
2. **Real learned matrices in this space are structured, not dense.** Low-rank (`U·V^T`), sparse, diagonal-plus-low-rank, or seed-generated. The lean bake-back form should match the structure, not unconditionally serialize dense.
3. **Rank-1 is already expressible.** A rank-1 `is_X` matrix is `u · v^T`; applied to `x` gives `u · dot(v, x)` — a scaled direction in the embedding space. The truth-axis scalar `(u · v^T · x)` projected to the truth axis is just `dot(v, x)`. **Stage-B's trained prototype vector + scalar gain is exactly the rank-1 case of "trained is-X matrix."**
4. **Higher-rank reduces to a list of vectors + scalars.** A rank-k `is_X` is `sum_i (u_i · v_i^T)`; applied to `x` it's `sum_i u_i · dot(v_i, x)`. Expressible with current Sutra syntax: declare `v_1...v_k` as vector parameters or vector literals; the `is_X` function is `bundle(...)` over `dot(v_i, x) * u_i`.

## What this means for the constrain-train targets

| Target | Lean encoding (no new syntax needed) |
|---|---|
| **`is_X` rank-1** | A prototype vector `v_X` + a scalar gain `T`. **= Stage-B already.** |
| **`is_X` rank-k** | `k` prototype vectors `{v_1...v_k}` + (optionally) `k` output-direction vectors `{u_1...u_k}` + `k` scalar gains. All bake back as Sutra vector / scalar literals using existing primitives. |
| **Defuzz matrix (acting on truth axis)** | The truth axis is a single canonical axis; "defuzz matrix" applied to a fuzzy scalar reduces to a polynomial in that scalar. Bake back as the trained polynomial coefficients (scalar literals) — no matrix literal needed. |
| **Learned-matrix binding (rotation/role matrices)** | Already mostly first-class via the rotation-binding runtime (slot rotations). For learned semantic binds, the natural surface is `role X = learned_from(data)` (see todo.md §"Learned-matrix binding") — the compiler fits the matrix at compile time from `(input, output)` embedding pairs, no in-source matrix literal needed. |

The common pattern: matrix-valued parameters bake back as **lists of vectors + lists of scalars** consumed by composition, not as a dense matrix literal.

## What we DO need (smaller surface changes)

1. **Vector-of-floats literal in `.su`.** Currently vectors are constructed via `basis_vector("name")`, `bundle(...)`, `embed(...)` — there's no `vector v = [0.123, -0.045, ...];` form. A vector-of-floats literal is necessary for baking back trained vectors that aren't `embed(word)` of a known anchor. Surface: `vector v = vector_literal([0.123, -0.045, 0.312, ...]);` using an existing constructor-call shape (no new grammar). Codegen: `_VSA.vector_from_floats([...])` which builds a `torch.tensor([...])` on the substrate's device.
2. **Existing `bundle`, `similarity`, scalar-multiply suffice for rank-k composition.** No new primitives needed.

## What we explicitly DON'T do

- No new `matrix` declaration grammar. `matrix X = ...;` stays not-accepted.
- No nested-array literals (`[[a,b],[c,d]]`).
- No new substrate primitives for matrix-matrix multiplication on the bake-back path.
- No matrix-as-file-reference. Trained values stay inline in the `.su`.
- No premature compile-time learned-matrix-fitting machinery for the constrain-train targets. The fitting is a separate spec (see todo.md §"Learned-matrix binding").

## Open follow-ups (not blockers)

- **A vector-of-floats literal in `.su`** is the one small surface change this decision requires. Implementing it: add a `vector_literal(list_of_numbers)` builtin to the codegen, emitting `torch.tensor([...])` on the substrate. Estimated effort: a few hundred lines, an Audit.md verifier note, and round-trip tests. This is the smallest concrete prerequisite for the rank-k `is_X` experiment.
- If a real use case emerges where dense `dim × dim` matrices genuinely need source-form bake-back, reopen this doc and design a proper matrix-literal grammar with the use case in hand. Until then, the lean composition is sufficient.

## Cross-links

- Stage-B precedent (rank-1 = prototype + scalar): `planning/findings/2026-05-18-differentiable-training-is-a-proxy-not-compiled.md` § "Cron fire 9"
- Equality cosine adjustment (same shape, isolated): `experiments/equality_cosine_adjustment.py`
- T-placement decision (same lean principle): equality-cosine-T-placement (pruned 2026-05-28; in git history)
- Constrain-train agenda the unblock feeds: `todo.md` §"Agentic RAG for constrained-training design" + §"Constrained Adam + FV-linked training + NN→code decompilation"
- Learned-matrix binding (still its own agenda; this doc doesn't replace it): `todo.md` §"Learned-matrix binding"
