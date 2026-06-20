"""Round-trip an axon payload through bytes — Emma's "easy slice" (2026-05-24).

The payload tensor + the bindings it carries must come back bit-exact after
``serialise_axon_payload`` → ``deserialise_axon_payload``. Two layers of
verification:

  1. Pure tensor round-trip across every supported dtype — no VSA needed,
     just ``torch.equal``.
  2. Through the calc's real VSA: bind several values into an axon,
     serialise, deserialise, decode each binding through ``axon_item``,
     check every decoded value is unchanged. This is the substrate-purity
     check — the bytes capture the VALUE, not a host re-computation of it.

Torch-gated like the other real-Sutra integration tests.
"""
from __future__ import annotations

import pathlib
import struct
import sys

import pytest

torch = pytest.importorskip("torch", reason="axon serialise round-trip needs torch")

from kernel.serialise import (  # noqa: E402
    AxonSerialiseError,
    deserialise_axon_payload,
    serialise_axon_payload,
)


# --- Layer 1: pure tensor round-trip ----------------------------------------


@pytest.mark.parametrize(
    "dtype,width,values",
    [
        (torch.float32, 8, [0.0, 1.0, -1.0, 3.14159, -2.71828, 1e10, -1e-10, 42.0]),
        (torch.float64, 8, [0.0, 1.0, -1.0, 3.141592653589793, 2.718281828459045,
                            1.797e308, -1e-308, 9.007199254740992e15]),
        (torch.complex64, 4, [1 + 2j, -3 - 4j, 0 + 0j, 1.5 - 0.5j]),
        (torch.complex128, 4, [1 + 2j, -3 - 4j, 0 + 0j, 1.5 - 0.5j]),
    ],
)
def test_round_trip_bit_exact(dtype, width, values) -> None:
    """Every supported dtype round-trips bit-exact through serialise/deserialise."""
    t = torch.tensor(values, dtype=dtype)
    data = serialise_axon_payload(t)
    restored = deserialise_axon_payload(data)
    assert torch.equal(restored, t), (
        f"round-trip not bit-exact for {dtype}: {t.tolist()} -> {restored.tolist()}"
    )
    assert restored.dtype == dtype
    assert restored.shape == (width,)


def test_round_trip_preserves_large_vsa_width() -> None:
    """A 768-d float32 axon (the runtime dim) round-trips bit-exact."""
    t = torch.randn(768, dtype=torch.float32)
    restored = deserialise_axon_payload(serialise_axon_payload(t))
    assert torch.equal(restored, t)


def test_round_trip_preserves_float64_runtime_dtype() -> None:
    """The calc's float64 substrate runtime dtype round-trips bit-exact."""
    t = torch.randn(768, dtype=torch.float64)
    restored = deserialise_axon_payload(serialise_axon_payload(t))
    assert torch.equal(restored, t)


def test_deserialise_to_cpu_explicitly() -> None:
    """Explicit ``device='cpu'`` matches the default (no surprise relocation)."""
    t = torch.tensor([1.0, 2.0, 3.0], dtype=torch.float32)
    restored = deserialise_axon_payload(serialise_axon_payload(t), device="cpu")
    assert restored.device.type == "cpu"
    assert torch.equal(restored, t)


@pytest.mark.skipif(not torch.cuda.is_available(), reason="needs CUDA")
def test_round_trip_cuda_device() -> None:
    """Restoring with ``device='cuda'`` places the tensor on GPU with the same values."""
    t = torch.randn(768, dtype=torch.float32, device="cuda")
    data = serialise_axon_payload(t)
    restored = deserialise_axon_payload(data, device="cuda")
    assert restored.device.type == "cuda"
    assert torch.equal(restored.cpu(), t.cpu())


# --- Layer 2: rejection paths -----------------------------------------------


