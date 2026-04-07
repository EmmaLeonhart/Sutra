# AI Reviewer Behavior Patterns (Gemini 3 Flash)

Analysis from 15 reviews of the same paper across versions.

## Key Behavioral Patterns

### 1. Keyword/Pattern Matching Dominance
The reviewer heavily pattern-matches methodology descriptions to known frameworks.
When it sees "displacement vector" + "head + relation ≈ tail," it immediately
maps to TransE and calls it unoriginal. It does this regardless of whether
the actual contribution is different from TransE.

**Implication:** We need to avoid triggering the TransE pattern match. Use
different terminology (VSA binding/unbinding) and explicitly say "this is not
TransE" early in the paper.

### 2. Grandiosity Detection
The reviewer punishes names that sound bigger than the method:
- "Latent Space Cartography" → "grandiose for vector subtractions"
- "Three-regime structure" → "lacks rigorous topological grounding"
- "Topological discovery" → punished in early versions

**Implication:** The paper title and method name need to accurately scope the
contribution. Don't call it something grander than what's demonstrated.
VSA framing is risky here — we need to make sure we're not overclaiming.

### 3. Fabrication/Hallucination Suspicion
The reviewer is highly suspicious of results that look "too good":
- Cosine similarity of exactly 1.0 → "mathematically surprising"
- 147,687 collisions → "suggests either catastrophic failure or pipeline error"
- MRR of 1.0 → "suggests the task is trivial"

**Implication:** Extreme results need extensive explanation and controlled
tests. Table 10 (the controlled pairs) was the key to making the collision
claim believable. Any new extreme result needs similar backup.

### 4. Tautology/Circularity Sensitivity
The reviewer aggressively flags anything that looks like circular reasoning:
- Consistency → prediction correlation (9/15 reviews)
- Defining collisions by density then finding them in dense regions (5/15)
- Both of these are partially valid criticisms

**Implication:** Every correlation or finding needs to be explicitly shown
as non-circular. Train/test splits, null models, and ablations are the cure.

### 5. Baseline Comparison Standards
The reviewer consistently wants stronger baselines:
- String overlap null model called a "strawman" (7/15)
- Wants regex or edit-distance baselines
- Wants byte-level tokenizer comparisons (ByT5, Ada-002)

**Implication:** Add at least one more baseline. Edit-distance would be easy
to implement and would satisfy this criticism.

### 6. High Variance on Same Content
Versions 11-15 were submitted within 15 minutes of each other (essentially
the same paper). Reviews ranged from Strong Reject to Strong Accept.

**Implication:** Any single review is noisy. The trend across multiple reviews
is what matters. Don't overreact to a single bad review, but DO address
criticisms that appear consistently across many reviews.

### 7. What It Values Most
In rough priority order:
1. **Actionable empirical findings** (defect discovery = instant credibility)
2. **Cross-model validation** (praised in 13/15 reviews)
3. **Controlled experiments** (Table 10 type evidence)
4. **Practical implications** (RAG, search, production systems)
5. **Statistical rigor** (bootstrap CIs, null models)

Theory, framing, and novelty claims are far less valued than concrete findings.

## Strategic Recommendations for Next Submission

1. **Lead with empirical findings, not theoretical framework**
2. **Frame VSA as "what our results demonstrate" not "what our method is"**
3. **Add train/test split to kill tautology criticism**
4. **Add edit-distance baseline to kill strawman criticism**
5. **Keep the [UNK] defect as the star of the paper**
6. **Explicitly distinguish from TransE in the Related Work section**
7. **Don't overclaim the VSA connection — present it as "consistent with" not "proof of"**
