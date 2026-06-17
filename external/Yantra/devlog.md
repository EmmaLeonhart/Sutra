# Yantra — Devlog

Where "done" lives. Each completed `queue.md` item is deleted from the queue and
recorded here, dated, in the same commit as the work. Releases and milestones too.

---

## 2026-06-13

### 2026-06-14 daily substrate-honesty audit — clean

Discharged the auto-prepended audit. No `.su` / kernel / apps / compile-admit
files changed on Yantra main since the 2026-06-13 audit — every commit was
website (`site/`), docs/planning, queue bookkeeping, or Sutra submodule pin
bumps. No "recurrent/RNN/substrate-pure" claims were made (no substrate work);
the only "verified" claims were render-verification (Playwright runs) and
fixture counts (counted against `sdk/`). Nothing amiss; item deleted.

### Follow-up — documented Sutra's other language frontends (PR #36, Emma-requested)

Emma: "do the sutra stuff and merge it in." Verified `sdk/` has 9 transpiler
frontends (ts 19, ocaml 45, rust 9, scala 9, clojure 8, elixir 7, fsharp 7,
haskell 6, c 2 fixtures) vs the docs' stale "TS is the sole transpiler, C
parked." Fixed `AGENTS.md` (agent-facing) and added an "Other language
frontends" section to `docs/typescript-to-sutra.md` (public site) with honest
maturity framing (fixture-tested, none as complete as TS). Counts verified
against actual `sdk/` dirs. **PR EmmaLeonhart/Sutra#36 auto-merged (squash)
to main**; submodule reconciled to main (9d30c6e), branch deleted.

### End-of-session summary (website refocus + celestial restyle)

Yantra repurposed as primarily the website repo for this session. Shipped:
- **Yantra site** (`yantraos.org`): pivoted off the OS / interpretable-neural-
  computer framing to the self-optimizing-landing-pages GTM wedge (mechanism-
  forward headline); stripped AI-safety framing (kept "interpretable" per Emma);
  removed paper CTA / bootloader / finance-defense market / co-founder asks;
  added a bolder celestial/glow CSS layer (`site/celestial.css`, separate from
  the shared `identity.css`). Live on Pages.
- **Sutra site** (`sutra.yantraos.org`): matching celestial layer + a docs
  accuracy refresh (introspection accessors marked removed per the no-readout
  ruling; TS import status corrected). Shipped via **PR #35**, auto-merged to
  Sutra main; submodule back on main, branch deleted.
- **Crons:** ran the 2:30pm-gated Sutra-pull/ignition + the three-cron
  autonomous loop all session; pin HEAD-tracked Sutra per Emma's override.
