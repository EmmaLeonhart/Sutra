# IDE Architecture

Akasha's IDE is not optional tooling. Because the language has long-range semantic dependencies that no single source file can capture (see [06-runtime.md](06-runtime.md)), the IDE is part of the language — the same way TypeScript's type checker is a second interpreter running alongside the code. This document describes the vision for that IDE.

Status: **v0.2 static additions on top of the v0.1 scaffold under `sdk/intellij-akasha/`.** v0.1 gave us file type registration, hand-written lexer, syntax highlighter, color settings page, brace matcher, commenter, quote handler, keyword/primitive/builtin completion, live templates ported from the VS Code extension, and an external annotator that shells out to `python -m akasha_compiler --json`. v0.2 adds a persistent `AkashaSettings` service and a proper **Settings → Tools → Akasha** `Configurable` that replaces the env-var-only v0.1 configuration (env vars remain a fallback), JUnit 4 unit tests for the hand-written lexer covering every token category, and a design-only Kotlin interface anchor for the MCP tool surface named in §"Minimum Agent Workflows" below (`AkashaMcpSurface` + stub). Everything beyond that — real PSI, the MCP implementation, visualizers, debugger, solution system — is still design-only.

## Non-Goal: Generic Editor With Akasha Support

Akasha is explicitly *not* targeting a VS Code extension as its primary development environment. Two reasons:

**Extension conflict.** VS Code was built as a text editor that grew into an IDE; the extension model was bolted on. Extensions share the same process space with no real sandboxing, and language servers in particular fight over file types. For a language whose tooling includes a running MCP server, a local vector database, an embedding model, and a spatial visualizer, sharing a process with arbitrary other extensions is not viable.

**API friction.** The VS Code extension API is large and under-documented in the places that matter for language tooling. Language Server Protocol gets you syntax highlighting and basic intellisense but not integrated debugging of embedding operations or a persistent visualizer pane.

A community-built TextMate grammar or VS Code extension is fine as a later convenience — but the **reference** development environment is its own IDE.

## Platform: IntelliJ Platform

The reference IDE is built on the **IntelliJ Platform** — the Apache-licensed Java/Kotlin base that JetBrains uses for IntelliJ IDEA, PyCharm, CLion, Rider, RustRover, etc. Third-party languages have built on the same platform; it is a well-trodden path.

Why IntelliJ Platform:

- **Built-in MCP server support.** JetBrains ships an MCP server as part of IntelliJ IDEA, exposing the PSI tree, project model, and editor state to external AI agents. This is the single most important reason to pick IntelliJ. **AI agents will write most Akasha code** — the language's long-range semantic dependencies and fuzzy vector primitives are exactly the kind of thing humans will delegate — and IntelliJ's MCP integration gives us agent authoring out of the box, not as a project we have to build. See the dedicated section below.
- **Proper plugin isolation.** Plugins can't accidentally stomp each other the way VS Code extensions routinely do. For a language where the "plugin" is really the entire runtime, isolation is load-bearing.
- **Language support APIs.** PSI (Program Structure Interface), inspection framework, refactoring support, inlay hints — the infrastructure needed for semantic tooling is already there, *and* the PSI tree is what the IntelliJ MCP server exposes to agents, so a good PSI implementation directly translates to good agent tooling.
- **Integrated debugger framework.** The debugger UI and stepping model are already wired; Akasha only has to implement the domain-specific parts (stepping through embedding operations, inspecting intermediate vectors).
- **Mature and documented** relative to VS Code internals.

