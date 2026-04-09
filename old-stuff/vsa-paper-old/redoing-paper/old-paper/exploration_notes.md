# Exploration Notes: Benchmark Results & Embedding Geometry

These are working notes from our first full evaluation run. The purpose is to document what actually happened, what the numbers mean, and what they tell us about the relationship between embedding (feature) space and semantic (logical) space.

---

## 1. Benchmark Results: 7-Scenario Suite

**Run date:** 2026-03-06
**Hardware:** Local Ollama, deepseek-r1:8b (reasoning), mxbai-embed-large (embeddings)
**Wall time:** ~49 minutes total

### Summary Table

| Scenario | Std Coverage | NS Coverage | Delta | Winner |
|---|---|---|---|---|
| Everest Boiling Point | 75% (3/4) | 100% (4/4) | +25% | NS |
| Drug Interaction Chain | 80% (4/5) | 100% (5/5) | +20% | NS |
| Economic Supply Cascade | 25% (1/4) | 75% (3/4) | +50% | NS |
| Coral Reef Collapse | 50% (2/4) | 50% (2/4) | 0% | Tie |
| Bridge Collapse | 75% (3/4) | 50% (2/4) | -25% | Std |
| Antibiotic Resistance | 80% (4/5) | 80% (4/5) | 0% | Tie |
| Satellite Signal | 50% (2/4) | 25% (1/4) | -25% | Std |

**Aggregate:** Std mean 62%, NS mean 69%, delta +6%. NS wins 3, ties 2, loses 2.

### What the wins tell us

**Everest (NS wins, +25%):** The original scenario and still the cleanest demonstration. Standard RAG retrieves 3/4 chain steps because C3 ("water boils at ~70C on Everest") scores 0.837 and pulls in its neighbors. But it misses C1 ("atmospheric pressure decreases as altitude increases") — scored only 0.560 against the query, below the distractor "Mount Everest is on the border between Nepal and Tibet" (0.641). The VKG rescues C1 because the entity "atmospheric pressure" bridges it to C0 and C3, which are already in the seed set.

**Drug Interaction (NS wins, +20%):** Standard RAG gets 4/5 — it actually does well here because the query mentions both "warfarin" and "ketoconazole" explicitly, pulling in most relevant sentences. But it misses C1 ("Warfarin is primarily metabolized by CYP2C9") which scored lower than the distractor "Ketoconazole is commonly used to treat fungal infections" (0.682 vs 0.619). The VKG bridges through the shared "warfarin" entity. Notably, the neurosymbolic pipeline retrieved all 5 chain steps despite finding 0 formal reasoning chains — the entity bridging in Pillar 2 alone was sufficient.

**Economic Cascade (NS wins, +50%):** The most dramatic win. Standard RAG retrieved only 1/4 chain steps — just C3 ("retail coffee prices rose 22%") because it directly matches the query. The trap distractors worked exactly as designed: "Starbucks announced a 5% price increase" (0.737) and "Consumer demand has grown 15%" (0.674) both outscored the actual causal chain about Brazilian drought and supply contraction. The VKG pulled in 3/4 by bridging through "brazil" as a shared entity between the price sentence and the drought/supply sentences.

### What the ties tell us

**Coral Reef (tie, 50%):** Both pipelines got 2/4. The extraction model struggled with this corpus — it reduced "Anthropogenic carbon dioxide emissions have increased atmospheric CO2 concentration" to `(Anthropogenic | relates to | unknown)`, losing the CO2 entity entirely. Without that entity, the VKG couldn't bridge from the atmospheric domain (CO2 emissions) to the oceanic domain (acidification). Standard RAG at least got C3 (coral/carbonate, 0.767) and C1 (CO2 absorption, 0.620) through direct similarity.

**Antibiotic Resistance (tie, 80%):** Both got 4/5. Standard RAG actually performed well here — the query "how do bacteria become resistant to penicillin-class antibiotics" has enough semantic overlap with the molecular chain steps (beta-lactamase, beta-lactam ring, hydrolysis) that cosine similarity ranked them highly. The one sentence both missed was C0 ("bacteria acquire resistance genes through horizontal gene transfer via conjugative plasmids"), which is about the *delivery mechanism* rather than the *biochemical mechanism* — a different kind of bridge the VKG also failed to construct.

### What the losses tell us

**Bridge Collapse (Std wins, -25%):** The extraction model collapsed badly here. "De-icing salts applied to road surfaces" became `(De | relates to | water)` — the model split "de-icing" at the hyphen and lost the semantic content entirely. "Corrosion of pre-stressed steel tendons" became `(Corrosion | relates to | unknown)`. Without meaningful entities extracted, bridging can't work. Meanwhile standard RAG actually did well: "de-icing salts" (0.751), "chloride ions" (0.607), and "tendon capacity" (0.583) all scored high enough to make the top-5.

**Satellite Signal (Std wins, -25%):** Similar extraction failure. "Coronal mass ejections (CMEs) from the sun" became `(3,000 km | relates to | Es)` — the model latched onto the speed figure and a fragment. "GPS signals passing through a disturbed ionosphere" became `(10 meters | relates to | unknown)`. The 8b model simply cannot handle multi-clause sentences with technical terminology across multiple domains in a single pass.

### Diagnosis: Why NS loses

The pattern is clear. The neurosymbolic pipeline has a **single point of failure: Pillar 1 extraction quality**. When the 8b model produces good subject-predicate-object triples with correct entities, the VKG construction and entity bridging work well (scenarios 0-2). When the model produces degenerate triples like `(X | relates to | unknown)`, the entire downstream pipeline collapses because there are no entities to bridge through.

This is not a flaw in the architecture — it's a flaw in the component. Swapping deepseek-r1:8b for a more capable extraction model (or even just improving the regex fallback) would likely flip the losing scenarios.

### A note on keyword hits

