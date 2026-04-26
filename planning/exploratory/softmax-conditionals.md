# Softmax conditionals — exploratory research

**Status:** parked. Not scheduled. Revisit after the Claw4S deadline (2026-04-20) or when the `permutation_conditional` / `fuzzy_conditional` work reopens the question.

**User stance (captured 2026-04-13):** the conditionals question is interesting but too hard to push on right now alongside paper work. Write up the research, don't ship a language change. The eventual goal is to make it **harder** to write a classic C#/TS-style if/else in Sutra than to write a softmax-weighted switch, because the two constructs have different semantics and programmers from other languages consistently conflate them.

## Why the existing `if/elif/else` shape is wrong for Sutra

Sutra is fuzzy-by-default. Its only spec-blessed conditional primitive is the 2-way algebraic form from `planning/sutra-spec/03-control-flow.md`:

```
result = (condition * branch_true) + (NOT_condition * branch_false)
```

Extend that to an `if/elif/elif/else` chain and each successive branch multiplies a running product of NOT_prev_condition terms:

```
result = c1 * b1
       + (1-c1) * c2 * b2
       + (1-c1) * (1-c2) * c3 * b3
       + (1-c1) * (1-c2) * (1-c3) * b4
```

Three problems with this shape:

1. **Priority-from-ordering is implicit.** A programmer who wrote `if/elif/elif/else` in TypeScript expects earlier cases to win on ties. In the fuzzy algebra above, the earlier cases literally *shrink the weight budget* available to later cases, not because the language author chose that but because the lowering did. This is not what the programmer wrote.
2. **The branches are not comparable.** `b1` contributes with weight `c1`, `b4` contributes with weight `(1-c1)(1-c2)(1-c3)` — even if the raw similarities `c1..c4` are all equal, the fourth branch gets a much smaller weight. That is a numerical artifact of the nested lowering, not a semantic decision.
3. **Reviewers keep catching this.** The `v17 Strong Reject` and the long-running "if-chains vs switch/softmax" entry in `todo.md` both point at the same gap: the canonical conditional chain does not mean what it looks like.

## What a softmax switch looks like instead

Given named cases `c_1 .. c_n` with branch outputs `b_1 .. b_n`, the softmax-switch lowering is:

```
w_i    = softmax( similarity(state, prototype_i) / tau )
result = Σ_i w_i · b_i
```

Properties:

- **Unordered.** Cases compete symmetrically; there is no priority-from-position.
- **One blend, not a cascade.** Weights sum to 1 by construction (softmax), so the blend is numerically comparable to any individual branch.
- **Already validated in prior work.** The retired `fly-brain/fuzzy_conditional.py` did exactly this with clipped cosine scores over 4 joint prototypes and hit 80/80 on the real hemibrain across 5 seeds. The language surface is what's missing, not the math.
- **Temperature `tau` is a knob.** Low `tau` → winner-takes-all (discrete-ish). High `tau` → uniform blend. This is a natural place for the defuzzification threshold to hook in, if we eventually unify `is_true` thresholds with switch-sharpening.

## Three-form taxonomy (sketch, not spec)

This is the design sketch from the 2026-04-13 session. It is **not** authoritative. It needs the defuzzification contradiction resolved (see below) before any of it is safe to ship.

| Syntax (sketch) | Semantics | Lowers to |
|---|---|---|
| `gate (cond) { body }` | **Single-branch, truth-weighted.** No else. `state ← truth(cond) · body + (1 − truth(cond)) · state`. The action runs to the extent the condition is true; otherwise state is unchanged. | One algebraic expression. O(1). |
| `select { CaseA => ..., CaseB => ..., default => ... }` | **N-way softmax switch.** Cases are named prototypes; branches are unordered and exhaustive (via `default`). Weights are softmax over cosine similarities between the query state and each case's prototype. | `Σ softmax(cos(query, proto_i) / tau) · branch_i` — the shape `fuzzy_conditional.py` already validates. |
| `if (cond) { ... } else { ... }` | **Hard codegen error.** Diagnostic points at `gate` (for no-else) and `select` (for multi-way) and explains that C#-style priority-ordered if/else does not lower cleanly onto the fuzzy algebra. | Emits a structured error with source span, not silently degrades. |

The motivation for making `if/else` a hard error rather than a silent lowering is exactly the user's stated design goal: the worst failure mode is a programmer who thinks their Sutra `if/else` does what a TypeScript `if/else` does. Silent lowering to the cascade-shape formula above is the failure mode that already bit the reviewer cycle.

`codegen_base.py` currently **already** rejects `if/else` with `CodegenNotSupported("if/else is not supported by the V1 codegen — the whole point is to compile it away into a prototype-table lookup")`. The implementation direction is already pointed the right way — what's missing is a named replacement that the programmer is *supposed* to reach for instead.

## Alternatives considered

