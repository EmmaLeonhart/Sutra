"""Axon router — the kernel's IPC primitive.

**Lazy evaluation is fundamentally compile-time wiring.** The Sutra
compiler statically knows what keys each program binds (the
producer's `add()`/`bind()` calls) and what keys each program
reads (the consumer's `axon_item()` calls). From those two static
sets per program, the cross-program connectome is computable as a
static wiring table: for each (sender role, receiver name) edge,
exactly which keys flow. The router's job at runtime is to
**execute** that wiring, not to compute it.

In this kernel:

  - The receiver's `Manifest.axon_keys` carries the keys-it-reads
    set (in production: emitted by the Sutra compiler from static
    analysis; for v0.0: hand-written in the manifest TOML).
  - The producer attaches the keys-bound set to each emitted
    `Axon` (in production: also compiler-emitted from static
    analysis of the producer's bind chain; for v0.0: passed
    explicitly to `Axon(keys=...)`).
  - The router at admit time builds the per-role receiver list
    once. At send time it filters that list by
    `axon.keys & receiver.axon_keys` — empty intersection ⇒ skip.

This means the connectome doesn't pay O(N²·D) bandwidth in the
worst case; it pays O(E·K) where E is the number of (sender,
receiver) edges that actually share a key and K is the typical
key count. See `planning/20-lazy-axon-evaluation.md` for the
combinatorial reasoning.

**Per-receiver projection IS implemented and wired** (corrected
2026-05-15 — this paragraph previously claimed it was not done /
"upstream-Sutra-dependent", which became false once Sutra shipped
`axon_project` and `SutraService` wired it; the stale text was the
same doc-lying class the substrate-purity audit flagged elsewhere).
The chain is: `register_projector(sender, fn)` here →
`SutraService` (kernel/services.py) registers a projector that
calls its compiled module's `_VSA.axon_project(payload, keys)` →
the `send()` projection branch below slims the payload to
`axon.keys & receiver.axon_keys` before delivery. The kernel
therefore does BOTH the skip-the-receiver slice AND payload
projection. A sender without a registered projector (PythonService
stubs, early bringup) falls back to full-payload delivery —
correct, just not bandwidth-optimal.

**Verification status (honest):** the router-level projection
branch is unit-tested with a stand-in projector
(`tests/test_kernel.py::test_projector_slims_payload_*`), and the
`SutraService`→`axon_keys` plumbing is tested
(`tests/test_kernel_sutra.py`). The end-to-end *semantic* test now
exists (`test_projected_payload_still_decodes_semantically`) and
**proves the projection is a no-op for embedding fillers**:
`_VSA.axon_project(bundle,[k]) = bind(k, unbind(k, bundle))`, and
for orthogonal rotation binding on semantic-block fillers
`Q_k·Q_kᵀ = I`, so the "slimmed" payload reconstructs the whole
bundle — a receiver that asked for one key still decodes every
key (measured: dropped key +0.5726 vs kept +0.5999). So the
projection branch below is *correctly wired* but delivers **no
bandwidth reduction and no capability isolation for the common
(embedding) case** — the holographic bundle still crosses, and a
receiver sees keys it never declared (bears on paper § 3.3.1).
True slimming must be producer-side (rebuild without the unwanted
`axon_add` terms — a Sutra-side design decision, not faked here).
See `planning/20-lazy-axon-evaluation.md` § Status + queue.md.
The strict-xfail test flips loud the moment this is actually
fixed.

Capability check still fires on every send: the sender must
possess the role in its `write_roles`; the receiver must possess
the role in its `read_roles`. The capability check happens
before the lazy-skip check. (Matches the threat-model story in
`paper/paper.md` § 3.3.1.)

**Eager fallback.** If a receiver's manifest declares no
`axon_keys` at all (default = empty frozenset), the receiver
opts into eager delivery: every axon on its read-roles arrives
regardless of key content. Useful for v0.0 stub receivers,
debugger / log / introspection processes that genuinely want
every axon, and for early-bringup before the static wiring table
is populated. Productions services should declare their
`axon_keys` so the router can skip-deliver.
"""

from __future__ import annotations

import dataclasses
import threading
from collections import defaultdict, deque
from typing import Any, Callable, Iterator

from kernel.manifest import Manifest


# A projector takes (full_payload, requested_keys) and returns a
# slimmed payload. Sutra-side: this is `_VSA.axon_project` from
# Sutra v0.3.5+. Python services can omit it (the router falls
# back to delivering the full payload).
ProjectorFn = Callable[[Any, frozenset[str]], Any]


class CapabilityError(PermissionError):
    """A process tried to send or receive on a role it doesn't possess."""


class NotAdmittedError(LookupError):
    """A process name was referenced that init never admitted."""


