# Yantra

## Skills

Workflow behaviors live as skills in `.claude/skills/` (auto-discovered by Claude Code):
`emergency-stop`, `cron-is-local`, `autonomous-loop`, `queue-driven-workflow`,
`writing-style`, `cleanvibe-update-check`. They are vendored into this repo and kept
current by the `cleanvibe-update-check` skill.

- **Last cleanvibe update check:** `never`
- **Updates source:** <https://cleanvibe.emmaleonhart.com/updates.md>


## Session-local auto-flush cron — RESTART AT THE START OF EVERY SESSION (Emma 2026-05-24)

**Leaving the `external/Sutra` submodule with uncommitted or unpushed changes actively causes complications** (dirty/detached submodule state, the Yantra working tree showing `M external/Sutra`, work that silently disappears). So: **push all the time** — never let the submodule sit dirty.

**At the START of every session, (re)create this `CronCreate` job** (it is session-local — `durable: false` — so it dies when the session ends and must be recreated each session):

- **Schedule:** `15 * * * *` (every hour at :15).
- **What it does:** commit + push ALL pending work in BOTH repos so nothing sits uncommitted —
  1. `external/Sutra`: `git -C external/Sutra fetch origin --quiet`; fast-forward if behind; if the working tree has changes, commit them on the current branch (**`main`** unless told otherwise this session — Emma works on `main`, not `yantra-driven`); push if ahead. **Never force-push, never `reset --hard`, never discard the other machine's work.**
  2. Yantra: `git fetch origin --quiet`; ff if behind; if **non-submodule files** changed, commit + push `origin main`. **Do NOT bump the `external/Sutra` pin here.** As of 2026-06-05 the Sutra pin tracks **release tags only**, advanced solely by the 6am release-pin cron (see next section). If the working tree shows `M external/Sutra` (the submodule HEAD drifted off the pinned release), leave it for the 6am job — never `git add external/Sutra` in auto-flush.
  3. Only commit/push when something is actually pending — no empty commits.
  4. Report one line: what was pushed (shas) or "nothing pending".
- **Caveats:** recurring `CronCreate` jobs auto-expire after 7 days; sessions are usually shorter, and each new session recreates it anyway. Not remote-durable by design — it is a within-session safety net, not infrastructure.

This complements (does not replace) the "commit early and often" rule above — the cron is the backstop that catches anything left uncommitted between manual pushes.

## Sutra submodule pin = RELEASE TAGS ONLY (Emma 2026-06-05)

**Decision:** Yantra's `external/Sutra` pin advances **only to Sutra release tags**, never to `main` HEAD. This is the stricter procurement posture the cross-repo workflow always allowed (see `external/` § "pin a specific tag, never `main`").