1. **`match` instead of `select`.** Rust/ML vocabulary. Arguably clearer for people coming from those languages. Possibly clearer-still: it leans into the pattern-match framing and away from the imperative-switch framing. Tradeoff: Sutra already uses `map<K, V>` as a primitive type (`05-type-system.md`), and `match` vs `map` reads weirdly.
2. **Pure cone traversal.** `03-control-flow.md` already describes cone-traversal-as-branching as a non-algebraic alternative. A `select` could lower to cone traversal instead of a softmax blend. Tradeoff: cone traversal is tier-3 (ANN-infrastructure) per `02-operations.md`, so it's more expensive and loses the "one algebraic expression" property. The softmax lowering is tier-2 (pure algebra) and matches the already-validated `fuzzy_conditional.py` behavior.
3. **Lint warning instead of hard error on `if/else`.** Softer migration path for existing `.su` code. Tradeoff: the user's goal is to make crisp conditionals *harder* to reach for, and a lint warning the IDE shows in grey does not accomplish that.
4. **Syntactic priority markers.** Let the programmer say `select { priority CaseA => ..., priority CaseB => ..., CaseC => ... }` to reintroduce ordering if they really want it. Probably out of scope until we've seen whether anyone needs it; YAGNI.

## Open questions that block shipping this

1. **Defuzzification contradiction.** `planning/sutra-spec/04-defuzzification.md` describes `is_true(v)` as iterated matrix multiplication `M(v) · v` with recursive refinement `t_{n+1} = M(t_n) · t_n`. Commit 7b41532 replaced that formulation in the paper with a **fixed** rank-1 projection `M = t_true · t_true^T` and `is_true(v) = cos(v, t_true)` — explicitly because the matrix-iteration form was a tautology (the old `M(v) = t_true · v^T / ||v||²` mapped every non-zero `v` to `t_true`, so iterating it was measuring nothing). The user has stated they do **not** want to throw away the performance improvement from 7b41532, but they have also described iterated-matrix defuzzification as their vision. **The spec and the paper currently disagree.** Per `CLAUDE.md` rule 5, this has to be resolved explicitly before `select` ships, because `select`'s softmax weights are the natural place to thread defuzzification through.
   - **Option A:** update `04-defuzzification.md` to match the paper (fixed cosine projection, threshold ladder for "recursive refinement"). `select` uses `cos` directly for weights. Cheapest to implement; consistent with the landed performance fix.
   - **Option B:** reintroduce a non-trivial iterated-matrix form where `M(v)` genuinely depends on `v` in a non-tautological way. Requires a real design, not a restoration. `select` uses the iterated form for high-confidence cases. Most expensive; also most powerful if the design works.
   - **Option C:** keep both, treat the iterated form as an opt-in high-accuracy mode. `select` defaults to cosine; `select strict { ... }` uses the iterated form. Splits the ambiguity into the syntax rather than the semantics.
2. **Tau (softmax temperature) — who sets it?** A fixed `tau` per language is simplest but sometimes wrong. A per-`select` `tau` is flexible but asks the programmer to understand softmax. A per-prototype learned `tau` (the retired fly-brain substrate did this with KC-pattern Jaccard thresholds) complicates the language surface.
3. **Do prototypes need explicit declaration?** `fuzzy_conditional.py` builds prototypes from joint bindings of the input vectors. Should `select` require `prototype CaseA = bind(smell_present, hunger_hungry)` as an explicit declaration, or should the compiler infer prototypes from case labels and the surrounding vector environment? Explicit is verbose but transparent; inferred is concise but magic.
4. **Interaction with `loop (condition)`.** Eigenrotation loops terminate on prototype match in KC space (`03-control-flow.md` lines 111–119). If `select` also does prototype matching, should the two share a prototype table? This is probably a "yes, obviously" but worth confirming — if they don't share, we get two parallel prototype-compilation pipelines for no clear reason.
5. **Backward compatibility.** The existing `.su` corpus uses `if` in at least `four_state_conditional.su`. A hard error on `if/else` breaks those files. Either (a) gate the hard error behind a version flag, (b) mechanically translate the existing files, or (c) lint-warning-for-a-release, hard-error-after. Decision is a policy call, not a technical one.

## Prior art (mostly retired)

- The retired `fly-brain/fuzzy_conditional.py` — the softmax-over-prototypes pattern, 80/80 on 5 hemibrain seeds. The math that `select` would expose as syntax. Source preserved in git history; supporting fly-brain backend retired 2026-04-26.
- The retired `fly-brain/permutation_conditional.py` — the deprecated 4-way branching via sign-flip on query. Broken for Programs B/C/D because `sign_flip(NOT_key, query)` is a category error. Do not resurrect.
- `sdk/sutra-compiler/sutra_compiler/codegen_base.py` — the current hard rejection of `if/else`. `select` would replace the rejection with a positive construct the programmer is directed toward.
- `planning/sutra-spec/03-control-flow.md` — spec for the 2-way algebraic conditional. `select` would be a spec addition, not a spec replacement.

## What "doing this work" would look like

Not scheduled. When it comes back:

1. Resolve the defuzzification spec/paper contradiction first (pick Option A, B, or C above). This is the blocker.
2. Spec addendum to `03-control-flow.md` covering `gate`, `select`, and the status of `if/else`. Spec before code.
3. Parser support for `gate` and `select`. Keep the existing `if/else` parse; change only the codegen error to point at the replacements.
4. Codegen that emits the softmax-weighted-superposition pattern from `fuzzy_conditional.py`. Share prototype compilation with eigenrotation loops if feasible.
5. Validation: a `.su` file using `select` should hit the same 80/80 accuracy as `fuzzy_conditional.py`. Report honestly if it doesn't. Per `CLAUDE.md`, a smaller number is a real result, not a failure to rerun.
6. Lint or mechanical-translate sweep across existing `.su` files that use `if`. Policy call on whether to warn or error.
