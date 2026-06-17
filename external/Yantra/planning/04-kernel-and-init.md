# Kernel and init

## Boot order

```
power on
   │
   v
firmware (C, conventional)
   │
   v
bootloader (small native-Rust program)
   │   loads:
   v
GPU image (Sutra kernel + init system)
   │
   v
Sutra runtime takes over; CPU drops to orchestrator role
   │
   v
init Sutra program admits the standard service set:
   - filesystem bridge
   - display server
   - input router
   - network stack
   - browser/window manager
   - default shells / login surface
```

The CPU is doing real work for the first few tens of milliseconds and then
goes mostly quiet. It wakes up to:

- Run the resource manager logic (admit / evict / resume).
- Move bytes between RAM, storage, and GPU memory arenas.
- Talk to physical devices that have not been ported into Sutra (NICs,
  legacy peripherals).

## The kernel

The Yantra "kernel" is a Sutra program — really, a small set of Sutra
programs the runtime always boots and never evicts. It owns:

- **The axon router.** All inter-process axon traffic flows through a
  shared addressing fabric the kernel manages. Capability checks happen
  here.
- **The process table.** Mapping of process id → manifest, GPU slot,
  state-vector pointer.
- **Syscalls.** Each syscall is just an axon-typed function the kernel
  exposes to userspace. `read_file`, `write_file`, `open_socket`,
  `query_local_model`, etc. There is no `int 0x80`-style trap; a syscall
  is an axon hand-off to a known kernel role.
- **Capability codebook root.** The original rotation operators that all
  derived child capabilities trace back to.

The kernel does not have its own scheduler. The runtime's fused forward
pass *is* the scheduler — every tick, every Active process runs.

## Init: the systemd-shaped thing

Yantra needs an init system, but it should be tiny because:

- One hardware target family (GPU + analog later), not Linux's hardware
  zoo.
- One filesystem.
- One display system (the browser).
- No distro fragmentation.

Init is therefore "start the filesystem, start networking, start the
browser runtime, start the desktop." A small TypeScript program that
compiles to Sutra. Maybe a few hundred lines.

The systemd-style sprawl exists in Linux because Linux has a chaotic
ecosystem to paper over. Yantra has the opposite problem (very few
moving parts) so init can stay small without anyone arguing about it.

## What the kernel does *not* do

- **No paging or virtual memory** on the GPU side. Each process's GPU
  arena is a literal range of memory, fixed at admission time, freed at
  exit. There is no page table because there is nothing to page.
- **No threads.** Processes are units of allocation; concurrency within a
  process is whatever the Sutra program's tensor graph naturally
  parallelizes to.
- **No filesystem in the kernel.** The kernel exposes the filesystem
  bridge syscalls, but the actual file system code (the part that
  manages ext4/btrfs blocks on the disk) runs as a userspace Sutra
  process that the kernel admits at boot. If it crashes, init restarts
  it. The kernel itself is unaware of inodes.
- **No driver model in the modern sense.** Devices that do not speak
  Sutra natively talk to a small CPU-side shim that translates their
  output into axons before it ever reaches the kernel. The kernel only
  ever sees axons.

## Bootloader implementation reality

The bootloader is written natively in Rust, the same language as the
CPU-side orchestrator. It runs on bare metal before any Sutra runtime
exists, so there is nothing for a tensor program to execute on yet; the
job is firmware-shaped, not connectome-shaped. It does the minimum
needed to:

1. Probe the GPU and any analog accelerators.
2. Allocate the GPU memory arenas the kernel manifest asks for.
3. Load the Sutra kernel image into one of those arenas.
4. Hand control to the GPU runtime.
5. Drop into resource-manager mode.

Keeping the bootloader and the orchestrator in one systems language
(Rust) is deliberate: a single trusted CPU-side base is easier to
audit than a polyglot one, and the verification arguments only have to
reason about one boot-time language rather than a transpilation chain.

## What we will steal from Linux

The Linux project documents what works and what doesn't extremely well,
and some of those decisions just port over:

- **Process model basics.** PID-like handles, exit codes, parent/child
  ownership, unprivileged-by-default.
- **Permissions model.** Users, groups, capabilities — adapted so that
  capabilities are literal rotation operators rather than bitmasks.
- **File system semantics.** POSIX-ish enough that forensics tools work
  on a Yantra disk pulled from a dead box.
- **Init service definition shape.** `.service`-like manifests, except
  every "service" is a Sutra program with a fixed GPU footprint.

Linux's "do one thing well" philosophy is also a good fit, even though
the systemd-shaped half of Linux famously violates it. Yantra's "one
thing" is: transpile JS/TS into Sutra, run it, render WebGL. That is
the entire system from one angle.

## Open questions

- **Multiple GPUs.** What does the boot story look like on a 2-GPU box?
  Both kernels with a master? One kernel with NUMA-style awareness?
- **Hot-plug devices.** USB, removable storage, etc. The CPU-side shim
  story works, but the kernel needs a way to be told "a new device just
  appeared" without polling.
- **Recovery.** If a userspace process the kernel depends on (e.g. the
  filesystem service) crashes, what does init do? Probably restart, but
  what about cascading dependencies?