def test_rejects_non_tensor() -> None:
    with pytest.raises(AxonSerialiseError):
        serialise_axon_payload([1.0, 2.0, 3.0])  # type: ignore[arg-type]


def test_rejects_2d_tensor() -> None:
    with pytest.raises(AxonSerialiseError, match="1-D"):
        serialise_axon_payload(torch.zeros(4, 4))


def test_rejects_unsupported_dtype() -> None:
    with pytest.raises(AxonSerialiseError, match="unsupported dtype"):
        serialise_axon_payload(torch.zeros(4, dtype=torch.int32))


def test_rejects_truncated_data() -> None:
    with pytest.raises(AxonSerialiseError, match="too short"):
        deserialise_axon_payload(b"YAXN")  # header truncated


def test_rejects_bad_magic() -> None:
    bad = b"NOPE" + b"\x01\x00\x00\x00\x08\x00\x00\x00" + b"\x00" * 32
    with pytest.raises(AxonSerialiseError, match="bad magic"):
        deserialise_axon_payload(bad)


def test_rejects_wrong_version() -> None:
    bad = b"YAXN" + struct.pack("<BBHI", 99, 0, 0, 8) + b"\x00" * 32
    with pytest.raises(AxonSerialiseError, match="unsupported version"):
        deserialise_axon_payload(bad)


def test_rejects_body_size_mismatch() -> None:
    # float32 width=8 → expected body 32 bytes; give it 16.
    bad = b"YAXN" + struct.pack("<BBHI", 1, 0, 0, 8) + b"\x00" * 16
    with pytest.raises(AxonSerialiseError, match="body size mismatch"):
        deserialise_axon_payload(bad)


# --- Layer 3: through the calc's real VSA -----------------------------------


@pytest.fixture(scope="module")
def calc_vsa():
    """The calc's _VSA — exercises the full bind/permute/embed pipeline."""
    sys.path.insert(
        0, str(pathlib.Path(__file__).resolve().parent.parent / "apps" / "calc")
    )
    from calc import Calculator

    calc = Calculator()
    return calc._service._compiled_module._VSA  # noqa: SLF001


def test_bindings_decode_after_round_trip(calc_vsa) -> None:
    """An axon with several real bindings round-trips and each binding still
    decodes through ``axon_item`` — the substrate value is captured bit-exact,
    not a host approximation. This is the substrate-purity check (CLAUDE.md
    § "Substrate purity"): we read the decoded values BEFORE and AFTER and
    require them to match.
    """
    vsa = calc_vsa
    axon = vsa.axon_add(vsa.zero_vector(), "a", 3.14159)
    axon = vsa.axon_add(axon, "b", -42.0)
    axon = vsa.axon_add(axon, "op_char", "+")

    a_before = float(vsa._re(vsa.axon_item(axon, "a")))
    b_before = float(vsa._re(vsa.axon_item(axon, "b")))
    # ``string_char_at`` returns a 0-d scalar (the codepoint at the index);
    # ``float()`` decodes it directly. The substrate-side calc lifts this
    # back through ``make_real`` before returning, but for a host audit we
    # read the scalar directly. Bundling noise from a/b is preserved
    # bit-exact by the round-trip, so the before/after values match.
    cp_op = vsa.axon_item(axon, "op_char")
    cp_before = float(vsa.string_char_at(cp_op, 0))

    data = serialise_axon_payload(axon)
    restored = deserialise_axon_payload(data, device=axon.device)

    assert torch.equal(restored, axon), "tensor round-trip is not bit-exact"

    a_after = float(vsa._re(vsa.axon_item(restored, "a")))
    b_after = float(vsa._re(vsa.axon_item(restored, "b")))
    cp_after = float(vsa.string_char_at(vsa.axon_item(restored, "op_char"), 0))

    assert a_after == a_before, f"binding 'a' drift: {a_before} -> {a_after}"
    assert b_after == b_before, f"binding 'b' drift: {b_before} -> {b_after}"
    assert cp_after == cp_before, f"op_char codepoint drift: {cp_before} -> {cp_after}"


