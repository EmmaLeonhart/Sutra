"""Orchestrator state checkpoint — (c) the actual RAM cold-store primitive.

Captures the kernel's full external-observable state — admission table,
storage tier per process, router inboxes — as Rust-portable bytes. A
restored kernel processes any queued axons identically to the original
(verified by integration test). This is what unblocks the RAM cold-store
tier in `planning/03-process-lifecycle.md`.

What this primitive does NOT need (finding 2026-05-25, see
`planning/26-orchestrator-serialisation.md` § "(b) … finding"): a
Sutra-side `serialise-process-state` hook. Current Sutra is purely
functional; VSA caches are deterministic from key strings; loop carriers
don't survive across ``on_axon`` calls. So per-program substrate state
is empty — the orchestrator's own state is the whole game.

Format (Rust-portable; no Python pickle):

    Header
        Offset  Size  Field
        0       4     Magic b'YKST' (Yantra Kernel STate)
        4       1     Version (uint8, current: 1)
        5       3     Reserved (pad to 8)
        8       4     compute_pool_total (uint32 LE)
        12      4     compute_pool_free  (uint32 LE)
        16      4     process_count      (uint32 LE)

    For each process record:
        4   name length (uint32 LE)
        N   name UTF-8 bytes
        4   manifest JSON length (uint32 LE)
        M   manifest JSON UTF-8 bytes
        1   tier tag (uint8: 0=GPU, 1=DISC, 2=RAM)
        3   pad
        4   service-identity JSON length (uint32 LE)
        I   identity JSON UTF-8 bytes
        4   inbox count (uint32 LE)
        For each axon in the inbox:
            4   envelope length (uint32 LE)
            E   envelope bytes (a full 'YAXE' :func:`serialise_axon` blob)

The structured fields (manifest, service identity) use JSON for the
inner schema; the framing is binary. A future Rust port can keep the
framing and swap the inner JSON for a binary schema without breaking
the outer layout.

This module composes :mod:`kernel.serialise` for the per-axon work; the
checkpoint is the inbox-and-table layer above it.
"""
from __future__ import annotations

import dataclasses
import enum
import json
import pathlib
import struct
from collections import deque
from typing import TYPE_CHECKING, Any, Callable

from kernel.serialise import (
    AxonSerialiseError,
    deserialise_axon,
    serialise_axon,
)

if TYPE_CHECKING:
    from kernel.init import Init
    from kernel.manifest import Manifest
    from kernel.router import Axon
    from kernel.services import Service

_MAGIC = b"YKST"
_VERSION = 1
_HEADER_FMT = "<4sB3sIII"  # magic, version, reserved, pool_total, pool_free, process_count
_HEADER_SIZE = 20

# Per-process cold-store blob ('YPRC' = Yantra PRocess Cold-store). A single
# admitted process captured self-contained: manifest + service identity +
# inbox. This is the RAM-tier unit (Init.cold_store / restore_from_cold),
# distinct from the whole-kernel YKST checkpoint above.
_MAGIC_PROC = b"YPRC"
_VERSION_PROC = 1
_PROC_HEADER_FMT = "<4sB3s"  # magic, version, 3-byte reserved (pad to 8)
_PROC_HEADER_SIZE = 8


class CheckpointError(ValueError):
    """A checkpoint blob is malformed, version-mismatched, or a service
    that the checkpoint references cannot be reconstructed."""


_TIER_TAGS: dict[str, int] = {"gpu": 0, "disc": 1, "ram": 2}
_TAGS_TIER: dict[int, str] = {v: k for k, v in _TIER_TAGS.items()}


def _pack_section(body: bytes) -> bytes:
    """uint32 length + body. Used for every variable-length field."""
    if len(body) > 0xFFFFFFFF:
        raise CheckpointError(f"section too long for u32 length: {len(body)}")
    return struct.pack("<I", len(body)) + body


def _unpack_section(data: bytes | bytearray | memoryview, offset: int) -> tuple[bytes, int]:
    """Inverse of :func:`_pack_section`. Returns (section_bytes, new_offset)."""
    if offset + 4 > len(data):
        raise CheckpointError("truncated at section length")
    (length,) = struct.unpack_from("<I", data, offset)
    start = offset + 4
    end = start + length
    if end > len(data):
        raise CheckpointError(
            f"truncated section body: need {length} from offset {start}, "
            f"only {len(data) - start} available"
        )
    return bytes(data[start:end]), end


