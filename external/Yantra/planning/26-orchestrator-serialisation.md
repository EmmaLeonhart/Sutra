# Orchestrator serialisation — design

> **What this document is.** The standing design for the orchestrator's
> serialisation primitives. Emma's direction 2026-05-24 split the work into
> two distinct kinds and asked we start with the easy one. This document
> records the split, the format the easy slice uses, and what composes on
> top of it.
>
> **Bottom line.** The easy slice — serialising an axon's output value —
> lands now as `kernel/serialise.py`. The long pole — serialising a *running*
> program's full state (weights + in-flight memory + scheduler position) —
> was thought to need Sutra-side `serialise-process-state`, but the 2026-05-25
> finding (§(b)) showed current Sutra has no such mutable state — RAM cold-store **shipped** (`Tier.RAM`) without it. See §3.

## The two kinds (Emma's direction 2026-05-24)

The orchestrator does serialisation, but the two interesting cases are
different jobs at different layers.

### (a) Serialise an axon's *output* — the easy, near-term kind

The structured-embedding value a program emits. By the time the router
sees an axon, the payload is already a well-typed torch tensor — a
1-D vector of the runtime dim (e.g. 768) carrying every binding the
producer wrote. Capturing it is "read these bytes off the GPU and write
them somewhere," and restoring it is "write these bytes back into a
fresh tensor on the right device with the right dtype."

This is the right place to start because:

1. The shape is **already settled** — the router defines payloads as
   1-D vectors; we don't have to design a new envelope.
2. **No co-design with Sutra** — the substrate doesn't need to expose
   any new primitive; we're capturing the value the substrate already
   emitted.
3. **Useful immediately** — every persistence story we eventually want
   (IPC, network, checkpoint of a conversation's history, audit log of
   what flowed through the connectome) composes from this.

### (b) Serialise a *running* program's full state — finding 2026-05-25

The framing this section originally had — "the slice of VRAM holding the
program's weights *and* its in-flight memory" — anticipated a Sutra that
has persistent mutable per-program state. **Audited 2026-05-25 against
the actual Sutra source: current Sutra is purely functional**, so for
today's programs (b) has nothing to capture.

Evidence:

1. `external/Sutra/planning/sutra-spec/concurrency.md`: spec says plainly
   *"No shared mutable state, no cross-path."* Sutra is a pure functional
   language; each `on_axon(input) -> output` call is independent.
2. `external/Sutra/planning/findings/2026-05-18-differentiable-training-is-a-proxy-not-compiled.md`:
   training currently runs as a hand-reimplemented PyTorch proxy, NOT
   through compiled `.su` source. Compiled Sutra programs do not carry
   trainable weight tensors; there are no weights to checkpoint.
3. The `_VSA` instance has mutable caches (`_rot_cache`, `_perm_cache`,
   `_codebook`) — but all three are **deterministic from key strings**:
   on resume they rebuild lazily, and the codebook is already disk-
   cached globally per `(LLM, dim)` via `_load_disk_cache` /
   `_write_disk_cache`. No per-program codebook snapshot is needed for
   stateless programs.
4. "In-flight" within a single `on_axon` call is the loop-carrier of a
   tail-recursive `loop`, but calls are synchronous and run to
   completion within a tick. There is no paused-mid-call state to
   serialise.

What this means: **for current Sutra, (b) is the empty set.** Per-program
state that survives across ticks lives in the next axon (the program
emits the new state as part of its output; the orchestrator routes it
back as input on the next tick), which (a) already captures. The
forward-looking version of (b) — where Sutra grows trained weights, or
declared cross-tick state — should be revisited when that lands;
likely shape: a Sutra-side `program_state_bytes()` accessor on the
compiled module that returns whatever mutable state the program has
declared. Today that accessor would return zero bytes; introducing the
no-op accessor now would be dead code per CLAUDE.md "no host shortcuts /
no fake primitives" — defer until a real consumer exists.

### (c) Orchestrator-level checkpoint — the actual blocker

What the queue/todo called "blocked on `serialise-process-state`" is in
fact the **orchestrator's** state, not the substrate's. To bring the
connectome back from a cold restart — a different machine, a power
cycle, or just an `Init.unload` → `Init.load` cycle for a process whose
inbox has pending axons — what needs to survive is:

