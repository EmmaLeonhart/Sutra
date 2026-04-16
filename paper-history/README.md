# Paper version history

Every historical version of `sutra-paper/paper.md`, `language-paper/paper.md`,
and `fly-brain-paper/paper.md` extracted from git, in chronological order,
one file per commit. The blob header at the top of each file records the
commit hash, date, commit subject, and repo path at the time.

Regenerate with:

```
python paper-history/extract.py
```

## sutra-paper/ — 27 versions (2026-04-08 → 2026-04-15)

This file was renamed twice: `S2-paper/paper.md` →
`akasha-paper/paper.md` → `sutra-paper/paper.md`. Title changes track
the rename: "S2" (v001–v006) → "Akasha" (v007–v013) → "Sutra" (v014–
v021) → "Sign-Flip Binding…" (v022–v027, the current scope).

**The scope trim happened at version 022 / commit `338762a4`
(2026-04-14 13:03) — "sutra-paper → embedding-operations paper:
rename, trim scope, drop language claims."** Every version at and
before 021 was titled as a *language* paper; every version at and
after 022 is the narrow empirical paper about sign-flip binding.

### Matrix-based content that was in earlier versions

| What | Where | Removed at | Notes |
|------|-------|-----------|-------|
| Truth-extraction matrix `M(v) = t_true · vᵀ / (‖v‖² + ε)` for `is_true` | v001–v015 §3.4 | v016 (`7b415324`, 2026-04-11 18:51) | Replaced with cosine `is_true`. The construction was a rank-1 outer-product matrix using a learned `t_true` direction from an empirical-initiation probe. Commit message: "fix(sutra-paper): replace trivial truth-extraction matrix with cosine is_true." |
| Rotation binding `R(role) @ a` (random orthogonal) | v001–v027 (still present) | — | Listed in the 6-binding comparison table; achieves 0.80 cosine at 7 roles. Random rotations, not learned. |
| Three-tier operations framing | v001–v017 | v018 (`c2b643c1`, 2026-04-13) | "strip tier-1/2/3 framing from prose and §3.2." |

### sutra-paper title progression

| # | Date (UTC-7) | Short hash | Title |
|---|--------------|-----------|-------|
| 001 | 2026-04-08 10:58 | 7b6c533d | S2: A Vector Programming Language for Computation in Embedding Spaces |
| 002 | 2026-04-08 10:58 | 51a997b8 | (same, duplicate commit) |
| 003 | 2026-04-08 13:20 | 076fe87b | S2: A Vector Programming Language … |
| 004 | 2026-04-08 13:20 | fe7731de | (same, duplicate) |
| 005 | 2026-04-08 13:41 | 82d513cc | S2 … (sign-flip deep testing results added) |
| 006 | 2026-04-08 13:41 | 533a6d46 | (same, duplicate) |
| 007 | 2026-04-10 04:04 | 16263070 | **Akasha** : A Vector Programming Language … (rebrand) |
| 008 | 2026-04-10 04:04 | a1a1e473 | (same, duplicate) |
| 009 | 2026-04-10 19:06 | aa9ccac0 | Akasha … + §6.6 Biological Substrate (compile-to-brain) |
| 010 | 2026-04-11 00:04 | 29f66622 | Akasha … v1-Reject review surgical fixes |
| 011 | 2026-04-11 11:49 | 4c7df5be | Akasha … v4 (learned MBON readout, dimensionality defense) |
| 012 | 2026-04-11 15:25 | 38693ced | Akasha … (.ak → .su file-extension rename) |
| 013 | 2026-04-11 16:16 | 44d6fffb | Akasha … (akasha-paper → sutra-paper dir rename) |
| 014 | 2026-04-11 16:30 | 3591fd01 | **Sutra** : A Vector Programming Language … |
| 015 | 2026-04-11 18:03 | 4c1321a6 | Sutra … (CI resubmit) |
| 016 | 2026-04-11 18:51 | 7b415324 | Sutra … (replace truth-extraction matrix with cosine `is_true`) |
| 017 | 2026-04-12 05:26 | b5bfb484 | Sutra … (unify fly-brain-paper title) |
| 018 | 2026-04-13 15:36 | c2b643c1 | Sutra … (strip tier-1/2/3 framing) |
| 019 | 2026-04-13 16:56 | d515ff9f | Sutra … §6.6 parity with fly-brain-paper |
| 020 | 2026-04-14 11:06 | ce1fce12 | Sutra … (scrub citation flags, honest `is_true`) |
| 021 | 2026-04-14 12:34 | 46b03e2a | Sutra … (last language-titled version) |
| 022 | 2026-04-14 13:03 | 338762a4 | **Sign-Flip Binding and Vector Symbolic Operations on Frozen LLM Embedding Spaces** (SCOPE TRIM) |
| 023 | 2026-04-14 13:22 | e30678bd | Sign-Flip … (post-pivot trim) |
| 024 | 2026-04-14 14:14 | 7269fc36 | Sign-Flip … (strip "honest limits" retraction theater) |
| 025 | 2026-04-14 15:11 | 40f30a37 | Sign-Flip … (whitespace CI trigger) |
| 026 | 2026-04-15 12:07 | 2410427a | Sign-Flip … (add Sutra-language-paper bib entry) |
| 027 | 2026-04-15 12:14 | fedb12b0 | Sign-Flip … (Wikidata-scale eval) |

