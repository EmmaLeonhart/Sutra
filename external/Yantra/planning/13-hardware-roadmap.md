# Hardware roadmap

## Three hardware eras

Yantra's hardware story has three distinguishable phases, each
strictly more aggressive than the last. The OS architecture is the
same across all three; the substrate underneath gets less and less
conventional.

### Phase 1 — Commodity GPU + small CPU

Today. A normal x86_64 (or ARM64) box with a CUDA-capable GPU and
plenty of RAM. The CPU is "small" only in the role-it-plays sense —
it can be a perfectly normal CPU, it's just that the OS doesn't ask
it to do much except orchestrate.

Why start here:

- Hardware exists, is cheap-ish, and customers already own it.
- CUDA toolchains are mature; Sutra already targets them.
- Easy story for partners and pilots: "buy this server, install
  Yantra, see the predictable-performance demo."
- Forces us to make the architecture work on substrate the world
  has, before reaching for substrate the world doesn't.

### Phase 2 — Reference Yantra appliance

Custom hardware integration but conventional silicon. A box where:

- The CPU is genuinely smaller (lower power, fewer cores) because it
  doesn't need to run a workload.
- The GPU is sized for the customer's process budget (e.g., 80 GB
  for a sensor-fusion appliance, 24 GB for an industrial control
  endpoint).
- Storage and RAM are sized for the cold-store / verbatim workload.
- Firmware and BIOS are minimised; the bootloader's job is small.
- The box is shippable, supportable, and validated for a target
  certification.

This is the first hardware product. Margins go on the appliance, not
on the OS.

### Phase 3 — Analog / neuromorphic substrate

The long-term bet. Replace the digital GPU with an analog matrix
hardware that natively runs Sutra's tensor operations. Candidates:

- **Memristor crossbars.** Analog matrix-vector multiply at low
  power. Mature enough to be in production at niche scale; not yet
  commodity.
- **Photonic / optical compute.** Matrix multiply by interference
  patterns. Promising for specific workloads, very early for general
  compute.
- **In-memory compute.** SRAM/RRAM cells that compute in place.
  Closest to "drop-in for GPU" mentally; differs from GPU mostly in
  power efficiency and determinism.
- **Custom mixed-signal ASICs.** A purpose-built Yantra/Sutra
  accelerator. Not a near-term product but a credible long-term
  target.

Yantra's value proposition gets *stronger* on this substrate, because:

- The whole OS already speaks tensor operations natively. The CPU is
  already minimal. There is no "port Linux to the new substrate"
  problem.
- Differentiability is already the assumption. An analog substrate
  whose forward pass is differentiable but whose precision is lower
  than IEEE-754 fits the system.
- Determinism and predictability — already Yantra design goals — are
  natural strengths of analog/neuromorphic hardware running known
  workloads.

The economic story is also better: analog hardware is harder to
commoditise than GPUs, so a vertically-integrated stack
(hardware + Yantra + Sutra) defends margin in ways "OS for someone
else's GPU" cannot.

## The CUDA/abstract-substrate relationship

A useful framing: Sutra's relationship to
hardware is roughly "compile to CUDA, conceptually need a CPU only to
orchestrate." This isn't tied to NVIDIA — the same applies to ROCm,
Apple silicon's Metal, and (eventually) any analog substrate. The
hardware-abstraction layer is small because the OS is asking the
hardware for one thing: run this fused tensor program.

Concretely, the runtime has a thin backend per substrate:

- `cuda_backend.su` — produces CUDA kernels from Sutra IR.
- `rocm_backend.su` — same for AMD.
- `metal_backend.su` — same for Apple.
- (Future) `analog_backend.su` — produces configuration for the
  analog accelerator and interprets its outputs.

The kernel and userspace do not change between backends. Only the
backend cares which substrate is underneath.

## Why analog computing matters even if Phase 3 never lands

Even if memristors and photonic compute don't pan out as commercial
substrates, the *posture* of being ready for them shapes the design
in useful ways:

- Forces the OS to assume the substrate is differentiable.
- Forces the OS to assume the precision may be lower than IEEE-754.
- Forces the OS to assume that exact bit-equality is rare; cosine
  similarity is what equality means at the edges.
- Forces the OS to keep the CPU at arms' length, so a future
  CPU-less system is not a rewrite.

These are all defensible architectural decisions on commodity GPUs
too. They just look more obviously correct on analog hardware.

## What we are *not* doing

- We are not building hardware in the next 12 months. The roadmap
  starts on commodity GPUs.
- We are not betting on a specific analog vendor. The plan is to be
  the *operating system* that runs on whatever substrate emerges,
  not to bet the company on a particular memristor maker.
- We are not promising performance numbers on Phase 3 hardware.
  Until that hardware exists in a form we can benchmark, claims
  about it are hand-wavy.

## Open questions

- **Multi-GPU scaling.** A real-world critical-systems appliance may
  need two or four GPUs. The architecture supports this in principle;
  the kernel role for "manage multi-GPU axon routing" is not
  designed.
- **GPU NUMA effects.** Multi-GPU boxes have non-uniform bandwidth.
  The fixed-allocation model has to account for which GPU a process
  lives on; cross-GPU axon traffic is not free.
- **Analog precision modeling.** For analog hardware to be a credible
  Phase 3 target, we need a precision model in the runtime that
  captures how analog noise affects beta-reduced tensor programs.
  This is research-grade work, not a v1 deliverable.
