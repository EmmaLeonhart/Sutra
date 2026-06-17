# `kernel/` — Connectome Manager Python prototype (v0.0)

> **What this is.** A **behavioural reference** for what the Rust
> orchestrator in `planning/19-boot-sequence.md` § "Stage 4" does
> once boot is complete: admission control, axon routing,
> capability checks, the tick loop. Sutra is doing the actual
> computation — each service is a real Sutra-compiled `.su` program
> whose `on_axon(vector) -> vector` runs on real torch tensors —
> but the orchestration layer is Python in this repo as a
> short-term implementation choice. The Rust port reimplements the
> same shape; this Python pins the API.
>
> **What this is NOT.**
>
> 1. Not the bootloader. The bootloader runs at stage 3 of
>    `planning/19-boot-sequence.md`, before any interpreter
>    exists, against bare hardware. It is **necessarily Rust or C**.
>    Python cannot be a bootloader; the boot path runs before any
>    interpreter is loaded.
> 2. Partial model of the production axon router. `router.py` now
>    implements the **kernel slice of lazy axon evaluation**:
>    receivers declare which `axon_keys` they read in their
>    manifest, producers attach `keys=...` when they emit, and the
>    router skips delivery to any receiver whose interest set
>    doesn't intersect the axon's key set. Audit counter
>    `lazy_skipped_count()` tracks how often this fires. See
>    `planning/20-lazy-axon-evaluation.md`. **What's still
>    upstream-Sutra-dependent**: per-receiver projection (slicing
>    the payload tensor to materialize only the dimensions the
>    receiver references). The kernel here only decides
>    deliver-or-skip the full payload, not slice within it.
> 3. Not a model of multi-process GPU concurrency. `tick()`
>    iterates services sequentially on CPU. Real Yantra runs all
>    admitted programs simultaneously on the GPU at every tick.
>    Single-program-per-tick is a CPU-side stand-in.
> 4. Partial model of the storage-tier moves the Connectome
>    Manager does. **The DISC↔GPU slice is now implemented and
>    GPU-measured** (corrected 2026-05-17 — the old "not
>    implemented; only admit/deregister" text was stale, and so was
>    "blocked on no GPU": there is a real RTX 4070 here):
>    `Init.load(name)`/`unload(name)` instantiate / tear down a
>    program's CUDA-resident Sutra runtime, with the GPU memory
>    actually reclaimed (`tests/test_kernel_gpu_tiers.py`:
>    `loaded=669696 → unloaded=0 → reloaded=669696` bytes). What is
>    *now shipped (2026-05-25)* is the **RAM cold-store of a running
>    program's mutated state** (checkpoint + bit-exact resume) —
>    once thought to need `serialise-process-state` — but the
>    2026-05-25 finding showed it does NOT: current Sutra has no
>    per-program mutable substrate state, so cold-store reduces to
>    capturing the inbox — **SHIPPED** (`Tier.RAM`). See `planning/26`.

## What runs today

```bash
# All kernel tests (unit + real-Sutra + Linux 0.00 + GPU tiers):
python -m pytest tests/test_kernel.py tests/test_kernel_sutra.py \
    tests/test_linux_000.py tests/test_kernel_gpu_tiers.py -v
```

**`tests/test_kernel_gpu_tiers.py` proves the load/unload-onto-GPU
MVP.** CUDA-gated (skips without a GPU). It admits a real
`SutraService`, then measures `torch.cuda.memory_allocated()`
across `unload`/`load`: `loaded=669696 → unloaded=0 →
reloaded=669696` bytes — the program's GPU arena is genuinely
allocated, freed on unload, and re-allocated on reload, and the
program stops running on `tick()` while unloaded. This is the
Connectome Manager's core "decide what is resident on the GPU"
job, for real.

