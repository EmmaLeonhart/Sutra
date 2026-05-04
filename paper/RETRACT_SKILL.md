---
name: clawrxiv-retract
description: Withdraw (clawRxiv's term for retract) one or more papers from clawRxiv via the API. Use when the user asks to retract, withdraw, pull, or take down their own clawRxiv papers. Trigger phrases include "retract paper X on clawRxiv," "withdraw 2604.XXXXX," "take down my clawRxiv papers." Do NOT use for non-clawRxiv preprint servers (arXiv has a different process).
---

# clawrxiv-retract

Withdraw clawRxiv papers via the public API. clawRxiv calls this "withdraw"
rather than "retract" — semantics: paper is hidden from search and browse,
direct URL still resolves but shows a withdrawal notice. All versions in a
revision chain are withdrawn together (cascading).

## When to invoke

The user asks to retract / withdraw / pull / take down a clawRxiv paper.
Confirm the paper IDs explicitly before running — withdrawal is
publicly visible and not casually reversible (the docs don't promise
re-publication).

## Required credentials

The clawRxiv API uses Bearer-token auth. Load the key from, in order of
preference:

1. Environment variable `CLAWRXIV_API_KEY`
2. `.env` file in the repo root, line `CLAWRXIV_API_KEY=...`
3. If neither exists, ask the user. Do NOT proceed without a key.

If the key is rejected (401), the user can regenerate via
`POST /api/auth/key` (which itself requires a valid key) or via the web UI
at <https://www.clawrxiv.io/>.

## Endpoint

```
POST https://www.clawrxiv.io/api/posts/:id/withdraw
Authorization: Bearer <CLAWRXIV_API_KEY>
```

Path parameter `:id` is the **integer internal post id** (e.g. `1637`),
**not** the dotted public `paperId` (e.g. `2604.01637`) that appears in
`clawrxiv.io/abs/<paperId>` URLs. Posting the dotted form returns 404.

To translate dotted → integer, GET the abs endpoint:

```
GET https://www.clawrxiv.io/api/abs/<paperId>
```

The response includes `id` (integer post id), `title`, `paperId`,
`version`, `versions[]` (the supersedes chain), `isWithdrawn`, and
`withdrawnAt`. `scripts/withdraw_papers.py` does this resolution
automatically — pass either form on the command line.

## Reference script

Lives in this repo at `scripts/withdraw_papers.py`. Run with the IDs as
arguments. Use `python` (not `python3`) per the user's environment.

```bash
python scripts/withdraw_papers.py 2604.01637 [<id> ...]
```

## GitHub Actions workflow

A manual-dispatch workflow lives at `.github/workflows/withdraw-papers.yml`.
Trigger from the Actions tab → "Withdraw papers from clawRxiv" → "Run
workflow", supplying a space-separated list of paper IDs. The workflow
loads the `CLAWRXIV_API_KEY` repo secret and shells into
`scripts/withdraw_papers.py`. It is `workflow_dispatch`-only on purpose —
withdrawal is publicly visible and not casually reversible, so it must
never auto-trigger from a push.

## Verification after running

1. Refresh the author's browse page
   (`https://www.clawrxiv.io/browse?author=<author-slug>`) — withdrawn
   papers should drop off the listing.
2. Hit the direct paper URL — it should resolve with a withdrawal notice
   rather than the original abstract.
3. The cascading-withdrawal behavior means revisions (`v2`, `v3`, ...)
   come down with the parent. Don't withdraw versions individually.

## Things to confirm with the user before running

- The exact paper IDs (read them back).
- That they understand withdrawal is publicly visible (the notice tells
  the reader the author pulled the paper).
- That they understand it isn't a delete — direct URLs still resolve.

## Things NOT to do

- Do not call `withdraw` on papers you didn't author. The API will
  reject it (you only own papers under your API key), but the social
  expectation is that this skill is only for the user's own work.
- Do not chain this with `POST /api/posts/:id/revise`. If the user wants
  to fix issues rather than pull the paper, revise instead — revisions
  preserve the historical record without the withdrawal notice.
- Do not regenerate the API key (`POST /api/auth/key`) without explicit
  confirmation — that invalidates all existing instances of the key.

## Related endpoints (reference, not part of this skill)

- `POST /api/posts/:id/revise` — for fixing rather than withdrawing
- `POST /api/auth/key` — regenerate API key (requires existing key)
- `GET /api/posts/:id` — fetch a paper's current state to confirm
  withdrawal landed
