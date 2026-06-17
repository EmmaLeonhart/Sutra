"""Orchestrator serialisation — Emma 2026-05-24 direction.

Two primitives, building toward the orchestrator-level checkpoint that
unblocks RAM cold-storage of the connectome:

  - :func:`serialise_axon_payload` / :func:`deserialise_axon_payload`
    capture an axon's value (the structured-embedding payload tensor) as
    Rust-portable bytes. This is (a) — the easy slice.
  - :func:`serialise_axon` / :func:`deserialise_axon` wrap the payload
    in the full router envelope (``role``, ``from_proc``, ``keys``) so a
    queued :class:`~kernel.router.Axon` round-trips bit-exact. This is
    the foundation for (c) — orchestrator state checkpoint.

Audited 2026-05-25: the (b) framing of "serialise the program's weights +
in-flight memory" had nothing to capture for current Sutra (purely
functional language; no persistent per-program state). The substantive
blocker is (c) orchestrator state — admission table + tier + router
inboxes — and that needs no Sutra-side primitive. See
``planning/26-orchestrator-serialisation.md`` for the full finding +
build order.

Format (Rust-portable; no Python pickle):

    Payload envelope ('YAXN' / version 1):
        Offset  Size  Field
        0       4     Magic b'YAXN'
        4       1     Version (uint8)
        5       1     Dtype tag (0=float32, 1=float64, 2=complex64, 3=complex128)
        6       2     Reserved (pads to 8-byte boundary)
        8       4     Width (uint32 little-endian)
        12      W*S   Raw little-endian payload (W=width, S=dtype size)

    Axon envelope ('YAXE' / version 1):
        Offset  Size  Field
        0       4     Magic b'YAXE'
        4       1     Version (uint8)
        5       3     Reserved
        8       4     role length (uint32 LE)
        12      Nr    role UTF-8 bytes
        ...     4     from_proc length (uint32 LE)
        ...     Np    from_proc UTF-8 bytes
        ...     4     keys count (uint32 LE)
                      per key: uint32 LE length + UTF-8 bytes
        ...     4     payload bytes length (uint32 LE)
        ...     Lp    payload bytes (a full 'YAXN' envelope)

Round-trip is bit-exact via ``torch.equal`` on the payload. Tested through
the calc's real VSA so every binding (a, b, op_char, ...) decodes unchanged
from a restored tensor — the substrate value is captured, not a host
approximation.
"""
from __future__ import annotations

import struct
from typing import TYPE_CHECKING, Any

import torch

if TYPE_CHECKING:
    from kernel.router import Axon

_MAGIC = b"YAXN"
_MAGIC_ENV = b"YAXE"
_VERSION = 1
_VERSION_ENV = 1
_HEADER_FMT = "<4sBBHI"  # little-endian: magic, version, dtype_tag, reserved, width
_HEADER_SIZE = 12
_ENV_HEADER_FMT = "<4sB3s"  # magic, version, 3-byte reserved (pad to 8)
_ENV_HEADER_SIZE = 8

# Dtype tags — fixed wire numbers; extending the table is allowed but never
# reassigning an existing tag. The eventual Rust reader must agree on this
# mapping, so it lives here as the source of truth.
_DTYPE_TAGS: dict[torch.dtype, int] = {
    torch.float32: 0,
    torch.float64: 1,
    torch.complex64: 2,
    torch.complex128: 3,
}
_TAGS_DTYPE: dict[int, torch.dtype] = {v: k for k, v in _DTYPE_TAGS.items()}


class AxonSerialiseError(ValueError):
    """Raised on malformed bytes, unsupported version, or shape/dtype mismatch."""