@dataclasses.dataclass(frozen=True)
class Axon:
    """A single in-flight message between processes.

    `role`        — the routing-role under which this axon flows
    `payload`     — the tensor (or tensor-like value) bundling the
                    bound key-slots
    `from_proc`   — the name of the sending process (for capability
                    + audit)
    `keys`        — the axon-internal keys actually bound in
                    `payload`. Used by the router for lazy-skip
                    delivery: a receiver whose `axon_keys` declared
                    in its manifest don't intersect this set is
                    skipped. In production, the Sutra compiler emits
                    this set from static analysis of the producer's
                    bind chain; for v0.0 the sender passes it
                    explicitly. Empty frozenset = "no key
                    declarations" — the router treats this as
                    eager-fallback (deliver to every receiver on the
                    role regardless of key intersection).
    """
    role: str
    payload: Any
    from_proc: str
    keys: frozenset[str] = dataclasses.field(default_factory=frozenset)


class AxonRouter:
    """In-memory router with capability check on send and receive.

    The router holds:
      - `_processes` : name → manifest, populated by init at admission
      - `_inboxes`   : name → deque[Axon], one inbox per admitted process
      - `_routes`    : role → list[receiver-name], the delivery table

    The route table is rebuilt at admission time from the union of
    every admitted process's `read_roles`. Multiple receivers on one
    role is a fan-out (every receiver gets a copy); zero receivers on
    a role is a black-hole (the send is logged and dropped, *not* an
    error — sending a "log" axon to a logger that hasn't been admitted
    yet is normal startup-order, not a capability violation).
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._processes: dict[str, Manifest] = {}
        self._inboxes: dict[str, deque[Axon]] = {}
        self._routes: dict[str, list[str]] = defaultdict(list)
        self._dropped_audit: list[Axon] = []
        # Lazy-skip audit: counts how many (axon, receiver) pairs the
        # router skipped because keys didn't intersect. Useful for
        # observability — if this is 0 in a connectome with declared
        # axon_keys, the wiring is sub-optimal (every axon goes
        # everywhere); if it's high, the lazy machinery is doing its
        # job. See planning/20-lazy-axon-evaluation.md.
        self._lazy_skipped_count: int = 0
        # Per-receiver projection: senders may register a projector
        # function that knows how to slim a payload to a key subset
        # (e.g. SutraService delegates to its compiled module's
        # _VSA.axon_project, available since Sutra v0.3.5). When a
        # sender's projector is registered AND a receiver declares
        # an axon_keys interest set, the router projects the payload
        # to the intersection before delivery.
        # Projectors are keyed by sender process name.
        self._projectors: dict[str, ProjectorFn] = {}
        # Counts how many times the router actually projected a
        # payload (a sender had a projector registered AND the
        # receiver had non-empty axon_keys AND the intersection was
        # smaller than the full axon keys). Distinct from
        # lazy_skipped_count, which counts skip-the-receiver-entirely
        # decisions.
        self._lazy_projected_count: int = 0

    # --- admission lifecycle (called by init) ---

    def register(self, manifest: Manifest) -> None:
        """Add a process and route its read-roles into the table."""
        with self._lock:
            if manifest.name in self._processes:
                raise ValueError(
                    f"router: process {manifest.name!r} already registered"
                )
            self._processes[manifest.name] = manifest
            self._inboxes[manifest.name] = deque()
            for role in manifest.read_roles:
                self._routes[role].append(manifest.name)

    def deregister(self, name: str) -> None:
        """Remove a process and tear down its routes."""
        with self._lock:
            if name not in self._processes:
                raise NotAdmittedError(name)
            for role in self._processes[name].read_roles:
                receivers = self._routes.get(role, [])
                if name in receivers:
                    receivers.remove(name)
                if not receivers:
                    self._routes.pop(role, None)
            del self._processes[name]
            del self._inboxes[name]
            # Drop the projector if any was registered.
            self._projectors.pop(name, None)

    def register_projector(self, sender_name: str, fn: ProjectorFn) -> None:
        """Register a per-sender payload-projection function.

        Called by services that can slim a payload to a key subset
        (SutraService delegates to its compiled module's
        `_VSA.axon_project`). When this is registered, the router
        calls `fn(payload, requested_keys)` per receiver before
        delivery, where `requested_keys = axon.keys & receiver.axon_keys`.

        Senders without a projector get pass-through behaviour: the
        full axon is delivered. Useful for PythonService stubs and
        early-bringup before all programs have axon_keys wiring.
        """
        with self._lock:
            if sender_name not in self._processes:
                raise NotAdmittedError(sender_name)
            self._projectors[sender_name] = fn

    def unregister_projector(self, sender_name: str) -> None:
        """Drop a previously-registered projector. Idempotent.

        Used when a process is **unloaded from the GPU** (its Sutra
        runtime is torn down) but stays admitted: the projector
        closure captures the compiled module's `_VSA`, so leaving it
        registered would pin that `_VSA`'s GPU tensors and defeat the
        memory free. The process keeps its route entry (it can be
        reloaded); only the projector is dropped. Falls back to
        full-payload pass-through until reload re-registers one.
        """
        with self._lock:
            self._projectors.pop(sender_name, None)

    # --- send / receive (called by services) ---

    def send(self, axon: Axon) -> int:
        """Deliver `axon` from `axon.from_proc`. Returns receiver count.

        Three filtering stages, in order:

        1. **Capability check on send.** The sender must possess
           `axon.role` in its `write_roles`. Violations raise
           `CapabilityError` (programming bug, surfaced loudly).
        2. **Route lookup.** If no admitted receiver reads
           `axon.role`, the axon is logged + dropped (black-hole;
           normal during startup or when a logger isn't admitted).
        3. **Lazy-skip per receiver.** For each receiver wired to
           the role, if the receiver declares `axon_keys` AND the
           axon declares `keys` AND the two sets don't intersect,
           skip delivery to that receiver. The
           `lazy_skipped_count` audit increments. Either side
           empty = eager fallback (deliver).

        Returns the number of receivers actually delivered to
        (after lazy-skip filtering). 0 is allowed.
        """
        with self._lock:
            sender = self._processes.get(axon.from_proc)
            if sender is None:
                raise NotAdmittedError(axon.from_proc)
            if axon.role not in sender.write_roles:
                raise CapabilityError(
                    f"process {axon.from_proc!r} cannot write role "
                    f"{axon.role!r} (write_roles={sorted(sender.write_roles)})"
                )
            receivers = list(self._routes.get(axon.role, []))
            if not receivers:
                # Black-hole: log + drop. Not an error — see class docstring.
                self._dropped_audit.append(axon)
                return 0
            delivered = 0
            for r in receivers:
                # Capability check on receive — defence in depth: even
                # if the route table is wrong, a process never gets an
                # axon for a role it can't read.
                receiver = self._processes[r]
                if axon.role not in receiver.read_roles:  # pragma: no cover
                    raise CapabilityError(
                        f"router invariant broken: route table claims "
                        f"{r!r} reads {axon.role!r} but its read_roles "
                        f"are {sorted(receiver.read_roles)}"
                    )
                # Lazy-skip: only when both sides have declared
                # their key sets AND the intersection is empty. If
                # either side is empty (the eager-fallback case),
                # we deliver. This is the kernel slice of lazy
                # evaluation; see class docstring + planning/
                # 20-lazy-axon-evaluation.md for the framing.
                if axon.keys and receiver.axon_keys:
                    intersection = axon.keys & receiver.axon_keys
                    if not intersection:
                        self._lazy_skipped_count += 1
                        continue
                    # Per-receiver projection: if the sender has a
                    # projector registered AND the receiver wants
                    # a strict subset of what the axon carries,
                    # slim the payload to just the intersection.
                    # Senders without a projector (PythonService
                    # stubs) fall through to delivering the full
                    # payload — correct, just not bandwidth-optimal.
                    projector = self._projectors.get(axon.from_proc)
                    if projector is not None and intersection != axon.keys:
                        slim_payload = projector(axon.payload, intersection)
                        delivered_axon = dataclasses.replace(
                            axon,
                            payload=slim_payload,
                            keys=intersection,
                        )
                        self._lazy_projected_count += 1
                        self._inboxes[r].append(delivered_axon)
                        delivered += 1
                        continue
                self._inboxes[r].append(axon)
                delivered += 1
            return delivered

    def receive(self, name: str) -> Axon | None:
        """Pop the next axon for `name`, or None if the inbox is empty."""
        with self._lock:
            inbox = self._inboxes.get(name)
            if inbox is None:
                raise NotAdmittedError(name)
            if not inbox:
                return None
            return inbox.popleft()

    def drain(self, name: str) -> Iterator[Axon]:
        """Yield all currently-buffered axons for `name`."""
        while True:
            ax = self.receive(name)
            if ax is None:
                return
            yield ax

    # --- introspection (used by tests + observability) ---

    def admitted(self) -> list[str]:
        with self._lock:
            return sorted(self._processes)

    def dropped_count(self) -> int:
        with self._lock:
            return len(self._dropped_audit)

    def lazy_skipped_count(self) -> int:
        """How many (axon, receiver) pairs the router skipped via
        lazy key-intersection filtering."""
        with self._lock:
            return self._lazy_skipped_count

    def lazy_projected_count(self) -> int:
        """How many (axon, receiver) pairs the router slimmed via
        per-receiver projection (sender's projector called to
        narrow the payload to the receiver's interest set)."""
        with self._lock:
            return self._lazy_projected_count

    def inbox_depth(self, name: str) -> int:
        with self._lock:
            inbox = self._inboxes.get(name)
            if inbox is None:
                raise NotAdmittedError(name)
            return len(inbox)