def test_axon_envelope_round_trip(calc_vsa) -> None:
    """A full ``Axon`` (role / payload / from_proc / keys) round-trips through
    ``serialise_axon`` / ``deserialise_axon`` — every field preserved, payload
    bit-exact. This is the foundation for orchestrator-level checkpoint (c):
    each entry in a program's inbox is one of these envelopes.
    """
    from kernel.router import Axon  # type: ignore[import-not-found]
    from kernel.serialise import deserialise_axon, serialise_axon

    vsa = calc_vsa
    payload = vsa.axon_add(vsa.zero_vector(), "a", 7.5)
    payload = vsa.axon_add(payload, "b", -1.25)

    original = Axon(
        role="R_switch_in",
        payload=payload,
        from_proc="calc_in",
        keys=frozenset({"a", "b"}),
    )
    data = serialise_axon(original)
    restored = deserialise_axon(data, device=payload.device)

    assert restored.role == original.role
    assert restored.from_proc == original.from_proc
    assert restored.keys == original.keys
    assert torch.equal(restored.payload, original.payload)

    # And bindings still decode through axon_item from the restored payload.
    assert float(vsa._re(vsa.axon_item(restored.payload, "a"))) == float(
        vsa._re(vsa.axon_item(original.payload, "a"))
    )


def test_axon_envelope_preserves_empty_keys_and_unicode(calc_vsa) -> None:
    """The envelope handles edge cases: empty key set, Unicode in role/from_proc/keys."""
    from kernel.router import Axon
    from kernel.serialise import deserialise_axon, serialise_axon

    vsa = calc_vsa
    payload = vsa.axon_add(vsa.zero_vector(), "value", 42.0)

    original = Axon(
        role="R_λ_out",  # Unicode role
        payload=payload,
        from_proc="процесс",  # Cyrillic from_proc
        keys=frozenset(),  # empty key set
    )
    data = serialise_axon(original)
    restored = deserialise_axon(data, device=payload.device)
    assert restored.role == "R_λ_out"
    assert restored.from_proc == "процесс"
    assert restored.keys == frozenset()
    assert torch.equal(restored.payload, payload)


def test_axon_envelope_rejects_bad_magic() -> None:
    """A blob that is not a YAXE envelope is refused at the header."""
    from kernel.serialise import deserialise_axon

    bad = b"NOPE" + b"\x01\x00\x00\x00" + b"\x00" * 16
    with pytest.raises(AxonSerialiseError, match="envelope magic"):
        deserialise_axon(bad)


def test_axon_envelope_rejects_non_axon_input() -> None:
    """Passing a plain tensor (not an Axon) to the envelope encoder is refused."""
    from kernel.serialise import serialise_axon

    with pytest.raises(AxonSerialiseError, match="not an Axon"):
        serialise_axon(torch.zeros(8))  # type: ignore[arg-type]


def test_format_header_layout(calc_vsa) -> None:
    """The first 12 bytes match the documented header layout — Rust readers
    can rely on this without re-discovering the offsets. Pulls one real axon
    so the width field reflects the actual runtime dim, not a synthetic guess.
    """
    vsa = calc_vsa
    axon = vsa.axon_add(vsa.zero_vector(), "a", 1.0)
    data = serialise_axon_payload(axon)

    assert data[:4] == b"YAXN", "magic must be 'YAXN' for Rust portability"
    version = data[4]
    assert version == 1, f"current version is 1, got {version}"
    dtype_tag = data[5]
    assert dtype_tag in (0, 1, 2, 3), (
        f"dtype tag {dtype_tag} not in the documented set 0..3"
    )
    width = struct.unpack("<I", data[8:12])[0]
    assert width == axon.shape[0]
    elem_size = axon.element_size()
    assert len(data) == 12 + width * elem_size