def _manifest_to_json(manifest: "Manifest") -> str:
    """Render a Manifest as JSON. Frozenset → sorted list for deterministic bytes."""
    return json.dumps(
        {
            "name": manifest.name,
            "axon_width": manifest.axon_width,
            "compute_units": manifest.compute_units,
            "read_roles": sorted(manifest.read_roles),
            "write_roles": sorted(manifest.write_roles),
            "source": manifest.source,
            "axon_keys": sorted(manifest.axon_keys),
        },
        sort_keys=True,
    )


def _manifest_from_json(blob: str) -> "Manifest":
    from kernel.manifest import Manifest  # local import: avoid cycle

    d = json.loads(blob)
    return Manifest(
        name=d["name"],
        axon_width=int(d["axon_width"]),
        compute_units=int(d["compute_units"]),
        read_roles=frozenset(d["read_roles"]),
        write_roles=frozenset(d["write_roles"]),
        source=d["source"],
        axon_keys=frozenset(d["axon_keys"]),
    )


def _service_identity(service: "Service") -> dict[str, Any]:
    """Extract enough state from a Service to reconstruct it via the factory.

    SutraService: kind="sutra", source_path / output_role / runtime_dtype /
    llm_model / entry_point.

    PythonService is rejected — its callable can't be reconstructed from
    bytes and the orchestrator must refuse the checkpoint rather than fake
    one. (CLAUDE.md "no fake primitives": shipping a stub would let a
    checkpoint round-trip "succeed" while silently losing the program's
    behaviour.)
    """
    from kernel.services import PythonService, SutraService  # local import

    if isinstance(service, SutraService):
        return {
            "kind": "sutra",
            "source_path": str(service._source_path),  # noqa: SLF001 (orchestrator owns this state)
            "output_role": service._output_role,  # noqa: SLF001
            "runtime_dtype": service._runtime_dtype,  # noqa: SLF001
            "llm_model": service._llm_model,  # noqa: SLF001
            "entry_point": service._entry_point,  # noqa: SLF001
        }
    if isinstance(service, PythonService):
        raise CheckpointError(
            "PythonService is not checkpointable: its on_axon callable cannot "
            "be reconstructed from bytes. PythonService is testing-only; a "
            "production checkpoint must contain only SutraService instances "
            "(or a Service subclass that exposes a serialisable identity)."
        )
    raise CheckpointError(
        f"Service type {type(service).__name__} has no known identity "
        "extractor; add a case in kernel.checkpoint._service_identity to "
        "support it (do not silently ship an empty identity — that would "
        "fake a no-op restore)."
    )


