# Merge / PR help — how to land work on this repo safely

User-requested doc (2026-04-13). Captures the "some craziness going on
with the API or I don't know what's going on" pattern that has bitten
recent sessions. Read this before opening PRs or merging branches.

Why this is tricky on *this* repo specifically:

- `papers-ci.yml` auto-submits to clawRxiv on every push that touches
  `sutra-paper/paper.md` or `fly-brain-paper/paper.md`. Every push is a
  new clawRxiv version. A merge commit that squashes three weeks of
  iteration into one push is a single clawRxiv submission with a messy
  diff — reviewers see the last-step contents, not the iteration.
- `GITHUB_TOKEN` cannot modify workflow files regardless of permissions
  config. Cron / CI pushes that touch any workflow YAML get rejected
  with a `workflows permission` error even if the specific commit in
  the push did not touch the YAML (push protection fires on the tree,
  not the diff). See `queue.md` → "CI pipeline state" for the full
  story; this is why `papers-ci` was reverted from branch+PR to
  direct-master-push in commit 211bd92.
- `competition-cron` still uses the branch+PR flow and still hits that
  wall from time to time.
- Paralysis-era Claude Desktop sessions (see the `dddd` transcript
  audit, 2026-04-13) committed *directly to master* during API-error
  loops while all other work that session was supposed to land via
  PRs. Later sessions that read master expecting it to match the PR
  queue got confused. This is the failure mode this doc is trying to
  prevent.

## Rules of thumb

### 1. One logical change per commit. One logical change per PR.

If the commit message needs the word "and" between two ideas, split it.
Paper edits especially: one paragraph or one table per commit per the
CLAUDE.md "incremental paper edits only" rule. Do not batch. The
reviewer is an LLM and the last commit is the one it evaluates — a
six-commit PR with one squash at the end lands as one version on
clawRxiv, and you cannot bisect which change caused a rating to move.

### 2. Pull with rebase before every push.

```
git pull --rebase origin master
```

Humans and cron both push to this repo. A merge commit for a trivial
race is noise in the history. If a rebase hits a conflict in
`paper.md` or `queue.md`, resolve by hand — both are high-churn files
and a bad auto-merge is worse than a visible conflict.

### 3. Never skip hooks, never force-push to master.

The pre-commit hooks exist because CI failure modes on this repo are
hard to diagnose from logs alone (see CLAUDE.md → "CI/CD IS BROKEN").
`--no-verify`, `--no-gpg-sign`, and `push --force` on master all make
the failure mode worse, not better. If a hook is failing, fix the hook
or fix the thing the hook is checking — don't route around it.

### 4. PRs for feature branches, direct pushes for one-liners on master.

- **Feature branch** (anything non-trivial, anything user-visible,
  anything that could fail CI): open a PR, let it sit, merge when
  green. Per branch-strategy rules, this repo's Claude sessions
  typically work on `claude/<task-slug>` branches per session.
- **One-liner fix on master** (typo, queue.md update, queue removal):
  direct push is fine — this is what `papers-ci` uses, and it's what
  `competition-cron` should probably switch to per `todo.md`'s
  GitHub-Actions-failure-modes section. A full PR for a one-line
  queue.md edit is ceremony that slows the iteration loop without
  adding safety.

### 5. Do *not* mix direct-master commits and PR-branch commits in the
same session.

This is the specific failure mode that motivated this doc. During the
paralysis episode captured in `dddd`, Claude Desktop committed
deletions directly to master while the same session was supposed to be
driving a PR-branch workflow. Later sessions reading the repo could
not tell "is this state current or is it mid-merge?" and made
decisions on bad data.

**Rule: pick one flow for the session and stick to it.** If you're
working on a branch, stay on the branch. If you're patching master
directly, don't also open PRs elsewhere on the same files. If you
have to switch mid-session, announce the switch in a commit message
and in queue.md so the next session knows what happened.

### 6. After every merge, update queue.md.

If a PR just landed and the queue in `queue.md` doesn't reflect it,
the queue is wrong. Per CLAUDE.md queue protocol: queue items removed
in the same commit as the implementation. Merges should never leave
queue.md claiming something is pending when it's done.

### 7. Ask for logs before diagnosing CI failures.

From CLAUDE.md: "Do not diagnose CI problems from the repo alone."
GitHub Actions logs are not accessible from the Claude Code
environment. If CI is red, ask the user for the run URL or the log
paste. Guessing at causes has repeatedly produced wrong fixes (e.g.
blaming `paper.md` merge conflicts when the real issue was
permissions).

## Recovery playbook

### "I have uncommitted work and a rebase conflict."

1. `git status` — confirm what's staged vs unstaged.
2. `git stash push -u -m "pre-rebase save <short reason>"` — named
   stash so you can find it later.
3. Do the rebase.
4. `git stash pop`.
5. Resolve any post-pop conflicts by hand.

Do not use `git reset --hard` as a conflict-resolution shortcut. Per
CLAUDE.md "Executing actions with care": destructive git operations
get used only when they are truly the best move, not when they are
merely expedient.

### "I committed to master but I meant to commit to a branch."

1. `git log -1 --stat` — confirm the commit you want to move.
2. `git branch <recovery-branch-name>` — tag the tip.
3. `git reset --hard HEAD~1` — **only if nothing has been pushed yet**.
   If the commit has been pushed, *do not* reset master; instead,
   `git revert` on master and re-apply on the branch.
4. `git checkout <recovery-branch-name>` and continue there.

Pushed mistakes on master are much more costly to undo than local
mistakes. Check `git status` / `git log --oneline origin/master..HEAD`
before any destructive step.

### "CI rejected my push with 'workflows permission'."

You probably did not modify a workflow file. GitHub's push protection
fires on the tree, not the diff. Options:
- Rebase onto the latest master so the push is fast-forward and the
  tree matches.
- Push the non-workflow parts directly to master (mirroring the
  `papers-ci` fix).
- If the error genuinely *is* about a workflow change, land that
  change through a human user's PAT — `GITHUB_TOKEN` cannot do it.

### "I pushed the wrong commit to master."

Do not force-push master. Commit a `git revert` instead, push that,
then re-work the change correctly on a branch. Per CLAUDE.md
"carefully consider the reversibility and blast radius of actions":
force-push to master destroys upstream state for every collaborator
and every downstream clone, and is overkill for any mistake you can
revert forward.

## When in doubt

Surface it to the user in plain text before acting. The session
failure mode that motivated this doc was a session that kept trying
to recover from API errors by pushing forward with more commits,
rather than pausing and asking. Pausing is cheap. An hour of repo
repair is not.
