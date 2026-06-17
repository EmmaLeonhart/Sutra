# Lazy axon evaluation — required, not optional

> **What this document is.** An explicit statement that lazy axon
> evaluation across program boundaries is a **hard requirement** for
> Yantra to scale, not a nice-to-have optimization. Written
> 2026-05-14 to fix a documentation gap: the Yantra-side
> `kernel/router.py` does eager full-payload routing, which is fine
> for the v0.0 1-axon-1-receiver smoke test but is **not the model
> the production connectome runs on**, and the readme didn't say so.
>
> **The Sutra spec calls this out.**
> `external/Sutra/planning/sutra-spec/axons.md` § "Lazy evaluation
> across boundaries" is the canonical reference. This document is
> the Yantra-side statement of why that spec section is load-bearing.

## The problem if axons are eager

Consider a connectome with N programs, each emitting axons of
bundle width D (D dimensions, packing K role-slots). A naive
**eager** router:

- Each program emits its full D-dimensional axon every tick.
- The router copies the full axon to every receiver.
- A receiver only reads the K_r ≤ K slots it has read-roles for.

Cost per tick: every emitter sends D floats to every receiver.
That's **O(N²·D)** floats moved per tick in the worst case, and
**O(N²·D·T)** over T ticks. The K_r-of-K slots a receiver
actually reads are a small fraction; the rest of the axon is
*dead weight on the wire*.

This is exactly the combinatorial-explosion failure mode the
Sutra paper's bundle-depth analysis warns against. At small N the
overhead is unnoticeable; at the scale a real OS connectome
needs to run (hundreds of programs, axons with dozens of slots),
the eager model collapses under its own bandwidth before any
useful computation happens.

## The lazy answer

A **lazy** router only materializes the slots a receiver
references. The emitter declares which roles it writes; the
receiver declares which roles it reads; the router materializes
only the intersection.

Cost per tick: each emitter→receiver edge transports K_intersect
floats, where K_intersect is the number of roles both ends agree
on. Over the connectome, that's **O(E·K_intersect)** where E is
the number of emitter-receiver edges actually wired (not N², just
the connected ones). For sparse connectomes this is a *huge*
constant-factor win and an asymptotic win.

Lazy materialization also means a receiver that never references
a particular role never pays for it — it's not just bandwidth, it's
that the unbind operation is never run on the receiver side for
unreferenced slots.

## Why this matters for the orchestrator's job

The Rust orchestrator's axon-router responsibility (§4 in
`19-boot-sequence.md`) is not "copy bytes around." It is
"materialize, on demand, the dimensions a receiver references,
and only those." The mechanism per the Sutra spec:

1. The compiler knows statically which roles each Sutra program
   reads. This is part of the program's contract surface (the
   spec calls these "read-roles" and Yantra's manifest format
   carries them as `read_roles`).
2. The router precomputes per-receiver projection: for the axon
   emitted on role R by sender S, project onto the dimensions
   receiver R' actually reads.
3. At tick time, the router does the projected copy, not the full
   copy.

For a single GPU running everything in shared memory, "copy"
collapses further — the projections can be expressed as torch
slicing / index ops on the same underlying tensor, with no
physical data movement at all. The lazy model + GPU shared
memory is most of what makes the connectome viable.

## Lazy is fundamentally compile-time wiring

