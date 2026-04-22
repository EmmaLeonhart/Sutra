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

- `binding-kind-surface-syntax.md` — how does a `.su` program distinguish a semantic (learned-matrix) role from a structural (sign-flip) role at declaration? Candidates A–E laid out; decision pending. Blocks STATUS.md queue item 1 (learned-matrix bind).
- `concurrency-and-monads.md` — the concurrency model is sketched in `planning/sutra-spec/concurrency.md` but the monad/effect structure isn't settled.
- `project-kind-connectome-vs-embedding.md` — the `fly-brain/` substrate and the numpy/embedding substrate have structurally different answers to some of the same spec questions. What's the right way to type or tag which substrate a program targets?
- `tier2-bundle-substrate-vs-algebra.md` — does `bundle(...)` run on the substrate or stay algebraic? The spec says tier-2 is pure math, the implementation routes through `bundle_on_brain`, and one concrete case (fuzzy_conditional) breaks unless we bypass the substrate. Unresolved. *(Note: tier framing is rejected per CLAUDE.md; this doc's terminology needs a rewrite separate from the question it raises.)*
- `conditional-branching-on-remote.md` — conditional branching currently decides at host Python time (the outer `argmax_cosine` call). What would it mean for the branch decision itself to execute on the substrate, not just the prototype matching that feeds it? Unresolved.
- `codegen-v1-feature-coverage.md` — the fly-brain codegen refuses methods, operator decls, `EmbedExpr`, `DefuzzyExpr`, `UnsafeCastExpr`. Paper-relevant programs all compile; several examples don't. Which gaps should V1 close? Unresolved.
