# Sutra — Work Queue

**This file is a queue, not a state snapshot.** It lists what is being worked on now and
what is next, in execution order — barrel it top to bottom. **Finished work is REMOVED in the
same commit it ships** (history lives in `git log`, `DEVLOG.md`, `planning/findings/`).
`todo.md` is the longer-horizon backlog; items migrate `todo.md` → here → deleted on completion.

**⭐ CLEARING the queue is the SAFE default (Emma 2026-06-21).** When an item is done, DELETE the
line — **version control + `DEVLOG.md` already hold the entire history, so nothing is ever lost by
removing it.** Deleting a finished item is NEVER the risky move; the git log is the safety net.
The UNSAFE thing is letting done work accumulate — a "Recently shipped" pointer block,
`~~struck-through~~` lines, "DONE"/"✓" markers, or a paragraph summarizing what shipped. That bloat
buries the open work and is exactly what keeps re-growing this file. The queue holds ONLY
not-yet-done work; the moment something ships, it leaves. **Do not defer work to a clock time either**
— if nothing else is in flight, just do it now (no "do this at 2pm" scheduling).

**Owned + autonomous (Emma 2026-06-20):** the agent organises this queue itself — pulls items from
`todo.md`/findings/specs, orders by value, decomposes into concrete steps, prunes done work, and
executes top-to-bottom WITHOUT asking. Report via commits + DEVLOG, not questions.

---

## Context (read first, do not work on)

- **`paper/paper.md` is UNFROZEN** (Emma 2026-06-07); `paper/neurips/` freeze RETIRED 2026-06-18.
  Measured numbers only; no overclaiming. Editing `paper/formal-verification/paper.md` or
  `paper/paper.md` triggers a clawRxiv resubmit CI — intended for real updates, not churn.
- **NEVER use `Math.mod`** (measured vector-collapse/NaN). Use complex rotation for wrap/periodic.
- **GUI is on Emma's SEPARATE branch** — OUT of this queue. Do NOT re-add GUI items.
- **Substrate purity is non-negotiable**: every op runs on the substrate, NO host readout
  (`.item()`/`float(tensor)`) inside operations.
- **Multi-clone**: editable `sutra_compiler` install points at the sibling `Github\Sutra`; verify
  changes here via `PYTHONPATH=sdk/sutra-compiler`. CI uses this repo's compiler.

## ACTIVE — barrel top to bottom

_Nothing active right now._ Recent work — numbers-on-substrate + its scalar-position fixes, perf/fusion,
multi-process, FV surface + measurement-claim gates, await core, the NeurIPS-frozen-layer removal, the
email-dedup, and the paper Background→Preliminaries refactor (after Related Work, with Kleene grounding +
the Shaw et al. citation) — is all shipped and lives in `DEVLOG.md`, `git log`, and `planning/findings/`.
When starting fresh, pull the next genuinely-unblocked item from `todo.md`.

## Stuff to do

So I am editing this on GitHub separately, but just keep in mind it's because of the fact that it's a bit unsafe to insert while you are also editing the queue. Just think of this as being an insertion but also a change of the parked to formerly parked thing in the queue. 

I am very confused as to why it is that we are not at v1.0.0 yet. Is there a technical reason in documentation? Is Sutra just not usable yet based on your judgment?

Do an audit to figure this stuff out.

Also check whatever is going on in [[#Formerly parked]] Audit whether those things are done or not, and if they are done then remove them and if not then implement them

Yantra is kinda not a thing anymore so weird that it is referenced. We are just doing desktop io for Sutra. Anynthing that is called Yantra here is just io stuff or the legacy imported content. But def we are moving away from calling it Yantra. It is now Sutra for Windows.

But yeah, I think that most of the stuff here is just kind of absent. Most of it in this section is just kind of absent. This, and the formerly parked stuff, might have just been added to the queue based off of some improperly done pull request or something like that. I want you to specifically audit the stuff. 


Once you have finished this stuff up, with finishing the paper and the formerly parked stuff and things like that, I think we're probably going to be able to have our actual proper version one. I'm not really entirely sure, because I don't really know what the actual judgement is for why we're not at version one. Even if we can't get to version one right now, unless a new version was pretty recent, we're probably at a point where we can move on beyond whatever version we're on right now.

Our releases: I'm not sure how well we're doing our releases, but I think we might have been a bit too conservative with them. Yeah, an audit after the paper's done and the stuff to do is done, and we've barreled through the formerly parked and stuff like that, we're going to be seeing if we can just do v1. 

---

## Formerly parked

- **await Stage-2 — full gated `while_loop` with a LIVE external-axon producer — Yantra-I/O-gated.**
  The await CORE shipped 2026-06-20 (mid-function lowering + Promises/A+ rejection propagation, substrate-
  pure). What remains is the poll loop spinning on a promise an EXTERNAL producer resolves over time — i.e.
  the orchestrator (Yantra) writing the resolved value into the awaited axon. `await_value` stays the
  β-reduced no-producer form until there's a real producer to test against. Also: awaits buried in nested
  control-flow still fall through to the codegen rejection. Resume when wiring Yantra's promise producer.
- **(historical) Full async/await Stage-1 desugar — was DESIGN-BLOCKED; the await MODEL is now settled.** First-class
  functions (now shipped) unblock the *mechanism* (a continuation can be a hoisted function), and the gap
  is concrete (`await` as a mid-function expr raises `CodegenNotSupported` in `codegen_base.py`; only
  tail-position `async function … return await e` works). BUT the await *model* itself is undecided: Emma
  2026-05-17 directed "model the awaited value as an implicit axon INPUT + an arrival-flag axis, NOT a poll
  loop," which conflicts with `planning/sutra-spec/promises.md`'s gated-while-loop lowering. That's a
  language-semantics decision (load-bearing, conforms to Promises/A+), not an implementation detail — so it
  is NOT a self-direct call. Parked until the model is settled; building either lowering now risks building
  the wrong one. (Do not queue this as a question — wait for Emma to settle the model in her own time.)
- **§1C steps 3 & 4 — per-process CUDA isolation + CUDA-IPC codebook sharing.** Need a Linux/CUDA box;
  unverifiable on this Windows clone (no CUDA IPC). The portable core is done + validated. Resume when a
  CUDA environment is available; until then writing the code would ship unverified substrate work.
- **§1C ProcessPoolRuntime CUDA path** (`force_cpu=False`, per-process CUDA contexts) — part of the above.
- **§2 WASM source frontend.** Sibling-owned (its own work-loop / `:33` cron) and largely
  clang/uv/wat2wasm-blocked here. Coordinate via CI; do not collide with the subtree agent. Decompose
  from `todo.md` §"Phase 3 — WASM" only if it lands on this clone with a toolchain.

---

## Pointers

- Substrate-leak catalogue: `Audit.md`. Longer-horizon backlog: `todo.md`. Findings: `planning/findings/`.
  Open design questions: `planning/open-questions/`. Devlog: `DEVLOG.md`.
- Transpiler edge cases (low-value, leave-on-WASM-fallback): `planning/wasm-fallback-edge-cases.md`.
- Corpus: `github.com/EmmaLeonhart/sutra-w2c-corpus` (submodule `corpus/`) + HF mirror.
- Yantra (downstream OS): vendored in-tree at `external/Yantra/`.

## Session bracket

- The autonomous loop is the self-timed `ScheduleWakeup` form (not the old three-cron playbook).
- Own the queue, barrel through, report via commits + DEVLOG — no questions.
