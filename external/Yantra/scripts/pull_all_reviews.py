"""Fetch every clawrxiv review we don't already have locally.

The companion to `paper_submit_and_fetch.py`. The submit script writes
one review per push (the canonical revision). This script catches up
anything that fell through the cracks: reviews for posts in
`paper/.post_id` (canonical) and `paper/candidates.jsonl` (one JSON
object per locally-submitted variant, if/when a `quick_review.py` is
ported into this repo) whose review file isn't already present in
`paper/reviews/`.

Why this exists separately from `paper_submit_and_fetch.py`:

  - `paper_submit_and_fetch.py` submits + fetches one review per push.
    This pulls reviews for ALL known posts, including local candidates.
  - The pull is idempotent so re-runs are cheap.
  - Decoupling submit from catch-up means a review-pull doesn't block a
    paper edit, and a submit failure doesn't lose pending reviews.

Run it from CI on a cron, or locally any time:

    set CLAWRXIV_API_KEY=...
    python scripts/pull_all_reviews.py --paper-dir paper

Force re-fetch even when a review file already exists:

    python scripts/pull_all_reviews.py --paper-dir paper --refresh

Adapted from the Alignment repo's identically-named script.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Iterator

# Reuse helpers from paper_submit_and_fetch.
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from paper_submit_and_fetch import (  # noqa: E402
    fetch_review,
    next_version_number,
    read_post_id,
    save_review,
)


def enumerate_post_ids(paper_dir: Path) -> Iterator[tuple[int, str]]:
    """Yield (post_id, source_label) for every post we know about.

    Sources, in priority order:
      - paper/.post_id (canonical)
      - paper/candidates.jsonl (each line's post_id)

    Deduplicates so the same post_id only appears once.
    """
    seen: set[int] = set()

    canonical = read_post_id(paper_dir)
    if canonical is not None:
        seen.add(canonical)
        yield canonical, "canonical"

    candidates_path = paper_dir / "candidates.jsonl"
    if candidates_path.exists():
        for line_no, raw in enumerate(
            candidates_path.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            raw = raw.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError as e:
                print(f"WARNING: candidates.jsonl line {line_no} not JSON: "
                      f"{e}", file=sys.stderr)
                continue
            pid = obj.get("post_id")
            if not isinstance(pid, int):
                print(f"WARNING: candidates.jsonl line {line_no} has no "
                      f"post_id: {raw[:80]}", file=sys.stderr)
                continue
            if pid in seen:
                continue
            seen.add(pid)
            label = obj.get("label", "") or "(unlabeled)"
            yield pid, f"candidate:{label}"


def review_file_exists(reviews_dir: Path, post_id: int) -> Path | None:
    """Return the existing review JSON path for a post_id, or None."""
    if not reviews_dir.exists():
        return None
    matches = list(reviews_dir.glob(f"v*_post{post_id}_review.json"))
    return matches[0] if matches else None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch any clawrxiv reviews not yet saved locally.",
    )
    parser.add_argument(
        "--paper-dir", default="paper",
        help="Paper directory (default: paper)",
    )
    parser.add_argument(
        "--refresh", action="store_true",
        help="Re-fetch even for posts where a review file already exists. "
             "Default is to skip those.",
    )
    parser.add_argument(
        "--timeout-per-post", type=int, default=30,
        help="Seconds to wait per post for a review (default 30). Short "
             "because we may be iterating across many posts; if a review "
             "isn't ready, we move on and try again next time.",
    )
    parser.add_argument(
        "--poll-seconds", type=int, default=5,
        help="Seconds between polls within a single post (default 5).",
    )
    args = parser.parse_args()

    api_key = os.environ.get("CLAWRXIV_API_KEY")
    if not api_key:
        print("ERROR: CLAWRXIV_API_KEY environment variable is not set",
              file=sys.stderr)
        return 1

    paper_dir = Path(args.paper_dir)
    if not paper_dir.is_dir():
        print(f"ERROR: {paper_dir} is not a directory", file=sys.stderr)
        return 1

    reviews_dir = paper_dir / "reviews"
    reviews_dir.mkdir(parents=True, exist_ok=True)

    posts = list(enumerate_post_ids(paper_dir))
    if not posts:
        print(f"No posts found in {paper_dir}/.post_id or "
              f"{paper_dir}/candidates.jsonl. Nothing to do.")
        return 0

    print(f"Checking reviews for {len(posts)} known post(s)...")

    fetched = 0
    skipped = 0
    not_ready = 0
    for post_id, source in posts:
        existing = review_file_exists(reviews_dir, post_id)
        if existing and not args.refresh:
            print(f"  post {post_id} ({source}): already have "
                  f"{existing.name}, skipping")
            skipped += 1
            continue

        print(f"  post {post_id} ({source}): fetching review...", end=" ",
              flush=True)
        t = time.monotonic()
        review = fetch_review(
            api_key=api_key,
            post_id=post_id,
            poll_seconds=args.poll_seconds,
            timeout_seconds=args.timeout_per_post,
        )
        if review is None:
            print(f"not ready after {args.timeout_per_post}s")
            not_ready += 1
            continue

        version = next_version_number(reviews_dir)
        json_path, md_path = save_review(
            reviews_dir=reviews_dir,
            review=review,
            version=version,
            post_id=post_id,
        )
        rating = review.get("rating") or review.get("recommendation") or "?"
        print(f"{rating}  ({time.monotonic() - t:.1f}s)  -> "
              f"{json_path.name}")
        fetched += 1

    print()
    print(f"Done: {fetched} fetched, {skipped} skipped (already had), "
          f"{not_ready} not ready yet.")
    if not_ready:
        print("Re-run later to pick up reviews that weren't ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