The user driving this work pointed out (correctly) that lazy
evaluation is essentially a compile-time problem. The Sutra
compiler statically knows what keys each program binds (the
producer's `add()` / `bind()` calls in the .su source) and what
keys each program reads (the consumer's `axon_item()` calls).
From those two static sets per program, **the cross-program
connectome wiring is computable as a static table** — for each
(sender role, receiver name) edge, exactly which keys flow.

The kernel router's job at runtime is to **execute** that
wiring, not to compute it. There is no clever runtime intersection
analysis happening in the production design; there's a precomputed
delivery table, populated at admission time from manifest data
the compiler emitted.

What the Yantra-side kernel implements is the runtime expression
of that static wiring:

  - `Manifest.axon_keys` — the keys-this-receiver-reads set.
    In production, the Sutra compiler emits this from static
    analysis. For v0.0, it's hand-written in the manifest TOML.
  - `Axon.keys` — the keys-bound-in-this-payload set. In
    production, the compiler emits this from analysis of the
    producer's bind chain. For v0.0, the calling service passes
    it explicitly to `service.emit(role, payload, keys=...)`.
  - `AxonRouter.send()` — at send time, intersects the axon's
    keys with each receiver's `axon_keys`. Empty intersection
    ⇒ skip. Non-empty ⇒ deliver. Empty on either side ⇒
    eager-fallback (deliver).

## Yantra-side status

**Implemented as of 2026-05-14.** `kernel/router.py` now does the
kernel slice of lazy evaluation as described above. Tested in
`tests/test_kernel.py`:

  - `test_lazy_skip_when_keys_dont_intersect` — receiver
    declaring keys it doesn't share with the axon is skipped;
    `lazy_skipped_count()` increments; black-hole NOT triggered.
  - `test_lazy_delivers_when_keys_intersect` — non-empty
    intersection delivers as expected.
  - `test_lazy_eager_fallback_when_receiver_unkeyed` — receivers
    with empty `axon_keys` get every axon (eager fallback path
    for v0.0 stub receivers and debugger / log processes).
  - `test_lazy_eager_fallback_when_axon_unkeyed` — axons
    emitted without declared keys go to every receiver
    (eager fallback for stub producers and debugger-emitted
    axons that don't go through static wiring).
  - `test_lazy_partial_fanout_one_skips_one_delivers` — two
    receivers on same role, only the keyed-matching one gets
    the axon.
  - `test_lazy_capability_check_still_fires_first` — capability
    check happens before lazy filtering; can't bypass capability
    by playing key games.
  - `test_lazy_keys_optional_in_manifest_toml` /
    `test_lazy_keys_in_manifest_toml` /
    `test_lazy_bad_manifest_axon_keys_raises` — manifest TOML
    schema for `axon_keys` (optional list of strings).

**Per-receiver projection — also implemented as of 2026-05-14.**
Sutra v0.3.5 added `_TorchVSA.axon_project(axon, requested_keys)`,
a runtime method that returns a slimmed axon containing only the
listed keys' bound contributions. Yantra's kernel router uses it
via `AxonRouter.register_projector(name, fn)` — `SutraService.bind()`
registers the compiled module's `axon_project` with the router,
and `AxonRouter.send()` calls the projector per receiver to
deliver a slimmed payload when the receiver's `axon_keys` is a
strict subset of the axon's `keys`. Audit counters
`lazy_skipped_count()` and `lazy_projected_count()` distinguish
the skip-entirely case from the slim-then-deliver case.

**What's left upstream**: per-key sub-vector slicing at the
*tensor* level. Today's `axon_project` rebuilds a slimmed axon by
extract-and-rebind (composed of bind/unbind/permute over the
existing primitives) — same on-the-wire shape, just with a
zeroed-out region for un-projected keys. A future Sutra-side
optimization could expose the actual sub-vector indices per role
and let the router copy only those bytes. That's a real win on
multi-GPU connectomes; for single-GPU shared memory it's the
same cost.

## Status (2026-05-15)

The body of this doc above was written 2026-05-14 describing the
router as **eager-only**. That is **no longer accurate** and the
text is kept only for the why-it-matters reasoning. Current truth:

- **Kernel-level slice — done.** `AxonRouter.send()` skips a
  receiver entirely when `axon.keys ∩ receiver.axon_keys = ∅`
  (`lazy_skipped_count` audit).
- **Per-receiver payload projection — done and wired.**
  `AxonRouter.register_projector(sender, fn)` +
  `SutraService` (kernel/services.py) registering a projector that
  calls the compiled module's `_VSA.axon_project(payload, keys)` +
  the projection branch in `send()` that slims the payload to
  `axon.keys & receiver.axon_keys` (`lazy_projected_count`
  audit). Sutra ships `axon_project` (`test_axon_project.py`
  green). PythonService stubs without a projector fall back to
  full-payload delivery (correct, not bandwidth-optimal).
- **Tested:** router projection branch with a stand-in projector
  (`tests/test_kernel.py::test_projector_slims_payload_*`);
  `SutraService`→`axon_keys` static-analysis plumbing
  (`tests/test_kernel_sutra.py`).
- **End-to-end semantic test now exists — and it PROVES the
  projection is a no-op for embedding fillers** (2026-05-15,
  `tests/test_kernel_sutra.py::test_projected_payload_still_decodes_semantically`,
  strict `xfail`). `_VSA.axon_project(bundle, [k])` is
  `bind(k, unbind(k, bundle))`. For orthogonal rotation binding on
  **semantic-block (embedding) fillers**, `Q_k·Q_kᵀ = I`, so
  `bind(k, unbind(k, ·))` is the **identity** — the "projected"
  payload reconstructs the *entire* bundle. Measured: a receiver
  that declared interest in only `animal` recovers the
  projected-OUT `color` key at cos `+0.5726`, essentially equal to
  the kept `animal` key at `+0.5999`.

  **Consequences (must not be papered over):**
  - **No bandwidth reduction** for the common (embedding-filler)
    case — the O(N²·D) → O(E·K) claim in this doc's body does NOT
    hold via `axon_project`; the full holographic bundle still
    crosses.
  - **No capability isolation.** A receiver gets every key's
    content regardless of its declared `axon_keys`. This
    contradicts the operator-capability story in
    `paper/paper.md` § 3.3.1 — flagged, not silently accepted.
  - The per-key **synthetic-block permutation** does make
    projection lossy for *synthetic* fillers (numbers via
    `make_real`, strings via `make_string`), so `axon_project`
    is only a true slim there — not for embeddings.

  **The real fix is producer-side, and is a Sutra-side design
  decision (not faked here):** true slimming requires the producer
  to rebuild the bundle WITHOUT the unwanted keys' `axon_add`
  terms (whole-program / compile-time analysis of which keys each
  receiver reads — `external/Sutra/.../axons.md` §"Lazy evaluation
  across boundaries"), because a finished bundle is holographic and
  cannot be sliced after the fact. Post-hoc `axon_project` on a
  bundled axon is information-theoretically a no-op for semantic
  fillers. Precise blocker in `queue.md`.

## Status (2026-05-17) — producer-side pruning PARTLY landed; blocker NARROWED not closed

The producer-side fix above was built **for the intra-module
case** and shipped as **Sutra v0.4.1** (submodule pinned here).
`_compute_axon_read_signatures` + the extended
`_compute_axon_elision` (Sutra `codegen_base.py`) now compute
per-`(function,param)` axon read demand across the whole module's
call graph and **never emit** a producer `.add(k,v)` whose key no
callee transitively reads — the filler is genuinely never bundled
(not sliced after the fact). Sound over-approximation: anything
the analysis can't bound (dynamic key, returned/aliased param,
unknown callee, `vector`-typed param) keeps **all** keys. Proven
by `external/Sutra/.../tests/test_codegen.py::TestCrossFunction
AxonElision` + 141 green + smoke PASS. The Sutra `axons.md`
open-question is resolved for the single-function-call case.

**Why this NARROWS but does NOT close the Yantra blocker.** This
doc's actual subject is the **connectome** boundary: Yantra's
producer and each consumer are **separately-compiled `.su`
modules**, wired by the kernel router at admission time. A
single-module compiler pass cannot see the consumer's read-set
across that boundary — and in the real shape the consumer types
its parameter `vector` and reads via `axon_item(state, …)` (see
`external/Sutra/examples/multi_program_axon/consumer.su`), which
the new pass deliberately treats as OPAQUE → producer keeps all
keys. So:

- **Closed:** producer-side pruning *within a single compiled
  program* across function calls (the spec's `getCat` example).
- **Still open (the original blocker, narrowed to its true
  scope):** cross-separately-compiled-program pruning for the
  connectome. `axon_project` on a finished bundle is still an
  information-theoretic no-op for embedding fillers; the
  remaining fix needs **whole-connectome compilation** (compile
  producer + its admitted consumers together so the producer sees
  the union of consumer read-sets) or **admission-time producer
  specialization** (re-emit/re-bundle the producer per wired
  consumer set when the kernel router connects them). Both are
  larger Sutra+kernel design items, deliberately not faked. The
  end-to-end strict-`xfail` test
  (`test_projected_payload_still_decodes_semantically`) stays
  `xfail` — it is still accurate for the connectome case.

## Cross-references

- `external/Sutra/planning/sutra-spec/axons.md` § "Lazy evaluation
  across boundaries" — canonical spec.
- `01-architecture.md` § "The kernel is a Connectome Manager" —
  the connectome framing this requirement falls out of.
- `19-boot-sequence.md` — where the orchestrator's axon-router
  responsibility lives in the boot/runtime flow.
- `kernel/router.py` — kernel slice + per-receiver projection both
  implemented (see § Status above; top-of-file docstring corrected
  2026-05-15).
- `kernel/services.py` — `SutraService` registers a
  `_VSA.axon_project`-backed projector with the router; the
  per-receiver projected slice is what crosses to the consumer
  once the end-to-end test confirms semantic correctness.
