# planning/open-questions/

Live design questions that we know we need to answer eventually, but haven't. Different from `planning/exploratory/`:

- **`exploratory/`** — parking lot for sketches and "maybe someday" ideas. Not load-bearing.
- **`open-questions/`** — known gaps in the Sutra design where the current implementation has made a choice (often silently), but that choice isn't justified by the spec and should be revisited. These block "is the spec self-consistent" before they block any particular feature.

## Rules

1. **Each doc states the question, what we currently do, why we do it, and what we don't know.** Not a plan — a problem statement.
2. **Add an entry here when a session-level decision gets made in lieu of a principled one.** e.g. "we picked X because Y worked in one test" — that's an open question, not a resolved design.
3. **Resolving an open question means updating the spec (`planning/sutra-spec/`) or the implementation**, then removing the doc from this folder. Don't let resolved questions rot here.
4. **Link from `queue.md` when an open question is actively blocking work.** Otherwise, these live here quietly until someone comes back to them.

## Triage verdicts (2026-05-16, task #15)

Per Emma: ~90% of these are not actually open — decided in the spec /
todo.md / voice-absorbed notes, the doc just never got retired. This
table is the authoritative "exactly what is going on" surface. Spec
pointers spot-verified to exist. Legend: **RESOLVED** (decided; cited
location is authoritative; doc is now rationale-only, retire on the
next pruning pass) · **STALE** (premised on a superseded design;
archive) · **OPEN** (a genuinely undecided sub-question, stated in
one line).

| Doc | Verdict | Where decided / the precise open part |
|---|---|---|
| `literals-and-auto-embedding.md` | RESOLVED (core) | `sutra-spec/strings.md` + literals shipped 2026-04-23; OPEN only on deferred binary-op/return/map-value embedding rules |
| `defuzzify-iteration-formula.md` | OPEN | which rule per type: exp-weighted 3-way polarizer vs `iterate f=f==true`; both coherent, pick/unify (see `sutra-spec/equality-and-defuzzification.md`) |
| `no-null.md` | RESOLVED (core) | no runtime null — `sutra-spec/types.md:262,273`; OPEN only on whether to forbid `var X:TYPE;` uninitialized syntax (user leaned forbid) |
| `function-taxonomy-and-closure.md` | OPEN | closure-free capture shipped 2026-05-09; the 4-kind taxonomy boundary stays undecided |
| `javascript-primitive-subclasses.md` | OPEN | per-primitive JS subclasses vs catch-all JavaScriptObject; not blocking until a TS dispatch case forces it |
| `rotation-hashmap-as-language-feature.md` | OPEN | first-class `map<K,V>` vs library pattern vs neither; depends on real programs |
| `concurrency-and-monads.md` | OPEN | monad/effect structure on top of `sutra-spec/concurrency.md` |
| `conditional-branching-on-remote.md` | OPEN | can the branch decision itself run on the substrate (not just the argmax feeding it) |
| `codegen-v1-feature-coverage.md` | NARROWED | Embed/Defuzzy SHIPPED (2026-06-20); open tail = method/operator decls + UnsafeCast |
| `zero-as-explicit-neutrality.md` | OPEN | how higher-level features consume truth-axis 0 (bool↔fuzzy coercion, branch-on-neutral); runtime already coherent |
| `nested-loops-as-orthogonal-subspaces.md` | OPEN | subspace allocation + termination + cross-subspace channel for nested `loop(cond)` |
| `cosine-vs-euclidean-for-post-algebraic-similarity.md` | OPEN | is Euclidean right for post-bind/bundle compare (magnitude info); never tested; gates any "right metric" claim |
| `contextual-vs-static-embedding-keys.md` | OPEN | static string-keyed `embed()` vs contextual; load-bearing only for beyond-toy NL claims |
| `paren-cast-vs-grouping-ambiguity.md` | OPEN | `(atom) <binop>` parses as a cast not a group; transpilers fully-group around it, hand-written `.su` still mis-parses; pick a cast syntax / disambiguation rule |

Tally (after the 2026-05-28 pruning pass):
**2 RESOLVED-core with a narrow OPEN tail** (`literals-and-auto-embedding`,
`no-null` — kept because each still has a live sub-question),
**11 genuinely OPEN** — most are narrow sub-questions, not undefined design
space, and none currently blocks queue work.

**Pruning pass (2026-05-28, Emma-greenlit).** Nine fully-RESOLVED docs whose
rationale is captured in the cited spec/findings were removed from the tree
(git history preserved): `binding-kind-surface-syntax` (→ `binding.md`),
`loop-function-declarations` / `loop-tail-call-surface` / `loop-body-semantics`
(→ `control-flow.md` §Loops), `axon-bind-needs-permutation-for-synthetic-fillers`
(→ commit `6d25f232`), `cosine-as-its-own-transcendental` (→ `ccos`+`csin`
shipped; findings), `equality-cosine-T-placement` (→ per-rule literal), `non-halting-loop-recur-primitive`
(→ `non-halting-loop.md`), `arbitrary-precision-digit-array` (→
`arbitrary-precision.md` + BigInt shipped). RESOLVED-core docs with a live OPEN
tail were LEFT in place.

