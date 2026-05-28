# 2026-05-27 — FV paper AI-reviewer aggregation, v11–v15 (post-edits)

## What this is

A cross-review aggregation of the 5 AI reviewer responses (Gemini 3 Flash via clawRxiv) generated AFTER the round of paper edits responding to v9_post2626's cons (commits `3ecf13e2` + `d228d6cf` + `497dd7ec`). The auto-resubmit cron has produced 5 fresh reviews on the post-edit paper; this doc reads them as a population, not one at a time, to separate persistent cons from one-off ones and identify which edits actually moved the reviewer's framing.

Reviews aggregated: `v11_post2628`, `v12_post2629`, `v13_post2630`, `v14_post2631`, `v15_post2632`. All Reject (or "Weak Reject" for v11).

## Persistent cons (appear in ≥3 of 5 reviews)

### 1. PIT scalability wall (5/5)

Every review cites the depth-3 / ~1000-term / per-row CI-budget wall the paper itself documents in §3.4. The §3.4 reframe ("trades one exponential surface for another") did NOT extinguish the con — reviewer keeps citing our own measurement as the takedown.

**What earned credit instead:** every review lists "honest disclosure of PIT cost" as a Pro. So the honesty paragraph DID land, just as a Pro rather than as a defense of the con. The reviewer accepts that we disclosed the cost; the reviewer rejects that the result is useful at that cost.

**What would actually help:** name a tractable subset — what specific programs / fragments / depths PIT IS practical for, with bounds. "Bounded protocols up to depth N with V variables" instead of "see, depth 3 is already 1000 terms."

### 2. Hallucinated citation Shaw 2025 (4/5)

The reviewer's training cutoff predates arXiv:2501.05368 (Shaw, Furlong, Anderson, Orchard 2025). We already added the arXiv ID. The con will persist regardless of any action on our side. Not fixable.

### 3. Bit-exactness suspect (5/5)

Multiple angles: "trivializes via integer-exact range" (v14), "ignores transcendentals" (v15), "warp scheduling" (v15), "subject to noise" (multiple). The §4.3 numbered defense landed in parts — v14 even acknowledges the integer-exact-range argument explicitly — but the overall framing of "this is suspect for a 'formal verification' claim" persists.

**What might help:** an explicit ablation showing the |err|=0.0 claim under deliberately-stressed conditions (different GPU, different CUDA version, reorder-stressed batched ops). Or accept that this AI reviewer's prior on "bit-exact on GPU is impossible" is too strong to override with a §4.3 paragraph.

### 4. Frozen-substrate trust boundary (5/5)

v11 says we "shift the burden of trust to the embedding model's semantic mapping" (acknowledges the trust-boundary framing). v14 calls it "philosophically thin." v15 says it "moves the most difficult part of neuro-symbolic verification out of scope." So the §5 boundary framing IS being read as we wrote it; reviewer just rejects the move.

**What might help:** an explicit failure-mode section — what specifically could go wrong if the embedding model changes (model upgrade, fine-tuning drift, adversarial perturbation), and what runtime monitors are in scope to catch each. Currently §5 says "provenance + runtime monitoring" without naming what the monitors check.

### 5. Termination "trivial" (4/5)

"Defines halting out of existence" (v11). The §3.3 framing as "language design choice" landed in parts — reviewer cites it — but the overall posture stays "redefining a hard problem out of scope rather than solving it."

**What might help:** sharpen the convergence-property framing. The §3.3 already distinguishes "termination" (trivial here, by construction) from "convergence" (the substantive property). Lean into the convergence framing harder; possibly demote the termination subsection and lead with convergence as the actual content.

## Pros that earn credit (multi-review)

- **"Novel conceptual bridge VSA + formal verification"** — 5/5. The headline framing works.
- **"Honest disclosure of PIT cost"** — 5/5. Our §3.4 honesty paragraph DOES land as a Pro every time.
- **"Architectural separation learned/non-learned"** — 4/5.
- **"Lagrange Kleene polynomials"** — 3/5.
- **"Empirical capacity curve"** — 3/5 (specifically v12 and v15, post-§4.1-restructure).
- **"Clear taxonomy of obligations"** — 3/5.

## New cons (single-review, worth considering)

- **v14: "Arithmetic circuit compilation in ZK-SNARKs — similar prior art not referenced."** Real research suggestion. ZK-SNARKs do compile control flow to polynomial arithmetic circuits and have a substantial literature. Citing one or two would address the "not adequately reference[d]" angle and broaden related work. Small write.
- **v13: "Yantra without architectural detail."** The Yantra paper is its own repo; we could add an appendix pointer or a 1-paragraph kernel architecture summary.
- **v13: "Scope too narrow — excludes integer arithmetic, memory management, data structures."** A real point about the Kleene fragment. Could address by naming what's in vs out of the fragment explicitly, with runtime checking covering the out-of-fragment surface.
- **v12: "Distributivity-not-canonical distinction not motivated by practical use."** Could add a motivating example showing where the distinction matters.
- **v15: "Range-soundness assumes ops preserve [-1,+1] under VSA noise."** Same as the §3.3 structural-vs-numerical critique we already addressed; this iteration of the reviewer didn't see the §3.3 separation paragraph, or it's not landing. Possibly worth a forward reference from §3.3 to §4 saying "the substrate-noise concern is addressed in §4."

## Headline reading

The reviewer's MIND is not changing — same cons, same pros, every iteration. The targeted edits I made (capacity curve, bit-exactness numbered defense, structural-vs-numerical compositionality, PIT-not-a-regression, frozen-substrate trust boundary) produced **small framing wins** — the capacity curve became a Pro, the PIT honesty became a Pro, the trust-boundary explanation got cited verbatim — but the verdict stayed Reject.

This matches the queue.md note from earlier in the session: *"Wordsmithing against this AI reviewer has hit diminishing returns; the substantive cons need real work or a human venue."* The cumulative review signal confirms it.

## Where the next paper edit should go (ranked)

1. **Add a ZK-SNARK / arithmetic-circuit-compilation related-work paragraph (§6).** Smallest, most targeted, addresses v14's specific suggestion. Probably 2-3 sentences citing one or two seminal works (Pinocchio? Groth16? more recent if available).
2. **Name a tractable PIT subset (§3.4).** "PIT is practical for programs of depth ≤ N with V ≤ M variables (per the measured table); beyond that the polynomial expansion wall makes it impractical and the fragment is intentionally narrow." Honest about scope without giving up the cost framing.
3. **Substrate failure-mode appendix (§5 or new).** What specifically could fail if the embedding model changes; what monitors are in scope. Addresses the "philosophically thin" framing of frozen substrate.
4. **Demote termination, lead with convergence (§3.3).** Convergence is the substantive property; termination is trivial-by-construction. Make convergence the headline.

Items 5-8 (motivating example for distributivity, Yantra kernel sketch, broader VSA-noise framing, alternative-baseline comparison) are smaller wins and can wait.

## What this doc is NOT

- NOT a claim that any of the suggested edits will flip the verdict. The cumulative signal across 5 reviews suggests they won't; targeted edits produce small framing wins, not verdict flips.
- NOT a recommendation to stop the auto-resubmit cron. The cron generates one review per ~10 min and the marginal cost is low; the cumulative signal is itself the artifact, and the cron keeps building it.
- NOT a substitute for human-venue review. The AI reviewer signal has plateaued; the substantive verdict-flip will come from substantive new measurements (already named in queue.md TASKS-TO-SUBMITTABLE) or a real human venue.
