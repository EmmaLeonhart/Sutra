# Solutions and Projects

A *solution* is a collection of *projects* that compile and run together as a unit. The solution file names the projects; each project file describes one buildable unit of `.ak` source. Solutions are the top level of the Akasha project model — everything else (source files, inter-project dependencies, substrate targeting, compiler flags) hangs off a solution-and-project hierarchy.

The motivation for this layer is laid out in [`20-ide-architecture.md`](20-ide-architecture.md) §"UX Model: Visual Studio, Not Jupyter", specifically the "solution file with multiple projects" bullet. This document is the formal schema for the two file formats it asks for.

## Design choices

**Format: TOML.** Both the solution file and the project file are [TOML](https://toml.io) documents. Rationale: TOML is the de-facto modern config format (`Cargo.toml`, `pyproject.toml`, `gradle.properties` is TOML-adjacent), Python's standard library has `tomllib` since 3.11 (zero extra dependencies for the reference parser), and IntelliJ Platform has first-class bundled TOML support. The downsides — no inheritance primitives, ugly deep nesting, DIY schema validation — are accepted; none of them is load-bearing for the v1 schema this document defines.

**Extensions:** `.aksln` for solution files, `.akproj` for project files. The reference IDE plugin registers both extensions as TOML-flavored file types so bundled TOML highlighting applies out of the box without a separate parser.

**Convention:** filesystem paths inside a solution or project file are **relative to the file that contains them**, never to the current working directory. A `.akproj` at `embedding-pipeline/similarity/similarity.akproj` that says `path = "../corpus"` points to `embedding-pipeline/corpus/`. The parser canonicalizes paths at resolution time.

**Non-goals for v1:**

- **Nested solutions.** A solution cannot contain sub-solutions. Flat list of projects only. Nesting can be added as a strict extension later if it turns out to be needed.
- **Multiple substrate targets per project.** Each project targets exactly one substrate (e.g. `silicon`, `fly-brain`, `logit`). If you need to ship the same source against two substrates, make two projects that share a sources directory via a symlink or a glob include.
- **Binary build artifacts declared in the solution.** The solution file says what projects exist and how they depend on each other; it does not say where compiled outputs go. That's a compiler concern, not a solution-file concern.
- **External package registry.** `[dependencies]` tables may only reference other projects in the *same* solution. A package-registry extension (think Cargo crates.io) is a separate design document.

## `.aksln` — solution file

A solution file is the top of the workspace. It enumerates the projects, declares solution-wide defaults, and pins the Akasha version.

### Minimum schema

```toml
[solution]
name = "embedding-pipeline"
akasha_version = "0.2"

[[project]]
path = "corpus"

[[project]]
path = "similarity"

[[project]]
path = "visualizations"
```

**Required fields:**

| Field | Type | Meaning |
|---|---|---|
| `solution.name` | string | Human-readable name. Also used as the tool-window label in the IDE. |
| `solution.akasha_version` | string | Minimum Akasha language version the solution needs. Matches the `version` string produced by `akashac --version`. The parser rejects a solution whose `akasha_version` is newer than the installed toolchain. |
| `project` | array of tables | One entry per project in the solution. Each entry has at least a `path`, relative to the `.aksln` file. |

**Optional fields:**

| Field | Type | Meaning |
|---|---|---|
| `solution.description` | string | Free-form description, shown in the IDE tool window as hover text on the solution node. |
| `solution.default_substrate` | string | Default substrate for projects that do not specify one. Must be one of `silicon`, `fly-brain`, `logit`. If omitted, `silicon`. |
| `solution.compiler_args` | array of strings | Extra arguments passed to `akashac` for every project in the solution. Per-project args (declared in the `.akproj`) are appended after these. |

Each `[[project]]` table may carry overrides that shadow the `.akproj` contents. This lets a solution file temporarily override a property without touching the project file (useful for A/B testing substrates):

```toml
[[project]]
path = "similarity"
substrate = "fly-brain"   # overrides similarity.akproj's own substrate field
```

## `.akproj` — project file

A project file lives at the root of a project directory (the directory `solution.project.path` points at) and describes one buildable unit.

### Minimum schema

```toml
[project]
name = "similarity"
entry = "main.ak"
```

**Required fields:**

| Field | Type | Meaning |
|---|---|---|
| `project.name` | string | Project identifier, unique within the solution. Must match `^[a-zA-Z_][a-zA-Z0-9_-]*$`. Used as the key in `[project.dependencies]` tables in sibling projects. |
| `project.entry` | string | Path to the entry-point `.ak` file, relative to the project directory. The compiler starts parsing here. |

**Optional fields:**

| Field | Type | Default | Meaning |
|---|---|---|---|
| `project.substrate` | string | inherited from solution, else `silicon` | Target substrate for this project. One of `silicon`, `fly-brain`, `logit`. |
| `project.description` | string | `""` | Free-form. Shown as hover text in the IDE. |
| `project.compiler_args` | array of strings | `[]` | Extra `akashac` args for this project only. Appended after solution-wide args. |
| `project.sources.include` | array of glob strings | `["**/*.ak"]` | Source file globs relative to the project directory. |
| `project.sources.exclude` | array of glob strings | `[]` | Paths to exclude from the include set. |
| `[project.dependencies]` | table of project-references | empty | See below. |

### Inter-project dependencies

A project's `[project.dependencies]` table is a flat map from dependency name to a reference table. The only supported reference kind in v1 is `{ path = "..." }`, where the path is relative to the depending project's directory (not the solution root):

```toml
[project.dependencies]
corpus = { path = "../corpus" }
embedding_api = { path = "../embedding_api" }
```

The parser:

1. Reads the `.akproj` at the target path
2. Verifies its `project.name` matches the key you used (so `corpus = { path = "../corpus" }` requires `../corpus/corpus.akproj` to have `name = "corpus"` — prevents silent rebinding)
3. Records the edge in the solution's dependency graph

Cycles are an error. Self-dependencies are an error. Dependencies on projects outside the current solution are an error.

## Resolution algorithm

The reference parser (see `sdk/akasha-compiler/akasha_compiler/solution.py`) does the following to load a solution:

1. **Read the solution file.** Parse the TOML, validate the schema, resolve `[[project]]` paths to absolute paths on disk.
2. **For each project entry**, locate the corresponding `.akproj` file. By default the parser looks for `{project_path}/*.akproj` and expects exactly one match; the solution entry may override with `akproj = "explicit_name.akproj"` if a project directory contains multiple `.akproj` files (rare, but supported).
3. **Parse each project file.** Validate its schema. Apply the solution-level overrides from the corresponding `[[project]]` entry.
4. **Collect source files.** For each project, expand `sources.include` and `sources.exclude` globs relative to the project directory. The resulting list is the project's source set.
5. **Resolve dependencies.** For each project, walk `[project.dependencies]`, verify each reference points to another project in the same solution, and build a directed dependency graph. Detect cycles; reject with a clear error listing the cycle.
6. **Topologically sort projects.** Produces the build order: if `similarity` depends on `corpus`, `corpus` comes first.
7. **Return a `Solution` object** — a Python data class (or Kotlin data class in the IDE plugin) with the solution metadata, the project list in build order, and the validated dependency graph.

## Error reporting

The parser emits structured errors in the same `AKA####` code space as the rest of the Akasha compiler, reserving codes `AKA2000-AKA2099` for solution-model errors. A non-exhaustive list:

| Code | Error |
|---|---|
| `AKA2001` | Solution file is not valid TOML |
| `AKA2002` | Solution file is missing a required field (`solution.name`, `solution.akasha_version`, or at least one `[[project]]`) |
| `AKA2003` | `akasha_version` requires a toolchain newer than the installed `akashac` |
| `AKA2004` | Project path in `[[project]]` does not exist on disk |
| `AKA2005` | Project directory contains zero or multiple `.akproj` files and the solution entry did not disambiguate via `akproj = "..."` |
| `AKA2006` | Project file is not valid TOML |
| `AKA2007` | Project file is missing a required field (`project.name` or `project.entry`) |
| `AKA2008` | Project file's `project.name` does not match the solution's expected dependency key |
| `AKA2009` | Project's `entry` file does not exist on disk |
| `AKA2010` | Dependency reference points to a path that does not contain a `.akproj` |
| `AKA2011` | Dependency cycle detected — the error payload names the cycle in order |
| `AKA2012` | Self-dependency |
| `AKA2013` | Dependency on a project outside the current solution |
| `AKA2014` | Unknown `substrate` value |
| `AKA2015` | Glob in `sources.include` or `sources.exclude` is malformed |

## IDE integration

The reference IntelliJ plugin at `sdk/intellij-akasha/` registers:

1. **`AkashaSolutionFileType`** — claims `.aksln` as a TOML-flavored file type so the bundled IntelliJ TOML support provides highlighting and bracket matching without any extra code on our side.
2. **`AkashaProjectFileType`** — same for `.akproj`.
3. **`AkashaSolutionToolWindowFactory`** — a new tool window on the left side of the workspace that scans the open project for the first `.aksln` file at or near the root, parses it via a Kotlin port of `solution.py`'s data model, and renders the solution structure as a `JTree`. Double-clicking a tree node opens the corresponding file in the editor (project nodes open the `.akproj`, source-file nodes open the `.ak` file, the solution node opens the `.aksln`).

Out of scope for the v1 plugin integration, explicit v1.1 follow-ups:

- **`ProjectOpenProcessor`** for "open folder → auto-detect solution" behavior. Currently the user opens the folder normally and then clicks the solution tool window. v1.1 will add the auto-open hook so the tool window opens automatically on recognized solutions.
- **Source root configuration** via `ModuleRootModificationUtil`. The v1 experience relies on the existing `.ak` file-type registration for language features, which works on any `.ak` file regardless of project membership. A proper source-root configuration would improve cross-file navigation and "find usages" across project boundaries.
- **Run configurations.** A first-class `ConfigurationType` that lets the user right-click a project in the tool window and run `akashac` against it. v1 has no run integration; the user invokes the compiler from the terminal.
- **MCP surface.** Once the runtime MCP server from [`20-ide-architecture.md`](20-ide-architecture.md) §"MCP Architecture" ships, the solution model should be exposed as an MCP tool (e.g. `akasha.solution(path)` returns the parsed solution JSON) so agents can query the project structure without going through the UI.

## Example: a two-project solution

```
embedding-pipeline/
├── embedding-pipeline.aksln
├── corpus/
│   ├── corpus.akproj
│   ├── main.ak
│   └── helpers.ak
└── similarity/
    ├── similarity.akproj
    ├── cosine.ak
    └── main.ak
```

**`embedding-pipeline.aksln`:**

```toml
[solution]
name = "embedding-pipeline"
akasha_version = "0.2"
default_substrate = "silicon"

[[project]]
path = "corpus"

[[project]]
path = "similarity"
```

**`corpus/corpus.akproj`:**

```toml
[project]
name = "corpus"
entry = "main.ak"
description = "Static corpus of reference vectors used by downstream projects."
```

**`similarity/similarity.akproj`:**

```toml
[project]
name = "similarity"
entry = "main.ak"
description = "Cosine-similarity queries against the reference corpus."

[project.dependencies]
corpus = { path = "../corpus" }
```

Resolution order: `corpus` first, `similarity` second.
