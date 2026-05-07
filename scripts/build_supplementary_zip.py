"""
Build the NeurIPS 2026 supplementary-material zip for the Sutra paper.

The output, `sutra-neurips-supplementary.zip`, contains a clean snapshot
of the Sutra repository sufficient to reproduce every empirical claim
in the paper. The agent-runnable replication skill is at the archive
root as `SKILL.md` (copied from `paper/SKILL.md`). The archive root
also contains a top-level `README.md` (copied from
`paper/SUPPLEMENTARY_README.md`) explaining what is in the archive,
where the skill lives, and how to run it.

The zip is intentionally NOT committed to the repo — it is a build
artifact regenerated each time. Run from the repo root:

    python scripts/build_supplementary_zip.py

Optional flags:
    --output PATH  Where to write the zip (default:
                   sutra-neurips-supplementary.zip in the repo root)
    --check        Print what would be included without writing the zip

The directories included verbatim are:
    sdk/             compiler + plugins + tests
    examples/        .su programs + smoke test driver
    experiments/     paper-empirical reproduction scripts
    sutraDB/         Rust FFI for embedded codebook
    tests/           top-level integration tests
    planning/sutra-spec/  language specification

Files excluded everywhere:
    .git, .gitignore, .gitattributes, __pycache__, *.pyc, .DS_Store,
    .pytest_cache, target/ (Rust build artifacts), node_modules,
    *.log, *.pt (regeneratable trained weights), .venv, .ruff_cache.

Top-level files added:
    README.md       (from paper/SUPPLEMENTARY_README.md)
    SKILL.md        (from paper/SKILL.md)
    REPRODUCE.md    (from paper/REPRODUCE.md)
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent

# Directories included verbatim under the archive root.
INCLUDE_DIRS = [
    "sdk",
    "examples",
    "experiments",
    "sutraDB",
    "tests",
    "planning/sutra-spec",
]

# Per-file additions: (source path relative to repo root, destination
# path inside archive).
TOP_LEVEL_FILES = [
    ("paper/SUPPLEMENTARY_README.md", "README.md"),
    ("paper/SKILL.md", "SKILL.md"),
    ("paper/REPRODUCE.md", "REPRODUCE.md"),
]

# Filename / extension exclusions applied during the walk.
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
}

ARCHIVE_ROOT = "sutra-neurips-supplementary"


def should_include_dir(path: Path) -> bool:
    return path.name not in EXCLUDE_DIR_NAMES


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
        # Reject if any ancestor directory is excluded.
        if any(part in EXCLUDE_DIR_NAMES for part in path.relative_to(src_dir).parts):
            continue
        if path.is_file() and should_include_file(path):
            out.append(path)
    return out


def build(output_path: Path, *, check_only: bool = False) -> None:
    """Build the supplementary zip at output_path. Prints a summary."""
    print(f"Repo root: {REPO_ROOT}")
    print(f"Output:    {output_path}")
    print()

    plan: list[tuple[Path, str]] = []  # (source path, archive path)

    # Top-level files first.
    for src_rel, dst_in_archive in TOP_LEVEL_FILES:
        src = REPO_ROOT / src_rel
        if not src.exists():
            print(f"  ERROR: required top-level file missing: {src_rel}",
                  file=sys.stderr)
            sys.exit(1)
        plan.append((src, f"{ARCHIVE_ROOT}/{dst_in_archive}"))

    # Then the included directories.
    for d in INCLUDE_DIRS:
        src_dir = REPO_ROOT / d
        files = walk_for_zip(src_dir)
        for f in files:
            arc = f"{ARCHIVE_ROOT}/{f.relative_to(REPO_ROOT).as_posix()}"
            plan.append((f, arc))

    # Summary.
    total_bytes = sum(src.stat().st_size for src, _ in plan)
    print(f"Files to include: {len(plan)}")
    print(f"Uncompressed total: {total_bytes / 1024 / 1024:.1f} MB")
    print()

    if check_only:
        for src, arc in plan[:30]:
            print(f"  {arc}")
        if len(plan) > 30:
            print(f"  ... and {len(plan) - 30} more")
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        output_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
    ) as zf:
        for src, arc in plan:
            zf.write(src, arcname=arc)

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