def serialise_kernel_state(init: "Init") -> bytes:
    """Capture an :class:`~kernel.init.Init` as Rust-portable bytes.

    Captured: compute pool totals, every admitted process's manifest +
    tier + service identity, and every axon currently in each process's
    inbox (via :func:`kernel.serialise.serialise_axon`).

    NOT captured (deliberately, per `planning/26-orchestrator-serialisation.md`):
    per-program substrate state (Sutra is purely functional; nothing to
    capture); dropped-axon audit log (observability only); lazy-skip
    counters (observability only); router routes (derived from manifests
    on restore).

    Raises :class:`CheckpointError` if any admitted service is not
    checkpointable (e.g. PythonService — see :func:`_service_identity`).
    Failing the whole checkpoint rather than silently dropping such a
    program is the substrate-purity rule: a "successful" checkpoint that
    lost a program would be the exact fake-substrate failure
    `CLAUDE.md` § "The fake-substrate-work threat" forbids.
    """
    with init._lock:  # noqa: SLF001 (orchestrator owns this lock)
        process_count = len(init._table)  # noqa: SLF001
        # Header first.
        header = struct.pack(
            _HEADER_FMT,
            _MAGIC,
            _VERSION,
            b"\x00\x00\x00",
            init._compute_pool_total,  # noqa: SLF001
            init._compute_pool_free,  # noqa: SLF001
            process_count,
        )
        parts: list[bytes] = [header]

        # Sort by name for deterministic output (identical kernel state →
        # identical bytes, useful for audit hashes).
        for name in sorted(init._table):  # noqa: SLF001
            ap = init._table[name]  # noqa: SLF001
            tier = init._tier.get(name, _default_gpu_tier())  # noqa: SLF001

            # A RAM-tier (cold-stored) process keeps its in-flight inbox in
            # an EXTERNAL cold blob (Init.cold_store's return value), not in
            # the router. Capturing it in a whole-kernel checkpoint here would
            # silently lose that queued work — exactly the fake-success the
            # substrate-purity rule forbids. Refuse cleanly: restore the
            # process from its cold blob first, then checkpoint the kernel.
            if tier.value == "ram":
                raise CheckpointError(
                    f"process {name!r} is on tier RAM (cold-stored). Its inbox "
                    "lives in an external cold blob, not the router, so a "
                    "whole-kernel checkpoint cannot capture it. Call "
                    "restore_from_cold(name, blob) to bring it back before "
                    "checkpointing the kernel."
                )

            parts.append(_pack_section(name.encode("utf-8")))
            parts.append(_pack_section(_manifest_to_json(ap.manifest).encode("utf-8")))
            tier_tag = _TIER_TAGS[tier.value]
            parts.append(struct.pack("<B3s", tier_tag, b"\x00\x00\x00"))
            identity = _service_identity(ap.service)
            parts.append(
                _pack_section(json.dumps(identity, sort_keys=True).encode("utf-8"))
            )

            inbox = init._router._inboxes.get(name, deque())  # noqa: SLF001
            parts.append(struct.pack("<I", len(inbox)))
            for axon in inbox:
                envelope = serialise_axon(axon)
                parts.append(_pack_section(envelope))

        return b"".join(parts)


def _default_gpu_tier():
    """Lazy import of Tier.GPU. Used when _tier is missing an entry
    (shouldn't happen; defensive)."""
    from kernel.init import Tier

    return Tier.GPU


def _service_device(service: "Service") -> Any:
    """Best-effort device of the service's substrate (the compiled VSA).

    A restored kernel's inboxes must live where the consuming service lives:
    on a GPU machine the service's ``_VSA`` is on ``cuda``, so its queued
    axons must be restored on ``cuda`` too — otherwise the router would have
    to host->device copy every payload at delivery, and a bit-exact
    ``torch.equal`` against the original (which was on the GPU) fails on a
    pure device mismatch. Returns ``None`` when the service exposes no
    compiled VSA (e.g. not yet bound, or a non-Sutra service); the caller
    then falls back to CPU.
    """
    mod = getattr(service, "_compiled_module", None)
    if mod is None:
        return None
    vsa = getattr(mod, "_VSA", None)
    if vsa is None:
        return None
    return getattr(vsa, "device", None)


