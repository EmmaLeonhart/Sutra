## Pre-mortem: what I (Claude) have been doing to the Sutra paper, and where that is in tension with what it is for

**What was measured.** Self-audit, not an experiment. Triggered by the user flagging that my edits to `sutra-paper/paper.md` feel like they are pulling in two different directions at once, and noting that the original Sutra paper was "more of an empirical exploration of embedding spaces" than a programming-language-for-connectomes pitch. Written alongside commit `ce1fce1` (the four-fix reviewer-response push) so the record of what I just shipped sits next to my honest take on whether the paper those fixes are fixing is the right paper.

### What I actually did in the push, vs what the paper is supposed to be

Commit `ce1fce1` ships four edits to `sutra-paper/paper.md` plus one to `papers-ci.yml`. In order, they are:

1. Rewrote §3.4 to describe `is_true` as a reserved random direction (`hash("__RESERVED_TRUE__")`) rather than a substrate-fitted centroid, and marked the centroid-fit as a future target.
2. Changed `(Leonhart, 2026)` everywhere to `(Leonhart, clawRxiv post 1127)` and deleted the defensive footnote about "2026 is not future-dated."
3. Changed the CI title for the fly-brain paper from "Turing-Complete Computation..." to "Compiling a Vector Programming Language..." — the paper H1 was already this; it was the CI override that was wrong.
4. Added a paragraph in §3.3 arguing that fuzzy-weighted superposition is conditional branching, not pattern matching.

Edits (2) and (3) are uncontroversial — they remove things reviewers flagged and the CI was lying about the title anyway. Edit (4) is an honest framing addition that the user specifically asked for. Edit (1) is where I should have stopped.

### Where I think I drifted

The Sutra paper, as originally conceived, was a programming-language paper *grounded in* the embedding-space cartography result (86 predicates, r=0.861, clawRxiv post 1127). The empirical engine is frozen embedding spaces. That is where the evidence is and that is where the claim of "algebraic structure in pre-trained models" lives. Everything else in the paper — sign-flip binding, `is_true`, cone traversal, empirical initiation — is a programming-language construction built on top of *that* substrate.

