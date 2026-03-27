# TODO — Claw4S 2026 Submission Sprint

**Deadline: April 5, 2026**

---

## CS Paper (FOL Discovery)

### Done
- [x] Core pipeline: BFS import, embedding, trajectory computation, FOL discovery
- [x] Paper draft with 7 tables of real data (86 operations, r=0.78 correlation)
- [x] SKILL.md with executable review steps
- [x] Propositional realization templates (13,286 properties with natural phrasings)
- [x] Collision analysis (164,084 cross-entity collisions at cosine >= 0.95)
- [x] Terminology fix: geodesic → trajectory throughout
- [x] Scripts moved to papers/fol-discovery/scripts/ with relative path resolution
- [x] Model-agnostic framing strengthened in intro
- [x] Terminology: geodesic → trajectory (paper, SKILL.md, docs done; scripts in progress)

### To Do — Paper Substance
- [ ] **Three-zone taxonomy in paper.** Integrate oversymbolic/isosymbolic/undersymbolic framework into Section 5 (Discussion). The collision analysis data already supports this — 164,084 collisions demonstrate the oversymbolic regime. The functional-vs-relational split maps to the isosymbolic boundary. Currently only mentioned in one line (Section 5.3).
- [ ] **VSA positioning in Related Work.** Add Section 2.5 covering Vector Symbolic Architectures and how our approach differs (we discover operations in existing spaces; VSAs construct hypervector algebras from scratch). Also mention stratified manifold work as independent validation of the three-zone idea.
- [ ] **Agent-driven literature search.** Use agents to search for prior work on model-agnostic neuro-symbolic approaches treating embedding spaces as infrastructure. Validate novelty claim. Create literature review file documenting the search process and findings — this is genuinely agentic methodology for Claw4S.
- [x] **Fix self-citation.** Removed "Leonhart, 2026" — three-zone taxonomy now presented as original contribution in this paper.
- [x] **Diversify composition examples.** Added note explaining Tadahira bias is from Engishiki seed, not method limitation.
- [x] **Competition analysis.** Full inventory of ~120+ CS submissions + Tier 1 deep dive (see competition-analysis/).
- [ ] **Resolve [CITATION NEEDED] markers in CS paper.** Specific items:
  - Kanerva (2009) and/or Plate (2003) on Vector Symbolic Architectures — find and verify
  - "Hyperdimensional Probe" paper — find the actual paper using VSAs to decode LLM representations
  - Stratified sub-manifold work — find the paper on stratified manifolds in embedding spaces
  These were identified in the strategic discussion lit review but need actual paper verification.
- [ ] **Reduce Wikidata import emphasis.** The brute-force BFS import was primarily for collision-hunting, not core methodology. Reframe it as data collection, not the contribution. The strategic approach to finding trajectories matters more.

### To Do — Experimental Enhancements (compete with resistome-profiler's 8 experiments)

**Current gap:** We have 1 model, 1 seed entity, 1 experiment. resistome-profiler has 8 experiments
with ablations. swarm-safety-lab uses 10 seeds with Bonferroni correction. We need experimental
volume and statistical rigor to match.

**Current sample sizes:** 159 predicates analyzed, 86 discovered operations, median 27 triples per
operation, only 40% have ≥30 triples. For statistical credibility, we should aim for ≥30 triples
per tested operation (the standard stats threshold for CLT assumptions).

- [ ] **Multi-model experiment (HIGH PRIORITY — key novelty claim).** Run the full pipeline on 3+ embedding models to demonstrate cross-model generalization. This is what differentiates us from all prior work. Models to test:
  - `mxbai-embed-large` (1024-dim, current) — already done
  - `nomic-embed-text` (768-dim) — `ollama pull nomic-embed-text`
  - `all-minilm` (384-dim) — `ollama pull all-minilm`
  - Optional: `bge-large-en` (1024-dim, same dim different architecture)
  Each model gets its own data directory under `papers/fol-discovery/data/`. Re-run `random_walk.py` (same seed Q1342448, same --limit 500) + `fol_discovery.py` for each. Compare: which operations are discovered across all models? Which are model-specific? The overlap is the core finding.
  **Estimated time:** ~45-60 min per model for import + ~10 min for discovery = ~2-3 hours for 3 models.

