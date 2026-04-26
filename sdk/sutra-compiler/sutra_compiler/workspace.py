"""Workspace and project loader for the Sutra compiler.

Reads `atman.toml` files. A workspace has a root `atman.toml` with a
`[workspace]` table that lists member projects; each member project
has its own `atman.toml` at its directory root with a `[project]`
table. The name `atman.toml` is fixed by convention — the language
runtime and every IDE integration looks for exactly that filename at
the top of a directory, so no `*.aksln` / `*.akproj` discovery heuristic
is needed.

Formal schema: `planning/sutra-spec/22-workspaces.md`. This file is the
reference Python implementation the schema describes — it is the source
of truth for "what does a well-formed `atman.toml` mean," and every
other tool (the IntelliJ plugin's Kotlin data model, the VS Code
extension, the website docs) is expected to match it.

Usage:

    from pathlib import Path
    from sutra_compiler.workspace import load_workspace

    ws = load_workspace(Path("atman.toml"))
    for project in ws.projects_in_build_order:
        print(project.name, project.substrate, project.sources)

Errors are raised as `WorkspaceError` with a stable `SUT####` code in
the `SUT2000-SUT2099` range reserved for workspace-model errors. The
same codes carry over from the old `.aksln`/`.akproj` era; call sites
that check `err.code` do not need to change.

Design notes:

- TOML parsing uses the Python 3.11+ standard library `tomllib` module.
  No third-party dependency.
- Filesystem paths inside TOML are always resolved relative to the
  `atman.toml` that contains them.
- Glob expansion uses `pathlib.Path.glob` with `**` support.
- Dependency resolution uses a three-pass approach: parse all member
  projects, build the edge set, then topologically sort with a cycle
  detector that reports the exact cycle on error.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


# ============================================================
# Error type
# ============================================================


class WorkspaceError(Exception):
    """Raised for any invalid `atman.toml` workspace or project file.

    Attributes:
        code: The `SUT####` diagnostic code from the spec (§Error reporting).
        message: Human-readable one-line summary.
        details: Optional structured payload.
        source_path: The file that produced the error, if applicable.
    """

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Any | None = None,
        source_path: Path | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.details = details
        self.source_path = source_path
        suffix = f" ({source_path})" if source_path else ""
        super().__init__(f"{code}: {message}{suffix}")


# ============================================================
# Data types
# ============================================================


VALID_SUBSTRATES = frozenset({"silicon", "logit"})
PROJECT_NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_-]*$")


@dataclass
class ProjectDependency:
    """One inter-project edge declared in a project `atman.toml`."""

    name: str
    path: Path  # absolute, resolved


@dataclass
class Project:
    """One project within a workspace, fully resolved and validated."""

    name: str
    path: Path  # absolute path to the project directory
    atman_file: Path  # absolute path to the project's `atman.toml`
    entry: Path  # absolute path to the entry-point `.su` file
    substrate: str  # one of VALID_SUBSTRATES
    description: str
    compiler_args: list[str]
    sources: list[Path]  # absolute paths, expanded from the globs
    dependencies: list[ProjectDependency]


@dataclass
class Workspace:
    """One workspace, fully resolved and validated."""

    name: str
    sutra_version: str
    description: str
    default_substrate: str
    compiler_args: list[str]
    atman_file: Path  # absolute path to the workspace `atman.toml`
    projects: list[Project]  # in topological (build) order
    projects_by_name: dict[str, Project] = field(default_factory=dict)

    @property
    def projects_in_build_order(self) -> list[Project]:
        """Alias for `projects`; kept for readability at call sites."""
        return self.projects


# ============================================================
# TOML helpers
# ============================================================


def _read_toml(path: Path, *, is_workspace: bool) -> dict[str, Any]:
    """Read an `atman.toml` file and return its top-level table.

    `is_workspace` determines which error code to use for malformed
    TOML: SUT2001 for the workspace-level atman.toml, SUT2006 for a
    member project atman.toml.
    """
    try:
        with path.open("rb") as f:
            return tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        code = "SUT2001" if is_workspace else "SUT2006"
        raise WorkspaceError(
            code, f"file is not valid TOML: {e}", source_path=path
        ) from e
    except OSError as e:
        raise WorkspaceError(
            "SUT2004",
            f"cannot open file: {e}",
            source_path=path,
        ) from e


def _require_string(
    table: dict[str, Any],
    key: str,
    *,
    code: str,
    source_path: Path,
) -> str:
    """Pull a required string field out of a TOML table."""
    value = table.get(key)
    if value is None:
        raise WorkspaceError(
            code,
            f"missing required field `{key}`",
            source_path=source_path,
        )
    if not isinstance(value, str):
        raise WorkspaceError(
            code,
            f"field `{key}` must be a string, got {type(value).__name__}",
            source_path=source_path,
        )
    return value


# ============================================================
# Workspace loading
# ============================================================


def load_workspace(atman_path: Path) -> Workspace:
    """Load, parse, validate, and resolve a workspace `atman.toml`.

    This is the main public entry point. It runs every stage of the
    resolution algorithm from §"Resolution algorithm" in the spec:
    TOML parse → schema validate → member discovery → dependency
    graph → topological sort → Workspace object.
    """
    atman_path = atman_path.resolve()
    if not atman_path.is_file():
        raise WorkspaceError(
            "SUT2004",
            f"workspace file does not exist: {atman_path}",
            source_path=atman_path,
        )
    doc = _read_toml(atman_path, is_workspace=True)

    workspace_table = doc.get("workspace")
    if not isinstance(workspace_table, dict):
        raise WorkspaceError(
            "SUT2002",
            "workspace file is missing the [workspace] table",
            source_path=atman_path,
        )

    name = _require_string(
        workspace_table, "name", code="SUT2002", source_path=atman_path,
    )
    sutra_version = _require_string(
        workspace_table, "sutra_version",
        code="SUT2002", source_path=atman_path,
    )
    description = workspace_table.get("description", "")
    if not isinstance(description, str):
        raise WorkspaceError(
            "SUT2002",
            "`workspace.description` must be a string",
            source_path=atman_path,
        )

    default_substrate = workspace_table.get("default_substrate", "silicon")
    if default_substrate not in VALID_SUBSTRATES:
        raise WorkspaceError(
            "SUT2014",
            f"unknown `workspace.default_substrate` value `{default_substrate}`; "
            f"must be one of {sorted(VALID_SUBSTRATES)}",
            source_path=atman_path,
        )

    compiler_args = workspace_table.get("compiler_args", [])
    if not isinstance(compiler_args, list) or not all(
        isinstance(a, str) for a in compiler_args
    ):
        raise WorkspaceError(
            "SUT2002",
            "`workspace.compiler_args` must be a list of strings",
            source_path=atman_path,
        )

    member_entries = workspace_table.get("member")
    if not isinstance(member_entries, list) or len(member_entries) == 0:
        raise WorkspaceError(
            "SUT2002",
            "workspace file must contain at least one [[workspace.member]] entry",
            source_path=atman_path,
        )

    # First pass: discover every member and load its project atman.toml,
    # applying any workspace-level overrides, without yet validating
    # dependencies.
    workspace_dir = atman_path.parent
    projects_unordered: list[Project] = []
    for idx, entry in enumerate(member_entries):
        if not isinstance(entry, dict):
            raise WorkspaceError(
                "SUT2002",
                f"[[workspace.member]] entry #{idx} must be a table",
                source_path=atman_path,
            )
        rel_path = _require_string(
            entry, "path", code="SUT2002", source_path=atman_path,
        )
        project_dir = (workspace_dir / rel_path).resolve()
        if not project_dir.is_dir():
            raise WorkspaceError(
                "SUT2004",
                f"workspace member path does not exist: {project_dir}",
                source_path=atman_path,
                details={"index": idx, "path": str(project_dir)},
            )
        project = _load_project(
            project_dir,
            workspace_default_substrate=default_substrate,
            workspace_compiler_args=compiler_args,
            workspace_member_overrides=entry,
            workspace_atman_path=atman_path,
        )
        projects_unordered.append(project)

    # Second pass: verify every dependency resolves to a project that
    # actually exists in this workspace, and that the dependency's name
    # matches the target project's declared name.
    projects_by_name: dict[str, Project] = {}
    for p in projects_unordered:
        if p.name in projects_by_name:
            raise WorkspaceError(
                "SUT2007",
                f"two projects in the same workspace share the name `{p.name}`",
                source_path=atman_path,
            )
        projects_by_name[p.name] = p
    for p in projects_unordered:
        for dep in p.dependencies:
            target = _find_project_by_dir(projects_unordered, dep.path)
            if target is None:
                raise WorkspaceError(
                    "SUT2013",
                    f"project `{p.name}` depends on a project outside the "
                    f"current workspace: {dep.path}",
                    source_path=p.atman_file,
                )
            if target.name != dep.name:
                raise WorkspaceError(
                    "SUT2008",
                    f"dependency key `{dep.name}` in project `{p.name}` "
                    f"does not match target project's declared name "
                    f"`{target.name}`",
                    source_path=p.atman_file,
                )
            if target.name == p.name:
                raise WorkspaceError(
                    "SUT2012",
                    f"project `{p.name}` declares a self-dependency",
                    source_path=p.atman_file,
                )

    # Third pass: topologically sort. Kahn's algorithm with an explicit
    # cycle detector that reports the cycle in order.
    ordered = _topological_sort(projects_unordered, projects_by_name, atman_path)

    return Workspace(
        name=name,
        sutra_version=sutra_version,
        description=description,
        default_substrate=default_substrate,
        compiler_args=list(compiler_args),
        atman_file=atman_path,
        projects=ordered,
        projects_by_name=projects_by_name,
    )


# ============================================================
# Project loading
# ============================================================


def _load_project(
    project_dir: Path,
    *,
    workspace_default_substrate: str,
    workspace_compiler_args: list[str],
    workspace_member_overrides: dict[str, Any],
    workspace_atman_path: Path,
) -> Project:
    """Locate, parse, validate, and return one member project.

    The project file is always `atman.toml` at the member directory
    root — there is no discovery heuristic, because the filename is
    fixed by convention.
    """
    atman_file = project_dir / "atman.toml"
    if not atman_file.is_file():
        raise WorkspaceError(
            "SUT2005",
            f"project directory has no atman.toml: {project_dir}",
            source_path=workspace_atman_path,
        )
    doc = _read_toml(atman_file, is_workspace=False)

    project_table = doc.get("project")
    if not isinstance(project_table, dict):
        raise WorkspaceError(
            "SUT2007",
            "project atman.toml is missing the [project] table",
            source_path=atman_file,
        )

    name = _require_string(
        project_table, "name", code="SUT2007", source_path=atman_file,
    )
    if not PROJECT_NAME_RE.match(name):
        raise WorkspaceError(
            "SUT2007",
            f"project name `{name}` is not a valid identifier "
            f"(must match {PROJECT_NAME_RE.pattern})",
            source_path=atman_file,
        )

    entry_name = _require_string(
        project_table, "entry", code="SUT2007", source_path=atman_file,
    )
    entry_path = (project_dir / entry_name).resolve()
    if not entry_path.is_file():
        raise WorkspaceError(
            "SUT2009",
            f"entry file does not exist: {entry_path}",
            source_path=atman_file,
        )

    # Substrate resolution: workspace.member override > project
    # atman.toml > workspace default.
    substrate = workspace_member_overrides.get(
        "substrate",
        project_table.get("substrate", workspace_default_substrate),
    )
    if substrate not in VALID_SUBSTRATES:
        raise WorkspaceError(
            "SUT2014",
            f"unknown substrate `{substrate}` for project `{name}`; "
            f"must be one of {sorted(VALID_SUBSTRATES)}",
            source_path=atman_file,
        )

    description = project_table.get("description", "")
    if not isinstance(description, str):
        raise WorkspaceError(
            "SUT2007",
            "`project.description` must be a string",
            source_path=atman_file,
        )

    per_project_args = project_table.get("compiler_args", [])
    if not isinstance(per_project_args, list) or not all(
        isinstance(a, str) for a in per_project_args
    ):
        raise WorkspaceError(
            "SUT2007",
            "`project.compiler_args` must be a list of strings",
            source_path=atman_file,
        )
    combined_args = list(workspace_compiler_args) + list(per_project_args)

    # Source file expansion.
    sources_table = project_table.get("sources", {})
    if not isinstance(sources_table, dict):
        raise WorkspaceError(
            "SUT2007",
            "`project.sources` must be a table",
            source_path=atman_file,
        )
    include_globs = sources_table.get("include", ["**/*.su"])
    exclude_globs = sources_table.get("exclude", [])
    for g in include_globs:
        if not isinstance(g, str):
            raise WorkspaceError(
                "SUT2015",
                "`project.sources.include` entries must be strings",
                source_path=atman_file,
            )
    for g in exclude_globs:
        if not isinstance(g, str):
            raise WorkspaceError(
                "SUT2015",
                "`project.sources.exclude` entries must be strings",
                source_path=atman_file,
            )
    sources = _expand_sources(project_dir, include_globs, exclude_globs)

    # Dependencies.
    deps_table = project_table.get("dependencies", {})
    if not isinstance(deps_table, dict):
        raise WorkspaceError(
            "SUT2007",
            "`project.dependencies` must be a table",
            source_path=atman_file,
        )
    dependencies: list[ProjectDependency] = []
    for dep_name, dep_ref in deps_table.items():
        if not isinstance(dep_ref, dict):
            raise WorkspaceError(
                "SUT2007",
                f"dependency `{dep_name}` must be a table "
                f"(e.g. `{dep_name} = {{ path = \"../corpus\" }}`)",
                source_path=atman_file,
            )
        dep_path_str = dep_ref.get("path")
        if not isinstance(dep_path_str, str):
            raise WorkspaceError(
                "SUT2007",
                f"dependency `{dep_name}` must have a `path` field",
                source_path=atman_file,
            )
        dep_path = (project_dir / dep_path_str).resolve()
        if not dep_path.is_dir():
            raise WorkspaceError(
                "SUT2010",
                f"dependency `{dep_name}` of project `{name}` "
                f"points to a directory that does not exist: {dep_path}",
                source_path=atman_file,
            )
        dependencies.append(ProjectDependency(name=dep_name, path=dep_path))

    return Project(
        name=name,
        path=project_dir,
        atman_file=atman_file,
        entry=entry_path,
        substrate=substrate,
        description=description,
        compiler_args=combined_args,
        sources=sources,
        dependencies=dependencies,
    )


def _expand_sources(
    project_dir: Path,
    include_globs: list[str],
    exclude_globs: list[str],
) -> list[Path]:
    """Expand include and exclude globs relative to `project_dir`.

    Returns absolute paths, deduplicated and sorted for determinism.
    The workspace's own `atman.toml` and any member atman.toml files
    are excluded automatically so a `**/*.su` default doesn't trip
    over them — they are not Sutra source.
    """
    included: set[Path] = set()
    for pattern in include_globs:
        for match in project_dir.glob(pattern):
            if match.is_file():
                included.add(match.resolve())
    excluded: set[Path] = set()
    for pattern in exclude_globs:
        for match in project_dir.glob(pattern):
            if match.is_file():
                excluded.add(match.resolve())
    remaining = included - excluded
    return sorted(remaining)


def _find_project_by_dir(
    projects: list[Project],
    target_dir: Path,
) -> Project | None:
    target = target_dir.resolve()
    for p in projects:
        if p.path.resolve() == target:
            return p
    return None


# ============================================================
# Topological sort + cycle detection
# ============================================================


def _topological_sort(
    projects: list[Project],
    projects_by_name: dict[str, Project],
    atman_path: Path,
) -> list[Project]:
    """Kahn's algorithm with cycle reporting."""
    in_degree: dict[str, int] = {p.name: 0 for p in projects}
    adjacency: dict[str, list[str]] = {p.name: [] for p in projects}
    for p in projects:
        for dep in p.dependencies:
            target = _find_project_by_dir(projects, dep.path)
            assert target is not None  # validated in load_workspace
            adjacency[target.name].append(p.name)
            in_degree[p.name] += 1

    queue = [name for name, deg in in_degree.items() if deg == 0]
    ordered: list[Project] = []
    while queue:
        name = queue.pop(0)
        ordered.append(projects_by_name[name])
        for consumer in adjacency[name]:
            in_degree[consumer] -= 1
            if in_degree[consumer] == 0:
                queue.append(consumer)

    if len(ordered) != len(projects):
        remaining = [p.name for p in projects if in_degree[p.name] > 0]
        raise WorkspaceError(
            "SUT2011",
            f"dependency cycle detected among projects: {remaining}",
            source_path=atman_path,
            details={"cycle": remaining},
        )
    return ordered


