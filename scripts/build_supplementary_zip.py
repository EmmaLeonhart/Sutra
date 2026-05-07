"""
Build the NeurIPS 2026 supplementary-material zip for the Sutra paper.

Output: `sutra-neurips-supplementary.zip` at the repo root, a tightly-
scoped reproduction archive — only the files a NeurIPS reviewer needs
to verify the paper's empirical claims. The agent-runnable replication
skill sits at the archive root as `SKILL.md`; the human-facing
`README.md` (from `paper/SUPPLEMENTARY_README.md`) explains the layout
and points reviewers at the skill.

Run from the repo root:

    python scripts/build_supplementary_zip.py            # build
    python scripts/build_supplementary_zip.py --check    # dry-run, list

The zip is intentionally NOT committed to the repo — it is a build
artifact regenerated each run, gitignored.

What's included
===============

Top-level (copied from paper/):
    README.md       (from paper/SUPPLEMENTARY_README.md)
    SKILL.md        (from paper/SKILL.md)
    REPRODUCE.md    (from paper/REPRODUCE.md)

The Python compiler and its tests (the §4 / §5 / §3 substrate of every
paper claim):
    sdk/sutra-compiler/

The .su programs invoked by the §5 smoke test driver, plus the smoke
test driver itself and the test harness:
    examples/*.su
    examples/_smoke_test.py
    examples/_su_harness.py
    examples/atman.toml

The §3 reproduction scripts referenced in SKILL.md / REPRODUCE.md, plus
the reference output JSONs reviewers can diff against:
    experiments/rotation_binding_capacity*.py
    experiments/crosstalk_chain.py
    experiments/differentiable_training.py
    experiments/rotation_hashmap_capacity.py
    experiments/sutra_vs_torchhd*.py
    experiments/synthetic_subspace_validation.py
    experiments/scallop_compare/             (Dockerfile + run_compare.py)
    experiments/*_results.json               (reference outputs)

The Rust FFI shared library (used by `pytest test_sutradb_embedded.py`
for the embedded-codebook test). The workspace Cargo.toml is rewritten
at build time to drop sutra-cli / sutra-proto / sutra-studio members
that the FFI doesn't depend on:
    sutraDB/Cargo.toml             (regenerated, trimmed)
    sutraDB/Cargo.lock             (if present, for reproducible build)
    sutraDB/LICENSE
    sutraDB/sutra-core/
    sutraDB/sutra-hnsw/
    sutraDB/sutra-sparql/
    sutraDB/sutra-ffi/

User-facing syntax and language documentation (the same pages served
at sutralang.dev). Describes what is implemented today; speculative /
forward-looking design docs are NOT included:
    docs/what-is-sutra.md          overview
    docs/primitive-classes.md      type system
    docs/operators.md              operator surface
    docs/loops.md                  loop forms (do_while, while_loop, etc.)
    docs/logical-operations.md     Kleene three-valued logic
    docs/numeric-math.md           numeric primitives
    docs/memory.md                 extended-state-vector layout
    docs/compilation.md            compiler pipeline
    docs/ontology.md               class system
    docs/paradigms.md              comparison with imperative OO
    docs/vision.md                 the geometric-compilation framing
    docs/tutorials/                step-by-step tutorials

Cargo.toml regeneration
=======================

The workspace Cargo.toml is rewritten at zip-build time so the trimmed
members list (`sutra-core`, `sutra-hnsw`, `sutra-sparql`, `sutra-ffi`)
matches what the archive actually ships. Without this, `cargo build -p
sutra-ffi` inside the unzipped archive would fail with "current package
believes it's in a workspace when it's not" pointing at the missing
sutra-cli / sutra-proto manifests.
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
ARCHIVE_ROOT = "sutra-neurips-supplementary"


# Per-file additions: (source path relative to repo root, destination
# path inside archive).
TOP_LEVEL_FILES = [
    ("paper/SUPPLEMENTARY_README.md", "README.md"),
    ("paper/SKILL.md", "SKILL.md"),
    ("paper/REPRODUCE.md", "REPRODUCE.md"),
]

# Directories included verbatim (with the standard exclusions below
# applied during walk).
INCLUDE_DIRS = [
    "sdk/sutra-compiler",
    "sutraDB/sutra-core",
    "sutraDB/sutra-hnsw",
    "sutraDB/sutra-sparql",
    "sutraDB/sutra-ffi",
    "docs/tutorials",
]

# Specific files to include (no recursion).
INCLUDE_FILES = [
    # Examples needed by the smoke test runner.
    "examples/_smoke_test.py",
    "examples/_su_harness.py",
    "examples/atman.toml",
    # SutraDB workspace-level files we keep (Cargo.toml is regenerated
    # below; LICENSE and Cargo.lock are taken verbatim if present).
    "sutraDB/LICENSE",
    "sutraDB/Cargo.lock",
    # User-facing syntax / language documentation. These are the same
    # pages served at sutralang.dev — they describe what's implemented
    # today, not speculative design. Marketing / history / paper-link
    # pages are left out (index.md, demos.md, history.md,
    # theory-and-paper.md).
    "docs/what-is-sutra.md",
    "docs/primitive-classes.md",
    "docs/operators.md",
    "docs/loops.md",
    "docs/logical-operations.md",
    "docs/numeric-math.md",
    "docs/memory.md",
    "docs/compilation.md",
    "docs/ontology.md",
    "docs/paradigms.md",
    "docs/vision.md",
]

# Glob patterns relative to repo root, evaluated as "include every match."
INCLUDE_GLOBS = [
    # All Sutra source programs.
    "examples/*.su",
    # Paper-claim reproduction scripts in experiments/.
    "experiments/rotation_binding_capacity.py",
    "experiments/rotation_binding_capacity_llm.py",
    "experiments/rotation_binding_capacity_bioinformatics.py",
    "experiments/crosstalk_chain.py",
    "experiments/differentiable_training.py",
    "experiments/rotation_hashmap_capacity.py",
    "experiments/sutra_vs_torchhd.py",
    "experiments/sutra_vs_torchhd_latency.py",
    "experiments/synthetic_subspace_validation.py",
    # Reference output JSONs (so reviewers can diff against their runs).
    "experiments/*_results.json",
    # Cross-paradigm comparison (Sutra / Scallop / DeepProbLog / TorchHD).
    "experiments/scallop_compare/*",
]

# Examples to suppress from the `*.su` glob (none currently — the
# scratch / legacy `_*.su` files were deleted from the source tree).
EXAMPLES_SU_EXCLUDE: set[str] = set()


# Exclusions applied during recursive walks.
EXCLUDE_DIR_NAMES = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "node_modules",
    "target",
    ".venv",
    "venv",
    ".pdf-check",
    ".pdf-prev",
    "benches",  # benchmarks for SutraDB crates — large, not paper-cited
}

EXCLUDE_FILE_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".log",
    ".pt",  # trained weights — regeneratable, ~3.5 MB each
}

EXCLUDE_FILE_NAMES = {
    ".DS_Store",
    "Thumbs.db",
    ".gitignore",
    ".gitattributes",
}


# The trimmed Cargo.toml written into the archive at sutraDB/Cargo.toml.
# Original lists sutra-cli / sutra-proto / sutra-studio etc. as workspace
# members; those crates are not in the archive, so the original would
# fail `cargo build -p sutra-ffi` with missing-manifest errors. This
# trimmed version lists only the four crates the archive ships.
TRIMMED_CARGO_TOML = """\
# Workspace Cargo.toml — trimmed for the NeurIPS supplementary archive.
# The full SutraDB workspace lists sutra-core, sutra-hnsw, sutra-sparql,
# sutra-proto, sutra-cli, sutra-ffi as members. The supplementary
# archive ships only the four crates `cargo build -p sutra-ffi` needs.
# The full project lives at https://github.com/EmmaLeonhart/SutraDB.

