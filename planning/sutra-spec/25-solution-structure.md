# Solution Structure

> **Status: planning document for v0.0.1.** Nothing in this document describes currently shipping behavior. v0.0.1 does not exist yet — it is the next planned language cut, on the order of two weeks out as of this writing. The current toolchain is v0.0.0 and v0.0.0 has no concept of solutions. This file is the design target the v0.0.1 work will implement against, not a description of anything you can run today. When v0.0.1 actually ships, this status banner comes off and the doc becomes normative.

A *solution* in Sutra is a complete compilable unit on disk: a workspace `atman.toml`, zero or more member projects, and the `.su` source files those projects own. This document describes what a well-formed solution looks like, how version pinning works, and what the compiler does with source trees that **don't** have a workspace file.

**Solutions are a v0.0.1+ concept. They do not exist in v0.0.0, and v0.0.1 does not exist yet** — it is the next planned cut, roughly two weeks out as of this writing. The current reference compiler in `sdk/sutra-compiler/` is the v0.0.0 toolchain and it operates directly on loose `.su` files; it was spaghetti-coded to the architecture of the FlyWire connectome before the workspace model existed, so it doesn't need a solution to run and it bakes a single substrate into the codepath. That is the whole reason solutions need to exist: **v0.0.1's solution structure is what lets a project specify a substrate other than FlyWire.** The `substrate` field on a project `atman.toml` (per [`22-workspaces.md`](22-workspaces.md)) is how a v0.0.1 solution says "this project targets silicon" or "this project targets a logit-space substrate" instead of inheriting v0.0.0's implicit fly-brain assumption.

`sdk/sutra-compiler/sutra_compiler/workspace.py` and `examples/workspace/` exist in the repo as **pre-implementation scaffolding** for the v0.0.1 surface; they are not part of what v0.0.0 promises and they are not yet wired into the compiler's default path. Reading this document as a description of v0.0.0's behavior is a category error — it describes what v0.0.1 will look like, and how v0.0.0 trees fit into that world once the cutover happens.

The workspace-file schema itself lives in [`22-workspaces.md`](22-workspaces.md); the surface grammar the source files must conform to lives in [`24-grammar.md`](24-grammar.md). This document ties the two together and adds the version-pinning policy.

## The three shapes a solution can take

From v0.0.1 onward, Sutra will recognize three levels of structure, in increasing order of formality:

### 1. Loose `.su` files (no `atman.toml`)

A directory containing one or more `.su` files with **no `atman.toml` anywhere up the tree** is a *loose source tree*. This is the only shape v0.0.0 knows about. The v0.0.0 reference compiler compiles loose trees directly, with no awareness of workspaces, projects, or dependencies — any `.su` file is a standalone unit.

Under v0.0.1 the same shape still works, but is now *explicitly* labeled development mode:

- There is no workspace, no project, no dependency graph.
- Source files cannot depend on each other across project boundaries (because there are no projects).
- The language version is implicitly **v0.0.0** — see §"Version pinning and v0.0.0" below.
- The v0.0.1+ toolchain warns that the tree is at v0.0.0 and is developer-only.

Everything under `examples/`, `fly-brain/`, `sutraDB/`, and `sutra-demo-program.su` is loose `.su` source at v0.0.0 today, and the reference compiler compiles it. Those files stay loose until someone explicitly bumps them to v0.0.1 by adding an `atman.toml`.

### 2. Single-project solution *(v0.0.1+)*

A directory with an `atman.toml` whose top-level table is `[project]` is a *single-project solution*. There is no workspace wrapper; the project is its own root. This is the minimum viable shape for a solution. v0.0.0 does not support this form — the v0.0.0 reference compiler ignores `atman.toml` entirely and just reads `.su` files.

```
my-analysis/
├── atman.toml          # [project] table
├── main.su
└── helpers.su
```

### 3. Multi-project workspace *(v0.0.1+)*

A directory with an `atman.toml` whose top-level table is `[workspace]` is a *workspace solution*. It enumerates member projects, each of which has its own `atman.toml` at its root. The full schema, resolution algorithm, and dependency model are in [`22-workspaces.md`](22-workspaces.md). v0.0.0 does not support this form.

```
embedding-pipeline/
├── atman.toml                # [workspace] table
├── corpus/
│   ├── atman.toml            # [project] table
│   └── main.su
└── similarity/
    ├── atman.toml            # [project] table
    └── main.su
```

