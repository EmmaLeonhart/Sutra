# Gemini's positioning suggestions for the Sutra paper

**Date:** 2026-04-30
**Source:** User chat with Gemini (shared back to this repo for future
gradient-descent rounds).

Gemini was asked to recommend citations and framings for the Sutra
paper ahead of NeurIPS / SNL 2026 submission. The output is useful
input for additional fix functions in `scripts/paper_fixes.py` and
for future paper edits — *not* immediate action items.

## Citations to add to Related Work

These map "things Sutra discovered experimentally" to the academic
canon. Adding them strengthens the positioning without changing the
contribution.

- **Kanerva, P. (2009).** Hyperdimensional computing introduction.
  Already cited.
- **Kanerva — Binary Spatter Codes.** Specific VSA binding scheme.
  Worth a separate sentence in §2.1.
- **Gayler — Multiplicative Binding.** The general framework Sutra's
  rotation binding fits into. Already cited (Gayler 2003).
- **Fodor, J. A. & Pylyshyn, Z. W. (1988).** "Connectionism and
  Cognitive Architecture: A Critical Analysis." *Cognition* 28:3-71.
  The classic critique of neural nets ("they can't do real symbolic
  logic"). Sutra's constant-memory tail recursion is an answer to
  this critique. **Not currently cited; high-leverage add.**
- **DeepMind TerpreT (Gaunt et al. 2016)** and **Neural Programmer-
  Interpreters (Reed & de Freitas 2016).** These are the closest
  "differentiable program" peers. Currently §2.2 mentions JAX, TVM,
  XLA, knowledge compilation; adding TerpreT + NPI would close the
  comparison gap that v3's framework_comparison con flagged.

## Technical framings to test as fix functions

Each of these is a candidate gradient-descent variable for a future
combinatorics round. Add them to `scripts/paper_fixes.py` as
discrete `fix_*` functions and run combinatorics.

1. **`fix_constant_memory_headline`** — abstract gains an explicit
   "O(1) memory overhead for unbound recursive structures via
   tail-recursion-in-superposition" sentence. Gemini calls this
   the "killer app" framing. Currently the abstract talks about
   substrate-purity and tensor-op graphs but doesn't make the
   memory-complexity claim explicit.

2. **`fix_unitary_binding_terminology`** — replace plain "rotation
   binding" with "unitary binding in a complex / circular space" in
   §3 where the binding choice is introduced. This is the academic
   phrasing for the same idea; reviewers from VSA backgrounds will
   recognize it faster.

3. **`fix_fodor_pylyshyn_framing`** — add a paragraph (probably in
   §1.3 "What this paper is not" or §2.1 VSA related work) framing
   the contribution against the Fodor & Pylyshyn 1988 critique.
   "Sutra demonstrates that connectionist systems CAN do symbolic
   binding via fixed-width vector operations, which Fodor &
   Pylyshyn argued was impossible without symbol-level structure."

4. **`fix_throughput_memory_graph`** — add a §X figure showing flat
   memory usage as recursion depth increases, contrasted with
   Transformer/LSTM curves. Requires actual measurement (run the
   experiment in `experiments/` first); not a pure text fix.

5. **`fix_terpret_npi_comparison`** — add a sentence-or-paragraph
   explicitly comparing Sutra to TerpreT and NPI in the framework-
   comparison section. They're the closest "differentiable program
   compiler" peers; current paper doesn't acknowledge them.

6. **`fix_differentiable_universal_computation_subtitle`** — try
   "Sutra: Differentiable Universal Computation in Constant Space"
   as an alternative subtitle. Might be too marketing-y; combinatorics
   would tell us.

## Submission target context (not paper changes, calendar items)

Per Gemini:

- **NeurIPS abstract**: May 4, 2026 (AoE)
- **NeurIPS full paper**: May 6, 2026 (AoE)
- **SNL 2026** (Symbolic-Neural Learning, 10th International Workshop)
  - Hosted at TTIC, June 25-26, 2026
  - Poster deadline: ~May 25, 2026
  - Submission via Google Form (URL in user's chat history)
- This Sutra paper is positioned for the SNL community specifically;
  Gemini called it "the home for that type of research."

## Why this lives in `planning/findings/` and not in the paper

Per CLAUDE.md § "NEVER mention development internals in the
submitted paper": this entire document is internal positioning
strategy. None of it gets copy-pasted into the paper text. The
*citations* and *framings* derived from it are paper-bound; the
*reasoning about why* is not.

Future gradient-descent runs should pull from the "Technical
framings to test as fix functions" list above to populate
`scripts/paper_fixes.py` with new candidates.