def serialise_axon_payload(payload: torch.Tensor) -> bytes:
    """Encode a 1-D axon payload tensor as Rust-portable bytes.

    The payload is the value an axon carries (``Axon.payload``). The bytes
    encode only the tensor — not the role, sender, or keys metadata.

    Constraints:
      - ``payload`` must be a ``torch.Tensor`` (host floats/ints aren't axons).
      - ``payload`` must be 1-D (axons are vectors at the router; higher-rank
        tensors are not axon outputs).
      - Dtype must be one of float32 / float64 / complex64 / complex128.

    Returns bytes with a 12-byte header + ``width * dtype_size`` body. The
    returned object is a plain ``bytes`` (immutable) and is safe to write to
    disk, hand to an IPC channel, or hash for an audit log.
    """
    if not isinstance(payload, torch.Tensor):
        raise AxonSerialiseError(
            f"payload must be a torch.Tensor, got {type(payload).__name__}"
        )
    if payload.dim() != 1:
        raise AxonSerialiseError(
            f"payload must be 1-D, got shape {tuple(payload.shape)}"
        )
    dtype = payload.dtype
    if dtype not in _DTYPE_TAGS:
        raise AxonSerialiseError(
            f"unsupported dtype {dtype}; supported: float32, float64, "
            "complex64, complex128"
        )
    width = int(payload.shape[0])
    # Move to CPU + contiguous for a predictable byte layout. ``detach``
    # drops any autograd history; serialisation is a value capture, not a
    # gradient capture.
    cpu = payload.detach().to("cpu").contiguous()
    body = cpu.numpy().tobytes()
    header = struct.pack(_HEADER_FMT, _MAGIC, _VERSION, _DTYPE_TAGS[dtype], 0, width)
    return header + body


def deserialise_axon_payload(
    data: bytes | bytearray | memoryview,
    device: Any = "cpu",
) -> torch.Tensor:
    """Decode bytes produced by :func:`serialise_axon_payload` back into a tensor.

    The returned tensor has the original dtype and width, placed on
    ``device`` (default ``"cpu"``). Round-trip is bit-exact: for any payload
    ``t`` produced by the encoder, ``torch.equal(deserialise_axon_payload(
    serialise_axon_payload(t)), t.cpu())`` holds.

    Raises :class:`AxonSerialiseError` on bad magic, unsupported version,
    unknown dtype tag, or body-size mismatch.
    """
    if len(data) < _HEADER_SIZE:
        raise AxonSerialiseError(
            f"data too short for header: {len(data)} bytes (need >= {_HEADER_SIZE})"
        )
    magic, version, dtype_tag, _reserved, width = struct.unpack(
        _HEADER_FMT, bytes(data[:_HEADER_SIZE])
    )
    if magic != _MAGIC:
        raise AxonSerialiseError(f"bad magic {magic!r}; expected {_MAGIC!r}")
    if version != _VERSION:
        raise AxonSerialiseError(
            f"unsupported version {version}; this build reads version {_VERSION}"
        )
    if dtype_tag not in _TAGS_DTYPE:
        raise AxonSerialiseError(f"unknown dtype tag {dtype_tag}")
    dtype = _TAGS_DTYPE[dtype_tag]
    elem_size = torch.tensor([], dtype=dtype).element_size()
    expected_body = width * elem_size
    actual_body = len(data) - _HEADER_SIZE
    if actual_body != expected_body:
        raise AxonSerialiseError(
            f"body size mismatch: got {actual_body} bytes, "
            f"expected {expected_body} ({width} * {elem_size})"
        )
    # ``torch.frombuffer`` views the buffer in-place and requires a writable
    # buffer; bytes is immutable, so copy into a bytearray first. The
    # subsequent ``.clone()`` cuts the tie to the buffer so the returned
    # tensor owns its memory.
    body = bytearray(data[_HEADER_SIZE:])
    cpu_tensor = torch.frombuffer(body, dtype=dtype, count=width).clone()
    return cpu_tensor.to(device)


def _pack_u32_prefixed(s: str) -> bytes:
    """Length-prefix a UTF-8 string with a uint32 LE length. The Rust reader
    is a 4-byte read followed by an N-byte read."""
    body = s.encode("utf-8")
    if len(body) > 0xFFFFFFFF:
        raise AxonSerialiseError(f"string too long for u32 length prefix: {len(body)}")
    return struct.pack("<I", len(body)) + body


def _unpack_u32_prefixed(data: bytes | bytearray | memoryview, offset: int) -> tuple[str, int]:
    """Inverse of :func:`_pack_u32_prefixed`. Returns (string, new_offset)."""
    if offset + 4 > len(data):
        raise AxonSerialiseError("truncated u32 length prefix")
    (length,) = struct.unpack_from("<I", data, offset)
    start = offset + 4
    end = start + length
    if end > len(data):
        raise AxonSerialiseError(
            f"truncated UTF-8 body: need {length} bytes from offset {start}, "
            f"only {len(data) - start} available"
        )
    return bytes(data[start:end]).decode("utf-8"), end


