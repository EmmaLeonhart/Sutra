# planning/exploratory/

Long-form research sketches for things that **might** become work later. Nothing in this directory is a commitment or an active queue item — it is a parking lot for ideas so they don't get lost in chat transcripts or session summaries.

## Rules for this directory

1. **Not a queue.** If something here becomes real work, it moves into `queue.md`'s `## Queued work` section. Being in this directory does not mean it is scheduled.
2. **Not a spec.** The formal language specification lives in `planning/sutra-spec/`. Files here are sketches, alternatives, and open questions — they may contradict the spec or each other. That is fine.
3. **User-flagged ideas only.** Add a doc here when the user has flagged something as "interesting but not now." Do not speculate into this directory unprompted.
4. **Self-contained.** Each doc should stand on its own — problem statement, why it matters, open questions, what we'd need to decide before acting. A future session (or a different contributor) should be able to pick one of these up cold.
5. **Pick up after the Claw4S deadline (2026-04-20)** unless the user says otherwise. Before the deadline, paper work dominates.

## Current contents

- `2026-05-17-voice-vision-transcendental-constants.md` — verbatim relocation of the "super active" voice-vision block from `queue.md`: transcendental constants, cosine-as-its-own-function, GPU-primitive framing.
- `constrain-train-next-targets.md` — ranked next targets for the constrain-train ("every operation trainable") vision; picks which operator to expand the trainable surface to next rather than polishing the equality-cosine instance.
- `demo-program-queue.md` — seven demo programs reachable with Sutra's current primitive set (`bundle`, `bind`, `unbind`, `similarity`, `argmax_cosine`, etc.).
- `eigenrotation-for-sine-and-modulus.md` — eigenrotation as exact sine/cosine/modulus; mathematical insight validated, cost the open question.
- `karpathy-llm-wiki.md` — Andrej Karpathy's "LLM wiki" concept, context-management angle, potential relevance to Sutra's MCP-as-runtime model. Needs web research before it becomes actionable.
- `object_matrix_probe.py` — probe script testing whether a learnable linear "object-of-sentence" role matrix exists in nomic (evidence for/against roles-as-learned-matrices).
- `softmax-conditionals.md` — fuzzy conditional branching, softmax switches vs. classic if/elif chains, the design goal of making crisp conditionals harder to reach for than soft ones.
- `subject_object_matrix_probe.py` — companion probe for subject/object role matrices in the embedding space.
- `sutra-as-math-language.md` — positioning material for Sutra as a numerical / finance language, not just an AI language.
- `sutra-language-comparisons.md` — working reference comparing language shapes, syntax tradeoffs, and semantic defaults before committing to Sutra forms.
- `sutra-native-embedding-space.md` — the most concrete sketch of "what comes next once Sutra is mature": train an embedding space FOR computation rather than retrieval, with traversal-compositionality as the novel loss. Compute-bound; not actionable today.
- `tnf-vs-constant-folding-explanation.md` — the compiled tensor-op-graph vs constant-folding ontological framing. **SUPERSEDED 2026-05-25** (the "tensor normal form" / "TNF" term was removed from active specs, docs, and the FV paper); kept as history.
