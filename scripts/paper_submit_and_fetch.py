"""Submit a paper to clawRxiv and poll for its peer review.

Shared between `.github/workflows/papers-ci.yml` (automatic push-triggered
submission) and `.github/workflows/submit-papers.yml` (manual one-off
submission). Pulled out of the inline YAML script so both workflows
share one implementation, so it can be unit-tested locally, and so the
review-fetching logic isn't trapped inside a heredoc.

Reads paper content from `<paper-dir>/paper.md`, optionally reads
`<paper-dir>/SKILL.md` as supplementary material, extracts the `## Abstract`
section (falling back to the first 500 characters if there is no such
section), and POSTs to clawRxiv's `/api/posts` endpoint.

After submission succeeds, polls `/api/posts/{post_id}/review` (the
undocumented review endpoint we've been using) every `--poll-seconds`
seconds until a review is returned or `--review-timeout-seconds` elapses.
On success, writes the review JSON and a rendered Markdown copy into
`<paper-dir>/reviews/v{N}_post{post_id}_review.{json,md}` where `N` is
derived from the count of existing files in that directory plus one.

On submission success, updates `<paper-dir>/.post_id` to the new post ID
so the next push to main automatically supersedes this version.

Example (local):

    export CLAWRXIV_API_KEY=...
    python scripts/paper_submit_and_fetch.py \\
        --paper-dir sutra-paper \\
        --title "Sutra: A Vector Programming Language for ..." \\
        --tags "programming-languages,vsa,embedding-spaces"

Exit code 0 on success (including successful submission with timed-out
review fetch — the submission landed, the review just isn't ready yet).
Exit code 1 on submission failure or any fatal error.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

CLAWRXIV_BASE = "https://clawrxiv.io"


class SupersedeConflict(RuntimeError):
    """HTTP 409 from clawRxiv (stale supersede target, or dedup:
    "already been revised" / "duplicate detected"). Carries the
    parsed JSON body so callers can follow `data.duplicateId` to
    the canonical live post and revise that instead."""

    def __init__(self, message: str, body: dict[str, Any] | None = None):
        super().__init__(message)
        self.body = body or {}

    def duplicate_id(self) -> int | None:
        v = (self.body.get("data") or {}).get("duplicateId")
        if isinstance(v, bool):
            return None
        if isinstance(v, int):
            return v
        if isinstance(v, str) and v.isdigit():
            return int(v)
        return None


class ReviseNotFound(RuntimeError):
    """HTTP 404 from POST /api/posts/{id}/revise.

    Observed 2026-05-27 against a healthy, non-withdrawn post (the FV
    paper's post 2622 in its 10-version chain): GET /api/posts/2622
    returns 200 with `versions[]` populated, but POST .../revise
    returns 404 with `{"message":"Server Error"}`. The endpoint exists
    (anonymous POST returns 401, not 404), so this is a server-side
    bug specific to a particular post entering an unrevisable state.

    The self-heal is the same shape as SupersedeConflict's: do not
    just fail — fall back to creating a fresh post (a new chain). The
    old chain stays on clawRxiv as orphaned versions; the canonical
    paper text lives on the project's own site, so the chain loss is
    cosmetic, not content loss. Calling code is expected to catch
    this and call `create_post()` instead of dying."""


def extract_h1_title(content: str) -> str | None:
    """Extract the H1 title from the paper markdown, if present."""
    match = re.match(r'^#\s+(.+)', content)
    return match.group(1).strip() if match else None


def read_paper(paper_dir: Path) -> tuple[str, str | None, str]:
    """Return (paper_content, skill_content_or_none, abstract)."""
    paper_path = paper_dir / "paper.md"
    if not paper_path.exists():
        raise FileNotFoundError(f"{paper_path} does not exist")
    content = paper_path.read_text(encoding="utf-8")

    skill_path = paper_dir / "SKILL.md"
    skill = skill_path.read_text(encoding="utf-8") if skill_path.exists() else None
    if skill is None:
        print(f"WARNING: {skill_path} does not exist — submitting without SKILL.md",
              file=sys.stderr)

    # Extract the abstract section. paper.md has:
    #     ## Abstract
    #     <paragraphs>
    #     ## <next section>
    # The regex captures the content between `## Abstract` and the next
    # H2 heading, regardless of whether that heading text starts with a
    # digit. Falls back to the first 500 characters if no abstract
    # section is found — the fly-brain paper currently has
    # "## What We Did" instead of "## Abstract", so the fallback matters.
    #
    # Note: an earlier version of this regex required the next heading
    # to start with a digit (`## [0-9]`), matching `## 1. Introduction`
    # style. When the body section numbering was stripped (paper commit
    # b3e5320, `## 1. Introduction` -> `## Introduction`), that pattern
    # stopped matching, the regex fell through to the 500-char fallback,
    # and clawRxiv reviewers flagged the abstract as "truncated mid-
    # sentence ('with th')." Match any `\n## ` now.
    match = re.search(r'## Abstract\s*\n(.*?)(?=\n## )', content, re.DOTALL)
    abstract = match.group(1).strip() if match else content[:500]
    return content, skill, abstract


def read_post_id(paper_dir: Path) -> int | None:
    """Return the previously-stored post ID for supersede, or None."""
    post_id_path = paper_dir / ".post_id"
    if not post_id_path.exists():
        return None
    raw = post_id_path.read_text(encoding="utf-8").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        print(f"WARNING: {post_id_path} contains non-integer value {raw!r}, "
              f"ignoring", file=sys.stderr)
        return None


def _post_json(
    url: str, payload: dict[str, Any], api_key: str,
) -> dict[str, Any]:
    """POST JSON to clawRxiv.

    Raises:
        SupersedeConflict — on HTTP 409 (stale supersede target /
            dedup), carrying the parsed body so callers can recover
            via data.duplicateId.
        ReviseNotFound — on HTTP 404 against a /revise endpoint.
            The endpoint exists (anon POST returns 401), so a 404
            here is a server-side bug specific to the targeted post
            (observed against post 2622 in its 10-version chain
            2026-05-27). Callers are expected to recover by creating
            a fresh post.
        RuntimeError — on any other HTTP error.
    """
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        if e.code == 409:
            try:
                parsed = json.loads(err_body)
            except (ValueError, TypeError):
                parsed = {}
            raise SupersedeConflict(
                f"clawRxiv HTTP 409: {err_body}", body=parsed
            ) from e
        if e.code == 404 and "/revise" in url:
            raise ReviseNotFound(
                f"clawRxiv HTTP 404 on revise URL {url}: {err_body}"
            ) from e
        raise RuntimeError(
            f"clawRxiv request failed: HTTP {e.code}: {err_body}"
        ) from e


def build_payload(
    *, title: str, abstract: str, content: str,
    skill: str | None, tags: list[str],
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "title": title,
        "abstract": abstract,
        "content": content,
        "tags": tags,
        "human_names": ["Emma Leonhart"],
    }
    if skill is not None:
        payload["skill_md"] = skill
    return payload


def create_post(*, api_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Create a brand-new clawRxiv post (first-ever submission)."""
    return _post_json(f"{CLAWRXIV_BASE}/api/posts", payload, api_key)


def revise_post(
    *, api_key: str, post_id: int, payload: dict[str, Any],
) -> dict[str, Any]:
    """Revise an existing post via clawRxiv's current revision API
    (`POST /api/posts/{id}/revise`). This replaced the old
    `POST /api/posts` + `supersedes` field, which now 409s with
    "already been revised" / "duplicate detected"."""
    return _post_json(
        f"{CLAWRXIV_BASE}/api/posts/{post_id}/revise", payload, api_key
    )


def _orphan_refused(pinned_post_id: int, create_response: dict[str, Any]) -> int:
    """Loud-fail when the create-fallback minted a fresh orphan post.

    "Stop new chains" guard (Emma 2026-05-30). When a `.post_id` is pinned,
    `create_post` is only ever a *probe* to elicit clawRxiv's 409 dedup
    response naming the canonical post to revise. If create_post instead
    SUCCEEDS, clawRxiv minted a brand-new unchained post — the exact failure
    that produced orphans 2626..2632 during the 2026-05-27 `/revise` outage
    (compounded then by `scripts/bump_fv_paper_revision.py` changing the H1
    timestamp so dedup could not collapse the resubmissions).

    We refuse to pin `.post_id` to the orphan: the caller returns this exit
    code 1 so CI goes red and a human looks, and `.post_id` stays at the
    pinned chain tip so the next push retries `revise` against the chain
    rather than feeding the orphan. The orphan clawRxiv already created is
    cosmetic (canonical text lives in the repo + on the site); the damage is
    bounded to one orphan per outage instead of one per push.
    """
    orphan_id = create_response.get("id") or create_response.get("postId")
    print(
        f"ERROR: revise of pinned post {pinned_post_id} failed and the "
        f"create-fallback minted a NEW unchained post {orphan_id} instead "
        f"of 409-deduping back onto the chain. Refusing to pin .post_id to "
        f"an orphan — this is the 2026-05-27/28 orphan-explosion failure "
        f"mode (orphans 2626..2632). Leaving .post_id={pinned_post_id} so "
        f"the next push retries revise against the chain. Likely cause: a "
        f"clawRxiv /revise outage. Wait for clawRxiv to repair revise, or "
        f"inspect the chain manually — do NOT let CI spawn a new chain.",
        file=sys.stderr,
    )
    return 1


def fetch_review(
    *, api_key: str, post_id: int, poll_seconds: int, timeout_seconds: int,
) -> dict[str, Any] | None:
    """Poll /api/posts/{post_id}/review until a review exists or timeout.

    Returns the review JSON on success, or None if the timeout elapses
    without a review being produced. A timeout is NOT an error — the
    submission itself succeeded, the reviewer just hasn't run yet.
    """
    deadline = time.monotonic() + timeout_seconds
    url = f"{CLAWRXIV_BASE}/api/posts/{post_id}/review"
    req_headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    attempt = 0
    while time.monotonic() < deadline:
        attempt += 1
        try:
            req = urllib.request.Request(url, headers=req_headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode("utf-8")
            parsed = json.loads(body)
            # The endpoint returns different shapes depending on state.
            # A review is "ready" if the payload has content beyond just
            # an empty envelope. Check common field names.
            if isinstance(parsed, dict) and (
                parsed.get("review")
                or parsed.get("body")
                or parsed.get("content")
                or parsed.get("rating")
            ):
                print(f"Review ready after {attempt} poll(s) "
                      f"(~{attempt * poll_seconds}s elapsed)")
                return parsed
        except urllib.error.HTTPError as e:
            # 404 or similar means "not ready yet" — normal, keep polling.
            if e.code in (404, 409, 202):
                pass
            else:
                print(f"poll attempt {attempt}: HTTP {e.code}", file=sys.stderr)
        except Exception as e:  # noqa: BLE001
            print(f"poll attempt {attempt}: {e}", file=sys.stderr)
        time.sleep(poll_seconds)
    print(f"Review not ready after {attempt} attempts "
          f"(~{timeout_seconds}s) — skipping for now",
          file=sys.stderr)
    return None


def next_version_number(reviews_dir: Path) -> int:
    """Return the next version number for a new review file."""
    if not reviews_dir.exists():
        return 1
    existing = [p for p in reviews_dir.glob("v*_post*_review.json")]
    return len(existing) + 1


def render_review_markdown(review: dict[str, Any], *, version: int, post_id: int) -> str:
    """Render the review JSON into a human-readable markdown file."""
    lines = [
        f"# Review v{version} · post {post_id}",
        "",
    ]
    rating = review.get("rating") or review.get("recommendation")
    if rating:
        lines.append(f"**Rating:** {rating}")
        lines.append("")
    body = (
        review.get("review")
        or review.get("body")
        or review.get("content")
        or json.dumps(review, indent=2)
    )
    lines.append(str(body))
    lines.append("")
    return "\n".join(lines)


def save_review(
    *, reviews_dir: Path, review: dict[str, Any], version: int, post_id: int,
) -> tuple[Path, Path]:
    reviews_dir.mkdir(parents=True, exist_ok=True)
    json_path = reviews_dir / f"v{version}_post{post_id}_review.json"
    md_path = reviews_dir / f"v{version}_post{post_id}_review.md"
    json_path.write_text(
        json.dumps(review, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    md_path.write_text(
        render_review_markdown(review, version=version, post_id=post_id),
        encoding="utf-8",
    )
    return json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Submit a paper to clawRxiv and poll for its peer review.",
    )
    parser.add_argument(
        "--paper-dir", required=True,
        help="Path to paper directory containing paper.md (e.g. sutra-paper)",
    )
    parser.add_argument(
        "--title", required=False, default=None,
        help="Paper title. If omitted, extracted from the H1 of paper.md. "
             "If provided, warns when it differs from the paper's H1.",
    )
    parser.add_argument(
        "--tags", required=True,
        help="Comma-separated tag list (e.g. programming-languages,vsa)",
    )
    parser.add_argument(
        "--supersedes", type=int, default=None,
        help="Post ID to supersede. Defaults to the contents of "
             "<paper-dir>/.post_id if present.",
    )
    parser.add_argument(
        "--poll-seconds", type=int, default=30,
        help="Seconds between review polls (default 30)",
    )
    parser.add_argument(
        "--review-timeout-seconds", type=int, default=600,
        help="Give up waiting for the review after this many seconds (default 600)",
    )
    parser.add_argument(
        "--no-review-wait", action="store_true",
        help="Submit and exit without polling for the review.",
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

    tags = [t.strip() for t in args.tags.split(",") if t.strip()]

    try:
        content, skill, abstract = read_paper(paper_dir)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    # Resolve the title: prefer the H1 from paper.md, fall back to --title.
    h1_title = extract_h1_title(content)
    if args.title is None:
        if h1_title is None:
            print("ERROR: no --title provided and no H1 found in paper.md",
                  file=sys.stderr)
            return 1
        title = h1_title
        print(f"Using title from paper.md H1: {title}")
    else:
        title = args.title
        if h1_title and h1_title != title:
            print(f"WARNING: --title does not match paper.md H1!",
                  file=sys.stderr)
            print(f"  --title:    {title}", file=sys.stderr)
            print(f"  paper H1:   {h1_title}", file=sys.stderr)
            print(f"  Using --title (override). Update the CI workflow or "
                  f"paper.md to make them consistent.", file=sys.stderr)

    supersedes = args.supersedes
    if supersedes is None:
        supersedes = read_post_id(paper_dir)
    payload = build_payload(
        title=title, abstract=abstract, content=content,
        skill=skill, tags=tags,
    )

    def _persist_post_id(pid: int) -> None:
        (paper_dir / ".post_id").write_text(str(pid), encoding="utf-8")
        print(f"Wrote {paper_dir}/.post_id = {pid}")

    try:
        if supersedes is not None:
            print(f"Revising existing post {supersedes} "
                  f"(POST /api/posts/{supersedes}/revise)")
            response = revise_post(
                api_key=api_key, post_id=supersedes, payload=payload
            )
        else:
            print(f"Creating NEW clawRxiv post for {paper_dir}/paper.md "
                  f"(no .post_id found)")
            response = create_post(api_key=api_key, payload=payload)
    except ReviseNotFound as e:
        # clawRxiv server-side bug observed 2026-05-27: a healthy,
        # non-withdrawn post in a long supersedes chain can enter a
        # state where POST /revise returns 404. The endpoint exists
        # (anon POST 401s) and the post itself is reachable via GET;
        # only revise fails. Self-heal: try create_post — clawRxiv's
        # 409 dedup response names the actual canonical revisable
        # post via data.duplicateId, which is NOT necessarily the
        # .post_id we had pinned. The dedup detector identifies the
        # canonical from title+abstract match.
        # First time this branch fired (2026-05-27 FV paper): the
        # pinned .post_id was 2622, /revise 404'd, create_post 409'd
        # with `duplicateId=2618` and `"use POST /api/posts/2618/
        # revise instead."` So 2618 was the actual canonical; the
        # 2619-2622 versions had drifted into the broken-revise state.
        print(f"WARNING: revise of post {supersedes} returned HTTP "
              f"404 (server-side bug). Trying create_post to let "
              f"clawRxiv's dedup response name the actual canonical "
              f"post via data.duplicateId.\n  Underlying 404 error: "
              f"{e}", file=sys.stderr)
        try:
            response = create_post(api_key=api_key, payload=payload)
            # STOP-NEW-CHAINS guard (Emma 2026-05-30). create_post is used
            # here only as a probe to elicit clawRxiv's 409 dedup response
            # (caught below) that names the canonical post to revise. If it
            # instead SUCCEEDS, clawRxiv just minted a brand-new *orphan*
            # post rather than deduping back onto the pinned chain — that is
            # exactly the 2026-05-27/28 failure that produced orphans
            # 2626..2632. Refuse to pin .post_id to the orphan: report
            # loudly and fail CI so a human investigates. .post_id stays at
            # {supersedes}, so the next run retries revise against the chain.
            return _orphan_refused(supersedes, response)
        except SupersedeConflict as e2:
            # The 409 we want: dedup pointed at the canonical post.
            dup = e2.duplicate_id()
            if dup is None:
                print(f"ERROR: create_post after 404 returned 409 "
                      f"with no data.duplicateId to recover from:\n"
                      f"  {e2}", file=sys.stderr)
                return 1
            print(f"clawRxiv dedup names post {dup} as canonical for "
                  f"this work; revising post {dup} and re-pinning "
                  f".post_id to it.", file=sys.stderr)
            try:
                response = revise_post(
                    api_key=api_key, post_id=dup, payload=payload
                )
            except ReviseNotFound as e3:
                # Worst case: the canonical post is ALSO in the
                # broken-revise state. Both the pinned post and the
                # dedup-canonical are unrevisable. The only remaining
                # path is to edit the paper title/abstract slightly
                # to break dedup matching — don't auto-mutate the
                # paper; report honestly so a human can decide.
                print(f"ERROR: canonical post {dup} ALSO 404s on "
                      f"revise. Both the pinned post ({supersedes}) "
                      f"and the dedup-canonical post ({dup}) are in "
                      f"clawRxiv's broken-revise state. Options: "
                      f"(a) wait for clawRxiv to fix the server-side "
                      f"bug, or (b) edit paper title/abstract slightly "
                      f"to break the dedup hash so a fresh chain can "
                      f"be created.\n  Underlying error: {e3}",
                      file=sys.stderr)
                return 1
            except SupersedeConflict as e3:
                pin = e3.duplicate_id() or dup
                print(f"NOTE: clawRxiv finds no substantive change vs "
                      f"post {pin}; treating as up-to-date and pinning "
                      f".post_id={pin}.", file=sys.stderr)
                _persist_post_id(pin)
                return 0
            except Exception as e3:  # noqa: BLE001
                print(f"ERROR: revising canonical post {dup} failed: "
                      f"{e3}", file=sys.stderr)
                return 1
        except Exception as e2:  # noqa: BLE001
            print(f"ERROR: fallback create_post after 404 also failed: "
                  f"{e2}", file=sys.stderr)
            return 1
    except SupersedeConflict as e:
        dup = e.duplicate_id()
        if dup is None:
            # 409 with no data.duplicateId — observed as "This paper
            # has already been revised. Submit revisions to the latest
            # version." This happens when revising a non-latest post
            # in a chain whose latest entry is itself broken (the FV
            # paper's 2618..2622 situation: revise(2618) routes to
            # "submit to latest"=2622 which 404s). Fall back to
            # create_post — either the title/abstract has been
            # bumped enough to break dedup (fresh post created) or
            # we re-enter the SupersedeConflict path with a duplicate
            # id we CAN follow.
            print(f"WARNING: clawRxiv 409 with no data.duplicateId "
                  f"(likely 'submit revisions to latest version' on an "
                  f"unrevisable chain). Falling back to create_post.\n"
                  f"  Underlying 409 error: {e}", file=sys.stderr)
            try:
                response = create_post(api_key=api_key, payload=payload)
                # STOP-NEW-CHAINS guard (Emma 2026-05-30) — same rationale
                # as the ReviseNotFound branch above. A *successful* create
                # here means an orphan was minted instead of deduping back
                # onto the pinned chain. (The old policy deliberately wanted
                # this — the bump-revision script changed the title so
                # create would succeed and spawn a fresh post. That policy
                # is retired: we now refuse the orphan and fail loudly.)
                return _orphan_refused(supersedes, response)
            except SupersedeConflict as e_dup:
                dup2 = e_dup.duplicate_id()
                if dup2 is None:
                    print(f"ERROR: create_post after no-duplicateId 409 "
                          f"ALSO returned 409 without data.duplicateId:\n"
                          f"  {e_dup}", file=sys.stderr)
                    return 1
                # The title/abstract is still dedup-matching some
                # existing post. Try to revise that one — same recovery
                # as the regular SupersedeConflict path below.
                print(f"clawRxiv dedup names post {dup2} as canonical "
                      f"for this work; revising post {dup2} and re-"
                      f"pinning .post_id.", file=sys.stderr)
                try:
                    response = revise_post(
                        api_key=api_key, post_id=dup2, payload=payload
                    )
                except Exception as e_inner:  # noqa: BLE001
                    print(f"ERROR: revising dedup-named canonical post "
                          f"{dup2} failed: {e_inner}", file=sys.stderr)
                    return 1
            except Exception as e_other:  # noqa: BLE001
                print(f"ERROR: fallback create_post after 409 also "
                      f"failed: {e_other}", file=sys.stderr)
                return 1
        else:
            # Standard self-heal: clawRxiv's dedup response names the
            # canonical live post for this work. Follow it and revise
            # THAT — deterministic self-heal of a stale/drifted .post_id
            # straight from the API, no key-authed chain lookup needed.
            print(f"WARNING: clawRxiv reports the live version of this "
                  f"work is post {dup} (HTTP 409). Revising post {dup} "
                  f"and re-pinning .post_id.", file=sys.stderr)
            try:
                response = revise_post(
                    api_key=api_key, post_id=dup, payload=payload
                )
            except SupersedeConflict as e2:
                pin = e2.duplicate_id() or dup
                print(f"NOTE: clawRxiv finds no substantive change vs "
                      f"post {pin}; treating as up-to-date and pinning "
                      f".post_id={pin}.", file=sys.stderr)
                _persist_post_id(pin)
                return 0
            except Exception as e2:  # noqa: BLE001
                print(f"ERROR: revising canonical post {dup} failed: "
                      f"{e2}", file=sys.stderr)
                return 1
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    print("Submission response:")
    print(json.dumps(response, indent=2, ensure_ascii=False))

    new_post_id = response.get("id") or response.get("postId")
    if not new_post_id:
        print("ERROR: submission response has no id/postId field",
              file=sys.stderr)
        return 1

    try:
        new_post_id = int(new_post_id)
    except (TypeError, ValueError):
        print(f"ERROR: response id {new_post_id!r} is not an integer",
              file=sys.stderr)
        return 1

    (paper_dir / ".post_id").write_text(str(new_post_id), encoding="utf-8")
    print(f"Wrote {paper_dir}/.post_id = {new_post_id}")

    if args.no_review_wait:
        print("Skipping review poll (--no-review-wait)")
        return 0

    reviews_dir = paper_dir / "reviews"
    version = next_version_number(reviews_dir)
    print(f"Polling for review of post {new_post_id} "
          f"(version={version}, timeout={args.review_timeout_seconds}s)...")
    review = fetch_review(
        api_key=api_key,
        post_id=new_post_id,
        poll_seconds=args.poll_seconds,
        timeout_seconds=args.review_timeout_seconds,
    )
    if review is None:
        print("No review fetched — submission still counts as success.")
        return 0

    json_path, md_path = save_review(
        reviews_dir=reviews_dir,
        review=review,
        version=version,
        post_id=new_post_id,
    )
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
