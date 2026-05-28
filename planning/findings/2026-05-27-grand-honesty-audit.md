# 2026-05-27 19:15 PST — Grand honesty audit (single-shot)

Scheduled by `9789b73b`. Read the repo's claim-vs-reality gap across paper, docs, queue, and tracking surfaces. Surface issues; do not silently fix.

## Summary

11 checks. **3 issues** found (1 freeze-discipline borderline, 1 queue-discipline restatement, 1 minor doc-description mismatch). 8 PASS. Concrete fix items appended to queue.md under `## Audit findings 2026-05-27 19:15 PST`.

---

## 1. paper/formal-verification/paper.md vs measured reality — PASS

Cross-checked every paper numeric claim against findings docs + runlogs:

| Paper claim | Source | Status |
|---|---|---|
| §4.1 capacity curve (k=2..48, all three substrates, every cell) | `planning/findings/2026-05-27-bundle-decoding-capacity-curve.md` | exact match for all 21 cells |
| §4.1 k=8 100% on ESM-2 protein model | `experiments/rotation_binding_capacity_bioinformatics_results.json` + `planning/findings/2026-05-01-replication-success.md` | match (k=8 = 100% rotation) |
| §3.4 PIT term counts (6 / 66 / 177 / 312 / 1054) + 56 s + ~770 MB | `planning/findings/2026-05-27-pit-term-count.md` | exact match |
| §4.2 round-trip 1.5 × 10⁻¹⁵ | `planning/findings/2026-04-30-crosstalk-noise-accumulation.md` + `2026-04-30-sutra-vs-torchhd-capacity.md` | match |
| §4.3 18/18 dispatch + 1024/1024 symbol round-trip + 2²⁴ boundary | sourced in downstream `../Yantra/` (cross-repo cite) | source exists; acceptable cross-repo citation |

No paper numeric claim is unsourced.

## 2. paper/paper.md FROZEN check — PASS

`git log --since="2026-05-22" -- paper/paper.md` → empty. No commits to the frozen live paper since the 2026-05-21 arXiv v2 correction series. Freeze respected.

## 3. paper/neurips/ FROZEN check — **ISSUE (borderline)**

`git log --since="2026-05-08" -- paper/neurips/` returns two commits:

- `2a9898bf` 2026-05-10 "paper: split NeurIPS-frozen archive into paper/neurips/, free up paper/paper.md" — this IS the commit that ESTABLISHED the freeze location, not a violation.
- `599424f8` 2026-05-24 "Standardize contact email to contact@emmaleonhart.com" — touches files under `paper/neurips/` AFTER the freeze (2026-05-07) and AFTER the post-arXiv lock-pin. CLAUDE.md says "Do not edit any file under paper/neurips/ — not the title, not the abstract, not the body, not the references, not the appendix, not the supplementary docs. Not for rewording, not for tightening, not for new findings, not for clawRxiv reviewer feedback, not for typos, not for anything."

Author: Emma-Leonhart. Co-authored with Claude. Metadata-only (contact-email standardization, not paper content). Technically a freeze violation; in practice an Emma-authored decision that probably should be exempted at the rule level rather than treated as drift. Flag for triage.

## 4. docs/capabilities.md vs source — PASS

Spot-checked 10 items by greppingdo both `codegen_pytorch.py`/`stdlib/*.su` and `docs/capabilities.md`. All 10 match (`axon_new`, `hashmap_get`, `string_concat`, `defuzzify_trit`, `rotation_for`, `complex_mul`, `is_string`, `Math`, `JavaScriptString`, `string_char_at` all present in both source AND doc). Internal-helper underscore methods (`_argmax_cosine`, `_lerp`, `_e_real`, `_exp_table`, `_as_truth_vector`, `_axon_permutation_for`) all confirmed in doc on second pass.

## 5. queue.md DONE/SHIPPED status — **ISSUE**

