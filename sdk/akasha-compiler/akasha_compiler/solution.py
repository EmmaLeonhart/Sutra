"""Solution and project file parser for the Akasha compiler.

Formal schema: `planning/akasha-spec/22-solutions.md`. This file is the
reference Python implementation that the schema document describes — it
is the source of truth for "what does a well-formed `.aksln` / `.akproj`
mean," and the IntelliJ plugin's Kotlin data model is a direct port of
the types defined here.

Usage:

    from pathlib import Path
    from akasha_compiler.solution import load_solution

    solution = load_solution(Path("embedding-pipeline.aksln"))
    for project in solution.projects_in_build_order:
        print(project.name, project.substrate, project.sources)

Errors are raised as `SolutionError` with a stable `AKA####` code in
the `AKA2000-AKA2099` range reserved for solution-model errors in the
spec. Callers who want machine-readable output can catch
`SolutionError` and inspect `err.code`, `err.message`, and
`err.details`.

Design notes:

- TOML parsing uses the Python 3.11+ standard library `tomllib` module.
  No third-party dependency; the reference parser runs on any Akasha
  toolchain installation that has Python 3.11 or newer.
- Filesystem paths inside TOML are always resolved relative to the
  file that contains them (the `.aksln` for solution-level paths, the
  `.akproj` for project-level paths). This is documented in the spec
  and enforced here.
- Glob expansion uses `pathlib.Path.glob` with `**` support.
- Dependency resolution uses a three-pass approach: parse all project
  files, build the edge set, then topologically sort with a cycle
  detector that reports the exact cycle on error.
"""

from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


# ============================================================
# Error type
# ============================================================


