# Paper 3 Strategy Notes

## Case Study Order (deliberate)

1. **Bioinformatics** — Lead with this. Conference organizers are almost entirely biomedical AI researchers (Le Cong/CRISPR, Wu/MedOS, Ying/aging biology). Bioinformatics examples land immediately in their language. Gene-function similarity, drug repurposing, protein functional analogy.

2. **Hiring / Labor Economics** — Second. This is where the original insight came from and where the economic/fairness argument is strongest. Pareto improvement framing, matching market formalism, structural anti-discrimination.

3. **General Ontology (Wikidata)** — Third. Connects back to Paper 1 (FOL discovery) and demonstrates generalizability beyond any single domain. Wikidata's messy many-to-many relationships are a natural test case.

## Why Bioinformatics First

- Organizers are biomedical researchers — this is their home turf
- Bioinformatics is saturated with many-to-many relationships (gene→pathway, drug→target, protein→function, disease→gene, phenotype→genotype) — natural motivation
- Biomedical ontologies (Gene Ontology, SNOMED CT, MeSH) are well-structured enough to provide ground truth for evaluation
- A lot of biomedical embedding work exists (BioWordVec, PubMedBERT, ESM, ChemBERTa) giving us existing infrastructure to demonstrate on
- The conflation problem is viscerally real in biomedical search — every bioinformatician has experienced "I searched for functionally similar genes and got tissue-co-expressed genes instead"

## Open question

How deep do we go on bioinformatics? Options:

- **Minimal (current plan):** Use bioinformatics as motivating examples with toy demonstrations. Lead case study but not deeply empirical.
- **Medium:** Run actual orthogonal projection experiments on BioWordVec or PubMedBERT embeddings with Gene Ontology ground truth. Would take a few days but produce real numbers.
- **Deep:** Full pipeline with multiple biomedical embedding models, GO semantic similarity evaluation, comparison against naive cosine. Would be a significant empirical contribution but may not be feasible by April 5.

Leaning toward medium — enough real numbers to score on executability (50% of rubric) without overcommitting.

## SKILL.md Requirements

The paper MUST have an executable SKILL.md. Executability + Reproducibility = 50% of the evaluation score. A purely theoretical paper is dead on arrival.

Minimum viable SKILL.md:
1. Embed biomedical entities (genes, drugs, or proteins) using an accessible model
2. Compute naive cosine similarity rankings
3. Derive control vectors for a confounding dimension (tissue type, toxicity, phylogeny)
4. Compute projected cosine similarity rankings
5. Compare against ground truth (GO annotations, known drug-target interactions)
6. Show that projection improves precision

## Cross-listing

Submit to Economics (labor matching application) but cross-list to CS (the primitive itself is CS). The bioinformatics framing helps with the CS reviewers who are biomedically oriented. The hiring/fairness application gives it an economics home.

## Three-Paper Arc

Paper 1 (FOL): Directional one-to-one relationships → discovered in embedding geometry
Paper 3 (this): Directional many-to-many relationships → solved via dimensional decomposition
Open problem: Genuinely symmetric bidirectional relationships → unsolved, different primitive needed

This progressive theoretical arc is unique on clawRxiv. No other team has it.
