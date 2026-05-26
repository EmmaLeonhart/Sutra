"""Precompile every .su example in this repo via sutra_compiler.compile_su.

The disk cache (`.<stem>.compiled-sutra<ver>-<hash>.py` next to each .su)
means a re-run of the same .su skips translate_module entirely.
Populating the caches in one batch -- after a fresh clone or after a
codegen-source edit -- means demos and tests don't pay the codegen
slowness on first launch.

Walks `examples/` by default and tries to compile every .su found.
Files that fail to compile (parser-corpus invalid fixtures, multi-file
programs that need orchestration, etc.) are reported and skipped --
not every .su in the tree is meant to stand alone.

Usage:

    python scripts/precompile_all_su.py                # examples/
    python scripts/precompile_all_su.py --root sdk     # any subdir
    python scripts/precompile_all_su.py --force        # delete + rebuild

Run from the Sutra repo root (or via `python -m sutra_compiler` if that
ever lands as a CLI subcommand).
"""
from __future__ import annotations

import argparse
import pathlib
import sys
import time


_REPO = pathlib.Path(__file__).resolve().parent.parent
_SDK = _REPO / "sdk" / "sutra-compiler"
if str(_SDK) not in sys.path:
    sys.path.insert(0, str(_SDK))


def _iter_su_files(root: pathlib.Path):
    for p in sorted(root.rglob("*.su")):
        # Skip parser-corpus invalid fixtures; they exist to fail parsing.
        if "corpus" in p.parts and "invalid" in p.parts:
            continue
        yield p


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Precompile every .su file under a root, populating "
                    "sutra_compiler.compile_su's on-disk codegen cache.")
    ap.add_argument("--root", default="examples",
                    help="Subdirectory under the Sutra repo root to walk "
                         "(default: examples). Use 'sdk' for stdlib + tests; "
                         "'.' for the whole repo.")
    ap.add_argument("--force", action="store_true",
                    help="Delete the existing cache file(s) for each .su "
                         "before recompiling.")
    ap.add_argument("--llm-model", default="nomic-embed-text")
    ap.add_argument("--runtime-dim", type=int, default=768)
    ap.add_argument("--runtime-dtype", default="float32",
                    help="Sutra codegen dtype. Use float64 for the math-exact "
                         "lane (e.g. calc-shaped programs).")
    ap.add_argument("--skip-on-error", action="store_true", default=True,
                    help="(default) Continue past .su files that fail to "
                         "compile -- many of them are multi-file fixtures "
                         "that don't stand alone.")
    args = ap.parse_args()

    from sutra_compiler import compile_su, __version__ as sutra_ver
    root_dir = (_REPO / args.root).resolve()
    if not root_dir.is_dir():
        print(f"[precompile] root not found: {root_dir}", file=sys.stderr)
        return 1

    print(f"[precompile] Sutra v{sutra_ver}, walking {root_dir.relative_to(_REPO)}, "
          f"llm_model={args.llm_model}, runtime_dim={args.runtime_dim}, "
          f"runtime_dtype={args.runtime_dtype}")

    overall_start = time.time()
    misses, hits, errors, skipped = 0, 0, 0, 0
    for su in _iter_su_files(root_dir):
        rel = su.relative_to(_REPO)

        if args.force:
            for stale in su.parent.glob(f".{su.stem}.compiled-*.py"):
                stale.unlink()

        was_miss = not any(su.parent.glob(f".{su.stem}.compiled-*.py"))
        t0 = time.time()
        try:
            compile_su(
                su,
                llm_model=args.llm_model,
                runtime_dim=args.runtime_dim,
                runtime_dtype=args.runtime_dtype,
                verbose=False,
            )
        except Exception as e:
            elapsed = time.time() - t0
            errors += 1
            print(f"[precompile] FAIL {rel}: {type(e).__name__}: {e}")
            continue

        elapsed = time.time() - t0
        if was_miss:
            misses += 1
            print(f"[precompile] BUILT {rel} in {elapsed:.1f}s")
        else:
            hits += 1

    total = time.time() - overall_start
    print(f"\n[precompile] {misses} built, {hits} cache hit, {errors} failed, "
          f"{skipped} skipped; total {total:.1f}s")
    return 1 if (errors and not args.skip_on_error) else 0


if __name__ == "__main__":
    sys.exit(main())
