# Security and process isolation

## The shape of the problem

Every Active process shares one tensor substrate. There is no per-process
address space in the conventional sense. Processes pass axons through a
shared router. Naively, this should mean any process can read any other
process's state by guessing the right rotation operator.

It does not, because rotation operators in a high-dimensional space are
practically impossible to guess. Plus: Yantra layers explicit
capability discipline on top, partitioning the synthetic-dimension space
so that crosstalk between unrelated processes is bounded by construction.

But "rotations are big" is not a security argument on its own. The real
security model is the combination of:

1. **Capability-shaped roles.** Possessing a rotation operator *is* the
   capability to read the slot it unbinds.
2. **Synthetic-dimension partitioning.** Each process owns a block of
   synthetic dimensions; cross-block bleed is engineered down to noise.
3. **Static admission.** A process declares, in its manifest, every
   capability it intends to use. The kernel grants none beyond that set.
4. **AOT only.** No runtime code injection paths exist. The browser
   refuses `eval`, refuses runtime imports of remote scripts, refuses
   service workers pushing JS at runtime.

## Capabilities as rotation operators

The kernel boots with a root codebook of rotation operators. These are
not literal cryptographic keys — they are unitary transformations a
process must possess in order to read or write a given role in the
shared axon space.

When the kernel grants a capability to a process, what it actually does
is bundle the relevant operator into the process's launch axon. The
process can derive child operators (for sub-capabilities it wants to
delegate). The kernel can revoke a capability by rotating the parent
operator: any axon bearing the old operator decodes to noise after
revocation.

This is the same machinery that does ordinary IPC, used reflectively
for security. It means the codebase only has to get one thing right
instead of two.

## Synthetic-dimension partitioning

The axon space has a global width. Every Active process gets a block of
that width — its **synthetic-dimension allocation** — within which its
private state lives. The runtime guarantees that:

- Writes by process A to its block do not appreciably perturb decodings
  in process B's block.
- The shared "address book" region (where role codebooks live) is
  read-only to userspace. Modifications go through a kernel role.

The bound on cross-block crosstalk is set at install time as part of
the manifest. A higher bound costs more synthetic dimensions but buys
more isolation. Critical processes get a higher bound than
"interactive" or "background" ones.

## Why airgapped customers love this

For defense, aerospace, and industrial customers running airgapped, a
lot of normal-OS attack surface is just *missing*:

- No `eval` in the browser → a huge class of XSS goes away.
- No service workers → no background code that can be poisoned.
- No runtime script injection → attackers can't slip JS into a request
  and have it run.
- No legacy syscall surface from 30 years of Unix — the syscall set is
  small, axon-typed, and audit-friendly.
- No package-manager-level supply chain footprint at runtime — apps are
  AOT-compiled at install, so a new dependency does not enter the
  running system without an explicit re-install.

This is not security theater. The reduction in attack surface is the
single best argument the platform has for the airgapped market. "It
doesn't run your existing software" is normally a liability; here it
is the same sentence as "it can't run your existing malware."

## What we still have to get right

The argument above is conditional on:

- **Side-channel discipline on the GPU.** Sharing a GPU between two
  process arenas can leak via timing or cache behavior. Yantra's fused
  forward pass model helps (every Active process runs in lockstep
  within a tick) but does not eliminate it. Mitigations are a research
  topic in their own right.
- **Codebook hygiene.** If two processes accidentally share a role
  operator (e.g., because of a buggy capability-derivation step) they
  can read each other. The kernel has to make sharing intentional and
  loud.
- **Bootloader integrity.** The CPU-side bootloader is the only piece
  of conventional code in the trusted base. Standard secure-boot
  practice applies — signed firmware, signed bootloader, signed kernel
  image.
- **The embedding-model boundary.** Embedding models are opaque ML
  artifacts that produce axons from bytes. A poisoned embedding model
  could leak information across the bridge in ways the rotation-binding
  story does not detect. The bridge has to treat embedding-model output
  as untrusted and run it through a sanitizer before letting it cross
  into a privileged process.

## What the certifier can ask for

A pitch to a certification authority looks like:

- Here is the syscall list. It is short and the semantics of each one
  are expressible as axon-typed pre/post conditions.
- Here is the kernel as a Sutra program; here is its tensor normal
  form; here is the polynomial-Kleene-logic representation of every
  branch in it.
- Here is the manifest of every process the system admits at boot, with
  its declared GPU footprint and capability set.
- Here is the audit log: every capability grant the kernel ever issues,
  every admit/evict/resume the resource manager ever performs.

That is the kind of evidence DO-178C-style arguments are built on. It
is more legible than "here is a 30-million-line Linux kernel; trust
us."

## Open questions

- **Process restart and replay.** When the kernel restarts a crashed
  service, does it inherit any state, or is that always a clean boot?
  The accurate answer is "it depends on the service" but we need a
  defensible default.
- **Sandboxing untrusted apps.** Defense customers will eventually want
  to run third-party code in restricted environments. The capability
  story handles this in principle (give the app a child codebook with
  fewer roles), but the UX of "restrict app to this folder" needs
  thought.
- **What happens when the embedding model is the attacker?** A
  worst-case threat actor swaps in a malicious embedding model that
  produces axons designed to confuse downstream processes. We need a
  story for verifying embedding-model identity at load time.