def serialise_axon(axon: "Axon") -> bytes:
    """Encode a full :class:`~kernel.router.Axon` as Rust-portable bytes.

    Captures the router envelope (``role``, ``from_proc``, ``keys``) plus
    the payload tensor — everything the router needs to deliver this axon
    again on a fresh kernel. The payload is encoded with
    :func:`serialise_axon_payload` and embedded as a nested blob, so the
    same bit-exact guarantee applies to the value.

    This is the foundation for orchestrator-level checkpoint (c) — see
    ``planning/26-orchestrator-serialisation.md``: each entry in a
    program's inbox round-trips through this function so a cold-restarted
    kernel can resume from exactly where it paused.
    """
    if not hasattr(axon, "role") or not hasattr(axon, "payload"):
        raise AxonSerialiseError(
            f"argument is not an Axon-shaped object (no role/payload): "
            f"{type(axon).__name__}"
        )
    payload_bytes = serialise_axon_payload(axon.payload)
    keys = sorted(axon.keys)  # deterministic order so identical axons → identical bytes
    if len(keys) > 0xFFFFFFFF:
        raise AxonSerialiseError(f"too many keys: {len(keys)}")
    header = struct.pack(_ENV_HEADER_FMT, _MAGIC_ENV, _VERSION_ENV, b"\x00\x00\x00")
    parts = [
        header,
        _pack_u32_prefixed(axon.role),
        _pack_u32_prefixed(axon.from_proc),
        struct.pack("<I", len(keys)),
    ]
    for k in keys:
        parts.append(_pack_u32_prefixed(k))
    parts.append(struct.pack("<I", len(payload_bytes)))
    parts.append(payload_bytes)
    return b"".join(parts)


def deserialise_axon(
    data: bytes | bytearray | memoryview,
    device: Any = "cpu",
) -> "Axon":
    """Decode bytes produced by :func:`serialise_axon` back into an Axon.

    Returns a fresh :class:`~kernel.router.Axon` with the original role /
    from_proc / keys / payload (placed on ``device``). Bit-exact on payload;
    string fields and key set round-trip via UTF-8.

    Raises :class:`AxonSerialiseError` on bad magic, unsupported version,
    truncated section, or any payload-level error from the inner decoder.
    """
    from kernel.router import Axon  # local import: avoid module-load cycle

    if len(data) < _ENV_HEADER_SIZE:
        raise AxonSerialiseError(
            f"data too short for envelope header: {len(data)} bytes"
        )
    magic, version, _reserved = struct.unpack(
        _ENV_HEADER_FMT, bytes(data[:_ENV_HEADER_SIZE])
    )
    if magic != _MAGIC_ENV:
        raise AxonSerialiseError(
            f"bad envelope magic {magic!r}; expected {_MAGIC_ENV!r}"
        )
    if version != _VERSION_ENV:
        raise AxonSerialiseError(
            f"unsupported envelope version {version}; this build reads "
            f"version {_VERSION_ENV}"
        )
    offset = _ENV_HEADER_SIZE
    role, offset = _unpack_u32_prefixed(data, offset)
    from_proc, offset = _unpack_u32_prefixed(data, offset)
    if offset + 4 > len(data):
        raise AxonSerialiseError("truncated at keys count")
    (keys_count,) = struct.unpack_from("<I", data, offset)
    offset += 4
    keys: list[str] = []
    for _ in range(keys_count):
        k, offset = _unpack_u32_prefixed(data, offset)
        keys.append(k)
    if offset + 4 > len(data):
        raise AxonSerialiseError("truncated at payload length")
    (payload_len,) = struct.unpack_from("<I", data, offset)
    offset += 4
    if offset + payload_len > len(data):
        raise AxonSerialiseError(
            f"truncated payload: need {payload_len} bytes from offset {offset}, "
            f"only {len(data) - offset} available"
        )
    payload_bytes = bytes(data[offset : offset + payload_len])
    payload = deserialise_axon_payload(payload_bytes, device=device)
    return Axon(role=role, payload=payload, from_proc=from_proc, keys=frozenset(keys))


__all__ = [
    "AxonSerialiseError",
    "deserialise_axon",
    "deserialise_axon_payload",
    "serialise_axon",
    "serialise_axon_payload",
]