def restore_kernel_state(
    data: bytes | bytearray | memoryview,
    services_factory: Callable[[str, dict[str, Any]], "Service"],
    *,
    device: Any = None,
) -> "Init":
    """Rebuild an :class:`~kernel.init.Init` from a checkpoint blob.

    ``services_factory(name, identity)`` is called once per admitted
    process to reconstruct its service. The identity dict is whatever
    :func:`_service_identity` captured at checkpoint time — for SutraService
    it has ``kind``, ``source_path``, ``output_role``, ``runtime_dtype``,
    ``llm_model``, ``entry_point``. The factory is the integration seam
    between the orchestrator and the host environment that knows where
    .su files live, what the available runtimes are, etc.

    The returned Init has the same admission table, tier map, and inbox
    contents as the original. Routes are rebuilt automatically via the
    re-admission path.

    ``device`` controls where each axon payload is restored. The default
    (``None``) restores each process's inbox onto the device of *that
    process's* service substrate — a GPU kernel comes back with
    GPU-resident inboxes, a CPU kernel with CPU inboxes — which is what
    makes the round-trip bit-exact (``torch.equal`` is device-sensitive;
    the originals lived on the service's device). Pass an explicit device
    to force every payload onto it instead. If a process was on DISC at
    checkpoint, it is admitted then immediately unloaded — same end
    state as the original.
    """
    from kernel.init import Init, Tier

    if len(data) < _HEADER_SIZE:
        raise CheckpointError(f"data too short for header: {len(data)} bytes")
    magic, version, _reserved, pool_total, pool_free, process_count = struct.unpack(
        _HEADER_FMT, bytes(data[:_HEADER_SIZE])
    )
    if magic != _MAGIC:
        raise CheckpointError(f"bad checkpoint magic {magic!r}; expected {_MAGIC!r}")
    if version != _VERSION:
        raise CheckpointError(
            f"unsupported checkpoint version {version}; reads version {_VERSION}"
        )
    if pool_free > pool_total:
        raise CheckpointError(
            f"checkpoint is internally inconsistent: pool_free {pool_free} > "
            f"pool_total {pool_total}"
        )

    init = Init(compute_pool=pool_total)
    offset = _HEADER_SIZE
    restored_axons_by_name: dict[str, list] = {}

    for _ in range(process_count):
        name_bytes, offset = _unpack_section(data, offset)
        name = name_bytes.decode("utf-8")
        manifest_bytes, offset = _unpack_section(data, offset)
        manifest = _manifest_from_json(manifest_bytes.decode("utf-8"))
        if offset + 4 > len(data):
            raise CheckpointError(f"truncated at tier tag for process {name!r}")
        (tier_tag,) = struct.unpack_from("<B", data, offset)
        offset += 4  # 1 byte tag + 3 bytes pad
        if tier_tag not in _TAGS_TIER:
            raise CheckpointError(
                f"unknown tier tag {tier_tag} for process {name!r}"
            )
        tier_name = _TAGS_TIER[tier_tag]
        identity_bytes, offset = _unpack_section(data, offset)
        identity = json.loads(identity_bytes.decode("utf-8"))

        # Defensive: a well-formed YKST blob never carries a RAM-tier
        # member — serialise_kernel_state refuses one (its inbox lives in an
        # external cold blob, not the kernel checkpoint). A RAM tag here means
        # a hand-built or corrupted blob; refuse rather than restore a process
        # with a silently-empty inbox. Per-process cold-store has its own path
        # (parse_process / Init.restore_from_cold).
        if tier_name == "ram":
            raise CheckpointError(
                f"checkpoint carries process {name!r} on tier RAM, which "
                "serialise_kernel_state never emits (a cold-stored process's "
                "inbox is held in a separate YPRC cold blob, not the kernel "
                "checkpoint). This blob is malformed; restore is refused. Use "
                "parse_process / Init.restore_from_cold for cold-stored state."
            )

        service = services_factory(name, identity)
        init.admit(manifest, service)
        # Capture the substrate device while the service is GPU-resident
        # (admit() always loads onto GPU). Restored inbox axons are placed
        # on the device the consuming service uses, so the round-trip is
        # bit-exact (torch.equal is device-sensitive). An explicit
        # `device=` argument overrides; otherwise fall back to CPU when the
        # service exposes no compiled VSA.
        axon_device = device if device is not None else (_service_device(service) or "cpu")
        # admit() always starts on GPU; replay the unload if the checkpoint
        # had this process on DISC.
        if tier_name == "disc":
            init.unload(name)

        # Read inbox.
        if offset + 4 > len(data):
            raise CheckpointError(f"truncated at inbox count for process {name!r}")
        (inbox_count,) = struct.unpack_from("<I", data, offset)
        offset += 4
        axons = []
        for _ in range(inbox_count):
            envelope_bytes, offset = _unpack_section(data, offset)
            axon = deserialise_axon(envelope_bytes, device=axon_device)
            axons.append(axon)
        restored_axons_by_name[name] = axons

    # Push axons back into inboxes. Done after all admissions so the router's
    # _inboxes dict is fully populated.
    with init._lock:  # noqa: SLF001
        for name, axons in restored_axons_by_name.items():
            inbox = init._router._inboxes[name]  # noqa: SLF001
            for axon in axons:
                inbox.append(axon)
        # Mirror the original pool_free. admit() already deducted compute_units
        # for each admitted process; this overrides the running total to match
        # exactly what the checkpoint recorded (handles the edge case where the
        # checkpoint included programs that were partially-allocated).
        init._compute_pool_free = pool_free  # noqa: SLF001

    return init


