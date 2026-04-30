# planning/exploratory/

Long-form research sketches for things that **might** become work later. Nothing in this directory is a commitment or an active queue item — it is a parking lot for ideas so they don't get lost in chat transcripts or session summaries.

## Rules for this directory

1. **Not a queue.** If something here becomes real work, it moves into `queue.md`'s `## Queued work` section. Being in this directory does not mean it is scheduled.
2. **Not a spec.** The formal language specification lives in `planning/sutra-spec/`. Files here are sketches, alternatives, and open questions — they may contradict the spec or each other. That is fine.
3. **User-flagged ideas only.** Add a doc here when the user has flagged something as "interesting but not now." Do not speculate into this directory unprompted.
4. **Self-contained.** Each doc should stand on its own — problem statement, why it matters, open questions, what we'd need to decide before acting. A future session (or a different contributor) should be able to pick one of these up cold.
5. **Pick up after the Claw4S deadline (2026-04-20)** unless the user says otherwise. Before the deadline, paper work dominates.

## Current contents

- `softmax-conditionals.md` — fuzzy conditional branching, softmax switches vs. classic if/elif chains, the design goal of making crisp conditionals harder to reach for than soft ones.
- `karpathy-llm-wiki.md` — Andrej Karpathy's "LLM wiki" concept, context-management angle, potential relevance to Sutra's MCP-as-runtime model. Needs web research before it becomes actionable.
- `sutra-paper-draft.md` — paper draft built around the embedding-space-as-ISA framing. Four computational novelties (beta-reduction-to-tensor-normal-form, differentiable Lagrange-polynomial fuzzy logic, eigenrotation loops, synthetic-dimension-rotation hashmaps) compose around that pillar. No venue or deadline yet; parking lot for framing and contributions list.
- `sutra-native-embedding-space.md` — the most concrete sketch of "what comes next once Sutra is mature": train an embedding space FOR computation rather than retrieval, with traversal-compositionality as the novel loss. Compute-bound; not actionable today.
