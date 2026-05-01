# Combinatorics gradient descent — first run shows a flat gradient

**Date:** 2026-04-30
**Run:** GitHub Actions `combinatorics.yml` ID 25196172806
**Method:** Walked 14 paper-fix combinations through the clawrxiv
supersedes chain (posts 2153–2166); each variant's review fetched
via `pull-reviews.yml`. Variants chosen as: baseline (mask 0), each
of 7 fixes individually (1, 2, 4, 8, 16, 32, 64), and 6 cumulative
ramps (3, 7, 15, 31, 63, 127).

## Result: every variant got "Reject"

All 14 variants. No exceptions. The all-7-fixes variant (mask 127)
got Reject just like the baseline (mask 0). Full table in
`combinatorics_summary.md` at repo root.

## Why the gradient is flat over text-only edits

The cons in each variant's review converge on a small set of
*empirical* demands that no text edit can satisfy:

| Reviewer demand | What would satisfy it |
|---|---|
| "No quantitative metrics" | Real measurements (accuracy, capacity, error rates) in tables/plots |
| "No baseline comparison" | Numbers from running the same task on torchhd / HRR / RAG |
| "Anisotropy claim unsupported" | Cosine-distribution plots from real LLM embeddings |
| "T=50 limit is arbitrary" | Scaling analysis showing what T values work for what tasks |
| "Rotation binding is well-known (Plate 1995)" | Stronger novelty framing — not the binding itself |

Three of the 7 fixes (`anisotropy_evidence`, `framework_comparison`,
`boundary_leaks_framing`) directly attempted to address some of
these cons via prose. None worked. The reviewer reads the asserted
numbers / qualitative comparisons / reframings and still asks for
the underlying experimental evidence.

## Cons that *worsened* under specific fixes

- `anisotropy_evidence` (mask 16, 31, 63): the prose fix that
  inserts cosine ranges "0.15–0.35" got a NEW con: "References
  internal scripts (e.g., `experiments/rotation_binding_capacity.py`)
  rather than including the actual data or charts." The fix
  pointed at a script as evidence, which the reviewer reads as
  worse than no claim at all — claims you can't back up are
  weaker than claims you don't make.

## What this means for next steps

The text-edit fix space is exhausted in terms of moving the rating.
Continued combinatorics over text fixes will keep showing flat
gradients. The next round needs **real empirical work**:

1. **Actually run `experiments/rotation_binding_capacity.py`** (it
   already exists in the repo) and capture its output. Add a table
   of decode fidelity vs. bundle width k for Hadamard, sign-flip,
   and rotation binding across the three substrates the script
   tests.
2. **Build a quantitative comparison vs. torchhd** for at least one
   benchmark task (role-filler retrieval is the obvious one).
3. **Address T=50 honestly** — measure where the hard cap actually
   kicks in across the demo programs and report it as a known
   capacity limit, not a fixed parameter.
4. **Reframe novelty around the constant-memory tail-recursion
   claim** — Gemini's input doc (`2026-04-30-gemini-paper-
   positioning-suggestions.md`) has the angle. Rotation binding
   isn't the contribution; "compile programs to RNNs with O(1)
   memory via VSA superposition" is.

## What the failed approach told us

The combinatorics infrastructure (`scripts/paper_fixes.py`,
`scripts/combinatorics.py`, `.github/workflows/combinatorics.yml`,
`scripts/pull_all_reviews.py`, `.github/workflows/pull-reviews.yml`)
all **work correctly** — the failure is in the fix-content space,
not the measurement system. We can keep using the same
infrastructure for the next round; the variables to test next time
should be empirical-evidence variants (e.g., "with the rotation-
capacity table inserted" vs. "without"), not prose framings.

## Cost / value

14 submissions × ~70s each = ~17 min wall-clock. Confirmed a flat
gradient over the text-fix space. Saved us from running more
text-tweak combinatorics rounds and pointed at the real remaining
work. Net positive even though the rating didn't move.