[workspace]
members = [
    "sutra-core",
    "sutra-hnsw",
    "sutra-sparql",
    "sutra-ffi",
]
resolver = "2"

[workspace.package]
version = "0.3.7"
edition = "2021"
license = "Apache-2.0"
authors = []
repository = "https://github.com/EmmaLeonhart/SutraDB"
description = "A lean RDF-star triplestore with native HNSW vector indexing and hybrid SPARQL"

[workspace.dependencies]
# Error handling
thiserror = "1"
anyhow = "1"

# Async
tokio = { version = "1", features = ["full"] }

# Serialization
serde = { version = "1", features = ["derive"] }
serde_json = "1"

# Logging
tracing = "0.1"
tracing-subscriber = { version = "0.3", features = ["env-filter"] }

# Storage
memmap2 = "0.9"
sled = "0.34"

# Hashing
xxhash-rust = { version = "0.8", features = ["xxh3"] }

# Parallelism
rayon = "1"

# URL encoding
urlencoding = "2"

# Benchmarking (used by [dev-dependencies] in member crates)
criterion = { version = "0.5", features = ["html_reports"] }

# Intra-workspace
sutra-core   = { path = "sutra-core" }
sutra-hnsw   = { path = "sutra-hnsw" }
sutra-sparql = { path = "sutra-sparql" }

[profile.release]
opt-level = 3
lto = "thin"
codegen-units = 1