`examples/workspace/` is the reference example. It is v0.0.1 scaffolding in a v0.0.0 repo — the `sutra_version = "0.2"` string in that file is an artifact of earlier draft work and should be ignored; the actual first version that honors the schema will be v0.0.1.

## Version pinning and v0.0.0

Every compiling Sutra solution pins a language version via the `sutra_version` field of its root `atman.toml`. The compiler uses that field to choose which grammar variant and which standard-library surface to expect; see [`24-grammar.md`](24-grammar.md) §"Status and versioning" for the grammar-side policy.

### What each version class means

| `sutra_version` | Status | Compilation under v0.0.0 toolchain (today) | Compilation once v0.0.1+ exists |
|---|---|---|---|
| (no `atman.toml`) | v0.0.0 implicit | accepted — this is the entire repo today, loose files only | development mode only, opt-in; may stop working at any future release |
| `"0.0.0"` | explicit v0.0.0 | the `atman.toml` is ignored; the compiler just reads `.su` files | same as "no `atman.toml`", with the version made explicit |
| `"0.0.1"` | first solution-aware release | n/a — v0.0.0 doesn't know how to read `atman.toml` | compiler honors the workspace/project schema, resolves dependencies, compiles in topological order |
| `"0.0.2"` and onward | subsequent releases | n/a | each release may change grammar and standard library; pinning is how a solution says which one it was written against |
| newer than installed toolchain | error | n/a (v0.0.0 has no version gate) | rejected with diagnostic `SUT2003` |

### Why v0.0.0 is special

**v0.0.0 is the pre-formalization development version.** It predates the solution concept, predates `atman.toml`, and predates any formal versioning at all. It is what the current repo runs on: a spaghetti-coded reference compiler that reads `.su` files directly and ignores everything else. The label exists so we have a name for "the thing that's running today" that isn't lying about being a stable release.

**Everything in this repo is v0.0.0 today.** Every `.su` file under `examples/`, `fly-brain/`, `sutraDB/`, `sutra-demo-program.su`, and anywhere else in this tree is v0.0.0 source. The reference compiler in `sdk/sutra-compiler/` *is* the v0.0.0 toolchain, and it must keep accepting v0.0.0 — that's the only job v0.0.0 has. The grammar in [`24-grammar.md`](24-grammar.md) is the v0.0.0 grammar. Nothing in this policy is meant to break the code that already runs.

The contract around v0.0.0 is about what happens **after v0.0.1 is cut**, not about today:

1. **v0.0.0 cannot normally compile under a post-v0.0.1 toolchain.** Once v0.0.1 ships, a solution-aware `sutrac` will refuse to build a v0.0.0 source tree by default and will direct the user to pin a real version. A best-effort development mode (see §"Development mode" below) keeps the v0.0.0 path alive as opt-in behavior, but it stops being the default the moment a version-pinning alternative exists.
2. **v0.0.0 is not guaranteed to survive any future grammar change.** Breaking changes between v0.0.0 and v0.0.1 are explicitly allowed — v0.0.1 is where the grammar first becomes something we are willing to *call* a version.
3. **v0.0.0 will not always be supported.** At some point after v0.0.1 is cut the compiler will drop the development-mode path entirely. Solutions still on v0.0.0 at that point will have to be migrated.
4. **Do not ship v0.0.0 code to anyone who expects a stable build.** Any solution you expect a second person, a CI pipeline, or a downstream dependency to consume once v0.0.1 exists **must** pin a real `sutra_version` in its `atman.toml`.

Rule of thumb: **today, v0.0.0 works; tomorrow, v0.0.0 is the explicit "I have not pinned a version" signal.** The grammar document this policy references is the v0.0.0 grammar, and it compiles.

### Development mode

Because v0.0.0 is where the language actually lives right now, the v0.0.1+ compiler will provide a **development mode** for loose `.su` files and explicit-v0.0.0 solutions. Development mode:

- Accepts the grammar as implemented by the v0.0.0 reference compiler with no version gate.
- Emits a warning on every run, prefixed with the file path, reminding the user that the source is at v0.0.0.
- Does **not** promise that the same input will be accepted in any future toolchain.

