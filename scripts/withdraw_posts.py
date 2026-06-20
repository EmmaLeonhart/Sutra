"""Withdraw (retract) one or more clawRxiv posts by ID.

clawRxiv exposes `POST /api/posts/{id}/withdraw` (discovered 2026-06-19: an
unauthenticated POST returns 401, i.e. the endpoint exists and requires the
Bearer key — every other verb/path we probed, retract/delete/unpublish/DELETE,
returns 404). This is the counterpart to `paper_submit_and_fetch.py`, used to
retract posts that were created by accident (e.g. the orphan duplicates
2628..2632 that the 2026-05-27/28 `/revise` outage spawned off the FV paper
chain — see `paper_submit_and_fetch.py` `_orphan_refused`).

Reads `CLAWRXIV_API_KEY` from the environment (the GitHub Actions secret).
Run via the `withdraw-papers.yml` workflow_dispatch so the key never leaves CI.

Example (in CI):

    CLAWRXIV_API_KEY=... python scripts/withdraw_posts.py \\
        --post-ids 2628,2629,2630,2631,2632 \\
        --reason "submitted accidentally (orphan duplicates of the FV paper)"

Exit code 0 iff every requested post ended in a withdrawn state (a post that
was ALREADY withdrawn counts as success — idempotent). Exit code 1 if any
withdraw failed, so a CI run goes red and a human looks.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

CLAWRXIV_BASE = "https://clawrxiv.io"


def _request(
    method: str, url: str, api_key: str, payload: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any] | str]:
    """Issue an authenticated request. Returns (status_code, parsed_body).

    Never raises on an HTTP error status — returns the code + body so the
    caller can treat "already withdrawn" (often 409/400) as success.
    """
    data = (
        json.dumps(payload, ensure_ascii=False).encode("utf-8")
        if payload is not None
        else None
    )
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode("utf-8")
            code = resp.status
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        code = e.code
    except urllib.error.URLError as e:
        return 0, f"network error: {e}"
    try:
        parsed: dict[str, Any] | str = json.loads(body) if body else {}
    except (ValueError, TypeError):
        parsed = body
    return code, parsed


def _is_withdrawn(body: dict[str, Any] | str) -> bool:
    """Best-effort detection that a GET shows the post in a withdrawn state."""
    if not isinstance(body, dict):
        return False
    for key in ("status", "state"):
        v = body.get(key)
        if isinstance(v, str) and "withdraw" in v.lower():
            return True
    for key in ("withdrawn", "isWithdrawn", "retracted"):
        if body.get(key) is True:
            return True
    return False


def withdraw_one(post_id: int, api_key: str, reason: str | None) -> bool:
    """Withdraw a single post. Returns True iff it ends up withdrawn."""
    url = f"{CLAWRXIV_BASE}/api/posts/{post_id}/withdraw"
    payload = {"reason": reason} if reason else {}
    code, body = _request("POST", url, api_key, payload)
    print(f"  POST {url} -> HTTP {code}")
    if isinstance(body, dict) and body:
        print(f"    body: {json.dumps(body, ensure_ascii=False)[:400]}")
    elif isinstance(body, str) and body:
        print(f"    body: {body[:400]}")

    if 200 <= code < 300:
        print(f"  ✓ post {post_id} withdrawn")
        return True

    # Already-withdrawn / idempotent cases: confirm via GET rather than trust
    # the error code. clawRxiv may 4xx a re-withdraw; the post is still gone.
    gcode, gbody = _request("GET", f"{CLAWRXIV_BASE}/api/posts/{post_id}", api_key)
    if _is_withdrawn(gbody):
        print(f"  ✓ post {post_id} already in a withdrawn state (idempotent)")
        return True
    if gcode == 404:
        print(f"  ✓ post {post_id} no longer retrievable (GET 404) — treating "
              f"as withdrawn/removed")
        return True
    print(f"  ✗ post {post_id} NOT withdrawn (withdraw HTTP {code}, "
          f"GET HTTP {gcode})", file=sys.stderr)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Withdraw clawRxiv posts by ID.")
    parser.add_argument(
        "--post-ids", required=True,
        help="Comma-separated post IDs to withdraw (e.g. 2628,2629,2630).",
    )
    parser.add_argument(
        "--reason", default="submitted accidentally",
        help="Withdrawal reason recorded with each post.",
    )
    args = parser.parse_args()

    api_key = os.environ.get("CLAWRXIV_API_KEY")
    if not api_key:
        print("ERROR: CLAWRXIV_API_KEY environment variable is not set",
              file=sys.stderr)
        return 1

    try:
        ids = [int(x.strip()) for x in args.post_ids.split(",") if x.strip()]
    except ValueError:
        print(f"ERROR: --post-ids must be comma-separated integers, got "
              f"{args.post_ids!r}", file=sys.stderr)
        return 1
    if not ids:
        print("ERROR: no post IDs given", file=sys.stderr)
        return 1

    print(f"Withdrawing {len(ids)} post(s): {ids}")
    print(f"Reason: {args.reason}")
    results = {}
    for pid in ids:
        print(f"\nPost {pid}:")
        results[pid] = withdraw_one(pid, api_key, args.reason)

    ok = [p for p, r in results.items() if r]
    bad = [p for p, r in results.items() if not r]
    print(f"\n=== Summary ===")
    print(f"Withdrawn: {ok}")
    if bad:
        print(f"FAILED:    {bad}", file=sys.stderr)
        return 1
    print("All requested posts withdrawn.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
