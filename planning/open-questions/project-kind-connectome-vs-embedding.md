## Project kind: connectome target vs embedding-space target

### The question

A Sutra project compiles to one of two qualitatively different substrates, and the tooling currently doesn't make that choice explicit:

- **Connectome target.** Compiles to an initial population state + drive schedule on a fixed anatomical W (FlyWire, Shiu LIF, someday a patient's connectome or neuromorphic chip). The substrate picks you — you don't choose rotation, you discover what the anatomy implements and fit your program to its eigenstructure. Operations like `bundle` are drive-sum on disjoint pops, `bind` is a spike-count product, `rotate` is "whatever the wiring does under iteration." Fundamentally *biological* and *spatial-in-hardware*.

- **Embedding-space target.** Compiles to trajectories and operators over a learned manifold (mxbai, OpenAI text-embedding-3, ModernBERT, whatever). You pick the substrate and you pick the rotation — the manifold is dense, the ops are cheap linear algebra, and the demo programs look like "move from A to B through C." The latent space is spatial-in-semantics, not spatial-in-hardware. Compile target is less obvious: it might be a runtime that emits embedding-space queries against a vector DB, it might be a sequence of LLM prompts with intermediate embedding readouts, it might be a standalone VM over fp32 tensors. This is the side that is *not yet designed* — connectome-target has concrete backends (Shiu, Brian2), embedding-target has none.

Both share the same fundamental VSA algebra (`planning/sutra-spec/11-vsa-math.md`) and the same surface syntax, but the todos, demo programs, stdlib, and backend expectations diverge hard enough that a single `sutra-project.toml` without a target field is under-specified.

### What we currently do

Implicit split — no manifest, no template, no IDE prompt:

- `fly-brain/`, `fly-brain-paper/`, `planning/findings/shiu-*`, and every `real_rotation_*.py` / `shiu_*.py` script are de-facto connectome-target.
- `sutra-paper/`, the `examples/*.su` programs, and the SutraDB work are closer to embedding-target in spirit but don't yet run on an embedding-space substrate end-to-end.
- The `sdk/sutra-compiler/` has one pipeline with connectome-shaped assumptions baked in at the codegen boundary (`EmbedExpr`, `UnsafeCastExpr` are `CodegenNotSupported` — see `planning/open-questions/codegen-v1-feature-coverage.md`).

### Why the current choice has force

- One compiler, one spec, one surface syntax. Adding a target axis risks splitting the dialect and reintroducing the "two languages with the same name" failure mode the Sutra pivot was meant to avoid.
- Connectome-target is where the paper results are, and the paper deadline (2026-04-20) dominates. Embedding-target can stay implicit until after the Claw4S submission.
- The actual code surface that *differs* by target today is small — mostly the backend / substrate-executor, not the frontend.

### Why the alternative has force

- A YC demo is unlikely to run on a connectome. It needs an embedding-space runtime on commodity hardware, with demo programs that visibly move across the space (the one thing connectome-target can't show in a pitch). See `todo.md` §[Pre-YC] Future Goals — "Get Sutra running on normal hardware first."
- The `todo.md` for a connectome project (wiring cleanup, FlyWire loader, Brian2 substrate parity, Shiu conditional sweeps) looks nothing like the todo for an embedding project (manifold choice, rotation operator, vector-DB backend, trajectory visualization). Keeping both in one `todo.md` is already painful and will get worse.
- An IDE / solution prompt ("New Sutra Project: connectome or embedding-space?") maps onto a real difference the user experiences, and lets the compiler pick different codegen paths, different stdlib, different examples — without forcing them into one over-general framework.
- The `papers-ci.yml` split already embodies this: `sutra-paper/` and `fly-brain-paper/` are separate papers precisely because the story, the audience, and the demo shape differ. Tooling lags the paper split.

### What we'd need to decide to close

1. **Manifest shape.** Add `target = "connectome" | "embedding-space"` to a `sutra-project.toml` (file doesn't exist yet — would be the first version of it). Define which other fields the manifest carries: substrate handle (e.g. `shiu` / `brian2-hemibrain` / `mxbai-1024d` / `openai-text-3-small`), dimensionality, seed, stdlib version.
2. **Template layout.** Under `sdk/templates/`: `connectome-project/` (with `fly-brain`-shaped starter, Shiu substrate config stub) and `embedding-space-project/` (with a laptop-runnable embedding-space substrate stub, demo "move from A to B through C" program). `sutra new --target connectome|embedding` instantiates one.
3. **IDE / solution plumbing.** The VS Code extension and IntelliJ plugin need a "New Project" action that writes the manifest. Pick which one gets the flow first (probably VS Code — smaller surface, faster iteration). Discover existing manifests on workspace open and expose the target in status bar / tool window so the user always knows which kind of project they're in.
4. **Split todo layout.** Either (a) introduce `fly-brain-paper/todo.md` and `sutra-paper/todo.md` as target-specific long-term agendas with the repo-root `todo.md` keeping only cross-cutting meta items, or (b) add target-tags (`[connectome]`, `[embedding]`) to existing priority-level sections. (a) matches the paper-repo split; (b) keeps one file. Not obvious which wins.
5. **Shared core boundary.** Decide which of `planning/sutra-spec/*.md` are target-independent (VSA axioms, `is_true`, loop semantics) vs target-specific (substrate candidates, operation implementation). The current spec is mostly target-independent by default, but §19-substrate-candidates and parts of §02-operations drift into connectome assumptions. If we split targets at the tooling level, the spec needs a small reorganization to match — otherwise the embedding-target backend has to "implement against" a spec that was quietly written for connectomes.
6. **Embedding-target backend prototype.** We don't currently have one. A minimal version — numpy-backed VSA over a frozen mxbai embedding space, with `bundle`, `bind`, `similarity`, `rotate` (pick: permutation-based or learned linear), and one demo program — would clarify whether target=embedding is easy or hard. This is the item that actually unblocks everything else here, and it's YC-shaped rather than paper-shaped, so it fits the Pre-YC bucket.

### Priority

Below the Claw4S paper deadline (2026-04-20), above the bulk of `[This year]` items — this is an active gap the YC pitch will trip on. Tracked in `todo.md` under `[Pre-YC] Future Goals`.
