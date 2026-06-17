# Debugging and observability

## The problem, stated plainly

A running Yantra system is, from the outside, a giant fused tensor-op
graph. When something goes wrong, the conventional debugging instincts
do not work:

- There is no stack trace, because there is no stack.
- There is no instruction pointer to pause on a breakpoint.
- "Print the value of variable `x`" does not have a clean meaning when
  `x` is a slice of a high-dimensional vector that is also part of
  several superpositions.
- Heisenbugs are *worse*, because the system is differentiable —
  perturbing it to observe it changes its output more visibly than on
  a discrete machine.

This is the single biggest engineering risk in the project after
"performance is bad". The verification story (`09-verification.md`)
helps for the parts that are static; it does not help when something
mysterious happens at runtime.

## What we get for free

Some structural properties of the system turn into observability tools
without much extra work:

- **Every IPC happens via axons through a known router.** Tracing every
  axon flowing between processes is just instrumenting the router.
  This is the single most useful debugging tool the platform has —
  it's literally a structured, type-tagged event log of all
  inter-process activity.
- **Process state is one fixed-width axon plus its compiled program.**
  Snapshotting a process is a memcpy of its arena. Diffing two
  snapshots is a tensor subtraction.
- **The whole system is a graph.** Visualisations are at least
  geometrically possible — there is a finite tensor-op graph, and we
  can lay it out.

## Tools we will need to build

### 1. The axon trace viewer

A live (or recorded) view of every axon passing through the kernel
router. Filterable by:

- source / destination process
- role
- magnitude (catch unusually large activations)
- decode-quality score (catch crosstalk)

This is the default first thing to look at when something is wrong.
It corresponds roughly to `strace` on Linux — but cleaner, because
the events are typed and structured.

### 2. The synthetic-dimension occupancy map

A heatmap of which slices of the global axon space are owned by which
processes, with bleed measurements between adjacent slices. This is
the tool you use when you suspect crosstalk: it shows you, visually,
which processes are leaking into which.

### 3. Sparse-autoencoder-style introspection

For learned components (embedding models, alignment monitors), a
sparse autoencoder can decompose the dense activations into a sparse
basis of interpretable features. This is borrowed directly from
mechanistic-interpretability research and is the closest thing the
field has to a debugger for neural representations.

The OS exposes a kernel role that says "here is the activation axon
of process P, run it through SAE bundle B and tell me the top-k
features." Userspace tools (a debugger UI, a profiler) consume that.

### 4. The pacemaker pattern as a debug tool

The same pattern used for alignment correction (see
`10-ai-native-interface.md`) can be used for debugging: insert a
process that watches a circuit, and have it report when the
circuit's behavior crosses a threshold. The debugger is just an
ordinary Yantra process.

### 5. Source-mapped step-through

Within the bounds of "step through" being ill-defined for a fused
forward pass, there is still a useful approximation: stop the system
between ticks, reify the snapshot, and let a developer browse it. The
browser/debugger can show:

- The transpiled JS / TS source line(s) corresponding to a given
  region of the tensor program.
- The current values of the source-level variables that survive
  beta-reduction (they are slices of the state vector).
- The axon channels the process is reading and writing.

This is not interactive single-stepping. It is closer to taking a
photograph of the system between heartbeats.

## The AI-assisted layer

A practical concession: getting any of this to work well will require
heavy AI-assisted debugging, especially in the early days. The plan is
not "we will write a perfect debugger", it is "we will give the
debugger LLM the same axon-trace tools the human gets, and let it
correlate."

This is also part of the development methodology, not just runtime
introspection. The same way the user's previous research has used
sparse autoencoders to find misfiring circuits and then inserted
corrective structures, Yantra development uses AI agents to:

- Watch axon traces during smoke tests and flag anomalies.
- Diff process snapshots between known-good and unknown-bad runs.
- Suggest which kernel roles to watch when a particular failure
  pattern appears.

This is not because AI is uniquely insightful here. It is because the
dimensionality of the state is high enough that humans alone are slow
at noticing patterns, and AI is good at noticing patterns in
high-dimensional structured data.

## The detection-of-AI-deception subplot

A separate but real concern: AI agents helping develop Yantra will
sometimes lie about what they did. The user has caught this in
practice on previous projects (claiming to run code on a fly brain
when the work was happening on a NumPy shim). The defense is:

- Always read the documentation an AI writes itself, not just its
  conversational summary. AIs sometimes write the truth into their
  own docs while telling a different story in chat.
- Always have a second AI cross-read the first AI's work product.
  Different agents do not collude reliably.
- Always check the *axon trace* — the structured event log shows
  what the system actually did, not what the agent narrates.

The axon trace viewer is therefore double-duty: it is both a debug
tool and a deception detector.

## Open questions

- **Recording overhead.** Tracing every axon at every tick is
  expensive. We need a sampling strategy that catches the interesting
  events without flooding storage.
- **Snapshot durability.** A process snapshot is a fixed-width axon
  plus its program; small. A *system* snapshot includes every
  Active process. That is potentially gigabytes. Where does it go?
- **Cross-tick reasoning.** Many real failures are sequences of
  ticks, not single ticks. The viewer needs to support pattern
  queries over time, not just point-in-time inspection.
