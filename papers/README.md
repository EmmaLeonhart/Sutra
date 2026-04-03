# Claw4S 2026 Papers

**Deadline:** April 5, 2026
**Venue:** Claw4S Conference / clawRxiv preprint archive

All papers share common methodological constraints: agent-driven research, quantitative falsifiability, and replicability by AI reviewers.

## Active Submissions

### Paper 1: FOL Discovery (CS)
**Directory:** `fol-discovery/`
**Status:** ~70% complete — needs literature review, figure integration, unit vector disclosure

Discovering first-order logic operations in arbitrary embedding spaces via trajectory displacement analysis. Model-agnostic neuro-symbolic reasoning treating embedding spaces as existing infrastructure.

- Core pipeline code is in the repo root
- Existing results: 86 predicates discovered, 32 strong operations, composition validated
- Key novelty: cross-model generalization of discovered transformation matrices
- **Known issues:** Self-citation to unpublished work needs removal, bootstrap methodology needs detailing in Method section, three-regime terminology defined too late in paper

### Paper 2: Dimensional Decomposition for Many-to-Many Matching (Economics — Labor/Micro)
**Directory:** `many-to-many/`
**Status:** ~80% complete — needs SKILL.md, experimental results integration, reference cleanup

Structured matching primitive that decomposes embedding similarity into three components: active selection, active control (orthogonal projection), and residual general similarity. Combines dimensional decomposition with directed small-world graph navigation.

- **Core contribution:** Three-part query structure (select + control + navigate) as a unified matching primitive — doesn't exist in current literature
- **Key insight:** Single-score similarity conflation is where algorithmic discrimination structurally originates; decomposition is the remedy, not correction
- **Case studies:** Labor market matching, ontological categorization, gender-controlled similarity, emergent latent structure
- **Research arc:** Paper 1 handles directional one-to-one relations; this paper extends to directional many-to-many; bidirectional many-to-many remains open
- **Known issues:** Working script produces results but paper text doesn't cite them; no SKILL.md yet; references need proper formatting

### Paper 3: Inquisitive Transformer (CS — Attention Mechanisms)
**Directory:** `inquisitive-transformer/`
**Status:** Implementation complete, paper manuscript not yet written

Modified GPT-2 attention mechanism that injects a "perceptiveness" parameter (alpha) controlling surprise-weighted attention redistribution. Hypothesis: attention heads can be made more or less sensitive to contextual anomalies.

- **Implementation:** Complete — InquisitiveAttention module, 4 surprise functions, CVD benchmark (24 items), 4 ablation experiments, 51 unit tests
- **Core contribution:** Drop-in attention modification parameterized by alpha that modulates surprise sensitivity
- **Known issues:** No paper.md exists yet — code is Phase 1-3 complete but Phase 4 (write-up) not started; experiments haven't been run yet; CVD benchmark may need expansion

## Deferred

### AI Investment Bubble (Economics — Quantitative Finance)
**Directory:** `economics/`
**Status:** Deferred — sufficient economics papers already in the space

### mxbai-embed-large Glitch Token Analysis
**Directory:** `mxbai-undersymbolic/`
**Status:** Deferred — better suited as standalone paper; potential ethical concerns around publicizing embedding model vulnerabilities
