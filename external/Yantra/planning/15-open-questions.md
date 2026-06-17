# Open questions

A consolidated list of design decisions still unmade. Organised by
concern rather than urgency. Each entry should eventually move to
"resolved" or "deferred" with a rationale.

## Axon model

- **Default axon width.** Embedding models vary (768 / 1024 / 4096).
  Pick one and run converters at the edges, or carry width in the
  type. *Lean: pick one, but make the runtime tolerate
  width-mismatched inputs by zero-padding or projection.*
- **Provenance role default.** Should every axon carry a provenance
  role by default? Useful for debugging and for the alignment
  monitor; costs codebook entries. *Lean: yes, with a small fixed
  size for it.*
- **Per-tenant codebooks vs global namespaced codebook.** Real
  partitioning question for multi-process safety. *Lean: per-tenant
  for capability hygiene.*
- **Higher-order axons.** Currently programs cannot be passed as
  fillers. Lifting this is research; not v1.

## Process lifecycle

- **Resume latency.** Is there a "warm" tier between Active and
  Cold? *Lean: yes — same RAM, but the program image stays in GPU
  memory, only state evicts.*
- **Working-set tracking.** Self-report from the process vs runtime
  monitoring. *Lean: runtime monitoring at the axon-channel level.*
- **Live migration across GPUs.** Probably not v1, but the manifest
  format should not preclude it.

## Kernel and init

- **Multi-GPU boot story.** Master kernel + slaves vs. one kernel
  with NUMA-style awareness. Open.
- **Hot-plug devices.** Notification path from CPU shim to kernel
  without polling. Open.
- **Crash recovery.** When a userspace service init depends on
  crashes, what does init do? *Lean: restart with backoff;
  cascading dependencies declared in manifests.*

## Filesystem bridge

- **Mounting embedded representations as virtual files.** `cat
  /docs/foo.md.embed` returning the cached embedding bytes.
  Probably ship.
- **Sparse / chunked verbatim reads.** A 10 GB log file in verbatim
  mode is unworkable. The syscall surface needs streaming.
- **Cross-FS mounts (NFS, S3).** Probably the same userspace-process
  trick. Each adds embedding-cache complications.

## GUI

- **WebGL precision on analog substrates.** Diverges from spec; need
  a conformance-testing strategy.
- **Animation budget.** Per-page, or window-manager-owned?
- **Browser product name.** Open.

## Transpilers

- **Source maps surviving JS → Sutra → tensor-program.** Required
  for any kind of step-through debugger UX.
- **Incremental / cached transpilation.** Compile-on-install is
  fine, but recompiling on every launch is unacceptable.
- **JS standard-library coverage.** Adequate for reactive UI;
  spotty on data-manipulation. Need to draw a line and document.

## Security and isolation

- **GPU side channels.** Timing/cache leaks across process arenas.
  Mitigations are research. Need a defensible v1 default
  (probably: explicit lockstep within a tick).
- **Embedding-model identity attestation.** Signature on every
  model bundle the bridge accepts.
- **Sandbox UX.** Granting an app capability to "this folder only"
  is intuitive on a conventional OS. Same UX in a capability-and-
  rotation world needs work.

## Verification

- **Compiler qualification.** What does a certified Sutra compiler
  look like? Self-hosted bootstrap with a verified microcompiler at
  the bottom?
- **Polynomial-Kleene-logic SMT toolchain.** May need to be ours;
  off-the-shelf SMT solvers don't speak this dialect.

## AI-native interface

- **Embedding-model versioning across the FS.** Stale `semantic`
  caches when the embedding model changes. Need a defensible
  "regenerate on demand" plus migration story.
- **Cross-process activation steering capabilities.** The pacemaker
  reads other processes' internal activations. Default should be
  conservative.
- **Reflective channel discovery.** Allowing a model to introspect
  the available axon channels borders on reflective programming;
  needs a careful design.

## Debugging and observability

- **Trace recording overhead.** Sampling strategy that catches
  interesting events without flooding storage.
- **System snapshot durability.** A *system* snapshot can be
  gigabytes. Where does it live?
- **Cross-tick pattern queries.** The trace viewer needs a query
  language for sequences over time.

## Hardware

- **Multi-GPU NUMA.** Cross-GPU axon traffic is not free; manifest
  format needs to express GPU affinity.
- **Analog precision modeling.** Required for a credible Phase 3
  story. Research-grade.

## Markets and licensing

- **First lighthouse customer.** Defense prime? Industrial? Research
  partnership?
- **Open-source surface vs proprietary.** Default is "OS open,
  hardware/services closed." Specific subsystems may want
  dual-licensing.
- **Compliance roadmap order.** FIPS 140-3, Common Criteria,
  DO-178C — order matters; not locked.

## Memory model

The single largest open area of the design. Tracked in detail in
`17-memory-model.md`; the highlights for this index:

- **Scratchpad arena vs synthetic-dim block.** Currently conflated;
  large-scratchpad-small-state processes are awkward.
- **Eviction granularity and resume latency target.** v1 lean is
  atomic eviction with per-process resume-latency manifests; the
  arithmetic on whether common hardware actually meets those budgets
  is not done.
- **MMIO and interrupt round-trip cost.** Flagged in the v1 paper
  review (post 2393): tight control loops talking to MMIO registers
  pay a CPU↔GPU round-trip per access. The architecture *bounds*
  rather than eliminates this; the bound is not yet measured.
- **Cold-store integrity.** Evicted processes need their state
  signed-on-evict and verified-on-resume, or the capability story
  is broken by a hostile CPU-side component. Latency budget is
  unclear.
- **GPU memory side channels.** Cross-ref `08`. Lockstep within a
  tick is the v1 default but degrades the no-degradation property.

## Cross-cutting

- **The naming.** Yantra is the OS. Sutra is the language. Future
  naming for: the browser, the runtime, the compiler, the appliance,
  the SDK, the marketplace. All TBD; staying within the Sanskrit
  naming convention is the working policy.
- **The thing-beyond-an-agent name.** The user is reaching for a
  word for "the AI on Yantra — not an agent, more like a mind whose
  cognition and action are continuous." Not yet named.