1. **The admission table** (`Init._table`): which programs are admitted,
   under what manifest, with which service identity (`.su` source path,
   output role, runtime dtype — enough to rebuild a fresh
   `SutraService` instance).
2. **The tier map** (`Init._tier`): which programs are GPU-resident vs
   DISC (eventually RAM cold-store).
3. **The router inboxes** (`AxonRouter._inboxes`): per-program queue of
   axons not yet consumed. Each axon carries `role`, `payload` (tensor —
   serialised via (a)), `from_proc`, and `keys`.
4. **The tick number** (when a real scheduler lands; v0.0 has none).

None of this requires a Sutra-side primitive. It's pure
orchestrator/host work, composable from the (a) primitive that already
ships. This is the substantive next piece, and it's what unblocks the
`Tier.RAM` cold-store in `planning/03-process-lifecycle.md`.

The build order for (c):

1. **Axon envelope serialiser — SHIPPED 2026-05-25.**
   `serialise_axon(Axon) -> bytes`, `deserialise_axon(bytes) -> Axon`.
   Composes (a)'s payload serialiser; adds role / from_proc / keys
   metadata around it. Foundation for inbox capture.
2. **Kernel checkpoint — SHIPPED 2026-05-25.**
   `kernel/checkpoint.py`: `serialise_kernel_state(init) -> bytes`,
   `restore_kernel_state(bytes, services_factory) -> Init`. Captures
   manifests + tier + per-program inboxes; uses YKST magic with a
   binary framing + JSON for the structured (manifest, service-identity)
   fields. Restore is bit-exact: an integration test admits echo on an
   Init, pushes axons into its inbox, checkpoints, restores on a fresh
   Init via the factory, and confirms the restored kernel emits the same
   bytes for the same queued input (decoded string still recovers
   verbatim through the substrate). PythonService is REFUSED at
   checkpoint (not faked) per CLAUDE.md "no fake primitives" — its
   callable isn't reconstructable from bytes. RAM tier is refused at
   restore until the `Tier.RAM` enum lands. 9 tests in
   `tests/test_kernel_checkpoint.py`. Full kernel gate 197 passed,
   1-xfail (measured 2026-05-25 on the RTX 4070 machine).

   **Device faithfulness (fixed 2026-05-25).** `restore_kernel_state`
   now restores each process's inbox onto the *device its own service
   uses* (default `device=None` infers from `service._compiled_module.
   _VSA.device`); an explicit `device=` overrides. The earlier hard
   `device="cpu"` default restored GPU-resident inboxes onto CPU, which
   the sibling (CPU-only) machine didn't catch but failed bit-exact
   `torch.equal` on the RTX 4070 (`other is on cuda:0, different from
   other tensors on cpu`). A restored kernel must put its inboxes where
   the consuming substrate lives — a GPU kernel comes back GPU-resident,
   no host->device copy at delivery.
3. **Wire `Tier.RAM` into `Init` — SHIPPED 2026-05-25.** `Tier.RAM` is now
   a real tier value meaning "cold-stored to a host blob" (distinct from
   DISC = "torn down, reloads fresh"). `Init.cold_store(name) -> bytes`
   captures the process's inbox into a self-contained per-process blob
   (`YPRC` magic, `kernel.checkpoint.serialise_process` / `parse_process`),
   frees its GPU residency, clears the live router inbox, and marks it RAM;
   `Init.restore_from_cold(name, blob)` reloads the runtime, re-pushes the
   inbox onto the reloaded service's device, and marks it GPU — the inverse.
   Round-trip is bit-exact and behaviour-identical through a real echo
   (`tests/test_kernel_ram_tier.py`, 10 tests: inbox bit-exact, GPU→RAM→GPU
   transitions, behavioural resume, error paths). **Boundary kept honest:**
   a RAM-tier process can't go through the *whole-kernel* checkpoint (its
   inbox lives in the external `YPRC` blob, not the router), so
   `serialise_kernel_state` refuses a RAM member rather than emit a checkpoint
   that silently loses queued work. The earlier "needs the tier value to land
   first" framing is resolved. Full gate 207 passed, 1 xfail.
   Remaining refinement: pool-budget accounting on tier moves (cold_store
   leaves the budget untouched, matching `unload` — v0.0's `compute_units` is
   bookkeeping-only, not a real device-memory carve-out; real accounting
   belongs with the production GPU-arena work).

## Format for (a): `kernel/serialise.py`

