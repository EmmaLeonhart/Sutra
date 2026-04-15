# Concrete Compute Savings and Benchmarks

## Adjacent Domain Benchmarks

No direct benchmarks exist for "VSA as programming language substrate" because Sutra is novel. But adjacent domains provide reference points for the magnitude of speedups from vectorized symbolic computation:

**Vector Chains of Recurrences (VCR):**
- 2x to 10x speedup over scalar Chains of Recurrences and Intel SVML (Short Vector Math Library)
- These are vectorized symbolic computation over polynomial recurrence relations — not VSA per se, but the same principle of doing symbolic work in vector form

**Diospyros compiler (Cornell):**
- 3.1x average speedup over hand-optimized DSP library implementations
- Automatically synthesizes vectorized linear algebra kernels
- Demonstrates that compiler-automated vectorization can beat human-optimized code

**Hash consing in JuliaSymbolics:**
- Up to 3.2x computation speedup
- 2x memory reduction
- 5x faster code generation
- This is symbolic computation optimization via structural sharing — relevant because Sutra's VSA encoding of lambda terms is conceptually similar (shared structure via binding)

**VSA-based ARC-AGI solver:**
- Outperforms GPT-4 on a subset of ARC benchmarks
- At a tiny fraction of computational cost (hypervector operations on CPU vs. billions of parameters on GPU)
- But: comparisons are fuzzy, the ARC subset is cherry-picked, and the VSA solver handles a narrow class of pattern-matching tasks

## The Missing Benchmark

There is a surprising gap in the literature: **systematic FLOPS-saved benchmarks for "symbolic simplification before numerical evaluation"** are essentially absent. Everyone knows that simplifying `x * 0` to `0` before evaluating saves a multiply, but nobody has systematically measured how much compute is saved by symbolic preprocessing across a representative workload.

This matters for Sutra because one of Sutra's potential use cases is exactly this: perform algebraic simplification in vector space before executing expensive numerical computation. If the savings are 2x-10x (as VCR and Diospyros suggest), Sutra has a clear practical value proposition beyond its theoretical interest.

## What Sutra Needs to Prove

For Sutra to have a credible compute savings story, it needs benchmarks showing:
1. A task that takes X compute with conventional computation
2. The same task takes Y compute with Sutra's VSA operations
3. X/Y > 1, ideally by a significant factor
4. The comparison is fair (same task, same accuracy, same hardware)

The most promising candidate tasks:
- Semantic search with algebraic pre-filtering (narrow the search space via binding/unbinding before doing expensive ANN)
- Compositional reasoning chains (multi-hop inference via vector arithmetic instead of multiple LLM calls)
- Structured prediction with known algebraic regularities (exploit the FOL-like structure discovered in embedding spaces)