## language-paper/ — 10 versions (2026-04-14 → 2026-04-15)

`language-paper/paper.md` was created on 2026-04-14 13:34 — half an
hour after the sutra-paper scope trim — as a separate new paper to
carry the language claims that had been stripped out of sutra-paper.

| # | Date (UTC-7) | Short hash | Title |
|---|--------------|-----------|-------|
| 001 | 2026-04-14 13:34 | 38e17f23 | A Programming Language Whose Only Control Primitives Are `select` and `gate` |
| 002 | 2026-04-14 14:14 | 7269fc36 | **Sutra: A Control-Flow-Free Programming Language for Hyperdimensional Computing** |
| 003–010 | 2026-04-14 → 2026-04-15 | … | (same title, iteration) |

## fly-brain-paper/ — 56 versions (2026-04-09 → 2026-04-15)

The fly-brain paper has the most version churn of the three. Two
matrix-based things relevant to your question lived here at various
points:

- **Learned MBON linear readout `W` fit via ridge regression** —
  added in v008 (`4c7df5be`, 2026-04-11 11:49 — commit subject
  "papers v4: learned MBON readout, dimensionality defense").
  Decoded from the KC population via a linear map *learned from
  experience*, not derived from the connectivity matrix.
  Subsequent versions described it as a 2000-KC → MBON readout
  fit by ridge regression for engineering convenience, with a
  biologically-closer revision (dopamine-gated plasticity) listed
  as future work.
- **Pseudoinverse PN-from-KC reconstruction** `pn_estimate =
  pinv(pn_kc_matrix) @ kc_rates` — appears as early as v005
  (`96258826`, 2026-04-10 22:27). Compressed-sensing argument that
  100 active KCs at 5% sparsity well-condition reconstruction of 50
  PN dimensions.

Neither of these is the corpus-fit semantic role matrix you remember
("R_object_of_sentence" fit on `(sentence_emb, object_emb)` pairs) —
they are fly-brain readout matrices, not LLM-embedding role matrices.

## What's NOT in this directory

- The **`is_converter` 140×140 learned matrix** experiment lived in
  `fly-brain/experiment_is_converter.py`, *not in any paper*. It
  was added 2026-04-12 in commit `ef8ade0` ("feat(fly-brain):
  is_converter matrix + KC-space binding experiments") and deleted
  2026-04-13 in commit `ebf2fa6` ("fly-brain: complete Python-file
  sprawl cleanup") as a "zero-reference, one-off, never imported"
  script. Recoverable via `git show ef8ade0:fly-brain/experiment_is_converter.py`.
- Anything in the cartography paper (`EmmaLeonhart/latent-space-cartography`)
  — that's a separate published repo, never lived in this tree.
