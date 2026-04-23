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
- `project-kind-connectome-vs-embedding.md` — the `fly-brain/` substrate and the numpy/embedding substrate have structurally different answers to some of the same spec questions. What's the right way to type or tag which substrate a program targets?
- `tier2-bundle-substrate-vs-algebra.md` — does `bundle(...)` run on the substrate or stay algebraic? The spec says tier-2 is pure math, the implementation routes through `bundle_on_brain`, and one concrete case (fuzzy_conditional) breaks unless we bypass the substrate. Unresolved. *(Note: tier framing is rejected per CLAUDE.md; this doc's terminology needs a rewrite separate from the question it raises.)*
- `conditional-branching-on-remote.md` — conditional branching currently decides at host Python time (the outer `argmax_cosine` call). What would it mean for the branch decision itself to execute on the substrate, not just the prototype matching that feeds it? Unresolved.
- `codegen-v1-feature-coverage.md` — the fly-brain codegen refuses methods, operator decls, `EmbedExpr`, `DefuzzyExpr`, `UnsafeCastExpr`. Paper-relevant programs all compile; several examples don't. Which gaps should V1 close? Unresolved.
- `literals-and-auto-embedding.md` — what is Sutra's literal set, and when does a string literal auto-embed vs. stay a string? Design captured 2026-04-23; char + implicit-fuzzy + string-auto-embed slices landed 2026-04-23 (317099a, 7fb7b50, 6e424d8). Follow-on rules (binary-op embedding, return-stmt embedding, map-value embedding) still deferred until concrete programs want them.
- `zero-as-explicit-neutrality.md` — `fuzzy f = 0` lands at the origin of the truth axis (neither true nor false). User framing: this is *not* truthy/falsy; it's "I'm explicitly not taking a side." Open questions: bool ↔ fuzzy coercion, branching on neutral, comparison with false. Current runtime is coherent; what's undecided is how higher-level language features consume neutrality.
- `numpy-inheriting-from-flybrain.md` — **resolved 2026-04-23.** Refactor landed: `codegen_base.py` extracted with `BaseCodegen`; `NumpyCodegen` and `FlyBrainCodegen` now sibling backends. `codegen_numpy.py` has zero fly-brain imports. Doc retained as decision rationale until next pruning pass.
- `no-null.md` — Null does not exist in Sutra at runtime. Every "absent" state has a first-class neutral value (`unknown` on truth axis, `0` on number axis, zero-vector for vectors). Open: whether to keep the `var x : TYPE;` uninitialized-declaration syntax (with initialize-before-use check) or forbid it entirely. User leaned toward forbidding ("it feels very imperative") but left it undecided.
- `defuzzify-iteration-formula.md` — the currently-shipped `defuzzify_trit` (exp-weighted three-way softmax polarizer) does not match the user's stated formula `iterate N: f = f == true` under cos-based equality. Both are coherent rules with different behaviors — binary snap vs. three-way smooth polarization. Pick one per type or unify. Deferred rather than quietly shipped as matching.
