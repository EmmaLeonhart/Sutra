"""Generate every 2^N combination of paper fixes, submit each as a
clawrxiv candidate, and tabulate the resulting reviews.

Usage:
    python scripts/combinatorics.py --baseline paper/paper.md --output combinatorics_results.json

Reads:
    scripts/paper_fixes.py — defines the N fix functions to combine.
    --baseline path — paper.md to use as the starting text. Default
        is paper/paper.md (master HEAD), but for clean combinatorics
        you typically want the post-2149 baseline (a snapshot saved
        elsewhere).

Behavior:
    For each mask in [0, 2^N):
      1. Apply fixes whose bit is set, producing a modified paper.md.
      2. Submit via scripts/quick_review.py (candidate mode — uses
         dedup_token to bypass the canonical chain, so this does NOT
         affect paper/.post_id or the canonical supersedes chain).
      3. Capture the review JSON.
    Results dumped to --output as a JSON list, one entry per variant.

This script is the orchestrator for true combinatorial gradient
descent: with N=6 fixes there are 64 variants; with N=4 (only the
not-yet-applied fixes) there are 16. Each takes ~5–10s submit + poll,
so 16 variants run in ~2 minutes serially or ~30s with the workflow
matrix fan-out.

Required environment:
    CLAWRXIV_API_KEY — same secret used by papers-ci.yml.

Companion CI workflow: .github/workflows/combinatorics.yml runs this
across a matrix of masks so each candidate submits in parallel.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from paper_fixes import ALL_FIXES, apply_fixes, mask_label  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run combinatorial paper-fix testing against clawrxiv.",
    )
    parser.add_argument(
        "--baseline", default="paper/paper.md",
        help="Path to the baseline paper.md. Default: paper/paper.md (master HEAD).",
    )
    parser.add_argument(
        "--paper-dir", default="paper",
        help="Paper directory for SKILL.md and tags context. Default: paper",
    )
    parser.add_argument(
        "--masks", default=None,
        help="Comma-separated list of integer masks to run. Default: 0..2^N "
             "where N = number of fixes in scripts/paper_fixes.py.",
    )
    parser.add_argument(
        "--output", default="combinatorics_results.json",
        help="Output JSON path. Default: combinatorics_results.json",
    )
    parser.add_argument(
        "--timeout-per-submission", type=int, default=60,
        help="Seconds per quick_review.py call (default 60).",
    )
    args = parser.parse_args()

    if not os.environ.get("CLAWRXIV_API_KEY"):
        print("ERROR: CLAWRXIV_API_KEY environment variable is not set",
              file=sys.stderr)
        return 1

    baseline_path = Path(args.baseline)
    if not baseline_path.exists():
        print(f"ERROR: baseline {baseline_path} does not exist", file=sys.stderr)
        return 1
    baseline_text = baseline_path.read_text(encoding="utf-8")

    n_fixes = len(ALL_FIXES)
    if args.masks:
        masks = [int(m) for m in args.masks.split(",")]
    else:
        masks = list(range(1 << n_fixes))

    print(f"Combinatorics over {n_fixes} fixes ({len(masks)} variants):")
    for i, (name, _) in enumerate(ALL_FIXES):
        print(f"  bit {i}: {name}")
    print()

    results: list[dict] = []
    quick_review_path = HERE / "quick_review.py"

    for idx, mask in enumerate(masks):
        modified_text, applied = apply_fixes(baseline_text, mask)
        label = mask_label(mask)
        print(f"[{idx + 1}/{len(masks)}] mask={mask} ({label}) "
              f"applies: {applied or '(none — pure baseline)'}")

        with tempfile.NamedTemporaryFile(
            mode="w", suffix="_paper.md", delete=False, encoding="utf-8",
        ) as tmp:
            tmp.write(modified_text)
            tmp_path = tmp.name

        # Use --no-track so candidate clutter doesn't pile into
        # paper/candidates.jsonl. The combinatorics output JSON is
        # the record.
        cmd = [
            sys.executable, str(quick_review_path),
            "--paper-dir", args.paper_dir,
            "--paper-md", tmp_path,
            "--label", label,
            "--no-track",
            "--timeout", str(args.timeout_per_submission),
            "--json-out", f"{tmp_path}.review.json",
        ]
        t = time.monotonic()
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=args.timeout_per_submission + 30)
            elapsed = time.monotonic() - t
            entry: dict = {
                "mask": mask,
                "label": label,
                "applied": applied,
                "elapsed_seconds": round(elapsed, 1),
                "exit_code": proc.returncode,
                "stdout_tail": proc.stdout.splitlines()[-15:] if proc.stdout else [],
                "stderr_tail": proc.stderr.splitlines()[-5:] if proc.stderr else [],
            }
            review_path = Path(f"{tmp_path}.review.json")
            if review_path.exists():
                try:
                    entry["review"] = json.loads(review_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError as e:
                    entry["review_parse_error"] = str(e)
                review_path.unlink()
            else:
                entry["review"] = None
            print(f"  -> {entry.get('review', {}).get('rating', '?')} "
                  f"({elapsed:.1f}s, exit {proc.returncode})")
        except subprocess.TimeoutExpired:
            entry = {
                "mask": mask,
                "label": label,
                "applied": applied,
                "elapsed_seconds": time.monotonic() - t,
                "exit_code": -1,
                "review": None,
                "error": "timeout",
            }
            print(f"  -> TIMEOUT ({entry['elapsed_seconds']:.1f}s)")
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        results.append(entry)

    out_path = Path(args.output)
    out_path.write_text(
        json.dumps(results, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nWrote {len(results)} variant results to {out_path}")

    # Print a compact summary table.
    print("\nSummary:")
    print(f"  {'mask':<6} {'label':<22} {'rating':<22} elapsed  applied")
    print(f"  {'-' * 6} {'-' * 22} {'-' * 22} -------  -------")
    for r in results:
        rating = (r.get("review") or {}).get("rating", "(no review)")
        print(f"  {r['mask']:<6} {r['label']:<22} {rating:<22} "
              f"{r['elapsed_seconds']:>6.1f}s  {','.join(r['applied'])}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
