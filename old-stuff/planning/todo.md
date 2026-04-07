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

- [ ] **Honest FOL vs predicate logic framing.** We currently claim "first-order logic" in the title, but what we've demonstrated so far is predicate-level consistency (functional predicates as vector displacements). True FOL includes quantifiers (∀, ∃), variable binding, negation, and complex composition — none of which we test yet. instance-of (P31) at 0.244 is specifically a FOL cornerstone that fails with simple displacement. However, we believe FOL-level operations ARE possible in embedding space — they just require more complex operations than simple additive displacement. The paper should:
  1. Keep "FOL" framing — it's what we're working toward and what makes the paper interesting
  2. Be honest about what we've demonstrated (predicate-level) vs what remains to show (quantifiers, composition)
  3. Frame the gap as "the operations are more complex, not impossible" — instance-of probably needs a matrix transformation or subtype decomposition, not a single vector

- [ ] **Attempt actual FOL operations in embedding space.** The predicate-level displacements are the easy case. FOL requires harder operations that we think are possible but more complex:
  - **instance-of decomposition:** Instead of one displacement for all instance-of triples, decompose by object type. "instance-of-country" and "instance-of-person" should be separate operations with much higher consistency than the combined 0.244. This is essentially discovering that instance-of is a *family* of operations, not one operation.
  - **Negation:** If "Japan" + d_flag = "flag of Japan", does "flag of Japan" - d_flag ≈ "Japan"? Test invertibility systematically. If displacements are invertible, that's a form of negation (undoing an operation).
  - **Quantifier-like behavior:** The two-hop composition (28.3% Hits@10) is already testing ∃-like behavior — "there exists a path through the space." Can we find universal patterns? E.g., does the mean displacement for "country → flag" work for ALL countries, or only a subset?
  - **Conjunction/disjunction:** Can we combine two displacement vectors to express "has flag AND has coat of arms"? Test whether d_flag + d_coat_of_arms applied to a country lands near the right compound target.
  These are harder than simple displacement but the embedding space geometry might support them — the operations are just more complex (matrices, compositions, decompositions) rather than impossible.

- [ ] **Deeper investigation of instance-of and other hard predicates.** instance-of at 0.244 isn't just a failure — it's telling us the operation exists but requires decomposition. Test:
  - Subtype-specific analysis (instance-of-country vs instance-of-person should work individually)
  - Propositional form ("Tokyo is an instance of city" instead of just "Tokyo" → "city")
  - Contextual embeddings (embedding with description, not just label)
  Even partial success here would justify keeping "FOL" in the title.

- [ ] **Elevate the Jinmyōchō finding.** The 147,687 undersymbolic collisions aren't just a side observation — they're a practical security finding for anyone using mxbai-embed-large (or similar models) for RAG. If your RAG pipeline retrieves documents by embedding similarity, and 147,687 entity pairs are indistinguishable to the model, you will get wrong retrievals for any query involving romanized non-Latin text. This affects production systems right now. The abstract mentions it but should frame it more prominently as a practical contribution alongside the FOL discovery. Consider: "We also identify a critical failure mode for RAG systems: 147,687 cross-entity embedding collisions caused by WordPiece diacritic stripping, affecting all queries involving romanized non-Latin text."

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