@dataclasses.dataclass(frozen=True)
class ColdProcess:
    """The parsed contents of a per-process cold-store blob (``YPRC``).

    ``axons`` are already deserialised onto the device requested at parse
    time. ``identity`` is the raw service-identity dict (``kind``,
    ``source_path``, …) the factory would consume — but the in-process
    restore path (:meth:`Init.restore_from_cold`) reloads the existing
    service rather than rebuilding from identity, so identity is carried
    for the cross-session / disk-backed case and for the name/manifest
    consistency check.
    """

    name: str
    manifest: "Manifest"
    identity: dict[str, Any]
    axons: list["Axon"]


def serialise_process(init: "Init", name: str) -> bytes:
    """Capture ONE admitted process as a self-contained cold-store blob.

    The blob holds the process's manifest, service identity, and current
    inbox (each axon via :func:`kernel.serialise.serialise_axon`) — enough
    to resume it bit-exact. This is the RAM-tier capture used by
    :meth:`Init.cold_store`; the tier itself is not stored (the blob *is*
    the cold-stored state).

    Raises :class:`CheckpointError` if the process is not admitted or its
    service is not checkpointable (e.g. PythonService — same refusal as the
    whole-kernel checkpoint; a faked identity would silently lose behaviour).
    """
    with init._lock:  # noqa: SLF001 (orchestrator owns this lock)
        if name not in init._table:  # noqa: SLF001
            raise CheckpointError(
                f"process {name!r} is not admitted; cannot cold-store"
            )
        ap = init._table[name]  # noqa: SLF001
        manifest_json = _manifest_to_json(ap.manifest)
        identity = _service_identity(ap.service)  # refuses non-checkpointable
        inbox = init._router._inboxes.get(name, deque())  # noqa: SLF001

        header = struct.pack(
            _PROC_HEADER_FMT, _MAGIC_PROC, _VERSION_PROC, b"\x00\x00\x00"
        )
        parts: list[bytes] = [
            header,
            _pack_section(name.encode("utf-8")),
            _pack_section(manifest_json.encode("utf-8")),
            _pack_section(json.dumps(identity, sort_keys=True).encode("utf-8")),
            struct.pack("<I", len(inbox)),
        ]
        for axon in inbox:
            parts.append(_pack_section(serialise_axon(axon)))
        return b"".join(parts)


def parse_process(
    data: bytes | bytearray | memoryview,
    *,
    device: Any = None,
) -> ColdProcess:
    """Decode a per-process cold-store blob produced by :func:`serialise_process`.

    ``device`` places the restored inbox axons (default ``None`` → CPU; the
    caller — :meth:`Init.restore_from_cold` — passes the reloaded service's
    own device so the round-trip is bit-exact). Raises :class:`CheckpointError`
    on bad magic / version / truncation.
    """
    if len(data) < _PROC_HEADER_SIZE:
        raise CheckpointError(
            f"data too short for cold-store header: {len(data)} bytes"
        )
    magic, version, _reserved = struct.unpack(
        _PROC_HEADER_FMT, bytes(data[:_PROC_HEADER_SIZE])
    )
    if magic != _MAGIC_PROC:
        raise CheckpointError(
            f"bad cold-store magic {magic!r}; expected {_MAGIC_PROC!r}"
        )
    if version != _VERSION_PROC:
        raise CheckpointError(
            f"unsupported cold-store version {version}; reads {_VERSION_PROC}"
        )
    offset = _PROC_HEADER_SIZE
    name_bytes, offset = _unpack_section(data, offset)
    name = name_bytes.decode("utf-8")
    manifest_bytes, offset = _unpack_section(data, offset)
    manifest = _manifest_from_json(manifest_bytes.decode("utf-8"))
    identity_bytes, offset = _unpack_section(data, offset)
    identity = json.loads(identity_bytes.decode("utf-8"))

    if offset + 4 > len(data):
        raise CheckpointError(f"truncated at inbox count for process {name!r}")
    (inbox_count,) = struct.unpack_from("<I", data, offset)
    offset += 4
    axon_device = device if device is not None else "cpu"
    axons: list[Axon] = []
    for _ in range(inbox_count):
        envelope_bytes, offset = _unpack_section(data, offset)
        axons.append(deserialise_axon(envelope_bytes, device=axon_device))
    return ColdProcess(name=name, manifest=manifest, identity=identity, axons=axons)


__all__ = [
    "CheckpointError",
    "ColdProcess",
    "parse_process",
    "restore_kernel_state",
    "serialise_kernel_state",
    "serialise_process",
]
