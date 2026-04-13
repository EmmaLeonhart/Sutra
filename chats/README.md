# chats/

Claude.ai web chats, saved as HTML by the user (File → Save Page As) and extracted to markdown with `scripts/extract_chat.py`.

These are unstructured thinking conversations — design sketches, naming discussions, concept explorations. They are cheaper than Claude Code sessions but the content is valuable and lives in the repo so it can be referenced from planning docs, the paper, and future sessions.

## Workflow

- User saves a chat as HTML into this directory.
- Run `python scripts/extract_chat.py` (or extract inline). It scans for `.html` files without a matching `.md` sibling and writes `<title-slug>.md`.
- Commit both `.md` and `.html`. The HTML is the source of truth; the `.md` is the working copy.

## Lifecycle

Chats are **triage inputs**, not permanent artifacts. Once a chat's content has been:

- implemented in code/spec, or
- recorded in `STATUS.md`, `todo.md`, `planning/open-questions/`, or `planning/findings/`, or
- consciously decided as not-pursuing,

the extracted `.md` (and its `.html`) can be deleted. The commit message should say which of the three paths applied.

This README exists so the directory survives when all chats are cleared.
