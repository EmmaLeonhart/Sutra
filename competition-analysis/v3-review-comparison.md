# V3 Review Comparison — What Changed

## FOL Discovery: v1 (Reject) → v2 (Reject) → v3 (Reject)

### What improved v2→v3:
- **Hallucination flag GONE** — removing Li & Sarwate citation worked. No citation issues raised.
- **"Idiosyncratic terminology" critique GONE** — replacing oversymbolic/isosymbolic/undersymbolic with standard terms worked.
- **Pros increased** from 3→4→4 and are more substantive (mentions "universal core of 30 relations", "architectural invariance")

### New critiques in v3:
- **"Discovered relations are trivial string template artifacts"** — P2633 "history of topic" just captures the prefix "history of", not relational knowledge. MRR=1.0 is suspicious because the task is trivial.
- **Collision geography still called circular** — despite reframing, reviewer says collision=density is definitional
- **Needs string manipulation baseline/null model** — to prove vector arithmetic does more than identify subword additions
- **Engishiki seed may overstate the collapse** — 147K collisions from 41K embeddings suggests degenerate clusters

### Assessment:
Citation and terminology fixes worked perfectly. The paper is no longer rejected for superficial reasons. The NEW critiques are deeper and more substantive — the reviewer is now engaging with the actual methodology rather than dismissing it. This is progress, even though the rating is unchanged.

**To fix:** Add a string-overlap null model baseline. Address the trivial template issue. Acknowledge MRR=1.0 reflects label similarity patterns.

---

## Many-to-Many: v1 (Strong Reject) → v1.5 (Strong Reject) → v2 (Strong Reject) → v3 (Strong Reject)

### What improved v2→v3:
- **Self-citation hallucination flag reduced** — no longer cites "Leonhart (2026)" or "clawrxiv". But reviewer still flagged "references 'our prior work' without citations" as "hallmark of AI-generated text"
- **Small-world critique GONE** — completely removed, no longer mentioned

### New/persistent critiques in v3:
- **"Trivial mathematical modification"** — weighted sum of dot product and projection is not novel
- **Abstract/body contradiction** — abstract says "10/12" but Section 5.2 says "9/9" (we left old abstract!)
- **Target direction from exemplars called "supervised"** — our clarification didn't convince; reviewer says it's biased
- **Control-only failing contradicts Bolukbasi literature** — reviewer says if our control-only doesn't help, something is wrong with implementation
- **Still too small** — 29-41 candidates remains "extremely weak"
- **Mathematical notation imprecise** — proj_t(e) ambiguous

### Assessment:
Rating unchanged despite major fixes. The fundamental problem: the reviewer sees the contribution as trivial (a weighted sum) and the experiments as too small. Removing self-citations and small-world helped but the core isn't convincing yet.

**To fix:** Fix abstract/body contradiction (10/12 vs 9/9). Scale to hundreds of candidates. Add a strong baseline (INLP or cross-encoder). Clean up notation. Frame as empirical finding, not novel primitive.

---

## Economics: v1 (Reject) → v2 (Strong Reject) → v3 (Strong Reject)

### What improved v2→v3:
- **Dateline issue partially addressed** — but reviewer found "retrieved on March 26, 2026" in the actual data/scripts, not just the paper text

### Persistent/new critiques:
- **"Data retrieved March 26, 2026" still present** — the retrieval date is embedded in the script output, not just the prose
- **Microsoft -11.8% return called factually incorrect** — reviewer says actual 2022-2024 performance was +70%. This may be a real data error in our scripts.
- **"Pure-play AI" definition too restrictive** — ignores Palantir, C3.ai, SoundHound
- **P/E analysis masks AI premium** — diversified conglomerates' non-AI earnings dilute the ratio

### Assessment:
The temporal problem is deeper than prose — it's in the data pipeline itself. The Microsoft data error may be a genuine bug worth investigating. This paper may need the most fundamental rework.

---

## Summary: Version-over-Version Progress

| Paper | v1 Rating | v2 Rating | v3 Rating | Hallucination flag | New substantive critiques |
|-------|-----------|-----------|-----------|-------------------|-------------------------|
| FOL | Reject | Reject | Reject | Gone ✓ | String template trivality, need null model |
| M2M | Strong Reject | Strong Reject | Strong Reject | Reduced but not gone | Abstract contradiction, notation, "trivial math" |
| Econ | Reject | Strong Reject | Strong Reject | Partially addressed | Microsoft data error, date in scripts |

**Key insight:** Fixing superficial issues (citations, terminology, unimplemented sections) works — those critiques disappear. But the reviewer then finds deeper issues with the actual methodology. The FOL paper is closest because its core methodology is sound; it just needs a null model baseline. The M2M paper needs a fundamentally larger experiment. The economics paper has a data integrity issue that may be a real bug.
