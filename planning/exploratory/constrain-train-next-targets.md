# Constrain-train — next targets, ranked

**Date:** 2026-05-27, updated 2026-05-28.
**Status:** Planning. Picks the next SHIPPED constrain-train instance and the order behind it. Per Emma's "every operation trainable" vision, the next target should *expand the trainable surface to a new operator*, not polish the equality-cosine instance.

## Update 2026-05-28: defuzz β SHIPPED; next pick is `select` softmax temperature

The 2026-05-27 doc picked defuzz β as the next ship. **That landed today** (`5ca1b043`). Measured:
- baseline loss 0.2126 ± 0.0114 → trained loss 0.0146 ± 0.0050 (~15× reduction)
- β* = 6.58 ± 0.17 across 3 seeds (real task optimum, low variance)
- round-trip max|Δ| = 1.19e-7 (bit-exact within float32 precision)

Path taken: (a) the cosine `==` wrapper-gain was diagnosed as scale-invariant (`85429dfd`), so the original "expose β at Sutra level" reframed as "the actual β IS inside `defuzzify_trit`, expose THAT"; (b) added `intrinsic function fuzzy defuzzify_trit(fuzzy v, number iters, number beta);` to stdlib/logic.su (`ffd085de`); (c) per Emma's `AskUserQuestion` Option-1 choice, made iters runtime-variable so the loss surface isn't step-shaped at iters=10 (`5ca1b043`). Documentation caught up in `73c995fc` (capabilities.md).

**Shipped constrain-train inventory after today:**
1. Equality-cosine T (`21778648`, 2026-05-26): +1.08× margin gain.
2. Defuzz β (`5ca1b043`, 2026-05-28): ~15× loss reduction.
3. Rank-k is_X (K=5 sweep `bwf96wgym` in flight 2026-05-28; K=2 smoke `132c8925` verified 3.01× margin improvement).

**Next pick per the original ranking: target 4, `select` softmax temperature.** Concrete because (a) `select` is the language's softmax/case-switch primitive — high-leverage; (b) the Sutra-level surface change is "wrap the scores in a divide" rather than a new parser form, smaller than (3) `bundle` weights; (c) the training task is just rerouting any existing classification harness to use a divided-score variant of select. ~3-4 hours estimated. After that, target (3) `bundle` weights, then target (7) Kleene per-callsite coefficients (the biggest swing, 1-2 days).

The ranking below is preserved as the original 2026-05-27 analysis. Read with the update above in mind.

---

## The constraint

Equality-cosine adjustment took ~2.7 hours of GPU time (substrate-pure training on 768-d nomic embeddings, 5-class classification). Rank-k is similar order. So we get **one substantial constrain-train run per session** in practice. The decision of "which one to run next" is therefore weight-bearing.

## Candidates, ranked by what each *adds to the trainable surface*

### 1. Defuzz sharpening β as a trainable Sutra parameter ⭐ RECOMMENDED NEXT

Currently `defuzzify_trit(v, iters=10, beta=2.0)` has a hardcoded sharpening rate β = 2.0 at the runtime. There is no Sutra-source-level way to override β per call site. The vision "every operation trainable" requires that **β be exposable as a Sutra-level number**.

Two-step ship:
1. **Add `defuzzy(v, number beta)` overload at the Sutra level** (parser/validator/codegen). Backwards-compatible: 1-arg `defuzzy(v)` stays valid, threads in the default β = 2.0.
2. **`experiments/defuzz_beta_adjustment.py`** — train β on a polarization task (given fuzzy inputs with known target polarizations on the truth axis, learn the β that minimizes polarization error). Bake the trained β back as a numeric literal. Round-trip check.

Operator surface added: **`defuzzy`** (was untrained today). Different from `==` cosine because defuzz is the *polarizer*, not the *comparison*. The shipped pattern would prove that the constrain-train mechanism generalizes from comparison operators to polarization operators.

