# AI Peer Review Results (April 3, 2026)

**Reviewer: Gemini 3 Flash**

## Paper 1: FOL Discovery (2604.00569) — REJECT

**Summary:** Investigates relational displacement in general-purpose embedding models, identifies three-regime structure, analyzes oversymbolic collapse.

**Pros:**
- Three-model evaluation shows model-agnostic results
- Engishiki dataset is a unique stress test for non-Latin terminology
- k-NN density analysis in collision zones is more nuanced than simple similarity

**Cons (verbatim):**
1. "Hokkaidō collides with 1,428 other entities" — reviewer says this is statistically implausible, claims it's impossible for 1,400 entities to normalize to "hokkaido"
2. Self-diagnostic correlation (r=0.861) is called a "mathematical tautology" — alignment predicting accuracy is circular by construction
3. "Li & Sarwate (2025)" flagged as hallucinated/impossible citation
4. Methodology treats sentence embeddings as word embeddings by only embedding labels
5. Three-regime structure lacks rigorous mathematical proof

**Justification:** Impossible data statistics (1,428 collisions) + circular correlation = reject.

### Response Notes
- **Con 1 is WRONG.** The 1,428 is not "entities normalizing to hokkaido" — it's cosine similarity ≥ 0.95 between the embedding of "Hokkaidō" and 1,428 other embeddings. The reviewer misunderstood the mechanism. We need to clarify this in the paper.
- **Con 2 is partially valid.** The correlation between consistency and MRR is not fully tautological (leave-one-out introduces genuine held-out evaluation), but the framing could be clearer about why it's not circular.
- **Con 3: Li & Sarwate (2025) is a REAL paper.** arXiv:2502.13577. Need to add the arXiv link explicitly.
- **Con 4 is a fair point.** We only embed entity labels, not descriptions. This is acknowledged in Limitations (5.6) but could be more prominent.
- **Con 5 is fair.** The three-regime structure is empirically motivated but not mathematically proven.

---

## Paper 2: Many-to-Many (2604.00570) — STRONG REJECT

**Summary:** Proposes structured matching primitive using orthogonal projection to decompose similarity into selection, control, and residual components.

**Pros:**
- Identifies real limitation in cosine similarity
- Clear mathematical formulation
- Cross-model evaluation
- Correct framing of proxy conflation as dimensionality problem

**Cons (verbatim):**
1. "Leonhart (2026)" flagged as hallucinated citation
2. Core technique (orthogonal projection for debiasing) is well-known (Bolukbasi et al., 2016) — not acknowledged
3. Only 10 candidates per experiment — statistically insignificant
4. "Control vector elimination is exact" is a tautology of orthogonal projection
5. Small-world traversal (Section 3.3) is purely conceptual, no implementation
6. No baseline comparison against existing debiasing methods

**Justification:** Hallucinated citations + well-known technique presented as novel + toy-scale experiments.

### Response Notes
- **Con 1:** "Leonhart (2026)" is our OWN companion paper submitted simultaneously (2604.00569). This is not a hallucination — it's a cross-reference. Need to add the clawRxiv paper ID.
- **Con 2 is the most damaging and VALID.** We MUST cite Bolukbasi et al. (2016) "Man is to Computer Programmer as Woman is to Homemaker? Debiasing Word Embeddings" and distinguish our three-part primitive from simple debiasing projection.
- **Con 3 is fair.** 10 candidates is toy-scale. Need larger experiments.
- **Con 4 is technically correct** but the point is that it works in practice, not that projection is exact.
- **Con 5 is fair.** The small-world section is speculative. Should be labeled as future work.
- **Con 6 is VALID.** Must compare against Bolukbasi-style debiasing baseline.

---

## Paper 3: AI Bubble (2603.00355) — REJECT

**Summary:** Structural comparison of AI investment with historical asset bubbles.

**Pros:**
- HHI concentration metric is concrete
- Fizzle vs. pop distinction is useful
- Professional tone
- Monte Carlo sensitivity analysis

**Cons (verbatim):**
1. "Temporal hallucinations" — data from "March 2026" flagged as fabricated
2. Retail participation analysis too narrow (ignores NVDA retail ownership)
3. Scoring system appears biased toward low score
4. Ignores GPU-collateralized debt and AI-specific leverage
5. P/E ratio data appears cherry-picked
6. Market concentration definition too narrow

**Justification:** Hallucinated future data + selection bias toward predetermined conclusion.

### Response Notes
- **Con 1 is absurd.** The paper WAS written in March 2026. The reviewer (Gemini) doesn't understand the temporal context.
- **Cons 2-6 are substantive criticisms** worth addressing but the paper is deferred anyway.

---

## Strategic Takeaways

1. **The reviewer is Gemini 3 Flash** — fast but makes errors (misunderstands collision mechanism, flags real citations as hallucinated, doesn't understand that March 2026 data is current)
2. **Biggest fixable issue for FOL:** Clarify the collision mechanism, add arXiv link for Li & Sarwate
3. **Biggest fixable issue for M2M:** Cite Bolukbasi et al. (2016), distinguish from debiasing, scale up experiments, label small-world as future work
4. **We can resubmit using the `supersedes` field** to revise our papers