[profile.bench]
inherits = "release"
debug = true
"""


def should_include_file(path: Path) -> bool:
    if path.name in EXCLUDE_FILE_NAMES:
        return False
    if path.suffix in EXCLUDE_FILE_SUFFIXES:
        return False
    return True


def walk_for_zip(src_dir: Path) -> list[Path]:
    """Walk a directory and return the file paths that should be included.

    Excludes directories named in EXCLUDE_DIR_NAMES at any depth; excludes
    files matching EXCLUDE_FILE_SUFFIXES / EXCLUDE_FILE_NAMES.
    """
    if not src_dir.exists():
        print(f"  warning: {src_dir.relative_to(REPO_ROOT)} not found, skipping",
              file=sys.stderr)
        return []
    out: list[Path] = []
    for path in src_dir.rglob("*"):
        rel = path.relative_to(src_dir)
        if any(part in EXCLUDE_DIR_NAMES for part in rel.parts):
            continue
        if path.is_file() and should_include_file(path):
            out.append(path)
    return out


def build(output_path: Path, *, check_only: bool = False) -> None:
    """Build the supplementary zip at output_path. Prints a summary."""
    print(f"Repo root: {REPO_ROOT}")
    print(f"Output:    {output_path}")
    print()

    plan: list[tuple[str, Path | str]] = []  # (archive path, source path or content string)

    # Top-level files.
    for src_rel, dst_in_archive in TOP_LEVEL_FILES:
        src = REPO_ROOT / src_rel
        if not src.exists():
            print(f"  ERROR: required top-level file missing: {src_rel}",
                  file=sys.stderr)
            sys.exit(1)
        plan.append((f"{ARCHIVE_ROOT}/{dst_in_archive}", src))

    # Directories included verbatim.
    for d in INCLUDE_DIRS:
        src_dir = REPO_ROOT / d
        files = walk_for_zip(src_dir)
        for f in files:
            arc = f"{ARCHIVE_ROOT}/{f.relative_to(REPO_ROOT).as_posix()}"
            plan.append((arc, f))

    # Specific single files.
    for f_rel in INCLUDE_FILES:
        src = REPO_ROOT / f_rel
        if not src.exists():
            print(f"  warning: include-file {f_rel} not found, skipping",
                  file=sys.stderr)
            continue
        arc = f"{ARCHIVE_ROOT}/{f_rel}"
        plan.append((arc, src))

    # Globs.
    for pattern in INCLUDE_GLOBS:
        for src in REPO_ROOT.glob(pattern):
            if not src.is_file():
                continue
            rel_str = src.relative_to(REPO_ROOT).as_posix()
            if rel_str in EXAMPLES_SU_EXCLUDE:
                continue
            if not should_include_file(src):
                continue
            arc = f"{ARCHIVE_ROOT}/{rel_str}"
            plan.append((arc, src))

    # Generated files: trimmed sutraDB/Cargo.toml. Append last so it
    # appears after the verbatim sutraDB/sutra-* directories in the
    # zip's central directory; not strictly required but readable.
    plan.append((f"{ARCHIVE_ROOT}/sutraDB/Cargo.toml", TRIMMED_CARGO_TOML))

    # Deduplicate while preserving first-occurrence order.
    seen: set[str] = set()
    deduped: list[tuple[str, Path | str]] = []
    for arc, src in plan:
        if arc in seen:
            continue
        seen.add(arc)
        deduped.append((arc, src))
    plan = deduped

    # Summary.
    total_bytes = 0
    for arc, src in plan:
        if isinstance(src, Path):
            total_bytes += src.stat().st_size
        else:
            total_bytes += len(src.encode("utf-8"))
    print(f"Files to include: {len(plan)}")
    print(f"Uncompressed total: {total_bytes / 1024 / 1024:.1f} MB")
    print()

    if check_only:
        # Group by archive top-level dir for a readable summary.
        from collections import defaultdict
        by_dir: dict[str, list[str]] = defaultdict(list)
        for arc, _ in plan:
            parts = arc.split("/", 2)
            key = parts[1] if len(parts) > 1 else "_root"
            by_dir[key].append(arc)
        for k in sorted(by_dir):
            print(f"  {k}/  ({len(by_dir[k])} files)")
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        output_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
    ) as zf:
        for arc, src in plan:
            if isinstance(src, Path):
                zf.write(src, arcname=arc)
            else:
                zf.writestr(arc, src)

    out_size_mb = output_path.stat().st_size / 1024 / 1024
    print(f"Wrote {output_path} ({out_size_mb:.1f} MB compressed)")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "sutra-neurips-supplementary.zip",
        help="Output zip path (default: sutra-neurips-supplementary.zip in repo root)",
    )
    p.add_argument(
        "--check",
        action="store_true",
        help="Print what would be included without writing the zip",
    )
    args = p.parse_args()
    build(args.output, check_only=args.check)


if __name__ == "__main__":
    main()