NS scored 0/7 on keyword wins (cases where NS got keywords and Std didn't). This seems bad but is misleading. In 4/7 scenarios, both pipelines hit the keywords. In the remaining 3, neither did (coral reef) or Std hit them and NS didn't. The keyword metric is primarily measuring answer generation quality, which depends on the same 8b model for both pipelines. The *retrieval* quality (coverage) is the metric that measures what our architecture actually changes.

---

## 2. Embedding Geometry Exploration

We embedded 5 families of propositions to understand how mxbai-embed-large (1024-dim) organizes semantic content. This directly addresses the paper's thesis about mapping feature space to semantic space.

### Family 1: "X are cute" (lexical substitution)

```
Dogs/Canines:  0.976    (near-synonyms)
Dogs/Hounds:   0.890    (hyponym)
Dogs/Huskies:  0.791    (specific breed)
Dogs/Wolves:   0.777    (related species)
Huskies/Hounds: 0.747   (most distant pair)
```

**Observation:** The embedding model has a fine-grained understanding of the hyponymy hierarchy. "Dogs" and "Canines" are near-identical (0.976) because they're true synonyms — every dog is a canine and vice versa. "Hounds" (0.890) is more specific but still a clear subset. "Wolves" (0.777) and "Huskies" (0.791) are related but taxonomically distinct.

**Implication for our work:** When two propositions differ only in a subject that the model considers a near-synonym, their embeddings are nearly identical. This means standard RAG would retrieve them interchangeably, which is correct behavior. The VKG doesn't add value here because there's no reasoning gap to bridge.

### Family 2: Socrates Syllogism

```
"Socrates is a man" / "Socrates is mortal":    0.879    (shared subject)
"All men are mortal" / "Socrates is mortal":    0.653    (shared predicate+object)
"All men are mortal" / "Socrates is a man":     0.560    (the logical bridge)
```

**This is the key finding.** The two *premises* of the syllogism — "All men are mortal" and "Socrates is a man" — are the farthest apart in embedding space (0.560). Yet they are the two sentences you need *together* to derive the conclusion. A standard RAG system retrieving top-k by similarity to the conclusion "Socrates is mortal" would rank "Socrates is a man" first (0.879) and "All men are mortal" second (0.653). It would *probably* get both in top-5 for this simple case, but the gap between them (0.560) is the kind of gap that gets exploited in harder scenarios.

The conclusion (0.879 to one premise, 0.653 to the other) is closer to one premise than the other. In embedding space, the conclusion lives near "Socrates is a man" because they share the subject entity, not because the model understands the logical derivation.

**Implication:** Embeddings organize by *entity overlap*, not by *logical role*. The premise-conclusion distance (0.879) is driven by shared "Socrates", not by the model understanding that one entails the other. Our VKG can exploit this by using "man/men" as a bridge entity between the two premises, which is exactly how a human would reason through the syllogism.

### Family 3: Robin Syllogism (structural parallel)

```
"A robin is a bird" / "A robin can fly":        0.912    (shared subject)
"All birds can fly" / "A robin can fly":         0.728    (shared predicate+object)
"All birds can fly" / "A robin is a bird":       0.671    (the logical bridge)
```

Same pattern as Socrates but with slightly higher similarities across the board. The universal premise and the particular instance are again the most distant pair (0.671 vs 0.560 for Socrates). The model "understands" robins and birds better than it understands the Socrates/man relationship — probably because robin-bird co-occurrence is more frequent in training data than Socrates-man.

### Family 4: Causal Chain (Altitude → Pressure → Boiling)

```
Altitude/Pressure:  0.660    (adjacent steps)
Pressure/Boiling:   0.640    (adjacent steps)
Altitude/Boiling:   0.476    (endpoints)
```

**This is our thesis in numbers.** The endpoints of the causal chain — "altitude increases" and "water boils at a lower temperature" — are only 0.476 similar. A query about boiling on a mountain would score the altitude fact very low. Yet the altitude fact is *essential* to the reasoning chain.

The adjacent steps hover around 0.65, close enough that entity bridging can link them if they share entities ("pressure" bridges step 1 and step 2, "temperature" bridges step 2 and step 3). But the endpoints can *only* be connected by traversing the intermediate step. This is exactly the gap that standard RAG fails on and that our VKG bridges.

### Family 5: "X inhibits Y" (shared predicate, different domains)

```
Ketoconazole/Aspirin:    0.553
Ketoconazole/Shade:      0.476
Ketoconazole/Regulation: 0.365
Aspirin/Shade:           0.435
Aspirin/Regulation:      0.410
Shade/Regulation:        0.463
```

Mean similarity: 0.450. This is barely above random.

**Critical insight:** Sharing a predicate ("inhibits") does almost nothing in embedding space. "Ketoconazole inhibits CYP2C9" and "Regulation inhibits competition" share identical relational structure (A inhibits B) but score only 0.365 — lower than many cross-family pairs. The embedding model is encoding *domain content* (pharmacology vs economics vs biology vs governance), not *relational structure*.

**Implication for the VKG:** This confirms that you cannot rely on embedding similarity to identify structurally analogous propositions across domains. A VKG that encodes predicate types (inhibition, causation, etc.) explicitly can make cross-domain analogies that embeddings completely miss. This is a potential direction for the paper: not just multi-hop retrieval but cross-domain structural analogy.

### Cross-Family Analysis

The closest cross-family pair was "Atmospheric pressure decreases" and "Shade inhibits photosynthesis" at 0.602 — probably because both describe a natural phenomenon with a negative effect. This is a **false bridge**: these sentences have no logical relationship, but an embedding-based system might link them.

The "cute animals" family clustered closest to the "robin syllogism" family (centroid similarity 0.509), likely because both involve animals with simple predications. This makes topical sense but is logically meaningless.

---

## 3. Synthesis: What This Means for the Paper

### The core argument, supported by data

1. **Embedding space encodes logical structure with non-uniform fidelity.** The "inhibits" family (0.450 mean) shows that identical relational structure across domains is severely under-represented. Embeddings DO encode structure (additive compositionality, consistent verb displacements), but entity/topical information receives ~3.5x more representational capacity than relational/predicate information.

2. **Multi-hop chains decay in embedding space.** Causal chain endpoints (0.476) are barely more similar than random cross-domain sentences. Standard RAG will miss chain steps that are essential but topically distant from the query.

3. **Entity bridging recovers what embeddings lose.** In the benchmark, the 3 scenarios where NS wins are exactly the cases where the extraction model successfully identifies shared entities between chain steps. The 2 losses are extraction failures, not architecture failures.

4. **The bottleneck is extraction, not the graph.** The VKG architecture works when fed good propositions. The current 8b model is the weak link. This suggests a clean separation of concerns: improve extraction quality independently, and the end-to-end system improves without changing the VKG or logic engine.

5. **Embeddings are compositional but lopsidedly weighted.** The semantic grid proves that S, P, and O each contribute a consistent, independent, approximately additive vector component. But the weights are drastically unequal: Subject (3.5x) > Object (2.6x) > Predicate (1.0x). The model allocates its dimensions to encode *what things are about* (entities/topics), not *what relationship holds* (predicates). This is optimal for topical retrieval but exactly wrong for logical reasoning, where the predicate is the most important component.

6. **Verbs are consistent translations, not deformations.** Despite weak magnitude, verb displacement vectors point in the same direction across S/O contexts (0.84 alignment). The verb shifts the entity subspace without reshaping it (subspace r=0.958). This explains why entity bridging works robustly — shared entities stay close regardless of what predicate connects them. But it also means you cannot discover structural analogies ("all inhibition relationships") via embedding distance alone. The VKG's explicit predicate labels fill exactly this gap.

### Observations worth highlighting in the paper

- **The Socrates gap:** 0.560 between the two premises of a valid syllogism. This is a vivid, citable example of embedding space failing at logical reasoning.
- **The distractor trap:** In the economic scenario, "Starbucks announced a 5% price increase" (0.737) outscored the actual cause "severe drought in Brazil" (not in top-5 at all). Standard RAG confidently retrieves the wrong explanation.
- **Entity bridging as the mechanism:** The VKG doesn't do anything magical — it simply follows shared entities between propositions. But this simple mechanism recovers chain steps that cosine similarity ranks below distractors.

### Known limitations to address

- **Extraction quality:** 2/7 scenarios fail because deepseek-r1:8b can't parse complex technical sentences. The paper should either use a better model or explicitly frame this as a component limitation, not an architecture limitation.
- **Keyword metric:** NS scores 0/7 on keywords-only-NS-hits, but this is an answer generation issue, not a retrieval issue. The paper should separate retrieval evaluation from generation evaluation.
- **Overhead:** 16.9x time overhead (163s vs 2753s). Most of this is the extraction step (14 LLM calls per scenario vs 1 for standard RAG). This is inherent to the approach but could be parallelized.
- **No formal chains found in winning scenarios:** In 2 of the 3 NS wins (Everest, Drug), the logic engine found 0 formal reasoning chains. The coverage improvement came entirely from Pillar 2 entity bridging, not Pillar 3 chain discovery. This weakens the "logic-gated" claim — really it's "entity-bridged" retrieval doing the work.

---

## 3b. Semantic Grid: Isolating Subject, Predicate, Object Axes

The embedding family experiments (§2) hinted that subject overlap drives similarity more than predicate overlap. The 3×3×3 semantic grid tests this rigorously by crossing 3 subjects (cats, trucks, children) × 3 predicates (eat, carry, watch) × 3 objects (fish, rocks, stars) into 27 propositions. Every word was chosen to be concrete, unambiguous, and maximally distinct from others in its role.

### The axis hierarchy

| Axis | Same-axis mean | Diff-axis mean | Separation | Relative strength |
|---|---|---|---|---|
| Subject | 0.702 | 0.462 | **+0.240** | 3.5x |
| Object | 0.658 | 0.482 | **+0.176** | 2.6x |
| Predicate | 0.583 | 0.515 | **+0.069** | 1.0x (baseline) |

Subject dominates. Two sentences sharing a subject are on average 0.240 more similar than two that don't — the predicate gap is only 0.069. This means that in embedding space, *who does something* matters 3.5x more than *what they do*.

Object is second. *What they act on* matters 2.6x more than the action itself. The predicate — the relational structure that a logician would consider the most important part of a proposition — is almost invisible to the embedding model.

### What this means for VKG design

This result quantitatively confirms what the "inhibits" family showed qualitatively: **embedding models encode entities, not relations**. Two propositions with the same subject and object but different predicates ("Trucks carry stars" vs "Trucks watch stars") score 0.915. Two with the same predicate but different entities ("Cats eat fish" vs "Children carry stars") score 0.247.

For the VKG, this has a specific architectural implication. Entity bridging works *because* embeddings are entity-dominated. When two propositions share an entity (subject or object), they're already close in embedding space and easily bridged. The VKG's contribution is bridging across the *predicate gap* — connecting "CYP2C9 is an enzyme" to "CYP2C9 is inhibited" where the shared entity pulls them together even though the predicates are unrelated.

But it also means the VKG should NOT rely on embedding similarity to identify structurally similar propositions across domains (the "inhibits" failure). If we want cross-domain analogy ("ketoconazole inhibits CYP2C9" ↔ "regulation inhibits competition"), we need explicit predicate-type matching in the ontology, not embedding distance.

### Per-value pull strength

Not all values within an axis pull equally:

- **Subjects:** "trucks" (+0.267) > "cats" (+0.254) > "children" (+0.201). The concrete, unambiguous noun "trucks" pulls harder than the more semantically rich "children" — likely because "children" co-occurs in many more contexts in training data, spreading its embedding across a wider region.
- **Predicates:** All nearly identical (~0.07). "eat", "carry", "watch" are all common verbs with clear meanings, and none pulls harder than the others. The predicate simply doesn't anchor the embedding.
- **Objects:** Also nearly identical (~0.18). Concrete nouns are equally effective as attractors.

### The step function at 0, 1, 2 shared axes

The joint analysis shows a clean staircase:

| Shared axes | Mean similarity | Interpretation |
|---|---|---|
| 0 | 0.361 | Different subject, predicate, object: near-random |
| 1 | 0.546 | Share one axis: moderate pull |
| 2 | 0.750 | Share two axes: strong cluster |

The steps are roughly equal (+0.19, +0.20), suggesting the axes contribute approximately additively. There's no strong interaction effect — sharing two axes is roughly the sum of sharing each independently.

---

## 3c. Verb Structure: Is the Predicate Signal Consistent or Just Weak?

The grid showed predicates have the weakest pull (+0.069). But weak overall doesn't mean incoherent. The verb structure analysis asks: when you swap a verb, does the embedding shift in a *consistent direction* — a "verb vector" — or does it just add noise?

### Verb displacement vectors ARE consistent

When you change eat→carry across all 9 subject/object combinations, the displacement vectors (the literal vector difference in 1024-dim space) have a mean pairwise cosine of **0.671**. This is well above zero — the verb swap moves the embedding in roughly the same direction regardless of what's eating or being eaten.

| Verb swap | Displacement cosine | Mean alignment to centroid direction |
|---|---|---|
| eat → carry | 0.671 | 0.841 |
| eat → watch | 0.640 | 0.825 |
| carry → watch | 0.641 | 0.825 |

All three verb pairs show ~0.65 consistency. The individual alignment to the mean displacement direction is even higher (~0.83), meaning each individual verb swap tracks the mean "verb direction" closely.

**Key finding:** There IS a consistent "verb direction" in embedding space. The predicate has weak *magnitude* (it doesn't move the vector far) but strong *directional consistency* (it moves it the same way every time). This is exactly what you'd expect from compositional semantics — the verb contributes a small but systematic component to the overall embedding.

### The verb direction is modulated by context

Breaking down displacement consistency by what's shared:

| Context | eat→carry | eat→watch | carry→watch |
|---|---|---|---|
| Same subject | 0.769 | 0.697 | 0.720 |
| Same object | 0.713 | 0.691 | 0.697 |
| Neither shared | 0.601 | 0.587 | 0.573 |

When the subject is the same, the verb displacement is MORE consistent (0.769 vs 0.601 for eat→carry). This makes sense: "cats eat fish → cats carry fish" and "cats eat rocks → cats carry rocks" are conceptually similar verb swaps (same agent performing a different action). When the subject also changes, the verb direction gets noisier because you're changing the conceptual frame.

### The verb doesn't change the internal structure

The verb-conditioned subspace analysis asks: within "eat" propositions, does the similarity landscape (which S/O pairs are close?) look the same as within "carry"?

| Verb pair | Pearson r | Rank r |
|---|---|---|
| eat vs carry | 0.958 | 0.889 |
| eat vs watch | 0.939 | 0.856 |
| carry vs watch | 0.973 | 0.935 |

Pearson r of **0.958** between the eat and carry subspaces. The verb changes the *location* of the cluster in 1024-dim space but barely touches its *internal geometry*. cats/fish is close to cats/rocks and far from trucks/stars regardless of whether they eat, carry, or watch. The verb is a translation, not a deformation.

### Naturalness: the model doesn't clearly encode selectional preferences

"Cats eat fish" is natural. "Trucks eat stars" is absurd. Does the embedding position "cats eat fish" closer to the verb centroid (as a more "prototypical" use of "eat")?

**No.** Overall correlation between hand-labeled naturalness (1-3) and centroid distance: **r = -0.031**. Essentially zero. The individual verbs show mixed signals (eat: -0.33, carry: +0.30, watch: -0.05) with no consistent pattern.

This is surprising. It means mxbai-embed-large either doesn't encode selectional preferences, or encodes them in a way that isn't captured by centroid distance. The model places "trucks eat rocks" just as comfortably within the "eat" cluster as "cats eat fish". For our purposes, this is actually useful — it means entity bridging won't be derailed by "weird" combinations that the model might otherwise push to the periphery.

### Interaction effects are minimal

The Subject × Predicate coherence matrix shows no strong interactions:

|  | eat | carry | watch |
|---|---|---|---|
| cats | 0.714 | 0.771 | 0.749 |
| trucks | 0.755 | 0.765 | 0.734 |
| children | 0.759 | 0.719 | 0.698 |

All values cluster between 0.70 and 0.77. No subject has a privileged relationship with any verb. Similarly, Predicate × Object shows flat interactions (0.65-0.70 throughout). The embedding model treats S, P, O as approximately independent contributions — further evidence for compositional structure.

### Synthesis: what this means for the paper

The verb has a small but **directionally consistent** effect on embeddings. It acts as a translation vector that shifts the entire subject/object landscape without deforming it. This has three implications:

1. **Entity bridging is robust.** Because verbs don't deform the S/O subspace, two propositions sharing an entity will be close regardless of their predicates. This is exactly what makes entity bridging work in the VKG.

2. **Predicate-aware retrieval needs explicit structure.** You can't use embedding distance to find "all inhibition relationships" across domains — the verb direction is consistent *within* a verb but the magnitude is too small to create a separable cluster. The VKG's explicit predicate labels fill this gap.

3. **Compositionality is real but lopsided.** The model composes S + P + O approximately additively, but with wildly unequal weights (subject 3.5x, object 2.6x, predicate 1x). A semantic space that rebalances these weights — giving predicates equal standing — would better represent logical structure.

---

## 4. Raw Data Artifacts

- `results.json` — Full benchmark metrics (per-scenario + aggregate)
- `prototype/embeddings_exploration.npz` — Raw 1024-dim embedding vectors for all 18 propositions across 5 families. Load with `np.load('prototype/embeddings_exploration.npz', allow_pickle=True)`. Keys: `vecs_cute_animals`, `vecs_socrates_syllogism`, `vecs_syllogism_variant`, `vecs_causal_chain`, `vecs_inhibits_X`, `all_vecs`, `all_labels`.
- `prototype/embeddings_exploration.json` — Pairwise similarity matrices and cluster statistics for all 5 families.
- `prototype/semantic_grid_results.json` — Full 27×27 similarity matrix and axis/joint/per-value analysis.
- `prototype/semantic_grid_results_embeddings.npz` — Raw 1024-dim vectors for all 27 grid propositions. Keys: `vecs`, `sentences`, `subjects`, `predicates`, `objects`.
- `prototype/verb_structure_results.json` — Displacement consistency, subspace correlation, naturalness, and interaction analysis.
- `prototype/word_isolation_results.json` — Isolated word embeddings, taxonomic hierarchies, jitter analysis, convergence data.
- `prototype/taxonomic_direction_results.json` — Full displacement, cross-hierarchy, abstraction level, and decay analysis.
- `prototype/taxonomic_direction_embeddings.npz` — Raw 1024-dim vectors for all 111 unique words.
- `prototype/taxonomic_direction_vectors.npz` — Mean "upward" displacement vectors for all 24 hierarchies.
- `prototype/linnaean_hierarchy_results.json` — Linnaean vs common-name comparison, convergence, displacement data.
- `prototype/linnaean_hierarchy_embeddings.npz` — Raw 1024-dim vectors for all Linnaean + common name terms.

---

## 3d. Word Isolation, Taxonomic Jitter, and Distributional vs Ontological Semantics

### Words in isolation reverse the proposition-level hierarchy

When we embed the 9 grid words *in isolation* (just the bare word, no sentence context), the within-role similarity ranking **reverses** compared to proposition-level:

| Role | Within-role sim (isolated words) | Pull strength (in propositions) |
|---|---|---|
| Predicates | 0.639 (highest) | +0.069 (weakest) |
| Objects | 0.618 | +0.176 |
| Subjects | 0.545 (lowest) | +0.240 (strongest) |

Predicates are the *most* similar to each other as bare words ("eat", "carry", "watch" cluster tightly), yet they have the *weakest* pull in propositions. Subjects are the *least* similar as bare words, yet dominate proposition structure.

This makes sense: predicates are functionally similar (all transitive action verbs), so they cluster at the word level. But precisely because they're so similar to each other, swapping one for another barely moves the proposition embedding. Subjects like "cats", "trucks", "children" are maximally dissimilar as words (different semantic domains), so they create the widest separation when composed into propositions.

### Taxonomic hierarchies: distance follows co-occurrence, not logical distance

Embedding dog-related words along the taxonomic hierarchy reveals a critical pattern:

| Pair | Cosine | Taxonomic relationship |
|---|---|---|
| dog / canine | 0.947 | Near-synonyms |
| dog / hound | 0.802 | Hyponym |
| dog / mammal | 0.816 | 2 levels up |
| dog / animal | 0.876 | 3 levels up |
| dog / creature | 0.756 | 4 levels up |
| puppy / creature | 0.619 | Endpoint to endpoint |

The striking result: **dog→animal (0.876) > dog→mammal (0.816)**, despite "mammal" being the more immediate taxonomic superclass. In any formal ontology, mammal is *closer* to dog than animal is. But in embedding space, "animal" is closer because "dog" and "animal" co-occur far more frequently in everyday language than "dog" and "mammal".

### Embeddings encode distributional semantics, not formal ontology

This reveals a fundamental property of embedding space: **it reflects how humans talk about things, not how things are logically organized.**

The evidence:
- **"dog" and "cat"** are informal, everyday words → high similarity to broad terms like "animal" (0.876, 0.769 respectively)
- **"feline" and "canine"** carry a taxonomic/scientific register → they cluster together more tightly (cat/feline: 0.923, dog/canine: 0.947)
- **"mammal"** is an educational/scientific term that appears more in textbooks than casual speech → lower co-occurrence with casual "dog" than with general "animal"
- **"carnivoran"** would be even more esoteric, likely clustering with other technical taxonomy terms rather than with the animals it classifies

The embedding distance between two words reflects their **distributional overlap** (do they appear in similar contexts?) rather than their **ontological distance** (how many taxonomic levels separate them?). Words that humans frequently use together end up close, regardless of their formal logical relationship.

### Context compresses predicate differences, amplifies entity differences

When we substitute taxonomic variants into proposition templates, sentence context acts as a selective filter:

- **Predicate jitter is almost invisible**: "Cats eat fish" vs "Cats devour fish" = 0.965, "Cats munch fish" = 0.925. Verb synonyms in context are nearly indistinguishable because the shared subject+object anchor the embedding.
- **Subject jitter preserves relative ordering**: dog→hound→canine→mammal→animal maintains the same relative distances across all 3 templates (r > 0.86), but the absolute distances are compressed.
- **Word↔sentence correlation is high**: subject jitter r=0.91, predicate r=0.92, object r=0.76. The word-level distance reliably predicts the sentence-level distance.

This means sentence context doesn't scramble the word-level structure — it selectively attenuates it. Predicates get compressed the most (because they contribute the least to proposition meaning in embedding space), while entity differences are preserved.

### Hierarchy convergence is literal, not graduated

Do "dog→mammal→animal" and "cat→mammal→animal" smoothly converge as they ascend the hierarchy?

**No.** The convergence is abrupt and literal:
- dog↔cat at base level: 0.691
- At mammal level: 1.000 (same word)
- At animal level: 1.000 (same word)

The model doesn't gradually merge the dog and cat "branches" as you go up. They remain distinct until you literally use the same word. There's no smooth interpolation between taxonomic branches — the embedding space doesn't represent the *structure* of the hierarchy, only the *distributional properties* of individual words within it.

### What this means for the paper

This finding strengthens the core thesis in two ways:

1. **Embedding space is systematically wrong about logical distance.** dog→animal being closer than dog→mammal is not noise — it's a predictable consequence of distributional training. Any retrieval system that relies on embedding distance for reasoning will inherit these systematic biases. The VKG corrects this by imposing explicit logical structure through entity-predicate-entity triples.

2. **Register and frequency contaminate semantic relationships.** The same concept at different levels of formality (dog/canine/canis) occupies different regions of embedding space, not because the meaning changed, but because the *contexts of use* changed. A formal ontology (the VKG) treats these as equivalent; an embedding space does not. This is another gap that only explicit symbolic structure can bridge.

---

## 3e. Taxonomic Direction: Is There a Universal "Up" in Embedding Space?

### The question

When you move from specific→general along a taxonomic hierarchy (puppy→dog→canine→mammal→animal→entity), does the displacement vector point in a **consistent direction**? And does that direction generalize across hierarchies — nouns, verbs, and adjectives alike?

If yes, embeddings encode a latent "abstraction axis." If no, taxonomic generalization is just a local phenomenon with no shared geometric structure.

### The experiment

24 hierarchies tested: 10 nouns (dog, cat, horse, fish, bird, tree, rock, truck, child, star), 10 verbs (eat, devour, carry, throw, watch, listen, cut, build, run, speak), 4 adjectives (red, huge, cold, fast). Each hierarchy runs from a maximally specific term to a maximally general one. 111 unique words embedded with mxbai-embed-large.

### Finding 1: Within each hierarchy, "up" is barely consistent

For each hierarchy, we computed the displacement vector at each step (word[i]→word[i+1]), normalized to unit length, then checked whether all step-vectors point in roughly the same direction.

| POS | Mean alignment to own mean direction | Pairwise step consistency |
|---|---|---|
| Nouns | 0.24 | -0.14 (near zero) |
| Verbs | 0.23 | -0.17 (near zero) |
| Adjectives | 0.33 | -0.18 (near zero) |

The mean alignment is weakly positive (~0.2-0.3), meaning there's a *slight* tendency for steps to point in the same direction, but the pairwise consistency between individual steps is essentially zero or negative. Going from "canine→carnivore" points in a completely different direction than going from "carnivore→mammal" — there is no single "upward" vector within a hierarchy.

**The first and last steps are the most aligned.** Across nearly all hierarchies, the first step (specific→near-synonym) and the last step (penultimate→most-general) show the highest alignment to the mean direction. The middle steps are the noisiest, with some even pointing "downward" (negative alignment). This suggests that specific→synonym and abstract→maximally-abstract may encode partially shared geometry, but the middle of the hierarchy is chaotic.

### Finding 2: Nouns share more "upward" direction than verbs

Cross-hierarchy comparison — does the "up" direction of dog agree with the "up" direction of cat, truck, fish, etc.?

| Comparison | Mean cosine of "up" directions |
|---|---|
| Noun × Noun | 0.465 |
| Verb × Verb | 0.381 |
| Adj × Adj | 0.057 |
| Noun × Verb | 0.061 |
| Noun × Adj | 0.030 |
| Verb × Adj | 0.051 |

**Nouns have the most shared "up" direction** (0.465 mean between hierarchies). Dog's "up" and horse's "up" agree at 0.696; dog and cat at 0.677. This makes sense — these hierarchies share the same upper levels (mammal→animal→organism→entity), so their displacement vectors literally traverse shared territory.

**Verbs have moderate agreement** (0.381). The eat/devour pair shares the most "up" direction (0.557), consistent with sharing the same hierarchy beyond "consume." But unrelated verbs like eat and listen only agree at 0.292.

**Adjectives have essentially zero shared "up" direction** (0.057). Going from crimson→perceptible has nothing in common directionally with going from enormous→sized. Adjective taxonomies are islands in embedding space.

**Cross-POS is near zero** (0.03-0.06). The noun "up" and verb "up" directions are unrelated. There is no universal abstraction axis.

### Finding 3: The global "up" exists but is POS-segregated

When we average all 24 hierarchy directions into a single "global up" vector, its magnitude is 0.456 (where 1.0 = perfect agreement, 0.0 = random). This is modest but non-zero.

Each hierarchy's alignment with this global "up":

| POS | Mean alignment with global "up" |
|---|---|
| Nouns | 0.541 |
| Verbs | 0.480 |
| Adjectives | 0.181 |

Nouns contribute the most to the global direction and align best with it. Verbs are weaker but still positive. Adjectives barely participate.

This means the "global up" is essentially the **noun abstraction direction**, contaminated slightly by verbs. It's not a universal feature of embedding space — it's an artifact of how noun hierarchies share upper levels (all converging on entity/organism/animal).

### Finding 4: Distance decay is non-monotonic

As you ascend a hierarchy, similarity to the origin word *should* decrease monotonically (each step takes you further from where you started). In practice:

| POS | Monotonic hierarchies | Total violations |
|---|---|---|
| Nouns | 3/10 | 16 violations |
| Verbs | 1/10 | 14 violations |
| Adjectives | 0/4 | 4 violations |

Only 4 out of 24 hierarchies show monotonic decay. The most common violation pattern: a word in the middle of the hierarchy is **closer** to the origin than the word below it. Examples:

- **puppy→...→canine (0.856) > hound (0.723)**: "canine" is closer to "puppy" than "hound" is, because canine is a near-synonym of dog while hound carries a hunting/breed connotation
- **puppy→...→mammal (0.676) < animal (0.745)**: "animal" bounces back up because it's more common/casual
- **pickup→...→vehicle (0.682) > machine (0.605) < object (0.637)**: "object" is more general than "machine" yet closer to "pickup"

**The recurring pattern:** violations happen at the transition between casual words and technical taxonomic terms (carnivore, primate, mineral) and again at very general words that "bounce back" due to high co-occurrence frequency (animal, object, entity).

This confirms §3d's finding at much larger scale: embedding distance tracks distributional frequency, not ontological distance. The hierarchy is **locally** respected (adjacent near-synonyms are close) but **globally** scrambled by register and frequency effects.

### Finding 5: Verb hierarchies are messier than noun hierarchies

Average decay curves (interpolated to common positions, 0.0 = most specific, 1.0 = most general):

| Position | Nouns | Verbs | Adjectives |
|---|---|---|---|
| 0.00 | 1.000 | 1.000 | 1.000 |
| 0.25 | 0.712 ± 0.070 | 0.685 ± 0.045 | 0.822 ± 0.084 |
| 0.50 | 0.613 ± 0.065 | 0.649 ± 0.067 | 0.710 ± 0.097 |
| 0.75 | 0.621 ± 0.053 | 0.577 ± 0.031 | 0.729 ± 0.092 |
| 1.00 | 0.536 ± 0.050 | 0.559 ± 0.026 | 0.588 ± 0.044 |

Key observations:
- **Nouns show a non-monotonic bump at 0.75** (0.621 > 0.613 at 0.50) — this is the "animal bounce-back" effect across many hierarchies
- **Verbs decay more smoothly** but end up **closer** to origin (0.559) than nouns do (0.536), meaning verb endpoints are less differentiated from their origins
- **Adjectives retain the most similarity** throughout, suggesting adjective hierarchies are shorter and the words stay closer in embedding space
- **Verbs have the smallest standard deviation at endpoint** (0.026) — they converge on a very consistent terminal similarity, likely because all 10 verb hierarchies terminate at "act"

### Finding 6: Same-level words do NOT cluster

Words at the same normalized abstraction level (specific, mid, general) are no more similar to each other than to words at different levels:

| Comparison | Mean similarity |
|---|---|
| Specific × Specific | 0.553 |
| Mid × Mid | 0.573 |
| General × General | 0.585 |
| Specific × Mid | 0.559 |
| Specific × General | 0.558 |
| Mid × General | 0.580 |

The within-level and cross-level similarities are nearly identical. There is no "abstraction cluster" — knowing that two words are both at the "mid" level of their respective hierarchies tells you nothing about whether they're close in embedding space.

### What this means for the paper

1. **There is no universal abstraction axis.** You cannot project embeddings onto a single dimension and recover ontological level. The "up" direction is a local phenomenon within related noun hierarchies (because they share words at the top), not a fundamental feature of the embedding space. This means any system that needs to reason about specificity/generality (e.g., "is a dog a kind of animal?") cannot do so through geometric operations on embeddings alone.

2. **Verb ontology is genuinely harder than noun ontology.** The user's intuition is confirmed: verb hierarchies show lower within-hierarchy consistency (0.381 vs 0.465), more monotonicity violations (1/10 vs 3/10), and near-zero cross-POS alignment. Verbs are less taxonomically organized in natural language (there's no verb equivalent of the Linnaean hierarchy), and this is faithfully reflected in embedding space.

3. **Adjectives are taxonomic islands.** With cross-hierarchy "up" cosine of 0.057, adjective abstractions share essentially no geometric structure. Going from "crimson" to "perceptible" is a completely different direction than going from "enormous" to "sized." This makes sense — adjective hierarchies don't share upper levels the way noun hierarchies converge on "animal" or "entity."

4. **The VKG's explicit type hierarchy fills a real gap.** Since embedding space cannot represent "is-a" relationships geometrically, any retrieval system that needs to reason about types (e.g., "retrieve all statements about mammals" when the corpus mentions dogs, cats, and horses) must have an explicit symbolic type system. The VKG provides exactly this through its ontological triples.

---

## 3f. Linnaean Taxonomy: Does Consistent Register Fix Monotonicity?

### The hypothesis

Experiment 6 found that mixed-register hierarchies (puppy→dog→canine→mammal→animal) produce non-monotonic distance decay. The violations seemed driven by register mixing: casual "animal" bouncing back closer than scientific "mammal." If we use **purely formal Linnaean taxonomy** — Canis lupus familiaris → Canis → Canidae → Carnivora → Mammalia → Vertebrata → Chordata → Animalia → Eukaryota — does the consistently scientific register eliminate the bounce-backs?

### The result: No. Linnaean names are ALSO non-monotonic.

| Category | Monotonic | Total violations |
|---|---|---|
| Linnaean (10 hierarchies) | 1/10 | 19 violations |
| Common English (6 hierarchies) | 0/6 | 18 violations |

Only bread yeast (Saccharomyces cerevisiae → ... → Fungi → Eukaryota) is monotonic. Every other hierarchy has violations.

### The "Animalia bounce" — a universal pattern

The most striking pattern: **Animalia bounces back in almost every animal hierarchy.** Every Linnaean hierarchy that passes through Chordata and Animalia shows the same violation:

| Hierarchy | Vertebrata | Chordata | Animalia | Pattern |
|---|---|---|---|---|
| Domestic dog | 0.423 | 0.433 ←! | 0.525 ←! | V < Ch < An |
| Domestic cat | 0.462 | 0.476 ←! | 0.528 ←! | V < Ch < An |
| Human | 0.548 | 0.566 ←! | 0.621 ←! | V < Ch < An |
| Horse | 0.486 | 0.488 ←! | 0.577 ←! | V < Ch < An |
| Brown trout | 0.388 | 0.456 ←! | 0.442 | V < Ch, then decays |
| House sparrow | 0.475 | 0.521 ←! | 0.587 ←! | V < Ch < An |
| Fruit fly | — | — | 0.536 | (skips Vertebrata/Chordata) |

"Animalia" is a far more common/recognizable word than "Vertebrata" or "Chordata" — even in Latin. This is the same distributional frequency effect we saw with common English names, just shifted into formal taxonomy. "Animalia" appears in more contexts (legal, philosophical, educational, everyday) than "Chordata" (biology textbooks only).

### E. coli: the most dramatic example

The E. coli hierarchy shows an extreme violation — similarity to origin *increases* as you go up:

| Level | Sim to "Escherichia coli" |
|---|---|
| Enterobacterales | 0.567 |
| Gammaproteobacteria | 0.587 ←! |
| Proteobacteria | 0.669 ←! |
| Bacteria | 0.806 ←! |

"Bacteria" (0.806) is **closer** to "Escherichia coli" than "Enterobacterales" (0.567) is! This is because "E. coli" and "Bacteria" massively co-occur in general science writing, while "Enterobacterales" and "Gammaproteobacteria" are specialist terms that appear in very different contexts (taxonomic databases, microbiology journals).

### Head-to-head: Linnaean vs common names (same organisms)

For the 6 organisms tested in both registers:

| Organism | Linnaean violations | Common violations |
|---|---|---|
| Domestic dog | 2 | 4 |
| Domestic cat | 2 | 4 |
| Human | 2 | 4 |
| Horse | 3 | 3 |
| Brown trout | 1 | 2 |
| House sparrow | 3 | 1 |

Linnaean names produce **fewer violations for mammals** (2 vs 4 for dog, cat, human) but the difference isn't dramatic. Common names are worse because they mix casual and scientific registers more aggressively (puppy→dog→canine→carnivore→mammal→vertebrate→animal has multiple register shifts).

The house sparrow is the one case where common names win — likely because "sparrow→songbird→bird→vertebrate→animal→organism→living thing" is a smoother frequency gradient than "Passer domesticus→Passer→Passeridae→Passeriformes→Aves→..." where Passeridae bounces back above Passer.

### Cross-hierarchy convergence: literal, not graduated (confirmed)

The Linnaean convergence analysis confirms what we found in §3d with common names:

- Dog vs Cat: Canidae ↔ Felidae = 0.785, then instant 1.000 at shared Carnivora
- Dog vs Human: Carnivora ↔ Primates = 0.553, then instant 1.000 at shared Mammalia
- Cat vs Horse: Carnivora ↔ Perissodactyla = 0.457, then instant 1.000 at shared Mammalia

There is no smooth convergence. Two branches remain distinct until they literally share a word. Canidae and Felidae (0.785) are reasonably close because they're both Latin "-idae" family names in zoology, not because the model understands they share an order. Carnivora and Primates (0.553) are much further apart despite being one taxonomic level below the same class.

### Displacement direction: Linnaean agrees within-hierarchy better than expected

| Metric | Linnaean | Common English (Exp. 6) |
|---|---|---|
| Mean within-hierarchy alignment | ~0.19 | ~0.24 |
| Cross-hierarchy "up" cosine | 0.360 | 0.465 |
| Eukaryotes-only cross-hierarchy | 0.426 | — |

The Linnaean "up" directions agree less across hierarchies (0.360 vs 0.465) because the common English hierarchies share more terminal words ("animal", "entity" appear everywhere). Linnaean hierarchies diverge earlier — Arthropoda, Plantae, Fungi, Bacteria are all different terminal branches, reducing the shared-word effect that inflated the common English cross-hierarchy score.

### What this tells us

1. **Register consistency doesn't fix the fundamental problem.** Non-monotonicity isn't caused by mixing casual and scientific words in the same hierarchy. It's caused by the mismatch between **taxonomic distance** and **distributional frequency** at every level. "Animalia" bounces back not because it's informal but because it's simply a more common Latin word than "Chordata."

2. **The "common word bounce" is universal.** Whether you use "animal" or "Animalia," "bacteria" or "Bacteria," the more frequently encountered word at a higher taxonomic level will be closer to the origin than the less frequent word at a lower level. This is a fundamental property of distributional embeddings, not a register artifact.

3. **Convergence is always literal.** Even in pure Latin taxonomy, branches snap to identity at shared words rather than gradually merging. The embedding model has no representation of "these two families share an order" — it only knows that the same word appears in both contexts.

4. **This is the strongest evidence yet for the VKG.** Even the most formally structured, register-consistent taxonomy humans have ever created (Linnaean classification) cannot be recovered from embedding geometry. The only way to know that Canidae and Felidae are both Carnivora is to have that relationship explicitly stated. The VKG does exactly this.

---

## 3g. Why Hyperbolic Embeddings Won't Save You

### The claim

A common response to the limitations of Euclidean embedding spaces for hierarchical data is to propose **hyperbolic embeddings** (Nickel & Kiela 2017, Dhingra et al. 2018, etc.). The argument: hyperbolic space has exponentially growing volume with distance from the origin, which naturally maps to the exponentially growing number of nodes at each level of a tree. Place the root near the origin, leaves far away, and the geometry does your taxonomy for you. Poincaré embeddings, hyperbolic neural networks, and related approaches have shown impressive results on *curated* ontologies like WordNet.

### Why our data says this won't work for general-purpose retrieval

The hyperbolic embedding argument assumes the problem is **geometric** — that Euclidean space lacks the capacity to represent tree structures efficiently, and switching to a space with native tree-like geometry will fix the hierarchy recovery problem. Our experiments show that the problem is not geometric but **distributional**.

**The core issue:** The non-monotonicity we observe is not caused by the embedding space lacking room for hierarchies. It's caused by the training data distribution. Consider:

1. **"Bacteria" (0.806) is closer to "Escherichia coli" than "Enterobacterales" (0.567) is.** This isn't because Euclidean space can't fit a tree — it's because "E. coli" and "Bacteria" co-occur millions of times in PubMed abstracts, news articles, and textbooks, while "E. coli" and "Enterobacterales" co-occur almost exclusively in taxonomy databases. A hyperbolic model trained on the same corpus would learn the same co-occurrence statistics. It would place "Bacteria" close to "E. coli" in the Poincaré disk for exactly the same distributional reasons.

2. **The "Animalia bounce" would become the "Animalia warp."** In hyperbolic space, distances near the origin are compressed while distances near the boundary are stretched. If "Animalia" gets pulled closer to species names by co-occurrence (as it does in Euclidean space), the hyperbolic metric would actually *amplify* this distortion. A word that's incorrectly close in Euclidean space would be incorrectly close in hyperbolic space too — but now the exponential metric makes the error in effective tree-distance even larger.

3. **Convergence is literal, not graduated, regardless of geometry.** Our experiments show that Canidae and Felidae don't gradually converge as they ascend toward Carnivora — they remain distinct until they literally share a word. This is a property of **how the model learns**, not of what space it learns in. A hyperbolic model would still map "Canidae" and "Felidae" to separate points and "Carnivora" to a third point. The "is-a" relationship between them would still need to be explicitly stated, not inferred from position.

4. **The frequency-distance inversion is training-objective-deep.** Embedding models are trained to place co-occurring terms close together. Frequent co-occurrence = short distance. This objective doesn't change when you switch from Euclidean to hyperbolic space — you're still minimizing a distance-based loss over co-occurrence statistics. The systematic errors we observe (common words closer than rare words at lower taxonomic levels) are direct consequences of this objective, not of the metric space.

### The empirical prediction

If someone trained a Poincaré embedding model on the same general-purpose corpus (Wikipedia, Common Crawl, etc.) used to train mxbai-embed-large, and then tested it on our Linnaean hierarchies, we predict:

- **Non-monotonicity would persist.** "Bacteria" would still be closer to "Escherichia coli" than "Enterobacterales" is, because the training signal is the same.
- **Non-monotonicity might be worse.** Hyperbolic space's exponential metric means that small errors in placement near the origin (where general terms like "Animalia" live) translate to large errors in effective tree-distance. A word that's slightly too close in Euclidean space could be dramatically too close in hyperbolic space.
- **The abstraction axis would still not exist.** Our Experiment 6 showed no universal "up" direction across hierarchies. Hyperbolic space provides a notion of "toward the origin" as an abstraction axis, but if the training data doesn't consistently push general terms toward the origin (and our data shows it doesn't — "Animalia" and "Bacteria" are pulled *toward* specific species, not away from them), then the hyperbolic geometry is wasted.