Found at lines 143, 147, 148, 152: four "DONE 2026-05-27" sub-items embedded under the rank-k section (REAL per-seed variation source; k-means cluster-centroid anchors; Sutra parser scientific-notation float literals; Original steps … DONE scaffold). This violates queue.md's own discipline stated at lines 6-8: *"If you find yourself writing '✅ DONE / ANSWERED / Recently shipped' status here, it belongs in git log or a finding, not in this file — that is the CRUD this queue is not for."*

Same pattern that bit the FV section earlier 2026-05-27 (trimmed in commit `1a54045b`). The rank-k section now has the same anti-pattern.

Internal-contradiction spot-check (the pattern from `133d9364`): scanned the FV section for a "Still OPEN" item that's actually discharged. None found this pass; the trimmed `aa709a27` rewrite is still clean.

## 6. DEVLOG.md recent shas — PASS

Spot-checked 16 cited shas across recent DEVLOG entries (`ee8b80e0`, `cb8ceba3`, `7091bda4`, `686201f6`, `ea7aac7c`, `848b0d60`, `133d9364`, `4f604520`, `0b151b79`, `e7cca673`, `ea6f8a01`, `4e3b76f7`, `525283b1`, `cad18562`, `1946f132`, `22d785db`) via `git cat-file -e`. All 16 exist. No narrative overstatements caught on review of the recent ~10 entries.

## 7. shipped / verified / passes claims in markdown — PASS (sample-checked)

Grep found 93 instances across non-frozen `.md` files (excluding `paper/neurips/`). Sampled from queue.md: all instances either refer to discipline-rule text ("Recently shipped status here, it belongs in git log"), to past-tense factual statements ("verified 2026-05-20"), or to forward-looking framings (the "to ship" candidates list). No overclaims caught in the sample. Not exhaustive — a full-pass check would be its own bounded task.

## 8. `.post_id` + `/papers/` page consistency — PASS (with minor description drift)

`paper/formal-verification/.post_id` = `2639` (current). `docs/papers.md` does NOT hard-code a specific post id — instead describes the chain-starts-fresh behavior. The PDF link `/formal-verification.pdf` is the on-site canonical and is independent of the clawRxiv post id, which is the right framing.

Minor drift: `docs/papers.md` says the chain starts fresh "whenever clawRxiv's revise endpoint returns 404 on a previously-pinned post" — but in current operation (since the title-bump approach landed) every cron tick produces a NEW post id (2630 → 2631 → 2632 → … → 2639), because each title bump breaks dedup and forces a fresh create. So the description isn't quite right anymore; it describes the 404 recovery rather than the steady-state title-bump-per-tick behavior. Flag for one-sentence update.

## 9. Auto-resubmit cron health — PASS

`gh run list --workflow=fv-paper-ci.yml --limit 5`: 4 most recent runs SUCCESS + 1 in-progress (the just-fired bump). Most recent review on disk: `v22_post2639_review.json` (timestamp matches the latest commit). Reviews are landing at the expected cadence (one per ~10 min cron tick).

## 10. K=5 rank-k sweep status — KNOWN-CRASH, already surfaced

`experiments/runlogs/2026-05-27-rank-k-K5-k1-n3.txt` ends in `RuntimeError: 1D tensors expected, but got 1D and 0D tensors` inside `similarity` → `is_class_2` → `rule_0`. The K=2 k=2 smoke didn't exercise the K≥3 cross-class path. Python process 35128 is dead.

Already surfaced in commit `848b0d60` with a queue.md top-of-Active 🚨 BUG item and a DEVLOG entry. Re-surfacing for completeness, not as a new finding.

## 11. Tests — PASS

`pytest sdk/sutra-compiler/tests/test_lexer.py tests/test_fv_general_checker.py -q` → **32 passed in 4.28s**. No regressions; no new xfails.

---

## Cross-cutting note

The audit found no fabricated numbers, no missing-source claims in the paper, no stale cited shas. The three issues are discipline drift (paper/neurips/ freeze touched by a metadata commit; queue.md rank-k section re-accumulating DONE sub-items; docs/papers.md description slightly behind current cron behavior) — not integrity violations. The high-velocity FV-paper cron + multi-commit session pattern this evening did not produce a wave of unverifiable claims; the per-finding citation discipline held.

Adding three concrete fix items to queue.md.