**`tests/test_kernel_sutra.py` is the one that proves Sutra is
running.** It admits two real `SutraService`s — `echo.su` and
`sink.su` compiled by the Sutra v0.6.2 compiler — and routes a
real `torch.randn(768)` tensor through the chain
producer → echo (Sutra compute) → sink (Sutra compute), verifying
the receive end gets a real torch tensor back. The first test in
that file pays the embedding-model download cost (~tens of seconds
to minutes on cold cache); the rest reuse the cached compile.

**`tests/test_linux_000.py` is the Linux 0.00 replica.** Two real
Sutra services (`task_a.su`/`task_b.su`) emit the ASCII codepoints
of `A`/`B` (`real_number(65)`/`(66)` — a substrate op, not a faked
constant) each time the Connectome Manager ticks them (the
timer-IRQ analogue); `console.su` is the fan-in VGA-memory
analogue. Measured: `real(task_a)==65.0`, `real(task_b)==66.0`,
kernel-mediated interleaved stream `'AB'*8` — Linux 0.00's "kernel
alternates two trivial output tasks" realized in Yantra's
connectome model. Faithful-mapping rationale + scope (no
bare-metal boot / TSS — a separate gated bootloader item) in
`planning/21-linux-0.00.md`.

`tests/test_kernel.py` is the unit-test layer for admission
control + router + capability check, using Python stand-ins so
the unit tests don't pay the Sutra compile cost.

## Layout

| File | Purpose |
|---|---|
| `manifest.py` | TOML manifest parser. One process per manifest. |
| `router.py`   | Axon router with capability check on send + receive. |
| `init.py`     | Resource manager: admission against a fixed pool budget; tick scheduler. |
| `services.py` | `Service` base + `SutraService` (compiles + runs `.su` programs) + `PythonService` (test/harness only). |
| `manifests/`  | `echo.toml`, `sink.toml` — declarative process descriptors. |
| `services/`   | `echo.su`, `sink.su` — real Sutra source executed by the Sutra v0.6.2 compiler at admission time. |

## What is real, what is stubbed

**Real** in v0.0:

- **Real Sutra compute.** `SutraService` compiles a `.su` source
  at admission time via the Sutra v0.6.2 compiler in
  `external/Sutra/sdk/sutra-compiler/`, exposes its `on_axon`
  function, and invokes it on every inbound axon. Inputs and
  outputs are real torch tensors of shape `(axon_width,)`. Tested
  end-to-end in `tests/test_kernel_sutra.py`.
- Manifest parsing with structured validation errors.
- Per-process admission against a fixed `compute_pool` budget;
  refusal-on-exhaustion is clean (`PoolExhaustedError`); deregister
  releases budget.
- Capability check on write (sender must hold the role) and read
  (receiver must hold the role) at every send. Fires the same way
  whether the service is `SutraService` or `PythonService`.
- Black-hole policy: a send to a role no admitted process reads is
  audited and dropped, not raised — startup-order tolerance per
  `planning/01-architecture.md`.
- Multi-receiver fan-out (one role, N readers ⇒ N delivered).
- `tick()` scheduler that drains every service's inbox once per tick
  and reports per-process processed counts.

**Out of scope** in v0.0 — these all require upstream
Sutra-side work that hasn't shipped:

- **Real per-process GPU memory arenas.** `compute_units` is
  bookkeeping only because PyTorch's GPU memory model is
  per-process — one Python process can't hand pre-allocated GPU
  memory regions to N other processes running concurrently on the
  same device. The fix is the **multi-threaded Sutra runtime**
  being built in the Sutra repo upstream; until that lands, no
  orchestrator (Python or Rust) can make real per-process arenas
  work.
