# 24 — Website-repository refocus: audit findings

**Date:** 2026-06-13. **Status:** audit complete (queue step 1); steps 2/4/6 blocked on an Emma positioning decision (see § 3).

This is the output of the "is Yantra now primarily the website repo, and what
(if anything) here is worth keeping vs. archiving" audit. Sutra submodule was
freshly pulled to **v0.7.1-745 (`11026ca`)** for the cross-check.

## 1. What duplicates Sutra vs. what is Yantra-only

The working hypothesis going in was "most of this duplicates Sutra-side work;
archive it and treat the repo as the website." The audit only partly supports
that. **Most of the non-website code is NOT in Sutra.**

| Item | In Sutra? | Disposition |
|------|-----------|-------------|
| `apps/calc/` | ✅ `external/Sutra/demos/calc/` | archive candidate (sources live Sutra-side) |
| `apps/echo/` | ✅ `external/Sutra/demos/echo/` | archive candidate |
| `apps/terminal/` (py) | ✅ `external/Sutra/demos/terminal/` | archive candidate |
| `apps/gui-rust/` | ❌ Rust orchestrator+GUI bridge | Yantra-only |
| `kernel/` | ❌ host-side Connectome Manager | Yantra-only, substantive |
| `orchestrator/` | ❌ Rust port + checkpoint codecs | Yantra-only, substantive |
| `bootloader/` | ❌ bare-metal QEMU boot | Yantra-only, substantive |
| `paper/` | ❌ (Sutra has a *different* FV paper) | Yantra-only — the position paper |
| `planning/` | ❌ OS design corpus | Yantra-only |
| `tests/`, `scripts/`, `tools/`, `Dockerfile`, CI | ❌ | Yantra-specific infra |
| `site/` | ❌ | the website itself |

So the clean version of "archive everything non-website" is **not** what the
repo actually contains. Only the three Python demos (`calc`, `echo`,
`terminal`) are genuine Sutra duplicates and clearly archivable. Everything else
is either the website or Yantra-only engineering that has no home in Sutra.

## 2. `daily-audit.yml`

Auto-prepends a kernel substrate-honesty audit item to `queue.md` daily (04:23
UTC). It exists to catch `runtime_dim` bloat / fake-recurrence drift in `.su`
work. Sutra has a companion copy. On a website-first `main` with the `.su` apps
archived, the Yantra-side copy has little to audit and just adds noise — so its
fate is tied to whether the apps move (§ 3). If the apps archive, this should
archive with them and let Sutra's copy be canonical.

## 3. The blocking decision: what is this website *for*?

Two contradictions surfaced that I cannot resolve without Emma:

1. **Scope.** The audit (§ 1) shows the repo is not mostly-duplicated-cruft; it
   holds real Yantra-only work (kernel, orchestrator, bootloader, the paper, the
   planning corpus). "Archive it all, keep only the website" would discard
   substantive, non-duplicated material. The narrower, defensible move is to
   archive only `apps/{calc,echo,terminal}` (+ their `!run*.bat`) and keep the
   rest.

2. **Positioning.** The current `site/index.html` copy leads with a market
   framing that appears to predate Emma's most recent go-to-market direction
   (captured in her **private** planning repos, which must not be reproduced
   here). Rewriting site copy (queue steps 4 and 6) requires Emma to confirm the
   current public framing first. **Do not copy any `business/` content from the
   private repos into this public repo or the site.**

**Until Emma decides both:** queue step 2 (archive) should be narrowed to the
three demos only (not a wholesale gut), and steps 4/6 (copy rewrites) are
blocked. Step 3 (the celestial CSS aesthetic) is positioning-neutral and can
proceed regardless.
