# Readiness assessment — kernel and browser

> **What this document is.** An accurate accounting of what we have *now* versus what we need to actually start writing (a) the kernel and (b) the browser. Originally written 2026-05-13 vs Sutra v0.3.1.
>
> **Refreshed 2026-05-16** (autonomous loop) against the current submodule, **`external/Sutra` @ `v0.4.0-27-gdd448b47`** — every "v0.3.1" / "the multi-process runtime hasn't landed" / "TS CLI is an unwired skeleton" claim below was stale or internally contradictory and is corrected inline, each correction measured (test run / CLI run / `git describe`), not asserted. The original-tone paragraphs are kept where still true.
>
> **Refreshed 2026-05-23:** submodule now pinned at `external/Sutra` **v0.6.0**; the kernel suite is **~56 tests** (54 pass / 1 fail / 1 xfail, measured 2026-05-23 — the failure is the GPU-memory-accounting assertion in `test_kernel_gpu_tiers.py`, the xfail is the cross-program `axon_project` no-op). The dated 2026-05-16 measurements below stand as their own snapshot; read them as of that date.
>
> **Refreshed 2026-05-24:** submodule now pinned at `external/Sutra` **v0.6.2** (adds the `dot` builtin + selectable `runtime_dtype`; the calc now selects on the substrate via `select` and runs float64, exact to 2⁵³). Measured this date on the **real CUDA box (RTX 4070, `torch.cuda.is_available()` True)**: `test_kernel_gpu_tiers.py` **passes 4/4 in isolation**, and a fresh-process probe shows **admit allocates +712,704 B of GPU memory** for `echo` (`_VSA.device == cuda`) — so **admit → GPU-resident works; the DISC↔GPU residency capability is real, not blocked.** The whole-suite gate is now **118 passed, 1 xfailed** (the 1 xfailed is the cross-program `axon_project` no-op). **Test-isolation fixed 2026-05-24:** `test_admit_makes_program_gpu_resident` previously read +0 admit-delta in the full suite (earlier modules warm the shared per-process substrate, so a later admit reuses it) and so failed there while passing in isolation. The residency assertion now proves the footprint **baseline-independently** — by the GPU memory that *unloading* echo frees (robust to a warm substrate; same delta `test_unload_*` checks) — instead of the fragile admit-vs-`base` delta. Not a weakening: it is a stronger residency proof. **Earlier drafts of this line wrongly called the +0 an "unbuilt per-process GPU arena" — that was a bad assumption about the machine; the capability works (+712,704 B at admit in a fresh process, `_VSA.device == cuda`), corrected against measurement.**
>
> **Refreshed 2026-05-25:** submodule now pinned at a `main` commit past **v0.7.0** (`599424f8`); v0.7.0 shipped Sutra's formal-verification public API (`from sutra_compiler import fv`: the Kleene-fragment equivalence decision procedure + the closed-form polynomial range-bounder). The whole-suite gate is now **207 passed, 1 xfailed** (measured 2026-05-25 on the RTX 4070; same lone `axon_project` xfail). **Shipped later this date:** the orchestrator checkpoint (`kernel/checkpoint.py` — whole-kernel admission table + tier map + inboxes, bit-exact round-trip), the **RAM cold-store tier** (`Tier.RAM`, `Init.cold_store`/`restore_from_cold`), and a device-faithfulness fix (restore places inboxes on the consuming service's device — the CPU-only sibling machine missed the GPU mismatch). The RAM cold-store needs **no** Sutra `serialise-process-state` primitive — see the item-4 correction below. Shipped under `apps/` since the 2026-05-24 line: the calculator now decides BOTH which operation runs AND the operator-character→operation mapping on the substrate (`switch.su` reads the op char's codepoint via `string_char_at`; the host `CODE[op]` map is gone); a first **GUI** (`apps/gui/` — every pixel computed on the substrate, plus an interactive red↔blue click whose state flips on the substrate); and a **terminal** surface (`apps/terminal/` — echo/calc through the kernel, zero-drift trace). **Still blocked (measured this session, not faked):** variable-length substrate number parsing needs a Sutra loop that iterates a string while accumulating a number — numeric loops work, but a string-state accumulator loop hits a runtime `expand([868], size=[])` shape error not cracked across 5+ attempts (needs a deliberate Sutra-loop session); the batched GUI render needs a Sutra `make_real`-batch (it is scalar-only); arbitrary precision needs substrate carry propagation. The 2026-05-24 measurements below stand as their own snapshot.
>
> **What this document is not.** A roadmap commitment. The "should we start" calls at the end are recommendations; the user picks.

## Build sequence

User clarification 2026-05-14: the build order is

1. **Connectome Manager (kernel)** — ship the runtime that decides
   what runs on GPU vs sits in RAM vs on disc. Python prototype
   under `kernel/` exists and is tested; production form is Rust.
2. **Command-line userspace utilities** — simple Linux-shaped file
   utilities (cat, ls, grep, etc.), accessed by SSH or serial from
   a host. **No GUI in this phase.**
3. **Browser / GUI** — only after (1) and (2). Every GUI component
   (start menu, mouse, login) is a browser-rendered HTML page;
   single framework; HTML5 + CSS + TS + WebGL/Three.js, no WASM.

Each section below is read in this sequencing context.

## TL;DR

- **Kernel (Connectome Manager) — Sutra-running v0.0 shipped; Rust port pending.** The v0.0 runtime under `kernel/` is real and tested. **Sutra is doing the actual computation**: `SutraService` compiles `.su` source via the Sutra compiler (now `v0.4.0-27-gdd448b47`, not v0.3.1) at admission time and invokes the program's `on_axon(vector) -> vector` on real torch tensors carried through the router. `tests/test_kernel_sutra.py` admits real Sutra services and routes a payload producer → echo → sink end-to-end. The orchestration layer (init/resource-manager + router + capability check) is currently in Python; production form on the CPU side is Rust per `planning/01-architecture.md` § "CPU side: small, Rust, orchestrator." **48 tests collected across `tests/test_kernel.py` + `tests/test_kernel_sutra.py`** (measured 2026-05-16; the old "25 total" is stale). **Correction 2026-05-16:** the Sutra **multi-process runtime SHIPPED** (Sutra v0.4.0) — `kernel.make_shared_sutra_services` builds shared-`_VSA` services and `test_make_shared_sutra_services_share_one_vsa` + `test_shared_runtime_axon_passing_through_router` **pass** (measured this run). So "blocked on the multi-process Sutra runtime" is no longer true for the shared-runtime case. Still genuinely out of scope: real per-process GPU memory carve-outs, disc/RAM/GPU storage-tier moves (missing serialise-process-state / evict-from-GPU primitives), GPU-tick-parallel scheduling. **New caveat (this loop's measured finding):** per-receiver axon projection (`_VSA.axon_project`) is a **no-op for embedding fillers** — `bind(k,unbind(k,bundle))≈identity` under orthogonal rotation binding, so the "slimmed" payload still holographically carries every key (a receiver asking for one key decoded a projected-OUT key at +0.5726 vs kept +0.5999). So lazy axon eval delivers neither the bandwidth nor the capability-isolation property for the common case — see `planning/20-lazy-axon-evaluation.md` § Status; bears on `paper/paper.md` § 3.3.1.
- **Native userspace utilities (cat, ls, grep, awk, etc.) — second milestone, deferred.** Written natively in Sutra. GNU coreutils / util-linux behaviour is the conceptual reference (no vendored Linux source). Blocked on Sutra's string + IO + FS vocabulary maturing and on the kernel `.su` loader landing.
- **Browser — third milestone, deferred.** "Every GUI component is a browser." HTML5 + CSS + idiomatic TS + WebGL/Three.js. WASM eventually but not for a long time (decision 2026-05-14). **The TS→Sutra transpiler ships as Sutra v0.3.2**: CLI works (`python -m sutra_from_ts in.ts -o out.su`), 17 fixtures pass through, `pip install sutra-dev[ts]` bundles it. Coverage isn't "every npm package compiles" — it's "the typed core works, edge constructs need new lowering rules as encountered." The Sutra-native renderer doesn't depend on the TS transpiler and could in principle start now, but is sequenced third per the user's plan.

