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

Top-level (copied from paper/supplementary/):
    README.md       (from paper/supplementary/README.md)
    SKILL.md        (from paper/supplementary/SKILL.md)
    REPRODUCE.md    (from paper/supplementary/REPRODUCE.md)
    SYNTAX.md       (from paper/supplementary/SYNTAX.md)

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

Language reference at the archive root, written specifically for
the anonymized supplementary (no author / repo identification, no
live-site references):
    SYNTAX.md                      types, operators, loops,
                                   compilation pipeline

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
# path inside archive). All four supplementary docs live under
# paper/supplementary/ and are written specifically for the
# anonymized archive (no author / repo identification, no live-
# site references). They are not the same as the docs/ pages
# served at the public site.
TOP_LEVEL_FILES = [
    ("paper/supplementary/README.md", "README.md"),
    ("paper/supplementary/SKILL.md", "SKILL.md"),
    ("paper/supplementary/REPRODUCE.md", "REPRODUCE.md"),
    ("paper/supplementary/SYNTAX.md", "SYNTAX.md"),
]

# Directories included verbatim (with the standard exclusions below
# applied during walk).
INCLUDE_DIRS = [
    "sdk/sutra-compiler",
    "sutraDB/sutra-core",
    "sutraDB/sutra-hnsw",
    "sutraDB/sutra-sparql",
    "sutraDB/sutra-ffi",
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
# Repository / author identification is omitted for double-blind
# review; the full project metadata lives upstream.
TRIMMED_CARGO_TOML = """\
# Workspace Cargo.toml — trimmed for the supplementary archive.
# The full upstream workspace lists sutra-core, sutra-hnsw,
# sutra-sparql, sutra-proto, sutra-cli, sutra-ffi as members. The
# archive ships only the four crates `cargo build -p sutra-ffi`
# needs.

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


# File extensions whose text content gets scrubbed on the way into the
# zip. Two layers are applied: (1) anonymization scrubs that strip
# author / repo identifiers, (2) comment stripping that removes ALL
# comments (line + block + Python docstrings). The source repo is
# untouched; only the archive copies are stripped.
SCRUB_TEXT_SUFFIXES = {".py", ".md", ".su", ".rs", ".toml", ".txt"}

# Comment stripping is applied to source files but NOT to docs. The
# docs files at the archive root (README.md / SKILL.md / REPRODUCE.md
# / SYNTAX.md) are themselves the documentation; markdown text is not
# "comments" that should be removed.
COMMENT_STRIP_SUFFIXES = {".py", ".su", ".rs", ".toml"}


# Path fragments where comment stripping is disabled. The test corpus
# directories contain .su files that are deliberately malformed — an
# unterminated /* block comment, etc. — to exercise specific parser /
# diagnostic paths. Stripping comments from those files removes the
# malformation the test is verifying, which then fails. Same logic
# applies anywhere a comment is itself the test fixture content.
COMMENT_STRIP_PATH_DISABLE = (
    "tests/corpus/",
    "tests\\corpus\\",
)


import re as _re

_SCRUB_PATTERNS: list[tuple[_re.Pattern[str], str]] = [
    (_re.compile(r"\(Emma (\d{4}-\d{2}-\d{2})([^)]*)\)"), r"(\1\2)"),
    (_re.compile(r"\bper Emma (\d{4}-\d{2}-\d{2})\b"), r"per a \1 design note"),
    (_re.compile(r"\bPer Emma (\d{4}-\d{2}-\d{2})\b"), r"Per a \1 design note"),
    (_re.compile(r"\bEmma (\d{4}-\d{2}-\d{2}):"), r"Design note \1:"),
    (_re.compile(r"\bEmma (\d{4}-\d{2}-\d{2})\b"), r"\1"),
    (_re.compile(r"\bEmma's\b"), "the"),
    (_re.compile(r"\bEmma observed\b"), "observation:"),
    (_re.compile(r"\bEmma\b"), ""),
    (_re.compile(r"https?://github\.com/EmmaLeonhart/[A-Za-z0-9_.-]+"), "(upstream repository)"),
    (_re.compile(r"\bEmmaLeonhart\b"), ""),
    (_re.compile(r"\bImmanuelle\b"), ""),
    (_re.compile(r"\bambie\b"), ""),
    (_re.compile(r"\bsutralang\.dev\b"), "(project site)"),
]


def scrub_text(content: str) -> str:
    """Apply anonymization scrubs (author / repo identifiers) to a
    text payload. Used for files added to the supplementary archive.
    """
    out = content
    for pat, repl in _SCRUB_PATTERNS:
        out = pat.sub(repl, out)
    return out


def strip_comments_python(src: str) -> str:
    """Remove ALL comments and docstrings from Python source.

    Two passes:
    1. AST-walk to drop docstrings (the first string-literal expression
       statement of any module / class / function / async function).
       Re-emit via ast.unparse — formatting is reset, but the program
       is functionally identical and contains no docstrings.
    2. tokenize-walk to drop COMMENT tokens. Run on the docstring-free
       output of pass 1.

    On parse error, falls back to tokenize-only line-comment stripping.
    """
    import ast
    import io
    import tokenize as _tokenize

    try:
        tree = ast.parse(src)
    except SyntaxError:
        return _strip_python_line_comments_only(src)

    for node in ast.walk(tree):
        if isinstance(
            node,
            (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
        ):
            if (
                node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)
            ):
                node.body.pop(0)
                if not node.body:
                    node.body.append(ast.Pass())

    docstring_free = ast.unparse(tree)

    try:
        tokens = []
        for tok in _tokenize.generate_tokens(
            io.StringIO(docstring_free).readline
        ):
            if tok.type == _tokenize.COMMENT:
                continue
            tokens.append(tok)
        return _tokenize.untokenize(tokens)
    except (_tokenize.TokenizeError, IndentationError):
        return docstring_free


def _strip_python_line_comments_only(src: str) -> str:
    import io
    import tokenize as _tokenize
    try:
        tokens = []
        for tok in _tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type == _tokenize.COMMENT:
                continue
            tokens.append(tok)
        return _tokenize.untokenize(tokens)
    except (_tokenize.TokenizeError, IndentationError):
        return src


def strip_comments_clike(src: str) -> str:
    """Remove // line comments and /* */ block comments. Aware of
    string literals so // inside a string is preserved. Used for .su
    and .rs sources.
    """
    out: list[str] = []
    i = 0
    n = len(src)
    while i < n:
        c = src[i]
        if c in '"\'':
            quote = c
            out.append(c)
            i += 1
            while i < n and src[i] != quote:
                if src[i] == "\\" and i + 1 < n:
                    out.append(src[i])
                    out.append(src[i + 1])
                    i += 2
                else:
                    out.append(src[i])
                    i += 1
            if i < n:
                out.append(src[i])
                i += 1
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "/":
            while i < n and src[i] != "\n":
                i += 1
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "*":
            i += 2
            while i + 1 < n and not (src[i] == "*" and src[i + 1] == "/"):
                i += 1
            i += 2
            continue
        out.append(c)
        i += 1
    result = "".join(out)
    # Collapse runs of blank lines left by removed block comments.
    result = _re.sub(r"\n{3,}", "\n\n", result)
    return result


def strip_comments_toml(src: str) -> str:
    """Remove # line comments from TOML, preserving in-string #."""
    out_lines: list[str] = []
    for line in src.splitlines(keepends=True):
        in_string = False
        quote = None
        i = 0
        while i < len(line):
            c = line[i]
            if c in '"\'':
                if not in_string:
                    in_string = True
                    quote = c
                elif c == quote:
                    in_string = False
                    quote = None
            elif c == "#" and not in_string:
                trailing_nl = "\n" if line.endswith("\n") else ""
                line = line[:i].rstrip() + trailing_nl
                break
            i += 1
        if line.strip() or not out_lines or out_lines[-1].strip():
            out_lines.append(line)
    return "".join(out_lines)


def strip_comments(src: str, suffix: str) -> str:
    """Dispatch comment stripping by file suffix."""
    if suffix == ".py":
        return strip_comments_python(src)
    if suffix in (".su", ".rs"):
        return strip_comments_clike(src)
    if suffix == ".toml":
        return strip_comments_toml(src)
    return src


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
                if src.suffix in SCRUB_TEXT_SUFFIXES:
                    # Two-pass scrub: anonymize first, then strip
                    # comments (where applicable). Source repo
                    # untouched; only the archive copy is stripped.
                    raw = src.read_text(encoding="utf-8")
                    raw = scrub_text(raw)
                    if src.suffix in COMMENT_STRIP_SUFFIXES and not any(
                        seg in arc for seg in COMMENT_STRIP_PATH_DISABLE
                    ):
                        raw = strip_comments(raw, src.suffix)
                    zf.writestr(arc, raw)
                else:
                    zf.write(src, arcname=arc)
            else:
                # Generated content (e.g. TRIMMED_CARGO_TOML). Apply
                # comment stripping if it's a comment-stripped suffix
                # so the workspace Cargo.toml is consistent with the
                # rest of the .toml files in the archive.
                content = src
                ext = "." + arc.rsplit(".", 1)[-1] if "." in arc else ""
                if ext in COMMENT_STRIP_SUFFIXES:
                    content = strip_comments(content, ext)
                zf.writestr(arc, content)

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
