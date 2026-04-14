# Sutra — Current State

**Read this at the start of every session.** It is the truth table, not the docs. Update it when state changes. Keep it under one screen.

## What this is right now

A **quantitative biology / programming-languages paper**, submitted to Claw4S 2026 (April 20 deadline), iterating on clawRxiv via `papers-ci.yml`. Not medicine. Not a physical device. A computational model with the real hemibrain graph as the substrate graph of the simulation. Physical deployment (patient neurons, neuromorphic chip, Neuralink-style interface) is Y-Combinator-tier future work, explicitly out of scope for the paper. **Lives are still at stake because the paper is load-bearing for that downstream pipeline** — faked numbers here propagate. See CLAUDE.md safety banner.

## Queued work (do in order)

Session 2026-04-13 shipped: (1) the two-pipeline restructure — fly-brain-paper now reports pipeline A (substrate-only, spiking rotation + cosine, 9/10 at k=3 + 14/30 k-sweep at SIM_MS=3000) alongside pipeline B (numpy rotation + MB-Jaccard, 20/20 + 30/30); (2) det=-1 construction bug fixed at source in `real_rotation_epg.py` via Kabsch sign correction; (3) tier framing stripped repo-wide (code + paper prose); (4) combined pipeline measured at 0/5 (MB is an anti-correlator, cannot tolerate Poisson-noised rotation output); (5) Q3 program-library expansion (`fly-brain/three_way_conditional.su`, `bind_unbind_chain.su` both codegen-clean); (6) Q1 substrate-only k-ceiling answered — SIM_MS sweep (`loop_140D_spiking_cosine_simms_sweep.py`) shows k-ceiling is integration-window-limited, not structural: 6000 ms lifts k=5 from 0/3 to 3/3, 12000 ms lifts k=8 from 0/3 to 2/3, consistent with Poisson √SIM_MS SNR scaling. Full findings: `planning/findings/2026-04-13-{combined-pipeline-0-of-5,140D-spiking-cosine-ordering-5-of-5,140D-spiking-cosine-v2-9-of-10,140D-spiking-cosine-ksweep-14-of-30,140D-spiking-cosine-simms-sweep}.md`.

Remaining queue, priority order:

1. **n=50 evaluation.** Rerun one or more headline results at n=50 seeds to kill the "n=5 is too small" reviewer thread. Candidates: 140-D Jaccard loop (5/5), target-k sweep (30/30), fuzzy conditional (80/80), substrate-only v2 (9/10).
2. **Pong with GUI.** Brain hosts game logic (ball physics = rotation, boundary = prototype match, AI paddle = fuzzy conditional). `fly-brain/pong_brain.py` has a 326-line scaffold. Stretch goal.

Tasks land one commit each per CLAUDE.md queue protocol. Commit both the STATUS.md removal and the implementation together.

## Direct-to-master audit (2026-04-13) — what the paralysis episode changed

A prior Claude Desktop session experienced repeated API timeouts while running a repo-content audit (transcript preserved in `dddd` at the repo root, itself queued for deletion once this section is read in a fresh session). During that paralysis the session committed directly to master while all other work it had been doing was routed through PRs. This mismatch is the exact pattern that produces "session reads the wrong source of truth" bugs. The resulting commits on master:

- `7e4c04c` deleted root `ARCHITECTURE.md` (byte-identical to `docs/architecture.md`, duplicated-doc risk).
- `863dd28` deleted `REPO-INVENTORY.md` (referenced `old-stuff/` and `inquisitive-transformer/` dirs that do not exist — pure stale narrator).
- `0e62b19` deleted `planning/akasha-{pivot,paper-strategy}.md` (pre-Sutra-rename, superseded by spec + DEVLOG).
- `9131247` deleted `fly-brain/{DOOM,DEMO,STATUS}.md` and the stray `real_rotation_epg_output.txt`. Note that `fly-brain/STATUS.md` is gone — the repo has exactly **one** STATUS.md (this file) from here on.
- `f3a3ea3` deleted the deprecated `fly-brain/permutation_conditional.{py,su}` (replaced by `fuzzy_conditional.{py,su}` months ago; the old files only survived as "deprecated" warnings in the former `fly-brain/STATUS.md`).
- `49fe4c7` deleted the `chats/... Claude_files/` browser-save sidecar directory (8 MB CSS/JS junk, extracted `.md` already present and was the real source).

