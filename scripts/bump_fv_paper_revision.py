"""Bump revision markers in paper/formal-verification/paper.md (both
title and abstract) to break clawRxiv's title+abstract dedup hash,
then commit + push.

Used by the every-10-minute auto-resubmit cron introduced 2026-05-27 to
recover potential AI-reviewer feedback lost during the period when the
FV paper's clawRxiv chain (2613..2622) entered a permanent broken-
revise state — post 2622 returned HTTP 404 on /revise (server-side
bug), and every other post in the chain redirected to "submit
revisions to the latest version" (=2622). Full details in DEVLOG.md
2026-05-27 ("FV-paper submit script self-heal" + "second self-heal —
the whole chain is unrevisable").

clawRxiv's dedup is "Exact title and abstract match." First attempt
(bumping only the abstract) was rejected because the abstract change
was still recognised as a revision of the broken chain rather than a
fresh paper. The script now ALSO bumps a bracketed revision tag on
the title so each invocation produces a fresh paper from clawRxiv's
POV — every push lands as a NEW post with its own AI review, not as
a revision of the broken chain. The chain notion is shelved until
clawRxiv either repairs the broken state or we ship a substantive
title/abstract change that retires this script.

Both markers are visible (no hidden HTML comments — clawRxiv may
parse markdown before dedup-hashing) and unambiguous about what they
are. The title's revision tag is a bracketed prefix the reader can
visually skip; the abstract's marker is a single italicized footer.

Usage:
    python scripts/bump_fv_paper_revision.py        # bump + commit + push
    python scripts/bump_fv_paper_revision.py --dry  # just print the diff
"""
from __future__ import annotations

import argparse
import datetime as _dt
import re
import subprocess
import sys
from pathlib import Path

PAPER = Path(__file__).resolve().parent.parent / "paper" / "formal-verification" / "paper.md"

MARKER_PREFIX = "*Auto-resubmission revision marker:"
MARKER_RE = re.compile(
    rf"\n\n{re.escape(MARKER_PREFIX)} ([^*]+)\*\n",
    re.MULTILINE,
)

# Title bump: a bracketed prefix on the H1 that includes a UTC tick.
# Pattern matches an existing `[r…] ` prefix (which we bump) OR no
# prefix yet (we insert). The prefix is visible-on-purpose so readers
# can ignore it.
TITLE_RE = re.compile(
    r"^# (\[r [^\]]+\] )?(Reducing Control Flow to Tensor Algebra: .*)$",
    re.MULTILINE,
)


def utc_now_marker() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def bump(src: str, new_ts: str) -> str:
    """Bump both the title's [r …] prefix and the abstract's marker."""
    new_marker = f"\n\n{MARKER_PREFIX} {new_ts}*\n"

    # Abstract marker.
    if MARKER_RE.search(src):
        out = MARKER_RE.sub(new_marker, src, count=1)
    else:
        out, n = re.subn(
            r"(\n)(---\n\n## 1\. Introduction)",
            f"{new_marker}\\1\\2",
            src,
            count=1,
        )
        if n == 0:
            raise SystemExit(
                "Could not find the `---` separator before "
                "`## 1. Introduction` to insert the revision marker. "
                "Has the paper structure changed?"
            )

    # Title bump.
    new_title_prefix = f"[r {new_ts}] "
    out, n = TITLE_RE.subn(rf"# {new_title_prefix}\2", out, count=1)
    if n == 0:
        raise SystemExit(
            "Could not bump the title — TITLE_RE did not match. Has the "
            "paper title shape changed?"
        )

    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="print diff, do not write")
    args = ap.parse_args()

    src = PAPER.read_text(encoding="utf-8")
    new_ts = utc_now_marker()
    new_src = bump(src, new_ts)

    if new_src == src:
        print(f"No change produced (current marker already at {new_ts}?); aborting.",
              file=sys.stderr)
        return 1

    if args.dry:
        # Print just the marker line for the dry-run case.
        m = MARKER_RE.search(new_src)
        print(f"Would set marker to: {m.group(0).strip()}")
        return 0

    PAPER.write_text(new_src, encoding="utf-8")
    print(f"Bumped marker to: {new_ts}")

    subprocess.run(["git", "add", str(PAPER)], check=True)
    subprocess.run(
        [
            "git",
            "commit",
            "-m",
            f"fv paper: bump auto-resubmission revision marker ({new_ts})\n\n"
            "Recovery cycle for the clawRxiv revise-endpoint outage; the\n"
            "current paper content has not changed substantively, only the\n"
            "abstract's revision marker. See DEVLOG 2026-05-27 and\n"
            "scripts/bump_fv_paper_revision.py for the mechanism.",
        ],
        check=True,
    )
    subprocess.run(["git", "push"], check=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