Until v0.0.1 is cut, development mode *is* the compiler — there is no gate to bypass because there is no stable version to fall back to. The `sdk/sutra-compiler/` reference toolchain parses `.su` source unconditionally and ignores any `atman.toml` it finds, which is the correct v0.0.0 behavior. Once v0.0.1 exists, development mode will become opt-in via an explicit `--dev` flag or `SUTRA_DEV_MODE=1` environment variable, and the default behavior against a loose tree will be to refuse with a diagnostic pointing here. Implementing that gate — along with actually honoring `atman.toml` at compile time — is the v0.0.1 work, not the v0.0.0 work.

## File conventions

### `.su` source files

Source files use the extension `.su`. The file is a `module` per [`24-grammar.md`](24-grammar.md) — a sequence of top-level items with no explicit module declaration.

A `.su` file is one of two things, determined by its contents, not by syntax or filename:

- An **object declaration**, if its top-level items are predominantly `method` declarations. The file acts as the body of a type; see `examples/01-objects-and-methods.su`.
- An **executable file**, if its top-level items are a mix of statements, variable declarations, and `function` declarations. The file runs top-to-bottom when loaded; see `examples/06-executable-file.su`.

The language does not force either shape. A single-file solution that just runs is as legitimate as a multi-project workspace with a formal object model.

### `atman.toml`

Every project and every workspace is named by a file called literally `atman.toml` at its directory root. The name is fixed by convention — there is no `.akproj` / `.aksln` discovery heuristic. The parser distinguishes workspace files from project files by the top-level table (`[workspace]` vs `[project]`).

A minimal single-project `atman.toml` at v0.0.1:

```toml
[project]
name = "my-analysis"
entry = "main.su"
sutra_version = "0.0.1"
```

A minimal workspace `atman.toml` at v0.0.1:

```toml
[workspace]
name = "embedding-pipeline"
sutra_version = "0.0.1"

[[workspace.member]]
path = "corpus"

[[workspace.member]]
path = "similarity"
```

For the full field list see [`22-workspaces.md`](22-workspaces.md). For the version-pinning semantics of `sutra_version` see §"Version pinning and v0.0.0" above.

### The `sutra_version` field in single-project solutions

A **single-project** `atman.toml` may carry `sutra_version` at the `[project]` level. If present, it pins the language version the same way a workspace-level `sutra_version` does. If absent from a single-project file, the solution is treated as v0.0.0.

(A `sutra_version` field inside a `[project]` table that sits **inside** a workspace is redundant — the workspace file's pin is authoritative. v0.0.0-era compilers should ignore a per-project pin when a workspace pin exists and emit a warning that the project-level field is doing nothing.)

## Compilation entry points

**v0.0.0 today.** The reference compiler reads `.su` files. `atman.toml` is not consulted. `sutrac path/to/file.su` compiles that file. There is no workspace pipeline because there is no workspace concept in v0.0.0. The compiler was spaghetti-coded before the solution model existed and that is fine for the status-quo version.

**v0.0.1 and onward.** The compiler is invoked at the solution root:

- **Workspace solution:** `sutrac path/to/workspace/atman.toml`. The workspace loader resolves the member projects, topologically sorts them, and compiles each in order. The reference Python implementation lives at `sdk/sutra-compiler/sutra_compiler/workspace.py` today as pre-v0.0.1 scaffolding — it parses the schema but is not yet wired into the compiler's default path.
- **Single-project solution:** `sutrac path/to/project/atman.toml`. Same pipeline, single project.
- **Loose file (development mode):** `sutrac --dev path/to/file.su`. Legal only at v0.0.0 (implicit or explicit). Produces a warning on every invocation. Without `--dev`, a v0.0.1+ toolchain rejects loose files.

Neither the `--dev` gate nor workspace-at-compile-time is wired into the reference compiler today, and that is deliberate. Wiring them in before v0.0.1 is cut would break every existing file in the repo, because every existing file is v0.0.0 loose source.

## Relationship to other docs

- **Grammar for `.su` source:** [`24-grammar.md`](24-grammar.md).
- **`atman.toml` schema and resolution algorithm:** [`22-workspaces.md`](22-workspaces.md).
- **Substrate the project targets:** [`19-substrate-candidates.md`](19-substrate-candidates.md).
- **Syntactic decisions underlying the grammar:** [`sutra-syntax-decisions.md`](../../sutra-syntax-decisions.md) at the repo root.
- **IDE tree view of the solution:** [`20-ide-architecture.md`](20-ide-architecture.md).
