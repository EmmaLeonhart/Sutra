# `basis_vector` lowers to `embed` — it is NOT a random basis (2026-06-23)

## What

`basis_vector(s)` lowers to `_VSA.embed(s)` (`codegen_base.py:_builtin_basis_vector` →
`f"_VSA.embed({args[0]})"`). So `basis_vector("cat")` and `embed("cat")` are the **same
operation** — both resolve the string to its point in the frozen embedding space. There is
no random/seeded/orthogonal "basis" being generated.

## Why it matters

Several example programs and (until 2026-06-23) several doc/tutorial passages describe
`basis_vector` as a *random* atom that carries no meaning, with near-orthogonal pairwise
cosine. That is measurably false.

**Measured** (nomic-embed-text, in-process; 6 atoms from the demos —
`hello_world`/`goodbye`/`are_you_there`/`fruit_apple`/`veh_car`/`tool_hammer`):

    pairwise cosine  min 0.409   max 0.597   mean 0.473

If these were truly random/orthogonal the mean would be ≈0. They are correlated
embeddings (~0.47). The demos still retrieve correctly (argmax picks the max), but the
separation margins are smaller than the "concentration of measure → cosine ~0" comments
imply, and the "random basis" framing is wrong.

Stale claims found (the doc ones were corrected 2026-06-23; the example comments remain):

- `examples/nearest_phrase.su` — "random-basis vectors stay cleanly separable… 20 random
  basis vectors have pairwise cosine ~= 0 (concentration of measure)". FALSE as written.
- `examples/classifier.su` — "instead of hand-coding one basis vector per class" (frames
  basis_vector as a hand-picked atom, not an embedding).
- `examples/hello_world.su` — neutral ("a vector in the space"); OK.
- Corrected already: `docs/tutorials/index.md`, `docs/tutorials/05-semantic-faq.md`,
  `docs/tutorials/01-hello-sutra.md` no longer claim "random atoms / need no model".

## Decision (Emma 2026-06-23): `basis_vector` is an ALIAS for `embed` — deprecate it

Emma's call: `basis_vector` is a pure alias for `embed`. It is NOT a distinct seeded-random
primitive (resolution 1, not 2). Per the aggressive-alias-deprecation principle she set the
same day (CLAUDE.md § "Deprecate aliases aggressively"), a pure alias with no semantic content
of its own is the easiest thing to retire and should be retired: **`embed` is canonical;
`basis_vector` is a deprecation on its way out.**

Follow-up work (folded into the alias + affordance audit — the next loop batch):
- Mark `basis_vector` deprecated; repoint every call site (`examples/*.su`, corpus, docs) to
  `embed`. Behaviour is identical, so outputs/tests don't change.
- Fix the now-false "random basis / pairwise cosine ~0 / concentration of measure" comments in
  `examples/nearest_phrase.su` + `examples/classifier.su` (they are correlated embeddings, ~0.47,
  not orthogonal random atoms) — these get rewritten when the call sites are repointed.
- The doc passages that repeated the false claim were already corrected 2026-06-23.
