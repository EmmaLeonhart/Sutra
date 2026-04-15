# Workspaces and Projects

> **Status: planning document for v0.0.1.** The workspace model is not part of v0.0.0. The current reference compiler reads `.su` files directly and ignores `atman.toml`. This document describes the design target for the v0.0.1 cut (roughly two weeks out as of this writing). `sdk/sutra-compiler/sutra_compiler/workspace.py` and `examples/workspace/` exist as scaffolding for that cut, not as a working piece of v0.0.0. See [`25-solution-structure.md`](25-solution-structure.md) for the full versioning story.

A *workspace* is a collection of *projects* that compile and run together as a unit. The workspace file names the projects; each project file describes one buildable unit of `.su` source. Workspaces are the top level of the Sutra project model — everything else (source files, inter-project dependencies, substrate targeting, compiler flags) hangs off a workspace-and-project hierarchy.

The motivation for this layer is laid out in [`20-ide-architecture.md`](20-ide-architecture.md) §"UX Model: Visual Studio, Not Jupyter", specifically the "workspace file with multiple projects" bullet. This document is the formal schema for the `atman.toml` file format it asks for.

## Design choices

**Format: TOML.** The workspace file and every member project file are [TOML](https://toml.io) documents. Rationale: TOML is the de-facto modern config format (`Cargo.toml`, `pyproject.toml`, `gradle.properties` is TOML-adjacent), Python's standard library has `tomllib` since 3.11 (zero extra dependencies for the reference parser), and IntelliJ Platform has first-class bundled TOML support. The downsides — no inheritance primitives, ugly deep nesting, DIY schema validation — are accepted; none of them is load-bearing for the v1 schema this document defines.

**Filename: `atman.toml`, fixed by convention.** Every Sutra workspace and every Sutra project uses a single file literally called `atman.toml` at its directory root. There is no workspace-vs-project filename split (the old `.aksln`/`.akproj` era used separate extensions) — the parser disambiguates on the top-level table (`[workspace]` vs `[project]`). The language runtime, the IDE plugins, the CLI, and every external tool all look for `atman.toml` at the root and nowhere else. The name is from Sanskrit *ātman* ("self"), chosen because it is iconic, pronounceable, sorts near the top of a directory listing, and coheres with the Sutra language name.

**Convention:** filesystem paths inside an `atman.toml` are **relative to the file that contains them**, never to the current working directory. A project `atman.toml` at `embedding-pipeline/similarity/atman.toml` that says `path = "../corpus"` points to `embedding-pipeline/corpus/`. The parser canonicalizes paths at resolution time.

**Non-goals for v1:**

- **Nested workspaces.** A workspace cannot contain sub-workspaces. Flat list of member projects only. Nesting can be added as a strict extension later if it turns out to be needed.
- **Multiple substrate targets per project.** Each project targets exactly one substrate (e.g. `silicon`, `fly-brain`, `logit`). If you need to ship the same source against two substrates, make two projects that share a sources directory via a symlink or a glob include.
- **Binary build artifacts declared in the workspace.** The workspace file says what projects exist and how they depend on each other; it does not say where compiled outputs go. That's a compiler concern, not a workspace-file concern.
- **External package registry.** `[project.dependencies]` tables may only reference other projects in the *same* workspace. A package-registry extension (think Cargo crates.io) is a separate design document.

## Workspace `atman.toml`

A workspace file is the top of the hierarchy. It enumerates the member projects, declares workspace-wide defaults, and pins the Sutra version.

### Minimum schema

```toml
[workspace]
name = "embedding-pipeline"
sutra_version = "0.0.1"

[[workspace.member]]
path = "corpus"

[[workspace.member]]
path = "similarity"

[[workspace.member]]
path = "visualizations"
```

**Required fields:**

| Field | Type | Meaning |
|---|---|---|
| `workspace.name` | string | Human-readable name. Also used as the tool-window label in the IDE. |
| `workspace.sutra_version` | string | Minimum Sutra language version the workspace needs. Matches the `version` string produced by `sutrac --version`. The parser rejects a workspace whose `sutra_version` is newer than the installed toolchain. A workspace with no `sutra_version`, or a tree with no `atman.toml` at all, is treated as v0.0.0 — the pre-formalization development version that today's reference compiler accepts unconditionally but that a post-v0.1.0 toolchain will only accept in opt-in development mode. See [`25-solution-structure.md`](25-solution-structure.md) §"Version pinning and v0.0.0" for the full policy. |
| `workspace.member` | array of tables | One entry per member project in the workspace. Each entry has at least a `path`, relative to the workspace `atman.toml`. |

**Optional fields:**

| Field | Type | Meaning |
|---|---|---|
| `workspace.description` | string | Free-form description, shown in the IDE tool window as hover text on the workspace node. |
| `workspace.default_substrate` | string | Default substrate for member projects that do not specify one. Must be one of `silicon`, `fly-brain`, `logit`. If omitted, `silicon`. |
| `workspace.compiler_args` | array of strings | Extra arguments passed to `sutrac` for every project in the workspace. Per-project args (declared in the project atman.toml) are appended after these. |

Each `[[workspace.member]]` table may carry overrides that shadow the member project's own `atman.toml` contents. This lets a workspace file temporarily override a property without touching the project file (useful for A/B testing substrates):

```toml
[[workspace.member]]
path = "similarity"
substrate = "fly-brain"   # overrides similarity's atman.toml substrate field
```

## Project `atman.toml`

A project `atman.toml` lives at the root of a member project directory (the directory `workspace.member.path` points at) and describes one buildable unit.

### Minimum schema

```toml
[project]
name = "similarity"
entry = "main.su"
```

**Required fields:**

| Field | Type | Meaning |
|---|---|---|
| `project.name` | string | Project identifier, unique within the workspace. Must match `^[a-zA-Z_][a-zA-Z0-9_-]*$`. Used as the key in `[project.dependencies]` tables in sibling projects. |
| `project.entry` | string | Path to the entry-point `.su` file, relative to the project directory. The compiler starts parsing here. |

**Optional fields:**

| Field | Type | Default | Meaning |
|---|---|---|---|
| `project.substrate` | string | inherited from workspace, else `silicon` | Target substrate for this project. One of `silicon`, `fly-brain`, `logit`. |
| `project.description` | string | `""` | Free-form. Shown as hover text in the IDE. |
| `project.compiler_args` | array of strings | `[]` | Extra `sutrac` args for this project only. Appended after workspace-wide args. |
| `project.sources.include` | array of glob strings | `["**/*.su"]` | Source file globs relative to the project directory. |
| `project.sources.exclude` | array of glob strings | `[]` | Paths to exclude from the include set. |
| `[project.dependencies]` | table of project-references | empty | See below. |

### Inter-project dependencies

A project's `[project.dependencies]` table is a flat map from dependency name to a reference table. The only supported reference kind in v1 is `{ path = "..." }`, where the path is relative to the depending project's directory (not the workspace root):

```toml
[project.dependencies]
corpus = { path = "../corpus" }
embedding_api = { path = "../embedding_api" }
```

The parser:

1. Reads the `atman.toml` at the target path
2. Verifies its `project.name` matches the key you used (so `corpus = { path = "../corpus" }` requires `../corpus/atman.toml` to have `name = "corpus"` — prevents silent rebinding)
3. Records the edge in the workspace's dependency graph

Cycles are an error. Self-dependencies are an error. Dependencies on projects outside the current workspace are an error.

## Resolution algorithm

The reference parser (see `sdk/sutra-compiler/sutra_compiler/workspace.py`) does the following to load a workspace:

1. **Read the workspace `atman.toml`.** Parse the TOML, validate the schema, resolve `[[workspace.member]]` paths to absolute paths on disk.
2. **For each member**, locate the member's `atman.toml` at `{member_path}/atman.toml`. Unlike the old `.akproj` discovery model, there is no filename variation — the parser looks for exactly one fixed filename.
3. **Parse each member project's `atman.toml`.** Validate its schema. Apply the workspace-level overrides from the corresponding `[[workspace.member]]` entry.
4. **Collect source files.** For each project, expand `sources.include` and `sources.exclude` globs relative to the project directory. The resulting list is the project's source set.
5. **Resolve dependencies.** For each project, walk `[project.dependencies]`, verify each reference points to another project in the same workspace, and build a directed dependency graph. Detect cycles; reject with a clear error listing the cycle.
6. **Topologically sort projects.** Produces the build order: if `similarity` depends on `corpus`, `corpus` comes first.
7. **Return a `Workspace` object** — a Python data class (or Kotlin data class in the IDE plugin) with the workspace metadata, the project list in build order, and the validated dependency graph.

## Error reporting

The parser emits structured errors in the same `SUT####` code space as the rest of the Sutra compiler, reserving codes `SUT2000-SUT2099` for workspace-model errors. A non-exhaustive list:

| Code | Error |
|---|---|
| `SUT2001` | Workspace `atman.toml` is not valid TOML |
| `SUT2002` | Workspace `atman.toml` is missing a required field (`workspace.name`, `workspace.sutra_version`, or at least one `[[workspace.member]]`) |
| `SUT2003` | `sutra_version` requires a toolchain newer than the installed `sutrac` |
| `SUT2004` | Member path in `[[workspace.member]]` does not exist on disk |
| `SUT2005` | Member directory does not contain an `atman.toml` |
| `SUT2006` | Project `atman.toml` is not valid TOML |
| `SUT2007` | Project `atman.toml` is missing a required field (`project.name` or `project.entry`) |
| `SUT2008` | Project file's `project.name` does not match the workspace's expected dependency key |
| `SUT2009` | Project's `entry` file does not exist on disk |
| `SUT2010` | Dependency reference points to a path that does not contain an `atman.toml` |
| `SUT2011` | Dependency cycle detected — the error payload names the cycle in order |
| `SUT2012` | Self-dependency |
| `SUT2013` | Dependency on a project outside the current workspace |
| `SUT2014` | Unknown `substrate` value |
| `SUT2015` | Glob in `sources.include` or `sources.exclude` is malformed |

## IDE integration

The reference IntelliJ plugin at `sdk/intellij-sutra/` registers:

1. **`SutraAtmanFileType`** — claims `atman.toml` as a TOML-flavored file type so the bundled IntelliJ TOML support provides highlighting and bracket matching without any extra code on our side. One file type covers both workspace-level and project-level `atman.toml` files; they are distinguished at parse time by whether the top-level table is `[workspace]` or `[project]`.
2. **`SutraWorkspaceToolWindowFactory`** — a tool window on the left side of the workspace that scans the open project for the root `atman.toml`, parses it via a Kotlin port of `workspace.py`'s data model, and renders the workspace structure as a `JTree`. Double-clicking a tree node opens the corresponding file in the editor (project nodes open the member `atman.toml`, source-file nodes open the `.su` file, the workspace node opens the root `atman.toml`).

Out of scope for the v1 plugin integration, explicit v1.1 follow-ups:

- **`ProjectOpenProcessor`** for "open folder → auto-detect workspace" behavior. Currently the user opens the folder normally and then clicks the workspace tool window. v1.1 will add the auto-open hook so the tool window opens automatically on directories that contain an `atman.toml`.
- **Source root configuration** via `ModuleRootModificationUtil`. The v1 experience relies on the existing `.su` file-type registration for language features, which works on any `.su` file regardless of project membership. A proper source-root configuration would improve cross-file navigation and "find usages" across project boundaries.
- **Run configurations.** A first-class `ConfigurationType` that lets the user right-click a project in the tool window and run `sutrac` against it. v1 has no run integration; the user invokes the compiler from the terminal.
- **MCP surface.** Once the runtime MCP server from [`20-ide-architecture.md`](20-ide-architecture.md) §"MCP Architecture" ships, the workspace model should be exposed as an MCP tool (e.g. `sutra.workspace(path)` returns the parsed workspace JSON) so agents can query the project structure without going through the UI.

## Example: a two-project workspace

```
embedding-pipeline/
├── atman.toml                # workspace atman.toml
├── corpus/
│   ├── atman.toml            # project atman.toml
│   ├── main.su
│   └── helpers.su
└── similarity/
    ├── atman.toml            # project atman.toml
    ├── cosine.su
    └── main.su
```

**Workspace `atman.toml`:**

```toml
[workspace]
name = "embedding-pipeline"
sutra_version = "0.0.1"
default_substrate = "silicon"

[[workspace.member]]
path = "corpus"

[[workspace.member]]
path = "similarity"
```

**`corpus/atman.toml`:**

```toml
[project]
name = "corpus"
entry = "main.su"
description = "Static corpus of reference vectors used by downstream projects."
```

**`similarity/atman.toml`:**

```toml
[project]
name = "similarity"
entry = "main.su"
description = "Cosine-similarity queries against the reference corpus."

[project.dependencies]
corpus = { path = "../corpus" }
```

Resolution order: `corpus` first, `similarity` second.