- **Accepted as-is:** kernel/apps CI red vs current Sutra (Emma's call). **Not
  done (Emma's call):** archive of non-website code (kept everything); public
  documentation of Sutra's 7 other language frontends + the stale AGENTS.md.



- **Website-refocus session set up.** Planned the repository-refocus + celestial
  restyle into `queue.md`; created the 2:30pm Sutra-pull/ignition cron and (after
  the pull) the work-loop / auto-flush / status-report crons. All session-local.
- **Sutra submodule pulled to v0.7.1-745 (`11026ca`)**, +312 commits past the prior
  pin, so website docs can reflect current capabilities. Pure fast-forward.
- **Step 6 (Sutra docs accuracy refresh) done + PR #35 merged.** Emma: do the refresh, PR it, automerge. Evidenced fixes (audit-backed): `capabilities.md` — removed the `real()/imag()/truth()/component()/semantic()/synthetic()` accessors (listed as supported but are violations being removed per the 2026-06-07 no-readout ruling) + the stale free-function axis-read row; `typescript-to-sutra.md` — corrected the import/export summary-table row (named ES imports work since 2026-05-10; namespace/require don't). Did NOT touch agent-facing `AGENTS.md` or advertise the other language frontends publicly (Emma's branding call — flagged). Site rebuilds clean. Folded into **PR EmmaLeonhart/Sutra#35**, which **auto-merged (squash) to Sutra main**. Submodule switched back to tracking main (a881c16); website-celestial branch deleted; Sutra-pull cron simplified to main-only.
- **Branding clarified (Emma 2026-06-13): debranding is SAFETY ONLY; "interpretable" stays.** Restored "interpretable" as a Sutra descriptor on the Yantra site (it had been over-stripped with the safety language). Sutra docs grepped — no AI-safety branding present, nothing to debrand. Step 6's remaining piece is an optional content-accuracy refresh (not branding), left for Emma to direct.
- **Queue step 5 (Sutra celestial restyle) done + PR opened.** Created Sutra branch `website-celestial`; added `web/celestial.css` (mirror of Yantra's bolder layer) and wired it into `scripts/build_site.py` (linked in the page `<head>`, copied into the built site). Sutra site is a custom static build (`build_site.py` from `docs/*.md` on the shared identity — not MkDocs). Render-verified locally (home page shows the celestial layer). Pushed; **PR EmmaLeonhart/Sutra#35** (docs/website-only, no language code touched). Step 6 (Sutra docs *content* pass) deferred to Emma — needs accurate review of the +300 commits and a call on whether safety-debranding applies to Sutra's technical "interpretable" framing.
- **Step 7 (verify) done inline.** Both sites render-verified via Playwright this session: Yantra dark+light (celestial + wedge copy, no safety/OS language), Sutra home (celestial layer loads). Yantra Pages green; Sutra PR build is docs/website-only.
- **Queue step 4 (Yantra copy pivot) done — Emma OK'd + "barrel through".** Front page pivoted off the OS / interpretable-neural-computer framing to the self-optimizing-landing-pages wedge (mechanism-forward headline "Your page, improving itself."). Stripped ALL AI-safety / interpretability / verifiability / critical-systems language (Emma: not a brand she wants anymore). Removed the paper CTA, bootloader bullet, financial/defense market section, and the co-founder/book-a-call asks. New sections: How it works / Why it's different / Built on Sutra (Sutra as enabling tech, not a safety story). Public-safe wording only. Render-verified; shipped to main; Pages deploys.
- **Queue step 3 (Yantra celestial layer) done.** `site/celestial.css` — a new layer linked after `identity.css` (shared identity untouched): deep-space field, cool periwinkle/cyan/violet nebula bloom, a glowing bloom behind the hero headline, twinkling starfield, fine grain, bloom on accent type/controls, gradient-hairline dividers. Dark-scoped; light theme stays calm. Render-verified both themes via Playwright; deployed via Pages (green). First pass was restrained; pushed bolder per Emma's call. Mirroring the look onto Sutra (step 5) waits on her confirm of the bolder intensity.
- **Decisions applied (Emma 2026-06-13):** archive dropped (keep all code); copy pivots to the self-optimizing-landing-pages wedge (mechanism-forward headline picked; full draft presented, awaiting sign-off); kernel/apps CI red is accepted (ignore — parked prototype, site Pages is green); one-shot PR cron set to PR `website-celestial`→Sutra main ~19:55 local; Sutra pin re-bumped to v0.7.1-747 on the 2-hourly tick.
- **Queue step 1 (audit) done** → `planning/24-website-repo-refocus.md`. Finding:
  most "non-website" code is NOT duplicated in Sutra (kernel, orchestrator,
  bootloader, paper, planning are Yantra-only); only `apps/{calc,echo,terminal}`
  are genuine Sutra duplicates. Two decisions raised for Emma (archive scope;
  current public positioning) that block queue steps 2/4/6. Step 3 (celestial CSS)
  is positioning-neutral and stays unblocked.

## 2026-06-16 — Preserve calc substrate-parsing in Sutra (additive)

Copied `apps/calc/parse_op.su` + `parse_int2.su` into Sutra's `demos/calc/`
(Sutra main `0f80c6a3`) so the substrate operator/int parsing building blocks
live in the actively-developed language repo too. Yantra's copies are kept —
duplication for safety, not a move. Part of the 2026-06-16 PRESERVE-mode cleanup
(Emma: "worth definitely preserving the stuff"; OS prototype is parked, not
deleted).

## 2026-06-16 — Disable daily-audit queue prepend

Disabled the `schedule:` trigger in `.github/workflows/daily-audit.yml` (kept the
file + `workflow_dispatch` for manual re-enable). The repo does no `.su` work now
(OS prototype parked, site rebranding), so the daily substrate-honesty prepend
was only cluttering `queue.md`. Reversible: restore the commented `schedule:`
block. Stale daily-audit items were also cleared from `queue.md` in the
2026-06-16 cleanup rewrite.

## 2026-06-16 — Reconcile docs to the rebrand (preservation-framed)

- `README.md`: added a top banner — public brand moving to Noldor Technologies
  (noldor.tech), `yantraos.org` redirects there from 2026-06-18, and the
  OS/kernel prototype is **preserved/parked, not abandoned**; Sutra is actively
  developed.
- `apps/README.md`: fixed the stale `font/` row (migrated to Sutra 2026-05-28),
  added a `gui-rust/` row (preserved/parked), and noted the 2026-06-16 calc
  `.su` preservation copy to Sutra.

This drains the 2026-06-16 PRESERVE-mode cleanup queue (calc-preserve,
daily-audit-disable, docs-reconcile all done). OS prototype untouched/preserved.

## 2026-06-16 — CLAUDE.md de-stale pass (todo item promoted)

Promoted "fix up the claude.md because it has bloat" from todo.md. Did a
conservative doc-truth pass, not an aggressive cut (every section is a
load-bearing rule):
- Cross-repo § "The mechanics": `master` → `main` throughout (Sutra migrated its
  default branch; master frozen at v0.4.1 — the loop's "start here" note flagged
  this stale ref).
- Reconciled the mechanics with the release-tags-only pin policy (the 6am cron
  owns pin advancement; don't hand-bump mid-session).
- Removed the wrong hardcoded `# currentDate 2026-05-07` block (the harness
  supplies the real date).
- Added a short Status note: rebrand to Noldor + OS prototype preserved/parked.
- Verified all rule sections still present; no stale Sutra-`master` refs remain.

Net 477→480 lines — this was de-staling, not net shrink. The deeper de-bloat
(move long rationale to planning/, keep CLAUDE.md terse) is left as an OPTIONAL
todo item pending Emma's OK, since cutting risks dropping a load-bearing rule.

## 2026-06-16 — Redirect cutover is now TIME-BASED in GitHub Actions (not a cron/PR)

Replaced the session-cron + merge-PR cutover with a date check in pages.yml
(Emma: "it's literally time based — have the Actions build check the date").
- Added redirect/ (index.html + 404.html path-preserving to noldor.tech + CNAME
  yantraos.org), separate from site/ so the normal page stays live until the date.
- pages.yml now picks site/ before 2026-06-18 and redirect/ on/after, and runs
  on a daily `schedule` (17 22 UTC ≈ 3:17pm Pacific) so it flips with no human
  action and no session dependency.
- Superseded: closed Yantra PR #1 and removed the local 3pm cutover cron.
