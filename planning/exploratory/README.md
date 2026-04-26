# planning/exploratory/

Long-form research sketches for things that **might** become work later. Nothing in this directory is a commitment or an active queue item — it is a parking lot for ideas so they don't get lost in chat transcripts or session summaries.

## Rules for this directory

1. **Not a queue.** If something here becomes real work, it moves into `STATUS.md`'s `## Queued work` section. Being in this directory does not mean it is scheduled.
2. **Not a spec.** The formal language specification lives in `planning/sutra-spec/`. Files here are sketches, alternatives, and open questions — they may contradict the spec or each other. That is fine.
3. **User-flagged ideas only.** Add a doc here when the user has flagged something as "interesting but not now." Do not speculate into this directory unprompted.
4. **Self-contained.** Each doc should stand on its own — problem statement, why it matters, open questions, what we'd need to decide before acting. A future session (or a different contributor) should be able to pick one of these up cold.
5. **Pick up after the Claw4S deadline (2026-04-20)** unless the user says otherwise. Before the deadline, paper work dominates.

## Current contents

- `softmax-conditionals.md` — fuzzy conditional branching, softmax switches vs. classic if/elif chains, the design goal of making crisp conditionals harder to reach for than soft ones.
- `karpathy-llm-wiki.md` — Andrej Karpathy's "LLM wiki" concept, context-management angle, potential relevance to Sutra's MCP-as-runtime model. Needs web research before it becomes actionable.
- `claw4s-paper-compile-time-vsa.md` — paper draft for the 2026-04-30 Claw4S window. Thesis: Sutra's compile-time beta reduction sidesteps the runtime VSA-lambda-calculus problem that the Flanagan / "Hey Pentti" line tackles inside the substrate. Four computational novelties (differentiable fuzzy logic, beta-reduction-to-tensor-normal-form, eigenrotation loops, synthetic-dimension rotation hashmaps). Has a target deadline; promote out of exploratory if it goes from outline to prose.
