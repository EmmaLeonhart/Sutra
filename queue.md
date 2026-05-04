# Sutra — Work Queue

**This file is a queue, not a state snapshot.** It is the
**stuff being worked on right at this moment**. Finished work
lives in `git log` and `planning/findings/`; longer-horizon
work lives in `todo.md`.

See CLAUDE.md §"Workflow Rules" for how queue.md and the task
tool stay in sync.

## Active

**Sprint:** NeurIPS 2026 abstract submission (deadline May 4
2026 AOE — same day). Abstract-only step; full paper deadline
is May 6 AOE. The §Abstract has been rewritten to drop the
"honest negative results" framing, drop unit-test / smoke-test
counts (engineering signaling, not science), and lead with the
two empirical headlines (rotation 100%@k=8 across four
substrates including ESM-2; symbolic-rule training 40%→100%
end-to-end via PyTorch autograd). Two body cleanups removed the
word "honest" elsewhere (line ~1039 O(N) summary, line ~1351
remaining-work list). Numbers in the abstract verified against
committed JSON.

Open before submission:
- [ ] Confirm OpenReview profile is activated (non-institutional
  emails can take up to 2 weeks of moderation).
- [ ] Confirm OpenReview abstract field length cap by reading
  the actual submission form (handbook + call don't spell it
  out; expect ~250 words / ~1500–3000 chars).
- [ ] Pick primary area + keywords on the OpenReview form.
  Closest fits: "deep learning" + "language and multimodal
  models" (or "AI/ML for sciences" if the ESM-2 row is the
  pitch).

After abstract: queue.md flips back to systematic todo.md
pass. Full paper PDF + checklist due May 6 AOE.

### Done in this sprint (2026-05-01)

- **Claw4S close-out + clawRxiv kept as feedback channel.** The
  Claw4S competition is over. The clawRxiv CI/CD was briefly removed
  in commit `80f8c41` and restored shortly after — Emma's framing:
  "I'm keeping the CI/CD because it's a venue for feedback and
  visibility." None of the Claw4S-specific rules (lock-in on Strong
  Accept, dedup-bypass concerns, etc.) apply anymore. The five
  workflows + scripts + `paper/.post_id` are restored; `papers-ci.yml`
  push trigger is on, so each paper edit submits a new version to the
  supersedes chain and the review drops into `paper/reviews/`.
- **Y Combinator references cleared.** `Pre-YC` and
  `Pre-Anthropic-grant-app` priority levels collapsed into `This
  year` (commit `0f4a89a`).
- **Operators page** added (`docs/operators.md`, commit `b2dda77`)
  — root-definition / function-expansion form for every Sutra
  operator. Wired into the Theory-and-Paper nav.
- **Website audit** of the docs/ pages: loops.md rewrite for the
  declared-function loop design, paradigms.md / index.md /
  what-is-sutra.md / demos.md / vision.md / README.md updated for
  retired loop syntax, demo count corrections, broken-link fixes,
  bind-unbind.js header clarified, agent-routing affordance on the
  landing page, noscript fallbacks on the JS widgets. Commits
  `02c3d1f`, `2a6654c`, `333f670`, `e1eed83`, `b69e313`, `473f5b1`,
  `ca421fe`, `ff81d09`, `6a07a75`, `a705e5d`, `dfd4b27`.
- **todo.md tidy-up.** Smoke-test-failures section closed (both
  items resolved); Concurrency description fixed to declared-function
  loop form; Formula-simplification section dropped (no remaining
  pieces); Integer-class section relabeled; Control-flow Dynamic-
  foreach question answered by `foreach_loop`; "after Claw4S"
  deferrals removed. Commits `4b2bebc`, `6eb350a`, `51c6c67`,
  `bab0b91`.

- **Object encapsulation (steps 0, 0.5, 1)** — landed 2026-05-01.
  - **Step 0** — `SUT0144` validator rejects file-scope reads from
    method bodies (commit `7e1240b`).
  - **Step 0.5** — parser accepts method declarations inside class
    bodies, including `static intrinsic method`. ClassDecl gains
    a `methods` list (commits `9600fab`, `72b3534`).
  - **Step 1** — codegen routes `Class.staticMethod(...)` calls
    (regular -> mangled wrapper, intrinsic -> `_VSA.<name>`); the
    stdlib_loader picks up class-bodied entries under both bare and
    namespaced names (commits `b0f4e87`, `72b3534`, `ee9483a`).
  - **Step 2 (partial)** — three stdlib files migrated to the
    class-as-namespace shape: `math.su` (`class Math`), `numbers.su`
    (`class Numbers`), `memory.su` (`class Memory`), `embed.su`
    (`class Embedding`). Logic / similarity / vectors / rotation
    still on the legacy top-level shape (their bodies use retired
    loop syntax that wants care before migration).

### Open issues to address

- **SutraDB FFI tests fail locally because `sutra_ffi.dll` isn't
  built.** `tests/test_sutradb_embedded.py` raises
  `FileNotFoundError: sutra_ffi.dll not found at
  sutraDB/target/release/sutra_ffi.dll`. To fix locally, build the
  Rust crate: `cd sutraDB && cargo build --release -p sutra-ffi`
  (build prereq from `planning/semantic-corrections.md` §15). All
  other 245+ tests pass without this. If a CI run picks this up,
  the workflow needs the same `cargo build` step before the Python
  tests; the SutraDB-related tests should be skipped (not failed)
  when the dll isn't present, so unrelated PRs don't bounce.

### Next up

The remaining language-ergonomics steps (3-6) of the encapsulation
taxonomy are all real refactors — non-static method instance
dispatch, free-function file-level closure, instance fields, static
method state, object loops. None blocking; each shippable as a
separate session.

Other open work in `todo.md`:

- **Compile-time math approximation** — needs a substrate-pure
  `log`/`exp(E)` design before implementation; lookup-table approach
  failed (see the 2026-04-29 finding).
- **Rotation-hashmap capacity / Monte-Carlo experiments** — need GPU
  time and a real evaluation harness.
- **MCP server for docs** — real infrastructure piece.
- **Concurrency / learned-matrix binding / atman.toml backend config
  / transcendentals** — substantial parser+codegen work each.

## Pointers

- Longer-horizon agenda: `todo.md`.
- Pinned semantic corrections: `planning/semantic-corrections.md`.
- Deprecated spec (read-only reference): `planning/sutra-spec-deprecated/`.
- New spec dir + meta-failure note: `planning/sutra-spec/README.md`.
- Findings (dated): `planning/findings/`.
- Open design questions: `planning/open-questions/`.
- Hardwired assumptions in the demo path: `examples/todo.md`.
- Devlog (full history): `DEVLOG.md`.