- [ ] **Increase sample size per operation.** Current --limit 500 gives median 27 triples per predicate. Raise to --limit 1000 or higher to push more predicates above 30 triples. This directly addresses the statistical rigor gap. Run with `--resume` to extend existing dataset.
  **Target:** ≥100 predicates with ≥30 triples, aiming for 100+ discovered operations. Beats swarm-safety-lab's 10 seeds/condition on raw power.

- [ ] **Multiple seed entities.** Run from 3 different seeds to show results aren't Engishiki-specific:
  - Q1342448 (Engishiki) — done
  - Q8502 (mountain) — different domain
  - Q5 (human) — maximally different
  Compare discovered operations across seeds. Operations found from all 3 seeds are robust.

- [ ] **Propositional trajectory experiment.** Templates exist (13,286). Fill slots with entity labels, embed the propositions, re-run FOL discovery on propositional embeddings. Tests whether full-sentence encoding improves results for currently-failing predicates (instance-of at 0.244). The axis hierarchy finding from redoing-paper (subject 3.5x > predicate 1.0x) predicts propositional form should help.

- [ ] **Alignment-vs-MRR scatter plot.** Generate a figure for the r=0.78 correlation. Most impactful single visual addition. Color-code by functional vs relational predicates.

- [ ] **Ablation study.** Vary the minimum triple threshold (5, 10, 20, 50) and report how discovery count and prediction accuracy change. Simple to compute from existing data, adds an "ablation" section matching resistome-profiler's experimental structure.

- [ ] **Statistical rigor matching.** For all reported metrics:
  - Report confidence intervals (not just point estimates)
  - Report effect sizes (Cohen's d equivalent for our correlation findings)
  - Run bootstrap resampling on the alignment-MRR correlation
  - Apply Bonferroni/Holm correction if making multiple claims
  This directly matches swarm-safety-lab's statistical discipline.

### Post-Deadline / Future Work
- [ ] Monthly property scanner (GitHub Actions) for keeping Wikidata properties current
- [ ] Systematic probing methodology for probe.py (5 modes exist, no systematic framework)
- [ ] Cross-model transformation matrix transfer (do matrices from model A work on model B?)
- [ ] Invertibility testing (can operations be undone by applying -d?)
- [ ] Controlled sentence corpus experiments (3x3x3 semantic grid from redoing-paper)

---

## Economics Paper (AI Bubble)

### Done
- [x] Data collection scripts (bubble data, AI investment, structural comparison)
- [x] Full pipeline working: historical bubbles avg 5.62/6.0, AI scores 0.5/6.0
- [x] Paper draft (~250 lines) with real data tables
- [x] SKILL.md with executable review steps
- [x] FRED API integration (Case-Shiller, Federal Funds Rate)
- [x] Scoring made data-driven (not hardcoded conclusions)
- [x] Figures generated (structural heatmap, market performance)
- [x] PDF generation script

### To Do
- [ ] **Resolve [CITATION NEEDED] markers.** Specific items to verify:
  - Kindleberger & Aliber (2005) "Manias, Panics, and Crashes" — verify it's the 5th edition, Wiley publisher
  - Minsky (1986) "Stabilizing an Unstable Economy" — verify Yale University Press
  - Online brokerage account growth (1.5M to 9.7M, 1997-2000) — find SEC/FINRA primary source
  - IPO counts (486 in 1999) — find Jay Ritter's IPO data or alternative source
  - NASDAQ median P/E exceeding 100 — find Shiller P/E database or similar
  - Housing price 70% above trend — find Case-Shiller price-to-rent historical data
  - FCIC Report leverage data — verify specific pages/chapters
  - NFT $25B annual sales (2021) — find DappRadar or NonFungible.com annual report
  - DeFi leverage data — find DeFi Llama TVL historical data
  - Training cost estimates ($100M-$1B+) — find Stanford AI Index or similar
  - Private company valuations (OpenAI ~$157B, Anthropic ~$61.5B, xAI ~$50B) — verify current figures via Crunchbase/PitchBook
- [ ] **Review for consistency.** Ensure all tables match the data files. Cross-check numbers.
- [ ] **Test SKILL.md end-to-end.** Run from clean checkout, verify all steps produce expected output.

---

## Shared / Repo

### Done
- [x] Repo reorganized: each paper self-contained in papers/
- [x] Both papers have paper.md + SKILL.md
- [x] README and CLAUDE.md updated for two-paper structure

### To Do
- [ ] **Final review pass on both papers.** Read critically for consistency, missing data, unresolved markers.
- [ ] **Submit to clawRxiv.** Push final versions, submit both papers.
