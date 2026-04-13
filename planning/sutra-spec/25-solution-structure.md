# Solution Structure

A *solution* in Sutra is a complete compilable unit on disk: a workspace `atman.toml`, zero or more member projects, and the `.su` source files those projects own. This document describes what a well-formed solution looks like, how version pinning works, and what the compiler does with source trees that **don't** have a workspace file.

The workspace-file schema itself lives in [`22-workspaces.md`](22-workspaces.md); the surface grammar the source files must conform to lives in [`24-grammar.md`](24-grammar.md). This document ties the two together and adds the version-pinning policy.

## The three shapes a solution can take

Sutra recognizes three levels of structure, in increasing order of formality:

### 1. Loose `.su` files (no `atman.toml`)

A directory containing one or more `.su` files with **no `atman.toml` anywhere up the tree** is a *loose source tree*. The compiler will try to read it in "development mode" — the same thing you get when you point `sutrac` at a single file from the command line.

In development mode:

- There is no workspace, no project, no dependency graph.
- Source files cannot depend on each other across project boundaries (because there are no projects).
- The language version is implicitly **v0.0.0** — see §"Version pinning and v0.0.0" below.

This is the only shape that currently exists in this repo. Everything under `examples/`, `fly-brain/`, and `sutra-demo-program.su` is loose `.su` source at v0.0.0.

### 2. Single-project solution

A directory with an `atman.toml` whose top-level table is `[project]` is a *single-project solution*. There is no workspace wrapper; the project is its own root. This is the minimum viable shape for a solution that wants stable compilation.

```
my-analysis/
├── atman.toml          # [project] table
├── main.su
└── helpers.su
```

### 3. Multi-project workspace

A directory with an `atman.toml` whose top-level table is `[workspace]` is a *workspace solution*. It enumerates member projects, each of which has its own `atman.toml` at its root. The full schema, resolution algorithm, and dependency model are in [`22-workspaces.md`](22-workspaces.md).

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

`examples/workspace/` is the reference example.

## Version pinning and v0.0.0

Every compiling Sutra solution pins a language version via the `sutra_version` field of its root `atman.toml`. The compiler uses that field to choose which grammar variant and which standard-library surface to expect; see [`24-grammar.md`](24-grammar.md) §"Status and versioning" for the grammar-side policy.

### What each version class means

| `sutra_version` | Status | Compilation |
|---|---|---|
| (no `atman.toml`) | v0.0.0 implicit | development mode only; may stop compiling in any future toolchain |
| `"0.0.0"` | explicit v0.0.0 | same as above, with the version made explicit |
| `"0.1.0"` and onward | stable release | compiler honors the grammar and standard library as shipped for that version |
| newer than installed toolchain | error | compiler rejects the solution with diagnostic `SUT2003` |

### Why v0.0.0 is special

**v0.0.0 is a development-only placeholder version.** It is the label the compiler applies when it has no information about what version a source tree was written for. It exists to let the current repo (where the grammar is still being shaken out) have something meaningful to call the status quo, rather than pretending it is already at v0.1.

The contract around v0.0.0:

1. **v0.0.0 cannot normally compile at all.** The compiler's default posture toward a v0.0.0 source tree is to refuse to build it and emit a diagnostic directing the user to pin a real version. A best-effort development mode exists (see §"Development mode" below) but it is opt-in, not the default.
2. **v0.0.0 is not guaranteed to survive any future grammar change.** Breaking changes between v0.0.0 and v0.1.0 are explicitly allowed. Anything that worked at v0.0.0 may stop working at v0.1.0 without a deprecation window.
3. **v0.0.0 will not always be supported.** At some point after v0.1.0 is cut the compiler will drop the development-mode path entirely. Solutions still on v0.0.0 at that point will have to be migrated.
4. **Do not ship v0.0.0 code to anyone else.** Any solution you expect a second person, a CI pipeline, or a downstream dependency to consume **must** pin a real `sutra_version` in its `atman.toml`.

Rule of thumb: **if you want the compiler to care whether your code is correct, give it an `atman.toml` with a real version.** v0.0.0 is for scratch work that the author is prepared to throw away.

### Development mode

Because v0.0.0 is where the language actually lives right now, the compiler provides a **development mode** for loose `.su` files and explicit-v0.0.0 solutions. Development mode:

- Accepts the grammar as currently implemented in `sdk/sutra-compiler/` with no version gate.
- Emits a warning on every run, prefixed with the file path, reminding the user that the source is at v0.0.0.
- Does **not** promise that the same input will be accepted in any future toolchain.

Development mode is enabled by an explicit `--dev` flag or `SUTRA_DEV_MODE=1` in the environment; the default behavior of `sutrac` against a v0.0.0 tree is to refuse to compile and print a diagnostic pointing the user at this document.

This compiler behavior is not yet implemented in `sdk/sutra-compiler/`; the current reference compiler parses v0.0.0 source unconditionally because there is no alternative. The policy described here is the target behavior for when v0.1.0 is cut. Until then, the reference compiler effectively runs in development mode at all times, and every `.su` file in this repo is v0.0.0.

## File conventions

### `.su` source files

Source files use the extension `.su`. The file is a `module` per [`24-grammar.md`](24-grammar.md) — a sequence of top-level items with no explicit module declaration.

A `.su` file is one of two things, determined by its contents, not by syntax or filename:

- An **object declaration**, if its top-level items are predominantly `method` declarations. The file acts as the body of a type; see `examples/01-objects-and-methods.su`.
- An **executable file**, if its top-level items are a mix of statements, variable declarations, and `function` declarations. The file runs top-to-bottom when loaded; see `examples/06-executable-file.su`.

The language does not force either shape. A single-file solution that just runs is as legitimate as a multi-project workspace with a formal object model.

### `atman.toml`

Every project and every workspace is named by a file called literally `atman.toml` at its directory root. The name is fixed by convention — there is no `.akproj` / `.aksln` discovery heuristic. The parser distinguishes workspace files from project files by the top-level table (`[workspace]` vs `[project]`).

A minimal single-project `atman.toml` at v0.1.0:

```toml
[project]
name = "my-analysis"
entry = "main.su"
sutra_version = "0.1.0"
```

A minimal workspace `atman.toml` at v0.1.0:

```toml
[workspace]
name = "embedding-pipeline"
sutra_version = "0.1.0"

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

The compiler is invoked at the solution root:

- **Workspace solution:** `sutrac path/to/workspace/atman.toml`. The workspace loader resolves the member projects, topologically sorts them, and compiles each in order. See `sdk/sutra-compiler/sutra_compiler/workspace.py`.
- **Single-project solution:** `sutrac path/to/project/atman.toml`. Same pipeline, single project.
- **Loose file (development mode):** `sutrac --dev path/to/file.su`. Only legal at v0.0.0; produces a warning on every invocation. Without `--dev`, v0.1.0+ toolchains reject loose files.

The reference compiler currently implements the workspace entry point (`python -m sutra_compiler.workspace path/to/atman.toml`) and a single-file entry point. The `--dev` gate is not yet wired up; every invocation today is effectively development mode.

## Relationship to other docs

- **Grammar for `.su` source:** [`24-grammar.md`](24-grammar.md).
- **`atman.toml` schema and resolution algorithm:** [`22-workspaces.md`](22-workspaces.md).
- **Substrate the project targets:** [`19-substrate-candidates.md`](19-substrate-candidates.md).
- **Syntactic decisions underlying the grammar:** [`sutra-syntax-decisions.md`](../../sutra-syntax-decisions.md) at the repo root.
- **IDE tree view of the solution:** [`20-ide-architecture.md`](20-ide-architecture.md).