## What Sutra actually ships

Pinned at `external/Sutra` @ **`v0.4.0-27-gdd448b47`** (refreshed 2026-05-16; was "commit 2582cd46, tag v0.3.1"). Direct read of the submodule:

### Working today

- **The Sutra compiler (`sutrac`).** Validate, `--emit` to self-contained PyTorch Python, `--run` end-to-end. Runs on Python 3.11+. Substrate-purity audit landed in v0.3.1 (the bug it fixed: complex `+`/`-`/`/` were silently host-Python instead of substrate-pure — bad enough that it warranted a same-day patch release).
- **Multi-program axon passing.** Two separately-compiled `.su` programs exchange a 5-key axon via a numpy `.npy` wire. **History:** this regressed (a compiler bug — `axon_item` string-key was `make_string`-coerced while the producer kept it a host str, so producer/consumer keyed on different role vectors → cross-module decode collapsed to ~0.04). Root-caused + fixed this loop (Sutra `eb0ce93e`); `examples/multi_program_axon/_run.py` is back to **PASS at +0.40 / margin +0.20** (measured, untuned). **This is the kernel-side IPC primitive**, shippable nucleus of the router — but note it round-trips the *full* bundle: lazy per-receiver slimming via `axon_project` is a no-op for embedding fillers (see the kernel TL;DR caveat + `planning/20-lazy-axon-evaluation.md`), so true bandwidth/isolation needs producer-side pruning, not the wire as-is.
- **Stdlib transcendentals — substrate-pure (after a real leak was found and fixed).** `Math.exp/log/sin/cos/tan/sinh/cosh/tanh/pow/sqrt` all native. **History (do not paper over):** the "interpolated lookup table, no host-Python fall-throughs" claim was *false* as of 2026-05-15 — `exp`/`log`/etc. did `float(x)` in, host `if`/`raise`, `float(...)` out (a substrate leak that had been labelled "substrate-pure" in a comment). Fixed in Sutra `21a9ff77`: one `_st()` host→substrate boundary, eigenrotation/`cexp` for trig, real `exp` = `cexp(x,0)` beta-reduced, out-of-range **saturates** (no host raise — the no-runtime-errors rule). Now genuinely substrate-pure; verified by `test_transcendentals` (20 subtests) at the time of the fix.
- **Modulus library.** `Math.mod` (eigen-rotation, ~10⁻⁷ max abs error), `Math.fmod` (truncation, JS/C semantics), the `%` operator now substrate-routed.
- **Async/await/`Promise<T>`** as first-class Sutra vocabulary, two-stage beta-reduction at compile time. This is a load-bearing enabler for the browser stack — async is the only sane way to do event-driven UI.

