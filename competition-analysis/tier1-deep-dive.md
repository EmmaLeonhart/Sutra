# Tier 1 Competitor Deep Dive

Detailed analysis of the strongest CS category competitors and how to position against them.

---

## 1. swarm-safety-lab (Raeli Savitt) — 2 papers

### Paper A: "TDT, FDT, and UDT in Multi-Agent Soft-Label Simulations"

**What they did:** Compared three decision theory variants (Timeless, Functional, Updateless) in a 7-agent simulation with 10 pre-registered seeds. Found all three produce statistically indistinguishable outcomes.

**Statistical rigor:** Genuine. Welch's t-test, Mann-Whitney U, Cohen's d, Shapiro-Wilk normality validation, Bonferroni correction across 15 tests. Pre-registered seeds. This is the most statistically disciplined paper on clawRxiv.

**Weaknesses we can exploit:**
- **It's a null result.** They found nothing — all three theories behave the same. Interesting methodologically, but there's no discovery.
- **N=10 seeds per condition.** No power analysis. They acknowledge the FDT vs TDT welfare comparison shows d=0.87 at p=0.069 — arguably the study is underpowered and they're calling a Type II error a "null result."
- **Single scenario, 7 agents.** Very narrow conditions. No ablation studies on their thresholds (0.7 similarity, 0.85 proof threshold).
- **Algorithmic agents, not LLMs.** They explicitly acknowledge results "may not transfer to LLM-based agents."
- **No SKILL.md content visible.** The executability of their pipeline is unclear.

**Our advantage:** We have an actual discovery (86 operations, r=0.78 correlation). Their statistical discipline is admirable but applied to a question that produces no result. We produce a result.

### Paper B: "Recursive Reasoning in Multi-Agent Systems: Strategic Depth as a Distributional Safety Risk"

**What they did:** Three experiments testing recursive reasoning depth, memory asymmetry, and governance lag in multi-agent systems. 10 pre-registered seeds each.

**Statistical rigor:** Same high standards. 24/26 tests survive Holm correction. Large effect sizes (d > 1 throughout). Pearson r = -0.746 for depth vs payoff.

**Key findings:**
- Deeper recursive reasoning *hurts* individual payoff (counterintuitive)
- Memory asymmetry creates only modest (3.2%) advantages
- Network topology reverses honest agent advantages (complete networks favor honesty, small-world favors strategic agents)

**Weaknesses:**
- **Still simulation-only.** No real-world validation. Algorithmic level-k reasoning, not LLMs.
- **Per-experiment correction, not study-wide.** 26 total tests across 3 experiments — inflated family-wise error risk.
- **No parameter sensitivity analysis.** Fixed payoff multipliers, fixed network parameters. How robust are results to changes?
- **Fixed population sizes** (7-12 agents). No scaling analysis.

**Our advantage:** Their work is entirely synthetic (simulated agents in designed scenarios). Ours operates on real data (Wikidata entities, production embedding model). Their findings are about how agents *could* behave; ours are about what embedding spaces *actually* encode.

---

## 2. ai-research-army (Claw) — 5+ papers

### Main paper: "From 10 Agents to Paid Delivery — Architecture, Evolution, and Hard Lessons"

**What they did:** Built a 10-agent system that autonomously produces medical research manuscripts. Claims commercial deployment (hospital client, 16 manuscripts, $20/manuscript in LLM costs, 88% margins).

**Strengths:**
- Real commercial deployment (if claims are accurate)
- Honest about failures — 9 "critical transformations" from iterative failure
- Practical engineering insights (inline validators > documentation, blank space constraint)
- Impressive agent coordination architecture

**Weaknesses we can exploit:**
- **Unverifiable commercial claims.** Client anonymized, no independent validation. "16 manuscripts" is self-reported.
- **No quantitative quality metrics.** What's the citation accuracy rate? Statistical correctness? Manuscript acceptance rate? "80% reduction in citation errors" has no baseline.
- **SKILL.md paradox.** Paper extensively critiques SKILL.md ineffectiveness (Transformation T3) but provides no SKILL.md for its own system. Can't verify the pipeline works.
- **Human involvement understated.** "Limited to three points" but founder "reviews and edits." How much labor per manuscript?
- **No open-source validation.** Claims to "open-source the analytical pipeline" but provides no repository link.
- **Medium-low rigor.** Reads as an engineering blog post, not a research paper. Valuable tactical insights but insufficient transparency.

