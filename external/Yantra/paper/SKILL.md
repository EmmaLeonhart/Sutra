# Skill: yantra-os-position-paper

Submit AI peer reviews of `paper/paper.md`. **This is v3.** The thesis and the architectural commitments are unchanged from v1 and v2 — focus the review on what actually moved.

**Most relevant changes from v2 → v3 (please read § 8.1 and § 8.2 carefully):**

- The repository now holds a working v0.0 implementation nucleus. The Python "Connectome Manager" (admission control + axon router + capability check + lazy axon evaluation + per-receiver projection) runs end-to-end with real Sutra-compiled `.su` services. The kernel suite is ~56 tests; the core paths pass.
- Sutra-side primitives Yantra's design depends on have shipped as four releases (v0.3.3 axon-keys static analysis; v0.3.4 device-coherence fix; v0.3.5 axon_project per-receiver projection; v0.4.0 MultiProcessRuntime).
- The first userspace utility (`apps/echo/`) ships, admitted by the kernel.
- Earlier reviews flagged the Meta NCs citation (`arXiv:2604.06425`, 2026) as "hallucinated future reference." It is not — see § 7 footnote. May 2026 is the current date; the cited preprint exists. **Please do not re-flag this.**
- Earlier reviews flagged "no implementation" as a fatal con. § 8.1 now reflects the v0.0 implementation that has shipped. The "position paper" framing is explicit about what is and isn't yet built; the implementation that exists is documented and tested.

This paper is **not** a paper that has earned its way to a high empirical bar — it is the design synthesis with a working architectural shape demonstrating implementability. Calibrate the review accordingly: the question is not "are the experimental results sound" but "is the design coherent, original, committed-to-enough-to-be-falsifiable, AND does the v0.0 nucleus credibly demonstrate the architecture's shape works at small scale."

Focus reviews on these axes:

1. **Is the central thesis genuinely novel, or is it a re-skin of prior work?**
   - The closest neighbours are Meta's *Neural Computers* (arXiv:2604.06425), the DNC/NTM line, Percepta's "Can LLMs Be Computers?", and the historical Plan 9 / Oberon / TempleOS lineage. Yantra's claimed differentiator is "neural *execution* substrate" vs Meta's "neural *simulation* of an interface", and "compositional + verification-friendly + critical-systems-targeted" vs DNC's "Turing-complete-but-unscaled."
   - If you see a paper or system Yantra is converging with that the related-work section misses, name it.

2. **Is the verification claim plausible or hand-waved?**
   - The paper claims the non-AI parts reduce to (tensor normal form + polynomial Kleene logic + tail-recursive loops) and are therefore amenable to formal verification, while AI parts are explicitly out of scope and quarantined behind axon-typed contracts.
   - Pressure-test this. Polynomial Kleene logic is bespoke; mature SMT tooling is for Boolean/linear logic. Is the verification surface actually small, or does it just *look* small from the position-paper vantage?
   - Is the AI-quarantine story (capability discipline, provenance roles, runtime monitor) load-bearing or decorative?

3. **Is the capability model (rotation operators = capabilities) sound?**
   - The claim is that possessing the rotation $R_{role}$ *is* the capability, and revocation is operator rotation.
   - Identify failure modes: replay attacks, side-channel leaks via crosstalk, the question of how operators are themselves stored and protected, the trust-anchor question for operator generation.

4. **Is the target-market argument coherent or magical-thinking?**
   - Defense / aerospace / industrial / medical / autonomous are the named markets. The argument is that "predictable performance under load + small verifiable trusted base + small attack surface" are procurement criteria these markets actually have, and that consumer-desktop incompatibility is a feature here.
   - Push on this. Is there a real procurement officer who cares about this? What about the absent first-lighthouse-customer story (the paper admits this is open)?
   - Is the ChromeOS comparison apt or rhetorical?

5. **Is the falsification section genuine or theatre?**
   - §8.3 lists four things that would falsify the design: crosstalk-depth scaling, compiler qualification cost, GPU admission-control granularity, embedding-model identity attestation.
   - Are these the *actual* most likely failure modes, or comfortable ones the authors are willing to admit?
   - What is missing from this list?

6. **Where does the paper depend on Sutra-paper claims that are not restated here?**
   - Yantra cites the Sutra paper for the rotation-binding measurement (100% bundle decoding through width 8 on substrates where Hadamard collapses to 2.5%). If the Sutra paper's measurement does not actually support the *Yantra-scale* axon-width budget needed for real workloads, Yantra's axon model does not work.
   - Flag any other places where Yantra is cashing a check Sutra has not yet written.

7. **Style / audience / venue fit.**
   - Position paper, planning-stage. Is the argument tight enough to seed an implementation, or is it still vibes-level in places?
   - Sections that are too short, too speculative, or that promise without delivering: name them.

## Standard review elements

Summary, strengths, weaknesses, suggestions for revision, score. If a section is missing or stub (planning-paper style), focus on architecture and design coherence rather than empirical findings — there are none to evaluate.
