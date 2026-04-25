# chats/

Claude.ai web chats, saved as HTML by the user (File → Save Page As) and extracted to markdown with `scripts/extract_chat.py`.

These are unstructured thinking conversations — design sketches, naming discussions, concept explorations. They are cheaper than Claude Code sessions but the content is valuable and lives in the repo so it can be referenced from planning docs, the paper, and future sessions.

## Workflow

- User saves a chat as HTML into this directory.
- Run `python scripts/extract_chat.py` (or extract inline). It scans for `.html` files without a matching `.md` sibling and writes `<title-slug>.md`.
- Commit the `.md`. **Delete the `.html` and any `<title>_files/` browser-asset directory** — the `.md` is the canonical, grep-able working copy and the HTML is multi-MB bloat. Policy revised 2026-04-25 after a chats/ cleanup; previously the HTML was kept as a backup, but the asset directories alone were ~38 MB and the `.md` extraction is sufficient.

If a chat is from Claude Code (CLI) rather than claude.ai, `extract_chat.py` will report 0 message blocks because the DOM markup differs. Fall back to a raw-text dump (see `sutradev-claude-code.md` for the pattern: cleaned visible text with a header noting provenance) before deleting the HTML.

## Lifecycle

Chats are **triage inputs**, not permanent artifacts. Once a chat's content has been:

- implemented in code/spec, or
- recorded in `STATUS.md`, `todo.md`, `planning/open-questions/`, or `planning/findings/`, or
- consciously decided as not-pursuing,

the extracted `.md` (and its `.html`) can be deleted. The commit message should say which of the three paths applied, and each chat gets its own commit so the reasoning stays auditable.

This README exists so the directory survives when all chats are cleared.
