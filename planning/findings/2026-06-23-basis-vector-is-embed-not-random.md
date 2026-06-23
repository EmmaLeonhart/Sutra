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

## The open decision (Emma's call)

This is a spec-vs-implementation disagreement (CLAUDE.md rule 5). Two resolutions:

1. **`basis_vector` is intentionally an `embed` alias.** Then it is mis-named and
   mis-documented: fix every "random basis / pairwise cosine ~0" comment to "a named point
   in the embedding space (correlated, not orthogonal)", and consider deprecating the name
   in favour of `embed` to remove the implication of a random basis.
2. **`basis_vector` should be a distinct random/seeded atom** (deterministic per string,
   decorrelated — what the name and example comments assume). Then it is a *missing
   primitive*: add a real seeded-random/Haar atom constructor, point the demos that want
   decorrelated labels at it, and keep `embed` for semantic content. This would also make
   the demos' separation margins match their comments.

Do NOT silently pick one — it changes language semantics. Documented here for the design
call; the example comments stay untouched until it is made.
