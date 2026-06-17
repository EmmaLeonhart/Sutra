# Boot sequence

> **What this document is.** The explicit step-by-step of what
> happens when you turn on a Yantra appliance, from cold power to
> the connectome being live on the GPU. Written 2026-05-14 to fix
> a documentation gap that was letting `kernel/`'s Python prototype
> get conflated with what the real boot path looks like.
>
> **Bottom line.** The bootloader and the post-boot orchestrator
> are **necessarily compiled native code (Rust or C)**, not because
> Rust is fashionable but because the boot path runs before any
> interpreter exists. Python is dev tooling that demonstrates
> behavioural shape; it never appears in the boot path.

## The five stages

```
   ┌──────────────────────────────────────────────────────────────┐
1. │ Power on   →   CPU starts executing firmware (BIOS / UEFI)   │
   └──────────────────────────────────────────────────────────────┘
                                  ↓
   ┌──────────────────────────────────────────────────────────────┐
2. │ BIOS / UEFI   →   POST + locates the bootloader on disc      │
   │                   and loads it into RAM                       │
   └──────────────────────────────────────────────────────────────┘
                                  ↓
   ┌──────────────────────────────────────────────────────────────┐
3. │ Bootloader (Rust / C, in RAM)                                 │
   │   - Discovers the GPU                                         │
   │   - Reads the compiled Sutra kernel image off disc            │
   │   - Loads it into GPU memory                                  │
   │   - Initialises the Connectome Manager state                  │
   │   - Hands control to the Rust orchestrator                    │
   └──────────────────────────────────────────────────────────────┘
                                  ↓
   ┌──────────────────────────────────────────────────────────────┐
4. │ Rust orchestrator (CPU side, running)                         │
   │   - Loads the boot service set (kernel programs) onto GPU     │
   │   - Wires the axon router                                     │
   │   - Starts the GPU tick loop                                  │
   │   - Becomes the standing CPU-side companion to the GPU        │
   └──────────────────────────────────────────────────────────────┘
                                  ↓
   ┌──────────────────────────────────────────────────────────────┐
5. │ Connectome live on GPU                                        │
   │   - Sutra programs run as the connectome                      │
   │   - Axons flow between programs each tick                     │
   │   - Orchestrator handles disc↔RAM↔GPU moves on demand         │
   └──────────────────────────────────────────────────────────────┘
```

## Stage 1 — power on

The CPU begins executing firmware (BIOS or UEFI). This is identical
to any other computer; Yantra has no special requirements at this
stage. The firmware is the vendor's, not ours.

## Stage 2 — BIOS / UEFI loads the bootloader

The firmware locates the bootloader on disc (via the conventional
boot order or UEFI boot entries) and loads it into RAM. The
bootloader at this point is just a sequence of bytes the firmware
copies; it has not begun executing yet.

**Yantra-specific: the bootloader is a Yantra binary, not GRUB.**
GRUB knows how to load a Linux kernel image; it doesn't know about
loading a Sutra kernel onto a GPU. The Yantra bootloader is its own
small Rust-or-C binary.

## Stage 3 — bootloader runs

This is the first piece of Yantra-authored code that executes. It
runs **on the CPU, in RAM, against bare hardware** — no operating
system below it, no interpreter, no runtime. Every constraint of
"writing code that runs at boot" applies: no `malloc`, no standard
library beyond what's compiled in, no syscalls (there's no kernel
to call into).

The bootloader's job:

1. **Discover the GPU.** Probe PCI, identify the device, verify
   it's a Yantra-supported model.
2. **Initialise the GPU.** Bring the device up to a state where it
   can accept commands and host data transfers.
3. **Read the compiled Sutra kernel image off disc.** The image is
   a known artifact built ahead of time — the output of the Sutra
   compiler with the kernel programs as input. It lives at a known
   location on disc (the Yantra equivalent of `/boot/vmlinuz`).
4. **Load the image into GPU memory.** DMA or PCIe writes to copy
   the compiled kernel program bytes into device memory.
5. **Initialise the Connectome Manager state.** The initial
   process table (which programs are admitted at boot), the axon
   router state (which roles route where), the storage-tier
   table (everything else is on disc, nothing in RAM yet beyond
   the bootloader itself).
6. **Hand control to the Rust orchestrator.** The orchestrator is
   either part of the bootloader binary or loaded by the
   bootloader as a second-stage payload. It begins running on the
   CPU and the bootloader's job is done.