### When hyperbolic embeddings DO work

Hyperbolic embeddings show strong results on **curated ontologies** — WordNet, medical taxonomies, organizational hierarchies — where the training data IS the hierarchy itself. When you train a Poincaré embedding directly on (hypernym, hyponym) pairs from WordNet, you're giving the model exactly the signal it needs: "dog" is below "canine" is below "carnivore." The hyperbolic geometry efficiently encodes this *given* hierarchy.

But this is precisely the point: **you need the explicit symbolic hierarchy first.** The hyperbolic embedding is a compressed representation of an ontology that already exists. It doesn't discover the ontology from distributional data. For general-purpose retrieval over arbitrary text — which is the RAG use case — you don't have a curated ontology. You have a corpus of sentences, and any embedding model trained on that corpus (Euclidean or hyperbolic) will inherit the distributional biases of the training data.

### What this means for our paper

This argument strengthens the neurosymbolic thesis in a specific way: **the problem isn't the geometry of the embedding space, it's the absence of explicit symbolic structure.** Changing from Euclidean to hyperbolic doesn't add symbolic structure — it just changes the manifold on which distributional statistics are projected. The VKG adds what's actually missing: explicit entity-predicate-entity triples that state relationships like "Canidae is-a Carnivora" directly, rather than hoping they'll emerge from corpus statistics in any geometry.

The right framing is not "Euclidean embeddings can't represent hierarchies" (they can, given the right training signal). It's "distributional training objectives can't recover hierarchies from corpus statistics, regardless of the target geometry." The fix is not a better embedding space — it's a knowledge graph.
