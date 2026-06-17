# paper/

This directory holds the Yantra position paper that is auto-submitted to
[clawRxiv](https://clawrxiv.io) for AI peer review on every push.

## Files

- **`paper.md`** — the canonical paper. Editing this on main triggers
  `.github/workflows/submit-papers.yml`, which submits the new version
  (superseding the previous one tracked in `.post_id`) and commits the
  fetched review back into `reviews/`.
- **`SKILL.md`** — instructions for the AI reviewer. Read by the
  reviewer alongside `paper.md`. Editing this also triggers a
  resubmission, since the reviewer's focus changes.
- **`reviews/`** — review files committed back by the workflow.
  Filenames are `v{N}_post{ID}_review.{json,md}`. `N` is the count of
  existing review files plus one; `ID` is the clawRxiv post ID.
- **`.post_id`** — the most recent clawRxiv post ID. Used by the
  submit script to supersede the previous version. Tracked in git so
  the next push picks up where the last one left off.
- **`candidates.jsonl`** — (optional, written by `scripts/quick_review.py`
  if/when ported) one JSON line per locally-submitted candidate
  variant, picked up by `scripts/pull_all_reviews.py` for catch-up
  fetches.

## Workflows

- **`submit-papers.yml`** — push-triggered on `paper/paper.md` or
  `paper/SKILL.md`. Submits and waits for one review. Auto-commits the
  result back with a `Skip-Submit: true` trailer to prevent infinite
  re-trigger.
- **`pull-reviews.yml`** — push-triggered on any `paper/**` change plus
  scheduled every 30 minutes. Idempotent catch-up that fetches reviews
  for any post we know about whose review file is missing.

## Manual operations

```bash
# Resubmit and pull the review locally (requires CLAWRXIV_API_KEY env):
python scripts/paper_submit_and_fetch.py --paper-dir paper \
    --tags operating-systems,neuro-symbolic,gpu,formal-verification,critical-systems

# Catch up reviews for everything we've submitted:
python scripts/pull_all_reviews.py --paper-dir paper
```

## How submission resolves the title

`paper_submit_and_fetch.py` reads the H1 from `paper.md` and uses it as
the clawRxiv post title. Pass `--title` to override (a warning prints
when the override does not match the paper H1).