**Why Rust (or C): no interpreter exists at this stage.** Python
is interpreted — the Python interpreter is itself a program that
runs on top of an OS kernel that has already loaded its
dependencies. At stage 3 there is no OS, no kernel, no
interpreter. The bootloader's bytes execute directly on the CPU.
A Python "bootloader" is a category error — there is nothing for
it to interpret it.

## Stage 4 — Rust orchestrator running

The orchestrator is the standing CPU-side companion to the GPU.
Its job is what the planning corpus has been calling the
**Connectome Manager**:

- Decide which programs live on disc, in RAM, on GPU at any
  moment
- Move programs disc→RAM→GPU (load) and GPU→RAM→disc (offload)
- Wire the axon router (which read_roles each program holds, which
  write_roles each program holds, who routes to whom)
- Enforce capability checks
- Wrap MMIO peripherals as axon channels (the §3.5 "hardware
  boundary" pattern from `paper/paper.md`)
- Start the GPU tick loop and keep it running

**This is what the Python in `kernel/` is a behavioural reference
for.** Not a smaller version of the bootloader — the Python has no
relationship to the bootloader at all — but a reference for what
the Rust orchestrator's API surface looks like once you're past
boot. `kernel/init.py` shows admission control; `kernel/router.py`
shows axon routing with capability check; `kernel/services.py`
shows how Sutra-compiled `.su` programs get wrapped as runnable
processes. The Rust port reimplements the same shape.

## Stage 5 — connectome live on GPU

Steady state. Sutra programs are running as the connectome on the
GPU. Axons flow between programs at each tick. The orchestrator
sits on the CPU side, handling storage-tier moves and hardware
boundary wrapping. This is the running-OS state.

## What's implemented today vs. what isn't

| Stage | Yantra-side status |
|---|---|
| 1 — Power on | N/A (vendor firmware) |
| 2 — BIOS/UEFI loads bootloader | **v0.0 shipped + verified booting in QEMU 11.0.50 (2026-05-14).** `bootloader/` is a Rust crate that builds a multiboot1 ELF binary via `cargo build --release`. QEMU's `-kernel` flag boots multiboot1 ELFs directly — no disk image, no BIOS sector. |
| 3 — Bootloader runs | **v0.4 shipped + verified (2026-05-14).** `bootloader/src/main.rs` boots in QEMU, prints the banner, enumerates the PCI bus, **reads the QEMU VGA's BAR0 + writes a 100x640 BGRA pixel gradient to the linear framebuffer at 0xfd000000**, **copies a 61-byte sentinel kernel-image placeholder to GPU memory at 0xfd100000 and reads back to verify**, hands off to a **stub orchestrator** that prints proof-of-life, then transitions to long mode (PML4+PDP identity-mapped 1 GiB, PAE on, EFER.LME set, far-jumps to 64-bit code segment) and prints "Long mode active" from 64-bit asm. v0.2 (real Rust in long mode) is blocked by QEMU's `-kernel` flag requiring 32-bit ELFs (multiboot2 needs GRUB to boot); v0.5+ (real Sutra kernel execution) is blocked on actual GPU passthrough (VFIO on Linux + spare GPU). |
| 4 — Rust orchestrator running | Python prototype only (`kernel/` in this repo). Rust port is the TODO. |
| 5 — Connectome live on GPU | Per-program Sutra compute works (`kernel/services.py` `SutraService`). Multi-process simultaneous execution on a single GPU is now partially shipped via Sutra v0.4.0 `MultiProcessRuntime` (one Python process, N programs sharing one `_VSA`); per-process GPU memory arena carve-outs still upstream. |

## Running Yantra inside a VM (no real GPU)

Emma asked 2026-05-24: *can a VM run on bare metal and simulate a GPU
even without a real one?* Two separable axes — the boot/orchestration
path and the GPU compute path — answer that question differently, and
the practical answer for VM-only development hinges on which path you
need.

### What works in a VM today

**The whole boot + orchestrator path is VM-testable, no GPU needed.**
This is what `bootloader/` already exercises: QEMU 11.0.50 boots the
multiboot1 ELF, runs Stage 3 setup (PCI scan, stub framebuffer write,
sentinel image copy, long-mode transition). Every artifact described
in stages 1–4 above is reachable in a vanilla QEMU run on a CPU-only
host. Multiboot, paging, long-mode, the orchestrator handoff — these
are all CPU-only mechanisms; the absence of a real GPU does not
prevent any of them.

**Sutra runs on CPU.** The PyTorch substrate has a CPU fallback
(`device='cpu'`), and the Sutra compiler emits the same tensor-op
graph either way. A VM with no GPU can run *the whole stack
functionally* — every kernel program, the calculator, echo, the
terminal, the GUI's substrate-side field/flip/tint — by pointing the
substrate at the CPU. Correctness is preserved; only throughput is
sacrificed. This is the right configuration for behavioural testing,
regression gates, and developer iteration on a machine without a
workstation GPU.

### What does NOT work in a VM today

**CUDA compute inside an ordinary VM.** QEMU's emulated display
adapters (`stdvga`, `cirrus`, `virtio-gpu` in its default 2D and
3D-OpenGL configurations) do not expose a CUDA device. There is no
practical CPU-emulated CUDA backend either — NVIDIA's runtime
depends on actual NVIDIA silicon. So the real-GPU compute path
(Sutra programs running on `device='cuda'`, the production
performance posture) is not reachable inside an ordinary VM.

The standard unblock is **GPU passthrough**: VFIO on a Linux host
with a spare GPU. The host binds the GPU to VFIO, the VM gets the
bare device, and CUDA inside the VM is indistinguishable from
running on the host. The cost is needing a Linux host *and* a spare
physical GPU — the host can't share its only GPU with itself.
Emma's current setup doesn't satisfy this (the RTX 4070 is the
host's, fine for running the kernel directly on the host, not for
VM passthrough).

### Open: paravirtualised CUDA paths

Three approaches exist in principle that, if any matured into a
usable shape for our case, would change the answer above. None is
plug-and-play today; they are noted here so a future session can
revisit if the situation changes.

- **virtio-gpu Venus / VirGL.** virtio-gpu is QEMU's paravirtualised
  GPU device. The Venus extension forwards Vulkan calls from the
  guest to the host's Vulkan stack. This gives the guest
  hardware-accelerated graphics, but it is **Vulkan, not CUDA**, and
  CUDA cannot be reached through it. Useful for the eventual
  browser/WebGL renderer (milestone 3); not useful for the substrate.
- **NVIDIA vGPU.** NVIDIA's licensed virtual-GPU product partitions
  a real datacenter GPU into VM-attachable slices. The vGPU does
  expose CUDA. Requires a vGPU-capable card (datacenter SKUs: A100,
  H100, etc.; consumer cards including the RTX 4070 are **not**
  supported) plus an active NVIDIA AI Enterprise / vGPU licence.
  Practical for a deployed system on hyperscaler infrastructure;
  not practical for individual developer machines.
- **CUDA-API forwarding shims (`rCUDA`, GVirtuS, GPU-Shim-style
  forwarders).** Research artifacts that intercept CUDA API calls
  in the guest and ship them to a remote-or-host CUDA runtime over
  RPC. None has shipped a stable consumer-grade story for arbitrary
  CUDA workloads, and the latency hit makes them inappropriate for
  the per-tick connectome. Not currently a real option.

The summary that should not drift: **the boot/orchestration path is
VM-testable on any host; the substrate is CPU-runnable in any VM;
CUDA compute in a VM needs either passthrough on a Linux host with a
spare GPU, or vGPU on supported datacenter silicon.**

### Implication for developer setup

| Configuration | Boot/orchestrator | Substrate (functional) | Substrate (CUDA) |
|---|---|---|---|
| CPU-only laptop / VM | ✓ (QEMU) | ✓ (`device='cpu'`) | ✗ |
| Workstation, 1 GPU (Emma) | ✓ (QEMU) on host | ✓ on host | ✓ on host, ✗ in VM |
| Workstation, 2+ GPUs, Linux | ✓ in VM | ✓ in VM | ✓ in VM (VFIO passthrough) |
| Datacenter / vGPU instance | ✓ in VM | ✓ in VM | ✓ in VM (licensed vGPU) |

The minimal "real Yantra" target — bare-metal-boot to a working
connectome on real silicon — sits at the third configuration, not
the first. A VM-only developer on a CPU-only host can reach
functional parity but not the production performance posture; that
is enough for correctness work and regression gates, not enough for
characterising the OS under real-GPU load.

## Cross-references

- `01-architecture.md` § "The kernel is a Connectome Manager" and
  § "CPU side: small, Rust, orchestrator" — the architectural
  framing.
- `03-process-lifecycle.md` — admit / active / cold-store /
  evict, the lifecycle the orchestrator manages.
- `17-memory-model.md` — the disc / RAM / GPU storage tiers, all
  the open hard problems around how memory works in Yantra.
- `20-lazy-axon-evaluation.md` — the axon-routing requirement that
  makes the connectome scale.
- `kernel/README.md` — what the Python prototype actually
  implements vs. what is stubbed.
- `paper/paper.md` § 3.5 — hardware boundary (interrupts, MMIO).