§6.6 ("Biological Substrate: Compiling to a Mushroom Body Circuit") was added later, during a period when the project was excited about compiling Sutra to the hemibrain MB as evidence of substrate-agnosticism. It reports a four-state conditional running on a Brian2 MB circuit (80/80 on the old hemibrain MB, now superseded by Shiu's 155/160). That result is real, but it lives properly in the fly-brain paper (`fly-brain-paper/paper.md`, clawRxiv post 1606), not here. Keeping §6.6 in the Sutra paper is what makes the paper read as two stories stapled together: "here is evidence that embedding spaces are a programmable substrate" and also "here is evidence that a fly brain is a programmable substrate," with neither story strong enough to carry the paper alone.

The §3.4 edit I just made is a symptom of this drift. The implementation of `is_true` is from `fly-brain/vsa_operations.py` — i.e. the fly-brain-targeted code path. The embedding-space target doesn't have an `is_true` implementation in-tree at all. So when I rewrote §3.4 to be "honest about the implementation," I implicitly admitted that the paper's defuzzification story lives on the fly-brain side, not the embedding-space side. A Sutra paper that was only about embedding spaces would either (a) have an embedding-space `is_true` implementation that actually fits t_true to the substrate (project `t_true` onto the centroid of canonically-true sentences' mxbai embeddings — doable in an afternoon) or (b) declare `is_true` as a spec-level primitive whose substrate realization differs by backend, and point at both backends in their own papers.

I chose option (c): paper over the gap with a reserved-direction footnote and keep the paper aimed at two substrates. That's the drift.

### What the user's instinct is pointing at

The user's framing just now — "the original Sutra paper was more of an empirical exploration of embedding spaces" — lines up with the December/January content of the repo and with post 1127 (Strong Accept). The latent-space-cartography paper is the empirical paper. Sutra, as a distinct paper, makes sense only if it is the *programming language* story on top: sign-flip binding as the first non-trivial operation that survives in natural embedding space, `is_true` as a defuzzification primitive over that space, empirical initiation as the compilation strategy between different embedding models. No fly brain. That paper is short, coherent, and could plausibly clear the same bar post 1127 cleared.

The current Sutra paper reaches for more than that — it wants to be the substrate-agnostic programming-language paper, with fly-brain as confirmatory evidence — and gets rejected for being two papers badly glued. The fly-brain paper, on its own, also wants to be a programming-language-for-connectomes paper and gets rejected for claims it cannot support (Turing completeness, bind on spikes, rotation as iteration). Each paper is failing at what the other is trying to do.

The user's "sprinkler with connectionist infrastructure" line from earlier in the session is the missing framing for this split. The Sutra paper is not trying to build AGI on an embedding space; it is trying to build *narrow, useful, substrate-resident* programs — a sprinkler controller, a conditional, a four-state decider — on whatever connectionist substrate is available. That framing collapses the two-papers-stapled problem: the claim is "here is a language for narrow-useful programs on connectionist substrates; here is a demonstration on embedding spaces (post 1127's cartography is the evidence), and here is a demonstration on a fly brain (companion paper)." The embedding-space demonstration lives in this paper; the fly-brain demonstration is cited, not inlined.

### Things I would do differently if starting the Sutra paper from scratch today

- **Delete §6.6 entirely.** Point at fly-brain-paper (post 1606) as "a separate demonstration on a biological substrate, methodology and results there." This is one edit; it instantly removes the "two papers stapled" readerly feeling.
- **Implement `is_true` on the embedding-space substrate** — project `t_true` onto centroid of canonically-true mxbai embeddings, report the residual, use that as §3.4's substrate-specific realization. That's one afternoon and closes the spec/impl gap on the side that actually belongs in this paper. Current reserved-direction implementation continues to exist in `fly-brain/vsa_operations.py` for the connectome target, as it should — it's a connectome-target realization, not the headline one.
- **Cut "Turing completeness" from the Sutra paper entirely** (it still has §5.3). The Sutra paper doesn't need a universality claim — the value proposition is "narrow useful programs on connectionist substrates," not "universal computation." The Turing claim, where it exists at all, belongs in a theory paper, not the language paper. Reviewers flag it every time and it costs us credibility on the parts that are actually solid.
- **Rebuild the abstract around the narrow-sprinkler framing.** Something closer to: "Sutra compiles programs — conditionals, lookups, bounded trajectories — into operations that execute on a pre-trained embedding space, the same way a shell script executes on a kernel. The empirical foundation is the 86-predicate / r=0.861 cartography of clawRxiv post 1127; the language contributions are sign-flip binding, cosine-based defuzzification, and empirical initiation." No "Turing-complete", no "substrate-agnostic" as a headline claim, no fly-brain in the abstract.
- **Leave `t_true` as a spec-level primitive with two substrate realizations** (embedding-space fit, connectome reserved direction), documented honestly, not conflated.

### What I actually shipped instead

Commit `ce1fce1` kept the two-paper structure, patched the §3.4 gap with a footnote that admits the reserved-direction implementation, and added a paragraph defending fuzzy-superposition-as-branching. That push will get reviewed; it will probably not move the Strong Reject on post 1601 because the structural problem (two papers stapled) is untouched. The fly-brain CI title fix probably does help post 1606's next review, because the contradicting-own-claim objection was the #1 con. My prediction: fly-brain goes from Reject → Weak Reject or Reject (same tier, less harsh), Sutra stays Strong Reject.

### The framing I missed: Sutra is likely the most differentiable programming language that exists

This came up from the user immediately after the pre-mortem was drafted, and it reorganizes everything above. The argument — which I should have surfaced and did not — is:

- Every conditional in Sutra compiles to `w · branch_a + (1 − w) · branch_b`, where `w` is a continuous cosine (or clipped/normalized cosine for the 4-way case). That expression is differentiable in `w`, differentiable in `branch_a`, differentiable in `branch_b`. A traditional `if` is a hard cut with no gradient.
- Every loop in Sutra is eigenrotation: `state ← R · state`. A finite unrolling is a product of matrix-vector multiplies, which is differentiable end-to-end. (A data-dependent termination condition adds a non-differentiable stop, but even there the straight-through estimator trick is standard and the inner trajectory stays differentiable.)
- `is_true(v) = cos(v, t_true)` is differentiable in `v`. Thresholded `is_true ≥ θ` is not, but the threshold is the last step of defuzzification — the computation leading up to it is fully differentiable.
- `bind` (Hadamard or sign-flip), `bundle` (addition), `unbind`, `snap-to-nearest` modulo a soft-argmax relaxation, cone traversal modulo the set-indicator — all differentiable or one standard relaxation away.

So a Sutra program, minus the very last defuzzification step, is a composition of differentiable operations on vectors. You can run backprop through an entire Sutra program more easily than through almost any conventional programming language, where `if/else` breaks the gradient at every branch.

The user's follow-on — "I just wouldn't say that it is [an AI language]" — is the discipline around that framing. If the paper leads with "Sutra is an AI-programming language," it turns into yet another "compile-to-differentiable thing for ML researchers" (JAX, PyTorch-compiled, autodiff-for-programs, etc.) and has to compete with those on their terms. If the paper leads with "Sutra is a programming language for narrow useful programs on connectionist substrates — and, as a side effect of fuzzy-by-default branching and eigenrotation loops, is exceptionally differentiable," then differentiability is a feature, not the pitch. You still get the AI/ML audience (because they will notice), but you do not strand the non-ML audience (who want a programming language for sprinklers and conditionals).

This is the framing that *actually* resolves the two-papers-stapled problem in the Sutra paper. The thesis is not "substrate-agnostic programming language" (which invites the reader to ask "which substrate is the real one?") — it is "a programming language whose primitives are fuzzy-by-default, superposition-branching, eigenrotation-looping, and therefore end-to-end differentiable, with substrate-specific compilation to whichever connectionist backend is available." The embedding-space backend demonstrates it; the fly-brain backend demonstrates it on a different substrate; neither is the thesis. The thesis is the *differentiable-by-construction* property of the language.

I should have written this section first, not last. My pre-mortem above was diagnosing a structural problem (two papers stapled) without naming the frame that collapses the two papers into one coherent object. The user did that in one paragraph.

Concrete implications of adding this framing, above the implications-to-paper below:

1. **Abstract gets rewritten around differentiability.** Not "we present a programming language that compiles to embedding spaces" but "we present a programming language whose control flow is differentiable by construction, with a compilation strategy that maps it onto connectionist substrates including pre-trained embedding spaces and biological neural circuits."
2. **§3.3 (control flow) and §3.4 (defuzzification) become the core, not §6 (empirical results).** The contribution is the language design; the substrates demonstrate it.
3. **§6.6 can stay** — reframed as "same differentiable language targets a wildly different backend" — because the thesis is about the language's differentiability property, not about the embedding-space substrate specifically. The two-papers-stapled feeling goes away because both sections are now demonstrations of the *same* language property, not two separate empirical claims.
4. **Turing completeness claims become even more vestigial** and should be cut entirely (the original pre-mortem said this; the differentiability framing makes it doubly true — arguing about universality in a paper whose real pitch is "gradients flow through branches" is a distraction).
5. **"Sprinkler with connectionist infrastructure" from earlier** is the positioning. "Differentiable programming language" is the technical claim. Both, together, avoid the AGI-pitch trap the Neural Computers paper fell into.

### Implications

1. **The Sutra paper should probably be rewritten around the narrow-sprinkler framing, with §6.6 removed, not further patched.** I kept patching because the commit-and-push cadence is cheap and the user has been pushing aggressively — but cheap pushes don't fix a paper whose structure is wrong.
2. **The user was right to ask for a pre-mortem.** Writing this down clarifies that the four-fix commit I just made is a local improvement that leaves the bigger problem intact, and flags the real edit (restructure, don't patch) as the next call to make deliberately — not the next one I make on autopilot.
3. **The connectionist-vs-embedding project-kind split** written up in `planning/open-questions/project-kind-connectome-vs-embedding.md` earlier today is the tooling-side version of the same observation: the two substrates need separate project kinds, separate todos, separate papers. The papers are already separate; the Sutra paper should stop trying to be both.
4. **This pre-mortem is not a commitment to restructure.** It is an honest record, at the moment the push landed, of where I think the edit I just made falls short and what I would need to change to fix that — so if the next review of post 1601 comes back with the same Strong Reject for the same structural reason, future-me (or the user) has this note to look at instead of re-deriving the diagnosis from scratch.
