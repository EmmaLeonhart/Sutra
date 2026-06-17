"""Orchestrator-state checkpoint round-trip — (c) the actual RAM cold-store.

The kernel's state (admission table + tier map + per-program inboxes) must
round-trip through bytes such that a restored kernel processes any queued
axons identically to the original. This test exercises the full path
through a real Sutra service (echo) — no host stand-in for the substrate
side.

Finding behind this test (`planning/26-orchestrator-serialisation.md`
§ "(b) finding 2026-05-25"): the long-pole serialisation framing required
a Sutra-side ``serialise-process-state`` primitive that current Sutra does
not need (purely functional language, no persistent per-program substrate
state). The orchestrator's own state is what was blocking RAM cold-store,
and ``kernel/checkpoint.py`` ships it.

Torch-gated like the other real-Sutra tests.
"""
from __future__ import annotations

import pathlib

import pytest

torch = pytest.importorskip("torch", reason="kernel checkpoint runs through real Sutra")

from kernel import (  # noqa: E402
    CheckpointError,
    Init,
    Manifest,
    PythonService,
    SutraService,
    Tier,
    load_manifest,
    restore_kernel_state,
    serialise_kernel_state,
)
from kernel.router import Axon  # noqa: E402


REPO = pathlib.Path(__file__).resolve().parent.parent
APPS_ECHO = REPO / "apps" / "echo"


def _echo_factory(name: str, identity: dict) -> SutraService:
    """A services_factory that knows how to build the echo service.

    In a real deployment this would be a registry mapping names → known
    program identities; for tests it's a small per-test closure that
    asserts the identity matches what we expected and builds a fresh
    service.
    """
    assert identity["kind"] == "sutra", (
        f"expected sutra service, got identity={identity!r}"
    )
    return SutraService(
        source_path=identity["source_path"],
        output_role=identity["output_role"],
        runtime_dtype=identity["runtime_dtype"],
        llm_model=identity["llm_model"],
        entry_point=identity["entry_point"],
    )


def _build_kernel_with_echo() -> tuple[Init, SutraService]:
    """Helper: a fresh Init with echo admitted (no other processes)."""
    init = Init(compute_pool=10)
    echo = SutraService(
        source_path=APPS_ECHO / "echo.su",
        output_role="R_stdout",
    )
    init.admit_from_path(APPS_ECHO / "echo.toml", echo)
    return init, echo


def _push_axon_into_inbox(init: Init, name: str, axon: Axon) -> None:
    """Inject an axon directly into a program's inbox (orchestrator state)."""
    with init._lock:  # noqa: SLF001
        init._router._inboxes[name].append(axon)  # noqa: SLF001


# --- Round-trip layer ------------------------------------------------------


def test_empty_kernel_round_trip() -> None:
    """A kernel with no admitted processes round-trips through bytes."""
    init = Init(compute_pool=10)
    data = serialise_kernel_state(init)
    restored = restore_kernel_state(data, services_factory=lambda n, i: None)  # type: ignore[arg-type]
    assert restored.admitted() == []
    # Pool totals preserved.
    assert restored._compute_pool_total == init._compute_pool_total  # noqa: SLF001
    assert restored._compute_pool_free == init._compute_pool_free  # noqa: SLF001


def test_admitted_echo_round_trip() -> None:
    """Echo's manifest + tier + identity survive a checkpoint round-trip."""
    init, _echo = _build_kernel_with_echo()
    data = serialise_kernel_state(init)
    restored = restore_kernel_state(data, services_factory=_echo_factory)

    assert restored.admitted() == ["echo"]
    assert restored.tier("echo") == Tier.GPU
    # The restored service is a fresh SutraService instance built from the
    # captured identity. Manifest fields preserved exactly.
    orig_m = init._table["echo"].manifest  # noqa: SLF001
    rest_m = restored._table["echo"].manifest  # noqa: SLF001
    assert rest_m == orig_m
    # Pool budget after restore matches the original.
    assert restored._compute_pool_free == init._compute_pool_free  # noqa: SLF001


