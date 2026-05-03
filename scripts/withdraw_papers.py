"""Withdraw clawRxiv papers by ID.

Usage:
    python scripts/withdraw_papers.py <id> [<id> ...]

Loads CLAWRXIV_API_KEY from env or `.env` in the repo root. Calls
`POST https://www.clawrxiv.io/api/posts/<id>/withdraw` for each ID.

Withdrawal is publicly visible and cascading (all versions in a revision
chain go down together). Confirm IDs with the user before running.
See `paper/RETRACT_SKILL.md` for the full operating contract.
"""
import io
import os
import sys
from pathlib import Path

import requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

API_BASE = "https://www.clawrxiv.io"


def load_key():
    key = os.environ.get("CLAWRXIV_API_KEY")
    if key:
        return key.strip()
    env_path = Path(".env")
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("CLAWRXIV_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit(
        "No CLAWRXIV_API_KEY found in env or .env. Set it before running."
    )


def withdraw(paper_id, key):
    url = f"{API_BASE}/api/posts/{paper_id}/withdraw"
    r = requests.post(
        url, headers={"Authorization": f"Bearer {key}"}, timeout=30
    )
    return r.status_code, r.text


def main(argv):
    if len(argv) < 2:
        print("usage: python scripts/withdraw_papers.py <paper_id> [<paper_id> ...]")
        return 2
    key = load_key()
    ok = True
    for pid in argv[1:]:
        status, body = withdraw(pid, key)
        if 200 <= status < 300:
            print(f"OK  {pid} -> {status}")
        else:
            ok = False
            print(f"ERR {pid} -> {status}: {body[:300]}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
