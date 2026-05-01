"""Regenerate `planning/competition-analysis-latest.md` from the
current state of `scripts/competition_analysis_raw.json` and
`scripts/competition_reviews.json`.

Intended usage: invoked by `.github/workflows/competition-cron.yml`
on a 6-hour schedule after `fetch_all_papers.py` and `fetch_reviews.py`
have refreshed the two JSON files. Can also be run manually after a
manual fetch for quick status.

The output file is deliberately a *rolling* summary — it overwrites
each run, so the repo history has one commit per 6-hour cron run with
the latest state inside the same file path. The longer prose analyses
(competition-analysis-2026-04-11.md, -evening.md, etc.) stay as
manual snapshots; this file is the automated one.

Exits with status 1 if the input files look wrong (e.g. paper count
too low, indicating a failed fetch). That way the workflow will
refuse to commit bad data over good data.

Run as:
    python scripts/write_competition_summary.py

Writes to:
    planning/competition-analysis-latest.md

No arguments, no configuration — the file paths are hardcoded relative
to the repo root, matching how the cron workflow runs it.
"""

from __future__ import annotations

import datetime as _dt
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


# File paths — relative to the repo root (the workflow cd's there first).
RAW_PAPERS_FILE = Path("scripts/competition_analysis_raw.json")
REVIEWS_FILE = Path("scripts/competition_reviews.json")
OUTPUT_FILE = Path("planning/competition-analysis-latest.md")

# Sanity floor: if we see fewer than this many papers or reviews, the
# fetch probably failed halfway through. Refuse to overwrite the
# output file with a degraded snapshot.
MIN_PAPERS = 1000
MIN_REVIEWS = 1000

# The accept-tier set for leaderboard sort.
ACCEPT_TIER = frozenset({"Strong Accept", "Accept", "Weak Accept"})


def _load_papers() -> list[dict]:
    if not RAW_PAPERS_FILE.exists():
        sys.stderr.write(f"ERROR: {RAW_PAPERS_FILE} does not exist\n")
        sys.exit(1)
    with RAW_PAPERS_FILE.open(encoding="utf-8") as f:
        papers = json.load(f)
    if len(papers) < MIN_PAPERS:
        sys.stderr.write(
            f"ERROR: {RAW_PAPERS_FILE} has only {len(papers)} papers "
            f"(minimum sanity floor is {MIN_PAPERS}). Refusing to "
            f"overwrite {OUTPUT_FILE} with a degraded snapshot.\n"
        )
        sys.exit(1)
    return papers


def _load_reviews() -> list[dict]:
    if not REVIEWS_FILE.exists():
        sys.stderr.write(f"ERROR: {REVIEWS_FILE} does not exist\n")
        sys.exit(1)
    with REVIEWS_FILE.open(encoding="utf-8") as f:
        reviews = json.load(f)
    if len(reviews) < MIN_REVIEWS:
        sys.stderr.write(
            f"ERROR: {REVIEWS_FILE} has only {len(reviews)} reviews "
            f"(minimum sanity floor is {MIN_REVIEWS}). Refusing to "
            f"overwrite {OUTPUT_FILE} with a degraded snapshot.\n"
        )
        sys.exit(1)
    return reviews


def _rating_distribution(reviews: list[dict]) -> Counter:
    counter: Counter = Counter()
    for r in reviews:
        rating = r.get("review_rating") or "unrated"
        counter[rating] += 1
    return counter


def _leaderboard(reviews: list[dict]) -> list[tuple[str, dict[str, int]]]:
    by_agent: dict[str, dict[str, int]] = defaultdict(
        lambda: {"SA": 0, "A": 0, "WA": 0, "WR": 0, "R": 0, "SR": 0, "total": 0}
    )
    key = {
        "Strong Accept": "SA",
        "Accept": "A",
        "Weak Accept": "WA",
        "Weak Reject": "WR",
        "Reject": "R",
        "Strong Reject": "SR",
    }
    for r in reviews:
        agent = r.get("clawName") or "unknown"
        by_agent[agent]["total"] += 1
        rk = key.get(r.get("review_rating"))
        if rk is not None:
            by_agent[agent][rk] += 1
    # Keep agents with at least one Accept-tier paper.
    filtered = [
        (a, v) for a, v in by_agent.items()
        if v["SA"] + v["A"] + v["WA"] > 0
    ]
    # Sort by SA desc, A desc, WA desc, total asc as tiebreaker (fewer
    # submissions wins the tie — rewards precision over spamming).
    filtered.sort(key=lambda x: (-x[1]["SA"], -x[1]["A"], -x[1]["WA"], x[1]["total"]))
    return filtered


def _strong_accepts(reviews: list[dict]) -> list[dict]:
    sa = [r for r in reviews if r.get("review_rating") == "Strong Accept"]
    sa.sort(key=lambda r: r.get("id", 0))
    return sa


def _our_papers(reviews: list[dict]) -> list[dict]:
    mine = [r for r in reviews if r.get("clawName") == "Emma-Leonhart"]
    mine.sort(key=lambda r: -r.get("id", 0))
    return mine


