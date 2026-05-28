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

## Update 2026-05-28 (later): target 4 SHIPPED + REAL LEAK #10 fixed; next pick is target 3 `bundle` weights

Target 4 shipped in the SutraBarrel work-loop tick:
- Smoke: `experiments/select_temperature_smoke.py` (`a01184e3`) — orthogonal-3-class synthetic task, monotonic gradient surface across T ∈ {0.01, 0.1, 0.5, 1.0, 5.0, 100.0}.
- Full harness: `experiments/select_temperature_adjustment.py` (this tick) — mirrors equality_cosine_adjustment.py; K=3 micro-task trains baseline margin +0.0039 → +0.2796 (71.6× ratio) with T*=0.0185 and round-trip max|Δ|=2.50e-06.
- K=5/per-class=10/epochs=80/3-seeds = NEGATIVE TASK-FIT RESULT (52.9s): T trains 1.0 → -0.79, margin stays flat. Mechanism trains, but the K=5 frozen-embed-prototype task's similarity gap is too narrow for select-T to lever. Details in `planning/findings/2026-05-28-select-T-trains-but-K5-embed-task-is-flat.md`.
- Substrate-purity contribution: surfaced REAL LEAK #10 in `Audit.md` — `_select_softmax`'s `_torch.as_tensor(scores)` was detaching grad-tracked tensor scores; fixed by routing tensor scores through `_torch.stack`.

**Shipped constrain-train inventory after target 4:**
1. Equality-cosine T (`21778648`, 2026-05-26): +1.08× margin gain on K=5 embed-protos task.
2. Defuzz β (`5ca1b043`, 2026-05-28): ~15× loss reduction on β-sweep task.
3. Rank-k is_X K=2 smoke (`132c8925`, 2026-05-27): 3.01× margin improvement; K=5 sweep still in flight under last-attempt rule.
4. Select T (this tick): mechanism trainable; K=3 micro 71.6× margin ratio; K=5 task FLAT.

**Next pick: target 3, `bundle` weights.** `bundle(w_a*a, w_b*b, w_c*c)` with trained scalars per term. Adds the `bundle` operator (a VSA primitive) to the trainable inventory. Needs both a parser-level extension (weighted bundle syntax) AND a task design where bundle weighting demonstrably matters. ~4-6h estimated. After that, target 7 Kleene per-callsite coefficients (1-2 days, biggest swing).

**Alternative pre-bundle ship: a non-flat select-T task.** ~1h to construct: K random orthonormal prototypes (not embeddings) + controlled-SNR mixture queries. Would push select-T from "mechanism shipped" to "mechanism shipped + non-trivial task win." Carries less new-operator-surface impact than target 3 but is cheap insurance against the existing shipped inventory being misread as "select-T mechanism doesn't help."

### Update 2026-05-28 (third): orthogonal-protos task SHIPPED — clean +1.77× margin gain + bimodal-T finding

The "alternative pre-bundle ship" above shipped in this work-loop tick. `experiments/select_temperature_orthogonal.py` (K random orthonormal protos + alpha=0.7 / noise=0.15 mixture queries; K=5 / per-class=10 / epochs=80 / 3-seeds):
- Smoke K=3 / per-class=3 / epochs=10: baseline margin +0.3389 → trained +0.9780 (2.89× ratio), T*=0.1899, round-trip 3.58e-07.
- Full K=5 / 3-seeds at lr=0.005: baseline +0.2233 ± 0.0013 → trained +0.3955 ± 0.0016 (1.77× ratio), T*=0.6222 ± 0.0002, round-trip 3.58e-07.
- Discovery: CE surface is BIMODAL in T (global min at T≈0.1, spurious basin at T<0). The original embed-protos K=5 NEGATIVE result was partially an optimizer pathology (lr=0.05 overshoots T=0 into wrong basin), not pure task-fit. Finding doc: `planning/findings/2026-05-28-select-T-bimodal-T-surface.md`.

**Shipped constrain-train inventory after this tick:**
1. Equality-cosine T (`21778648`, 2026-05-26): +1.08× margin gain on K=5 embed-protos task.
2. Defuzz β (`5ca1b043`, 2026-05-28): ~15× loss reduction on β-sweep task.
3. Rank-k is_X K=2 smoke (`132c8925`, 2026-05-27): 3.01× margin improvement.
4. Select-T (orthogonal protos K=5, this tick): +1.77× margin gain.

**Next pick: target 3, `bundle` weights** (4-6h, needs parser change + task design). After that, target 7 Kleene per-callsite coefficients (1-2 days, biggest swing).

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