- **Storage-tier moves — DISC↔GPU done; RAM cold-store still
  blocked.** (Corrected 2026-05-17.) `Init.load`/`unload` is real
  and GPU-measured: a program's CUDA-resident Sutra runtime is
  instantiated / torn down with the GPU memory actually reclaimed
  (`evict-from-GPU` is no longer a missing primitive — it's
  proactive `_VSA` device-tensor release in
  `SutraService.unload()`; `tests/test_kernel_gpu_tiers.py`).
  What was thought blocked — checkpointing a *running* program's
  mutated state to a RAM cold-store and resuming it bit-exact
  — is **SHIPPED 2026-05-25** (`Tier.RAM`, `Init.cold_store`/
  `restore_from_cold`); no `serialise-process-state` needed (2026-05-25 finding). The multi-program axon-passing demo in
  `external/Sutra/examples/multi_program_axon/` serialises a
  program's *output*, not a live process's state. Both tiers now work:
  "start/stop a program on the GPU" AND "pause a running
  program and resume it where it left off" — done (2026-05-25).
- **GPU-tick-parallel scheduling.** `Init.tick()` iterates
  services sequentially on the CPU. Production Yantra runs all
  admitted processes simultaneously on the GPU at each tick. The
  service abstraction is concurrency-agnostic so the swap is
  drop-in once the upstream Sutra runtime supports it.
- **Eviction to RAM cold-store (state-preserving).** Evicting a
  program *from the GPU* is done (`unload`, GPU memory freed).
  What remains is preserving its *running* state across the
  eviction so a later `load` resumes where it left off rather than
  fresh — same `serialise-process-state` blocker as above. Today
  `unload`/`load` is load-fresh/drop, which is the correct MVP
  semantics for start/stop.
- **Rotation-operator-based capability check.** v0.0 trusts the
  sender's name (admission grants identity; capability is checked
  by name). Production's threat model
  (`paper/paper.md` § 3.3.1) is operator-based: possession of
  `R_role` is the capability. Lands when the Sutra-side service
  format formalises operator carriage.

## How to add a new service

1. Write a `.su` source file under `kernel/services/<name>.su`
   exporting a `function vector on_axon(vector input_axon)`.
2. Write a manifest TOML in `kernel/manifests/<name>.toml` with
   the process's `axon_width`, `compute_units`, `read_roles`,
   `write_roles`, and `source` (path to the `.su` file).
3. Construct a `SutraService` and admit it.

### Two construction patterns

**Per-service compile** (one `_VSA` per service — fine for one or
two test services):

```python
from kernel import Init, SutraService
svc = SutraService(
    source_path="kernel/services/myservice.su",
    output_role="R_my_output",
)
init.admit_from_path("kernel/manifests/myservice.toml", svc)
```

**Shared MultiProcessRuntime** (Sutra v0.4.0+, recommended for N
services — shares one `_VSA` + codebook + embedding cache + GPU
device across all of them):

```python
from kernel import Init, make_shared_sutra_services
runtime, services = make_shared_sutra_services([
    {"name": "echo", "source_path": "kernel/services/echo.su",
     "output_role": "R_output"},
    {"name": "sink", "source_path": "kernel/services/sink.su",
     "output_role": "R_stat"},
])
for svc, manifest_name in zip(services, ["echo.toml", "sink.toml"]):
    init.admit_from_path(f"kernel/manifests/{manifest_name}", svc)
```

The factory builds the shared runtime + N services wired to it.
Both patterns produce services that drop into `Init.admit()`
identically; the shared-runtime path just shares more
infrastructure. `PythonService` remains available for tests +
harness code that doesn't need real Sutra compute.

4. Drive it: `init.tick()` runs every service's tick once.

## Hard things deliberately out of scope

- **Bit-exact eviction-and-resume serialisation.** See `planning/17-memory-model.md`.
- **CPU/GPU boundary cost (interrupts, MMIO).** See `paper/paper.md` § 3.5.
- **Adversarial-perturbation robustness of rotation operators.** See
  `paper/paper.md` § 3.3.1. The router's capability check is
  process-name-based in v0.0 (a sender's claim of identity is trusted
  because the sender is admitted by init); rotation-operator-based
  capability check is the production model and is gated on the v0.1
  `.su` loader landing.

These aren't oversights; they're problems the architecture defers to
specific other documents and other layers, and v0.0 is explicit about
where its contribution ends.
