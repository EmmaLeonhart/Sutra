# Combinatorics review results — first run, 14 variants, all Reject

Run: GitHub Actions `combinatorics.yml` ID 25196172806, completed
2026-04-30. Walked 14 paper-fix combinations through the clawrxiv
supersedes chain (posts 2153–2166), each variant's review fetched
asynchronously via `pull-reviews.yml`.

| post | mask | label | rating | applied fixes |
|---:|---:|---|---|---|
| 2153 | 0 | `fixes_0000000` | Reject | (baseline — no fixes) |
| 2154 | 1 | `fixes_1000000` | Reject | demo_count |
| 2155 | 2 | `fixes_0100000` | Reject | claude_md |
| 2156 | 3 | `fixes_1100000` | Reject | demo_count, claude_md |
| 2157 | 4 | `fixes_0010000` | Reject | section_61_jargon |
| 2158 | 7 | `fixes_1110000` | Reject | demo_count, claude_md, section_61_jargon |
| 2159 | 8 | `fixes_0001000` | Reject | boundary_leaks_framing |
| 2160 | 15 | `fixes_1111000` | Reject | + boundary_leaks |
| 2161 | 16 | `fixes_0000100` | Reject | anisotropy_evidence |
| 2162 | 31 | `fixes_1111100` | Reject | + anisotropy |
| 2163 | 32 | `fixes_0000010` | Reject | framework_comparison |
| 2164 | 63 | `fixes_1111110` | Reject | + framework_comparison |
| 2165 | 64 | `fixes_0000001` | Reject | remove_acknowledgments |
| 2166 | 127 | `fixes_1111111` | **Reject** | **ALL 7 FIXES** |

## Headline finding

**The gradient is flat. Every variant — including the one with all 7
fixes applied — gets Reject.** The text-only fix space we tested
does not move the rating from the baseline (Reject) regardless of
combination.

## What the cons reveal across variants

Even though the ratings don't move, the cons shift slightly across
variants — and the pattern reveals what the reviewer actually wants:

1. **"No quantitative evaluation"** appears in 14/14 variants. Even
   the `anisotropy_evidence` fix (which inserts asserted cosine
   ranges 0.15–0.35) gets dinged because it doesn't show *actual
   data* — just claimed ranges. The reviewer wants tables/plots.

2. **"No baseline comparison"** appears in 13/14 variants, *including
   the `framework_comparison` variants*. The qualitative comparison
   to JAX/LTN/DeepProbLog that the fix added didn't satisfy — the
   reviewer wants quantitative comparison numbers, not prose.

3. **"References to internal scripts" without showing data** newly
   appeared in the `anisotropy_evidence` variant (mask 16, 31, 63).
   My fix made things slightly worse by pointing at
   `experiments/rotation_binding_capacity.py` without including its
   output in the paper.

4. **"T=50 iteration limit is arbitrary"** is a NEW con surfaced
   across multiple variants — wasn't in the v1/v2/v3 reviews on the
   pre-combinatorics paper. The reviewer noticed it once we ran more
   submissions through.

5. **"Rotation binding is well-known (Plate 1995); novelty is low"**
   another NEW con. Suggests the paper's framing under-sells
   whatever novel parts exist (substrate-purity claim, the
   programming-language layer, the constant-memory recursion).

## Real takeaway

The fixes I (Claude) wrote in `scripts/paper_fixes.py` are too
superficial to close the gap from "Reject" to anything else. The
reviewer's threshold for upgrading the rating is **empirical
evidence**, not text edits.

To actually move the rating, the next round needs:

- **Run `experiments/rotation_binding_capacity.py` and put the
  output (table or plot) in the paper.** Real numbers, real
  comparison rotation vs. Hadamard vs. sign-flip on real LLM
  substrates.
- **Quantitative comparison vs. torchhd or another existing VSA
  library.** Run the same task, report numbers.
- **Address the T=50 issue** — either justify with scaling analysis
  or remove the hard cap.
- **Strengthen the novelty claim.** Per Gemini's input
  (`planning/findings/2026-04-30-gemini-paper-positioning-suggestions.md`),
  the constant-memory tail-recursion-in-superposition framing is
  the strongest novelty pitch we haven't yet tested.

## Cost of this run

14 clawrxiv submissions, 14 reviews, ~17 min wall-clock. Net signal:
**a confirmed flat gradient over text-only fixes.** That's a
negative result — useful, even if not the result we hoped for. It
saves us from churning on more text-tweak combinations and points
us at the real remaining work (empirical experiments).