This session (2026-04-13, branch `claude/complete-todo-md-RBGYu`) finished the other half of the audit that the paralyzed session never got to:

- Consolidated `fly-brain/todo.md` and `sutraDB/TODO.md` into root `todo.md` (one file instead of three — per the "multiple parallel narrators" critique in the audit transcript). Fly-brain content prepended with `!` markers; SutraDB content appended as the lower-priority tail.
- Added meta-tasks at the top of `todo.md`: (a) audit the `fly-brain/` Python sprawl, (b) keep `todo.md` organized under an explicit priority scheme (Immediate / Pre-Claw4S / Pre-YC / This year).
- Wrote `planning/merge-help.md` covering the PR/merge workflow on this repo specifically — why direct-master vs branch+PR matters here, why `GITHUB_TOKEN` cannot push workflow changes, and a recovery playbook for the "committed to the wrong branch" case that caused this episode.

Do **not** reconstitute the deleted files. If something was deleted that should not have been, restore from git history with an explicit commit that names the file and says why. Silent resurrection is the failure mode.

## Built / Works

- **Snap / MB Jaccard on real hemibrain wiring** — PN→KC sparse projection, APL-enforced ~7.8% sparsity, Jaccard prototype match. This is genuinely on the connectome.
- **Conditional branching** — 16/16 and 80/80 across 5 hemibrain seeds via fuzzy weighted superposition (`fly-brain/fuzzy_conditional.py`). 4/4 distinct program mappings.
- **Bounded loops `loop[N]`** — unrolled at compile time into flat algebraic expressions. No runtime iteration. No eigenrotation. Works.
- **Eigenrotation loops (scaled eval)** — 20/20 across 5 hemibrain seeds (`fly-brain/scale_eval_loop.py`): convergence@3, counting to 3, counting to 6, ordering-first-EARLY all 5/5. Convergence iters σ=0.
- **Bundle / bind / rotate on synthetic-weight spiking circuits** (`fly-brain/neural_vsa.py`) — Brian2 LIF, Givens R as synapse weights. Cos 0.94–0.99 vs numpy reference (numpy used as the monitoring reference, not the runtime). Rotation R is chosen by us, not by biology.
- **Bundle on real FlyWire wiring** (`fly-brain/neural_vsa_flywire.py`) — cos 0.94 vs W·v reference.
- **I/O rate coding** — centered rate encoding of hypervectors as PN currents, linear MBON readout via ridge regression. Works.
- **Compiler pipeline** — `sdk/sutra-compiler/` emits Python that calls `fly-brain/vsa_operations.py`. `.su` programs (e.g. `permutation_conditional.su`) compile through it.
- **End-to-end fuzzy conditional compile** — `fly-brain/fuzzy_conditional.su` → codegen → live MB simulation, 16/16 pass, 4/4 distinct program mappings (`fly-brain/test_codegen_e2e_fuzzy.py`).

## Conditional branching — FIXED

**Spec-aligned 4-way fuzzy weighted superposition hits 16/16 on toy substrate and 80/80 across 5 independent seeds on the real hemibrain (100%, σ=0).** New file: `fly-brain/fuzzy_conditional.py`. The deprecated `permutation_conditional.py` used `sign_flip(NOT_key, query)` as semantic NOT — that's a category error (a random ±1 pattern has no relationship to the "other polarity" of a feature axis), which is why Programs B/C/D averaged ~50%. Per spec 03-control-flow.md: `result = Σ w_i · branch_i` with weights from clipped cosine scores against the 4 joint prototypes. 4 programs differ only in the prototype-to-behavior map; decision pipeline is identical.

