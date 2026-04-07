# TODO — Neurosymbolic GraphRAG Paper

## Prototype (Done)
- [x] Knowledge base with curated corpus and ground truth
- [x] Pillar 1: Propositional extraction via DeepSeek-R1
- [x] Pillar 2: VKG construction with entity bridging
- [x] Pillar 3: Logic engine (chain search, contradiction detection, pruning)
- [x] Standard RAG baseline
- [x] Full neurosymbolic pipeline
- [x] Side-by-side demo (100% vs 75% ground truth coverage)
- [x] 7 benchmark scenarios across diverse domains
- [x] Benchmark runner with JSON export

## Experiments Completed
- [x] **Exp 1: 7-Scenario Benchmark** — NS 69% vs Std 62%, wins on entity-bridging scenarios, loses on extraction failures
- [x] **Exp 2: 5 Proposition Families** — Socrates gap (0.560), causal chain decay (0.476 endpoints), predicate blindness (0.450 mean for "inhibits")
- [x] **Exp 3: Semantic Grid (3×3×3)** — Axis hierarchy S(3.5x) > O(2.6x) > P(1.0x), clean staircase at 0/1/2 shared axes
- [x] **Exp 4: Verb Structure** — Verbs are consistent translations (0.84 alignment), subspace r=0.958, naturalness NOT encoded (r=-0.031)
- [x] **Exp 5: Word Isolation & Taxonomic Jitter** — Within-role similarity REVERSES between word-level and proposition-level; context compresses predicates, amplifies entities; hierarchy convergence is literal not graduated; distributional vs ontological semantics (dog→animal > dog→mammal)
- [x] **Exp 6: Taxonomic Direction (24 hierarchies)** — No universal "up" axis; noun "up" ≠ verb "up" ≠ adj "up"; only 4/24 monotonic; same-level words don't cluster
- [x] **Exp 7: Linnaean Taxonomy** — Consistent register does NOT fix non-monotonicity; "Animalia bounce" is universal; E. coli extreme case (Bacteria 0.806 > Enterobacterales 0.567)
- [x] **Theoretical argument: Hyperbolic embeddings won't help** — Problem is distributional, not geometric; hyperbolic space trained on same corpus inherits same biases

## Paper Draft Status (README.md)

### Sections with draft content
- [x] Abstract
- [x] Introduction (motivation, thesis, contributions)
- [x] Method — 3-pillar architecture overview
- [x] §4.1 Axis Hierarchy (S >> O >> P)
- [x] §4.2 Syllogism Gap
- [x] §4.3 Causal Chain Decay
- [x] §4.4 Predicate Blindness Across Domains
- [x] §4.5 No Universal Abstraction Axis
- [x] §4.6 Distributional vs Ontological Distance
- [x] §5 Benchmark results table and analysis
- [x] Paper structure / section outline

### Findings NOT YET in the paper draft
- [ ] Verb displacement consistency — verbs as translation vectors, not deformations (Exp 4)
- [ ] Verb-conditioned subspace preservation (r=0.958) — entity bridging is robust because verbs don't deform S/O structure (Exp 4)
- [ ] Naturalness not encoded — absurd combos sit equally within verb clusters (Exp 4)
- [ ] Compositionality is real but lopsided — S+P+O additive with unequal weights (Exp 3+4)
- [ ] Within-role similarity reversal — predicates most similar in isolation, weakest in propositions (Exp 5)
- [ ] Context compression — predicate synonyms nearly invisible in sentences (devour/eat = 0.965) (Exp 5)
- [ ] Hierarchy convergence is literal, not graduated — branches snap to identity at shared words (Exp 5+7)
- [x] Linnaean taxonomy results — register consistency doesn't fix non-monotonicity (Exp 7)
- [x] "Animalia bounce" as universal pattern (Exp 7)
- [x] E. coli extreme case — Bacteria closer than Enterobacterales (Exp 7)
- [x] Argument against hyperbolic embeddings — problem is distributional not geometric (§3g)
- [ ] Distractor trap analysis — Starbucks outscoring Brazilian drought in economic scenario
- [x] Pillar 3 finding: 0 formal chains in 2/3 winning scenarios — entity bridging alone is doing the work (in §6.1)
- [x] 16.9x time overhead analysis (in §6.4)

### Sections now drafted
- [x] Related Work — GraphRAG, neurosymbolic AI, KG embeddings, computational expressivity, System 1/2
- [x] Discussion — extraction bottleneck, FSM/dimensional cramming theory, System 1/2, tool use vs architecture, scalability, future directions
- [x] Conclusion
- [x] §4.9 Dimensional Cramming: A Unifying Theory (new subsection)

## Evaluation Gaps (needed to strengthen paper)
- [ ] Ablation study: Pillar 2 only (bridging, no logic) vs full pipeline — the data already hints bridging alone is sufficient
- [ ] Test with a better extraction model — confirm losses are component failures, not architecture failures
- [ ] Consider a public benchmark dataset for external validity

## Paper Preparation
- [ ] Choose paper title (12 candidates in `paper_names.md`)
- [ ] Set up LaTeX template (arXiv compatible)

## Polish
- [ ] Figures: architecture overview diagram, VKG example, pipeline flow
- [ ] Figures: embedding geometry visualizations (PCA projections, similarity heatmaps)
- [ ] Tables formatted for LaTeX
- [ ] Proofread and revise
- [ ] Submit to arXiv