- **The daily auto-bump-to-main is retired.** `.github/workflows/sutra-submodule-bump.yml` (which tracked Sutra's default-branch HEAD) was **deleted 2026-06-05**. Do not reintroduce a HEAD-tracking bump; it contradicts this policy.
- **A 6am local cron owns the pin.** Each morning it checks out the latest Sutra **release tag** in the submodule, and if the pin moved, syncs the documented version refs (`paper/paper.md` "Sutra, pinned at vX.Y.Z"; the three `CLAUDE.md` version refs) and commits + pushes the bump. Session-local — recreate it each session (like the auto-flush above).
- **The auto-flush and submodule-sync crons must NOT move the pin** — they push Sutra-side *work* (don't lose commits) but leave `external/Sutra` pin advancement to the 6am release job.
- **When Yantra needs a Sutra change that isn't released yet:** cut a Sutra release (tag + `gh release`) per the cross-repo workflow, then the 6am job (or a manual bump) pins to it. A red Yantra CI after a release-pin means the release is missing something Yantra depends on — cut a new Sutra release, don't fall back to main-HEAD pinning.

## Project Description

Yantra is a neuro-symbolic, GPU-native operating system written in Sutra.
The OS is one big differentiable tensor-op graph: kernel, processes, IPC,
and GUI all live in the same tensor space. The CPU is a small orchestrator
that boots the system and shuffles inactive processes between GPU and RAM.

Target market is critical systems (defense, aerospace, industrial,
medical, autonomous) where predictable latency, formal verifiability, and
a small attack surface matter more than mass-market compatibility.

This repo holds **planning documents** plus a v0.0 kernel nucleus
under `kernel/` (a Python orchestration layer over real Sutra
compute). The Sutra compiler/runtime and the JS/TS transpiler live
in adjacent projects.

**Status (2026-06-16):** the public brand is moving to **Noldor
Technologies** (noldor.tech) and the OS/website framing is being
wound down (`yantraos.org` → noldor.tech). The kernel/OS prototype
here is **preserved/parked, not abandoned** — it may still be
continued; do not delete it. See `README.md` + `CONTENT_AUDIT.md`.

## Architecture and Conventions

- All design notes live in [`planning/`](planning/README.md), numbered for
  reading order. Treat them as planning, not specification — they reflect
  current best thinking, not committed APIs.
- New architectural decisions go into the relevant `planning/NN-*.md`
  file, with a one-line update in `planning/15-open-questions.md` if
  something there moved from open to resolved (or vice versa).
- Code lives under `kernel/` (the v0.0 multi-process runtime
  nucleus, native Sutra + a Python init/resource-manager shim). See
  `kernel/README.md` for what's real vs stubbed. Future code
  layout: `kernel/`, `runtime/`, `apps/` (native-Sutra
  userspace), `docs/`. The `external/` directory holds pinned
  submodules of Sutra and reference Linux source trees.

## Build/policy clarifications (kernel + transpilers)

### Build sequence (set 2026-05-14)

1. **Connectome Manager (kernel)** — see below. Python prototype
   under `kernel/` exists; production form is Rust.
2. **Command-line userspace utilities** — simple Linux-shaped file
   utilities (cat, ls, grep…) written natively in Sutra. Initial
   system access is **command-line only via SSH/serial** from a
   host computer. **No GUI in this phase.**
3. **Browser / GUI** — only after (1) and (2) ship. Single GUI
   framework (HTML5 + CSS + idiomatic TS + WebGL/Three.js, **no
   WASM**); every UI component (start menu, mouse cursor, login
   screen, file manager) is a browser-rendered HTML page.

### The kernel is a Connectome Manager (not a traditional kernel)

- The kernel's job is **deciding what is connected to what**, not
  scheduling or memory allocation in the traditional sense. The
  three storage tiers are **disc** (programs at rest), **RAM**
  (programs loaded but not running — semantically closer to disc
  than to traditional RAM), and **GPU** (programs in the live
  connectome). The kernel moves programs between tiers; it does
  not schedule or context-switch.
- **Kernel implementation.** The `kernel/` directory in this repo
  is the v0.0 Connectome Manager. **Sutra is doing the
  computation** — `SutraService` compiles `.su` source via the
  Sutra v0.7.1 compiler and runs `on_axon(vector) -> vector` on
  real torch tensors routed through the kernel. The
  **orchestration layer** (init/resource-manager + axon router +
  capability check) is in Python here; the production form on the
  CPU side is **Rust** per `planning/01-architecture.md` § "CPU
  side: small, Rust, orchestrator." When updating Yantra-side
  kernel code today, edit the Python and write `.su` files;
  treat the Python as the API-shape pin the eventual Rust
  reimplementation must match.
- **Kernel is native Sutra, not transpiled.** The verification
  surface in `paper/paper.md` § 4 depends on the trusted base
  reducing cleanly to a compiled tensor-op graph. Sutra services run on the
  GPU; the Rust orchestrator runs on the CPU, written natively in
  Rust.

### Transpilers

- **TS→Sutra is the only transpiler in scope, and it is
  browser/GUI-scoped.** Outside the browser layer, TS→Sutra is not
  used. **Shipped as Sutra v0.3.2** (released 2026-05-14): CLI
  works, 17 fixtures pass, `pip install sutra-dev[ts]` bundles it.
  Coverage caveat: typed core works, but TS-completeness is not a
  solved problem — real-world bundles may need new lowering rules.
  Foundation, not finished feature.
- **C→Sutra transpiler is NOT planned** (decision 2026-05-23).
  Sutra is a systems language for a GPU-native architecture; Yantra
  is not copying the Linux kernel or C apps. Userspace is written
  natively in Sutra; the bootloader and orchestrator are written
  natively in Rust. C→Sutra may be revisited someday but is not on
  any roadmap and must not be presented as planned work.
- **WASM target deferred** — eventually in scope but not now and not
  for a long time (its linear-memory/threading model is alien to
  Sutra's substrate; the v0 GUI is JS/TS only; not a v0 or v0.1
  target). See `planning/07-transpilers.md` and
  `planning/06-gui-stack.md`.

### Userspace utilities (cat, ls, grep, awk, sed, sort, etc.)

Written **natively in Sutra**. The Linux source trees under
`external/` are behavioural reference for native rewrites, not
transpile inputs. Deferred until the Sutra-side string + IO + FS
vocabulary matures and the kernel `.su` loader lands. Q-list is in
`todo.md` § 2.

## Project context for paper/agent work

- **Meta's *Neural Computers* paper IS real.** Schmidhuber et al.,
  *Neural Computers*, arXiv:2604.06425, 76 pp., 2026. AI reviewers
  flag the 2026 date as a hallucinated future citation — it is not,
  this is May 2026 and the paper is a real recent pre-print. Do not
  remove or qualify the citation; if a reviewer rejects on this basis,
  push back in the next revision with a parenthetical that the paper
  exists. Yantra's position is that *Neural Computers* validates the
  design space but its video-diffusion approach takes the opposite
  engineering posture from Yantra — useful as inspiration and
  competitive awareness, not as a foundation Yantra rides on.
- **Two core dependencies Yantra rides on, both Sutra-side:**
  1. **Sutra** — the typed functional language with rotation-binding +
     polynomial Kleene logic + tail-recursive RNN-cell loops. Pinned
     in this repo at `external/Sutra` (submodule, currently v0.7.1).
     Language website: [sutra.emmaleonhart.com](https://sutra.emmaleonhart.com). The
     Sutra paper at `external/Sutra/paper/paper.md` is the canonical
     reference for empirical claims Yantra makes (100% bundle
     decoding through width k=8 across four substrates, ~1.5×10⁻¹⁵
     round-trip error, 4→95% end-to-end-differentiable training in
     50 epochs on a 19-AND fuzzy rule tree). When Yantra makes a
     claim that depends on Sutra empirics, cite the Sutra paper
     explicitly rather than hand-waving.
  2. **TypeScript → Sutra transpiler** — the lowering engine
     (`external/Sutra/sdk/sutra-from-ts/sutra_from_ts/lower.py`) is
     ~1474 lines of real code with 17 passing fixtures covering
     functions, classes, async/await, discriminated unions, etc. The
     CLI wrapper (`__main__.py`) is *not* yet wired up to the
     lowering pass and the README still says "skeleton" — that README
     is out of date relative to the actual code. **When discussing
     the TS transpiler, say "the lowering engine works; the CLI is
     unwired" rather than "it's a skeleton" or "it's done." Both
     extremes are wrong.** Essential for the browser GUI layer
     because "everything is a browser" only works if real JS/TS
     bundles can be AOT-compiled to Sutra without a human rewrite.
- **The memory model is the long-term hard problem.** Process memory,
  the CPU-side RAM cold-store, MMIO patterns, and the boundary where
  axon-typed compute meets byte-typed hardware do not yet have a
  worked-out design. `planning/17-memory-model.md` exists to keep
  the open questions in one place. Do not promise solutions in the
  paper that the planning corpus does not yet have.
- **Kernel + browser readiness lives in `planning/18-kernel-browser-
  readiness.md`** — accurate engineering accounting, not paper-tone.
  Read this before claiming the OS is or isn't writable; refresh it
  when the situation changes.

## Cross-repo workflow (Yantra ↔ Sutra)

**This is atypical, but it's the right shape for these two projects
because they are tightly coupled.** Yantra and Sutra are not really
independent codebases — Yantra is "the OS that uses Sutra"; Sutra is
"the language Yantra is built in." A change to one frequently
requires a change to the other in the same session.

### Division of responsibility

- **Yantra (this repo) — actual kernel orchestration, runtime
  shape, OS-level concerns.** What goes in `kernel/`, the
  Connectome Manager design, the eventual Rust orchestrator,
  storage-tier moves, capability check architecture, the FS
  bridge, the GUI/browser stack, the paper.
- **Sutra (`external/Sutra` submodule) — connecting things
  together at the language level, debugging the language,
  language-side primitives Yantra needs.** What goes in
  `sdk/sutra-compiler/`, `sdk/sutra-from-ts/`, the compiler,
  the lowering passes, the
  axon spec, the multi-process runtime, the
  serialise-process-state primitive, the runtime ABI Yantra
  consumes.

When working in this repo and a Sutra-side change is needed, do
**not** treat that as someone else's problem. The submodule is a
real git checkout you have push access to. Edit it, commit on
Sutra `main`, push, and tag a release if Yantra needs to depend on
it. **Pin advancement is owned by the 6am release-pin cron** — see
§ "Sutra submodule pin = RELEASE TAGS ONLY"; don't bump the pin
by hand mid-session.

### The mechanics

```bash
# 1. Move into the submodule, get on main (Sutra's default branch —
#    master is FROZEN at v0.4.1; do NOT use it).
cd external/Sutra
git checkout main
git pull origin main --ff-only

# 2. Edit Sutra-side files. (The Sutra repo has its own CLAUDE.md
#    with its own workflow rules — read it first; in particular,
#    Sutra requires plan-into-queue.md and commit + push immediately
#    rather than batching local commits.)

# 3. Commit + push on Sutra main (rebase if rejected; never force-push).
git add ...
git commit -m "..."
git push origin main

# 4. (If Yantra must depend on this change) tag a release.
git tag -a vX.Y.Z -m "..."
git push origin vX.Y.Z
gh release create vX.Y.Z --repo EmmaLeonhart/Sutra ...

# 5. The 6am release-pin cron moves external/Sutra to the latest
#    release TAG and pushes the bump. For a manual bump:
#    git -C external/Sutra checkout vX.Y.Z
#    git add external/Sutra && git commit -m "Bump Sutra pin to vX.Y.Z — <why>"
#    git push origin main   # (Yantra's default branch is main)
```

### When NOT to do this

- Don't make a Sutra-side change just because Yantra-side code is
  awkward. Sutra has its own audience (the language's users beyond
  Yantra) and its own NeurIPS-paper code-durability constraint.
  If a Yantra workaround is possible, prefer it.
- Don't tag a Sutra release for a docs-only fix unless something
  in Yantra needs to depend on a specific Sutra version that
  carries the doc. A submodule pointer bump to master HEAD is
  enough for non-release-shaped changes.
- Don't edit anything under `external/Sutra/paper/neurips/` —
  that's Sutra's frozen NeurIPS submission archive (per Sutra's
  CLAUDE.md). If a Yantra change makes the Sutra paper claims look
  shaky, surface that to the user, don't silently amend the frozen
  copy.

### Read the Sutra CLAUDE.md before editing the submodule

`external/Sutra/CLAUDE.md` has rules that are stricter than
Yantra's in places — notably, Sutra is biomedical-hardware-adjacent
("PEOPLE CAN DIE IF YOU FAKE RESULTS") with hard rules about
substrate purity (no Python shortcuts inside Sutra operations, no
numpy on the runtime hot path, every operation runs on the
substrate). When editing Sutra source, those rules bind. When
editing Sutra docs / pyproject / CLI scaffolding, they don't, but
the workflow rules (commit + push immediately, plan into Sutra's
own queue.md, mirror to task tool) still apply.

## Accuracy rules (added 2026-05-14)

Two rules added after the user pointed out the docs were papering
over difficulty:

### Python is dev tooling, not runtime

- **No Python in the boot path.** The bootloader is Rust (or C);
  there is no interpreter at boot. See
  `planning/19-boot-sequence.md` § "Stage 3" for the long version.
  A Python "bootloader" is a category error — there is nothing for
  the interpreter to run on.
- **No Python features in `kernel/` that wouldn't port cleanly to
  Rust.** The Python in `kernel/` is the behavioural reference for
  the eventual Rust orchestrator. Decorators that do nontrivial
  work, `__getattr__` magic, dynamic monkey-patching, runtime
  type-juggling (e.g. `isinstance` switches that change behaviour),
  metaclass tricks — none of these belong in `kernel/`. If the
  Python is doing something the Rust port can't naturally do, the
  Python is wrong.
- **The Rust port is the production target.** Treat the Python as
  load-bearing for tests, not for runtime. When in doubt, ask:
  "would this compile to a clean Rust translation?" If the answer
  is "you'd have to redesign," don't add it.

### Don't paper over difficulty

When something is hard or unbuilt, name it. Specific things that
are hard, that are not yet built, and that should be called out
plainly when they come up rather than waved past:

- **The bootloader.** An early version **exists and boots in QEMU**
  (`bootloader/`, v0.4 — multiboot1 boot, PCI scan, GPU-framebuffer
  write, kernel-image handoff, 32→64-bit long-mode transition; plus a
  bare-metal Linux 0.00 replica). It is a **boot demo, not the
  production boot path**: the handoff target is a stub and real
  Sutra-on-GPU execution is gated on GPU passthrough (VFIO + a spare
  GPU) the QEMU dev tier lacks. Still ahead, and Rust target: firmware
  (BIOS/UEFI) handoff, real bare-metal CPU+GPU init, and loading the
  compiled Sutra image into actual GPU memory. Don't say "the
  bootloader doesn't exist" — say what the demo does and where the
  production boot path stops.
- **The Rust orchestrator.** Doesn't exist. The Python in
  `kernel/` is a behavioural reference for what its API surface
  should look like, not a "smaller version" of it.
- **Lazy axon evaluation.** Without it, the connectome bandwidth
  is O(N²·D) and collapses under its own weight. See
  `planning/20-lazy-axon-evaluation.md`. The kernel/router.py in
  this repo implements the skip-uninterested-receivers slice of
  this; full per-receiver projection is upstream-Sutra-dependent.
- **The multi-threaded Sutra runtime.** Upstream Sutra-side work,
  not shipped yet. Without it, the orchestrator can't actually
  run all admitted programs simultaneously on a single GPU.
- **Disc ↔ RAM ↔ GPU storage-tier moves.** The Connectome
  Manager's primary job. Not implemented. Blocked on Sutra-side
  primitives (serialise-process-state, evict-from-GPU) that
  don't yet exist.
- **GPU memory carve-outs per process.** Bookkeeping only in the
  Python prototype. Real per-process arenas need the multi-process
  Sutra runtime.
- **Boot-time hardware discovery (PCI scan, GPU init, MMIO
  setup).** Bootloader-stage work. PCI enumeration and GPU-framebuffer
  init exist in the QEMU bootloader demo above; MMIO/interrupt setup
  against real target hardware does not.

When writing docs, code comments, commit messages, or paper text,
if you find yourself reaching for "the prototype demonstrates the
shape" or "we'll figure that out later" or "this is a v0
limitation," **first check whether the underlying difficulty is on
the list above and name it explicitly**. The user has called this
out twice; do not let the docs drift back to softer framing.

## Substrate purity — no host shortcuts

Yantra's claim is that computation happens on the Sutra substrate. A host-Python
result in a substrate costume is a lie about what executed — the same rule Sutra
enforces (`external/Sutra/CLAUDE.md` § NO MATH SHORTCUTS).

- **Host code is orchestration + monitoring only — never the returned value.**
  Parsing, I/O, admission live on the CPU side. But a service's returned value must
  be what the *substrate* computed, not a host re-computation. (The 2026-05-24 calc
  bug: it computed on the substrate, discarded that, and returned a host `Fraction`
  — using the substrate only as a gate. Return the substrate's decoded value. See
  `planning/23-calc-substrate-purity.md`.)
- **Operation *selection* is computation — run it on the substrate.** Don't let host
  Python pick which op runs (`OPS[op]` choosing a `.su`). The operator is data;
  dispatch on it in Sutra via a **defuzzified switch** — compute every branch, build
  a one-hot selector from the operator (`is_true`/`select`), sum `branch·selector`
  so unselected branches are ×0.
- **No host oracle deciding the output.** Don't compute the "true" answer on the
  host and gate or replace the substrate output with it. Host-oracle verification is
  allowed as a *test/audit*, never as the runtime value.
- **Parsing belongs on the substrate too.** Sutra has the string ops (codepoint
  `String`/`Character` model); host string-parsing is a shortcut to retire, not a
  permanent boundary. Host stays I/O only (read the line, print the result).

### The fake-substrate-work threat (real, recurring — guard against it)

**This is a real threat that has already occurred, not a hypothetical.** An agent
(or a person) can produce work that *looks like* the spec but is fake underneath —
the computation claimed to run on the substrate is actually done by the host.

**Documented instance (2026-05-24):** the calculator (`apps/calc/`) presented as
"math runs on the Sutra substrate, exact through the kernel," but host Python picked
which operation ran **and** returned a host-`Fraction` answer, using the substrate
only as a pass/refuse gate. It passed its tests and read as real — it was not. Full
write-up: `planning/23-calc-substrate-purity.md`.

**How it happens:** the implementer doesn't 100% understand the substrate mechanism,
so they write code that *resembles* the instruction and lean on the host for the
parts they can't express. The result looks correct and is **worse than nothing** —
it hides the gap and burns trust.

**Guard against it:**
- **Do not implement what you do not 100% understand.** If you cannot build the real
  substrate version, do **not** ship a host-faked stand-in. Stop and ask, or write a
  spec/plan in `planning/` and queue the real work. (That is exactly what
  `planning/23` is — design + queue, not a rushed half-implementation.)
- **The returned value must be decoded from the substrate** (see § Substrate purity).
- **Every decision that affects the result — including *which* operation — is a
  substrate op, not a host `if`.**
- **When reviewing "it works," check *what actually executed*,** not just that a
  number came out right. A passing test against a host oracle proves the *host* is
  right, not the substrate.
- **Don't barrel into code surgery in another repo unbidden.** Add the design + queue;
  let the owner (or a deliberate session) execute. Plausible-looking speed is the trap.

## When Emma gives an algorithmic explanation, implement it

Emma knows Sutra — and the substrate mechanisms Yantra rides on — far better
than an agent does. Recurring, costly failure: she gives a concrete algorithm,
the agent decides it "can't work," substitutes its own variant, the variant
fails, and the idea gets reported as blocked — when **her original idea was
right**. Implement the thing she actually described *first*, run it, read the
output. "I think that can't work" is a hypothesis to test on the substrate, not
a conclusion. If it seems not to compose, the gap is usually a primitive to
expose, not a wrong idea. (2026-05-24: "defuzzify `select` enough so the
branches don't blend" → **18/18 bit-exact** once actually built, after a
session lost to agent-invented detours; full write-up + the Sutra-side rule in
`external/Sutra/CLAUDE.md` § "When Emma gives an algorithmic explanation.")

## External dependencies (`external/`)

Submodules pinned at known-good releases. Layout:

- `external/Sutra` (tag `v0.7.1`) — the language, compiler, runtime,
  and Sutra paper Yantra depends on. Website: <https://sutra.emmaleonhart.com>
  (canonical, built from `external/Sutra/docs/`).
The Linux userspace submodules (`coreutils`, `util-linux`,
`busybox`) were **removed 2026-05-23** along with the C→Sutra
transpilation path they were imported for. GNU behaviour remains the
conceptual reference for native-Sutra utility rewrites, but no Linux
source is vendored. `external/` now holds only `external/Sutra`.

To add a new external dependency: pin a specific tag, never `main`.
A floating dependency on master is a procurement-security
non-starter for the markets Yantra targets.

## Paper revision discipline

- The paper at `paper/paper.md` auto-submits to clawRxiv on push (see
  `paper/README.md`). Each revision should land *one* coherent set of
  changes, not a kitchen sink — reviewers see version diffs and
  oscillating scope hurts.
- When addressing a review, name the specific con being addressed in
  the commit message. Don't claim a con is "addressed" if the change
  is cosmetic; reviewers will catch this.
- Sutra-empirics claims must cite the Sutra paper. Don't paraphrase
  numbers — quote them with their context (substrate, width, etc.).
- Scope limits beat overclaim every time. If a hardware reality
  (interrupts, MMIO, side channels) is not solved, say so in the paper
  rather than letting a reviewer find the gap.

## Formal verification — keep the FV paper in sync as we work

Formal verification is an active, ongoing strand (early stages: the
framework + first paper, not mechanized proofs yet). **As we do FV
work, update the formal-verification paper alongside it** — the paper is
a live artifact that tracks the work, not a one-off writeup. Canonical
locations (Sutra-side, so edits go on the `yantra-driven` branch per the
cross-repo workflow, and the paper auto-submits to clawRxiv via
`fv-paper-ci.yml`):

- **Paper:** `external/Sutra/paper/formal-verification/paper.md`
  (clawRxiv post 2613). When an FV obligation is discharged, a primitive
  lands, or a claim's scope changes, reflect it in the paper in the same
  session — and cite only measured numbers, mirror the §"What we are not
  claiming" discipline.
- **Rules/spec:** `external/Sutra/planning/sutra-spec/formal-verification.md`
  is the ground truth the paper must not contradict.
- **Agenda:** the FV work items live in Sutra's `todo.md` + `queue.md`;
  keep them current as items move.

The discipline above (one coherent change per revision, name the con,
cite the Sutra paper, scope-limit over overclaim) applies to the FV
paper too.

## Cron + task requests: schedule the cron immediately, do the task now

When Emma asks for a cron job at a given time AND a separate independent task in the same message: set up the cron IMMEDIATELY and do NOT ask questions about it or try to work out what it will do — the firing session figures that out when the time hits. The other task is genuinely urgent and must be done right away. This is a common, always-intentional request from Emma; spending time figuring out the cron's intent actively harms the urgent task. Just schedule the cron with whatever (even terse) description she gave, then go straight to the urgent task.
