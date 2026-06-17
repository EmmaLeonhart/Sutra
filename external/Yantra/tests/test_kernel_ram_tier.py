"""Tier.RAM per-process cold-store round-trip — planning/26 § 3.

``Init.cold_store(name)`` captures a process's in-flight inbox to a host
blob, frees its GPU residency, and marks it ``RAM``;
``Init.restore_from_cold(name, blob)`` resumes it bit-exact. This is pure
orchestrator-side serialisation — it needs NO Sutra ``serialise-process-
state`` primitive (the 2026-05-25 finding; see the ``Tier`` docstring and
``planning/26-orchestrator-serialisation.md``).

Contrast with DISC (``unload`` / ``load``): DISC reloads a program *fresh*
(queued work lost); RAM preserves the inbox.

Torch-gated like the other real-Sutra kernel tests — the round-trip runs
through a real compiled echo service, not a host stand-in.
"""
from __future__ import annotations

import dataclasses
import pathlib

import pytest

torch = pytest.importorskip("torch", reason="RAM cold-store runs through real Sutra")

from kernel import (  # noqa: E402
    AdmissionError,
    CheckpointError,
    Init,
    Manifest,
    PythonService,
    SutraService,
    Tier,
    load_manifest,
    serialise_kernel_state,
)
from kernel.router import Axon  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parent.parent
APPS_ECHO = REPO / "apps" / "echo"


def _build_kernel_with_echo() -> tuple[Init, SutraService]:
    init = Init(compute_pool=10)
    echo = SutraService(source_path=APPS_ECHO / "echo.su", output_role="R_stdout")
    init.admit_from_path(APPS_ECHO / "echo.toml", echo)
    return init, echo


def _admit_echo_as(init: Init, name: str) -> SutraService:
    """Admit a second echo-backed service under a different manifest name."""
    svc = SutraService(source_path=APPS_ECHO / "echo.su", output_role="R_stdout")
    base = load_manifest(APPS_ECHO / "echo.toml")
    init.admit(dataclasses.replace(base, name=name), svc)
    return svc


def _sink_manifest() -> Manifest:
    return Manifest(
        name="stdout_sink", axon_width=768, compute_units=1,
        read_roles=frozenset({"R_stdout"}), write_roles=frozenset(),
        source="sink.py", axon_keys=frozenset({"stdout_text"}),
    )


def _stdin_axon(vsa, text: str) -> Axon:
    return Axon(
        role="R_stdin",
        payload=vsa.axon_add(vsa.zero_vector(), "stdin_text", vsa.make_string(text)),
        from_proc="external",
        keys=frozenset({"stdin_text"}),
    )


def _push(init: Init, name: str, axon: Axon) -> None:
    with init._lock:  # noqa: SLF001
        init._router._inboxes[name].append(axon)  # noqa: SLF001


# --- Round-trip layer ------------------------------------------------------


def test_cold_store_round_trips_inbox_bit_exact() -> None:
    """Two axons queued before cold-store come back bit-exact after restore —
    every field (role, from_proc, keys, payload)."""
    init, echo = _build_kernel_with_echo()
    vsa = echo._compiled_module._VSA  # noqa: SLF001
    a1 = _stdin_axon(vsa, "hello")
    a2 = _stdin_axon(vsa, "world")
    # Clone the originals: cold_store tears the service down, and we want an
    # independent reference to compare against.
    originals = [
        (a1.role, a1.from_proc, a1.keys, a1.payload.clone()),
        (a2.role, a2.from_proc, a2.keys, a2.payload.clone()),
    ]
    _push(init, "echo", a1)
    _push(init, "echo", a2)

    blob = init.cold_store("echo")
    # Cold-stored: RAM tier, GPU residency freed, live inbox cleared.
    assert init.tier("echo") is Tier.RAM
    assert "echo" not in init.gpu_resident()
    assert not echo.is_loaded
    assert len(init._router._inboxes["echo"]) == 0  # noqa: SLF001

    init.restore_from_cold("echo", blob)
    # Resumed: GPU tier, runtime reloaded, inbox refilled.
    assert init.tier("echo") is Tier.GPU
    assert init._table["echo"].service.is_loaded  # noqa: SLF001
    assert "echo" in init.gpu_resident()

    inbox = list(init._router._inboxes["echo"])  # noqa: SLF001
    assert len(inbox) == 2
    for (role, from_proc, keys, payload), copy in zip(originals, inbox):
        assert copy.role == role
        assert copy.from_proc == from_proc
        assert copy.keys == keys
        assert torch.equal(copy.payload, payload.to(copy.payload.device))


def test_cold_store_empty_inbox_round_trips() -> None:
    """A process with no queued work cold-stores and restores cleanly."""
    init, _echo = _build_kernel_with_echo()
    blob = init.cold_store("echo")
    assert init.tier("echo") is Tier.RAM
    init.restore_from_cold("echo", blob)
    assert init.tier("echo") is Tier.GPU
    assert len(init._router._inboxes["echo"]) == 0  # noqa: SLF001