class SolutionError(Exception):
    """Raised for any invalid solution or project file.

    Attributes:
        code: The `AKA####` diagnostic code from the spec (§Error reporting).
        message: Human-readable one-line summary.
        details: Optional structured payload — for cycle errors this is
            the list of project names in cycle order; for path errors
            this is the offending path; etc.
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


VALID_SUBSTRATES = frozenset({"silicon", "fly-brain", "logit"})
PROJECT_NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_-]*$")


@dataclass
class ProjectDependency:
    """One inter-project edge as declared in a `.akproj` file."""

    name: str
    path: Path  # absolute, resolved


@dataclass
class Project:
    """One project within a solution, fully resolved and validated."""

    name: str
    path: Path  # absolute path to the project directory
    akproj_file: Path  # absolute path to the `.akproj` file itself
    entry: Path  # absolute path to the entry-point `.ak` file
    substrate: str  # one of VALID_SUBSTRATES
    description: str
    compiler_args: list[str]
    sources: list[Path]  # absolute paths, expanded from the globs
    dependencies: list[ProjectDependency]


@dataclass
class Solution:
    """One solution, fully resolved and validated."""

    name: str
    akasha_version: str
    description: str
    default_substrate: str
    compiler_args: list[str]
    aksln_file: Path
    projects: list[Project]  # in topological (build) order
    projects_by_name: dict[str, Project] = field(default_factory=dict)

    @property
    def projects_in_build_order(self) -> list[Project]:
        """Alias for `projects`; kept for readability at call sites."""
        return self.projects


# ============================================================
# TOML helpers
# ============================================================


def _read_toml(path: Path) -> dict[str, Any]:
    """Read a TOML file and return its top-level table.

    Raises:
        SolutionError(AKA2001 or AKA2006) on malformed TOML.
    """
    try:
        with path.open("rb") as f:
            return tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        code = "AKA2001" if path.suffix == ".aksln" else "AKA2006"
        raise SolutionError(
            code, f"file is not valid TOML: {e}", source_path=path
        ) from e
    except OSError as e:
        raise SolutionError(
            "AKA2004" if path.suffix == ".aksln" else "AKA2004",
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
        raise SolutionError(
            code,
            f"missing required field `{key}`",
            source_path=source_path,
        )
    if not isinstance(value, str):
        raise SolutionError(
            code,
            f"field `{key}` must be a string, got {type(value).__name__}",
            source_path=source_path,
        )
    return value


# ============================================================
# Solution loading
# ============================================================


def load_solution(aksln_path: Path) -> Solution:
    """Load, parse, validate, and resolve a solution file.

    This is the main public entry point. It runs every stage of the
    resolution algorithm from §"Resolution algorithm" in the spec:
    TOML parse → schema validate → project discovery → dependency
    graph → topological sort → Solution object.
    """
    aksln_path = aksln_path.resolve()
    if not aksln_path.is_file():
        raise SolutionError(
            "AKA2004",
            f"solution file does not exist: {aksln_path}",
            source_path=aksln_path,
        )
    doc = _read_toml(aksln_path)

    solution_table = doc.get("solution")
    if not isinstance(solution_table, dict):
        raise SolutionError(
            "AKA2002",
            "solution file is missing the [solution] table",
            source_path=aksln_path,
        )

    name = _require_string(
        solution_table, "name", code="AKA2002", source_path=aksln_path,
    )
    akasha_version = _require_string(
        solution_table, "akasha_version",
        code="AKA2002", source_path=aksln_path,
    )
    description = solution_table.get("description", "")
    if not isinstance(description, str):
        raise SolutionError(
            "AKA2002",
            "`solution.description` must be a string",
            source_path=aksln_path,
        )

    default_substrate = solution_table.get("default_substrate", "silicon")
    if default_substrate not in VALID_SUBSTRATES:
        raise SolutionError(
            "AKA2014",
            f"unknown `solution.default_substrate` value `{default_substrate}`; "
            f"must be one of {sorted(VALID_SUBSTRATES)}",
            source_path=aksln_path,
        )

    compiler_args = solution_table.get("compiler_args", [])
    if not isinstance(compiler_args, list) or not all(
        isinstance(a, str) for a in compiler_args
    ):
        raise SolutionError(
            "AKA2002",
            "`solution.compiler_args` must be a list of strings",
            source_path=aksln_path,
        )

    project_entries = doc.get("project")
    if not isinstance(project_entries, list) or len(project_entries) == 0:
        raise SolutionError(
            "AKA2002",
            "solution file must contain at least one [[project]] entry",
            source_path=aksln_path,
        )

    # First pass: discover every project and load its .akproj file,
    # applying any solution-level overrides, without yet validating
    # dependencies.
    solution_dir = aksln_path.parent
    projects_unordered: list[Project] = []
    for idx, entry in enumerate(project_entries):
        if not isinstance(entry, dict):
            raise SolutionError(
                "AKA2002",
                f"[[project]] entry #{idx} must be a table",
                source_path=aksln_path,
            )
        rel_path = _require_string(
            entry, "path", code="AKA2002", source_path=aksln_path,
        )
        project_dir = (solution_dir / rel_path).resolve()
        if not project_dir.is_dir():
            raise SolutionError(
                "AKA2004",
                f"project path does not exist: {project_dir}",
                source_path=aksln_path,
                details={"index": idx, "path": str(project_dir)},
            )
        akproj_name = entry.get("akproj")
        project = _load_project(
            project_dir,
            akproj_name_override=akproj_name,
            solution_default_substrate=default_substrate,
            solution_compiler_args=compiler_args,
            solution_entry_overrides=entry,
            aksln_path=aksln_path,
        )
        projects_unordered.append(project)

    # Second pass: verify every dependency resolves to a project that
    # actually exists in this solution, and that the dependency's name
    # matches the target project's declared name.
    projects_by_name: dict[str, Project] = {}
    for p in projects_unordered:
        if p.name in projects_by_name:
            raise SolutionError(
                "AKA2007",
                f"two projects in the same solution share the name `{p.name}`",
                source_path=aksln_path,
            )
        projects_by_name[p.name] = p
    for p in projects_unordered:
        for dep in p.dependencies:
            target = _find_project_by_dir(projects_unordered, dep.path)
            if target is None:
                raise SolutionError(
                    "AKA2013",
                    f"project `{p.name}` depends on a project outside the "
                    f"current solution: {dep.path}",
                    source_path=p.akproj_file,
                )
            if target.name != dep.name:
                raise SolutionError(
                    "AKA2008",
                    f"dependency key `{dep.name}` in project `{p.name}` "
                    f"does not match target project's declared name "
                    f"`{target.name}`",
                    source_path=p.akproj_file,
                )
            if target.name == p.name:
                raise SolutionError(
                    "AKA2012",
                    f"project `{p.name}` declares a self-dependency",
                    source_path=p.akproj_file,
                )

    # Third pass: topologically sort. Kahn's algorithm with an explicit
    # cycle detector that reports the cycle in order.
    ordered = _topological_sort(projects_unordered, projects_by_name, aksln_path)

    return Solution(
        name=name,
        akasha_version=akasha_version,
        description=description,
        default_substrate=default_substrate,
        compiler_args=list(compiler_args),
        aksln_file=aksln_path,
        projects=ordered,
        projects_by_name=projects_by_name,
    )


# ============================================================
# Project loading
# ============================================================


def _load_project(
    project_dir: Path,
    *,
    akproj_name_override: str | None,
    solution_default_substrate: str,
    solution_compiler_args: list[str],
    solution_entry_overrides: dict[str, Any],
    aksln_path: Path,
) -> Project:
    """Locate, parse, validate, and return one project."""
    if akproj_name_override:
        akproj_file = project_dir / akproj_name_override
    else:
        akproj_files = sorted(project_dir.glob("*.akproj"))
        if len(akproj_files) == 0:
            raise SolutionError(
                "AKA2005",
                f"project directory contains no .akproj file: {project_dir}",
                source_path=aksln_path,
            )
        if len(akproj_files) > 1:
            raise SolutionError(
                "AKA2005",
                f"project directory contains multiple .akproj files; use "
                f"`akproj = \"name.akproj\"` in the solution's [[project]] "
                f"entry to disambiguate. Found: "
                f"{[f.name for f in akproj_files]}",
                source_path=aksln_path,
            )
        akproj_file = akproj_files[0]

    if not akproj_file.is_file():
        raise SolutionError(
            "AKA2004",
            f"project file does not exist: {akproj_file}",
            source_path=aksln_path,
        )
    doc = _read_toml(akproj_file)

    project_table = doc.get("project")
    if not isinstance(project_table, dict):
        raise SolutionError(
            "AKA2007",
            "project file is missing the [project] table",
            source_path=akproj_file,
        )

    name = _require_string(
        project_table, "name", code="AKA2007", source_path=akproj_file,
    )
    if not PROJECT_NAME_RE.match(name):
        raise SolutionError(
            "AKA2007",
            f"project name `{name}` is not a valid identifier "
            f"(must match {PROJECT_NAME_RE.pattern})",
            source_path=akproj_file,
        )

    entry_name = _require_string(
        project_table, "entry", code="AKA2007", source_path=akproj_file,
    )
    entry_path = (project_dir / entry_name).resolve()
    if not entry_path.is_file():
        raise SolutionError(
            "AKA2009",
            f"entry file does not exist: {entry_path}",
            source_path=akproj_file,
        )

    # Substrate resolution: project override > solution override > project
    # .akproj > solution default.
    substrate = solution_entry_overrides.get(
        "substrate",
        project_table.get("substrate", solution_default_substrate),
    )
    if substrate not in VALID_SUBSTRATES:
        raise SolutionError(
            "AKA2014",
            f"unknown substrate `{substrate}` for project `{name}`; "
            f"must be one of {sorted(VALID_SUBSTRATES)}",
            source_path=akproj_file,
        )

    description = project_table.get("description", "")
    if not isinstance(description, str):
        raise SolutionError(
            "AKA2007",
            "`project.description` must be a string",
            source_path=akproj_file,
        )

    per_project_args = project_table.get("compiler_args", [])
    if not isinstance(per_project_args, list) or not all(
        isinstance(a, str) for a in per_project_args
    ):
        raise SolutionError(
            "AKA2007",
            "`project.compiler_args` must be a list of strings",
            source_path=akproj_file,
        )
    combined_args = list(solution_compiler_args) + list(per_project_args)

    # Source file expansion.
    sources_table = project_table.get("sources", {})
    if not isinstance(sources_table, dict):
        raise SolutionError(
            "AKA2007",
            "`project.sources` must be a table",
            source_path=akproj_file,
        )
    include_globs = sources_table.get("include", ["**/*.ak"])
    exclude_globs = sources_table.get("exclude", [])
    for g in include_globs:
        if not isinstance(g, str):
            raise SolutionError(
                "AKA2015",
                "`project.sources.include` entries must be strings",
                source_path=akproj_file,
            )
    for g in exclude_globs:
        if not isinstance(g, str):
            raise SolutionError(
                "AKA2015",
                "`project.sources.exclude` entries must be strings",
                source_path=akproj_file,
            )
    sources = _expand_sources(project_dir, include_globs, exclude_globs)

    # Dependencies.
    deps_table = project_table.get("dependencies", {})
    if not isinstance(deps_table, dict):
        raise SolutionError(
            "AKA2007",
            "`project.dependencies` must be a table",
            source_path=akproj_file,
        )
    dependencies: list[ProjectDependency] = []
    for dep_name, dep_ref in deps_table.items():
        if not isinstance(dep_ref, dict):
            raise SolutionError(
                "AKA2007",
                f"dependency `{dep_name}` must be a table "
                f"(e.g. `{dep_name} = {{ path = \"../corpus\" }}`)",
                source_path=akproj_file,
            )
        dep_path_str = dep_ref.get("path")
        if not isinstance(dep_path_str, str):
            raise SolutionError(
                "AKA2007",
                f"dependency `{dep_name}` must have a `path` field",
                source_path=akproj_file,
            )
        dep_path = (project_dir / dep_path_str).resolve()
        if not dep_path.is_dir():
            raise SolutionError(
                "AKA2010",
                f"dependency `{dep_name}` of project `{name}` "
                f"points to a directory that does not exist: {dep_path}",
                source_path=akproj_file,
            )
        dependencies.append(ProjectDependency(name=dep_name, path=dep_path))

    return Project(
        name=name,
        path=project_dir,
        akproj_file=akproj_file,
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
    aksln_path: Path,
) -> list[Project]:
    """Kahn's algorithm with cycle reporting."""
    in_degree: dict[str, int] = {p.name: 0 for p in projects}
    adjacency: dict[str, list[str]] = {p.name: [] for p in projects}
    for p in projects:
        for dep in p.dependencies:
            target = _find_project_by_dir(projects, dep.path)
            assert target is not None  # validated in load_solution
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
        raise SolutionError(
            "AKA2011",
            f"dependency cycle detected among projects: {remaining}",
            source_path=aksln_path,
            details={"cycle": remaining},
        )
    return ordered


