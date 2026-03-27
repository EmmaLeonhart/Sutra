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
- [ ] **Fix self-citation.** "Leonhart, 2026" referenced twice as a "working draft" that doesn't exist publicly. Either fold the relevant claims into this paper directly, or remove and replace with the three-zone taxonomy section.
- [ ] **Diversify composition examples.** Table 6 compositions all start from Tadahira — looks cherry-picked. Add examples from other entities or note this is due to the Engishiki seed.
- [ ] **Competition analysis.** Review existing Claw4S CS submissions — what they do well and poorly — to identify differentiation opportunities.
- [ ] **Reduce Wikidata import emphasis.** The brute-force BFS import was primarily for collision-hunting, not core methodology. Reframe it as data collection, not the contribution. The strategic approach to finding trajectories matters more.

### To Do — Experimental Enhancements
- [ ] **Propositional trajectory experiment.** Templates exist (13,286). Fill slots with entity labels, embed the propositions, re-run FOL discovery on propositional embeddings. Tests whether full-sentence encoding improves results for currently-failing predicates (instance-of at 0.244). The axis hierarchy finding from redoing-paper (subject 3.5x > predicate 1.0x) predicts propositional form should help.
- [ ] **Multi-model experiment (optional).** Re-run pipeline with nomic-embed-text or all-minilm. Demonstrates cross-model generalization — the key novelty claim. Change EMBED_MODEL in import_wikidata.py, run into separate data directory. 3-5 hours compute.
- [ ] **Alignment-vs-MRR scatter plot.** Generate a figure for the r=0.78 correlation. Most impactful single visual addition.

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
- [x] Full pipeline working: historical bubbles avg 5.62/6.0, AI scores 1.0/6.0
- [x] Paper draft (~250 lines) with real data tables
- [x] SKILL.md with executable review steps
- [x] FRED API integration (Case-Shiller, Federal Funds Rate)

### To Do
- [ ] **Resolve [CITATION NEEDED] markers.** ~7 in the paper. Verify Kindleberger/Minsky/Shiller editions. Some data citations (retail participation rates, IPO counts) need primary sources.
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