def test_tier_transitions_gpu_ram_gpu() -> None:
    """The tier walks GPU → RAM → GPU across a cold-store/restore cycle."""
    init, _echo = _build_kernel_with_echo()
    assert init.tier("echo") is Tier.GPU
    blob = init.cold_store("echo")
    assert init.tier("echo") is Tier.RAM
    init.restore_from_cold("echo", blob)
    assert init.tier("echo") is Tier.GPU


# --- Behavioural layer: a cold-stored process resumes identically ----------


def test_cold_store_resumes_behaviour_identically() -> None:
    """The decisive substrate check: a cold-stored-then-restored echo emits
    bit-exact the same output as a control echo that was never cold-stored,
    for the same queued input — and the decoded string recovers verbatim."""
    # Control: echo + queued axon, ticked directly.
    ctrl, echo_c = _build_kernel_with_echo()
    received_ctrl: list[Axon] = []
    ctrl.admit(_sink_manifest(), PythonService(on_axon=lambda s, ax: received_ctrl.append(ax)))
    vsa_c = echo_c._compiled_module._VSA  # noqa: SLF001
    _push(ctrl, "echo", _stdin_axon(vsa_c, "resume"))

    # Test: echo + queued axon, cold-stored then restored, THEN ticked.
    test, echo_t = _build_kernel_with_echo()
    vsa_t = echo_t._compiled_module._VSA  # noqa: SLF001
    _push(test, "echo", _stdin_axon(vsa_t, "resume"))
    blob = test.cold_store("echo")
    test.restore_from_cold("echo", blob)
    received_test: list[Axon] = []
    test.admit(_sink_manifest(), PythonService(on_axon=lambda s, ax: received_test.append(ax)))

    for kernel in (ctrl, test):
        kernel.tick()  # echo drains R_stdin → emits R_stdout
        kernel.tick()  # sink drains R_stdout

    assert len(received_ctrl) == 1
    assert len(received_test) == 1
    out_c, out_t = received_ctrl[0], received_test[0]
    assert out_c.role == out_t.role == "R_stdout"
    assert out_c.from_proc == out_t.from_proc == "echo"
    assert out_c.keys == out_t.keys
    assert torch.equal(out_c.payload, out_t.payload.to(out_c.payload.device))

    vsa_out = test._table["echo"].service._compiled_module._VSA  # noqa: SLF001
    decoded = vsa_out.string_to_python(vsa_out.axon_item(out_t.payload, "stdout_text"))
    assert decoded == "resume"


# --- Boundary: whole-kernel checkpoint refuses a RAM member ----------------


def test_whole_kernel_checkpoint_refuses_ram_member() -> None:
    """A cold-stored process's inbox lives in an EXTERNAL blob, not the
    router. serialise_kernel_state must refuse rather than silently emit a
    checkpoint that loses the queued work (the fake-success the substrate-
    purity rule forbids)."""
    init, _echo = _build_kernel_with_echo()
    init.cold_store("echo")
    with pytest.raises(CheckpointError, match="tier RAM"):
        serialise_kernel_state(init)


# --- Refusal / error paths -------------------------------------------------


def test_cold_store_unadmitted_raises() -> None:
    init = Init(compute_pool=5)
    with pytest.raises(AdmissionError, match="not admitted"):
        init.cold_store("nope")


def test_cold_store_already_ram_raises() -> None:
    """No live state to capture twice; the caller holds the existing blob."""
    init, _echo = _build_kernel_with_echo()
    init.cold_store("echo")
    with pytest.raises(AdmissionError, match="already cold-stored"):
        init.cold_store("echo")


def test_restore_from_cold_wrong_tier_raises() -> None:
    """restore_from_cold only resumes a RAM-tier process; a GPU-tier one
    (e.g. already restored) is refused."""
    init, _echo = _build_kernel_with_echo()
    blob = init.cold_store("echo")
    init.restore_from_cold("echo", blob)  # back to GPU
    with pytest.raises(AdmissionError, match="not cold-stored"):
        init.restore_from_cold("echo", blob)


def test_restore_from_cold_mismatched_blob_raises() -> None:
    """A blob for a different process is refused (name-mismatch guard), and
    it is caught BEFORE any kernel state is mutated."""
    init, _echo = _build_kernel_with_echo()
    _admit_echo_as(init, "echo2")
    blob_echo = init.cold_store("echo")
    init.cold_store("echo2")
    with pytest.raises(CheckpointError, match="is for process"):
        init.restore_from_cold("echo2", blob_echo)
    # echo2 stays cleanly cold (validate-before-mutate): still RAM, not loaded.
    assert init.tier("echo2") is Tier.RAM
    assert not init._table["echo2"].service.is_loaded  # noqa: SLF001


def test_restore_from_cold_bad_magic_raises() -> None:
    """Bytes that aren't a YPRC blob are refused at the header."""
    init, _echo = _build_kernel_with_echo()
    init.cold_store("echo")
    with pytest.raises(CheckpointError, match="cold-store magic"):
        init.restore_from_cold("echo", b"NOPE" + b"\x00" * 16)
