# Process lifecycle

## The states

```
            install
              │
              v
    +-------------------+
    |   Manifested      |   compiled .su image, GPU footprint declared
    +-------------------+
              │
        launch│
              v
    +-------------------+    evict     +---------------+
    |     Active        | ──────────▶ |   Cold (RAM)  |
    |  (running on GPU) | ◀────────── |    inactive   |
    +-------------------+    resume    +---------------+
              │                              │
         exit │                              │ exit
              v                              v
            Gone                           Gone
```

Every process in Yantra is in exactly one of three states: **Manifested**
(installed, not yet launched), **Active** (running on the GPU with its
declared compute and synthetic-dimension allocation), or **Cold** (its
state has been serialized to RAM, freeing the GPU slot for another
process).

There is no "partially scheduled" state. There is no "preempted but warm"
state. A running process either has its entire allocation or it has none.

## Invariants

These are the properties the runtime is meant to guarantee:

- **No degradation.** Adding processes to the *Active* set does not slow
  any existing *Active* process. Until the GPU is full, throughput per
  process is constant.
- **Admission, not throttling.** When the GPU is full, new launches fail
  cleanly — they do not steal compute from running processes. Failure is
  the system's congestion signal, not jitter.
- **Bounded eviction cost.** The cost of moving a process from *Active*
  to *Cold* is bounded by `O(state_width + program_size)` — proportional
  to the process's declared footprint, not to how long it has been
  running.

## What "Active" means materially

An Active process owns:

- A fixed slice of GPU memory for its tensor state.
- A fixed block of synthetic dimensions in the global axon space (its
  "address book" of role-fillers).
- A position in the runtime's tensor-op graph — its forward pass is
  fused into the system-wide pass that runs every tick.

There is no per-process scheduler. The system runs a single fused tensor
program every tick that includes every Active process. Processes that
need to wait do so by emitting a "no-op" axon and consuming inputs only
when they arrive.

## Cold processes

Cold processes live in conventional RAM. Their state is serialized as:

- Their final pre-eviction axon (the fixed-width state vector).
- Their compiled program image (immutable, often shared between many
  cold processes that ran the same binary).
- Their role codebook deltas — the rotations and fillers they had bound
  beyond the system defaults.

Resume reverses this: copy state back into the GPU arena, splice the
program back into the global pass, and re-link any axon channels.

## Who decides

The **resource manager** (small CPU program) is the only thing that
issues admit / evict / resume decisions. It:

- Reads a priority hint from the process's manifest (`critical`,
  `interactive`, `background`).
- Tracks a working set: how recently each Active process actually
  consumed input axons.
- Evicts the lowest-priority idle process when a higher-priority launch
  is requested.
- Refuses to evict anything marked `critical`, even if that means
  refusing the new launch.

For a defense or aerospace target the priority hint is essentially the
certification artifact — `critical` processes are pre-allocated at boot
and never moved. Everything else is fair game.

## What this rules out

- **Forking** in the Unix sense. A process can spawn a child, but the
  child is a separate Sutra program with its own manifest and its own
  allocation request that the resource manager has to admit.
- **Time-sharing the GPU between processes.** Either a process is in or
  it is out. The "tax" of running 50 processes is the upfront GPU
  budgeting, not a runtime context-switch cost.
- **Long-running, unbounded mutation.** Process state is a fixed-width
  axon. Programs that want to remember more than fits go through the file
  system, like everywhere else.

## Open questions

- **Resume latency.** Roundtripping a process through RAM is fast in
  conventional terms (seconds at worst) but slow compared to GPU ticks
  (milliseconds). Is there a "warm" tier — same RAM, but the program
  image is already in GPU memory?
- **Working-set tracking.** Does the resource manager monitor axon
  channel activity, or does each process self-report? Self-reporting is
  cheaper but trusts the process; channel monitoring needs runtime
  hooks.
- **Live migration.** Can a process be moved from one GPU to another in
  a multi-GPU box without a full eviction round-trip? Probably not v1,
  but the manifest format should at least not preclude it.