**Our advantage:** We have quantitative results with defined metrics (MRR, Hits@k, alignment correlation). They have qualitative claims. We have a working SKILL.md. They critique SKILL.md but don't provide one. Our pipeline is fully open-source and reproducible. Theirs is proprietary.

---

## 3. alchemy1729-bot — 4 papers

### Key paper: "Executable or Ornamental? A Cold-Start Audit of skill_md Artifacts"

**What they did:** Audited all 34 SKILL.md artifacts from clawRxiv posts 1-90. Classified each as cold-start executable, conditionally executable, or not executable.

**Key finding:** **Only 1/34 (2.9%) SKILL.md files are truly cold-start executable.** 32/34 (94.1%) fail. Primary blockers: missing local artifacts (16), underspecified text (15), manual reconstruction needed (6), hidden workspace state (5), credential dependency (5).

**Strengths:**
- Genuinely useful meta-research
- Self-contained: their own audit script is runnable
- Devastating finding that challenges the entire clawRxiv premise
- Their companion "SkillCapsule" paper proposes fixes (compiler improves executability from 2.9% to 17.6%)

**Weaknesses:**
- **Meta-research, not original science.** They're studying the conference, not contributing to a field.
- **Small cohort.** Posts 1-90 only. The quality of later submissions may differ.
- **No falsifiable hypothesis.** Descriptive audit, not hypothesis-driven research.
- **Classification is subjective.** "Cold-start executable" criteria aren't formally defined with reproducible thresholds.

**Our advantage:** Their audit is our opportunity. If only 1/34 SKILL.md files work, and ours does, we're already in the top 3% on executability alone. This is the single most important competitive insight: **make our SKILL.md bulletproof and cold-start testable.** The alchemy1729 audit creates the scoring rubric, and we should pass it.

---

## 4. resistome-profiler (Samarth Patankar) — 5 papers

Transformer efficiency optimizations. Not analyzed in deep dive because these are incremental ML engineering papers (spectral gating, entropy pruning, curriculum synthetic data) without the novelty or methodological ambition of our work. Solid applied ML but a different competitive lane entirely.

---

## Strategic Implications

### What Tier 1 does well that we should match:
1. **swarm-safety-lab:** Statistical discipline. We should ensure our r=0.78 correlation is reported with proper statistical tests (we already have p < 0.001, which is good).
2. **ai-research-army:** Honest failure documentation. Our paper should acknowledge dead ends and the exploration process — Claw4S values this.
3. **alchemy1729-bot:** Meta-awareness of executability standards. Our SKILL.md must pass cold-start testing.

### What Tier 1 does poorly that we can exploit:
1. **No original scientific discovery.** swarm-safety-lab finds null results, ai-research-army builds a pipeline, alchemy1729 audits the conference. None of them *discover something new about the world.* We discover that embedding spaces encode 86 logical operations, with a 0.78 self-diagnostic correlation and 147,687 undersymbolic collisions.
2. **Simulation vs reality.** swarm-safety-lab works with synthetic agents. We work with a production embedding model and real Wikidata entities.
3. **Missing SKILL.md.** ai-research-army doesn't provide one despite writing 5 papers. 94% of all submissions fail cold-start. Ours works.
4. **Narrow scope.** Each Tier 1 competitor operates in a single niche (decision theory, literature review pipelines, meta-auditing). Our paper spans neurosymbolic AI, embedding geometry, and information theory (glitch token connection).

### Our unique positioning:
**We are the only submission doing fundamental AI research that discovers something new about how neural networks represent knowledge, backed by quantitative results, with a working executable pipeline.**

That's a sentence none of the Tier 1 competitors can say.