# ============================================================
# CLI convenience
# ============================================================


def _main(argv: Iterable[str] | None = None) -> int:
    """CLI for ad-hoc solution validation.

    Usage: `python -m akasha_compiler.solution <path-to-.aksln>`
    """
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(
        prog="akasha_compiler.solution",
        description="Parse and validate an Akasha solution file.",
    )
    parser.add_argument("aksln", help="Path to the .aksln file")
    parser.add_argument(
        "--json", action="store_true",
        help="Emit a JSON summary of the resolved solution to stdout.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        solution = load_solution(Path(args.aksln))
    except SolutionError as e:
        print(str(e), file=sys.stderr)
        return 1

    if args.json:
        out = {
            "name": solution.name,
            "akasha_version": solution.akasha_version,
            "description": solution.description,
            "default_substrate": solution.default_substrate,
            "compiler_args": solution.compiler_args,
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
                for p in solution.projects
            ],
        }
        print(json.dumps(out, indent=2))
    else:
        print(f"solution: {solution.name} (v{solution.akasha_version})")
        print(f"  default_substrate: {solution.default_substrate}")
        print(f"  projects in build order:")
        for p in solution.projects:
            deps = ", ".join(d.name for d in p.dependencies) or "(none)"
            print(
                f"    - {p.name} [{p.substrate}] "
                f"({len(p.sources)} source files, deps: {deps})"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