## CI pipeline state

Reverted from branch+PR to direct-master-push (commit 211bd92). The branch+PR approach failed because `GITHUB_TOKEN` cannot modify workflow files regardless of permissions config. Push-retry-with-rebase loop handles the race conditions that motivated the PR flow. Preserved the `detect-changed` full-push-range fix from bd85ce0. Cron verified working (competition-cron run 24320014564 succeeded).

## Open / Known Gaps

Currently active top-priority gap (real progress 2026-04-12):

- **Rotation from real wiring** 🟢 **COMPOSED ACROSS 4 MOTIFS, 713-D** — surveyed 11 FlyWire motifs (`fly-brain/survey_rotation_candidates.py`). Winner: **CX EPG→EPG recurrent, 51 neurons, effective rank 49, off-diagonal fraction 0.508** — an order of magnitude closer to orthogonal than ALPN→LHLN. Polar decomposition (`fly-brain/real_rotation_epg.py`) yields Q = nearest orthogonal matrix to the real biological W, with Q^T Q = I to 1e-14, det Q = +1, norm preservation to machine precision. Geometric loop test on Q (`fly-brain/real_rotation_epg_loop.py`) passes **10/10 counting (k=3 and k=6 × 5 seeds) + 5/5 ordering (EARLY first at k=2)** — Q iterates cleanly and the `loop(condition)` pattern works on real-wiring-derived rotation. Composing Q block-diagonally from 4 near-orthogonal FlyWire motifs (EPG→EPG, LH→LH, FB vDelta→vDelta, FB hDelta→hDelta) scales cleanly to **713 dimensions with orthogonality residual 5.34e-14** (`fly-brain/real_rotation_composed.py`), passing 10/10 counting + 5/5 ordering at every composition stage (51-D, 167-D, 524-D, 713-D). Spiking lift (`fly-brain/real_rotation_epg_loop_spiking.py`) iterates Q through Brian2 LIF `rotate(v, Q)` (51 Poisson inputs → 51 LIF outputs via Q-weighted synapse matrix) at SIM_MS=3000ms per step and hits **3/5 seeds argmax_k=3 at target k=3** — the honest result is: iterated spiking rotation accumulates Poisson noise, and for seeds where the numpy cos between state_1 and Q³·v₀ is already close to cos between state_3 and Q³·v₀ (a spectral-structure artifact of EPG Q — `cos(Q v, Q³ v) = cos(v, Q² v)` which can be large if Q² has eigenvalues near 1), the spike noise flips argmax. The numpy equivalent is 10/10 because Q is orthogonal at machine precision. Paths to improve: longer SIM_MS, sharper-spectrum Q composed from motifs with more evenly distributed eigenphases, or loop-termination via Jaccard-on-KC which has higher SNR than direct cosine readout. Caveat: biological W is 98.3% Frobenius-distance from Q — the orthogonal operator is derived from W's SVD subspace, not equal to W. Also: this test runs rotation in 51-D EPG space, not through the MB spiking circuit — integrating the two (compose Q with PN→KC, or run a 51-D KC-free geometric loop end-to-end with spiking `rotate(v, Q)`) is the next step. Honest framing: "rotation operator within the 51-D subspace spanned by the EPG recurrent projection, derived via polar decomposition from the real FlyWire weights." Not "the biology IS the rotation" — but not synthetic Givens either, and the loop compiles.

Lower priority (still open, not blocking):

- **Conditional branching on remote substrate** — the final argmax over 4 behavior candidates and the outer loop sequencer run in host Python. Note: this is NOT the conditional branching itself; branching (choosing which of 4 prototypes matches the query) already runs on the MB via Jaccard on KC patterns. The host's job is a small 4-way readout and loop driver. Reviewer v22 conflated readout-on-host with branching-on-host; they are different. Design doc kept in `planning/open-questions/conditional-branching-on-remote.md` for when/if we want fully-autonomous execution, but not urgent.

