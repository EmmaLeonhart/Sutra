# Sutra — consolidated TODO

## TOP PRIORITY

## Neural-network Turing-completeness — the architectural roadmap (metabolised 2026-06-07)

Metabolised from Emma's Claude conversation "Neural network approaches to Turing
completeness" (saved page is gitignored, reference only — not committed). This is
the organizing frame for Sutra's architectural diversification.

**Emma's three primary routes — each makes a DIFFERENT resource unbounded:**

| Route | Unbounded resource | Sutra status |
|---|---|---|
| **RNN / recurrent neurons** | **time** (steps) | DONE — substrate loops / `recur` are a substrate-RNN; the loop step now fuses into one graph + exports as a weight file (#6/#7, `emit_loop_weight_file`). See `non-halting-loop.md`. |
| **External memory (NTM / DNC; LLM-context)** | **space** (tape / stack / context) | ACTIVE — external RAM + orchestrator + VRAM mailbox (`ram-pointers.md`, `experiments/ntm_ram/`). RAM stays EXTERNAL + hard/discrete I/O; a *trainable* NTM trains the **controller**, not the RAM. **Do NOT fuse RAM into VRAM** (the 2026-06-07 wrong turn, reverted). |
| **Reservoir computing** | **state** (fixed dynamics; infinite reservoir = infinite state) | DEFERRED to the OS era (Yantra). |

**The sharper organizing principle (from the conversation): classify by *which
resource is made unbounded*** — time (recurrence), state (reservoir), space
(external memory), **precision** (analog / real-valued nets — Siegelmann & Sontag:
finite-precision discrete RNNs hit *exactly* Turing-completeness, real-valued ones
*exceed* it; this is Sutra's existing theoretical framing), **depth** (a fixed net
applied an unbounded number of times with a halting condition — chain-of-thought +
scratchpad; the orchestrator-driven step loop is exactly this shape). Keep these
five axes straight in the paper's theory section.

**External-memory sub-splits + other proposed routes (future framings, not active
work):** DNC/NTM (addressable tape), stack-augmented nets (one stack suffices),
pointer-nets / attention-over-mutable-state; hypernetworks (a net writes another
net's weights at runtime — the "program" written step by step); neural program
synthesis / execution (compile a target formalism in — Graves' differentiable
Forth; close to Sutra's compile-a-program-to-a-graph stance); iterative application
/ CoT-scratchpad (finite net, unbounded *process*); Neural ODEs (continuous-time
dynamics — the precision axis).

**Why this matters for Sutra:** Sutra deliberately pursues the three primary routes
as DISTINCT architectures (do not blur them — the 2026-06-07 fused-RAM mistake
blurred NTM into RNN). The resource-axis frame is the clean way to position Sutra's
Turing-completeness claims in the paper(s) and to scope what each architecture must
demonstrate.

> ## 🔬 TOP PRIORITY — PCA on the WASM transformer (remove this block when done)
>
> Do **principal component analysis on the WASM transformer** — the
> transformer that comes in with the `WASM/` subtree (from
> `replicating-neural-computers-2`).
>
> **Why:** we want to use the transformer's learned **weights** to figure out
> the most optimal way to run **attention for the differentiable-neural-computer
> (DNC) work**. The transformer is very likely **significantly larger than it
> needs to be**, so a PCA of its weights should reveal the genuine
> low-dimensional structure we can keep — i.e. the reduced attention we can
> actually run on the substrate.
>
> **Gating: LIFTED 2026-06-06 — `WASM/` is now in-tree** (subtree merge,
> full history). The transformer weights live under `WASM/` (analytic model
> `d_model=38, 7 layers, 19 heads, vocab=915`; plus the learned-ops
> checkpoints under `WASM/src/learned_ops/`). This is the first WASM-gated
> item to actually work — promote it into `queue.md` when starting.
>
> **Remove this entire block once the PCA work is done.**

---

## 🌐 Merged agenda — from the Neural WebAssembly (`WASM/`) repo

> **Origin banner.** The items below were merged in from the long-horizon
> `todo.md` of the **Neural WebAssembly** repo (`replicating-neural-computers-2`,
> remote `EmmaLeonhart/neural-webassembly`) when it was subtreed into `WASM/`
> on 2026-06-06. They are now part of Sutra's long-horizon agenda. Overview:
> `docs/neural-webassembly.md`; deep notes under `WASM/notes/`. Decompose into
> `queue.md` one phase at a time (design-only until pulled).

### Forward goal: integrate `transformer-vm` into the Yantra OS

Adopt `transformer-vm` as the way Yantra runs WebAssembly. Architecture decided in
the 2026-06-05 interview — full design + trap-and-resume ABI + phased roadmap in
`WASM/notes/yantra_integration.md`. Decisions: real neural executor · universal
interpreter · per-process sandbox · full WASM MVP · syscalls trap-and-resume to
kernel · floats trap to host FPU · linear memory = real RAM. **This converges with
Sutra's own NTM/RAM-pointer track** (`planning/sutra-spec/ram-pointers.md`) — keep
the trap ABI and the Sutra orchestrator design aligned.

- **P0 — Trap substrate** (linchpin): trap ABI + C++ engine pause/host-callback/
  resume + one round-tripping demo trap.
- **P1 — Memory as trapped real RAM** (LOAD/STORE → host RAM).
- **P2 — Syscalls / WASI** over the trap channel.
- **P3 — Floats via host-FPU trap.**
- **P4 — Integer ISA completion** (i64, native bitwise/shift, br_table, typed select).
- **P5 — Tables / indirect calls, memory.grow.**
- **P6 — Per-process lifecycle** (snapshot/restore residual+hull state; scheduling).

### Replication follow-ups (optional — core replication already done)

- **Python hull path:** with `python3-dev`, confirm `wasm-eval --hull` /
  `pytest -m "not slow"` pass fast; compare hull (O(log n)) vs `--nohull`
  brute-force timings to quantify the attention-scaling claim.
- **Throughput gap:** investigate the ~18K vs ~30K tok/s gap (WSL overhead,
  BLAS-free matvec); try a native-Linux or BLAS-linked build.

### ★ The isomorphism program: Neural WebAssembly → Rust → OCaml → Sutra

Full motivation/classification in `WASM/notes/significance_and_isomorphism.md`. In
one line: `transformer-vm` is an **autoregressive, deterministic Neural Turing
Machine** — attention used to address RAM, then deterministic, fully
code-describable operations. Make that code **explicit and isomorphic**, and carry
the isomorphism across languages until it reaches **Sutra**. Equivalence by
behavioural tests (formal verification later). Worked strictly in order:

1. **Research + write-up** — consolidate the architectural classification. (Done;
   seed `WASM/notes/significance_and_isomorphism.md`, overview
   `docs/neural-webassembly.md`.)
2. **Search for a reference implementation** — C/C++/Rust of this append-only /
   attention-addressed shape. (Done — Percepta's own reference.)
3. **Rust (isomorphic)** — deterministic imperative port. (Done — `WASM/iso/rust/`.)
4. **Test Rust** — byte-identical traces vs the transformer on all examples. (Done.)
5. **OCaml (isomorphic)** — ML-family port, structurally close to Sutra. (Done —
   `WASM/iso/ocaml/`; transformer ≡ reference ≡ Rust ≡ OCaml, byte-identical.)
6. **Test OCaml** — same battery. (Done.)
7. **Sutra (end of the road) — ISO-5.** Port the OCaml realisation into Sutra and
   test how far Sutra can express this machine. **This is the final item.** It was
   blocked in the WASM repo only on lack of access to Sutra's syntax/toolchain —
   **that blocker is now gone** (Sutra is this repo). Sutra's `sutra-from-ocaml`
   frontend (`sdk/sutra-from-ocaml/`) is the natural on-ramp.

> ## 📋 ACTION FOR EMMA — set up the daily cloud-audit routine
>
> The `RemoteTrigger` tool fails in-session (every call arrives with
> empty params — harness bug, not a param issue), so this routine
> can't be created programmatically. Create it once by hand at
> **https://claude.ai/code/routines** with the config below. The web
> UI uses the same cloud mechanism, so it runs even when no local
> session / machine is up. Delete this block once the routine exists.
>
> **Routine config**
> - **Name:** `Sutra daily substrate-leak + stale-open-question audit`
> - **Schedule (cron, UTC):** `17 9 * * *` (daily 09:17 UTC ≈ 02:17
>   America/Vancouver, overnight)
> - **Repo:** `https://github.com/EmmaLeonhart/Sutra`
> - **Model:** `claude-opus-4-7` (safety-critical)
> - **Environment:** Default
> - **Tools:** Bash, Read, Write, Edit, Glob, Grep
>
> **Prompt (paste verbatim):**
>
> ```
> Daily substrate-leak + stale-open-question audit for the Sutra repo,
> a SAFETY-CRITICAL compiler. Do NOT fake results.
>
> 1. git pull origin master (fresh).
>
> 2. SUBSTRATE-LEAK AUDIT.
>    (a) cd sdk/sutra-compiler && python ../../experiments/substrate_leak_sweep.py
>        — compiles every corpus+examples .su and greps emitted Python
>        for raw-operator leaks; rc != 0 means a leak.
>    (b) Grep the emitted runtime in sutra_compiler/codegen_pytorch.py
>        for host-scalar leak signatures INSIDE op definitions: float(,
>        .item(), _math., _np., "for ... in range", host if/raise on a
>        scalar. Cross-check Audit.md's REAL LEAK / BORDERLINE /
>        LEGITIMATE taxonomy so the compile-time-constant cache guards,
>        the _st()/_cnum entry boundary, and monitoring accessors are
>        NOT re-flagged.
>    (c) Re-read Audit.md REAL LEAK: verify ones marked FIXED still
>        show 0 leak signatures + their cited test; confirm the still-
>        open ones (#3 promise await loop, #4 generic loop runtime
>        host for, #5 string host codepoint loops) are still accurate.
>
> 3. STALE-OPEN-QUESTION AUDIT. For every planning/open-questions/*.md
>    and every entry in planning/sutra-spec/open-questions.md, check
>    whether it is actually already decided elsewhere — planning/
>    sutra-spec/*.md, todo.md, DEVLOG.md, or a dated planning/findings/
>    doc. "Resolved elsewhere" = the design it asks about is specified
>    authoritatively even though the open-question file still says
>    open. (This failure occurred 2026-05-15: the unified-complex-
>    number representation was treated as open when todo.md fully
>    specifies it. The open-questions README now has a verdict table —
>    cross-check it; flag any drift.)
>
> 4. IF ANYTHING FOUND: prepend ONE concrete fix item to the TOP of
>    queue.md's Active queue — immediately after the "## super active"
>    block, before the existing first item, so it is the new highest
>    priority. Leak: name file:line + the fix shape (tensors in ->
>    tensor ops -> tensors out; saturate, never raise). Resolved-
>    elsewhere question: name the open-question file AND the
>    authoritative location that resolves it, and say to reduce the
>    doc to a pointer. Then git add + commit ("daily audit: <finding>")
>    + git push (git pull --rebase then push if rejected; stash
>    .claude/*.lock if it blocks the rebase; never discard others'
>    work).
>
> 5. IF CLEAN: do not invent work. Append one line to DEVLOG.md:
>    "<UTC date> daily audit: clean (<N> .su compiled, 0 leaks; <M>
>    open-questions checked, 0 resolved-elsewhere)", commit + push.
>    That is the legitimate no-op.
>
> 6. Honor CLAUDE.md. Never relax a gate, doctor a number, or mark
>    anything resolved you did not verify. If the audit itself cannot
>    run (e.g. torch missing), write that in the DEVLOG line and exit
>    nonzero rather than reporting a false clean.
> ```

> ## 🌅 RESTART HERE (handoff 2026-05-20, post-arXiv upload)
>
> **`paper/paper.md` is on arXiv.** The arXiv-fitting abstract trim
> landed 2026-05-19 at commit `e7cca673`; the current repo state is
> the version that was uploaded. `paper/neurips/` stays frozen
> per CLAUDE.md §"NeurIPS submission is FROZEN." Live `paper/paper.md`
> may continue to evolve toward the next venue. **`DEVLOG.md` was
> refreshed 2026-05-20** with a comprehensive entry covering everything
> from the 2026-05-06 NeurIPS sprint through the arXiv upload (Stage A/B
> §3.6 integrity fix, anisotropy spine, site rebuild, master→main
> migration, scalar→number rename, transcendentals via interpolated
> lookup, implicit-loop work, TS transpiler closeout, substrate-leak
> audit).
>
> No paper-editing pressure right now. Optional next-venue polish lives
> in `queue.md` (ablation table, polynomial-rationale paragraph,
> Le Chat's section-granular AI-use breakdown, optional Futamura bib
> entry).
>
> Done earlier and still load-bearing: `ccos` complex-argument cosine;
> `scalar`→`number` rename (3 gated commits, `number` canonical,
> `scalar` deprecated alias for the frozen archive); Audit REAL
> LEAK **#4 reclassified NOT a leak** (Emma — it is a fixed-T
> tail-recursive cell, no host branch on data); queue hygiene;
> open-question banners; "eigenrotation" dropped for the loop
> surface (it described a tail-recursive RNN-cell, not a literal
> eigenrotation — misleading; the trig/rotation-primitive math
> keeps the term legitimately). What remains, genuinely hard,
> left in-progress on purpose (NOT faked):
>
> ### 1. Implicit tail-recursive loops — `loop(x){ body }` sugar — ✅ SHIPPED
> **DONE.** The implicit `loop(expr){ body }` desugar is built
> (`sdk/sutra-compiler/sutra_compiler/loop_desugar.py`, with
> `loop_capture.py` for the free/mutated-variable analysis) and
> tested end-to-end on both backends
> (`sdk/sutra-compiler/tests/test_implicit_loop_desugar.py`):
> single-var, multi-var (the implicit axon, item 1b), `while`-
> relational bounds, class-method local state, literal-bound
> still-unrolls no-regression, plus clear-error cases. The old
> "parsed-but-rejected / build-from-scratch" framing below is
> obsolete.
>
> ### 2. Audit REAL LEAK #3 — promise `await_value` host `if/break` — (may be shipped — verify)
> Audit.md now reports all REAL LEAK #1–#10 FIXED, which includes
> #3; the host `if/break` poll-loop framing here is likely closed.
> Verify against `Audit.md` and `planning/sutra-spec/promises.md`
> before acting on the text below.
> `codegen_pytorch.py:~808` `for _ in range(100): if
> self.isPending(p) <= 0.5: break` — the `if … break` is a real
> host Python branch on a predicate (this is the genuine leak;
> the surrounding fixed-count `for` is not, same reason #4 isn't).
> **Emma direction 2026-05-17 (supersedes the earlier "await is
> just the simplest loop" framing):** async/await/promise should
> probably NOT be modeled as a poll loop at all. Model the awaited
> value as an **implicit axon INPUT to the function plus a runtime
> "has it arrived yet" flag axis** for the whole program — the
> value is a deferred input slot; a flag says delivered/not; no
> spinning, no host branch. async/await/promise have **explicit
> formal specifications** (Promises/A+, ECMAScript async) — the
> implementation must conform to those, not improvise. **How:**
> reconcile `planning/sutra-spec/promises.md` with this
> implicit-axon-input + arrival-flag model and the formal spec,
> then re-lower `await_value` accordingly (delete the host
> `if/break`). **Gate:** promise corpus fixtures + smoke; behavior
> checked against the formal async/promise spec, not just "it
> ran". Deliberate, gated.
>
> ### 3. Literate-math tail — drop the 0-d projection (scalar→number DONE)
> The `scalar`→`number` rename **shipped this session** (3 gated
> commits: compiler `number` first-class + `scalar` deprecated
> alias; stdlib `.su` dogfood; docs). What REMAINS is the
> separate, riskier half: **drop the 0-d projection so
> `exp`/`cos`/`sin` return the full number-vector** instead of a
> 0-d tensor, then migrate call sites + corpus in batches. **Why
> hard:** changes observable return shape; can regress paper-cited
> `cos`/`sin`/`exp`; high blast radius; tedious. **How:**
> projection drop behind the verified `cexp`, full suite green per
> batch, explicit paper-code-durability check (the frozen NeurIPS
> examples must still produce the same observable outputs).
> cexp + pow/sqrt/tan/sinh/cosh/tanh are already literate and
> verified — this only finishes exp/cos/sin. Deliberate, gated.
>
> Lower-value remainder (do last, or decide to skip): #15 dossier
> retirement — the `planning/open-questions/README.md` verdict
> table is authoritative; deleting the 9 RESOLVED/STALE dossier
> files is a destructive rationale-loss call left for Emma, not a
> blocker.
>
> Discipline that held all session and must keep holding: verify
> against ground truth + the real test suite before marking
> anything done; revert rather than ship wrong/half math; read
> the documented vision (todo.md / spec / findings) before calling
> anything an "open design gap"; commit+push each verified unit.

This file is the long-term agenda. `queue.md` at the repo root is the
active session queue — if the two disagree, queue.md wins for what is
being worked on *now*, and this file wins for what needs doing
*eventually*. Do not re-split this into per-subdirectory todo files.

## 🗂 Priority levels

- **Immediate** — do right now / this session. Usually mirrored in `queue.md`.
- **This year** — should land in 2026, not necessarily tied to a deadline.

When adding an item, pick a level. When closing one, delete the line.

Note: the "Pre-Claw4S" priority level (deadline 2026-04-20) was retired
on 2026-04-20 when the papers/submission layer was removed from the
repo. Items that used to live under it have either been completed
(sign-flip removal → rotation binding, 2026-04-22) or no longer apply
(paper-scope maintenance) or moved to findings (substrate design work
is now ongoing under `planning/findings/` rather than deadline-driven).

---

## [This year] Multi-language transpiler frontends (source → Sutra) — roadmap (Emma 2026-06-05)

> **⏸ ON HOLD — DEPRIORITIZED BEHIND GUI (Emma 2026-06-11).** GUI is the top
> priority. The work-loop finishes the GUI block (queue.md) FIRST, then attempts
> these new-language frontends automatically via this todo. They are *not* killed —
> just last to pull. OCaml (the reference frontend) is already done for now; the
> on-hold set is the **new languages** (Scala → F# → Elixir/Erlang → Clojure →
> Haskell → Rust → WASM) plus **`let rec` non-tail recursion**. See the consolidated
> "[ON HOLD — after GUI]" section at the END of this file for the pull-last summary.

Sutra today has exactly one working source-language frontend:
`sdk/sutra-from-ts/` (TypeScript, with JavaScript read as untyped TS).
`sdk/sutra-from-c/` is parked. The TS/JS path works but is not a great
fit — JS's dynamic, imperative, mutation-heavy core fights Sutra's
purely-functional algebraic substrate, so much of the surface lowers
awkwardly or is rejected.

**The bet:** Sutra is a *purely functional* language, so the source
languages that transpile *cleanly* are the other functional languages —
their expression-orientation, immutability, and algebraic data types
line up with Sutra's core instead of fighting it. The next frontends are
therefore functional, easiest-mapping first.

**Borne out (2026-06-05).** `sdk/sutra-from-ocaml/` is now the most complete
*verified-running* frontend (functions, arithmetic, comparisons, if/then/else,
`let…in`, tail-recursive `let rec`→`loop`, `match`, records→axons — every
feature checked compile-AND-run on the substrate). It is now the **reference
implementation** new frontends model on, not `-ts`. Building OCaml records even
exposed that the TS `interface`→axon path returns zeros at runtime (it was only
ever compile-tested). **Priority (Emma 2026-06-05): (1) OCaml first; (2) fix the
TS axon bug; (3) then Scala → F# → Elixir/Erlang → Clojure → Haskell → Rust →
WASM.** Active decomposition lives in `queue.md` §Transpiler track.

**Execution model.** This whole track runs on the **1pm local-cron
work-loop** (set up 2026-06-05), kept separate from the main RAM/W2C
queue another agent is driving. The work-loop **pulls from remote and
rebases first on every tick** — the other agent pushes real work, so
sync-before-work is mandatory, not optional. The transpiler track gets
its own queue.md section so it does not stomp the RAM/W2C items.

### Phase 1 — functional-language frontends, in priority order

Each is a new `sdk/sutra-from-<lang>/` frontend modeled on
`sutra-from-ts/`: source reader/parser → lowering rules → `.su`
emission → fixtures that compile end-to-end. Priority order
(Emma 2026-06-05):

1. **OCaml** — `sdk/sutra-from-ocaml/`. First: ML-family syntax +
   algebraic data types + pattern matching are the closest structural
   match to Sutra's axon/record model.
2. **Scala** — `sdk/sutra-from-scala/`.
3. **F#** — `sdk/sutra-from-fsharp/` (ML-family, close cousin of OCaml).
4. **Elixir / Erlang** — `sdk/sutra-from-erlang/` (the BEAM pair;
   immutable, message-passing — maps onto the axon IPC story).
5. **Clojure** — `sdk/sutra-from-clojure/` (Lisp; homoiconic, persistent
   data structures).
6. **Haskell** — `sdk/sutra-from-haskell/` (purest; laziness +
   typeclasses are the hardest edges — hence last in the functional set).

(The bullet list in Emma's original message garbled the last name —
"Oak Hamel" — ignore it; the authoritative order is the six above,
OCaml first.)

### Phase 2 — Rust

After the functional set: **Rust** (`sdk/sutra-from-rust/`). Emma's
read: Rust is the imperative language that translates *well*, because it
is expression-oriented, immutable-by-default, and has algebraic enums +
exhaustive matching — so it carries far more functional structure than C
or plain JS. Framing: Python and JavaScript are the "most basic /
supports a huge surface" baseline; Rust is the imperative language worth
doing properly because it maps cleanly. This is the general vision of the
imperative path.

### Phase 3 — WASM + the Neural Computers documentation

After Rust: **WASM**, tied to the replication work in
`../replicating-neural-computers-2` (the "Neural Computers" paper
replication, arXiv 2604.06425 — a learned runtime state unifying
compute/memory/IO; video models rolling out CLI/GUI screen frames from
instructions, pixels, and user actions).

**Integration plan (Emma 2026-06-05, explicitly authorized despite being
non-standard).** The DNC/NTM WebAssembly work in
`../replicating-neural-computers-2` is fundamental to Sutra's differentiable-
neural-computer / Neural-Turing-machine capabilities, but agentic
complications left it in a separate repo. Rather than keep it a submodule, we
**`git subtree` it into this repo under `WASM/`, preserving its full history** —
the history is worth keeping. A local hourly cron (`:33`) watches the sibling
repo and triggers the integration **once its agent has gone quiet for a full
hour** (no commit in 60 min = the agent that's actively working there has
finished its current pass). Before the subtree, any uncommitted changes in the
sibling are committed + pushed. After the subtree:
- the sibling's `todo.md` is prepended to the TOP of this `todo.md`;
- the sibling's `queue.md` is appended to the BOTTOM of this `queue.md`, under a
  "BARREL THROUGH" section whose steps are: (1) commit + push so the integrated
  subtree is canonical on origin; (2) systematically update ALL Sutra docs to
  incorporate the WASM/Neural-Computers work (website discipline applies); then
  the merged WASM queue items; (3) bottom item = work the merged WASM todo items.

This is intentional and Emma-directed — not best practice, done on purpose to
preserve the development history. See DEVLOG 2026-06-05.

**Refined 2026-06-06 (Emma — now ACTIVE in `queue.md`, not just cron-gated).**
The subtree is the **first thing in `queue.md`** (`## 🚀 ACTIVE #1`); the
document-and-merge pass is `## 🚀 ACTIVE #2`. Two sequencing changes vs. the
above: (a) the WASM repo's `queue.md` merges in directly **below the active
subtree items** (not appended to the very bottom of our queue); (b) the doc
pass is comprehensive ("everything that exists in that repo") and explicitly
precedes working the merged queue. The `:33` sibling-watch cron remains the
fallback trigger if the active item isn't executed locally first.

---

## [This year] Architectural diversification — Neural Turing Machine + reservoir computing (2026-06-01)

Emma's 2026-06-01 direction: widen Sutra's architectural surface beyond
RNN-recurrence (which Sutra keeps siding with for many purposes). Two
new architectures, very different maturity:

### RAM pointers → a programmable Neural Turing Machine (ACTIVE, decomposed into `queue.md`)

Spec: `planning/sutra-spec/ram-pointers.md`. Sutra gets pointers to
**RAM** (host memory, distinct from VRAM), accessed as an **I/O device**
via a modified `await`:

```sutra
number x = await ramRead(pointer);
ramWrite(pointer, data);
```

An **orchestrator** (host-side producer — the role `axon-io.md` left
open) bridges VRAM mailbox slots to host RAM: the program writes a
pointer to a request slot and spins the `await` heartbeat; the
orchestrator decodes the pointer, does the host RAM access, and writes
the value back into the response slot. `ramRead` reuses the
`await`→`Promise`→`while_loop` lowering (`promises.md`); `ramWrite`
formalises the output axon (`non-halting-loop.md`). End goal: a
*programmable* NTM that can later be **trained to achieve goals** — but
the first cut is hard (discrete) addressing; differentiable/soft
addressing is an explicit open question, not to be substituted in now.
Demo target: read text from RAM and display it, compared against the
substrate-RNN text-generation demo (same task, two architectures).
- **Core DONE 2026-06-01:** spec (`ram-pointers.md`), read+write runtime
  (orchestrator + RAM device; sequential-scan + pointer-chase reads +
  axon-mailbox write, all exact on the substrate;
  `experiments/ntm_ram/`, `test_ntm_ram.py` 6/6), and the pixel-lookup-vs-
  neural-font-render finding Emma named. See DEVLOG 2026-06-01.
- [ ] **`ramRead`/`ramWrite` surface syntax — BLOCKED on the async/await
  Stage-1 desugar.** Emma's surface is the inline `number x = await
  ramRead(pointer);` / `ramWrite(pointer, data);`. The mechanism (her
  method: orchestrator + VRAM axon-mailbox + tick loop) is built and works
  via the hand-wired harness; the inline-await *surface* needs the
  function split at the await point into tick-resumable continuations =
  the async Stage-1 desugar (`promises.md`; "Full async/await Stage-1
  desugar" below, only trivial shapes done). Build that first, then lower
  `ramRead`/`ramWrite` onto it. Do NOT substitute a non-inline surface or
  fake the continuation transform. Spec: `ram-pointers.md`
  § "Surface-syntax lowering". Follow-up open Q: a model-free
  hash-keyed-role axon to drop the mailbox's 768-dim key-embedding cost.
- **Differentiability — RESOLVED (Emma 2026-06-01): RAM is NOT
  differentiable.** I/O is outside the differentiable realm; a pointer
  between two cells rounds to the nearest discrete location (no soft
  attention). A trainable NTM trains its *controller* (the substrate
  program computing pointers / consuming values), not the discrete RAM
  access. Further RAM design work to scope here later: what training
  signal the controller / write-head needs to be trained end-to-end
  with RAM as a discrete I/O boundary; a model-free hash-keyed-role axon
  to drop the mailbox's 768-dim key-embedding cost; multi-cell payloads.

### Differentiable Neural Computer (DNC) — design exploration (Emma 2026-06-02)

The NTM's differentiable successor (Graves 2016): a neural controller +
a **differentiable** memory with content / allocation / temporal-link
**soft addressing**. Differentiability is the access *method* (soft
attention), not the store: the hard round-to-nearest `ramRead` method
isn't differentiable, but soft attention over a substrate matrix — or
over RAM contents read onto the substrate — is (Emma 2026-06-02). First
build is an on-substrate matrix (simplest); it's the natural showcase of
the constrain-train "every op trainable" vision. Defuzz stays smooth;
DNC components are just smoother.
Sutra is well-suited: content addressing = cosine+softmax+weighted-readout
(native substrate ops), the PyTorch codegen is autograd-differentiable,
and `recur` holds the memory/usage/link state. Full design + mechanism
mapping + open questions + a minimal copy-task first experiment:
`planning/exploratory/differentiable-neural-computer.md`.
**The actual goal (Emma 2026-06-02): isomorphism between DNC memory access
and written code.** A trained soft DNC policy should *defuzz* (β dial, the
smooth defuzz path) into a readable program over the hard ram-ops
(`ramRead`/`ramWrite` + content lookup + traversal), and back — the
weight→code vision specialized to memory access. Soft (trainable) and hard
(written) are the same op at two β. The doc's § "The point" has the
operation correspondence + the round-trip plan.
- [ ] First experiment: content-addressing-only copy-task DNC; train it,
  then defuzz and read off the addressing — does it land on the obvious
  sequential-`ramWrite`/`ramRead` program? Measure the soft→code recovery
  (the smallest DNC↔code-isomorphism evidence).

### Reservoir computing (DEFERRED to the OS era)

Emma: materially more complex; expected to land **with Yantra**, not
now. Do not start until the NTM direction is mature and Emma
re-greenlights. Placeholder so the roadmap records the intent.

---

## [This year] Formal verification — from framework to mechanical checks (2026-05-24)

Emma: put more FV work here. The framework + first clawRxiv paper exist
(`planning/sutra-spec/formal-verification.md`; `paper/formal-verification/paper.md`,
clawRxiv post 2613). We are at the *early* stage: the obligations are
*stated*, not yet *discharged mechanically*. Goal: build the bespoke
checker that turns the three obligation families into run-and-read checks,
smallest first, and keep the FV paper updated as each lands (CLAUDE.md §
FV-paper-sync). Off-the-shelf SMT solvers target Boolean/linear arithmetic,
not the polynomial obligations the compiled graph produces — hence bespoke.

**Spine: trusted base compiles to a tensor-op graph, so verification is
discharging a finite set of closed-form obligations over a small fixed set
of tensor graphs, not navigating control flow. Polynomial Kleene logic is
the lever that removes branch/path explosion.**

- **Kleene grid-exactness checker (first artifact, queued).** Evaluate each
  connective polynomial (`and`/`or`/`not`/t-norms) at the nine grid points
  {−1,0,+1}² and assert exact reproduction of the 3-valued Kleene table.
  Finite + decidable; anchors the smooth polynomial to the discrete logic.
- **[proposed] Promote the three measurement checks from prose to CI gates**
  (dimension / state-locus / signal-separation). Per the 2026-06-02
  substrate-leak retrospective
  (`planning/findings/2026-06-02-substrate-leak-and-claim-reality-retrospective.md`
  § S1): the breach class that cost the most weeks (C5, "dispatch
  cleanliness mistaken for sufficiency") has the *weakest* automation —
  only the dispatch leak-sweep is a hard gate; the other three are
  manual/cron prose checks. Targets: a dimension gate (zero `basis_vector`
  + large `runtime_dim` fails unless waived), a state-locus gate (any
  "RNN"/"recurrent" label needs a walk-N-steps-no-host-extraction test —
  `count.su`'s test is the template), a signal-separation gate (any
  classifier ships a measured `gap = min(pos)−max(neg)` table —
  `test_font_bound.py` is the template). **Needs gate-semantics design
  first** (which `.su` claim dim-minimality vs. tutorials that legitimately
  use the default; how to waive) — Emma's call before building, since it
  touches the substrate rails. Not auto-started.
- **Contract obligation (§3.1) — the genuinely-hard family. Two halves
  discharged, one open.** A program `p` with axon-typed contract `C` must:
  read only `C.read_roles`, write only `C.write_roles`, AND compute the
  role-to-role function `C` specifies. Status:
  - ✅ **Role-isolation (confinement) — DISCHARGED at the kernel (2026-05-24).**
    A process emits only on roles in its `write_roles` (capability-checked,
    else `CapabilityError`) and is delivered only axons on roles in its
    `read_roles`, no cross-role leakage. Mechanically tested in Yantra
    (`tests/test_kernel.py`: `test_fv_role_contract_read_isolation`,
    `test_send_refused_when_sender_lacks_write_role`,
    `test_send_to_unadmitted_role_is_black_hole`). This is the read/write
    *confinement* part only.
  - ✅ **Role-to-role function correctness — DISCHARGED for the Kleene
    fragment (2026-05-24, commit `133d9364`).** For a trusted program whose
    body is a Kleene-logic expression, "does the implementation compute the
    contract's specified function?" IS the equivalence procedure already
    built: `reduces_to_same_graph(implementation, contract_reference)` —
    decidable, exact, any depth. Demonstrated by
    `test_contract_function_correctness_kleene_fragment` (a NAND
    implementation passes its `!(a && b)` contract; a NOR implementation
    is correctly rejected). Honest scope: `echo` and `switch.su` are
    OUTSIDE the Kleene fragment and have their function-correctness
    covered by their own substrate tests, not by this procedure.
  - ❌ **Static `AXON_KEYS_READ`/`BOUND` soundness — OPEN, needs design.**
    (Re-added 2026-05-27 per Emma — explanation cron `b348c005` fires
    13:36 PST.) That the compiler's statically-emitted key sets match the
    keys the program actually touches at runtime (the lazy-delivery
    contract the kernel relies on). Needs runtime key-usage instrumentation,
    or a key-level contract in the manifest to check the static analysis
    against. Do NOT ship a vacuous check; settle the design in
    `planning/sutra-spec/formal-verification.md` first. Why it matters: if
    the static keys under-approximate, the lazy router could withhold an
    axon the program needs → silent wrong behaviour. Emma's leaning is to
    ship it with very good specifications inside the FV paper.
- **Branch-range obligation discharge.** ✅ DONE for the connectives,
  closed-form (2026-05-24). The polynomial-bounding routine — the core of the
  bespoke checker — is built (`sutra_compiler/fv_poly_bound.py`,
  corners+edge+interior critical points, exact sympy) and proves `&&`/`||`/`!`
  have exact range [−1,+1], cross-checked against the compiled substrate
  (`tests/test_fv_poly_obligation_checker.py`). **Remaining:** run the bounder
  on the *composed* polynomials of whole reduced programs (degree grows with
  branch-nesting; characterise the numerical cost there).
- **Termination obligation.** For a tail-recursive soft-halt loop, check the
  halt signal is monotone within bounded steps (§3.3) — far smaller than
  proving an arbitrary `while` terminates.
- **Graph-equivalence obligation.** Decide whether two programs compile to the
  same graph by algebraic comparison of the two graphs (not execution traversal);
  start from the simplifier/CSE passes already in the compiler.
- **End-to-end worked example.** Take one `.su` program → emit its compiled graph →
  mechanically check it against its published contract. The first real FV
  artifact (framework → demonstrated). Feeds a paper revision.
- **Tie to Yantra's trusted base.** The kernel roles + named critical
  programs are the in-scope surface (Yantra `paper/paper.md` §4); coordinate
  which programs get contracts first.

Honest scope (keep in the paper): covers the **non-AI** trusted base, per
contract — NOT whole-system closed-form, NOT anything riding on a learned
weight. The checker does not exist yet; that is the bulk of the work.

---

## First-class function values (2026-05-09)

Sutra's arrow functions today get hoisted to top-level `function`
declarations rather than passed as values (per the 2026-05-08 TS
transpiler note; see `sdk/sutra-from-ts/tests/fixtures/arrow_function/`).
That works for the TS lowering but blocks several language-level
features that need to pass behaviour as data:

- **Full async/await Stage-1 desugar.** The trivial shapes (pure
  return, thin wrapper) are shipped (queue.md item 1, phase 3 first
  cut). Anything richer — `vector v = await x; return g(v);`,
  multi-await chains, `try { await ... } catch { ... }` — needs to
  emit `.then(v -> g(v))` callbacks. With no first-class functions,
  the desugar would have to generate explicit named continuation
  functions and thread them through manually, which is doable but
  ugly and unidiomatic. Worth doing properly: lift first-class
  function values, then the desugar becomes a clean source-to-
  source rewrite.
- Higher-order list operations (`map`, `filter`, `reduce`) for the
  Sutra surface beyond what the TS transpiler erases.
- Callback-based event/observable APIs.

Likely difficult — every existing pass that walks function decls has
to learn that a function name can also appear in a value position.
The codegen needs to emit Python-level closures (or named-helper
indirection) for function-typed values. Type system needs a function-
arrow type. Best handled as its own focused session rather than
rolled into a feature work-stream.

When this lands, queue.md item 1 phase 3+ unblocks immediately.

---

## TS transpiler / Sutra postponed pieces (2026-05-08, sharpened 2026-05-10)

Three deferred dimensions of the TS → Sutra pipeline. The core
transpiler shipped 2026-05-08 with 12 fixtures green end-to-end
(TS source → `.su` → runnable Python). **After these three land,
JavaScript transpilation is feature-complete** — that is the
explicit closeout target Emma set 2026-05-10.

Working order (Emma 2026-05-10): interpolated lookup tables first,
then module imports, then the multi-program axon demo last.

- [x] **Interpolated lookup table for `Math.*` (transcendentals)** —
  shipped 2026-05-10. The actual fix turned out to be even simpler
  than the rotation-geometry retry hypothesis: the prior bound-table
  attempt was fundamentally pigeonhole-limited (N samples bundled
  into 2 scalars). The replacement architecture (length-N value
  tensor + triangle-weight soft-index dot product) avoids the
  pigeonhole entirely — see
  `planning/findings/2026-05-10-interpolated-lookup-table-works.md`.

  **What landed:**
  - `_VSA.exp` and `_VSA.log` on both PyTorch and numpy backends as
    substrate-pure intrinsics (every step is a tensor op: sub, abs,
    div, clamp, dot).
  - `_VSA.pow(x, y) = exp(y * log(x))` and `_VSA.sqrt(x) = exp(0.5 * log(x))`
    as beta-reductions to the two leaves.
  - `SutraMathOverflow` exception raised when input falls outside the
    precomputed table range (per Emma's "specific overflow exception,
    not silent zero" directive).
  - Tables: exp on [-10, 10] N=16384, log on [1e-3, 1e3] N=16384,
    trig on (-π, π] N=4096 (periodic so no overflow path). Float32
    runtime gives ~1e-5 relative precision; float64 study in the
    experiment hit ~1e-7.
  - `_TRANSCENDENTALS_DISABLED` is now the empty `frozenset()` —
    trig (sin/cos/tan) and hyperbolic (sinh/cosh/tanh) all
    landed via the same lookup architecture (trig with modulo
    reduction; hyperbolic via beta-reduction to exp). `Math.PI`,
    `Math.TAU`, `Math.E` round out the namespace.
  - TS `Math.*` calls now flow through end-to-end with no
    transpiler change (the codegen already routed `Math.foo(x)`
    to `_VSA.foo(x)`).

  **Follow-on, not blocking JS-completion:**
  - Range reduction for `log` (`ln(x) = ln(x/2^k) + k*ln(2)`) so
    inputs near 0 or beyond 1e3 stop being out-of-range overflows
    and start being domain-reducible to the bounded table.
  - Higher-order interpolation kernels if the linear-interp residual
    becomes a bottleneck for any real demo.

- [x] **`async` / `await` / `Promise`** — un-postponed 2026-05-09
  and substantially shipped. Active in `queue.md` item 1; the
  remaining work (full Stage-1 desugar) is blocked on first-class
  function values, listed at the top of this file.

- [x] **Module imports** (`import { X } from "./foo"`) — shipped
  2026-05-10. Confirmed Emma's intuition: same mechanism as
  stdlib. Implementation inlines imported declarations at the top
  of the importing file's lowered output, bracketed by `// ---
  begin module: <spec> ---` / `// --- end module ---` markers.
  Diamond imports dedup via visited set; circular imports
  terminate cleanly. Resolution tries `.ts`, `.tsx`, then `.su`.
  Raw `.su` imports inline verbatim. Fixture
  (`module_import/`) green for both lowering and end-to-end
  compilation. Spec doc updated:
  `docs/typescript-to-sutra.md` § Modules.

  **Follow-on, not blocking JS-completion:**
  - Tree-shaking — currently every declaration in an imported
    file inlines regardless of whether the import-clause names
    it. Cheap follow-on: prune dead inlined decls.
  - Namespace imports (`import * as ns from "./x"` then
    `ns.foo(…)`) — parses but inline-everything MVP doesn't
    track the namespace name.
  - Bare-specifier resolution (NPM packages) — only relative
    paths resolve today. Adding `node_modules/` lookup is the
    obvious next layer.

- [x] **Multi-program axon passing demo** — shipped 2026-05-10
  (`examples/multi_program_axon/`). End-to-end wire-passing
  between two separately-compiled `.su` modules works: 5-key axon
  serializes to a 3600-byte `.npy`, consumer decodes three keys
  with clear cosine margins over never-bundled decoys. Finding:
  `planning/findings/2026-05-10-multi-program-axon-passing-works.md`.

  **Lazy materialization is the next layer, not blocking
  JS-completion:** Today the full bundle crosses regardless of
  what the receiver reads. The 2026-05-10 demo's earlier 12-key
  draft hit the rotation-binding capacity wall on cat/dog
  disambiguation in nomic embedding space — that's the empirical
  motivation for the producer-side pruning pass. Implementation
  shape: walk the consumer's `axon_item` calls at compile time
  to collect the referenced-key set, rewrite the producer's
  `make_state` to skip `axon_add` calls for keys outside that
  set. Whole-program analysis across the cross-program boundary;
  natural follow-on when there's a concrete user (Yantra IPC,
  multi-program TS demos via the import system, real
  cross-process Sutra apps).

---

## [This year] Object encapsulation — language ergonomics

**Source:** Emma 2026-04-30 (during the loop-tail-call-surface work).
**Steps 0, 0.5, 1, 2 (partial), 3 (no-op), 4, 6 (partial) shipped 2026-05-01.**

The rule: free (non-object) functions read file-scope; object
methods (static or non-static) do not. The validator emits
**SUT0144** on any method body that reads a file-scope name.
Class bodies accept method declarations (regular, static,
intrinsic, static-intrinsic) and loop function declarations.
Static methods compile via mangled wrappers; non-static methods
take `this` as their first param; class loop functions emit as
`_loop_{Class}_{name}`. `Class.method(...)` and
`loop Class.name(...)` both dispatch correctly. The
stdlib_loader picks up class-bodied static methods alongside
top-level FunctionDecls.

Per Emma's 2026-05-01 correction: there is no closure in Sutra
— what the design calls "closure" is namespace-access scoping
(free functions read file-level names through Python's natural
emission, methods see only their class). The "free-function
file-level closure" step is therefore a no-op.

See `planning/open-questions/function-taxonomy-and-closure.md`
for the full taxonomy.

Remaining work:

- [ ] **Migrate the four remaining stdlib files** to class-as-namespace
  shape: `logic.su`, `similarity.su`, `vectors.su`, `rotation.su`.
  Their bodies use the `loop (10)` form which still works but
  needs a careful check that the inliner still expands them
  correctly inside class bodies (it does, per the 2026-05-01
  inliner extension).
- [ ] **Field declarations inside class bodies** (`field x : int;`).
  Without fields there's no per-class state for non-static methods
  to encapsulate, and step 5 (class-level slots) has no referent.
- [ ] **Non-static object loops with `this` threading.** Today
  class loops are effectively static — the cell function takes
  only the declared state params. Per Emma's design, non-static
  loops should pass `this` through each iteration so the loop
  walks the same instance. Implementation: insert `this` as an
  implicit additional state parameter on non-static class loops.
- [ ] **Instance-syntax dispatch on typed variables** (`g.method(args)`
  for `Greeter g`). Needs variable type tracking through the
  codegen.

## [This year] GUI — long-horizon (early-adoption surface)

The GUI block shipped 2026-06-11 (Emma's top priority): `demos/gui/` whole-frame renders
(glow / moving glow / substrate-RNN animation / ring / click→substrate-state), the
`hadamard` elementwise/buffer primitive, and the human-facing `docs/gui.md` page ("Drawing
pixels"). Emma's framing: GUI is a much stronger early-adoption surface than earlier
assumed — a window of substrate-computed pixels is the most legible "Sutra runs and you can
see it" demo. Long-horizon extensions (autonomous, as the loop reaches them):

- [ ] Simple multi-widget **layout** — compose several whole-frame widgets into regions.
- [ ] **Colour / RGB** frames (three channels interleaved) and more shapes/gradients.
- [ ] A real **window event loop** (live clicks/animation, not just per-frame render calls).
- [ ] **Learned decoder / arbitrary-image generation** — a trained nonlinear decoder from a
  latent to an arbitrary frame (the constrain-train "every op trainable" vision meets GUI);
  the analytic whole-frame render is the fixed-weight base case.
- [ ] **Yantra GUI integration** — the window living in the orchestrator, per the Yantra OS.

HARD RAILS (same as all substrate work, CLAUDE.md): every pixel on the substrate; no host
math in the op; stateful widgets are substrate-RNNs (state a vector across ticks, not a host
shuttle); verify the rendered frame against a reference, measured.

---

## [This year] Make `sutralang.dev` more agent-accessible

Sutra's stance per CLAUDE.md is that agents are first-class consumers
of the documentation, not an afterthought. The site is already
markdown-driven, but specific moves to take it further:

- [ ] Expose the docs through an MCP server (or a documented
  fetch-this-URL pattern) so agents can query Sutra's surface
  programmatically rather than scraping HTML.

---

## [This year] Rotation-hashmap capacity + Monte-Carlo exploration

The rotation-hashmap library-pattern prototype landed 2026-04-22
(5/5 exact-lookup on nomic; `examples/_rotation_hashmap_test.py`).
Two follow-ups flagged during that work:

- [ ] **Cross-substrate attractor comparison.** Follow-on to the
  2026-04-22 single-substrate result. Train separate MLPs on
  nomic, mxbai, and minilm codebooks. Compare: does v0 land in
  queen's basin on nomic only, or does the MLP "rescue" queen on
  the weaker substrates too? The cross-substrate sweep
  (`_king_queen_multi_substrate.py`) showed mxbai and minilm fail
  naive analogy — the interesting question is whether attractor
  dynamics can recover the right answer anyway.

- [ ] **Larger-codebook attractor.** 14 words is proof-of-mechanism.
  Scaling to thousands of codebook entries (a real concept-memory
  for a working agent-style program) is the next scaling step.
  Capacity characterization as a function of codebook size +
  MLP size would land alongside.

- [ ] **Attractor-MLP as a Sutra language builtin.** Currently the
  attractor is only accessible from Python. A language-level
  declaration like `attractor M = learn_attractor(codebook);`
  with a matching iteration op would let `.su` programs use
  attractor dynamics natively. Sequence after learned-matrix
  binding lands (which uses related machinery — fit a matrix at
  compile time).

## [This year] Per-program embedding-space override

User direction 2026-04-22: *"programmes should be able to have their
native embedding space [declared] at the beginning of them as an
override thing so that we could have a bunch of different test
programmes that show it in different vector spaces."*

Current state: `NumpyCodegen.__init__` already accepts `llm_model=...`
as a kwarg, but there's no source-level way to set it — the codegen is
invoked with default args by `examples/_smoke_test.py`.

Minimum scope:
- [ ] Source-level declaration (not a comment) — a `embedding_space`
  pragma the parser recognizes. Decide after seeing how the magic-
  comment version is used in practice.

## [This year] `main(embedding_space: string)` compile-time override

User direction 2026-04-23: *"the runtime override, honestly, it
wouldn't be at runtime; it would be at compile time"* and *"both of
those things go after the anthropic application."* Moved from
queue.md (where it was erroneously framed as runtime override) to
this post-Anthropic-grant-app bucket.

File-level (`// @embedding`) and project-level (`atman.toml`
`[project.embedding]`) declarations landed 2026-04-22. What remains
is the third layer — a `.su`-language-level way to set the
embedding substrate from inside source code itself, so a test
program can declare its own substrate without a harness-level hint.

Scope:
- [ ] Pick the source-level syntax. Candidates: a
  `main(embedding_space: string)` signature that the compiler reads
  at compile time (NOT passed as a runtime arg — the codegen bakes
  it into the `_NumpyVSA` constructor); or an explicit
  `embedding_space "nomic-embed-text";` pragma at the top of the
  file. Either way the substrate resolves before any `embed()` call
  is compiled, so no runtime lazy-init.
- [ ] Wire the chosen syntax into the parser and have
  `NumpyCodegen.__init__` accept the resolved model.
- [ ] Make sure file-level and project-level declarations still
  override correctly when the source-level form is also present.
  Precedence order is source > file > project > compiler default.

## [This year] Concurrency — only the cases that need explicit handling

User direction 2026-04-22 (afternoon): concurrency is implicit by
default in Sutra because the language's functional algebraic nature
already gives the compiler license to evaluate independent sub-
expressions in parallel via formula simplification. **An explicit
syntax is only needed for the cases where the compiler can't derive
the parallelism algebraically**.

The shapes that still need explicit handling:

- [ ] **Concurrent looping.** Each declared loop function
  (`do_while` / `while_loop` / `iterative_loop` / `foreach_loop`)
  is a single trajectory today. A concurrent form would run N
  independent trajectories in parallel — same cell, different
  initial states, collected as a basin distribution. Surface
  syntax TBD; probably an extension of the existing call form
  (e.g. `loop[N] NAME(...)` for N parallel runs) given the
  user's "implicit except where needed" framing.

- [ ] **MLP attractor search.** N independent trajectories through
  an attractor MLP, each from `v0 + noise[i]`, each iterated until
  its fixed point, collected as a basin distribution. This is the
  first-class concrete use case driving the concurrency work (see
  `planning/findings/2026-04-22-mlp-attractor-king-queen-nomic.md`).
  Currently hand-rolled in Python; the pre-grant-app work lets the
  language express it natively.

Deferred sub-questions (from the original 2026-04-14/15 open-
question doc; the user has not expressed a position on these and
they don't block the two shapes above):

- Convergence test formula — cosine threshold? snap identity?
  Both-finished as a fallback?
- Timing mismatch — return-fast-cancel-slow vs. wait-both.
- External concurrency (parallel Ollama calls) — probably just
  compiler-does-it given the "implicit by default" framing, but
  I/O error modes may force a more explicit treatment.

Source-of-truth for the design: `planning/sutra-spec/concurrency.md`
(implicit-by-default, with explicit as fallback).
`planning/open-questions/concurrency-and-monads.md` (monad framing
was considered and demoted).

## [This year] Learned-matrix binding

Deferred from the 2026-04-22 rotation-binding pass. The feature is
genuinely useful (see `feedback_learned_matrix_is_not_next.md`) — it's
simply not the next active item. When picked up:

- [ ] Add a matrix-fitting step at compile time. A `role X =
  learned_from(data)` declaration reads `(input, output)` embedding
  pairs and fits R via lstsq (or Procrustes, or low-rank —
  substrate-dependent).
- [ ] Wire the `role` surface syntax into the parser. queue.md item
  3's decision (Candidate B: `role` / `var`) is resolved at the spec
  level but not implemented in `sdk/sutra-compiler/`.
- [ ] Emit `R @ filler` runtime for semantic roles; `R.T @ record`
  for unbind (or precomputed pinv for non-orthogonal R).
- [ ] A new demo that exercises learned-matrix bind end-to-end (e.g.
  a `located_in_country` program using cartography-style displacement
  data).

## [This year] Extended state vector — remaining integration

The runtime-primitive half of the extended-state / synthetic-subspace
design landed 2026-04-24 (`planning/findings/2026-04-24-slot-rotation-
runtime.md`). `_VSA` now exposes `slot_store` / `slot_load` /
`rotate_slot` — 48 disjoint 2D-Givens slots in the synthetic block,
exact reversibility, zero semantic drift. All 4 reversibility tests
PASS on the compiled runtime.

What this pass closed:
- [ ] Compile-time slot allocator — map named variables to slot
  indices deterministically, with a compile-error when capacity
  (48 slots per program at synthetic_dim=100) is exceeded. Lands
  alongside the slot codegen integration (see "Compilation updates"
  below).

## [This year] Compilation updates

Compiler-side integration for primitives that already landed at the
runtime / surface-syntax level. The egglog post-pass and slot
rotation runtime both shipped 2026-04-24/25; what remains here is
the codegen work that turns those primitives into things `.su`
programs can rely on without explicit harness intervention.

### Egglog — linearity analysis codegen

The egglog rules already do the algebra (matrix-chain fusion via
`R @ S` associativity + apply distribution + cost model preferring
fused chains). The remaining work is **codegen integration**:
function bodies that are pure linear tensor-op compositions get a
single cached matrix `M` and compile down to `M @ arg`.

- [ ] Detect when a function body's egglog form is a single
  `(M_n @ ... @ M_1)` composed-matrix expression.
- [ ] Extend the lift/lower bridge in
  `sdk/sutra-compiler/sutra_compiler/simplify_egglog.py` to handle
  matrix-compose forms.
- [ ] Emit `M = M_n @ ... @ M_1` at module init; replace the call
  site with one matrix-vector op.

Sub-200 lines of compiler work. This is the pass that makes the
global-efficiency story (every linear function compiles to one
cached matrix) actually realize.

### Egglog — CSE pass

Falls out of equality saturation when the cost model charges per-use
rather than per-node. Implementation is mostly in the lower step.

- [ ] Adjust the cost model in `simplify_egglog.py` to charge
  per-use.
- [ ] Emit Python `let`-bindings (a temporary variable) for any
  subexpression that appears more than once in the extracted form,
  instead of inlining.

Adjacent prior art: JuliaSymbolics hash consing reports 3.2× speedup
+ 5× faster codegen on similar workloads.

### Slot codegen integration

Surface syntax landed 2026-04-25 — `slot TYPE name [= expr];`
parses, validates, and IDE-highlights. The codegen rejects with
SUT0150 ("slot declaration is parsed but the codegen integration
... isn't wired yet"), so user programs fail fast with a clear
message. Roughly 200 lines of compiler work to finish.

- [ ] Per-scope state vector that holds slot contents.
- [ ] Transform slot-name reads to `slot_load` calls at codegen
  time.
- [ ] Transform slot-name writes to `slot_store` (then reassign the
  state vector).
- [ ] Wire the compile-time slot allocator (deterministic
  name → index map; 48-slot capacity check at synthetic_dim=100).

Once this lands, `examples/imperative_reversible.su` can be
rewritten using natural `x = a; x = b; x = a;` assignment syntax
instead of the explicit harness it uses today.

## [This year] Monotonicity of fuzzy logic polynomials

The current AND/OR polynomials are Lagrange-interpolated on the
three-valued grid `{-1, 0, +1}²`. Exact at grid corners, smooth
everywhere, but **non-monotonic between grid points.** Concrete
example: `AND(a, 0)` as a function of `a` peaks at `a = 0.5`
(value 0.125) and drops back to 0 at `a = 1`. Derivative
`(1 + b − 2a + 2ab²)/2` is negative for `a > 0.5` when `b ≈ 0`.

Fuzzy logic does not strictly require monotonicity, but preferring
it would make the operators behave less surprisingly on off-grid
inputs.

Options to restore monotonicity:

- **Use `minimum` / `maximum` primitives directly.** `np.minimum`
  and `torch.minimum` are vectorized tensor ops — monotonic and
  exact on the grid. Tradeoff: kink at `a = b` (non-smooth there;
  differentiable almost everywhere via subgradients).
- **Higher-degree polynomial.** Some degree-6 or higher polynomial
  might be both exact on the grid and monotonic. Hasn't been
  explored; likely more expensive.
- **Softened min/max** (Einstein t-norm, Yager family, soft-min
  with temperature). Smooth + monotonic but loses exactness at
  the grid corners.

User preference (2026-04-24): prefers more monotonic than current,
not essential. Parked here rather than switched immediately.

## [This year] Language-design open questions

Not blocking the active work; grouped because they are of a piece.

- Anonymous functions (leaning toward `lambda` keyword).
- How primitive substrate operations read in source.
- Declaration syntax for implicit conversions.
- Lightweight role-annotation system for semantic roles.
- Expression-vs-statement bias.
- Access modifiers beyond public/static defaults.
- Half-compilation / immediate-execution model.
- `hop` non-algebraic function.
- IO — how Sutra handles input/output.
- Softmax-over-switch vs. if/elif chains —
  `planning/exploratory/softmax-conditionals.md`.
- **`^` (exponent) as a Sutra operator** (declared 2026-04-29 from
  the transcendentals chat). Not a function call (`pow(x, y)`),
  not a derived form — a first-class infix operator on the number
  axis. User reasoning: "there are no bits in Sutra," so `^` is a
  numeric primitive, not a bitwise XOR (which is what `^` means
  in C/Python). When implementation lands: lexer needs `^` token,
  parser needs an infix-binary production at the appropriate
  precedence (above `*`, right-associative is the math convention),
  codegen routes through whatever exponentiation tier the math-
  approximation work picks (Chebyshev for non-integer exponents,
  potentially the rotation-based path from the transcendentals
  chat for the trig family). Source-of-truth for the algorithm:
  the §"Transcendental functions — design absorbed from voice
  chat" section at the bottom of this file.

## [This year] Make loops idiomatic

The 2026-04-30 loop redesign (`planning/open-questions/loop-function-declarations.md`)
ships loops as first-class declared functions with `pass` for tail-recursive
yield and `loop name(args)` call sites that mutate caller variables by
reference. Emma 2026-04-30: "this is a bit of a weird thing... it's
unidiomatic... I'm probably going to figure out a nicer way to represent
this at some point. I'm not going to be able to do this right now though...
my priority is making it work."

So: ship the by-reference form first (substrate-pure RNN cell, body
actually runs, completion flag propagates), then later this year revisit
to make it idiomatic. Likely cleanup direction: loop calls return a
tuple of state values that the caller assigns explicitly, eliminating
the by-reference surprise:

```sutra
x = loop addNumber(x < 11, x);          // single-state return
(max, count) = loop findMax(arr, 0, 0); // multi-state return
```

Don't touch this until the function-declaration form has shipped and a
few real programs have exercised it — premature cleanup risks designing
the wrong thing.

## [This year] Docs / website

- [ ] **Website visual remake to fully match the shared identity
  (website-only — never the language/math/substrate).** Emma's
  standing complaint: the site is well-structured (keep the structure,
  the Material GitHub repo widget, and search — she likes all three)
  but it looks ugly/outdated next to emmaleonhart.com and the sister
  sites. 2026-05-16 shipped a chrome restyle in
  `docs/stylesheets/identity.css` (dark Lacquer header/tabs, the
  shared Loka-feel `.md-button`, grid cards, admonitions, header
  element re-order: search one side, light/dark toggle next to the
  GitHub widget). Still to do for a true match: tighten spacing/typography
  to the emmaleonhart.com feel, a proper landing-hero treatment, and
  port Sutra's *better* Material GitHub repo widget back onto the
  other sister sites (Emma prefers it to the small `.gh` pill they
  use). Treat as iterative; never block on it, never touch claims.

- [ ] **Expand `docs/paradigms.md` once more is built.** The page was
  shrunk on 2026-04-27 to a single Java contrast (assignment, loops,
  classes) plus the no-memory-points / non-locality core. The earlier
  version had Haskell, Prolog, C, and Curry/Mercury sections that ran
  ahead of what the language can actually demonstrate. Once we have
  more substantive working programs (real class bodies post-ontology
  work, working learned-matrix binding examples, more
  cross-language-flavor demos that compile and run), revisit the page
  and add back whichever comparisons are now backed by code that
  actually executes — not aspirational prose. Do not restore the old
  text wholesale; rewrite from current ground truth.

- [ ] Interactive pipeline viewer: paste `.su` source, see the AST,
  the simplified AST, the emitted Python, and the expanded polynomial
  form of any expression, side-by-side with rewrite highlights. Same
  stylistic template as the existing widgets (`graph-to-vector`,
  `bind-unbind`, `snap-to-nearest`, `fuzzy-logic`). Lives on
  `docs/interactive/` when built.

- [ ] **Standing rule: keep internal-scratchpad references off the
  public website.** The website pages (`docs/*.md`, rendered to
  `sutra.emmaleonhart.com`) must not mention repo-internal files —
  `queue.md`, `todo.md`, `planning/...`, `DEVLOG.md`, or deep
  `sdk/...` paths — nor inline author/date dev-notes ("Emma 2026-04-30
  hunch", "(2026-05-09)") or quoted chat lines. A 2026-05-23 sweep
  cleared the current set; this is the discipline for every future doc
  edit, not a one-time cleanup. Related: do **not** reintroduce the
  deprecated numpy backend (`codegen.py`) anywhere on the website —
  the canonical (and only website-mentioned) compile target is
  `codegen_pytorch.py`. The numpy mention was removed from
  `compilation.md` on 2026-05-23 because framing it as "legacy"
  overstated it; the website simply doesn't discuss it.

- [ ] **Make the website clearer about what Sutra actually does.** The
  system is genuinely complicated and the paper is dense; the site
  should carry an accessible, concrete account of the real mechanics
  (not just the pitch) so a reader who will never wade through the
  paper still leaves understanding what is being built and how it
  works. Iterative; never overstate beyond what runs.

- [ ] **(Uncertain — Emma not committed yet) JavaScript / TypeScript
  tutorials on the site.** TS-shaped source is Sutra's front door, so
  a "here is your JS/TS program, here is the same thing as Sutra"
  tutorial track could land well for newcomers. Emma flagged it as a
  good-thing-to-include but is not 100% sure about it (2026-05-23);
  scope and validate the angle before committing.

## [This year] Smoke-test substrate-margin notes

The smoke test (`examples/_smoke_test.py`) reports overall PASS as of
2026-05-01. Two soft notes worth keeping:

- **`fuzzy_dispatch.su` lands 2/4 dispatches.** The dispatch
  mechanism itself (soft-mux on Lagrange-fuzzy AND/NOT scores) is
  correct; nomic-embed-text places "weather"/"music" and
  "cancel"/"alarm" on adjacent prototype clusters, so the
  argmax_cosine resolves the wrong neighbor. Test relaxed to require
  ≥ 2/4 (`run_fuzzy_dispatch` line ~256). A better-separated
  substrate or a manually-tuned prototype set would push this to
  4/4 without compiler changes — the demo isn't broken, the
  embedding geometry is the limit.
- **`sequence.su` self-similarity** previously failed an
  unrealistically tight `(0, 0.5)` window for `sim(fox, dog)`; the
  test now reports `sim(fox,dog)=+0.827` and asserts only "cross <
  self," which holds.

## [This year] Sutra-NumPy: a substrate-native numerical library

User direction 2026-04-29: build Sutra's equivalent of NumPy — a
numerical library whose primitives compile to substrate operations
(rotations, eigenrotations, matmul, lookup tables, Chebyshev
polynomials) instead of libm / BLAS calls. **Explicitly NOT in the
initial MVP.** This is later-this-year scope; the MVP keeps the
existing math intrinsics as stubs (per the math-approximation
section below) and the language-correctness work stays the focus.

The umbrella covers what's already broken out below as separate
entries plus what isn't yet broken out:

- **Already tracked**: compile-time math approximation tiers
  (Chebyshev / lookup / CORDIC — see next section), `[backend]`
  dtype configuration, eigenrotation-as-trig (de-prioritized
  architectural-uniformity refactor — see findings 2026-04-28).
- **Not yet broken out** (umbrella scope to add later):
  substrate-native linear algebra primitives (matmul, decomp,
  pinv) routed through the rotation/Givens machinery where
  possible, rather than calling torch.linalg directly. Random
  number generation. Statistics primitives. Array-creation /
  slicing / broadcasting as first-class language constructs.

The pitch: when Sutra is doing math, it should be doing math on
its own substrate, not bouncing out to torch's host-side numerical
stack. The architectural-uniformity argument from the
eigenrotation finding (2026-04-28) generalizes — uniform substrate
operations enable global-efficiency fusion in a way that
host-side calls never can. The cost-per-op story is mixed (see
that finding); the *whole-program-fusion* story is the actual win.

This entry exists so the broader vision is captured without
expanding the MVP. When the MVP lands and the focus shifts here,
the per-piece work below will get re-organized under this
umbrella. Until then, treat the per-piece entries as the active
slice.

## [This year] Compile-time math function approximation

User direction (2026-04-25): "Make a math library and some
compilation wizardry." The Kolmogorov–Arnold angle says any
continuous function decomposes into univariates, which can be
approximated as tensor ops on a bounded domain. Sutra should
compile `log`, `sqrt`, `sin`, `exp`, etc. to tensor expressions at
compile time rather than calling out to libm at runtime. See
`docs/numeric-math.md` § "Transcendental functions" for the
design.

User direction (2026-05-01): the unlock is **natural log + exp(E)**.
If we get a reliable, substrate-pure way to represent those two,
everything else cascades — `Pow(a, b) = exp(a * log(b))` makes `^`
work, and the rest of the transcendental family composes from
there. Lookup-table approach was attempted and didn't pencil out
(see `planning/findings/2026-04-29-bound-table-capacity-limit.md`);
worth retrying with a different shape. The principle: every
non-recursive function beta-reduces to its components, so once the
two leaves work, the chain is done.

Pieces below are sub-pieces of the broader Sutra-NumPy umbrella
above; tracked separately because they're the active slice.

Concrete work:

- [ ] **Add `[math]` section to `atman.toml`** with
  `approximation_precision` (target abs error) and
  `approximation_method` (`"chebyshev"` / `"lookup"` /
  `"cordic"`). Parse it in `sdk/sutra-compiler/sutra_compiler/
  workspace.py` (or wherever atman.toml is read).
- [ ] **`stdlib/math.su` math intrinsics** (`log`, `sqrt`, `exp`,
  `sin`, `cos`, `tan`, `pow`). 2026-04-29 implementation was
  withdrawn 2026-04-30 because it ran as host Python scalar
  arithmetic at runtime (substrate-purity violation; values were
  correct but architecture wrong). Codegen now rejects calls
  with a clear CodegenNotSupported pointing at math.su. Future
  direction: eigenrotation-as-modulus (Emma 2026-04-30 hunch —
  the unit circle is naturally periodic so applying R unboundedly
  could give substrate-pure trig without floor-based range
  reduction). Re-implementation needs a real design first;
  belongs in `planning/open-questions/` when picked up.
- [ ] **Bounded-domain inference.** For the polynomial-tier path
  to work the compiler needs to know `x ∈ [a, b]`. Either via
  type annotations (e.g. `bounded<scalar, 0.01, 10> x`), via
  static analysis on simple cases, or via runtime guard +
  fallback. Pick a path; type annotation is the most consistent
  with the rest of the language.
- [ ] **Precision-vs-speed test corpus.** Three programs at
  three precisions (1e-3, 1e-6, 1e-12); show the polynomial
  degree shifts and the result still matches. This is the
  audit-friendly story for finance use cases.
- [ ] **Eigenrotation as a substrate-uniformity refactor for trig
  intrinsics** (de-prioritized 2026-04-28 after validation).
  User insight 2026-04-28: rotation matrices contain sin/cos as
  their entries by definition, so `sin(x)` = "build R(x), apply
  to (1,0), read y-coordinate." Exploratory writeup:
  `planning/exploratory/eigenrotation-for-sine-and-modulus.md`.
  Validated 2026-04-28 in
  `planning/findings/2026-04-28-eigenrotation-as-trig-validation.md`
  via `experiments/eigenrotation_as_trig.py`:
  - Math identity holds (trivially).
  - "Modulus for free" is real but inherited from libm's range
    reduction — not a Sutra-specific differentiator.
  - **Cost-saving claim REFUTED.** Rotation path is 1.41× scalar
    direct trig and 99× vectorized direct trig on numpy CPU. The
    rotation builder calls *both* `cos` and `sin` to fill R, then
    adds a 2×2 matvec — strictly more work, not less.
  - Surviving Sutra-specific value is architectural only: one
    runtime code path instead of two (substrate-uniformity for
    trig). Not a speed win.
  - Cost-win story would only materialize on hardware rotation
    primitives (CORDIC / FPGA / future native instructions),
    which is not where Sutra runs today.

  Implication: this is a "nice cleanup if/when we touch the
  math-tier code" item, NOT a priority feature. It does not
  justify prioritizing it ahead of the Chebyshev / lookup /
  CORDIC tiers above. Kept in the queue so we don't re-derive
  the insight; not a near-term work item.

## [This year] `atman.toml` backend / dtype configuration

Companion to the math-approximation work. Today `atman.toml` only
carries `[project.embedding]`. Per the Kolmogorov chat (2026-04-25):

```toml
[backend]
target = "cuda"               # or "cpu", "metal", "tpu"
dtype = "float16"             # or "float32", "bfloat16"
mixed_precision = true

[pytorch]
compile = true                # torch.compile
```

Dtype is the more interesting half — float16 vs float32 vs
bfloat16 changes both throughput and what the compiled tensor's
precision contract actually realizes. Right now the codegen hard-
codes float64 for the numpy backend; the pytorch backend picks at
init. Letting projects set this per-program closes the precision-
contract story.

Concrete work:

- [ ] Extend `atman.toml` schema with `[backend]` (target, dtype,
  mixed_precision) and `[pytorch]` (compile, etc.).
- [ ] Plumb the dtype through `codegen_pytorch.py` so `_VSA.dim`
  and the tensor allocations honor it.
- [ ] Document the interaction with `[math]` precision — a
  1e-12 precision target on float16 storage is incoherent; the
  compiler should warn or escalate dtype.

## [This year] Ontology — make the class system real

User reflection (2026-04-25): "We have the ontology somewhat, but
I don't think we've really implemented classes that much, even
though we should be implementing classes, or ontology. […]
Defining classes is going to be a relatively late thing for us
to do in this, once we've more or less done a large amount of
other stuff."

Sutra calls its type system an *ontology* deliberately — both
because it's a knowledge-representation framing (OWL/RDF sense),
because it communicates "rules of how to use things" rather than
proof-theoretic structure, and because the user is a philosopher
and the framing fits. See `docs/ontology.md` for the existing
exposition.

**Audited state of the ontology / class / function surface
(2026-04-25):**

- **Functions** — fully working. `function T name(T arg) { … }`
  parses, validates, codegens, runs. Used in nearly every `.su`
  example.
- **Methods** — parsed (`MethodDecl` AST node, `method` keyword
  in lexer). **Rejected at codegen** with "method declarations
  are not supported by the V1 codegen." Surface syntax
  exists; no method ever actually runs. `examples/uncertain/01-
  objects-and-methods.su` shows the intended shape and explicitly
  fails to run.
- **Generics** — same shape. `function T Identity<T>(T value)`
  parses, codegen rejects with "generic function declarations
  are not supported by the V1 codegen."
- **`class Foo extends Bar { }` declaration form** —
  ✅ MVP landed 2026-04-25. Empty bodies, single inheritance,
  parent-chain must bottom out at a primitive. See
  `docs/ontology.md` § "MVP declaration form" and
  `examples/classes_demo.su`. Diagnostic codes SUT0140
  (non-empty body), SUT0141 (duplicate), SUT0142 (extends
  unknown).
- **Inheritance / operator overloading on user classes** — not
  at all. Operators are defined on primitive classes only, in
  `codegen.py` / `codegen_pytorch.py`.

`docs/ontology.md` now describes both the intended end-state and
the MVP landing point. The compiler-recognized "ontology" today
is: the primitive hierarchy (vector / int / float / complex /
fuzzy / trit / bool / char / string), user-declared empty-body
classes that bottom out at a primitive, plus user-named
identifiers in type positions that the validator tolerates but
the codegen treats as plain vectors.

Concrete things still missing — the next layer above the MVP:

- [ ] **Class bodies that aren't empty.** Field declarations
  (storage layout — which axes the class uses), method
  declarations, operator implementations. Each is rejected by
  the parser today (SUT0140 for non-empty bodies). The MVP
  empty-body form is the wedge; this entry is the actual
  ergonomics.
- [ ] **Instance constructors / instantiation.** Today a `Cat`
  is just a vector — there's no `new Cat(...)` form, no
  constructor body, no per-class layout. The user's framing:
  "objects don't even show up as a non-implemented stub." That
  gap is real.
- [ ] **Operator implementations on a class.** A class body
  defining `+`, `-`, `*`, etc. that subclasses inherit or
  override. This is the path that makes `Dollar + Dollar` work
  but `Dollar + Euro` fail — the F# units-of-measure
  replacement story.
- [ ] **Inheritance chains that the type checker walks at
  operator dispatch.** Today the validator tracks the chain
  for diagnostic purposes only; the codegen still treats the
  value as the primitive root. A real chain that the compiler
  uses to resolve `(Dollar)x + (Dollar)y` to a Dollar-typed
  result requires per-class operator tables.
- [ ] **Method dispatch on user-defined classes.** Drop the
  current SUT-style rejection and actually wire it through.
- [ ] **Generic functions and classes.** Drop the current
  "generic declarations not supported" rejection.

When these land, the natural follow-on demos are:

- A `Currency` base class in the stdlib whose subclasses
  (Dollar, Yen, etc.) inherit "addable to same currency only"
  semantics. The Kolmogorov-Arnold chat (2026-04-25) sketched
  this as the F# units-of-measure replacement story; it's the
  canonical demo of the ontology working end-to-end.
- Re-examine `codegen-v1-feature-coverage.md` in
  `planning/open-questions/` — that doc tracks the V1-codegen-
  rejects-this-construct list, and most of those rejections
  trace back to this gap.

This is **deferred — not because it's unimportant, but because
it's hard and most other Sutra work doesn't depend on it.** The
math-approximation work and the egglog migration both proceed
without the ontology layer being filled in. When the ontology
work happens, the natural follow-on items are:

- A `Currency` base in the stdlib whose subclasses (Dollar, Yen,
  etc.) inherit "addable to same currency only" semantics. The
  Kolmogorov-Arnold chat (2026-04-25) sketched this as the F#
  units-of-measure replacement story; it's the canonical demo of
  the ontology working. Originally captured here as a "[This year]
  Currency stdlib base class" item; merged into this entry because
  it depends on real class-declaration support landing first.
- Re-examine `codegen-v1-feature-coverage.md` in
  `planning/open-questions/` — that doc tracks the V1-codegen-
  rejects-this-construct list, and most of those rejections trace
  back to the ontology gap.

## [This year] Tooling

- [ ] Diagnose why `sdk/intellij-sutra/editor.bat` fails (likely JAVA_HOME or Gradle daemon
  issue). Get `sdk/intellij-sutra` `runIde` task working, verify `.su`
  syntax highlighting and completion in the sandbox IDE.
- [ ] Build `sutra_ffi.dll` so `tests/test_sutradb_embedded.py` stops
  raising `FileNotFoundError`. Local fix: `cd sutraDB && cargo build
  --release -p sutra-ffi`. All 245+ other tests pass without it; not
  paper-blocking, fix when convenient.
- [ ] **Class system as autocomplete recommendation, not enforcement.**
  Originally surfaced in the project-genesis chat: the
  implicit class system in Sutra is meant to *suggest* meaningful ways
  to bind / unbind / bundle / unbundle / permute, not enforce them.
  Violating a class still produces a vector — possibly noise, possibly
  accidentally meaningful — and the language doesn't error. The IDE
  / MCP layer should surface class-coherent operations as autocomplete
  options ranked by ontological fit, while leaving off-class
  combinations callable with no warning. Pairs with the recognition-
  layer / ontology-detector idea: completion quality is bounded by
  how well the recognizer identifies what region of semantic space a
  vector occupies.

## [This year] Future Goals

- **Pick the multi-option `select` firing threshold.** Single-option
  `select` has a 0.5 default with a clean justification (softmax-of-one-
  vs-not is a probability distribution, and 0.5 is its natural decision
  boundary — see §26 "Single-option `select`"). For a `select` over
  k > 1 options the equivalent rule is unresolved. Candidates: winning
  weight exceeds `1/k + δ`; winning weight exceeds runner-up by a
  margin; absolute threshold (no clean softmax justification at k > 1);
  or no firing threshold at all (downstream consumers decide). Decision
  needs a multi-option demo where firing/not-firing matters. Logged as
  open question in §26 "What this document does not settle" §3.
- **Revisit the single-option `select` default threshold (0.5).** Picked
  provisionally over 0.9. If a real demo shows 0.5 lets too much fire,
  raise it. Either way, log the rationale in §26 alongside the
  decision.
- **IntelliJ / VS Code: inline interpretation hints for `select`,
  `is_true`, and other Sutra-specific constructs.** Modeled on the way
  Visual Studio shows git-blame author/commit hints inline against the
  code. The Sutra version would surface "this `select` will polarize
  with default threshold 0.5 and fire if `is_true(score) ≥ 0.5`",
  "this `is_true` polarizes the fuzzy state but does not binarize it",
  etc. — small, dismissable, contextual annotations that explain how
  the language interprets the code at the cursor. Helps onboard
  readers who don't yet have the spec in their head. Should hook into
  the LSP / MCP layer that already holds the semantic context (S1
  side of the dual runtime). Lives alongside the existing IDE work in
  `sdk/`.
- **Pick the `else_score` formula in `select(...) else fallback`.** Spec
  §26 currently pencils in `s_else = 0` as the working default — the
  user has flagged this as discouraged because a constant baseline does
  not measure "how unlike any of the named options the input is," which
  is what the else clause is supposed to capture. Plausible
  alternatives: `1 - max(scores)`, `-logsumexp(scores)`, or a
  substrate-computed novelty score. Decision needs a demo that actually
  exercises `select … else` semantics so the trade-offs are concrete.
  When the formula changes, update `planning/sutra-spec/26-select-and-gate.md`
  ("What this document does not settle" §1) and any backend that has
  started implementing `select … else`. Also fold a corresponding grammar
  change into `24-grammar.{ebnf,md}` (the `select(...) else fallback`
  production is not in the grammar yet — added at the spec level
  2026-04-15, still TBD in the grammar).
- **Sutra on commodity hardware end-to-end.** Every operation from
  `02-operations.md` running on a laptop substrate (the connectionist-
  computer work above is the path here). Numpy allowed only at the
  compile/monitor boundary, never at runtime.

## [This year] Integer class — follow-on work

The integer class landed as a compile-time tag on 2026-04-22
(augmented assignment works; `var n : int = 0; n += 1;` compiles
and runs). The canonical number axis in the synthetic subspace is
spec'd (see `planning/sutra-spec/types.md` §"The number axis and
the integer class" and
`planning/sutra-spec/equality-and-defuzzification.md` §"Canonical
axes in the synthetic subspace").

Follow-on work (none of this is in master yet):
- [ ] **Compile-time integer-specific checks.** Overflow bounds,
  mod-N wrap semantics, division by constant zero, etc. Today
  `var n : int` is a float at runtime with no checks; an integer-
  class compile-time pass could catch obvious mistakes.
- [ ] **Range-typed integers** — `int<0..N>` for loop indices,
  slot indexing into `var[N] slots : vector`, etc. Natural fit
  with the extended-state-vector design's rotation-slot allocation
  (each rotation plane is indexed by an int in a known range).
- [ ] **Type propagation through expressions.** Currently
  `var x : int = 3; var y = x + 1;` leaves y untyped (Python-
  duck-typed at runtime). A type-propagation pass would infer
  that y is also int-classed, which enables the checks above
  and sharpens IDE surface.
- [ ] **Float class as a separate tag.** The user's framing says
  "doubles have it to some extent too, but [integers] please it
  more." Making `float` / `double` a distinct compile-time tag
  alongside `int` would unlock float-specific behaviors (e.g.
  explicit precision, NaN / inf handling). Not urgent.

## [This year] Control-flow completion

The `foreach_loop NAME(array, state) { pass element(state); }`
declared-function form (2026-04-30 redesign) walks a Sutra
binding-array at runtime, so the old "Dynamic foreach" question is
now answered: dynamic iteration goes through `foreach_loop` over a
binding-array (`array_from_literal` / `array_length` /
`array_get`). The earlier compile-time `foreach (x in [a,b,c])`
unroll-over-literal form is folded into the same surface — a
literal array is just a binding-array constructed at compile time.

Remaining pieces:

- [x] **Variable-vs-variable loop condition — FIXED 2026-05-23
  (PR #32, branch `fix-loop-var-condition-typeprop`).** Was a crash at
  `--run` (type-propagation gap, NOT a substrate breach). A declared
  `while_loop` whose condition compares two *variables* (e.g.
  `i < n`) crashes at runtime with `TypeError: len() of a 0-d
  tensor` in `truth_axis`. A condition comparing a variable to a
  *literal* (e.g. `x < 11`, as in `examples/do_while_adder.su`)
  works fine — that example runs and the 23 loop tests pass.
  Root cause (verified 2026-05-23): the comparison dispatch in
  `codegen_base.py` (~line 2734) only routes `<`/`>` through the
  substrate operator `_VSA.lt`/`_VSA.gt` when
  `_is_number_expr(left) or _is_number_expr(right)` is true. A
  numeric literal satisfies that; two loop `int` params do NOT,
  because their int type isn't propagated into the loop-body scope
  (same gap as the integer-class "type propagation through
  expressions" item above). So `i < n` falls through to the raw
  `({left} {op} {right})` branch (`codegen_base.py:2750`), emitting
  a hard torch comparison `(n > i)` that yields a 0-d bool tensor.
  That 0-d tensor then hits `truth_axis`'s guard
  (`hasattr(x,'__len__') and len(x) > 1`) — a 0-d tensor *has*
  `__len__` but `len()` on it raises. Two fixes, ideally both:
  (1) propagate loop-param `int` types so `_is_number_expr` is true
  and `i < n` routes to `_VSA.lt` (the real fix);
  (2) make `truth_axis` 0-d-safe (use `.dim()`/`.ndim`, not
  `hasattr(__len__)`) so the halt check never crashes on a scalar.
  NB the raw `(n > i)` still runs on the device (torch op on 0-d
  cuda tensors) — it is the *wrong* op, not a host-scalar leak; the
  failure is loud (a crash), not a silent miscompute. Repro:
  `ts2su sdk/sutra-from-ts/tests/fixtures/for_loop_sum/input.ts -o /tmp/f.su`
  then `sutrac --run /tmp/f.su`. Found while writing tutorial 04
  (which therefore shows the for→while_loop transform + validation
  only, no run claim).
  **Fix (this PR, both layers):** (1) register loop state-param types
  in `_var_type` so `i < n` routes through `_VSA.gt`/`_VSA.lt`
  (`codegen_base.py`, `_translate_loop_function_decl`); (2) lift 0-d
  scalar tensors onto the real axis in `_as_complex_vector`
  (`codegen_pytorch.py`) so `_VSA.gt` returns a proper truth-axis
  vector — which also means `truth_axis` never sees a 0-d tensor on
  this path, so the separately-noted 0-d-safe `truth_axis` guard is not
  needed for this bug (left as a latent-robustness nicety, not done).
  `for_loop_sum`/`while_loop_sum` now `--run` → `tensor(45.)`; full
  compiler suite + 23 loop tests + transpiler tests all green.

- [ ] **`try-catch`.** Parser accepts it; codegen rejects. Sutra
  has no `raise` / `throw` primitive, so "what does a catch
  catch" is the open question — not just an implementation gap.
  Candidates: substrate-level errors (Ollama down, rotation
  produced NaN), user-level errors via a hypothetical `raise`
  primitive, fuzzy-threshold failures (a `select` where nothing
  fired). None have been designed. Park until a real use case
  pushes one of these forward.

## [This year] Exploratory / parked

Long-form research sketches live in `planning/exploratory/` — not
commitments, just parking spots. Currently parked:
- `softmax-conditionals.md` — fuzzy conditional branching as softmax over
  named cases vs classic if/elif chains.
- `karpathy-llm-wiki.md` — Karpathy's "LLM wiki" concept; interest is in
  the context-management angle.

## C → Sutra transpiler — parked (deprioritized 2026-05-08)

Skeleton landed at `sdk/sutra-from-c/` (commit `6970c52`); `c2su`
CLI exits 2 pointing at `DESIGN.md`. Decision 2026-05-08: user no
longer views transpiling Linux as a useful path to OS-level Sutra
work, so the C transpiler is no longer paired with the TypeScript
transpiler as a Yantra prerequisite. TypeScript is the sole
transpiler gate.

The skeleton stays in tree — do not delete it. If a future use case
revives the need for C-source ingestion (some specific kernel
component, a runtime library someone wants to lift into Sutra), the
DESIGN.md and skeleton are the starting point.

Until then this is the very back of the queue.

## [This year] OS-blockers (from `planning/os-blockers.md`)

These are the items standing between Sutra-the-language-toolchain
(feature-complete enough as of 2026-05-10) and Yantra writing an
actual OS. Full text + status table lives in `planning/os-blockers.md`.

- **Lazy materialization across axon boundaries.** Per `axons.md`
  § "Lazy evaluation across boundaries": only keys the consumer
  references should cross the wire. Today the full bundle crosses.
  Works fine for small N + small-magnitude fillers (the typical OS
  case — strings + numbers in the synthetic block); the 12-key
  LLM-embedding capacity wall is documented in
  `2026-05-10-multi-program-axon-passing-works.md` as the empirical
  motivation. Implementation shape: compile-time pass that walks
  the consumer's `axon_item` calls to collect referenced keys, then
  rewrites the producer's `axon_add` chain to skip the rest.
  Whole-program analysis across the import boundary; the module-
  imports machinery (shipped 2026-05-10) is the foundation.

- **Sutra-without-embeddings mode.** Per Emma 2026-05-10: "I don't
  think the kernel is going to be using embeddings at all, and
  Sutra should be able to be used without embeddings." Today every
  compiled program initializes a full `_VSA(semantic_dim,
  synthetic_dim)` with Ollama bootstrap and codebook. A program
  that never calls `basis_vector`, `embed`, or `argmax_cosine`
  against a vector codebook still pays the init cost. Needs:
  compile-time detection of whether the program touches the
  embedding subsystem; if not, skip the Ollama init, collapse
  `_VSA.dim` to just the synthetic block, keep bind/unbind/axon
  working (the rotation cache uses per-key hashes, not embeddings).
  Spec doc in `planning/open-questions/` when starting.

- **JSO operator overrides — the remaining set.** 2026-05-10
  shipped `js_add` with string-concat coercion, `js_strict_eq`
  (sharpened with element-wise diff norm), `js_strict_neq`,
  `js_loose_eq` (with string-vs-number coercion), `js_loose_neq`,
  `js_truthy`, and `js_typeof`. Plus a `String + String` operator
  that concats via the proper class-bodied operator dispatch
  (stdlib operator decls now participate in the dispatch chain).
  JS-primitive subclass declarations
  (`JavaScriptString extends String`, `JavaScriptInt extends int`,
  `JavaScriptFloat extends float`, `JavaScriptBool extends bool`)
  landed as inheritance-chain scaffolding so dispatch finds the
  right overload. Still to do:
  - **Ordered comparison with type coercion** (`<`, `>`, `<=`,
    `>=` on strings vs numbers — JS lexically compares string
    operands, numerically otherwise).
  - **`a in b` and `b instanceof T`** — need prototype-chain
    spec first; not blocking anything specific.
  - **`undefined` sentinel** for missing-property access and
    out-of-axon-key reads. Need an axis bit (AXIS_AXON_POPULATED
    is partial; uniform undefined-vs-zero needs reconciliation).
  - **`JSON.parse / .stringify`** — text round-trip. Needs
    string-axis encoding for object trees.
  - **Per-primitive intrinsics** — the stdlib subclass
    declarations are empty bodies today; specific JS-flavored
    behaviors that don't fit the JSO catch-all (e.g. JS's
    weird `[].toString() === ""` behavior) will land as
    intrinsic methods on the subclass when a concrete program
    needs them.

- **Infinity (and -Infinity, NaN) as first-class numbers.** Per
  Emma 2026-05-10: "I feel like the big thing that we wouldn't be
  able to do with the numbers is numbers have infinity in
  JavaScript, and I don't know how we would do that. But it might
  actually be worth looking into including infinity as a number,
  as a kind of a number flag in our thing." Two design options:
  - Reserve a synthetic axis (e.g. `AXIS_NUMERIC_TAG` taking
    values `0` for finite, `+1` for +Infinity, `-1` for
    -Infinity, with NaN as the off-axis sentinel).
  - Use Float32's native ±inf / NaN representation directly at
    `AXIS_REAL` — the substrate is already float32 tensors, so
    `make_real(float('inf'))` would work mechanically; the
    question is whether downstream ops (multiply, add,
    transcendentals) handle it correctly.
  Not blocking anything specific. Park as a TODO; revisit when
  a real program either needs Infinity (numerical bounds, search
  algorithms) or produces it accidentally and we want defined
  behavior.

- **I/O primitives.** Lives in Yantra repo; Sutra side will grow
  an `io` stdlib class declaring intrinsics. Surface dictated by
  what Yantra actually wants. Not Sutra's call to pre-design.

- **Performance** — inherent to "every op is a tensor matmul on
  868-d vectors." Tracked under existing entries:
  `[This year] Compilation updates` (egglog fusion), per-program
  embedding-space override, Sutra-without-embeddings mode (above).

## [This year] Speculative

- **Sutra-embedded-in-Python (`@sutra` decorator + import hook).**
  Longer-term interoperability path. User vision (2026-04-22): a
  Python function decorated with
  `@sutra` has a Python signature (types at the boundary become the
  FFI contract) but a body written in Sutra syntax. Example:

      @sutra
      def greet(name: str) -> str:
          vector v_name = basis_vector(name);
          vector winner = argmax_cosine(v_name, [v_hello, v_goodbye]);
          return PHRASE_NAME[winner];

  The `def` line is the FFI; strings and numpy arrays cross cleanly;
  the body can only use pure Sutra ops (no imperative mutation,
  which the compiler enforces). Mechanism options: an import hook
  that preprocesses `.py` files before Python sees them, or
  explicit `sutra.compile(fn)` / `sutra.run("""...""")` calls for a
  less magical version. PHP-in-HTML is the prior-art analogy —
  host language is declarative scaffolding, embedded language is
  the active computation, demarcation is meaningful not cosmetic.

  Why this matters: adoption. HDC researchers live in Python; their
  vectors live next to datasets and pipelines. A Sutra that ships
  as a PyPI library with `@sutra`-decorated functions lets them
  write real Sutra programs without leaving their existing
  environment. The segregation (imperative Python handles I/O,
  functional Sutra handles vector computation) is a *feature*, not
  a compromise.

  Scope sketch:
  1. PyPI package (`pip install sutra`) that wraps the existing
     `sdk/sutra-compiler`.
  2. `@sutra` decorator that marks a function for Sutra compilation.
     The Python-visible function becomes a thin wrapper that
     marshals args in, executes the compiled Sutra body, and
     marshals return values out.
  3. Import-hook or AST-preprocessing so the Python parser doesn't
     choke on Sutra syntax in the decorated body. A compilation
     step that runs before Python sees the file is the simplest
     path; import hooks are the seamless path.
  4. Type marshalling: `str → vector` via `basis_vector`, `numpy
     array → vector` pass-through, `vector → str` via codebook
     lookup or caller-supplied serializer.
  5. IDE support for the dual-layer file. VSCode's embedded-language
     mechanism (CSS-in-JS precedent) is designed for this pattern
     but is non-trivial to wire up for a new outer+inner language
     pair.

- **OWL → SutraDB extension + Sutra ontology import/editing.** Build out
  OWL handling so SutraDB gains a first-class ontology extension and Sutra
  gains ontology-aware operations. Protégé may be a more helpful starting
  point than raw OWL files.

## [This year] Transcendental functions — design absorbed from voice chat

User direction (voice conversation, mid-2026 — full chat absorbed
2026-05-02 from `chats/implementing-transcendental-functions.md`,
which has since been deleted). The intuition that crystallized
during the chat: in the complex plane, the four "main"
transcendentals — exponential, logarithm, sine, arc-sine — are
all the same operation viewed from different angles.

- `exp(x + iy)` is scaling (real part) plus rotation (imaginary
  part). On the unit circle (`x = 0`) it's pure rotation by `y`
  radians. Scaling and rotation compose because exponents
  multiply: `exp(a + b) = exp(a) * exp(b)`.
- `sin` is the imaginary part of `exp(iθ)`. Cosine is the real
  part. They're not independent operations — they're projections
  of the rotation onto the two axes.
- `log` inverts: real part of the log is the magnitude (how much
  scaling), imaginary part is the angle (how much rotation).
  `log(-1) = iπ`, `log(i) = iπ/2`. The "log of negative numbers
  doesn't exist" graph is lying by omission — it just means the
  output is on the imaginary axis. Zero is the only genuine
  asymptote.
- `arcsin` is just `log` in disguise — given an imaginary value,
  find the rotation that produced it. The branch-cut artifact
  arises from picking which of the infinite valid rotations to
  return.

### Two primitives, lookup tables, everything else derived

The Sutra implementation reduces to **two primitives**: `exp` and
`ln`. Both backed by lookup tables. Everything else beta-reduces:

```
x ^ p              ->  pow(x, p)            (operator desugar)
pow(x, p)          ->  exp(p * ln(x))       (change-of-base identity)
log(b, x)          ->  ln(x) / ln(b)        (change-of-base for log)
sin(θ)             ->  imag(exp(iθ))        (definitional)
cos(θ)             ->  real(exp(iθ))        (definitional)
arcsin(z)          ->  imag-extract(log(...))  (deferred)
sinh / cosh / tanh ->  combinations of exp(x), exp(-x)  (deferred)
```

`exp(1)` returns Euler's number — no need to hardcode `e` as a
constant; it falls out of the primitive.

**Complex-argument cosine shipped 2026-05-17.** `Math.ccos(complex z)
= (cexp(i·z) + cexp(-i·z))/2` — substrate-pure over the verified
`cexp` keystone; ground-truth ≤2e-4 vs `cmath.cos`; finding:
`planning/findings/2026-05-17-complex-argument-cosine-implemented.md`.
**Follow-on — ✅ SHIPPED 2026-05-28.** Complex `csin(z) = (cexp(i·z) −
cexp(-i·z))/(2i)` — the symmetric sibling — is declared in
`stdlib/math.su` (`static intrinsic method complex csin(complex z)`).
Finding: `planning/findings/2026-05-28-csin-complex-sine-shipped.md`.

### `^` operator (no XOR conflict in Sutra)

`^` is exponentiation. Sutra has no bits to flip, so the C-family
"^ means bitwise XOR" convention doesn't apply — XOR exists only
as a logical connective on the truth axis (and is reachable as
the keyword `xor` plus the parser-level chain reductions). `^`
binds above `*`, right-associative is the math convention.

### `sin` via rotation matrix, not lookup

Per the Emma 2026-04-28 eigenrotation finding (validated, refuted
on speed but accepted for substrate-uniformity), sine via rotation
matrix is one matmul. The rotation matrix entries are sin/cos of
the angle, so it does a self-referential thing internally — but
once Sutra has `exp` working on the imaginary axis, the rotation
matrix can be built from `exp(iθ)` instead of calling out to libm
sin/cos. That closes the loop: every transcendental in the
language compiles down to `exp` and `ln` lookups.

### Implementation order, when picked up

1. **`exp(x)` lookup table** for real x in a bounded range, plus
   integer-iteration for the part outside the range and
   geometric-root for the fractional part. Substrate-pure (no
   host scalar arithmetic — that was the architecture mistake
   the 2026-04-29 implementation made and got withdrawn).
2. **`ln(x)` lookup table** for positive real x. Negative x
   handled by `ln(-x) + iπ`. Zero raises (genuine asymptote).
3. **`exp(z)` for complex z** = `exp(real(z)) * (cos(imag(z)) +
   i sin(imag(z)))`. With the rotation-matrix path for sin/cos,
   this is one scalar lookup plus one rotation matmul.
4. **`pow`, `log`, `sin`, `cos`** as inliner-expanded calls over
   the two primitives. No new runtime ops.
5. **`arcsin`, hyperbolic** deferred — useful for completeness
   but not needed for the language to be complete.

The bound-table-via-binding approach didn't pencil out
(`planning/findings/2026-04-29-bound-table-capacity-limit.md`),
but the lookup-table approach the chat settled on is different —
it's a flat table-plus-interpolation, not a VSA-bundle of bound
table entries. Worth retrying.

This is a "later this year" item, not blocking. Re-implementation
needs a real design doc in `planning/open-questions/` before
codegen, plus a re-validation pass against the substrate-purity
audit.

## [This year] Examples-corpus open semantic questions

Merged here 2026-05-15 from the former `examples/todo.md` (a
per-subdirectory todo file, which this file forbids — "Do not
re-split this into per-subdirectory todo files"). The
`codegen_numpy.py`-era framing of that file (numpy backend as the
fixed substrate, dim=256, fly-brain backend, "switch the numpy
backend to a real frozen LLM") is **dropped as stale** — the
canonical backend is `codegen_pytorch.py` and the numpy backend is
deprecated. The genuinely-live questions it raised, kept:

- **What does a Sutra program output?** The paper framing ("the
  edge commits a trajectory to a discrete answer" via snap /
  argmax-cosine) is too narrow — a program can output a discrete
  codebook entry, a raw/fuzzy vector, a logit vector, a polarized
  fuzzy state, or a tuple of these. The terminal commit is a
  choice the *program* makes, not a language property. Open:
  reflect this in the paper's output-semantics section and have at
  least one demo output raw logits rather than a snapped entry.
- **`snap` spec coverage.** `snap` is spec'd as a substrate-level
  attractor cleanup; the PyTorch backend rejects it
  (`_UNSUPPORTED_BUILTINS`) and demos use `argmax_cosine`. Decide:
  route `snap` → `argmax_cosine` as the no-attractor fallback, or
  state explicitly in the spec that `snap` needs a substrate
  attractor and the demo path uses `argmax_cosine`.
- **"Every class is a vector (or matrix)."** Working position:
  scalars/fuzzy/bool/permutation are all vector-shaped, matrices
  are functions on the substrate. Open: does `types.md`'s
  primitive-type list need a refactor that says "everything is a
  vector, with type-level labels carrying extra structure"?
- **Vector classes carry compile-time memory.** Vectors record
  which ops were applied (the bool defuzzification counter is one
  case) — compile-time metadata, not runtime side effects. You
  can't branch on it at runtime; you can normalize it at compile
  time. Candidate dedicated spec section when the user has thought
  more about it.
- **`role(name)` vs `embed(name)`.** Under a frozen LLM,
  lexically-similar role names embed near-identically, which
  breaks VSA binding (`sequence.su` drops 11/11 → 3/11 — see
  `planning/findings/2026-04-15-llm-substrate-role-name-collision.md`).
  The split that works: content from the LLM, roles from a seeded
  near-orthogonal RNG. Open: spec a `role("name")` primitive
  distinct from `embed("name")`, add to the compiler, re-run the
  smoke test expecting 11/11.

Whether the language is *literally* monadic (pure body + edge
commit with unit/bind/associativity) is parked in
`planning/exploratory/` — not load-bearing.

---

# SutraDB (appended from former `sutraDB/TODO.md`) — lower priority

Companion Rust triplestore (own crate, own `sutraDB/CLAUDE.md`); 228/249
items complete. All items below are **[This year]** unless noted.

## SutraDB — Next Release (v0.3.1): Gradle Migration, MCP Agentic UX, Maven Central

- [ ] Merge Gradle migration + Maven Central publishing setup (local commits).
- [ ] Bump version to 0.3.1 in `sdks/java/build.gradle.kts` and all other
  SDK configs.
- [ ] Set up Maven Central secrets: `MAVEN_USERNAME`, `MAVEN_TOKEN`,
  `GPG_PRIVATE_KEY`, `GPG_PASSPHRASE`. Generate GPG key, upload public key
  to keyserver.
- [ ] Tag `v0.3.1` and push to trigger publish workflow. Verify
  `io.github.emmaleonhart:sutradb:0.3.1` appears on Maven Central.

## SutraDB — Java/Kotlin SDK

- [ ] Integration test: start SutraDB, insert triples, query, verify
  round-trip.
- [ ] OWL validation (match Python SDK: domain/range/subclass/disjoint/
  equivalent).
- [ ] Connection retry logic with configurable timeouts.

## SutraDB — Future Versions

### AI Agent Installer
- [ ] End-to-end test: fresh install → insert → query → verify.
- [ ] Serverless mode testing.
- [ ] Agent-consumable structured output (JSON mode).

### HNSW Traversal via SPARQL Property Paths
- [ ] Greedy descent + beam search semantics from graph structure and
  property path evaluation.
- [ ] Test: `sutra:hnswNeighbor+` produces correct ANN results.

### Predicate-Based Exit Conditions (UNTIL)
- [ ] Design UNTIL syntax for exit conditions on property path traversal.
- [ ] Per-step predicate evaluation during traversal.
- [ ] Backtracking interaction, ordered traversal, HNSW-specific exit.

### Cost-Based Query Planning
- [ ] HNSW as access path: planner chooses HNSW index scan vs SPO scan.
- [ ] Adaptive execution: observe intermediate result sizes, reorder mid-query.

### Background Maintenance Cycle
- [ ] Low-usage detection heuristic.
- [ ] Background HNSW rebuild with atomic swap.
- [ ] Background pseudo-table rediscovery and rebuild.

### Pseudo-Tables
- [ ] Invalidation tracking; update planner to match multi-pattern SPARQL
  queries to subgraph pseudo-tables.

### Database Health Dashboard
- [ ] Per-pattern latency percentiles, planner decision accuracy.
- [ ] `sutra health --json` for programmatic agent consumption.
- [ ] Sutra Studio health dashboard as Flutter landing page.

### SDK Publishing
- [ ] Python → PyPI, TypeScript → npm, Rust → crates.io, C# → NuGet,
  Go module tag.

### Sutra Studio
- [ ] Remote Studio access over the network.
- [ ] Dart FFI bindings replacing HTTP client.
- [ ] Studio-embedded MCP server (background thread).
- [ ] Flutter graph view parity with `browse.html`.
- [ ] Long-term: absorb core Protégé functionality.

### Query Language Wrappers
- [ ] Cypher → SPARQL transpiler.
- [ ] GQL (ISO 39075) → SPARQL transpiler.
- [ ] Query validation: reject constructs that can't map to RDF.

### Premium Tier — deferred until paying customers
RBAC, encryption at rest, TLS, audit logging, replication, clustering /
sharding, multi-tenancy, connection pooling.

## SutraDB — Reference Architectures

| System | Why |
|--------|-----|
| [Qdrant](https://github.com/qdrant/qdrant) | HNSW impl, visited pools, normalize-at-insert |
| [Oxigraph](https://github.com/oxigraph/oxigraph) | RDF storage, SPO/POS/OSP, SPARQL pipeline |
| [DataFusion](https://github.com/apache/datafusion) | Cost-based planning, join ordering, vectorized execution |
| [DuckDB](https://github.com/duckdb/duckdb) | Columnar analytics, zonemap pruning, join ordering |
| [GlueSQL](https://github.com/gluesql/gluesql) | Small readable query engine |
| [Limbo](https://github.com/tursodatabase/limbo) | Rust SQLite reimpl, storage ideas |
| [Materialize](https://github.com/MaterializeInc/materialize) | Streaming SQL on Differential Dataflow |

SutraDB benchmark baseline: `sutraDB/benchmarks/LATEST.md`.

---

## [NEXT YEAR] Formally define "tensor normal form" — before using the term anywhere

**Status: deferred, ~next year (Emma 2026-05-25).** We removed every use of
"tensor normal form" / "TNF" from the active specs, docs, and the FV paper,
because **we have not formally defined it** and claiming a canonical "normal
form" we have not proven is an overreach that has actively hurt the FV paper's
reception. Until it is properly defined, the honest, defensible phrasing is the
descriptive one we now use everywhere: *the compiler emits a tensor-op graph
that is the program's semantics.*

The rough idea we DO have (keep, do not over-promise):
- **Tensor normal form ≈** the sense in which a program can be algebraically
  simplified to *just a sequence of matrix multiplications* (an
  affine/multilinear pipeline over the substrate).
- **Recurrent tensor normal form ≈** the same idea for the bounded soft-halt
  loop case — a fixed-width recurrence `state ← R · state` as the normal form
  for iteration.

Why it is deferred, not done now:
- A real *normal-form* claim needs formal-verification / rewriting-theory
  machinery (confluence, a canonicalisation/decision procedure, a proof that the
  form is canonical) that we do not have in hand yet.
- It is genuinely unclear what standing we have to *declare* a new normal form
  as a formal object; doing so prematurely reads as unsupported. Define it
  properly, with proofs, or do not call it that.

When picked up: define TNF + recurrent-TNF precisely as part of the FV process,
prove the canonicalisation properties claimed, THEN (and only then) reintroduce
the term into the spec/paper. Mirrored in Yantra `todo.md`.

## [This year] Agentic RAG for constrained-training design (generalize the equals-stuff machinery)

**Priority sequence (Emma 2026-05-26):**
1. **Equality cosine-similarity adjustment** — first concrete piecemeal target. The Stage-B `w` scalar generalized to a global / per-rule learnable `similarity` temperature (or anisotropy-correction term) that tightens the AND/NOT decision margin on the narrow LLM cone. Smallest, most-architectural scalar; the "equals stuff" sharpening Emma is most confident about.
2. **Everything else that's low-hanging fruit** — the remaining scalar-first targets in the list below (`select` sharpness, soft-halt threshold, number-axis scale/offset, codebook decode threshold, class-method dispatch sharpness, per-axis defuzz rates). Each is small, scoped, individually verifiable.
3. **Harder stuff made easier by 1 + 2** — matrix-valued targets (`is_X`, defuzz matrix, learned-matrix binding). Gated on the `.su` matrix-literal spec decision; the meta-tool + equivalence-guard + bake-back machinery built during phases 1+2 carries straight over.
4. **Full back-propagation of all weights into code** — the endpoint of the §"NN → code decompilation" thread below: arbitrary trained NN fragments (matrices, multi-layer MLPs, attention heads) decompile back into source-recompilable `.su`. The Stage-B `w`-scalar bake-back is the degenerate 1-parameter case of this; phase 4 generalizes to all parameter shapes the language can express as literals.

The four phases are sequential — each builds the infrastructure the next consumes. The work-loop cron should always prefer (1)-style scalar work over (3)-style matrix work until phases 1+2 are demonstrably finished.

Stage A/B (`planning/findings/2026-05-18-differentiable-training-is-a-
proxy-not-compiled.md`) showed the pattern works for the equality-rule
case: compile a `.su` rule (similarity + Kleene AND/NOT) through the
real PyTorch codegen, train a scalar gain `w` + K prototypes through
the **emitted** graph with Adam + cross-entropy, then **bake the
trained `w` back into the `.su` source as a numeric literal** — a
recompilable Sutra file that reproduces the trained behaviour
(round-trip max logit Δ ≈ 2×10⁻⁷). The trained model IS legible
source code.

That same shape — compile-once + train-through-emitted-graph +
batched-vs-per-sample equivalence guard + bake-back-into-`.su` —
should generalize to most other learnable parameters in the
language. This agenda is (a) the **agentic RAG meta-tool** that
picks a training shape for a given target by retrieving prior
findings + harnesses + spec snippets, and (b) the **list of
concrete constrain-train targets** the meta-tool can be aimed at.

**Scope.** The pattern is proven for *scalar* + *prototype-
vector* parameters. Matrix-valued parameters (the `is_X` matrix; the
defuzz matrix; learned binding matrices) need a bake-back surface for
frozen matrices — and that surface now exists: **`matrix_literal`
shipped 2026-05-28** (per Emma's AskUserQuestion decision;
`sdk/sutra-compiler/tests/test_matrix_literal.py`,
`_VSA.matrix_from_rows`). The matrix-target training experiments below
are still open, but the "no matrix literal in `.su`" blocker they cite
is resolved.

### Meta-tool: the agentic RAG system

- [ ] **Corpus indexer.** `scripts/build_training_corpus.py`: walk
  `planning/findings/`, `planning/sutra-spec/`, `experiments/
  differentiable_training*.py`, `planning/open-questions/`, chunk
  by section heading, embed via Ollama `nomic-embed-text` (the same
  model Sutra's runtime uses — eat your own dogfood, no extra
  dependency), store as JSON or sqlite under `.training_corpus/`
  (gitignored — rebuild script is the committed artifact).
- [ ] **Retrieval CLI.** `scripts/training_design_query.py "train
  is-X matrix"` → returns top-k ranked chunks with file:line
  anchors. Builds on the corpus above.
- [ ] **Decision template.** A structured schema the meta-tool
  fills per target: `{operator_target, parameterization, loss,
  equivalence_guard, bake_back_form, expected_baseline,
  expected_target, integrity_checks_against_CLAUDE_md}`. Stored
  as `planning/training-designs/<name>.md` per target.
- [ ] **Sub-agent definition.** `.claude/agents/constrained-
  training-designer.md`: a sub-agent that takes a target operator,
  runs the retrieval CLI, fills the decision template, and proposes
  a concrete experiment shape — *without* implementing it (separate
  step, gated on Emma's review of the template).
- [ ] **Experiment scaffolder.** Given a filled decision template,
  generate `experiments/<name>.py` following the Stage-A/B harness
  pattern: compile rule once via the real codegen; build training
  loop; **mandatory batched-vs-per-sample equivalence guard** to
  10⁻⁴ before training begins (run aborts on mismatch); train; bake
  back; recompile round-trip; assert round-trip max-Δ ≤ 1e-6.
- [ ] **Integrity rail auto-check.** Before any scaffolded
  experiment runs, statically scan it for forbidden patterns
  (CLAUDE.md "Forbidden" list — scalar extraction inside an op,
  Python control flow on scalar predicates, "algebraic" /
  "host" / "O(1) on the host" comments). Fail closed if any hit.
- [ ] **Findings auto-writer.** After a successful experiment,
  generate `planning/findings/YYYY-MM-DD-<name>.md` matching the
  format of prior findings: verified facts (read, not assumed),
  measured numbers, verdict, what is NOT claimed, follow-ups.
  Emma reviews/edits before commit.

### Constrain-train targets (each is an independent experiment)

Highest-leverage first. Pick one per session; do not parallel-fire
without explicit go-ahead — the per-experiment integrity surface
needs human review.

- [ ] **`is_X` matrix end-to-end (top priority — most architectural).**
  Train per-concept "is-X" predicate matrices through the compiled
  graph. Currently `equality-and-defuzzification.md` § "Open questions"
  asks: "What is the exact construction of the is-X matrix? Is it a
  single canonical function per type, or user-definable per
  predicate?" — train it and find out. (Former blocker "matrix
  literals in `.su`" is **resolved** — `matrix_literal` shipped
  2026-05-28; bake-back surface exists.)
- [ ] **Defuzz matrix.** `equality-and-defuzzification.md` says "a
  defuzz matrix exists such that multiplying a fuzzy value by it
  produces a defuzzified-by-a-certain-amount version" — *exists* is
  a placeholder. Train the polarization matrix on the truth axis
  against ground-truth defuzz-step targets. (Same former matrix-
  literal blocker as `is_X`, now **resolved** — `matrix_literal`
  shipped 2026-05-28.) Possibly the same matrix as some canonical
  `is_true`-matrix factor — answer that en route.
- [x] **`select` sharpness coefficient (scalar) — ✅ MECHANISM SHIPPED 2026-05-28.**
  The select softmax temperature `T` is exposed as a Sutra-level
  trainable `number`; the full harness
  (`experiments/select_temperature_adjustment.py`) trains it, bakes
  T\* back as a `.su` numeric literal, and verifies round-trip
  (max|Δ| ≈ 2.5e-06). Findings:
  `planning/findings/2026-05-28-select-T-trains-but-K5-embed-task-is-flat.md`
  and `…-select-T-bimodal-T-surface.md`. Task-fit caveat recorded in
  the finding: the K=5 embedded-category-name task surface is flat
  (near-degenerate similarity gap, nothing for T to sharpen) — that is
  a task observation, not a mechanism failure, and per CLAUDE.md the
  K=5 sweep is closed, do not re-run.
- [ ] **Soft-halt threshold for loops (scalar).** `loop (condition)`
  iterates `state ← R · state` with a sigmoid halt. The threshold
  determines decisiveness; train it on a corpus of converging /
  non-converging programs against ground-truth iteration counts.
  Scalar → straightforward bake-back.
- [ ] **`similarity` temperature (scalar).** Emitted form is
  `dot/(||a||·||b|| + eps)`. Adding a learned temperature `T` so
  `similarity_T(a,b) = T · dot/(||a||·||b|| + eps)` sharpens or
  flattens the cosine output across the anisotropic embedding cone.
  Train `T` per task (or as a per-program tunable). Scalar bake-back.
  Compare against the Stage-B `w` result — the gain there was
  essentially a per-rule `T` baked into one site; this is the
  global version.
- [ ] **Number-axis scale/offset (two scalars).** Currently the
  number axis hosts integer / float scalars at a fixed unit scale.
  Train `(scale, offset)` to maximize dynamic range subject to a
  round-trip-accuracy threshold (defuzz then `as_number` returns
  the input within ε). Two-scalar bake-back; substrate-pure.
- [ ] **Codebook decoding threshold (scalar).** String literals
  decode through a `map<vector, string>` codebook (`strings.md`).
  Train the decision threshold — below which similarity to any
  codepoint counts as "no match" — on a corpus of clean + noisy
  decode tasks. Scalar.
- [ ] **Class-method dispatch sharpness (scalar).** When a method
  is called on a class instance, dispatch resolves via similarity
  to the method's name. Same shape as `select` sharpness; separate
  target because it composes differently and may want its own
  trained value.
- [ ] **Per-axis defuzz rates (vector of scalars).** Different
  canonical axes (truth, number, future enum / position) may want
  different polarization rates. Train per-axis rates against a
  task-mix; bake back as a vector literal (smaller blocker than the
  matrix-literal case — likely already expressible via a list `.su`
  literal).
- [ ] **Learned-matrix binding (already on todo.md as a separate
  agenda item).** Listed here for cross-reference: the
  Procrustes / lstsq fit at compile time is itself a constrain-
  train step. Sharing the meta-tool's decision template + scaffolder
  with the existing `## [This year] Learned-matrix binding` section
  is the natural reuse — do not duplicate work.

### Cross-cutting infrastructure (reusable across targets)

- [ ] **Equivalence-guard harness.** Extract the batched-vs-per-
  sample equivalence guard from `experiments/
  differentiable_training_compiled.py` (the ≤10⁻⁴ assertion that
  aborts the run on mismatch) into a reusable
  `experiments/_equivalence_guard.py`. Every constrain-train
  experiment imports it; the guard is the integrity surface the
  paper / arXiv claims rest on.
- [ ] **Bake-back machinery for matrix-valued parameters.** Once
  the matrix-literal spec decision lands (see `is_X` target
  above), implement the `.su` ↔ matrix-tensor serializer +
  round-trip recompile test. This is shared infrastructure across
  the `is_X`, defuzz, and learned-binding targets.
- [ ] **Constraint catalog.** A short `planning/sutra-spec/
  constrained-training.md` enumerating the constraints every
  constrain-train target MUST satisfy: (a) trains through the
  emitted compiled graph (not a reimplementation); (b) batched
  ≡ per-sample within 10⁻⁴; (c) trained value is `.su`-literal
  expressible; (d) recompile round-trip Δ ≤ 1e-6; (e) substrate-
  purity rails pass (no host shortcuts, no scalar extraction inside
  an op). The meta-tool checks every proposed design against this
  list before scaffolding.
- [ ] **Per-target baseline / target table.** As targets land,
  collect their (chance, baseline, trained, wall-clock) numbers
  into a single table — `planning/findings/CONSTRAINED-TRAINING-
  RESULTS.md` — so the cumulative evidence for "the pattern
  generalizes" stays auditable. Cite-able from the live
  `paper/paper.md` once the freeze lifts (2026-06-01).

## [This year] Back-propagation into code — third paper + docs page (Emma 2026-05-26)

The "back-prop into code" thread — trained model values bake back into recompilable `.su` source — is substantial enough to warrant its own paper and a dedicated docs page on `sutra.emmaleonhart.com`, separate from the main arXiv paper (`paper/paper.md`), the frozen NeurIPS submission (`paper/neurips/`), and the live FV paper (`paper/formal-verification/`).

The thread spans:
- **Stage-B (2026-05-18, shipped):** trained scalar `w*` baked into `.su` as a numeric literal; recompile round-trip max logit Δ ≈ 2×10⁻⁷.
- **Equality cosine adjustment (2026-05-26, in flight as `bu7o9mqxu`):** trained `T*` baked into `.su` as a numeric literal in the isolated-`T`-only probe; smoke run +1.18× margin ratio, round-trip 2.38e-07.
- **Per-rule literal placement decision (2026-05-26, resolved):** `planning/open-questions/equality-cosine-T-placement.md`. Lean.
- **Matrix-valued bake-back (next):** gated on the `.su` matrix-literal spec decision; learned matrices land back as `.su` literals.
- **Endpoint:** arbitrary trained NN fragments (matrices, MLPs, attention heads) decompile to recompilable `.su` — see §"NN → code decompilation" thread below.

### Paper: `paper/back-prop-into-code/paper.md` (new clawRxiv post chain)

- [ ] **Scaffold the paper directory.** `paper/back-prop-into-code/{paper.md, .post_id, reviews/}`. Mirror the FV paper's auto-submit workflow (`fv-paper-ci.yml`): on push to this paper, submit to clawRxiv, fetch review, commit back.
- [ ] **Workflow file.** `.github/workflows/bpic-paper-ci.yml` — copy from `fv-paper-ci.yml`, change paper dir.
- [ ] **First draft.** Scope: "trained models as recompilable source code." Cite Stage-B + equality cosine + (when measured) matrix bake-back results. Mirror the §"What we are not claiming" discipline; do NOT claim "decompile any NN into Sutra" (anti-claim documented in §"NN → code decompilation").
- [ ] **Live artifact (not frozen).** Like the FV paper, this is free to evolve as the constrain-train targets land. Cite measured numbers only.

### Docs page: `docs/back-prop-into-code.md` (`sutra.emmaleonhart.com/back-prop-into-code/`)

- [ ] **Write the page.** Human-facing explanation of the bake-back idea. Start with Stage-B's "trained `w*=1.4339...` IS the trained model — recompilable, legible, no checkpoint blob" framing. Add the equality cosine result once measured. Build a worked example: a tiny `.su` rule, training, bake-back, side-by-side trained-rule-source. Indexable; no `noindex`. Keep free of repo-internal scratchpad references (`queue.md`, `todo.md`, `planning/...`, deep `sdk/...`) per CLAUDE.md §"Audiences".
- [ ] **Link from homepage.** Add a card / link from `docs/index.md` in the same shape as the existing concept-page links. Don't ship the page un-discoverable.
- [ ] **Cross-link to /paper/.** When the paper PDF is available on clawRxiv, link it from the docs page; same shape as the existing `/paper/` button.

### Honest non-claims for both surfaces

- Not "trained models always decompile to legible code" — only for the FV-decided fragment (scalars, then matrix-valued once the spec lands, then composed Kleene rules; attention heads explicitly exploratory).
- Not "Sutra replaces neural-network training" — it composes with NN training; the back-prop-into-code result is that the *trained values* are recompilable source, not that the *training procedure* is novel.
- Not "this is decompilation in the reverse-engineering sense" — it's bake-back of trained values into a source form the compiler already accepts; the *training graph* is the compiled `.su`'s emitted form, not an arbitrary NN's forward pass.

## [This year] Constrained Adam + FV-linked training + NN→code decompilation (Emma 2026-05-26)

Extends the agentic-RAG agenda above. The three threads are tightly
coupled: a *constrained* Adam (which parameters move, with what
range/monotonicity constraints) *is* the bridge between the FV
checker's discharged obligations and the trained substrate values,
and the bake-back step *is* a degenerate decompilation that wants to
generalize beyond the Stage-B `w` scalar.

### Vision arc — "constrain to meaningful" is the *first phase* of mapping everything to meaning

**Emma 2026-05-26: "the vision is eventually we will be able to map
everything to being meaningful." Long-term direction, advanced
piecemeal — the near-term work IS the scalar-first targets in the
preceding agenda and the constrained-Adam section below.** This vision
arc is *what makes those piecemeal choices coherent over time*, not a
replacement plan. Read every sub-item through this lens; don't promote
the long-arc phases over the piecemeal targets.

Current state. The 768-d frozen-LLM embedding space is anisotropic:
content concentrates in a cone (`equality-and-defuzzification.md`
§ "undersymbolic realm"), with the rest of the unit sphere sparsely
populated by anything natural-language can name. Sutra currently
splits this into:
- **Semantic subspace** — the content cone where the LLM's meaning
  lives. Descriptive (work with what the model already learned).
- **Synthetic subspace** — a handful of *constructed-orthogonal*
  canonical axes (truth axis, number axis; future enum / position /
  time) hosting bookkeeping that should never collide with content.
  Prescriptive (nothing was supposed to live here in the first place).
- **Undersymbolic realm** — the void. Directions orthogonal to both
  the content cone and the named canonical axes. Currently used as
  a *reservoir of safe rotation-bind slots* (nothing collides because
  nothing lives there).

The arc. Each phase below shrinks the undersymbolic realm by
mapping more directions to *named, typed, meaningful* roles.

- **Phase 1 (now): Restrict training to the union of (content cone +
  named canonical axes + anchor-ball neighborhoods).** This is the
  meaningful-only Adam constraint in the constrained-Adam section
  below. Adam never pushes a learned value into the undersymbolic
  realm — *because we don't yet know what those directions mean.*
- **Phase 2: Add more canonical axes for known abstract types.**
  Enum, position, time, sentiment — types the language can name
  without LLM-corpus evidence. Each new canonical axis carves a slice
  out of the undersymbolic realm and tags it as meaningful-of-this-
  type. (Some of this is already in todo.md § "Extended state
  vector".) The constrain-train framework picks up each new axis as
  an additional target subspace.
- **Phase 3: Discover canonical axes by training.** Run a learned
  decomposition over the undersymbolic realm that surfaces directions
  whose variation across a corpus correlates with a useful abstract
  distinction (causality, modality, aspect, evidentiality — things
  LLMs encode implicitly but don't surface as orthogonal axes). Each
  discovered axis gets a name + a type + a place in the canonical-
  axis registry. The FV checker gets a new role to verify; the
  constrain-train framework gets a new target subspace.
- **Phase 4: Coverage measurement as a first-class metric.** Track
  the fraction of the unit sphere assigned to a named meaningful
  role over time. Coverage starts low (the content cone is a small
  fraction of 768-d) and rises as Phase 2/3 axes accumulate.
  Publishable as a real metric in the next-venue paper.
- **Phase 5: Cone-expansion / meaningfulness saturation.** The end
  state: every direction in the representation space carries either
  semantic-cone meaning (descriptive) or canonical-axis meaning
  (prescriptive). The undersymbolic realm shrinks to zero. The
  constrain-train framework's *restriction* role becomes obsolete
  (every direction is meaningful, so "constrain to meaningful" no
  longer restricts); only its *structural* role remains (which type
  of meaning, not whether meaning). Substrate purity rules stay
  identical — every operation still runs on the substrate, just over
  a fully-mapped representation.

Concrete near-term experiments this vision suggests (independent of
the constrain-train scalar targets above):

- [ ] **Coverage measurement script.** A scriptable estimator that,
  given the current set of canonical axes + an empirical content-
  cone estimate (top-K PCA of `nomic-embed-text` over a fixed
  corpus), reports the fraction of unit-sphere directions within
  angle `θ` of *some* meaningful subspace. Baseline number first;
  watch it climb across phases.
- [ ] **Discovered-axis probe.** Phase-3 proof-of-concept: run
  per-position embedding statistics on a labeled corpus (e.g. negated
  vs unnegated sentences) and check whether the leading principal
  component of the *difference vectors* lies in the undersymbolic
  realm. If yes, that's a candidate canonical axis for "negation
  polarity." Honest non-claim: this might just rediscover known
  cone directions; "no new axis found" is a real possible outcome
  and a finding.
- [ ] **Anti-realm-collision audit.** Every time a new canonical
  axis is committed, check that no current `bind` / `bundle` /
  rotation operation produces a nonzero coordinate on that axis
  *before* the axis was added. If yes, the prior code was
  accidentally living in what is now meaningful space and needs
  audit. This is the inverse of the substrate-purity audit:
  catches *retroactive* meaning collisions.
- [ ] **Vision-arc DEVLOG entries.** Track each canonical axis
  added (with date + commit) so the long-arc claim "we are
  progressively mapping more of the space to meaning" is backed by
  a real timeline, not a story.

Honest scope: this is multi-month exploratory work, not the next
queue item. Captured here so the meta-tool above (corpus indexer +
decision-template) can route training-design decisions through it
once the scalar targets land and the matrix-literal spec decision
settles.

### Constrained Adam — constraints from FV become training constraints

**The core idea (Emma 2026-05-26): constrain to only meaningful
things when training, at least at first.** Adam wanders by default —
it'll happily push a learned 768-d vector into the *undersymbolic
realm* (directions roughly orthogonal to the LLM content cone where
no natural concept lives) or off a canonical axis (a truth-axis
scalar developing a number-axis component that nothing should ever
emit). The §3.2 polynomial-range-bounder (`fv_poly_bound.py`) +
`range_sound_by_composition` prove operator-output ranges; **the
*meaningful-only* constraint goes further and restricts the parameter
itself to the subspace where it has semantic interpretation**, not
just keeps its downstream output in-range. The two stack: meaningful-
direction projection first, then box/monotonicity/freeze on what
remains.

This matches the language's architecture. `equality-and-
defuzzification.md` already separates the semantic subspace (where
LLM content lives, anisotropic, content cone) from the synthetic
subspace (canonical axes for bookkeeping — truth axis, number axis;
constructed-orthogonal-by-design). A learned parameter has a *type*
that says which subspace it inhabits; the constraint enforces that
the trained value still inhabits it after every Adam step.

- [ ] **Semantic-cone projection (TOP PRIORITY).** Project gradient
  updates onto the empirical content cone of the frozen LLM
  embedding. Implementation: precompute the top-K PCA directions of
  a representative corpus's `nomic-embed-text` embeddings (this is
  the "where meaning lives" subspace); at each Adam step, project the
  update vector onto that K-dim span before applying. Trained
  vectors then stay in the manifold where real concepts embed —
  they never drift into the undersymbolic void where the FV
  guarantees don't apply and the decode-back-to-meaning is
  unstable. K is a hyperparameter; start at K=50 and measure decode
  quality vs full-dim Adam. This is the load-bearing constraint —
  the others stack on top.
- [ ] **Canonical-axis projection.** For parameters typed as
  truth-axis scalars / number-axis scalars / any future canonical-
  axis-typed value, project the update onto exactly that single axis
  (or pair, for `complex` on `synthetic[0..1]`). Zero the orthogonal
  components. Cheap (single dot product + scale per step) and makes
  "this is a truth-axis value" a real invariant, not a convention
  that learned drift violates.
- [ ] **Codepoint-snap projection (for string-typed parameters).**
  When a learned vector is supposed to decode to a codepoint via the
  codebook (`strings.md`), project the update so the post-step value
  stays within the Voronoi cell of *some* valid codepoint. Without
  this, training a string-typed parameter is free to push the value
  into a region the codebook decodes ambiguously or to a junk
  codepoint. The cheap version: nearest-codepoint snap every K
  steps; the expensive version: project onto the union of small
  balls around each codebook entry continuously.
- [ ] **Anchor-ball constraint (init-from-meaning, stay-near-
  meaning).** Initialize each learned vector from `embed("anchor
  word")` for some known meaningful anchor; constrain updates to a
  δ-ball around the anchor. Trained value stays interpretable as
  "the meaning of anchor, slightly nudged." δ is a hyperparameter;
  too tight = nothing learned, too loose = drift. Measure δ vs
  decode quality on the constrain-train targets.
- [ ] **Box-constrained Adam wrapper.** A drop-in `BoxedAdam` that
  takes a `param_name → (lo, hi)` map and projects each step onto
  the box. Implementation is `param.data.clamp_(lo, hi)` after
  `optimizer.step()` — the simple part. The work is *wiring* the
  constraint source: the FV checker emits the box per learnable
  parameter as a side output of the obligation discharge.
- [ ] **Monotonicity-constrained Adam.** Some learned scalars
  (sharpening factors, defuzz rates) should monotonically increase
  during training (or decrease) — going the wrong way means the
  loss landscape lied. Add a `monotone={"increasing","decreasing"}`
  option that vetoes step directions opposite the declared
  monotonicity. This catches optimizer pathology that loss-only
  training silently absorbs.
- [ ] **Frozen-mask Adam.** Mark subsets of parameters as
  `frozen={...}` per-step — used for staged training (train `w`
  first, freeze, then train prototypes; or train prototypes first,
  freeze, then train `w`). Stage-B already does this implicitly;
  formalize it as a first-class optimizer option so the meta-tool
  can schedule staged training.
- [ ] **Constraint-source plumbing from FV checker.** Extend
  `fv_obligation_checker.py` to emit, per checked program, a
  `parameter_constraints.json` mapping each learnable name to its
  proved box + monotonicity + freeze schedule. The meta-tool reads
  this when scaffolding an experiment. Substrate-purity:
  constraints are produced symbolically (sympy) at compile-time, not
  on the runtime hot path.
- [ ] **Equivalence-guard composition with constraints.** The
  batched-vs-per-sample 10⁻⁴ guard must still pass *under* the
  constraints — a clamp that breaks equivalence is a bug, not a
  feature. The guard runs post-clamp every K steps (cheap; same
  shape as the existing equivalence check).
- [ ] **Findings doc per constraint type.** Each constraint type
  (box / monotonicity / frozen-mask) gets a
  `planning/findings/YYYY-MM-DD-constrained-adam-<type>.md` once
  measured on a real target, with the (free Adam vs constrained
  Adam) accuracy + wall-clock comparison.

### Automatic theorem proving for FV — extend the obligation checker beyond Kleene

`fv_obligation_checker.py` decides equivalence in the Kleene fragment
via polynomial identity, refuses on non-polynomial residuals, and
bounds branch ranges. To verify training outputs, the checker needs
to discharge ATP-style obligations the constrain-train step *targets*
("the trained classifier separates classes with margin ≥ M"; "the
trained gain `w` keeps the AND/NOT polynomial range inside [−1,+1]").

- [ ] **Obligation language.** A small DSL for trainable-program
  obligations: `range(param) ⊆ [lo, hi]`, `margin(classes) ≥ M`,
  `round_trip(bake_back) ≤ ε`, `monotone(param, direction)`. Each
  obligation has (a) a static verifier (runs at compile time on the
  symbolic polynomial), (b) a runtime monitor (runs at each
  training step; raises if violated), and (c) a final-pass certifier
  (runs on the trained value; produces a `parameter_certificate.json`
  bundled with the baked `.su`).
- [ ] **Polynomial-identity discharge for trained scalar bake-back.**
  When a Stage-B-style scalar bake-back happens (param `w` →
  literal `1.4339`), the baked `.su` reduces via
  `reduces_to_same_graph` to a known canonical form modulo `w`. The
  ATP step is mechanical: substitute the literal and check the
  resulting polynomial against the obligation. Cheap; first target.
- [ ] **External solver bridge — Z3 / dReal — bounded scope.**
  For obligations the polynomial-identity / range-bounder can't
  decide (real-arithmetic inequalities over composed connectives,
  margin obligations against trained prototypes), bridge to Z3
  (linear / nonlinear real arithmetic) or dReal (δ-decidable
  reals). Bounded scope: only the contract layer, never the
  substrate runtime. Refusal-on-timeout is acceptable — surfaces the
  obligation as undischarged rather than faking a discharge.
- [ ] **Certificate format + paper integration.** Each fully
  discharged training run emits a certificate file the FV paper
  (`paper/formal-verification/paper.md`, free to evolve) can cite as
  evidence. Format: which obligations, which checker discharged each,
  which timed out, sympy / Z3 / dReal version + seed. The paper
  drops "FV is an agenda" framing once a real certificate exists for
  a real training run.
- [ ] **Counterexample-driven retraining (CEGAR shape).** When the
  ATP step finds a counterexample (a point where the trained
  parameter violates an obligation), surface it back into the
  training data as a hard example. CEGAR-style loop: train → check
  → counterexample → retrain. Risk: divergence; guard with a max-
  iteration cap and a "no progress" detector.

### NN → code decompilation — generalize the Stage-B bake-back

Stage-B baked one scalar `w` back into `.su` as a numeric literal
(round-trip Δ ≈ 2×10⁻⁷). That is decompilation of a 1-parameter
"NN" — the simplest case. The generalization is: take a trained
neural fragment (matrix, multi-layer MLP, attention block) and
decompile it back into a Sutra program whose compiled graph is
behaviorally equivalent.

This is *not* "interpret the NN's weights" — that's a different
ambition. This is the inverse of constrain-train: if a Sutra program
compiles to a tensor-op graph that *behaves like* an arbitrary
trained NN fragment, then decompilation is *finding the Sutra
program* whose compile output matches the fragment.

- [ ] **Decompilation target: matrix → `.su` literal.** Given a
  trained matrix `M` (e.g. the `is_X` matrix from the constrain-train
  targets above), emit a `.su` matrix literal that the compiler
  reads back as `M` exactly (up to a documented ε). (The matrix-literal
  spec decision + surface **shipped 2026-05-28** — `matrix_literal` /
  `_VSA.matrix_from_rows`; this no longer blocks.) This is the smallest
  non-trivial decompilation — load-bearing for the matrix-valued
  constrain-train targets.
- [ ] **Decompilation target: MLP → composed Kleene rule.** Given
  a trained MLP that classifies via Kleene-style soft logic, decompile
  to a `&&`/`||`/`!` composition over learned `is_X` predicates.
  Decision procedure: enumerate composition trees up to depth D,
  compile each through the real codegen, score against the MLP's
  outputs on a probe set, return the smallest tree within ε. This is
  the FV-friendly fragment — every decompiled program lands inside
  the Kleene fragment the checker already decides.
- [ ] **Decompilation target: attention head → `select` + bind.**
  Single attention heads compute weighted sums that look a lot like
  `select(scores, values)` over a bound store. Probe: can the
  Yantra-calculator `select`-sharpness pattern decompile a real
  attention head (e.g. one head from a frozen small model) into a
  Sutra `select` + `bind` program? Honest non-claim: this is
  exploratory; "no" is a real possible outcome and a finding.
- [ ] **Verifiability of decompiled programs (where the ATP closes
  the loop).** A decompiled program is only useful if it (a) matches
  the source NN within ε on a probe set AND (b) is in a fragment the
  FV checker can verify. The ATP step from the previous sub-agenda
  is what makes (b) load-bearing. Decompiled programs that fall
  outside the Kleene + scalar-parameter fragment are flagged as
  "decompiled-but-unverified" rather than presented as equivalent.
- [ ] **Anti-claim discipline.** Do NOT advertise "decompile any
  NN into Sutra" as a paper claim. The honest claim is "for
  fragments inside the FV-decided language subset, decompilation
  produces source-recompilable equivalents." Outside that subset the
  result is a probe with measured similarity, not a proof. The
  `paper/formal-verification/paper.md` § "What we are not claiming"
  discipline applies here too.

### Cross-cutting: how these three threads compose

The meta-tool's decision template (above) grows three new fields per
target:
1. `fv_obligations: List[Obligation]` — what the trained parameter
   must satisfy.
2. `optimizer_constraints: BoxedAdam config` — which Adam constraints
   the FV checker emits.
3. `decompilation_target: Optional[NNShape]` — if the goal is to
   decompile a known trained NN fragment, what shape.

A constrain-train run thus produces: (trained values, certificate,
decompiled `.su` if applicable). The cumulative results table
gains certificate-status columns alongside the accuracy / wall-clock
columns. The FV paper's "agenda → done" sentence rests on the
existence of real certificates for real training runs.

---

## [This year] Self-improving-system roadmap — explain the requirements FIRST

`planning/self-improving-system-roadmap.md` is the consolidated long-term
agenda (reformatted 2026-05-28 from the 2026-05-27 Emma↔agent vision
conversation): **train everything trainable → accumulate a corpus →
train a formally-verified learned decompiler → close a legible
self-improvement loop.** Most of the finer-grained work it sits above is
already tracked in this file (§ "Constrain-train / NN→code decompilation",
§ "Formal verification") and in `queue.md`.

**Before executing the roadmap's steps, write out its requirements /
prerequisites here.** The roadmap describes the destination and the order;
it does not yet enumerate, as todo items, *what must be true or built
first* for each step to be startable. We should have some level of
explaining the requirements before barreling into the roadmap. Spell out,
at minimum:

- [ ] **Constrain-train harness generalization** — the Stage-1b per-category
  setups (single scalars, per-key values, per-role rotation matrices,
  Kleene coefficients) as a uniform, reusable harness, not one-off scripts.
  Prereq for the corpus. (Shipped instances to template from: `==` cosine
  scale `T`; defuzz β.)
- [ ] **FV-obligation-as-acceptance-criterion plumbing** — the bake-back
  check that re-runs the relevant FV obligation on each trained literal and
  refuses to bake on drift. Prereq for "every trained value is certified."
- [ ] **Corpus-generation infrastructure** — a fine-tuned Sutra code
  generator + the compile-filter pipeline (idiomatic preferred; anything
  that compiles is valuable; non-compiling = ~infinite loss). The roadmap
  calls this the immediate unlock.
- [ ] **Depth / dimension indexing** — how `(composition-depth, substrate-
  dimension)` is measured on the compiled graph so the decompiler family is
  well-defined. (Roadmap notes the *formalization* of layer-count can wait,
  but the *indexing scheme* is a prerequisite for per-cell training.)
- [ ] **Round-trip residual harness** — compile a candidate `.su`, compare
  its graph to a target tensor, report the residual norm as the certificate
  / error metric. Prereq for the first per-cell decompiler.

Each of these is a requirement gating a roadmap step; turning them into
concrete, verifiable queue items is the "explain the requirements" work.

## [This year] Go through every instruction in the self-improving-system roadmap

Once the requirements above are spelled out: **walk
`planning/self-improving-system-roadmap.md` end to end and act on every
instruction / step in it.** Stage by stage (Stage 1 general-purpose language +
trainable components + structural FV → Stage 2 build the corpus → Stage 3 the
program-recovery model → Stage 4 generalize generation/fine-tuning → Stage 5
the completely neural computer → Stage 6 self-training auditable computer),
atomize each into a concrete `queue.md` item (mirrored to the task tool), do
it, verify against ground truth, and check it off. This is the standing
pointer that keeps the roadmap from becoming a document nobody executes —
**Stage 1 is the current stage**, and its trainable-component list (1b) is the
near-term entry point.

## [This year] Make the loop-halting flag explicit

Sutra loops emit a **halting flag** — the signal a repeating loop raises to
say *"the output right now is NOT the final output,"* which on reaching its top
value means the program halts. Its intended shape is a **monotone function that
starts at 0 and rises to 1** (sigmoid-like, but it need not be a sigmoid — any
monotone 0→1 signal works); reaching 1 = halt. It is **not** meant to be a hard
step, which is how it is implemented today.

Status: the flag exists **implicitly** right now and is a real program
behavior — the codegen gates the halting loop forms (`do_while` /
`iterative_loop` / `foreach_loop`) via the runtime `heaviside` helper — but it
is underspecified and awkward to work with. Emma is not 100% certain on the
halting details; settle the design before changing the loop gate.

- [ ] Spec the halt flag explicitly: what it is (a program-emitted
  "not-final-output" / halt signal), its monotone 0→1 shape and polarity, and
  how a program emits/reads it. Reconcile with `recur` (non-halting loops have
  no such flag) and with the FV termination obligation.
- [ ] Decide whether/how the runtime gate moves from the hard `heaviside`
  helper to the intended monotone 0→1 flag without breaking termination — a
  function that actually *reaches* 1 gives crisp halt while staying soft on the
  way (unlike an asymptotic sigmoid that never quite arrives).

## [This year] todo.md follows the roadmap; make planning documentation more comprehensible

`planning/self-improving-system-roadmap.md` (the Stage 1→6 timeline) is the
spine this file follows. The rest of the planning documentation
(`planning/*.md`, `planning/sutra-spec/`, `planning/findings/`,
`planning/open-questions/`) should be pulled into a more comprehensible,
navigable shape that points back to the roadmap stage each piece supports, so
the agenda reads as one coherent plan rather than scattered docs.

- [ ] Build a planning index / map tying each planning doc to the roadmap
  stage it serves; surface it from `todo.md` and the roadmap so the planning
  surface is legible end to end.

---

## [ON HOLD — after GUI] Deprioritized, pull LAST (Emma 2026-06-11)

GUI is the top priority. The work-loop completes the GUI block (queue.md) first;
only after that does it attempt the items below, automatically, from this todo.
They are on hold, not cancelled.

### New-language transpiler frontends — ON HOLD
The full roadmap (the bet, priority order, per-language notes, Rust/WASM phases)
lives in "## [This year] Multi-language transpiler frontends" above, now banner-marked
ON HOLD. Pull order when GUI is done: **Scala → F# → Elixir/Erlang → Clojure →
Haskell → Rust → WASM** (F# is the cheapest — OCaml's ML cousin — and a defensible
first pick over Scala on effort/reward). Each is a multi-session build: new
`tree-sitter-<lang>` grammar → `sdk/sutra-from-<lang>/lower.py` → `.su` emission →
fixtures that compile AND run on the substrate (the OCaml harness bar). OCaml stays
the reference implementation; new frontends model on it, not `-ts`.

### OCaml `let rec` non-tail recursion — PROMOTED to the back of `queue.md` (Emma 2026-06-11)
No longer todo-end / on-hold: Emma moved this to the END of `queue.md` (after the GUI
block, ahead of the new-language frontends) as an aggressive build of **two** approaches —
**CPS + trampolining** and **Tree RNNs** — to be compared on the substrate. Full design:
`planning/exploratory/non-tail-recursion-on-the-substrate.md`. (Tail-recursive
accumulators already lower to a Sutra `while_loop`; the non-tail case is the target.)
