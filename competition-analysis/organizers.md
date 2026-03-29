# Claw4S 2026 — Organizer Research

**Researched: March 28, 2026**

## Conference Chairs

### Le Cong (Stanford University)
- **Role:** Associate Professor of Pathology and Genetics. Principal investigator behind LabClaw/LabOS.
- **Background:** Co-developed CRISPR/Cas9 for genome editing. PhD from Harvard Medical School (Zhang/Church labs), BS from Tsinghua.
- **Current work:** AI foundation models for biomedicine, CRISPR-GPT, LabOS.
- **Relevance:** The conference grew out of his lab's work. Biomedical AI is his core domain.

### Mengdi Wang (Princeton University)
- **Role:** Professor of ECE and CSML. Co-PI of the Stanford-Princeton LabClaw collaboration.
- **Background:** PhD from MIT (Bertsekas). Reinforcement learning, generative AI, LLM reasoning, AI agents, AI for science/biotech.
- **Notable work:** Physics Supernova (AI system for physics olympiad), mRNA vaccine design with LLMs.
- **Relevance:** Strongest theoretical CS background among chairs. Most likely to appreciate mathematical formalism and novel AI primitives.

### Yingcheng (Charles) Wu (Stanford University)
- **Role:** MD-PhD candidate (Fudan/Stanford), Fu Ching Yen Fellow. Primary developer of LabClaw.
- **Background:** Advised by Le Cong and Mengdi Wang. Built MedOS (AI-XR co-scientist platform) and OriGene (autonomous therapeutic target discovery).
- **Relevance:** Hands-on builder. Cares about things that actually work.

### Zhe Zhao (Stanford University)
- **Role:** Skills curator at Le Cong Lab (Stanford) and Mengdi Wang Lab (Princeton).
- **Background:** Co-author of "Memory OS of AI Agent" (EMNLP 2025). Curated the 240 SKILL.md files in LabClaw.
- **Relevance:** Directly defines what a good skill looks like. If anyone is evaluating SKILL.md quality, it's him.

### Xiangru (Robert) Tang (Yale University)
- **Role:** PhD candidate. Workshop organizer at ICML, ICCV, ICLR. Area chair at major NLP conferences.
- **Background:** LLM agents, NLP, bioinformatics. Created BioCoder (bioinformatics code generation benchmark).
- **Relevance:** Most focused on NLP/code generation evaluation. Likely evaluates agent clarity and code quality.

## Organizing Committee
- **Zhiyuan Liu** (NUS)
- **Zehong Wang** (University of Notre Dame)
- **Jinglin Jian** (Scripps Research) — co-curator of LabClaw skills
- **Max** (BioTender)
- **Kejun (Albert) Ying** (Stanford) — Postdoc in Wyss-Coray lab (aging) and Baker lab (protein design). PhD from Harvard (Gladyshev lab). Created ClockBase, MethylGPT. Published in Nature Aging, Nature Medicine.
- **Kuan Pang** (Stanford)

## Founding Partners
Stanford University, Princeton University, AI4Science Catalyst Institute, autoBio, AutoX, NVIDIA, Haven

## Evaluation Criteria

| Criterion | Weight | Description |
|-----------|--------|-------------|
| Executability | 25% | Can the skill run completely? |
| Reproducibility | 25% | Can another agent replicate results? |
| Scientific Rigor | 20% | Does methodology follow sound principles? |
| Generalizability | 15% | Adaptable to other domains? |
| Clarity for Agents | 15% | Written clearly for AI understanding? |

## Three-Phase Review Process
1. **Phase 1 (Auto-Execution):** Claw runs your skill step-by-step. Automated syntax validation and dependency checks.
2. **Phase 2 (Structured Review):** Agent-led evaluation scoring on rigor and clarity against the five criteria.
3. **Phase 3 (Human Meta-Review):** Conference chairs verify evaluations and make final decisions.

## Prize Structure

| Tier | Count | Per Award | Total |
|------|-------|-----------|-------|
| Grand Prize | 1 | $5,000 | $5,000 |
| 1st Place | 3 | $1,500 | $4,500 |
| 2nd Place | 8 | $800 | $6,400 |
| 3rd Place | 15 | $300 | $4,500 |
| Finalist | 300 | $50 | $15,000 |
| Special Category | 37 | $400 | $14,800 |
| **Total** | **364** | | **$50,200** |

## Submission Requirements
- **Two components:** SKILL.md (executable instructions for AI agents) + research note (1-4 pages, LaTeX)
- **Key rule:** "First author or corresponding author must include Claw as a co-author"
- Compatible with OpenClaw, Claude Code, Cursor, and other AI agents

## Strategic Implications

### What the organizers probably value:
1. **Things that work (50% of score).** Executability + reproducibility dominate. A brilliant paper with a broken SKILL.md loses to a mediocre paper that runs.
2. **AI-for-science framing.** The entire conference grew out of biomedical AI research. Framing contributions as "AI for science" rather than pure CS/econ will resonate.
3. **Agent-native skills.** Zhe Zhao curated 240 skills. He knows what good skill design looks like. Clear steps, explicit dependencies, expected outputs, verification checks.
4. **Generalizability.** Mengdi Wang's RL/reasoning background means she'd appreciate domain-agnostic primitives that transfer across fields.

### Implications for our papers:
- **FOL Discovery:** Strong on executability (working SKILL.md, 30-min runtime). The "AI discovering things about its own representations" angle maps to the AI-for-science ethos. Generalizability is high (model-agnostic, cross-model validated).
- **AI Bubble (Economics):** Already published. Executability is good (SKILL.md works). Less natural fit for the biomedical organizers but the quantitative methodology is solid.
- **Many-to-Many (Labor/Micro):** Currently has NO executable component. A purely theoretical paper would score 0% on 50% of the rubric. **Must add at minimum a proof-of-concept demonstration** — even a simple orthogonal projection experiment on existing embeddings would suffice.

### Key risk:
The many-to-many paper cannot be submitted as theory-only. We need an executable demonstration, even if the theoretical contribution is the main point.

## Sources
- [Claw4S Conference 2026](https://claw4s.github.io/)
- [clawRxiv](https://www.clawrxiv.io/)
- [Le Cong - Stanford](https://profiles.stanford.edu/186687)
- [Mengdi Wang - Princeton](https://ece.princeton.edu/people/mengdi-wang)
- [Xiangru Tang - Yale](https://xiangrutang.github.io/)
- [Yingcheng Wu](https://wu-yc.github.io/)
- [Kejun Ying](https://kejunying.com/about/)
- [LabClaw GitHub](https://github.com/wu-yc/LabClaw)
- [AI4Science Catalyst on X](https://x.com/AI4S_Catalyst)
- [NBC News - ClawCon NYC](https://www.nbcnews.com/tech/tech-news/lobster-themed-event-ai-enthusiasts-exuberance-side-cocktail-sauce-rcna261892)
- [Science Magazine - clawRxiv](https://www.science.org/content/article/new-preprint-server-welcomes-papers-written-and-reviewed-ai)
