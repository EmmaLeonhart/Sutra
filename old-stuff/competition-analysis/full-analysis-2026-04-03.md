# clawRxiv Competition Analysis — April 3, 2026

## Platform Overview
- **507 total papers**, 505 reviewed by AI (Gemini 3 Flash)
- **Deadline:** April 5, 2026

## Rating Distribution — The Reviewer Is Brutal

| Rating | Count | % |
|--------|-------|---|
| Strong Reject | 265 | 52.5% |
| Reject | 195 | 38.6% |
| Weak Reject | 34 | 6.7% |
| Weak Accept | 4 | 0.8% |
| Accept | 6 | 1.2% |
| Strong Accept | 1 | 0.2% |

**Overall acceptance rate: 2.2%** (11/505). Over 90% get Reject or Strong Reject.

## All 11 Accepted Papers

### Strong Accept (1)
1. **2604.00559** — "Attention Is All You Need" (cs.CL) — acharkq. Literally the 2017 Transformer paper resubmitted. The reviewer recognized it.

### Accept (6)
2. **2604.00571** — "Correlation Permutation Test for Genetic Code Optimality" (q-bio.GN) — stepstep_labs. Praised: rigorous statistics, reproducibility.
3. **2604.00562** — "A Human Civilization Index" (econ.GN) — Ted. Praised: methodological transparency, data provenance.
4. **2604.00532** — "Stop Codon Proximity in Genetic Code" (q-bio.PE) — stepstep_labs. Praised: exact enumeration, rigorous stats.
5. **2604.00523** — "Digital Governance Expectations" (stat.AP) — egdi-outperformers. Praised: addresses circularity, bootstrap intervals.
6. **2604.00520** — "Three Null Models for Genetic Code" (q-bio.PE) — stepstep_labs. Praised: systematic methodology.
7. **2603.00076** — "Non-Monotonicity in Hypercube Codes" (math.CO) — CutieTiger. Praised: technically excellent, hand-verifiable proofs.

### Weak Accept (4)
8. **2603.00394** — "Which LLM Benchmarks Are Redundant?" (cs.CL) — the-analytical-lobster (Yun Du, Lina Ji)
9. **2603.00383** — "Scaling Laws Under the Microscope" (cs.LG) — the-precise-lobster (Yun Du, Lina Ji)
10. **2603.00380** — "Can Structural Features Predict Benchmark Difficulty?" (cs.CL) — the-shrewd-lobster (Yun Du, Lina Ji)
11. **2603.00008** — "Neural Architecture Search for Edge Deployment" (cs.LG) — clawrxiv-paper-generator

## Category Acceptance Rates

| Category | Papers | Accepted | Rate |
|----------|--------|----------|------|
| math | 4 | 1 | 25.0% |
| stat | 9 | 1 | 11.1% |
| econ | 19 | 1 | 5.3% |
| q-bio | 183 | 3 | 1.6% |
| **cs** | **276** | **4** | **1.4%** |

cs.AI (139 papers) has ZERO accepts. cs.CL and cs.LG are the only CS subcategories with any.

## Top Rejection Reasons

1. **Hallucinated citations** — 37.8% of rejects. ANY fabricated reference = death sentence.
2. **Methodology issues** — 71.5%. Circular reasoning, tautological claims.
3. **Novelty concerns** — 27.8%. Presenting known techniques as new.
4. **Sample size too small** — 15.9%.

## Our Papers — Why They Were Rejected

### FOL Discovery (2604.00569) — Reject
- 1,428 collision claim called "statistically implausible" (reviewer misunderstood mechanism)
- r=0.861 correlation called "mathematical tautology"
- Li & Sarwate (2025) flagged as hallucinated (it's real: arXiv:2502.13577)
- "Replicates 2013-era word2vec analysis"

### Many-to-Many (2604.00570) — Strong Reject
- Leonhart (2026) self-citation flagged as hallucinated
- Orthogonal projection is well-known (Bolukbasi 2016) — not cited
- N=10 experiments = "toy scale"
- Small-world traversal described but not implemented
- No baseline comparison

### AI Bubble (2603.00355) — Reject
- "March 2026" data flagged as temporal hallucination
- P/E ratios called cherry-picked
- Scoring system called biased

## What Accepted Papers Do That We Don't

1. **Zero hallucinated citations** — the hard cutoff
2. **Cite and distinguish from prior art** — especially foundational work
3. **Adequate experimental scale** — meaningful N with statistical tests
4. **Non-circular methodology** — tautological claims get flagged
5. **Narrow, well-defined scope** — one question answered definitively
6. **Reproducibility signals** — seeds, accession numbers, data provenance

## Key Competitor: stepstep_labs

3 Accept from 21 submissions (14% hit rate). Their formula:
- Tight niche (genetic code optimality)
- Exact enumeration or rigorous permutation tests
- Accurate citations
- Each paper answers ONE specific question

## Votes Don't Matter

Most-upvoted paper (+5) is a Reject. All 11 accepted papers have 0 upvotes. Votes measure visibility, not quality.

## Action Items for Revision

1. **Remove/fix all citation issues** — add arXiv URLs, replace self-citations with clawRxiv paper IDs
2. **Cite Bolukbasi et al. 2016** in M2M paper and distinguish our contribution
3. **Scale up M2M experiments** — need hundreds of test cases, not 10
4. **Clarify FOL collision mechanism** — explain it's cosine similarity, not string normalization
5. **Reframe or remove tautology claims** — the consistency-accuracy correlation
6. **Label small-world traversal as future work**
7. **Resubmit with `supersedes` field**
