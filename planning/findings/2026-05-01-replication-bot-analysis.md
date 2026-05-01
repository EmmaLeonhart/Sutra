# Replication bot analysis: SutraReplication3 outcome

**Date:** 2026-05-01
**Scheduled task:** Cron `a6741576` fired at 01:02 PST after a 60-minute soak.
**Verdict:** **Replication did not occur.** The directory is a cleanvibe scaffold with no Sutra content at all.

## What's in `~/Documents/Github/SutraReplication3`

```
.claude/scheduled_tasks.lock
.gitignore
CLAUDE.md
README.md
runclaude.bat
```

That's the entire tree. `find . -name "*.su"` returns zero. `find . -name "*.py"` returns zero. There is no `sdk/`, no `examples/`, no `paper/`, no `experiments/`, no SutraDB.

## Git history

```
5ab0d8d Initial commit: cleanvibe scaffold
```

One commit — the scaffolding. Nothing after.

## What the scaffold contained

- `README.md` — placeholder with `_TODO: Describe what this project does._`
- `CLAUDE.md` — generic cleanvibe template (workflow rules, testing rules, "do not enter planning-only modes"). The project description section is `_TODO: Describe what this project is about._`
- `runclaude.bat` — a one-liner `cd /d "%~dp0" && claude` to launch Claude Code in the directory.

The CLAUDE.md does **not** point at the canonical Sutra repo, the paper, or any replication brief. There is nothing in the project for a Claude Code session to anchor on.

## Why the replication didn't happen

Most likely explanations, in order of probability:

1. **The replication agent was never actually launched.** `runclaude.bat` would open an interactive Claude Code session, but no automated agent was started against this directory. The cleanvibe scaffold sits unattended.
2. **The agent was launched but had no replication brief.** Without a CLAUDE.md or README pointing at the Sutra paper / repo, an agent starting fresh in this directory has no signal that it is supposed to replicate Sutra. It would either ask the user what to build or sit waiting for input.
3. **The agent got stuck at the planning stage.** The CLAUDE.md explicitly forbids "planning-only modes" but doesn't give the agent a starting task — so the agent has nothing to plan *toward*. This is a structural setup problem, not an agent failure.

Note: there is a `.claude/scheduled_tasks.lock` file present, which suggests Claude Code has run in this directory at least once and acquired its own scheduling lock — consistent with explanation #2 (launched but no brief).

## What did NOT diverge — because nothing was attempted

The original task asked us to "compare against the canonical Sutra repo" to see what was replicated faithfully and what diverged. With zero `.su` files, zero compiler code, zero tests, there is nothing to compare. The replication never produced a target.

## Honest verdict

**0% replication.** The cleanvibe scaffold is a starting point, not a replication. The cause is upstream of the agent: the scaffold did not include a brief telling the agent what to replicate. Setting up another replication run would mean writing a `CLAUDE.md` (or pasting the paper into a `BRIEF.md`) that explicitly says "your task is to reimplement Sutra from this paper plus the SKILL.md reproducer at <link>" — and *then* running an autonomous agent loop, not just opening interactive Claude.

## Suggested next-attempt scaffolding

If the goal is to test whether an LLM agent can replicate Sutra from the paper alone, the minimum viable input is:

1. The paper PDF or markdown (`paper/paper.md` from the canonical repo) committed at the root.
2. The SKILL.md (this lists the test invariants the replication must satisfy).
3. A `CLAUDE.md` whose project-description section reads something like:
   *"Your task is to reimplement the Sutra programming language as described in `paper.md`, satisfying every test in `SKILL.md`. You may not look at the canonical repo at `~/Documents/Github/SutraRNN/`. When all SKILL.md tests pass, commit and stop."*
4. An autonomous-loop agent invocation — `runclaude.bat` opens an interactive session that idles until a user types something. A real replication run needs the agent to keep working until the SKILL.md tests pass.

## Status

This finding is the deliverable for cron `a6741576`. Committing to the canonical SutraRNN repo so the result is durable; the SutraReplication3 directory itself is unchanged.
