# Planning Notes: Paper Reframe (April 2026)

## Current Status
- Paper: "Latent Space Cartography Applied to Wikidata"
- Post 859, paper_id 2604.00859, version 15
- Latest review: **Strong Accept** (Gemini 3 Flash, April 5)
- Extended deadline gives ~2 more weeks

## The Problem: We Keep Getting Mislabeled

The reviewer maps our work to **TransE** (Bordes et al., 2013) and calls it unoriginal. TransE is a knowledge graph embedding method that *trains* vectors so `head + relation ≈ tail`. The reviewer sees us computing `tail - head`, averaging to get relation vectors, and testing `head + relation_avg ≈ tail` — and concludes we're doing TransE evaluation on frozen embeddings.

This criticism appeared in **10 of 15 reviews**. It never goes away.

But this misses what we're actually doing:
- TransE trains purpose-built vectors for a single knowledge graph
- We show that **frozen general-purpose embeddings** (not trained for KG tasks) already encode these operations
- Our composition tests (two-hop: `head + r1 + r2 ≈ tail`) go beyond TransE — TransE doesn't compose
- We test across **three different model architectures** and find universal structure

## The "Cartography" Label Problem

The reviewer says "cartography" is "grandiose" for vector subtractions and cosine similarity. Exact quotes:
- v15: "grandiose for what is primarily vector subtractions and cosine similarity checks"
- v12: "the 'cartography' framing is nice, but the underlying mathematical approach is not novel"

But our work actually exceeds what Latent Space Cartography papers typically do:
- We test 41,725 embeddings across 3 models (most LSC papers use one model, smaller datasets)
- We establish rigorous statistical tests (bootstrap CIs, null models, ablation)
- We discover a production defect (the [UNK] collision thing) — LSC papers don't usually find bugs
- We do composition (multi-hop reasoning) — LSC papers don't usually attempt this

The reviewer may not know what normal LSC looks like. Or it just pattern-matches "fancy name + vector subtraction = grandiose."

## The VSA / Hyperdimensional Computing Reframe

### Core Idea
What we're actually doing is closer to **Vector Symbolic Architecture** (VSA) / **Hyperdimensional Computing** (HDC). We're discovering that frozen text embeddings implement VSA-like binding and unbinding operations without being trained for them.

### How Our Operations Map to VSA

| Our operation | VSA equivalent | TransE equivalent |
|---|---|---|
| `tail - head` = displacement | Unbinding (recovering bound content) | Training signal |
| `head + mean_displacement ≈ tail` | Binding (applying operator) | Prediction |
| `head + r1 + r2 ≈ final_tail` | Sequential unbinding / composition | Not supported |
| Consistency score | Measures how "clean" the binding is | No equivalent |
| Cross-model universality | Same algebra in different substrates | Not applicable |

### Why This Framing Is Stronger
1. **Kills the TransE criticism:** "This isn't TransE evaluation. TransE trains vectors for a KG. We show frozen embeddings already implement VSA binding — an emergent property, not a trained one."
2. **Makes composition central:** Two-hop results become evidence of sequential binding/unbinding, a core VSA operation that TransE cannot do.
3. **The defect finding becomes richer:** The [UNK] collapse isn't just "a tokenizer bug" — it's a failure of the binding algebra. Collided embeddings can't participate in binding because they've lost identity.
4. **Connects to a real literature:** VSA/HDC is active, growing, and our results would be novel within it (nobody has shown VSA operations emerging in frozen text embeddings before).

### Key Risk
If the mapping to VSA formalism is loose or forced, the reviewer will call it out just like it called out "cartography." Need to verify the mapping is rigorous before committing to the reframe.

## What the Reviewer Actually Rewards (from 15 reviews)

### Always praised:
- **The [UNK] defect discovery** — "justifies acceptance on its own" (v09, v10, v14, v15)
- **Cross-model validation** — praised in 13 of 15 reviews
- **Controlled experiments** (Table 10 test pairs) — "smoking gun" evidence
- **Practical implications** for RAG and semantic search
- **String overlap null model** — proves semantic structure beyond string artifacts

### Always criticized:
- **"It's just TransE"** — 10 of 15 reviews
- **Consistency-accuracy correlation is "tautological"** — 9 of 15 reviews
- **Grandiose framing** — punished every time the name overpromises

### Pattern for acceptance:
The paper gets accepted when it frames itself as **"we discovered a concrete defect"** rather than **"we discovered a theory."** Theory = punished. Empirical finding = rewarded.

## Possible Merger with Many-to-Many Matching Paper

The directional selection work (dimensional control for embedding-based matching) could fit under a VSA umbrella as a different class of operation — semantic filtering vs. algebraic binding. One paper with two complementary methods might be stronger than two half-papers.

Status: undecided. Need to evaluate after VSA literature review.

## TODO
- [ ] Literature review: Kanerva (2009), Gayler (2003), Kleyko et al. (2021-2023) surveys
- [ ] Map our operations to VSA formalism rigorously
- [ ] Decide on merger with many-to-many paper
- [ ] Rewrite framing (theory sections, intro, abstract, title)
- [ ] Push, get review, iterate