def test_inbox_axons_round_trip_bit_exact() -> None:
    """An axon pushed into an inbox before checkpoint is recovered bit-exact
    after restore — every field (role, payload, from_proc, keys)."""
    init, echo = _build_kernel_with_echo()
    vsa = echo._compiled_module._VSA  # noqa: SLF001

    a1 = Axon(
        role="R_stdin",
        payload=vsa.axon_add(vsa.zero_vector(), "stdin_text", vsa.make_string("hello")),
        from_proc="external",
        keys=frozenset({"stdin_text"}),
    )
    a2 = Axon(
        role="R_stdin",
        payload=vsa.axon_add(vsa.zero_vector(), "stdin_text", vsa.make_string("world")),
        from_proc="external",
        keys=frozenset({"stdin_text"}),
    )
    _push_axon_into_inbox(init, "echo", a1)
    _push_axon_into_inbox(init, "echo", a2)

    data = serialise_kernel_state(init)
    restored = restore_kernel_state(data, services_factory=_echo_factory)

    restored_inbox = list(restored._router._inboxes["echo"])  # noqa: SLF001
    assert len(restored_inbox) == 2
    for original, copy in zip([a1, a2], restored_inbox):
        assert copy.role == original.role
        assert copy.from_proc == original.from_proc
        assert copy.keys == original.keys
        assert torch.equal(copy.payload, original.payload)


def test_disc_tier_round_trip() -> None:
    """A process on DISC at checkpoint comes back on DISC after restore."""
    init, _echo = _build_kernel_with_echo()
    init.unload("echo")
    assert init.tier("echo") == Tier.DISC

    data = serialise_kernel_state(init)
    restored = restore_kernel_state(data, services_factory=_echo_factory)
    assert restored.tier("echo") == Tier.DISC


# --- Behavioural layer: a restored kernel runs the same -------------------


def test_restored_kernel_processes_inbox_identically() -> None:
    """The substantive substrate-purity check: tick a kernel with a queued
    axon AND tick a restored copy of that kernel, and the outputs that echo
    emits must match bit-exact. This is what (c) is FOR — a connectome can
    be cold-stored and brought back with no behavioural drift.
    """
    # Build the original kernel: echo + a sink that records what echo emits.
    init, echo = _build_kernel_with_echo()
    received_orig: list[Axon] = []
    sink_orig = PythonService(on_axon=lambda s, ax: received_orig.append(ax))
    init.admit(
        Manifest(
            name="stdout_sink", axon_width=768, compute_units=1,
            read_roles=frozenset({"R_stdout"}), write_roles=frozenset(),
            source="sink.py", axon_keys=frozenset({"stdout_text"}),
        ),
        sink_orig,
    )

    vsa = echo._compiled_module._VSA  # noqa: SLF001
    msg = vsa.axon_add(vsa.zero_vector(), "stdin_text", vsa.make_string("checkpoint"))
    queued = Axon(
        role="R_stdin", payload=msg, from_proc="external",
        keys=frozenset({"stdin_text"}),
    )
    _push_axon_into_inbox(init, "echo", queued)

    # Checkpoint BEFORE we tick — we want the post-restore behaviour to
    # match the post-tick behaviour of the original.
    # PythonService can't be in the checkpoint, so deregister the sink first.
    init.deregister("stdout_sink")
    # Re-admit the sink so we can still tick the original and compare.
    sink_after = PythonService(on_axon=lambda s, ax: received_orig.append(ax))
    init.admit(
        Manifest(
            name="stdout_sink", axon_width=768, compute_units=1,
            read_roles=frozenset({"R_stdout"}), write_roles=frozenset(),
            source="sink.py", axon_keys=frozenset({"stdout_text"}),
        ),
        sink_after,
    )
    # Now (after re-admit) the original kernel has the sink + the queued axon.
    # Take the checkpoint snapshot... but we can't because PythonService is
    # un-checkpointable. So: snapshot a kernel that has ONLY echo + the
    # queued axon; rebuild that on restore; admit a sink on the restored
    # side to receive echo's emission.
    only_echo, _ = _build_kernel_with_echo()
    _push_axon_into_inbox(only_echo, "echo", queued)
    data = serialise_kernel_state(only_echo)

    # Restore.
    restored = restore_kernel_state(data, services_factory=_echo_factory)
    # Admit a sink on the restored side so we can read what echo emits.
    received_restored: list[Axon] = []
    restored.admit(
        Manifest(
            name="stdout_sink", axon_width=768, compute_units=1,
            read_roles=frozenset({"R_stdout"}), write_roles=frozenset(),
            source="sink.py", axon_keys=frozenset({"stdout_text"}),
        ),
        PythonService(on_axon=lambda s, ax: received_restored.append(ax)),
    )

    # Tick original (queued → echo emits → sink receives).
    init.tick()  # fire echo, drains R_stdin
    init.tick()  # fire sink, drains R_stdout
    # Tick restored.
    restored.tick()
    restored.tick()

    assert len(received_orig) == 1
    assert len(received_restored) == 1
    orig_out = received_orig[0]
    rest_out = received_restored[0]
    assert orig_out.role == rest_out.role == "R_stdout"
    assert orig_out.from_proc == rest_out.from_proc == "echo"
    assert orig_out.keys == rest_out.keys
    # The decisive check: the substrate's emitted value matches across the
    # two kernels. echo is purely functional, the input axon is identical
    # bit-exact, so the output should be identical bit-exact.
    assert torch.equal(orig_out.payload, rest_out.payload), (
        "restored kernel did not produce a bit-exact match — checkpoint "
        "lost orchestrator state somewhere"
    )

    # And the decoded string still recovers verbatim.
    restored_vsa = restored._table["echo"].service._compiled_module._VSA  # noqa: SLF001
    decoded_restored = restored_vsa.string_to_python(
        restored_vsa.axon_item(rest_out.payload, "stdout_text")
    )
    assert decoded_restored == "checkpoint"