Estimated effort: ~3-4 hours for the parser/codegen change (small, well-scoped), then a CPU-runnable training loop (defuzz polarization doesn't need 768-d embeddings; can run on synthetic truth-axis data). The training itself is much faster than equality-cosine because no embeddings are involved.

Honest scope: depends on getting the parser/codegen change right. If the codegen routing for the 2-arg form turns out to be more invasive than expected, fall back to candidate 2.

### 2. Per-class temperature T_i in is_X (extension of equality cosine)

Train K scalars (one per class) instead of the global T trained by the equality-cosine adjustment. Same harness, K times the parameters.

Operator surface added: *None new* — this is the same equality-cosine surface generalized from 1 to K parameters. Per the "expand trainable surface" framing, this is **polishing, not expanding**. Listed here as the safe fallback in case (1) hits parser/codegen friction.

Estimated effort: ~30 minutes to fork equality_cosine_adjustment.py + ~3 hours of GPU training.

### 3. Bundle weights — `bundle(w_a*a, w_b*b, w_c*c)`

Today `bundle(a, b, c)` is uniform (`(a+b+c)/3` + L2 normalize). A trained-weight version is `(w_a*a + w_b*b + w_c*c)` + L2 normalize where `w_*` are trained scalars per bundle term.

Operator surface added: **`bundle`** (was untrained — VSA core primitive, one of bind/unbind/bundle/similarity). High-leverage because bundle weights are how a substrate-side "attention" emerges naturally.

Estimated effort: ~4-6 hours including the new Sutra surface for weighted bundles and a task where bundle weighting demonstrably matters (e.g., "this bundle component is the actual answer; this one is distractor noise" — supervised attention).

Honest scope: needs both a parser-level extension (weighted bundle syntax) AND a task design. Bigger than (1). Worth doing AFTER (1) lands as the proof of mechanism.

### 4. Softmax temperature inside `select`

The `select([scores], [options])` primitive softmaxes the scores before weighting. A trainable temperature `select_softmax(scores / T, options)` would let downstream tasks sharpen or soften the decision per call site.

Operator surface added: **`select`** (was untrained). Important because `select` is the language's softmax / case-switch primitive.

Estimated effort: ~3-4 hours. Smaller than (3) because the Sutra-level surface is "wrap the scores in a divide" rather than a new parser form — train a scalar T, baked back as a numeric literal that divides the score list.

### 5. Per-callsite cosine adjustment inside `similarity`

Already addressed indirectly by equality_cosine_adjustment (which trains T scaling the cosine *output*). Listed here for completeness as the path of least resistance for "yet another scalar somewhere in the cosine pipeline." NOT recommended as the next ship; redundant with (1) and (2).

### 6. Per-loop max_iters

Each declared loop has a fixed `max_iters`. A trainable per-loop iter count could pick the bound from data.

Operator surface added: **the soft-halt loop's bound** — a structural parameter, not just a value.

Estimated effort: ~5-7 hours; the loop machinery does not currently take a trainable max_iters (it's a literal compile-time constant in the unroll). Either (a) make max_iters dynamic (harder), or (b) train across discrete max_iters values and pick the best — less satisfying.

Defer.

### 7. Kleene connective polynomial coefficients per call site

The biggest swing on this list. Train the 6 coefficients of `a&&b = (a+b+ab−a²−b²+a²b²)/2` separately per call site, with the {-1, 0, +1} grid exactness as a regulariser. This would land in the FV paper as "per-callsite connective specialization."

Operator surface added: **the Kleene connectives themselves** (`&&`, `||`, `!`) — currently fixed by Lagrange interpolation.

Estimated effort: 1-2 days. Touches the codegen's connective lowering, needs a regulariser-aware training loop, needs measurement against the grid-exactness FV claim. Big and high-impact; defer as the dedicated session's worth of work.

## The decision

**Ship target (1) next.** β-as-trainable-Sutra-parameter is the cleanest "new operator surface" instance, smallest parser/codegen change, fastest training loop (no embeddings needed). It directly demonstrates Emma's "every operation trainable" vision because **today `defuzzy` has zero trainable parameters from the Sutra surface; after this lands, it has one**.

When (1) ships, the queue advances to (4) `select` temperature, then (3) `bundle` weights, then (7) Kleene coefficients per call site. Each cumulatively expands the inventory in `docs/capabilities.md` from one SHIPPED row to several.

## What goes into queue.md

A pinned item: "Next constrain-train ship: defuzz β as Sutra-level parameter (see `planning/exploratory/constrain-train-next-targets.md`). Fires when GPU frees from K=5."