Tradeoffs accepted: Java/Kotlin under the hood, large platform with a learning curve. These are acceptable given the alternative (fighting VS Code's extension model forever).

The IDE will be open source.

## UX Model: Visual Studio, Not Jupyter

The inspiration for the developer experience is Visual Studio / C#, not Jupyter.

**Why not Jupyter.** Notebooks are inherently sequential and stateful in non-obvious ways. Cells depend on each other in hidden order; scientists tolerate it, engineers do not. For a language that wants to be taken seriously as an engineering tool — and that has to survive contact with bioinformatics and connectome labs that have already been burned by notebook-driven workflows — Jupyter signals "research toy."

**Why Visual Studio.** Concrete features that map well to Akasha's model:

- **Solution file with multiple projects.** Separation of concerns lives at the *project* level, not the file level. Each Akasha project within a solution is a clean unit: one project for embedding operations, one for models, one for visualizations, with explicit dependency arrows between them.
- **Libraries as first-class citizens.** A NuGet-equivalent package ecosystem from day one. Embedding-space programming is inherently compositional; you will be combining spaces, models, and transformations constantly, and the package system needs to assume that.
- **Inline error highlighting before you run.** The compiler's probing phase (see [07-empirical-initiation.md](07-empirical-initiation.md)) can surface "this space doesn't look well-formed enough for reliable results" as a pre-flight inspection, not a runtime crash.
- **Integrated debugger** that feels the same way Visual Studio's does — step through embedding operations, inspect the intermediate vectors, set conditional breakpoints on similarity thresholds.
- **Output panel with compilation results** that updates on save, not on explicit run.

## The Bundled Vertical Stack

A single installer ships the entire stack. No configuration required to run hello world.

What's bundled:

| Component               | Default                                        | User-replaceable? |
|-------------------------|------------------------------------------------|-------------------|
| Language + compiler     | Akasha reference implementation                | No                |
| Vector database         | Lightweight embedded DB ("SQLite of vectors")  | Yes               |
| Embedding model         | Small local model (quantized sentence transformer class) | Yes       |
| Embedding map / corpus  | Small curated default corpus                   | Yes               |
| 3D visualizer           | Linear projection onto user-chosen composite basis, plus optional UMAP/t-SNE | Yes |
| MCP server              | Local, auto-started by the IDE                 | Yes               |
| Project system          | Solution-based multi-project layout            | No                |

**The vector-database problem.** Most vector databases assume production infrastructure. Pinecone, Weaviate, Qdrant all assume a server context; getting a beginner to spin up one of those before they can print "hello world" is the same as asking them to set up PostgreSQL first. Akasha needs the SQLite equivalent — embedded, zero-config, just there. This is a required component of the stack; it may well become its own project.

**The zero-config default.** If the user doesn't choose an embedding space, Akasha picks one of the bundled ones and keeps going. This is the single most important affordance for learning — the onboarding friction of modern ML tooling is what keeps embedding-space programming out of reach for most people.

**The default embedding map.** This is the hardest part to bundle well, because the meaningful structure in the space depends on what's *in* the database. The default is a small curated corpus chosen to make the space feel navigable rather than to be comprehensive.

## Embedding-Space Visualizer as a Core Pane

Embedding spaces are mathematically high-dimensional, but humans need a handle on what they are navigating. The IDE ships with a visualizer pane that shows a 3D projection of the current embedding space, with the vectors your code is currently touching highlighted.

Not because the 3D projection is mathematically complete — it obviously isn't — but because seeing where your code is operating in the space is the single most useful debugging affordance for this paradigm. This is genuinely unprecedented as a development experience; no existing IDE has a first-class "here is your computational substrate, rendered" panel.

### Default projection: 3D hyperplane with user-chosen composite-vector basis

**The default is not UMAP or t-SNE.** It's a linear projection onto three composite vectors the programmer (or an agent) picks. Each axis is itself an Akasha expression — `male - female`, `king - peasant`, or any other bound name — and the visualizer simply renders the dot products. Three dot products per point, trivially redraws at 60fps, degrades gracefully to 2D with two axes.

Why this beats the usual dimensionality-reduction pick:

- **Stable under edits.** UMAP and t-SNE reshuffle whenever points get added or removed, which is disorienting when your code is mutating the space. A linear projection onto user-chosen vectors stays put across edits.
- **Semantically meaningful.** Picking basis vectors out of the space itself turns the visualizer into a navigable semantic coordinate system you can reason about in the same vocabulary as your code — not just a pretty picture. This matches Akasha's "computation is geometry" pitch.
- **Composable with code.** The axes are first-class Akasha expressions. Code can reference the visualizer's current basis; the visualizer can bind to names computed by the code. UMAP can't do that — its projection isn't a first-class object.
- **Agent-visible.** Because the basis is just three vectors, the MCP surface exposes it as three `vector` values plus a `project(vector) -> (x, y, z)` tool. Agents can set the basis, query projected coordinates, and animate between bases the same way humans can.
- **Cheap.** Two (or three) dot products per point. Matters because JCEF/Swing performance with large point clouds is an open empirical question this design has to survive.

**2D vs 3D.** 3D with three composite vectors is the default because humans navigate 3D spatial scenes well, and the third axis earns its keep. 2D is a supported mode (pick two of the three) for cases where the third basis vector is genuinely absent.

**UMAP and t-SNE remain available** as alternative projections for cluster-structure exploration, but they are *not* the default. Switching projection mode is a dropdown, not a language-level concern.

### Caveat: non-algebraic tier doesn't project linearly

Composite-basis projection works cleanly on the **algebraic tier** (see [02-operations.md](02-operations.md)) — `bind`, `unbind`, `bundle` produce points and the operations between them become visible lines. Non-algebraic results (`snap`, `cone`, `hop`) project fine as points but the *operations* that produced them do not map to straight lines in the chosen basis. The visualizer should surface this distinction — dotted lines for non-algebraic transitions, solid lines for algebraic ones — so users are not misled into reading geometric continuity where none exists.

### Fly-brain visualizer

A second visualizer pane, tuned specifically to the fly-brain substrate, is planned as a tiered deliverable alongside the embedding-space pane. See the dedicated planning doc at [`planning/fly-brain-visualizer.md`](../fly-brain-visualizer.md) for the topological-vs-anatomical split, the hemibrain/FlyWire mapping research it depends on, and the staged v0.1–v0.3 rollout.

## MCP Architecture: Two Servers, One IDE

Akasha's MCP story is the hinge of the whole IDE design. There are actually **two** MCP servers involved, and they serve different audiences:

1. **The IntelliJ-provided MCP server** (shipped with IntelliJ IDEA) — exposes the IDE itself to AI agents: PSI tree, open files, project model, diagnostics, run configurations, debugger state. This is how agents *write* Akasha code.
2. **The Akasha runtime MCP server** ([06-runtime.md](06-runtime.md)) — exposes the embedding space itself: ANN lookups, entity resolution, cone/snap/hop primitives, the codebook. This is how Akasha code *runs*.

Both run locally inside the IDE process. The IDE is the place where agent tooling and language runtime meet.

### Why This Matters: AI Agents Are The Primary Authors

A key design assumption: **AI agents will write most Akasha code**, not humans. This isn't a hedge, it's the base case. Akasha has long-range semantic dependencies, fuzzy vector primitives, and an "instruction set" that is literally the geometry of a particular embedding space — the kind of code where human developers will instinctively delegate to an agent and review the output rather than write it by hand. The same forces that make Akasha need an IDE at all (semantics too rich for a single file to capture) also make it a language that rewards agent authoring.

This inverts the usual "IDE with optional AI help" framing. Akasha's IDE is an **agent-first authoring environment** where human editing is one of several input paths, not the default one.

Concrete implications for the IDE:

- **Every feature must be agent-accessible.** If a human can do it through the UI, an agent must be able to do it through the MCP server. No human-only affordances.
- **The MCP surface is the primary API.** UI elements are thin wrappers over MCP calls; the MCP tool definitions are effectively the IDE's public interface, and they get the same care a human-facing API would get.
- **Diagnostics and inspections are agent feedback channels.** When the compiler's empirical-initiation probe (see [07-empirical-initiation.md](07-empirical-initiation.md)) says "this embedding space is noisy on predicate X," the agent needs to see that the same way a human sees a red squiggle. Structured, queryable, streamable.
- **Debugger state is agent-visible.** Stepping through embedding operations is most useful when the agent can observe the intermediate vectors and decide what to try next, not just when a human is staring at the screen.
- **The visualizer pane has a queryable backing model**, not just a rendered bitmap. An agent should be able to ask "what's near this vector?" and get structured data, with the UI pane as a rendered view of the same data.

### Minimum Agent Workflows The MCP Server Must Support

"Vibe coding" Akasha — i.e. an agent iterating on code without a human in the tight loop — is an explicitly supported workflow, not an afterthought. Two agent loops in particular must be first-class, and both of them depend on MCP surfaces that most IDEs don't expose:

**1. The syntax-check loop.** The agent writes or edits Akasha code, asks the MCP server "is this well-formed and does it type-check against the current embedding space?", gets structured diagnostics back, and iterates. Required MCP tools:

- `akasha.parse(source) -> { ast, parse_errors }` — pure syntactic check, no space access needed
- `akasha.check(source, space_ref) -> { type_errors, probe_warnings, unresolved_entities }` — full semantic check against a target embedding space, including the empirical-initiation probe results
- `akasha.diagnostics(file) -> [...]` — same structured diagnostics the red-squiggle UI layer consumes, queryable at any time

The point of this loop is that the agent should almost never need to *run* Akasha code just to find out if it compiles. Syntax and type feedback is cheap, fast, and side-effect-free.

**2. The prototype-build loop.** The agent has a rough goal ("build an embedding-space classifier for these fly-brain cell types"), scaffolds a small Akasha program, compiles it, runs it against real vectors, inspects the output, and iterates. Required MCP tools:

- `akasha.scaffold(template, params) -> { project, files }` — bootstrap a new solution/project skeleton from a template, so the agent isn't rebuilding the project layout from scratch every time
- `akasha.compile(project) -> { artifact, compile_errors }` — drive the compiler directly, without going through the UI's run button
- `akasha.run(artifact, input) -> { output, intermediate_vectors, trace }` — execute a compiled artifact with instrumented output, so the agent gets not just the final vector but the intermediate steps, the S1/Akasha routing decisions, and any empirical-initiation corrections that fired
- `akasha.inspect(vector) -> { nearest, cone, magnitude, labels }` — query the runtime MCP server for "what does this vector mean in the current space," which is the agent's equivalent of a human dragging a point in the visualizer

These two loops together are the minimum viable contract for agent authoring. Until both loops close cleanly over MCP, the IDE is failing its primary user.

**Design rule:** if the IDE ever gains a feature that a human can use but an agent cannot access over MCP, that's a bug. File it against the IDE.

### IDE-Hosted Runtime MCP Responsibilities

The Akasha runtime MCP server, hosted inside the IDE, specifically:

- Resolves long-range semantic dependencies for the code currently being edited
- Provides ANN lookups against the local vector database for non-algebraic operations (snap, cone, hop)
- Feeds the visualizer pane with "what's near the vector under the cursor"
- Handles entity resolution — when the same surface form maps to different vectors depending on context, the IDE needs to *know*, and the MCP server is how it knows
- Exposes the probing results from empirical initiation as structured diagnostics

The S1 cache (see [06-runtime.md](06-runtime.md)) lives inside the IDE process during development so that recompiling doesn't blow away everything that has been resolved. Agents benefit from this cache the same way humans do — "this binding was already resolved to that vector in the last edit" is valuable context regardless of who is asking.

## Logits as an Escape Hatch

There is a research-track option to skip the vector database entirely: operate directly on a decoder-only model's logit distributions, using the model itself as the embedding space. Logits already form a high-dimensional space with exploitable geometric structure; the logit-lens literature (Nostalgebraist 2020, Dar et al. 2022, Logit Prisms 2024) shows that this is a real substrate, not hand-waving.

This is *not* the default path because it requires a running LLM locally, which is a much bigger dependency than the bundled lightweight vector DB. But it is kept as a first-class alternative execution mode — the same Akasha source should compile against either substrate, the way [07-empirical-initiation.md](07-empirical-initiation.md) already describes for conventional embedding models.

## Open-Source Community Strategy

The expected division of labor once the core ships:

- **Core language, compiler, IDE platform** — maintained by the Akasha team.
- **Bioinformatics libraries** — contributed by bio people, who are already used to writing their own tooling and run almost entirely on community-maintained packages. The fly-brain result (see [../fly-brain-architecture.md](../fly-brain-architecture.md)) is the hook that gets connectome researchers curious enough to try it.
- **LLM-integration libraries** — contributed by ML people once the logit-space execution mode is stable.
- **Dev-tooling polish** — contributed by whoever loves dev tooling enough to improve the IDE beyond the reference implementation.

The core has to be solid enough that early contributors aren't fighting the language itself, and the docs have to be good enough that smart people can onboard without talking to the author. Both are prerequisites for the community dynamics to work.

## Open Questions

- **Which lightweight vector DB?** Pick an existing embedded option (SQLite-vec, LanceDB embedded mode, sqlite with pgvector-style extension) vs. build the "SQLite of vectors" from scratch as its own project.
- **Which default embedding model?** Needs to be small, CPU-runnable, and non-normalized (see [19-substrate-candidates.md](19-substrate-candidates.md) for the non-normalization requirement).
- **How is the solution file structured?** Borrow Visual Studio's `.sln` format, define a new one, or use something like TOML.
- **What does "stepping through an embedding operation" actually look like?** The debugger UI is clear in the abstract but the concrete stepping model — per vector? per binding? per cone traversal? — needs design.
- **Can the IntelliJ Platform render the visualizer pane efficiently?** Swing/JCEF performance with large point clouds is still open even for the cheap composite-basis projection. JCEF + three.js is the obvious first experiment; native Swing with a batched renderer is the fallback.
- **How are the default basis vectors chosen when a programmer hasn't picked one?** Candidates: first three PCA components of the loaded corpus, three curated "semantic anchor" vectors shipped with the default map, or blank until the user picks. The visualizer has to have *something* to render on a cold open.
- **Agent/human parity enforcement.** How is the "every feature is MCP-accessible" rule mechanically enforced? Code review, automated audit that diffs UI actions against MCP tools, or a test suite that drives the whole IDE via MCP and asserts coverage?
- **Scaffolding templates.** What's the starter set of `akasha.scaffold` templates for the prototype-build loop — classifier, similarity retriever, cone-traversal demo, fly-brain substrate program?

### Resolved

- **TextMate grammar as a day-one deliverable** → shipped. Lives at `sdk/vscode-akasha/syntaxes/akasha.tmLanguage.json` and is the source the IntelliJ plugin's hand-written lexer was ported from.
- **Default visualizer projection** → linear projection onto three user-chosen composite basis vectors, not UMAP/t-SNE. See the "Embedding-Space Visualizer" section above.
