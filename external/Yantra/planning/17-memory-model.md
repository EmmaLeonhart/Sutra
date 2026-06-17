# Memory model — open hard problem

> **This is a placeholder for the long-term hard problem.** Yantra's
> memory story is *not* worked out at the level of the other planning
> docs. This file exists so that the open questions live in one place
> rather than scattered, and so future work can find them. Do not cite
> this document as evidence the problem is solved — it is the
> opposite: the inventory of unsolved questions.

## Why this is its own document

The other planning docs treat memory as something the runtime
"handles." This is the part of the design where that hand-wave costs
the most when a reviewer pushes on it. Three concrete pressures make
memory the long pole:

1. **GPU memory is the compute substrate, not just storage.** Every
   admitted process has its compute state living in GPU memory as
   part of the tensor-op graph. There is no separation between
   "where the program is" and "where the program runs."
2. **RAM is cold-store for suspended processes.** When the resource
   manager evicts a process from GPU, it serialises that process's
   state vector + synthetic-dimension block into RAM. The serialise
   / deserialise pair has to be exact (no precision drift on
   resume), fast (eviction is not free, but it cannot dominate the
   admission decision), and identity-stable (capability operators
   survive eviction).
3. **The hardware boundary** — interrupts, MMIO, DMA transfers from
   peripherals — happens on the CPU side and crosses into the GPU
   world. Some round-trips remain; the architecture *bounds* them
   rather than eliminating them, and the cost of those bounded
   round-trips has to fit inside the latency budget the OS promises.

## Open questions

### Process-side memory

- **What does a Sutra program's view of memory look like?** Sutra has
  fixed-width state vectors and synthetic-dimension blocks. It does
  not have heap. Working sets larger than the state vector either go
  through axon-streamed IO (`read_file` syscalls returning chunked
  bytes-axons) or live in an explicit "scratchpad" arena. We do not
  yet have a worked design for the scratchpad.
- **How does scratchpad accounting work in the install manifest?**
  Compute + synthetic-dimension footprint are already declared. A
  scratchpad budget probably needs to join them, but its semantics
  (peak vs steady-state, deterministic vs bounded growth) are open.
- **Is there a per-process arena distinct from the synthetic-dim
  block?** The current answer is "no, the synthetic-dim block IS the
  scratchpad" — but that conflates compute state with working memory
  in ways that bite when a process wants a large scratchpad without
  a large state vector.

### Eviction and cold-store

- **Eviction granularity.** Is a process atomic (evicts whole) or can
  parts go cold while parts stay hot? *Lean: atomic for v1.* The
  finer-grained eviction story is research.
- **Resume latency target.** What is the budget for an evict-then-
  resume round-trip? Defense-critical control loops can afford
  ~microseconds; AI-pipeline processes can tolerate milliseconds.
  This needs to be a per-process declaration in the manifest, with
  the resource manager refusing admission of a process whose declared
  budget the current hardware cannot meet.
- **Serialisation format.** GPU → RAM transfer is bytes-shaped; the
  serialisation needs to round-trip bit-exact, with no precision
  drift in low-order bits of the state vector. Float32 to bytes is
  trivial in principle; the question is whether the resume restores
  *exactly* the activation pattern the process was running with
  before evict.
- **Cold-store storage shape.** RAM is fast; persistent storage is
  slow. Can a cold-stored process spill further to disk if RAM is
  also full? *Lean: no in v1 — the appliance is sized so it does not
  need to.* For multi-tenant deployments this answer probably
  changes.

### The CPU/GPU boundary

- **Interrupt delivery from peripherals.** A network packet, a sensor
  read, a timer fire — all arrive at the CPU. The CPU shim has to
  turn these into axons the kernel can route. Cost of this turn is a
  CPU-GPU round-trip per event; the architecture is "batch these at
  a tick boundary" but the tick rate and the batching policy are
  not yet worked out.
- **MMIO patterns.** Memory-mapped IO is a CPU-world concept. For a
  device whose registers live in MMIO space, the Yantra answer is
  "wrap it in a userspace driver process on the CPU shim side that
  re-exports an axon channel" — but the latency cost of this
  per-register-access wrapping is not measured, and a tight control
  loop talking to MMIO registers will see the round-trip cost on
  every access. This is the part the v1 review (post 2393) flagged
  and that is genuinely open.
- **DMA from peripherals into GPU memory.** Modern hardware supports
  this; Yantra's process model assumes the kernel mediates all
  axon-shaped IO. The intersection — DMA-direct-to-GPU-memory while
  still respecting the kernel's capability check on the receiving
  process — needs design.
- **Clock domain crossings.** The CPU shim's wall clock and the GPU's
  tick clock are separate. Processes that need wall-clock time
  (timestamps, deadlines, log timestamping) need a defined,
  bounded-jitter path to it.

### Multi-GPU and hardware roadmap interactions

- **Cross-GPU axon traffic.** Already an open question in
  `15-open-questions.md`. From the memory side: a cross-GPU send is
  a GPU→host-RAM→GPU pair of copies. This needs to be priced and
  the manifest format needs to express GPU affinity.
- **Analog substrate memory.** `13-hardware-roadmap.md` sketches a
  future analog tier. Memory on analog substrates does not match
  GPU memory in any of its assumptions (no bytes, no exact
  serialisation, no addressable randomness). The Phase 3 story for
  memory is research-grade and not addressed here.

### Security and side channels (cross-ref §08)

- **GPU memory side channels across processes.** Timing leaks
  through shared caches; voltage / DVFS leaks; bus contention.
  These are real on conventional GPUs and the v1 default is
  probably "lockstep within a tick" — but the cost of lockstep is
  the loss of the no-degradation property under load. Where the
  trade-off lands is open.
- **Cold-store integrity.** A process evicted to RAM and then
  resumed: is its state vector signed? If a hostile component on
  the CPU side could modify cold-stored state, the capability
  story is broken on resume. A signature-on-evict + verify-on-
  resume pair is the candidate; it has to fit inside the latency
  budget.

## What this document does NOT commit to

This file is the inventory, not the answer. None of the leans above
should be cited in `paper/paper.md` as committed design. The paper's
job is to be explicit about which of these are open. If a question
moves from open to committed, it moves out of this file and into
the relevant numbered planning doc, with a one-line note in
`15-open-questions.md`.

## Cross-references

- `01-architecture.md` — the layer cake, where the
  memory-as-compute substrate lives.
- `03-process-lifecycle.md` — the evict/resume protocol, where
  the cold-store side of the story is staged.
- `08-security-and-isolation.md` — the side-channel section is
  the corresponding security concern.
- `13-hardware-roadmap.md` — the analog substrate trajectory
  that breaks current memory assumptions.
- `15-open-questions.md` — duplicated open-questions index that
  links back here.