Longer-term / lower-priority:

- **Intrinsic temporal dynamics** — the `for i in range(max_iters)` that threads ops together runs in host Python. No substrate-intrinsic trajectory yet. (User: don't need to address for this paper.)
- **Dimensionality** — 140-PN I/O is narrow vs standard VSA (1k–10k). Real limitation; KC-promotion to 1,882-D is planned but not urgent.
- **Eval size** — branching now 80/80 across 5 seeds, loops 20/20 across 5 seeds. Reviewer's residual objection is program-*template* variety (4 conditional templates, 3 loop-test types), which seeds don't buy. Open whether this matters — the paper is a primitive demonstration, not a program-library survey.
- **Biological learning rule** — MBON readout is ridge regression, not dopamine-gated plasticity. Planned, not urgent.

## Strategic notes

- **Conditional branching fully on the MB is likely paper-worthy in its own right.** `fuzzy_conditional.py` running 80/80 σ=0 on hemibrain — with the branching decision (snap + Jaccard prototype match) executed entirely on the substrate — is a standalone contribution. Probably not enough to *win* Claw4S on its own, but genuinely career-building. If the combined primitives paper doesn't land, a narrower branching-on-connectome paper is a credible fallback.
- **Reviewer v22 conflated readout with branching.** The host Python code does (a) read which of 4 behavior prototypes won a 4-way max, and (b) drive the outer loop iteration. Only (b) is real "control flow on host." (a) is readout — every biological system has readout. This distinction should be explicit in the next paper revision.

## Backlog (not urgent, pick up after paper)

Concrete work that is worth doing but not ordered into the queue. Different from `## Open / Known Gaps` (those are limitations of the current approach) and from `planning/open-questions/` (those are design decisions that need resolving before acting). Backlog items are ready to implement, just not yet prioritized.

- **Codegen V1 feature coverage** — lint sweep on 2026-04-12 found 7/13 `.su` files compile fine, 6/13 hit `CodegenNotSupported` on method decls / operator decls / `EmbedExpr` / `DefuzzyExpr` / `UnsafeCastExpr`. Paper-cited programs all compile; illustrative examples don't. Cheap wins: lower `EmbedExpr` → `basis_vector(name)`; lower `DefuzzyExpr` → `_VSA.is_true(...)` (needs matching runtime method). See `planning/open-questions/codegen-v1-feature-coverage.md` for the full breakdown and decision points.

## Out of Scope (don't touch unless user opens it)

- Physical deployment, in-vivo execution, neuromorphic hardware bridge, BCI interface design.
- Intrinsic temporal dynamics / host-free run loop (user explicitly said skip).
- `foreach` loops (not yet in spec; if added, would unroll like `loop[N]`, no eigenrotation).

## Pinned semantic corrections (I keep dropping these)

1. **`loop[N]` unrolls at compile time. Zero runtime iteration. No eigenrotation.** Only `loop(condition)` with data-dependent termination eigenrotates. See `planning/sutra-spec/03-control-flow.md`. The eigenrotation gap is a narrow slice of the language surface, not the common case.
2. **No loop counters live on the host at runtime.** The "counter" for `loop(condition)` IS the angular position on the helix R^i·v₀ in the substrate. Corkscrew geometry. Not an integer.
3. **"Rotation on neurons" has two meanings, don't conflate:**
   - Synthetic R (Givens composition) realized as Brian2 synapse weights → works (`neural_vsa.py`).
   - Real FlyWire weight matrix AS the rotation → does not rotate (compressive projection).
   Paper must say which is which every time.
4. **Compile target is patient neurons / neuromorphic chip with FlyWire topology.** Brian2 is dev-time simulator only. Simulation wall-clock latency is irrelevant to deployment — but deployment itself is out of scope for this paper.
5. **Rotation in biology is fixed by anatomy.** You do not pick R. You compile within the eigenstructure the patient's connectome provides.
6. **Permute → sign_flip rename.** The op does sign-flip binding (`a * sign(role)`), not dimension permutation. Spec's `permute` means shuffle. Class aliases preserved for back-compat.

## Current paper state

- `fly-brain-paper/paper.md` — 2026-04-13 two-pipeline restructure pushed. Abstract, §Result 2, §Honest Limits, §Future Work all rewritten around pipeline A (substrate-only, 9/10 + 14/30) and pipeline B (numpy rotation + MB-Jaccard, 20/20 + 30/30) reported side-by-side. Awaiting next papers-CI review.
- `sutra-paper/paper.md` — tier framing stripped (commit earlier today); has not yet been restructured around the two-pipeline result. Queued (item 3).

## Workflow reminders

- **Push triggers papers-CI** → new clawRxiv submission + new review. Every push is a version. Edit aggressively; the old "incremental edits only" rule was retired 2026-04-13.
- **Never mention "Claw4S 2026"** in paper body — reviewer flags as hallucinated citation. Reference companion papers by clawRxiv post number only.
- `git pull --rebase` before every push is still wise (human collaborators, pages.yml, etc.), but papers-CI and competition-cron no longer push to master — they open PRs on branches `papers-ci/<paper_dir>/run-<id>` and `competition-cron/run-<id>`. Merge PRs by hand until auto-merge is wired up.
- **Merge / PR guidance: `planning/merge-help.md`.** Consult before opening PRs, after CI rejections, or when recovering from a mis-targeted commit. Includes the recovery playbook for the "committed to master but meant a branch" case that produced the 2026-04-13 paralysis episode.
- **There is exactly one todo.md** (repo root) and exactly one STATUS.md (this file). `fly-brain/todo.md` and `sutraDB/TODO.md` have been consolidated into the root `todo.md`; do not recreate them. STATUS.md = active queue; todo.md = long-term agenda. If the two disagree, STATUS.md wins for now-work and todo.md wins for later-work.

## Formal Sutra grammar (EBNF)

Derived from `sdk/sutra-compiler/sutra_compiler/lexer.py` + `parser.py`, reconstructed 2026-04-13. Authoritative source is the parser; this is a readable summary.

```ebnf
(* Module structure *)
module          = { top_level } EOF ;
top_level       = function_decl | method_decl | operator_decl ;
modifiers       = { "public" | "private" | "static" | "implicit" } ;

function_decl   = modifiers "function" IDENT [ type_params ] param_list
                  [ ":" type ] block ;
method_decl     = modifiers "method" IDENT [ type_params ] param_list
                  [ ":" type ] block ;
operator_decl   = modifiers "operator" operator_symbol [ type_params ]
                  param_list [ ":" type ] block ;
type_params     = "<" IDENT { "," IDENT } ">" ;
param_list      = "(" [ param { "," param } ] ")" ;
param           = IDENT ":" type ;
type            = IDENT [ "<" type { "," type } ">" ] ;

(* Statements *)
block           = "{" { statement } "}" ;
statement       = var_decl | if_stmt | while_stmt | for_stmt
                | foreach_stmt | do_while_stmt | loop_stmt
                | try_stmt | return_stmt | expr_stmt ;

var_decl        = ( "var" | "const" ) IDENT [ ":" type ]
                  [ "=" expr ] ";" ;
if_stmt         = "if" "(" expr ")" block [ "else" ( if_stmt | block ) ] ;
while_stmt      = "while" "(" expr ")" block ;
for_stmt        = "for" "(" [ var_decl | expr_stmt ] ";"
                  [ expr ] ";" [ expr ] ")" block ;
foreach_stmt    = "foreach" "(" IDENT "in" expr ")" block ;
do_while_stmt   = "do" block "while" "(" expr ")" ";" ;
try_stmt        = "try" block "catch" block ;
return_stmt     = "return" [ expr ] ";" ;
expr_stmt       = expr ";" ;

(* The core Sutra iteration construct *)
loop_stmt       = "loop" "(" loop_header ")" block ;
loop_header     = INT_LIT [ "as" IDENT ]   (* bounded: unrolled at compile time *)
                | expr ;                    (* condition-based: eigenrotation *)

(* Expressions — precedence from low to high *)
expr            = pipe_forward ;
pipe_forward    = assignment { "|>" assignment } ;
assignment      = logical_or [ ( "=" | "+=" | "-=" | "*=" | "/=" ) assignment ] ;
logical_or      = logical_and { "||" logical_and } ;
logical_and     = equality { "&&" equality } ;
equality        = comparison { ( "==" | "!=" ) comparison } ;
comparison      = additive { ( "<" | ">" | "<=" | ">=" ) additive } ;
additive        = multiplicative { ( "+" | "-" ) multiplicative } ;
multiplicative  = unary { ( "*" | "/" | "%" ) unary } ;
unary           = [ "!" | "-" | "++" | "--" ] postfix ;
postfix         = primary { "." IDENT | "(" arg_list ")"
                          | "<" type_args ">" "(" arg_list ")"
                          | "[" expr "]" | "++" | "--" | "as" type } ;

primary         = INT_LIT | FLOAT_LIT | STRING_LIT | interp_string
                | "true" | "false" | "this"
                | IDENT | special_call | map_literal | array_literal
                | "(" expr ")" ;

special_call    = ( "unsafeCast" | "unsafeOverride"
                  | "defuzzy" | "embed" )
                  [ "<" type { "," type } ">" ] "(" expr ")" ;
map_literal     = "{" [ map_entry { "," map_entry } ] "}" ;
map_entry       = ( IDENT | STRING_LIT ) ":" expr ;
array_literal   = "[" [ expr { "," expr } ] "]" ;
interp_string   = "$\"" { STRING_LIT_CHUNK | "{" expr "}" } "\"" ;

arg_list        = [ expr { "," expr } ] ;
type_args       = type { "," type } ;
operator_symbol = "+" | "-" | "*" | "/" | "==" | "<" | ">" | "<=" | ">="
                | "[]" | "[]=" ;

(* Reserved keywords (from lexer KEYWORDS table) *)
(* function method static public private var const return
   if else while for foreach in do loop as try catch this
   operator new implicit true false                           *)
```

**Notes on the grammar.**

- `loop` is the only iteration construct that Sutra *semantically* distinguishes between a bounded (compile-time unrolled) form and a condition-based (eigenrotation on the substrate) form. `while`, `for`, `foreach`, `do_while` are host-side iteration; they compile to scaffolding, not to substrate eigenrotation.
- Sutra has no dedicated `bind`, `bundle`, `snap`, `similarity`, etc. keywords. These are ordinary functions in the runtime — calls written with regular `IDENT "(" arg_list ")"` syntax. The special-call production only covers the four forms (`unsafeCast`, `unsafeOverride`, `defuzzy`, `embed`) that need compiler-internal AST nodes rather than regular function dispatch.
- `if`/`else` is present in the grammar but is *host-side* control flow. Sutra programs that need substrate-side branching use fuzzy weighted superposition (spec §03) expressed as ordinary function calls, not an `if`-tree. The compiler does not reject `if` — it emits host Python `if`, same as any other scaffolding construct.
- `defuzzy(expr)` is the opt-in defuzzification marker (spec §04), lowered to `_VSA.is_true(...)` when the runtime supports it. `embed(expr)` is the string-to-vector primitive for codebook construction.
- The surface syntax is C-family: braces, semicolons, `==`/`!=`, dot-access, postfix `++`/`--`. This is deliberate — the novel semantics live in the runtime (fuzzy-by-default, vector operations on the substrate), not in the syntax.
