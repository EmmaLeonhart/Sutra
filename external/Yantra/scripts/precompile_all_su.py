"""Precompile every .su file in this repo, populating the on-disk codegen cache.

`sutra_compiler.compile_su` (Sutra >= v0.7.1) caches the emitted Python on
disk, so a re-run of the same .su skips the slow `translate_module` pass
(~5 min for `apps/font/font.su` on a typical CPU machine; seconds for
smaller .su like `apps/calc/switch.su` or `apps/gui/count.su`). This
script primes the caches for every .su Yantra ships, so:

  - After a fresh clone, run this once and every subsequent demo
    launch / test run is fast.
  - Periodically (say, in a daily cron, or after a Sutra submodule
    bump) re-run this so the caches keyed on the new Sutra
    codegen-source hash get populated before the next user touches them.

The cache files land next to the .su (`.<stem>.compiled-sutra<ver>-<hash>.py`)
and are committed to git, so CI also benefits.

Manifest below = (relative path, runtime_dtype). All Yantra .su use the
same llm_model / runtime_dim today (`nomic-embed-text`, 768); only the
dtype varies. Add a row when a new .su that benefits from precompilation
lands.

Usage:
    python scripts/precompile_all_su.py            # precompile all
    python scripts/precompile_all_su.py --force    # delete + regenerate caches
"""
from __future__ import annotations

import argparse
import pathlib
import sys
import time


_REPO = pathlib.Path(__file__).resolve().parent.parent
_SUTRA_SDK = _REPO / "external" / "Sutra" / "sdk" / "sutra-compiler"
if str(_SUTRA_SDK) not in sys.path:
    sys.path.insert(0, str(_SUTRA_SDK))


# (relative path from repo root, runtime_dtype). runtime_dim is 768 for
# everything; if a .su lands that needs a different dim, extend the row
# to (path, dtype, dim).
_MANIFEST: list[tuple[str, str]] = [
    # Apps
    ("apps/calc/digits.su",       "float64"),
    ("apps/calc/parse_int2.su",   "float64"),
    ("apps/calc/parse_op.su",     "float64"),
    ("apps/calc/switch.su",       "float64"),
    ("apps/echo/echo.su",         "float32"),
    ("apps/font/font.su",         "float32"),
    ("apps/gui/count.su",         "float32"),
    ("apps/gui/frame.su",         "float32"),
    ("apps/gui/toggle.su",        "float32"),
]


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Precompile every .su file Yantra ships, populating "
                    "sutra_compiler.compile_su's on-disk codegen cache.")
    ap.add_argument("--force", action="store_true",
                    help="Delete the existing cache file for each .su before "
                         "recompiling. Use after a Sutra submodule bump if you "
                         "want to confirm clean codegen from scratch.")
    ap.add_argument("--llm-model", default="nomic-embed-text",
                    help="Frozen-LLM model name passed to codegen (default: "
                         "nomic-embed-text; must match what the consumer uses).")
    ap.add_argument("--runtime-dim", type=int, default=768,
                    help="Extended-state dim (default: 768; must match what "
                         "the consumer uses).")
    args = ap.parse_args()

    from sutra_compiler import compile_su, __version__ as sutra_ver
    print(f"[precompile] Sutra v{sutra_ver}, llm_model={args.llm_model}, "
          f"runtime_dim={args.runtime_dim}")

    overall_start = time.time()
    misses, hits, errors = 0, 0, 0
    for rel_path, runtime_dtype in _MANIFEST:
        su_path = _REPO / rel_path
        if not su_path.is_file():
            print(f"[precompile] SKIP {rel_path} (file not found)")
            continue

        if args.force:
            # Delete any cache files matching this .su's stem under its parent
            # dir. Pattern matches the helper's filename scheme.
            for stale in su_path.parent.glob(f".{su_path.stem}.compiled-*.py"):
                print(f"[precompile]   removing {stale.name}")
                stale.unlink()

        t0 = time.time()
        was_miss = not any(
            su_path.parent.glob(f".{su_path.stem}.compiled-*.py"))
        try:
            compile_su(
                su_path,
                llm_model=args.llm_model,
                runtime_dim=args.runtime_dim,
                runtime_dtype=runtime_dtype,
                verbose=False,
            )
        except Exception as e:
            print(f"[precompile] FAIL {rel_path} ({runtime_dtype}): "
                  f"{type(e).__name__}: {e}")
            errors += 1
            continue

        elapsed = time.time() - t0
        if was_miss:
            misses += 1
            print(f"[precompile] BUILT {rel_path} ({runtime_dtype}) "
                  f"in {elapsed:.1f}s")
        else:
            hits += 1
            print(f"[precompile] hit   {rel_path} ({runtime_dtype}) "
                  f"in {elapsed:.2f}s")

    total = time.time() - overall_start
    print(f"\n[precompile] {misses} built, {hits} cache hit, {errors} failed; "
          f"total {total:.1f}s")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