### TypeScript transpiler — shipped, CLI wired (corrected 2026-05-16)

- **TypeScript transpiler (`sdk/sutra-from-ts/`).** `lower.py` is real lowering: function declarations, type annotations, interface/type erasure, member access (`p.x` → `p.item("x")` for axon-typed `p`), JS-coercive `+` via `JavaScriptObject.add`, classes (fields + methods + static + constructors + `new`), discriminated unions, while/for/do-while loops, string concat, arrays, enums. 17 fixtures exercise it end-to-end. **The CLI is WIRED** — measured 2026-05-16: `python -m sutra_from_ts --help` prints the real `ts2su` argparse usage ("Transpile a typed core of TypeScript … into Sutra (.su) source", exit 0), shipped as Sutra v0.3.2 (2026-05-14). The earlier "CLI is still the skeleton not-yet-implemented stub, wiring it is a small task" text in this doc was stale and **contradicted its own TL;DR**; deleted. Real remaining work is TS-completeness (lowering rules for constructs the 17 fixtures don't cover), not CLI wiring.

### Not planned

- **C transpiler (`sdk/sutra-from-c/`).** A ~57-line stub exists in the Sutra SDK; it will not be built out. C→Sutra is **not planned** (decision 2026-05-23) — Yantra does not bring across the Linux kernel or C apps. Userspace is native Sutra; the bootloader and orchestrator are native Rust.

### Adjacent

- **`sutraDB/`** — included in the repo. Vector-store-flavoured. Not directly on the OS critical path but useful for the FS bridge's `semantic` mode.
- **CUDA backend** — `compile_to_cuda.py`, `hello_world_cuda.py`. The PyTorch backend works on CPU and CUDA; an explicit CUDA emission path exists.
- **`paper/paper.md`** — the Sutra paper itself, with the empirical measurements Yantra's design rests on (100% bundle decoding through k=8 across four substrates, ~1.5×10⁻¹⁵ round-trip, 4→95% in 50 epochs). Cite this directly from `paper/paper.md` in Yantra rather than paraphrasing.

## Kernel — what we have, what we need

### What we have (v0.0, shipped)

- **`kernel/` runtime nucleus.** Manifest parser, axon router with capability check, init resource manager with admission control, two example services (echo + sink), and 19 passing tests including a flagship round-trip. See `kernel/README.md` for the layout.
- **Orchestrator checkpoint + RAM cold-store — shipped 2026-05-25.** `kernel/checkpoint.py` captures the whole-kernel state (admission table + tier map + per-program inboxes) to Rust-portable bytes and restores it bit-exact through a real echo round-trip; `kernel/serialise.py` is the per-axon wire format. The **`Tier.RAM`** cold-store tier (`Init.cold_store(name) -> bytes` / `restore_from_cold`) parks a process's in-flight inbox in a host blob and resumes it bit-exact — pure orchestrator-side serialisation, **no Sutra `serialise-process-state` primitive needed** (2026-05-25 finding). `tests/test_kernel_checkpoint.py` (9) + `tests/test_kernel_ram_tier.py` (10). See `planning/26-orchestrator-serialisation.md`.
- A working language (Sutra `v0.4.0-27-gdd448b47`) with multi-program axon passing demonstrated as a separate primitive in `external/Sutra/examples/multi_program_axon/` (regression-fixed + verified this loop — see above).
- A compile-to-CUDA path (Sutra ships `compile_to_cuda.py`) so the kernel runs on real GPUs eventually, not only the PyTorch reference.
- Async / `Promise<T>` for event-driven scheduling primitives.
- All seventeen planning docs defining the kernel's intended behaviour.

### What's stubbed in v0.0 — the v0.1 work list

1. **Real GPU memory arena allocation.** `compute_units` in the manifest is bookkeeping only; the runtime tracks budget but does not carve out actual device memory. Production-grade per-process arenas need Sutra-runtime cooperation.
2. **GPU-tick-parallel scheduling.** v0.0 ticks services sequentially on CPU; production runs all admitted processes simultaneously on the GPU at each tick. The service abstraction is concurrency-agnostic, so this is a scheduler swap, not a service-side rewrite.
3. ~~**`.su` service loading.**~~ **Works — corrected 2026-05-16.** The old claim ("`kernel.services.load_su_service()` raises `NotImplementedError`; v0.0 services are `PythonService` subclasses") was false on both counts: `load_su_service` is defined nowhere (measured — absent on `kernel`/`kernel.services`), and real `.su` services load + run via `SutraService(source_path=…, output_role=…)` (compiles the `.su`, runs `on_axon(vector)->vector`, consumes `AXON_KEYS_BOUND/READ` static analysis). The `kernel/services/{echo,sink}.su` seeds are *used*, not just documentation, and many `tests/test_kernel_sutra.py` tests admit real `.su` services. The "convention from the Sutra side" the old text waited on shipped (it's in `SutraService`'s docstring). The genuine remaining work is the *Rust* orchestrator's own `.su` loader, not a missing Python stub — drop from the Python v0.1 list.
4. ~~**Eviction to RAM cold-store.**~~ **Done — corrected 2026-05-17; completed 2026-05-25.** The old "not implemented; only admit/deregister" is stale. `Init.load`/`unload` now instantiate / tear down a program's CUDA-resident Sutra runtime with GPU memory genuinely reclaimed on the real RTX 4070 (measured 669696→0→669696 B; `tests/test_kernel_gpu_tiers.py`). So **eviction *from the GPU* is done**; the state-preserving half — RAM cold-store of a paused program — **also shipped 2026-05-25** (`Tier.RAM`, `Init.cold_store`/`restore_from_cold`, bit-exact resume of the inbox through a real echo). It needs **no** Sutra `serialise-process-state` primitive: the 2026-05-25 finding established current Sutra has no per-program mutable substrate state (purely functional; training is a host PyTorch proxy, not compiled `.su`; VSA caches are deterministic from keys), so "preserve running state" reduces to "preserve the orchestrator-side inbox" — pure host serialisation. Start/stop-on-GPU: done. Pause-resume-preserving-state: done. A `serialise-process-state` accessor stays deferred until a real consumer (trained `.su` programs) exists.
5. **MMIO / interrupt / hardware-boundary path** (paper §3.5). Blocked on having hardware to develop against.
6. **A worked memory model** (`planning/17-memory-model.md`). Doesn't block first-prototype writing but bites at scale.

### Assessment

The kernel nucleus is real and tested. v0.1 is the hardening list above. **Correction 2026-05-16:** the multi-process Sutra runtime *itself* shipped (Sutra v0.4.0; shared-`_VSA` services + router axon-passing tests pass — measured). **Correction 2026-05-17:** DISC↔GPU load/unload (item 4's GPU half) now works on a real GPU (RTX 4070, measured). What remains for the "no degradation under load" property is the *specific* slice still missing: per-process GPU memory arenas and GPU-tick-parallel execution (items 1–2), the *state-preserving* half of eviction (RAM cold-store of a paused program) **shipped 2026-05-25** with no `serialise-process-state` needed. Items 1–2 are now the long pole, not "the runtime hasn't landed" and not "no GPU".

## Browser — what we have, what we need

### What we have

- Async / `Promise<T>` in Sutra (event-driven UI is feasible).
- The TS transpiler's `lower.py` covering classes, methods, instance fields, arrays, discriminated unions, async/await — i.e., the JS-shape that real reactive frameworks produce after compilation. 17 passing fixtures.
- A WebGL plan in `planning/06-gui-stack.md` (not a runtime, but a plan).
- The `JavaScriptObject` runtime in Sutra for the untyped-JS fallback path.

### What we need to start writing

1. **A Sutra-native renderer** — at minimum a layout engine + display server pair that consumes axons describing the screen state and emits framebuffer-shaped axons. **Writable in pure Sutra today.** The GUI layer's tensor-op shape is exactly what Sutra is for; we do not need any transpiler to start.
2. ~~**The TS transpiler's CLI wired up to `lower.py`.**~~ **Done** (Sutra v0.3.2; `ts2su` works — measured 2026-05-16). No longer a prerequisite.
3. **A minimal JS/TS web app, transpiled, running.** Something on the order of a "Hello world" reactive component that compiles through `ts2su → sutrac → executes`. The CLI exists now, so this is the actual next browser-track step (gated only by the build sequence — milestone 3, after kernel + CLI utilities).

### What we still don't have

- **HTML/CSS parser and layout.** Not in Sutra at all (any version). Either we write a layout engine in Sutra (substantial) or we transpile a small one (e.g., a stripped-down Servo subset, but that depends on the C/Rust transpiler path which doesn't exist).
- **WebGL bindings.** The plan mentions WebGL; the implementation does not exist.
- **Network stack / `fetch` / `WebSocket`.** A minimum-viable fetch-shim is several weeks of work even with the language in place.

### Assessment

**Start writing the Sutra-native renderer now.** This is the part that does not depend on the TS transpiler being polished, and it is the part that is most novel — the layout engine that consumes axons and emits axons is the load-bearing demonstration that "everything is a browser" can be implemented at all. Defer the web-app-loading story until both the renderer and the TS transpiler CLI are ready. A v0.0 browser that displays a hand-written Sutra "page" before it can load any HTML is a perfectly defensible milestone.

## Cross-cutting recommendations

- ~~**Wire up the TS transpiler CLI first thing.**~~ **Done** (Sutra v0.3.2). `ts2su` is a working command (measured 2026-05-16). This recommendation is retired.
- **No C-transpilation Linux story.** C→Sutra is not planned (decision 2026-05-23) and the vendored Linux source (`coreutils`/`util-linux`/`busybox`) was removed. Yantra's userspace is hand-written Sutra; the browser layer is TS-transpiled.
- **TS→Sutra is genuinely running, CLI included.** Earlier this doc and the paper hedged on "the CLI is unwired" — that nuance is now obsolete (CLI shipped v0.3.2). The accurate statement: the lowering engine + CLI work; TS-*completeness* (rules for constructs beyond the 17 fixtures) is the open edge, not CLI wiring. Keep CLAUDE.md / `planning/07-transpilers.md` matching this.
- **The bottleneck is not the language, and not "the multi-process runtime hasn't landed" — it landed (Sutra v0.4.0, measured).** The real long pole is now the *specific* GPU-side slice: per-process memory arenas + tick-parallel execution + storage-tier eviction. Plus the newly-measured caveat that `axon_project` doesn't actually slim embedding-filler axons (no lazy-eval bandwidth/isolation for the common case) — a Sutra-side design problem (`planning/20-lazy-axon-evaluation.md` § Status).

## Cross-references

- `paper/paper.md` § 8.2 milestones — high-level readiness, but written before this submodule audit; this doc supersedes for engineering planning.
- `planning/06-gui-stack.md` — what the GUI layer is supposed to look like.
- `planning/07-transpilers.md` — the transpiler section as written; the TS transpiler is real **and CLI-wired** (Sutra v0.3.2); C→Sutra is not planned. Keep that doc matching this.
- `planning/17-memory-model.md` — the long-pole problem that does not block first writing but bites at scale.
- `external/Sutra/` — the actual code; read it, don't trust this summary alone.
