# TODO — Claw4S 2026 Submission Sprint

**Deadline: April 5, 2026**

---

## CS Paper (FOL Discovery)

### Done
- [x] Core pipeline: BFS import, embedding, trajectory computation, operation discovery
- [x] Paper draft with 9 tables of real data
- [x] SKILL.md with 9 executable steps
- [x] Propositional realization templates (13,286 properties with natural phrasings)
- [x] Collision analysis (164,084 cross-entity, 147,687 genuine semantic)
- [x] Terminology fix: geodesic → trajectory throughout (including geodesics.ttl → trajectories.ttl)
- [x] Scripts moved to papers/fol-discovery/scripts/ with relative path resolution
- [x] Model-agnostic framing strengthened in intro
- [x] Three-zone taxonomy (oversymbolic/isosymbolic/undersymbolic) in Section 5.3 with Jinmyōchō data
- [x] VSA positioning in Related Work (Section 2.5)
- [x] Self-citation fixed (Leonhart 2026 removed, three-zone taxonomy is now original contribution)
- [x] Composition examples bias explained (Tadahira = seed artifact)
- [x] Competition analysis: full inventory + Tier 1 deep dive
- [x] Multi-model experiment: 3 models (mxbai 1024d, nomic 768d, minilm 384d), 30 universal operations
- [x] Statistical rigor: bootstrap CIs, Cohen's d, Bonferroni correction
- [x] Ablation study: min-triple threshold sensitivity
- [x] Scatter plot + 7 figures total
- [x] PDF generation with embedded figures (12 pages)
- [x] Cross-model comparison script + figure
- [x] Li et al. (2024) glitch token citation added
- [x] Author name fixed: Emma Leonhart

### To Do — Paper Substance

- [ ] **Honest FOL vs predicate logic framing.** We currently claim "first-order logic" in the title, but what we actually demonstrate is predicate-level consistency (functional predicates as vector displacements). True FOL includes quantifiers (∀, ∃), variable binding, negation, and complex composition — none of which we test. instance-of (P31) at 0.244 is specifically a FOL cornerstone that fails. Options:
  1. Reframe as "predicate logic operations" or "relational operations" — more honest
  2. Keep "FOL" but add explicit caveats about what we do and don't test
  3. Argue that discovering which predicates encode as displacements IS a FOL discovery (about what the space can represent)
  Need to decide and update title, abstract, and framing accordingly. This is important — overclaiming will hurt credibility with reviewers.

- [ ] **Deeper investigation of instance-of and other hard predicates.** instance-of at 0.244 isn't just a failure — it's a measurement of how far the space is from encoding FOL's most fundamental operation. Can we improve it with:
  - Propositional form ("Tokyo is an instance of city" instead of just "Tokyo" → "city")
  - Subtype-specific analysis (instance-of-country vs instance-of-person might work individually)
  - Contextual embeddings (embedding with description, not just label)
  Even partial success here would strengthen the FOL claim significantly.

- [ ] **Agent-driven literature search.** Create lit review documenting search process and findings — genuinely agentic for Claw4S.

- [ ] **Resolve [CITATION NEEDED] markers:**
  - Kanerva (2009) / Plate (2003) on VSAs
  - "Hyperdimensional Probe" paper
  - Stratified sub-manifold work

- [ ] **Reduce Wikidata import emphasis.** Reframe BFS as data collection, not the contribution.

### To Do — Experimental Enhancements

- [ ] **Multilingual experiments.** Run pipeline with non-English Wikidata labels on multilingual embedding models. Priority tests:
  - Japanese labels on multilingual-e5-large or similar — does the undersymbolic diacritic collapse disappear when using a model trained on Japanese?
  - Languages with case systems (Finnish, German, Latin) — do grammatical cases produce different displacement patterns for the same semantic relationships?
  - Compare: do the same 30 universal operations appear across languages, or are some language-specific?
  This requires a multilingual Ollama model (e.g., `multilingual-e5-large` or `bge-m3`).

- [ ] **Derive transformation matrices.** Currently we only compute additive displacements (d = embed(object) - embed(subject)). The richer model: embed(proposition) = embed(subject) + M * embed(predicate) where M is a transformation matrix. Compute M via least squares across examples. Test:
  - Does M improve prediction over simple displacement?
  - Is M invertible? (Can you recover subject from object + inverse M?)
  - Do case-system languages produce different M matrices for the same semantic relationship?

- [ ] **Increase sample size.** --limit 1000+ to push more predicates above 30 triples (CLT threshold).

- [ ] **Multiple seed entities.** Q8502 (mountain), Q5 (human) — robustness check across domains.

- [ ] **Propositional trajectory experiment.** Templates ready. Test full-sentence encoding vs label-only.

### Post-Deadline / Future Work
- [ ] Monthly property scanner (GitHub Actions)
- [ ] Systematic probing methodology for probe.py
- [ ] Cross-model transformation matrix transfer
- [ ] Invertibility testing
- [ ] Controlled sentence corpus (3x3x3 semantic grid from redoing-paper)

---

## Economics Paper (AI Bubble)

### Done
- [x] Data collection scripts (bubble data, AI investment, structural comparison)
- [x] Full pipeline working: historical bubbles avg 5.62/6.0, AI scores 0.5/6.0
- [x] Paper draft with real data tables
- [x] SKILL.md with executable review steps
- [x] FRED API integration (Case-Shiller, Federal Funds Rate)
- [x] Scoring made data-driven (computed from retrieved data, not hardcoded)
- [x] Figures generated (structural heatmap, market performance)
- [x] PDF generation script
- [x] Author name fixed: Emma Leonhart

### To Do
- [ ] **Resolve [CITATION NEEDED] markers.** Specific items:
  - Kindleberger & Aliber (2005) — verify 5th edition, Wiley
  - Minsky (1986) — verify Yale University Press
  - Online brokerage growth (1.5M to 9.7M) — SEC/FINRA primary source
  - IPO counts (486 in 1999) — Jay Ritter's IPO data
  - NASDAQ median P/E > 100 — Shiller P/E database
  - Housing price 70% above trend — Case-Shiller price-to-rent
  - FCIC Report leverage data — verify pages
  - NFT $25B (2021) — DappRadar annual report
  - DeFi leverage — DeFi Llama TVL
  - Training costs ($100M-$1B+) — Stanford AI Index
  - Private valuations (OpenAI, Anthropic, xAI) — Crunchbase/PitchBook
- [ ] **Review for consistency.** Tables match data files, numbers cross-checked.
- [ ] **Test SKILL.md end-to-end.** Clean checkout test.

---

## Shared / Repo

### Done
- [x] Repo reorganized: each paper self-contained in papers/
- [x] Both papers have paper.md + SKILL.md + figures + PDF
- [x] README and CLAUDE.md updated
- [x] Competition analysis with Tier 1 deep dive
- [x] Literature review pages for both papers

### To Do
- [ ] **Final review pass on both papers.**
- [ ] **Cold-start test both SKILL.md files.** Clone fresh, run from scratch. Critical — alchemy1729 audit found 94% fail.
- [ ] **Submit to clawRxiv.**