Rust-portable, no Python pickle. The format is intentionally tiny so
that the eventual Rust orchestrator (planning/01 § "CPU side: small,
Rust, orchestrator") can read and write the same bytes with `struct`-
equivalent C primitives — no serde framework, no version negotiation
beyond a magic + version byte.

```
Offset  Size  Field         Notes
0       4     Magic         b'YAXN' (Yantra AXoN)
4       1     Version       Current: 1
5       1     Dtype tag     0=float32, 1=float64, 2=complex64, 3=complex128
6       2     Reserved      Pads the header to an 8-byte boundary
8       4     Width         uint32 little-endian; the 1-D payload length
12      W·S   Payload body  Raw little-endian bytes; W=width, S=dtype size
```

Total header: 12 bytes. Body: width × dtype-size bytes. A 768-d
float64 axon: 12 + 768·8 = 6156 bytes.

### What the format is NOT

- **Not the router envelope.** The bytes carry the *payload only* —
  `Axon.role`, `Axon.from_proc`, and `Axon.keys` are orchestrator
  routing state, not part of the value the program emitted. Persisting
  those alongside is a *separate* envelope concern (a caller that
  needs them writes them to its own log alongside the payload bytes).
- **Not the VSA configuration.** The receiver must already have a
  VSA configured with the same role-vector basis (the LLM embedding)
  and the same per-key permutation function (deterministic from
  `_role_hash`); decoding a restored tensor through `axon_item` will
  only round-trip if the VSA matches what the producer used. A future
  version of the format may carry a VSA-config fingerprint at the
  caller layer, but the bytes the easy slice produces are the payload
  bytes, not the VSA spec.
- **Not pickled.** No Python class identity, no version-pinned object
  graph. Same shape rule the bootloader follows: every cross-process
  format must be parseable from a non-Python reader.

### Round-trip guarantees (measured, not promised)

1. `deserialise_axon_payload(serialise_axon_payload(t))` returns a
   tensor that is `torch.equal` to `t`. Bit-exact (no quantisation,
   no normalisation).
2. Every binding decodes from the restored tensor through `axon_item`
   the same as from the original. Verified by composing the calc's
   real VSA: bind `a`, `b`, `op_char`; serialise; deserialise; check
   each binding's decode value is unchanged.
3. Round-trip works on both CPU and CUDA. The `device` parameter
   of `deserialise_axon_payload` controls where the result lives,
   not the values it carries.

## What's deliberately not in v1

- **Multi-axon batches / streams.** The easy slice is one axon →
  bytes. A persistence layer that wants to log N axons in a single
  file can frame them itself (length-prefix, etc.); the kernel
  primitive doesn't impose a framing.
- **Compression.** A float64 axon is 6 KiB; compression complicates
  the format without materially shrinking storage at the scales we
  care about for v1. If the connectome's audit log eventually wants
  it, that's a layer above the primitive.
- **Encryption / signing.** Same reasoning. Future capability work
  (rotation-operator-based capability checks, the §3.5 hardware
  boundary in `paper/paper.md`) may want signed axons; this primitive
  is the wire-shape, not the security envelope.
- **Cross-VSA-config conversion.** A float32 axon cannot be restored
  into a float64 VSA without explicit dtype conversion + the recipient
  knowing the conversion is safe. The format records the dtype the
  payload was written with; matching it to the VSA's dtype is the
  caller's job.

## Rust port note

This is a candidate first target for the "many small Rust programs"
build strategy under `planning/01-architecture.md` § "CPU side": the
format is small enough to port end-to-end, the test surface
(round-trip a tensor) is unambiguous, and the Python implementation
is already pinned to the wire shape a Rust reader would see. A Rust
port of `serialise.py` doesn't need any of the rest of the orchestrator
to be Rust-ported first.

## Cross-references

- `todo.md` § 1 — Storage-tier moves, Emma's direction 2026-05-24
  (the source of the (a)-then-(b) split).
- `planning/01-architecture.md` § "CPU side: small, Rust,
  orchestrator" — the eventual Rust target.
- `planning/17-memory-model.md` — the broader disc/RAM/GPU storage
  question that (b) is gated on.
- `kernel/router.py` — the `Axon` dataclass whose `payload` field is
  the value being serialised.
- `kernel/serialise.py` — the implementation.
- `tests/test_axon_serialise.py` — the round-trip + bindings-decode
  tests.