# ============================================================
# CLI convenience
# ============================================================


def _main(argv: Iterable[str] | None = None) -> int:
    """CLI for ad-hoc workspace validation.

    Usage: `python -m sutra_compiler.workspace <path-to-atman.toml>`
    """
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(
        prog="sutra_compiler.workspace",
        description="Parse and validate a Sutra workspace atman.toml.",
    )
    parser.add_argument("atman", help="Path to the workspace atman.toml")
    parser.add_argument(
        "--json", action="store_true",
        help="Emit a JSON summary of the resolved workspace to stdout.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        workspace = load_workspace(Path(args.atman))
    except WorkspaceError as e:
        print(str(e), file=sys.stderr)
        return 1

    if args.json:
        out = {
            "name": workspace.name,
            "sutra_version": workspace.sutra_version,
            "description": workspace.description,
            "default_substrate": workspace.default_substrate,
            "compiler_args": workspace.compiler_args,
            "projects": [
                {
                    "name": p.name,
                    "path": str(p.path),
                    "entry": str(p.entry),
                    "substrate": p.substrate,
                    "description": p.description,
                    "compiler_args": p.compiler_args,
                    "sources": [str(s) for s in p.sources],
                    "dependencies": [
                        {"name": d.name, "path": str(d.path)}
                        for d in p.dependencies
                    ],
                }
                for p in workspace.projects
            ],
        }
        print(json.dumps(out, indent=2))
    else:
        print(f"workspace: {workspace.name} (v{workspace.sutra_version})")
        print(f"  default_substrate: {workspace.default_substrate}")
        print(f"  projects in build order:")
        for p in workspace.projects:
            deps = ", ".join(d.name for d in p.dependencies) or "(none)"
            print(
                f"    - {p.name} [{p.substrate}] "
                f"({len(p.sources)} source files, deps: {deps})"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
