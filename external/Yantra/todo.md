# Yantra — longer-horizon TODOs

> **What this file is.** Forward work that doesn't fit in the
> current `queue.md` (which is strictly "what's being done right
> now"). Items here can sit for weeks. They migrate to `queue.md`
> when picked up; cleared from `queue.md` when done.
>
> **What this file is not.** A roadmap commitment. Order is
> heuristic; the user picks what to start.

---


## stuff Emma is saying to do

(claude.md de-staled 2026-06-16: cross-repo master→main, stale hardcoded date
removed, pin-ownership reconciled, rebrand/preserve status noted. OPTIONAL
deeper de-bloat — move long rationale into planning/ and keep CLAUDE.md terse —
left undone: it touches load-bearing rules, wants Emma's OK before cutting.)

barrel through all of the blocked things below

(queue.md crud fixup — done 2026-05-27, 250→63 lines, shipped narrative moved to git log; see DEVLOG)

## ⛔ Blocked / not-autonomous — surfaced 2026-05-24 (Emma asked these be pinned at the top)

These are the queue items that were **deliberately NOT done autonomously**
during the 2026-05-24 scheduled drain — each is a genuine blocker, a
product decision, or substrate surgery that wants Emma's direct guidance.
Named plainly per the hard rails (don't paper over difficulty; when Emma
gives an algorithmic explanation, implement *hers*). Stage-2 terminal
surface (the one cleanly-actionable item) shipped; everything below did
not, for the stated reason.

1. **CLI utilities beyond echo (`cat`, `ls`, `wc`)** — *blocked on
   Sutra-side string + IO + FS vocabulary.* Not a Yantra-side fix; `echo`
   works only because it's a pure axon round-trip. Promote per § 2 below
   as each unblocks. (headline-demo step 1)

2. **calc step c — return a substrate-decoded value, not a host `Fraction`**
   — **DONE 2026-05-25 (Emma's product decision).** Instead of dropping the
   refuse-gate to return a raw float, the result is decomposed into its
   1000s/100s/10s/1s digits ON THE SUBSTRATE (`apps/calc/digits.su`:
   Fourier-series eigenrotation modulus + integer division, `digit =
   round(mod(floor(n/place)+0.5,10)-0.5)`; the +0.5 offset dodges the
   branch-cut at multiples) and returned as a STRING via
   `Calculator.result_string`. The digits are decoded from the substrate, host
   only joins them. 4-digit demo scope (0..9999); `tests/test_calc_digits.py`
   (4 tests, measured exact over all digit-boundary cases). The internal
   `evaluate` still composes exact `Fraction`s + the monitoring oracle. See
   `planning/23` step c.

3. **calc step d remaining — full substrate parse** — *substrate `.su`
   surgery; do WITH Emma.* Shipped on the substrate: `parse_int2.su` (1–2
   digit integer); `parse_op.su` (operator-char → op-code, standalone
   demonstrator of the codepoint-scoring technique); and **operator-from-
   char dispatch wired into the live calc (8d8b2d3, 2026-05-24)** —
   `switch.su` now reads the operator as a 1-char string axon item,
   takes its codepoint with `string_char_at`, and scores 43/45/42/47
   directly, so the host `CODE[op]` map is gone (57/57 calc + full kernel
   gate green). Remaining: variable-length >2-digit parse (Sutra
   accumulator loop / digit array), two-operand "DD OP DD" split (find
   space/operator positions on the substrate), then compose parse_int2 +
   the wired char-dispatch into `calc.py` replacing the host recursive-
   descent parser. This is exactly the kind of substrate-loop mechanism
   where Emma's guidance beats an agent guess — not barreled into
   autonomously. See `planning/23` Stage-1.

4. **calc step e — arbitrary precision (digit-array)** — *open; needs
   carry propagation ON the substrate (not host) to stay pure.* float64
   already extended exact integers to 2⁵³; true unbounded exactness is the
   harder follow-on. Not a quick win.

5. **Headline-demo contrast figure** — *needs a generative BASELINE.* The
   Yantra side is pinned (zero drift, incl. N=60 through the terminal); the
   decaying right side needs a CLIGen-shaped DiT-frame model reproduced or
   Meta's published degradation numbers cited. Will NOT fabricate numbers.
   See `planning/22` § "Making it measurable". (headline-demo step 3)

6. **GUI open issues** (`planning/24-first-gui.md`):
   - **Live window + click verification** — *needs a human at the screen*;
     the substrate parts (field, flip, tint) are tested, the window/click
     are not headless-testable.
   - **Per-pixel render batching** — *blocked on a Sutra-side change*:
     `make_real` is scalar-only, so the compiled `pixel` graph can't take a
     batch dim. Not a clean Yantra-side fix (Sutra-side / deliberate
     session).
   - **Reverse-CNN decoder** (Emma's "return a vector → reorganise into
     pixels") — *unbuilt; the bigger next GUI step.*

7. **`axon_project` no-op across the connectome** — *narrowed blocker for a
   future Sutra+kernel design session.* Intra-module slice shipped
   (Sutra v0.4.1); the cross-separately-compiled-program case needs
   whole-connectome compilation or admission-time producer specialization.
   See `planning/20` § Status and § 1 below.

---

## ▶ Continuation — start here (autonomous hourly loop)

**An autonomous hourly cron drives this repo** (a sibling machine
pushes Sutra + site work concurrently). Every cycle: `git fetch` →
FF/rebase Yantra (never force-push / reset --hard / discard the
other machine's work) → bump `external/Sutra` **to its latest
release tag** → commit+push → then work `queue.md`, and when it
has no actionable Yantra item, promote the next
**genuinely-unblocked, bounded, verifiable** `todo.md` item (plan
into `queue.md` first).

> **⚠️ Submodule-tracking correction (2026-05-17).** The old text
> here (and Yantra CLAUDE.md § "Cross-repo workflow") said bump to
> `origin/master`. **Sutra migrated its default branch master→main
> (CI + Pages migrated; `master` is now FROZEN at `v0.4.1`).**
> Following the stale `master` instruction silently missed 36
> Sutra commits + the `v0.5.0` tag for a whole session. **Pin
> against Sutra release *tags*** (the External-dependencies rule
> already says "pin a specific tag, never a branch"): check the
> latest tag with `git -C external/Sutra fetch --tags && git -C
> external/Sutra tag --sort=-creatordate | head`, verify the
> Yantra kernel regression is green at it, then pin. CLAUDE.md
> § "Cross-repo workflow" still says `git checkout master` — that
> is stale; treat "master" there as "the latest release tag on
> Sutra's real default branch (`main`)" until the user updates it.

**Where the live state is** (don't re-derive it — read these):
- `queue.md` — the active item + the standing **Sutra-side
  `axon_project` blocker** (it's a no-op for embedding fillers;
  real fix is producer-side pruning — a Sutra design decision,
  deliberately not forced/faked from here).
- `planning/20-lazy-axon-evaluation.md` § Status — the measured
  lazy-eval reality.
- `planning/18-kernel-browser-readiness.md` — accurate engineering
  accounting (refreshed; keep it accurate as reality moves).
- `external/Sutra/planning/findings/2026-05-15-*` — the
  transcendental-leak and axon-key-coercion root-cause records.
- `git log` — the narrative; each commit message says *why*.

**Hard rails (these are why the loop is trusted):** never fake,
never weaken/skip a test to make it pass, never claim
"works"/"verified"/"substrate-pure" without having run it and
measured. A real defect → strict `xfail` or a precise documented
blocker, never a loosened assertion. Correct stale/false docs the
moment you find them (this loop has de-lied several already). Name
unbuilt/hard things plainly ("Don't paper over difficulty").

**What's genuinely unblocked vs not** (refreshed 2026-05-17):
DISC↔GPU load/unload is now DONE (real RTX 4070; `evict-from-GPU`
turned out to be buildable, not an unbuilt primitive — it's
`_VSA` device-tensor release). Still blocked: the RAM cold-store
of *running* state (genuinely needs Sutra
`serialise-process-state`), real per-process GPU arenas + GPU-tick
parallelism (need the multi-process Sutra runtime), the large Rust
orchestrator port (no tight spec), and bare-metal-boot-to-GPU
(needs Linux host + VFIO + spare GPU — the RTX 4070 is the host's,
fine for running the kernel on it directly, not for VM
passthrough). The browser (§3)
is build-sequence-gated (milestone 3, after kernel + CLI
utilities) — do not jump it. The high-yield unblocked work has
been: cross-repo regression root-causes+fixes, and accurate
engineering-accounting / doc-truth passes. Pick in that spirit.

---

## 1. Kernel — Connectome Manager, beyond the Python v0.0 prototype

The `kernel/` directory ships a working **Python prototype** of the
Connectome Manager (manifest + router + init + two example services
+ 19 passing tests). The Python is a behavioural harness; the
production form is Rust. Hardening list:

- **Bootloader (Rust) — v0.4 shipped + verified in QEMU 11.0.50 (2026-05-14).** The first Yantra-authored code that runs at boot. Lives at `bootloader/`. End-to-end demonstrated: multiboot1 entry, PCI bus enumeration, GPU framebuffer pixel writes, kernel-image placeholder copy to GPU memory, stub orchestrator handoff, long-mode transition with 64-bit "Long mode active" print. **v0.2 (real Rust in long mode) attempted and blocked**: QEMU's `-kernel` refuses 64-bit ELFs; multiboot2 needs GRUB to boot. Two unblock paths: GRUB ISO build, or two-crate i686-boot-stub + x86_64-payload workspace. **v0.5+ (real Sutra kernel execution) gated on actual GPU passthrough**: VFIO on a Linux host with a spare GPU. QEMU's emulated stdvga can't run CUDA, so Sutra-on-virtualized-GPU isn't possible at the QEMU dev tier.
- **Rust port of the Connectome Manager (orchestrator).** The
  production form on the CPU side, runs after boot. "As small as
  possible" with strong static guarantees; the Python prototype
  is the API reference. Single largest piece of post-bootloader
  work in this list, and the one that turns `kernel/` from
  "behavioural harness" into "runtime."
- **Lazy axon evaluation in the production router.** Kernel-level
  slice (skip uninterested receivers) works. Per-receiver
  projection is wired (`register_projector` → `_VSA.axon_project`)
  but the 2026-05-15 end-to-end semantic test
  (`test_projected_payload_still_decodes_semantically`, strict
  xfail) **proves it is a no-op for embedding fillers**:
  `axon_project(bundle,[k]) = bind(k,unbind(k,bundle))` is identity
  for orthogonal rotation binding on semantic-block fillers, so the
  "slimmed" payload still holographically contains every key
  (dropped key decoded +0.5726 vs kept +0.5999). **No bandwidth
  reduction and no capability isolation for the common case** —
  bears on `paper/paper.md` § 3.3.1. The real fix is producer-side
  pruning (rebuild the bundle without the unwanted `axon_add`
  terms, whole-program analysis per Sutra `axons.md` §"Lazy
  evaluation across boundaries") — a **Sutra-side design
  decision**, not a Yantra-side wiring task. See
  `planning/20-lazy-axon-evaluation.md` § Status and `queue.md`.
  **NARROWED 2026-05-17:** the *intra-module* slice of producer-
  side pruning shipped (Sutra v0.4.1 — cross-function read-demand
  propagation; submodule pinned). What remains is **only** the
  cross-separately-compiled-program (connectome) case: producer +
  consumer are independent `.su` modules wired at admission, which
  a single-module compiler structurally cannot bridge. The fix is
  whole-connectome compilation or admission-time producer
  specialization (a Sutra+kernel design item, not the no-op
  `axon_project`). The strict-`xfail` test stays accurate for the
  connectome case. Full reasoning: `planning/20` § "Status
  (2026-05-17)".
- **Storage-tier moves: disc ↔ RAM ↔ GPU — DISC↔GPU DONE
  2026-05-17; RAM cold-store reframed 2026-05-25.** The DISC↔GPU slice ships:
  `Init.load`/`unload` instantiate / tear down a program's CUDA-resident
  Sutra runtime with the GPU memory genuinely reclaimed (real RTX 4070,
  measured 669696→0→669696 B; `tests/test_kernel_gpu_tiers.py`). The old
  "only admit/deregister against an in-memory pool" + the §44-46 "blocked
  on … evict-from-GPU" are stale: `evict-from-GPU` is now real (proactive
  `_VSA` device-tensor release). **The RAM cold-store framing
  ("genuinely needs Sutra `serialise-process-state`") was wrong** — see
  `planning/26-orchestrator-serialisation.md` § "(b) … finding 2026-05-25".
  Current Sutra is purely functional (`planning/sutra-spec/concurrency.md`:
  *"No shared mutable state"*), training is a hand-reimplemented PyTorch
  proxy (not compiled `.su`; 2026-05-18 Sutra finding), and VSA caches
  are deterministic from key strings — so there is **no per-program
  mutable substrate state to capture**. The real RAM cold-store gap is
  (c) orchestrator-level state: admission table + tier map + router
  inboxes. Pure Yantra-side work, no Sutra primitive needed.
  `kernel/checkpoint.py` (`serialise_kernel_state` /
  `restore_kernel_state`) SHIPPED 2026-05-25 + verified bit-exact
  through a real echo round-trip (`tests/test_kernel_checkpoint.py`,
  9 tests; full gate 197 passed/1-xfail on the RTX 4070, after the
  2026-05-25 restore-device-faithfulness fix — restore now places each
  process's inbox on its own service's device, not a hard-coded CPU; the
  CPU-only sibling machine didn't surface the GPU device mismatch).
  Per-process cold-store API + a runtime `Tier.RAM` enum value —
  **SHIPPED 2026-05-25.** `Tier.RAM`, `Init.cold_store(name) -> bytes`,
  and `Init.restore_from_cold(name, blob)` are live (per-process `YPRC`
  blob via `kernel.checkpoint.serialise_process` / `parse_process`),
  bit-exact + behaviour-identical through real echo
  (`tests/test_kernel_ram_tier.py`, 10 tests). Whole-kernel checkpoint
  refuses a RAM member (its inbox lives in the external cold blob). See
  `planning/26` § 3. Remaining refinement: pool-budget accounting on
  tier moves (left untouched, matching `unload`; v0.0 bookkeeping-only).
  - **Emma's direction (2026-05-24): the orchestrator does the
    serialisation, in two distinct kinds — start with the easy one.**
    (a) **Serialise an axon's output — SHIPPED 2026-05-25.** Payload tensor
    bit-exact via `kernel/serialise.py` (`serialise_axon_payload` /
    `deserialise_axon_payload`, Rust-portable 12-byte header + raw little-
    endian body). Foundation extended 2026-05-25 with the full router
    envelope (`serialise_axon` / `deserialise_axon`: role, payload,
    from_proc, keys). Verified across every supported dtype and through
    the calc's real VSA (`tests/test_axon_serialise.py`, 20 passed + 1
    CUDA-gated skip). Format spec: `planning/26-orchestrator-serialisation.md`.
    (b) **Serialise the full process state — finding 2026-05-25.** The
    original framing ("VRAM holding the program's weights + in-flight
    memory") expected mutable per-program substrate state Sutra does not
    currently have: spec says *"No shared mutable state"*; training is a
    hand-reimplemented PyTorch proxy, not compiled `.su`; VSA caches are
    deterministic from keys; loop carriers don't survive across calls.
    So **(b) reduces to (a) for current Sutra**. The substantive next
    piece is (c) below; a Sutra-side `program_state_bytes()` accessor
    would be a no-op today and is deferred until a real consumer (e.g.
    trained `.su` programs) exists. **Rust preferred** for the
    orchestrator note below.
- **Real per-process GPU memory arenas.** v0.0's `compute_units`
  is bookkeeping only. Production needs the multi-process Sutra
  runtime (being implemented in the Sutra repo upstream) to carve
  out actual device memory per admitted process, with admission-
  time refusal that corresponds to actual hardware capacity rather
  than an integer counter.
- **GPU-tick-parallel scheduling.** v0.0 ticks services
  sequentially on CPU. Production runs every admitted process
  simultaneously on the GPU at each tick. Drop-in once the Sutra
  multi-process runtime lands upstream; the service abstraction is
  concurrency-agnostic.
- **`.su` service loading — WORKS (corrected 2026-05-16).** This
  bullet previously claimed `kernel.services.load_su_service()`
  "is currently `NotImplementedError`" and needs "an upstream
  Sutra decision." Both false: `load_su_service` is defined
  nowhere (measured — absent on `kernel` and `kernel.services`),
  and `.su` services load + run via `SutraService(source_path=…,
  output_role=…)` — it compiles the `.su`, invokes
  `on_axon(vector)->vector`, and consumes the compiled module's
  `AXON_KEYS_BOUND`/`AXON_KEYS_READ` static analysis. That export
  convention is the "Sutra-side decision" the old text waited on;
  it shipped and is exercised by many passing
  `tests/test_kernel_sutra.py` tests (incl. real echo/sink `.su`
  services). No `load_su_service` wrapper is needed —
  `SutraService(...)` already is the one-liner. What genuinely
  remains here is the *Rust* orchestrator's own `.su` loader (the
  Python `SutraService` is the API reference), not a missing
  Python stub.
- **Rust orchestrator — built incrementally; NOT "blocked, no spec"
  (Emma's direction 2026-05-24).** The vision: a Python orchestrator
  *now*, switching to a **Rust** orchestrator as time allows. Rust is the
  target because the orchestrator manages GPU memory/processes and Rust
  gives more granular access + far more potential to run on bare metal —
  it's the OS-grade piece. The "blocked: no tight spec" framing was wrong;
  **the spec direction is: write many small Rust programs that each do one
  small task, then merge them into the orchestrator over time.** This is
  itself bare-metal-friendly (small freestanding Rust units compose toward
  a no-std image). **This build strategy is now written into
  `planning/01-architecture.md` § "CPU side: small, Rust, orchestrator"
  (the standing plan).** Grow `bootloader/` (already real Rust) along the
  same lines. The Python `kernel/` stays the behavioural API reference each
  Rust unit must match.
- **Rotation-operator-based capability check.** v0.0 trusts the
  sender's name (admission grants identity; capability is checked
  by name). Production's threat model (`paper/paper.md` § 3.3.1)
  is operator-based: possession of `R_role` is the capability.
  Lands when the `.su` loader does.
- **CPU-side hardware shim** for the interrupt + MMIO + tick
  pattern in `paper/paper.md` § 3.5. Blocked on having target
  hardware. The shim itself is in the Rust orchestrator's scope.
- **Bootloader.** A small program that loads the compiled kernel
  image onto the GPU and starts it executing. Written **natively in
  Rust** (see `bootloader/`), the same systems language as the
  orchestrator — not a C→Sutra transpile target (that transpiler is
  not planned).
- **Bare-metal via a VM — write-up DONE 2026-05-25.** Emma asked
  2026-05-24 *can a VM run on bare metal and simulate a GPU even without a
  real one?* The answer is documented in
  `planning/19-boot-sequence.md` § "Running Yantra inside a VM (no real
  GPU)": the boot/orchestration path is VM-testable on any host (QEMU
  already exercises it); the substrate is CPU-runnable in any VM
  (`device='cpu'`); CUDA compute in a VM needs either VFIO passthrough on
  a Linux host with a spare GPU, or vGPU on supported datacenter silicon.
  virtio-gpu Venus, NVIDIA vGPU, and CUDA-API-forwarding shims (rCUDA,
  GVirtuS) are noted as research paths that would change the answer if
  any matured. **Remaining as a deeper investigation:** characterising
  whether any of those paravirt paths has become practical enough for
  a developer-machine setup since they were last surveyed — left as a
  future-session task, not a near-term blocker.

## ~~Investigate: bundle-decoding regression~~ — RESOLVED 2026-05-15

Root-caused and fixed in Sutra `eb0ce93e`. It was NOT a numerical /
bind-chain regression and did NOT degrade the VSA-capacity story:
the Sutra compiler coerced `axon_item`'s string-literal key to a
`make_string` codepoint vector (because the stdlib signature types
the param `string`) while the producer's member-access path kept it
a host str → producer/consumer keyed on different role vectors →
cross-module decode corruption. Surgical codegen fix; `_run.py` now
PASS at the exact README numbers (+0.40 / margin +0.20), untuned.
Full record: `external/Sutra/planning/findings/2026-05-15-axon-key-
make-string-coercion-regression.md`. (Line kept as a one-time
breadcrumb; delete on next todo.md tidy.)

## 2. Userspace utilities — native Sutra rewrites — second milestone

**Build order:** these are the **second milestone** after the
Connectome Manager works. Initial system access is **command-line
only** (SSH or serial from a host computer). No GUI in this phase.
The vision is "we can edit files on this thing from my computer";
once that works the browser becomes the third milestone.

**Policy:** written natively in Sutra. GNU coreutils / util-linux
behaviour is the conceptual reference for these rewrites; there is
no C→Sutra transpiler (not planned), and no vendored Linux source is
kept in-tree for them.

**Status: cannot do right now.** The blocker is not the language —
it's that Sutra's string + IO + filesystem vocabulary isn't mature
enough to make these comfortable to write yet. Once the kernel
`.su` loader lands and the Sutra stdlib grows pattern-match /
string-split / process-args / read-stdin primitives, this opens
up.

The Q-list, in rough order of priority:

| Priority | Utility | Why first/last |
|---|---|---|
| **High — first wave** | `echo` | Trivial. Smoke test for "Sutra utility writes to stdout." |
| | `cat` | Smoke test for "Sutra utility reads files." |
| | `ls` | First non-trivial — directory iteration + formatting. Forces decisions on the FS-bridge directory-listing axon shape. |
| | `wc` | Stream consumption + counter accumulation. Pure functional pattern. |
| | `head` / `tail` | Stream consumption + bounded buffering. Tail's `-f` is a real exercise of the axon-channel-as-stream model. |
| **Mid wave** | `grep` | Regex (or initial-cut substring match). Forces a regex implementation in Sutra or a stdlib decision to defer. |
| | `cut` / `tr` | Field/character processing. Pure stream transforms. |
| | `sort` / `uniq` | Whole-buffer accumulation + sort. Memory-shape question — how does a Sutra utility allocate "all the input" when the input is unbounded? |
| | `find` | Recursive directory traversal. Forces FS-bridge recursion shape. |
| | `mv` / `cp` / `rm` | Mutating FS operations. Forces capability check on `R_write_path`. |
| | `mkdir` | Trivial once `mv`/`cp`/`rm` work. |
| **Late wave — research-grade** | `awk` | Whole programming-language-in-a-utility. Either ship a minimal `awk` or document the gap. |
| | `sed` | Same shape as `awk` but for stream-edit. Often deferred to "use Sutra source directly." |
| **Out of scope, probably** | `bash` / `sh` | Yantra doesn't have a shell story yet. Possibly a Sutra-native REPL replaces this entirely; possibly we do ship a minimal POSIX shell. Open. |
| | `mount` / `dmesg` / `lsblk` (util-linux) | Kernel-adjacent. Belong with the kernel work, not userspace. |
| | `systemd` / service managers | Yantra's init/resource-manager IS the service manager. systemd has no analogue. |

Each utility lands as `apps/<name>.su` once the Sutra stdlib +
kernel loader can support it. Manifest goes in `apps/manifests/`.

## 3. Browser — renderer + TS-transpiler-CLI + first transpiled web app — third milestone

**Build order: third milestone**, after (1) Connectome Manager and
(2) command-line userspace utilities are working. The browser is
"everything is a browser" — every GUI component (start menu, mouse
cursor, login screen, file manager) is a browser-rendered HTML
page. Single GUI framework, no exceptions.

**Stack: HTML5 + CSS + idiomatic TypeScript + WebGL/Three.js.
WASM is eventually in scope but not for a long time** — not v0,
not v0.1, not on any near-term roadmap (decision 2026-05-14, see
`planning/06-gui-stack.md` and `planning/07-transpilers.md`). TS
components are pre-transpiled to Sutra ahead of time, not at
runtime.

Three parallel tracks once we get to milestone three:

- **Sutra-native renderer.** Layout engine + display server pair
  that consumes axons describing the screen state and emits
  framebuffer-shaped axons. Writable in pure Sutra today; doesn't
  depend on any transpiler. Probably lives at `apps/renderer.su` +
  a `kernel/services/display.su` once we have a real kernel loader.
  First concrete deliverable: render a hand-written Sutra "page"
  (literally just text + a colored rectangle) without touching HTML.
- ~~**TS→Sutra transpiler CLI wired up.**~~ Done in Sutra v0.3.2
  (released 2026-05-14). `python -m sutra_from_ts in.ts -o out.su`
  works end-to-end; `pip install sutra-dev[ts]` bundles it. Real
  TS-completeness work (rules for constructs the 17 fixtures don't
  cover) is the ongoing version of this item, but the CLI itself
  is no longer a blocker.
- **First transpiled web app.** Once the CLI is wired, a
  hello-world reactive component (Solid/Svelte-style) compiled
  through `ts2su → sutrac → executes` is the smallest demonstration
  that the browser can load real web content.

What's not yet in any plan:

- HTML parser. Probably written natively in Sutra.
- CSS engine. Same.
- WebGL bindings. Mentioned in `planning/06-gui-stack.md` but no
  implementation path.
- Network stack (`fetch`, `WebSocket`). Several weeks of work even
  with the language in place.

## 4. Language reach + local data — future wants (2026-05-23)

Two capabilities flagged as wanted, not yet scheduled:

- **Run Python on Yantra.** Python is, with JavaScript, one of the
  two most widely used languages and the gateway to most ML tooling.
  The likely path is the route that already works — Python → JS/TS →
  Sutra — rather than a separate Python frontend. JavaScript stays
  the priority (the browser layer requires it); Python is the
  next-most-important language to reach. Leaning *toward* doing this
  eventually; not a near-term milestone.
- **A local database.** Yantra is strong on the web/compute side but
  has no local-data story, and real systems need one — this is a
  genuine gap. The lean is toward a variant of the Sutra ecosystem's
  vector-flavoured store (`sutraDB/`), referred to in conversation as
  a "LOKA"-style store; the exact product is open. Scope: what a
  process uses to persist and query structured / vector data locally
  without leaving the axon world. Design not started.

## 5. Headline demo — out-do the Meta *Neural Computers* prototypes (symbol-stable)

The decisive external proof. Meta's *Neural Computers*
(arXiv:2604.06425, 2026, Meta AI + KAUST) ship **NCCLIGen** (terminal)
and **NCGUIWorld** (desktop): DiT video-diffusion models that *generate
plausible screen frames*, and whose own paper names **symbolic
stability** as an open problem. Yantra's posture is the opposite —
neural *execution*, not simulation (and still a trainable neural
network, since every Sutra program is differentiable). So the focus is
**not** competing on video; it is the one axis they concede is
unsolved: a terminal whose output is *computed* — exact and drift-free
over any horizon. The optimal version is a **visible calculator app**
(press buttons → the real, exact computed result), which exceeds Meta
outright (a diffusion model can't compute 4729 × 8831; ours does). Ship
it as a **downloadable, runnable demo on the Yantra site** once ready.

Full roadmap + measurement (exact-match symbol fidelity vs.
interaction horizon): `planning/22-meta-demo-replication.md`. The
proof-in-miniature — an exact symbol round-trip through the kernel —
already holds via `apps/echo`; the symbol-fidelity harness (the
measured seed) is fully unblocked today.

---

## Pointers to the live work

- Active: `queue.md`
- Architecture: `planning/01-architecture.md`
- Hard memory problem: `planning/17-memory-model.md`
- Engineering readiness audit: `planning/18-kernel-browser-readiness.md`
- Kernel layout + what's stubbed: `kernel/README.md`
- Paper revision discipline: `CLAUDE.md` § "Paper revision discipline"

---

## [NEXT YEAR] Formally define "tensor normal form" — before using the term anywhere

**Status: deferred, ~next year (Emma 2026-05-25).** "Tensor normal form" / "TNF"
has been **removed from the active specs and docs** (here and in Sutra) because we
never formally defined it, and asserting a canonical "normal form" we have not
proven actively hurt the FV paper's reception. The defensible phrasing used
everywhere now is descriptive: *the compiler emits a tensor-op graph that is the
program's semantics.*

Rough idea we have (keep, do not over-promise):
- **Tensor normal form ≈** algebraically simplifying a program to *just a
  sequence of matrix multiplications* (an affine/multilinear pipeline).
- **Recurrent tensor normal form ≈** the same for the bounded soft-halt loop
  (`state ← R · state`).

Deferred because a real normal-form claim needs FV / rewriting-theory machinery
(confluence, a canonicalisation/decision procedure, proofs of canonicality) we
do not have yet, and it is unclear what standing we have to declare a new normal
form as a formal object. Define it properly, with proofs, as part of the FV
process — then and only then reintroduce the term. Mirrored in Sutra `todo.md`.

Note: the arXiv-frozen `paper/paper.md` (+ its supplementary, e.g. `paper/SKILL.md`)
still use "tensor normal form" and cannot change until the freeze lifts (June 1).
Review records (`paper/reviews/*`) are left as-is. These are the only remaining
in-repo uses on the Yantra side.

---

## Project wind-down & loose-ends cleanup (Emma 2026-06-16)

The public brand is moving to **Noldor Technologies** (noldor.tech) and the
Sanskrit/OS framing is being dropped from the *website*. `yantraos.org` redirects
to `noldor.tech` (Yantra PR #1, cutover 2026-06-18 3pm Pacific). **The OS
prototype itself is PRESERVED, not wound down** (Emma 2026-06-16: "worth
definitely preserving the stuff" — the OS may still be continued). This backlog
tidies the *meta* (stale queue, doc drift, noisy CI) without destroying code.
Decompose into `queue.md` and barrel through it.

- **PRESERVE the OS prototype.** Do NOT delete kernel/, orchestrator/,
  bootloader/, or apps/. Content-audit recommendations apply
  *additively/preservationally*:
  - `apps/gui-rust` — KEEP. The real GUI demo also lives in
    `external/Sutra/demos/gui/`; that's a safety duplicate, not grounds to delete.
  - `apps/calc` — COPY the Yantra-unique substrate-parsing `.su`
    (`parse_op.su`, `parse_int2.su`) into Sutra's `demos/calc/` so it's preserved
    in the active repo too. KEEP Yantra's copy. Update `apps/README.md`.
- **Clear stale `queue.md` cruft** — the completed 2026-06-13 website session,
  the daily substrate-honesty audit auto-prepends, and the "to be dispositioned /
  archived" kernel section.
- **Stop the daily-audit queue spam** — `.github/workflows/daily-audit.yml`
  prepends a substrate-honesty audit item to `queue.md` every day. The repo does
  no `.su` work anymore and is winding down; disable the schedule so it stops
  cluttering the queue (keep the file, reversible).
- **Reconcile docs to the rebrand** — note in `README.md` (and `CLAUDE.md` where
  relevant) that the site now redirects to noldor.tech and the OS/language work
  lives in Sutra.
- **Kernel/apps CI is red and accepted** (Emma 2026-06-13: "ignore it") — do not
  spend cycles fixing the parked-prototype pytest CI; Pages deploys green.
