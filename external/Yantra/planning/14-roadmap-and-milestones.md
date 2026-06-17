# Roadmap and milestones

This is the planning-level roadmap, not a project schedule. It
describes the order operations should land in, with each milestone
shippable and demoable on its own. Time estimates are deliberately
absent; what matters is the ordering and the success criterion at
each step.

## Phase A — Foundations (the things that have to exist before any
demo)

Goal: a multi-process Sutra runtime running on Linux today, with
fixed allocations and the axon model proven in microcosm.

A1. **Multi-process Sutra runtime with fixed GPU slices.**
   Success criterion: launch N independent Sutra processes, each
   declares a footprint, and the runtime guarantees frame timing
   for all of them up to GPU saturation. Adding the (N+1)th, if it
   doesn't fit, fails admission instead of degrading the others.

A2. **Axon model + IPC implementation.**
   Success criterion: two Sutra processes exchange axons through a
   kernel-router-style intermediary; capability-shaped roles
   actually gate access; crosstalk between unrelated processes is
   measurably bounded.

A3. **Filesystem bridge.**
   Success criterion: `read_file` / `write_file` syscalls operating
   in `verbatim` and `semantic` modes, against a real ext4 mount.
   Embedding cache lives in sidecar files.

A4. **JS / TS → Sutra transpiler hardening.**
   Existing transpiler exists. What's needed: the flow-object
   pruning pass, a minimal-viable-UI-subset documentation, and a
   benchmark harness that catches regressions in transpiled-program
   size.

## Phase B — "Sutra Real-Time Shell" (the first thing worth showing)

Goal: a usable shell + window-manager-like environment running on
Linux as a guest, demonstrating the predictability claim
end-to-end.

B1. **Sutra shell as a Linux process.**
   A long-lived Linux process hosting the Sutra runtime. From the
   user's point of view it is "yantra-shell" launched from the
   Linux desktop; from inside, it is the world.

B2. **Multi-window demo.**
   Several "applications" running simultaneously inside the shell.
   At minimum: a clock, a file browser, a system monitor, and a
   local-AI chat window. All written in TS, compiled to Sutra,
   running with fixed allocations.

B3. **The "no degradation" demo.**
   Launch one application, measure its frame time. Launch nine more.
   Show that the first one's frame timing is unchanged — flat line
   on the graph. This is the single most important demo Yantra
   has, because it is the one a defense customer will care about
   most.

B4. **Axon trace viewer.**
   The first observability tool. Live view of axons flowing between
   the running applications.

## Phase C — Real boot

Goal: Yantra boots its own kernel, not piggybacking on Linux.

C1. **Bootloader (small C).**
   Loads a Sutra image onto the GPU. Hands off.

C2. **Kernel + init.**
   The Sutra kernel program; init admits the standard service set.

C3. **Networking + display server + input router.**
   The minimal services for an interactive system, written as
   Sutra programs admitted at boot.

C4. **Boot from cold metal.**
   A reference machine boots into Yantra without Linux underneath.
   This is the milestone that turns Yantra from "a runtime on
   Linux" into "an OS."

## Phase D — Reference appliance

Goal: a physical box you can sell.

D1. **Hardware integration.**
   A specific server platform, validated against Yantra. CPU/GPU/
   storage/network components confirmed. Shippable BOM.

D2. **Certification work begins.**
   Pick the first target (most likely DO-178C-shaped or Common
   Criteria depending on the lighthouse customer). Produce the
   verification artefacts the audit will ask for.

D3. **First lighthouse customer.**
   A real deployment with a name attached. Pilot, not GA.

## Phase E — AI-native applications

Goal: turn the AI-native interface into product.

E1. **Local-model integration as a kernel service.**
   The OS ships with a default embedding model and a default LLM
   slot, both running as ordinary Yantra processes. Other
   applications consume them by capability.

E2. **Alignment pacemaker as a userspace tool.**
   Compile-and-launch a pacemaker for an arbitrary local model.
   Document the workflow.

E3. **Connectome-driven processes.**
   Run a fly-connectome control loop as a Yantra process, exposed
   via a controller-style API. This is the substrate-independence
   demo: the same OS that runs a transformer-based assistant can
   run a biologically-grounded controller.

## Phase F — Forward-leaning / research

This is the "if Phase E succeeds" tail. Not committed.

- Analog/neuromorphic backend for the runtime.
- WASM compatibility hardening; aim for Figma-class apps.
- Self-hosted Sutra compiler (the compiler compiled by Sutra).
- Compiler qualification for certification scope.

## What lights the path

The single best forcing function for the early phases is **the
no-degradation demo**. Everything in Phase A and B exists to make
that demo persuasive. If we can stand up a graph that shows ten
processes running simultaneously with constant per-process frame
time, every subsequent phase is easier to fund and easier to recruit
into.

If something in Phase A turns out to be much harder than expected
(e.g., the crosstalk story doesn't actually hold up under the
multi-process workload), it's worth pausing and reconsidering before
investing in B/C. The architectural commitments are bets; we should
notice when the evidence is against them.

## What we will *not* do early

- **Self-host the Sutra compiler.** Tempting, but premature; the
  current C++ Sutra compiler works.
- **Try to run real Linux apps unmodified.** That is a multi-year
  swamp. Transpile-curated-Linux-pieces is the trade-off.
- **Productize the analog hardware story.** Phase 3 hardware is a
  long-term posture, not an early deliverable.
- **Try to be a consumer OS.** Resist every pitch that begins "if
  you just added X, regular people would use it."
