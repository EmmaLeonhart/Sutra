# planning/open-questions/

Live design questions that we know we need to answer eventually, but haven't. Different from `planning/exploratory/`:

- **`exploratory/`** — parking lot for sketches and "maybe someday" ideas. Not load-bearing.
- **`open-questions/`** — known gaps in the Sutra design where the current implementation has made a choice (often silently), but that choice isn't justified by the spec and should be revisited. These block "is the spec self-consistent" before they block any particular feature.

## Rules

1. **Each doc states the question, what we currently do, why we do it, and what we don't know.** Not a plan — a problem statement.
2. **Add an entry here when a session-level decision gets made in lieu of a principled one.** e.g. "we picked X because Y worked in one test" — that's an open question, not a resolved design.
3. **Resolving an open question means updating the spec (`planning/sutra-spec/`) or the implementation**, then removing the doc from this folder. Don't let resolved questions rot here.
4. **Link from `STATUS.md` when an open question is actively blocking work.** Otherwise, these live here quietly until someone comes back to them.

## Current contents

- `binding-kind-surface-syntax.md` — **resolved 2026-04-21**. Candidate B chosen: `role` for semantic, `var` for rotation-bound. Syntax is now spec in `planning/sutra-spec/binding.md`. Doc retained for decision rationale until the next resolved-entry pruning pass.
- `rotation-hashmap-as-language-feature.md` — should Sutra have a rotation-hashmap (hash-vector-to-angles → rotation-bind storage) as a first-class `map<K, V>` language feature, as a library pattern, or not at all? Soft-lookup on semantic-vector keys is the distinctive property. Decision pending; depends partly on what programs people end up writing.
- `concurrency-and-monads.md` — the concurrency model is sketched in `planning/sutra-spec/concurrency.md` but the monad/effect structure isn't settled.
- `project-kind-connectome-vs-embedding.md` — **largely resolved 2026-04-26** by fly-brain retirement; current single target is the embedding-space PyTorch backend. Doc preserved as design-space map for any future second-target reintroduction.
- `tier2-bundle-substrate-vs-algebra.md` — **moot 2026-04-26.** The only substrate that routed `bundle(...)` through a circuit was the retired fly-brain backend; the current PyTorch backend uses normalized vector addition. Doc preserved as design-space map for any circuit-routed-substrate future.
- `conditional-branching-on-remote.md` — conditional branching currently decides at host Python time (the outer `argmax_cosine` call). What would it mean for the branch decision itself to execute on the substrate, not just the prototype matching that feeds it? Unresolved.
- `codegen-v1-feature-coverage.md` — the V1 codegen refuses methods, operator decls, `EmbedExpr`, `DefuzzyExpr`, `UnsafeCastExpr`. Most demo programs compile; several examples don't. Which gaps should V1 close? Unresolved.
- `literals-and-auto-embedding.md` — what is Sutra's literal set, and when does a string literal auto-embed vs. stay a string? Design captured 2026-04-23; char + implicit-fuzzy + string-auto-embed slices landed 2026-04-23 (317099a, 7fb7b50, 6e424d8). Follow-on rules (binary-op embedding, return-stmt embedding, map-value embedding) still deferred until concrete programs want them.
- `zero-as-explicit-neutrality.md` — `fuzzy f = 0` lands at the origin of the truth axis (neither true nor false). User framing: this is *not* truthy/falsy; it's "I'm explicitly not taking a side." Open questions: bool ↔ fuzzy coercion, branching on neutral, comparison with false. Current runtime is coherent; what's undecided is how higher-level language features consume neutrality.
- `_archived-numpy-inheriting-from-flybrain.md` — **resolved 2026-04-23, superseded 2026-04-26.** Original concern was that `NumpyCodegen` inherited from `FlyBrainCodegen`. The 2026-04-23 refactor extracted `BaseCodegen` so they were siblings; the 2026-04-26 fly-brain retirement made the concern moot entirely. Archived doc retained as historical record.
- `no-null.md` — Null does not exist in Sutra at runtime. Every "absent" state has a first-class neutral value (`unknown` on truth axis, `0` on number axis, zero-vector for vectors). Open: whether to keep the `var x : TYPE;` uninitialized-declaration syntax (with initialize-before-use check) or forbid it entirely. User leaned toward forbidding ("it feels very imperative") but left it undecided.
- `defuzzify-iteration-formula.md` — the currently-shipped `defuzzify_trit` (exp-weighted three-way softmax polarizer) does not match the user's stated formula `iterate N: f = f == true` under cos-based equality. Both are coherent rules with different behaviors — binary snap vs. three-way smooth polarization. Pick one per type or unify. Deferred rather than quietly shipped as matching.
- `nested-loops-as-orthogonal-subspaces.md` — the spec defines single `loop(cond)` as eigenrotation on the substrate but is silent on what nested `loop(cond)` constructs compose into. Design intuition is "rotations in orthogonal subspaces, cross-subspace info flow via bind"; the compiler currently host-sequences nested loops, recapitulating the host-sequencer caveat at every nesting level. Subspace allocation, termination semantics, and cross-subspace back-channel are all unresolved.
- `cosine-vs-euclidean-for-post-algebraic-similarity.md` — Sutra uses cosine everywhere (similarity, equality, argmax_cosine, defuzzify, vector-keyed map fallback), but the user has an old recorded reservation that Euclidean might be the right metric for post-bind/post-bundle comparison since "magnitude carries information" that cosine throws away. Never tested; harvested from chats triage 2026-04-29. Not blocking current work; needs settling before any "we picked the right metric" public claim.