**Pruning pass (2026-05-21).** The fly-brain-related resolved/stale
dossiers were removed from the tree (git history preserved):
`loop-surface-redesign`, `tier2-bundle-substrate-vs-algebra`,
`numpy-inheriting-from-flybrain`, and
`project-kind-connectome-vs-embedding` — all premised on the retired
connectome target.

## Current contents

- `rotation-hashmap-as-language-feature.md` — should Sutra have a rotation-hashmap (hash-vector-to-angles → rotation-bind storage) as a first-class `map<K, V>` language feature, as a library pattern, or not at all? Soft-lookup on semantic-vector keys is the distinctive property. Decision pending; depends partly on what programs people end up writing.
- `concurrency-and-monads.md` — the concurrency model is sketched in `planning/sutra-spec/concurrency.md` but the monad/effect structure isn't settled.
- `conditional-branching-on-remote.md` — conditional branching currently decides at host Python time (the outer `argmax_cosine` call). What would it mean for the branch decision itself to execute on the substrate, not just the prototype matching that feeds it? Unresolved.
- `codegen-v1-feature-coverage.md` — the V1 codegen still refuses method decls, operator decls, and `UnsafeCastExpr`. `EmbedExpr` and `DefuzzyExpr` are now SHIPPED (lower to `_VSA.embed` / compile-time defuzzy expansion; verified 2026-06-20). Open tail: which of the OO surface (method/operator decls) + `UnsafeCast` V1 should close.
- `literals-and-auto-embedding.md` — what is Sutra's literal set, and when does a string literal auto-embed vs. stay a string? Design captured 2026-04-23; char + implicit-fuzzy + string-auto-embed slices landed 2026-04-23 (317099a, 7fb7b50, 6e424d8). Follow-on rules (binary-op embedding, return-stmt embedding, map-value embedding) still deferred until concrete programs want them.
- `zero-as-explicit-neutrality.md` — `fuzzy f = 0` lands at the origin of the truth axis (neither true nor false). User framing: this is *not* truthy/falsy; it's "I'm explicitly not taking a side." Open questions: bool ↔ fuzzy coercion, branching on neutral, comparison with false. Current runtime is coherent; what's undecided is how higher-level language features consume neutrality.
- `no-null.md` — Null does not exist in Sutra at runtime. Every "absent" state has a first-class neutral value (`unknown` on truth axis, `0` on number axis, zero-vector for vectors). Open: whether to keep the `var x : TYPE;` uninitialized-declaration syntax (with initialize-before-use check) or forbid it entirely. User leaned toward forbidding ("it feels very imperative") but left it undecided.
- `defuzzify-iteration-formula.md` — the currently-shipped `defuzzify_trit` (exp-weighted three-way softmax polarizer) does not match the user's stated formula `iterate N: f = f == true` under cos-based equality. Both are coherent rules with different behaviors — binary snap vs. three-way smooth polarization. Pick one per type or unify. Deferred rather than quietly shipped as matching.
- `nested-loops-as-orthogonal-subspaces.md` — the spec defines single `loop(cond)` as eigenrotation on the substrate but is silent on what nested `loop(cond)` constructs compose into. Design intuition is "rotations in orthogonal subspaces, cross-subspace info flow via bind"; the compiler currently host-sequences nested loops, recapitulating the host-sequencer caveat at every nesting level. Subspace allocation, termination semantics, and cross-subspace back-channel are all unresolved.
- `cosine-vs-euclidean-for-post-algebraic-similarity.md` — Sutra uses cosine everywhere (similarity, equality, argmax_cosine, defuzzify, vector-keyed map fallback), but the user has an old recorded reservation that Euclidean might be the right metric for post-bind/post-bundle comparison since "magnitude carries information" that cosine throws away. Never tested; harvested from chats triage 2026-04-29. Not blocking current work; needs settling before any "we picked the right metric" public claim.
- `contextual-vs-static-embedding-keys.md` — Sutra's `embed()` is string-keyed and static: `embed("bank")` always returns the same vector regardless of whether the program is reasoning about rivers or finance. The user has explicit recorded interest in contextual embeddings ("more contextuality is better"); the static-keyed surface is the opposite pole by accident of which substrates were cheap to integrate. Not blocking current work; load-bearing when Sutra tries to claim natural-language reasoning beyond toy domains. Harvested from chats triage 2026-04-29.
- `function-taxonomy-and-closure.md` — what counts as a closure in Sutra given the no-host-mutation rule, and how the four function-kind taxonomy (free function, method, intrinsic, loop-function) relates to the closure question. Partially resolved 2026-05-09 (closure-free closure capture for TS arrow functions ships by parameter-lifting); the deeper taxonomy question stays open.
- `javascript-primitive-subclasses.md` — surfaced 2026-05-10. Emma's clarification of the JS-compat model: per-primitive subclasses (`JavaScriptInt extends int`, `JavaScriptString extends String`, etc.) with JS-specific operator overrides, instead of the catch-all `JavaScriptObject` carrying all of them. Refinement of the MVP that landed 2026-05-10; not blocking, picks up when a real TS program exposes a dispatch case the catch-all can't handle.