def _recent_submissions_today(papers: list[dict]) -> list[dict]:
    today = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d")
    today_posts = [
        p for p in papers
        if (p.get("createdAt") or "").startswith(today)
    ]
    today_posts.sort(key=lambda p: -p.get("id", 0))
    return today_posts


def _format_markdown(papers: list[dict], reviews: list[dict]) -> str:
    now_utc = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    total_papers = len(papers)
    total_reviews = len(reviews)
    ratings = _rating_distribution(reviews)
    leaderboard = _leaderboard(reviews)
    strong_accepts = _strong_accepts(reviews)
    ours = _our_papers(reviews)
    today = _recent_submissions_today(papers)

    lines: list[str] = []
    lines.append("# Claw4S 2026 — Latest competition snapshot")
    lines.append("")
    lines.append(
        "> **Auto-generated by `.github/workflows/competition-cron.yml` "
        "every 6 hours.** This file is a rolling summary that overwrites "
        "each run. For longer prose analyses see the dated files in the "
        "same directory (e.g. `competition-analysis-2026-04-11.md`). "
        "Regenerated manually by running "
        "`python scripts/write_competition_summary.py` after a fresh "
        "`fetch_all_papers.py` + `fetch_reviews.py` pair."
    )
    lines.append("")
    lines.append(f"**Generated:** {now_utc}")
    lines.append(f"**Papers on site:** {total_papers}")
    lines.append(f"**Reviews fetched:** {total_reviews}")
    unrated = total_papers - total_reviews
    if unrated > 0:
        lines.append(
            f"**Unrated / mid-review:** {unrated} "
            f"(likely papers submitted in the last few minutes whose "
            f"reviews have not landed yet)"
        )
    lines.append("")
    lines.append("## Rating distribution")
    lines.append("")
    lines.append("| Rating | Count | % |")
    lines.append("|---|---:|---:|")
    for r in ("Strong Accept", "Accept", "Weak Accept",
              "Weak Reject", "Reject", "Strong Reject"):
        c = ratings.get(r, 0)
        pct = 100.0 * c / total_reviews if total_reviews else 0.0
        lines.append(f"| {r} | {c} | {pct:.1f}% |")
    lines.append(f"| **Total rated** | **{total_reviews}** | |")
    lines.append("")

    lines.append(f"## Strong Accept tier ({len(strong_accepts)} papers)")
    lines.append("")
    if not strong_accepts:
        lines.append("_No Strong Accepts currently on the site._")
    else:
        lines.append("| Post | Agent | Title |")
        lines.append("|---:|---|---|")
        for r in strong_accepts:
            title = (r.get("title") or "").strip()
            agent = (r.get("clawName") or "").strip()
            lines.append(f"| {r['id']} | {agent} | {title} |")
    lines.append("")

    lines.append("## Leaderboard (agents with at least 1 accept-tier paper)")
    lines.append("")
    lines.append("| Rank | Agent | SA | A | WA | Accepted | Submitted |")
    lines.append("|---:|---|---:|---:|---:|---:|---:|")
    for rank, (agent, counts) in enumerate(leaderboard, start=1):
        accepted = counts["SA"] + counts["A"] + counts["WA"]
        lines.append(
            f"| {rank} | {agent} | {counts['SA']} | {counts['A']} | "
            f"{counts['WA']} | {accepted} | {counts['total']} |"
        )
    lines.append("")

    lines.append("## Emma-Leonhart paper-by-paper")
    lines.append("")
    lines.append("| Post | Rating | Title |")
    lines.append("|---:|---|---|")
    for r in ours:
        title = (r.get("title") or "").strip()
        rating = r.get("review_rating") or "(unrated)"
        lines.append(f"| {r['id']} | {rating} | {title} |")
    lines.append("")

    lines.append("## Papers added today (UTC calendar day)")
    lines.append("")
    if not today:
        lines.append("_No papers added to the site today._")
    else:
        lines.append("| Post | Agent | Time (UTC) | Title |")
        lines.append("|---:|---|---|---|")
        for p in today:
            title = (p.get("title") or "").strip()
            agent = (p.get("clawName") or "").strip()
            created = p.get("createdAt") or "?"
            lines.append(
                f"| {p['id']} | {agent} | {created} | {title} |"
            )
    lines.append("")

    lines.append("## Data sources")
    lines.append("")
    lines.append(
        "- Paper metadata: `scripts/competition_analysis_raw.json`, "
        "regenerated by `python scripts/fetch_all_papers.py`."
    )
    lines.append(
        "- Review metadata: `scripts/competition_reviews.json`, "
        "regenerated by `python scripts/fetch_reviews.py`."
    )
    lines.append(
        "- This summary: `planning/competition-analysis-latest.md`, "
        "regenerated by `python scripts/write_competition_summary.py`."
    )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    papers = _load_papers()
    reviews = _load_reviews()
    markdown = _format_markdown(papers, reviews)
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(markdown, encoding="utf-8")
    sys.stdout.write(
        f"Wrote {OUTPUT_FILE} "
        f"({len(papers)} papers, {len(reviews)} reviews).\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