# --- Refusal paths --------------------------------------------------------


def test_checkpoint_refuses_python_service() -> None:
    """PythonService callables aren't serialisable; the checkpoint REFUSES
    rather than ship a no-op stub. CLAUDE.md "no fake primitives": a
    checkpoint that silently drops a program would be the documented
    fake-substrate failure mode.
    """
    init = Init(compute_pool=5)
    init.admit(
        Manifest(
            name="stub", axon_width=768, compute_units=1,
            read_roles=frozenset({"R_in"}), write_roles=frozenset(),
            source="stub.py", axon_keys=frozenset(),
        ),
        PythonService(lambda s, ax: None),
    )
    with pytest.raises(CheckpointError, match="not checkpointable"):
        serialise_kernel_state(init)


def test_restore_refuses_bad_magic() -> None:
    """A blob that isn't a YKST checkpoint is refused at the header."""
    bad = b"NOPE" + b"\x00" * 32
    with pytest.raises(CheckpointError, match="checkpoint magic"):
        restore_kernel_state(bad, services_factory=lambda n, i: None)  # type: ignore[arg-type]


def test_restore_refuses_truncated_data() -> None:
    """Truncated bytes raise CheckpointError, not a partial-state Init."""
    with pytest.raises(CheckpointError, match="too short"):
        restore_kernel_state(b"YKST", services_factory=lambda n, i: None)  # type: ignore[arg-type]


def test_restore_refuses_ram_tier() -> None:
    """A whole-kernel checkpoint never legitimately carries a RAM-tier member
    (serialise_kernel_state refuses one — a cold-stored process's inbox lives
    in a separate YPRC blob, not the kernel checkpoint). A YKST blob with a
    RAM tag is therefore malformed/hand-crafted, and restore refuses it rather
    than rebuild a process with a silently-empty inbox. RAM cold-store has its
    own round-trip path — see tests/test_kernel_ram_tier.py.
    """
    # Manually craft a minimal checkpoint with tier tag 2 (RAM).
    import struct
    name = b"echo"
    manifest_json = (
        b'{"axon_keys":[],"axon_width":768,"compute_units":1,"name":"echo",'
        b'"read_roles":["R_stdin"],"source":"echo.su","write_roles":["R_stdout"]}'
    )
    identity_json = (
        b'{"entry_point":"on_axon","kind":"sutra","llm_model":"nomic-embed-text",'
        b'"output_role":"R_stdout","runtime_dtype":"float32","source_path":"x"}'
    )
    blob = (
        struct.pack("<4sB3sIII", b"YKST", 1, b"\x00\x00\x00", 10, 9, 1)
        + struct.pack("<I", len(name)) + name
        + struct.pack("<I", len(manifest_json)) + manifest_json
        + struct.pack("<B3s", 2, b"\x00\x00\x00")  # tier=RAM
        + struct.pack("<I", len(identity_json)) + identity_json
        + struct.pack("<I", 0)  # empty inbox
    )
    with pytest.raises(CheckpointError, match="tier RAM"):
        restore_kernel_state(blob, services_factory=_echo_factory)
