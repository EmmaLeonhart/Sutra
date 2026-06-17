"""Kernel MVP: load / unload a program onto the real GPU.

The Connectome Manager's core job is moving programs between
storage tiers. This proves the DISC<->GPU slice on the **real GPU**
(measured, not asserted by faith):

  - admit a real per-service-compile `SutraService` -> it is
    GPU-resident (`_VSA.device` is cuda; GPU memory rises).
  - `init.unload(name)` -> the Sutra runtime is torn down,
    `torch.cuda.memory_allocated()` strictly drops, the program no
    longer runs on `tick()`.
  - `init.load(name)` -> GPU memory rises again, the program runs
    and produces the correct output again.

Honest scope: this is *residency* (load-fresh / drop). A running
program's mutated state is NOT preserved across unload — that needs
the Sutra `serialise-process-state` primitive, which does not
exist. The MVP semantics are "start/stop a program on the GPU".

Gated: skipped without torch, and skipped (not failed) without
CUDA — the measurement is meaningless on CPU and CI lanes without
a GPU must still pass.
"""

from __future__ import annotations

import pathlib

import pytest

torch = pytest.importorskip("torch", reason="kernel GPU tiers need torch")
if not torch.cuda.is_available():
    pytest.skip(
        "no CUDA device — GPU residency move is unmeasurable on CPU",
        allow_module_level=True,
    )

from kernel import Init, Manifest, PythonService, SutraService, Tier
from kernel.router import Axon

KERNEL_DIR = pathlib.Path(__file__).resolve().parent.parent / "kernel"
ECHO_SU = KERNEL_DIR / "services" / "echo.su"
AXON_WIDTH = 768


def _mem() -> int:
    torch.cuda.synchronize()
    return torch.cuda.memory_allocated()


_CAPTURED: list = []


@pytest.fixture(scope="module")
def loaded_echo():
    """A real per-service-compile SutraService (echo.su), admitted,
    plus a sink that *captures* echo's R_output into _CAPTURED (the
    sink is ticked by init.tick() like any process, so it must keep
    what it receives rather than discard it)."""
    base = _mem()
    init = Init(compute_pool=5)

    echo = SutraService(source_path=ECHO_SU, output_role="R_output")
    init.admit(
        Manifest(
            name="echo", axon_width=AXON_WIDTH, compute_units=1,
            read_roles=frozenset({"R_input"}),
            write_roles=frozenset({"R_output"}),
            source="services/echo.su",
        ),
        echo,
    )
    sink = PythonService(lambda s, ax: _CAPTURED.append(ax.payload))
    init.admit(
        Manifest(
            name="sink", axon_width=AXON_WIDTH, compute_units=1,
            read_roles=frozenset({"R_output"}),
            write_roles=frozenset(),
            source="sink.py",
        ),
        sink,
    )
    return init, echo, base


def _run_echo_once(init: Init, echo: SutraService, val: float):
    """Inject one axon into echo, tick, return the tensor delivered
    to sink (echo's output) or None. Uses the manifest axon_width
    for the payload so it works even when echo is unloaded (its
    `_compiled_module` is None then)."""
    _CAPTURED.clear()
    # Sutra's runtime dim is the extended-state width (semantic +
    # synthetic), not the manifest axon_width — read it live when
    # echo is loaded. When unloaded, dim is irrelevant (echo is
    # skipped on tick; nothing runs).
    if echo.is_loaded:
        dim = echo._compiled_module._VSA.dim  # noqa: SLF001
    else:
        dim = AXON_WIDTH
    payload = torch.full((dim,), val)
    init.router._inboxes["echo"].append(  # noqa: SLF001 — test inject
        Axon(role="R_input", payload=payload, from_proc="echo")
    )
    # Two ticks so the result is independent of intra-tick service
    # order (echo emits; sink captures — possibly on the next tick).
    init.tick()
    init.tick()
    if not _CAPTURED:
        # echo didn't run (unloaded): clear the stale inbox entry so
        # it can't leak into a later reload tick.
        init.router._inboxes["echo"].clear()  # noqa: SLF001
        return None
    return _CAPTURED[-1]


def test_admit_makes_program_gpu_resident(loaded_echo):
    init, echo, base = loaded_echo
    assert init.tier("echo") is Tier.GPU
    assert echo.is_loaded is True
    vsa = echo._compiled_module._VSA  # noqa: SLF001
    assert vsa.device.type == "cuda", (
        f"Sutra runtime not on the GPU: device={vsa.device}"
    )

    # echo runs correctly while GPU-resident
    out = _run_echo_once(init, echo, 0.25)
    assert out is not None, "echo produced no output while GPU-resident"
    oc = out.detach().cpu().float()
    assert torch.allclose(oc, torch.full_like(oc, 0.25), atol=1e-3), (
        f"echo did not faithfully echo its input while GPU-resident; "
        f"mean={oc.mean().item():.4f}"
    )

    # Residency = a real, attributable GPU footprint. The admit-vs-`base`
    # delta is NOT a reliable measure of it: in the full test suite earlier
    # modules warm the shared per-process substrate, so admitting echo reuses
    # it and `loaded == base` (+0) even though echo IS resident (measured
    # +712,704 B at admit in a fresh process). The baseline-INDEPENDENT proof
    # is the footprint that *unloading* frees — robust to a warm substrate
    # (this is the same delta `test_unload_frees_gpu_and_stops_the_program`
    # checks, which passes in the full suite). Reload to restore state for the
    # rest of the module. See queue.md "gpu_tiers test-isolation".
    mem_loaded = _mem()
    init.unload("echo")
    freed = mem_loaded - _mem()
    print(f"\n[gpu-tiers] base={base} loaded={mem_loaded} "
          f"freed_on_unload={freed} B")
    assert freed > 0, (
        "echo held no freeable GPU memory while admitted — not GPU-resident"
    )
    init.load("echo")
    assert init.tier("echo") is Tier.GPU
    assert echo.is_loaded is True


def test_unload_frees_gpu_and_stops_the_program(loaded_echo):
    init, echo, _ = loaded_echo
    mem_loaded = _mem()

    init.unload("echo")
    assert init.tier("echo") is Tier.DISC
    assert echo.is_loaded is False
    mem_unloaded = _mem()
    print(f"[gpu-tiers] loaded={mem_loaded}  unloaded={mem_unloaded} "
          f"(freed {mem_loaded - mem_unloaded} B)")
    # Strict: the echo _VSA's cuda tensors are genuinely freed. Not
    # a tuned tolerance — unload must return GPU memory.
    assert mem_unloaded < mem_loaded, (
        f"unload did not free GPU memory: {mem_unloaded} >= {mem_loaded}"
    )

    # An unloaded program is not on the GPU → it does not run.
    counts = init.tick()
    assert counts["echo"] == 0, "unloaded echo still ran on tick()"
    out = _run_echo_once(init, echo, 0.5)
    assert out is None, "unloaded echo still produced output"

    # Idempotent.
    init.unload("echo")
    assert init.tier("echo") is Tier.DISC


def test_reload_restores_gpu_residency_and_output(loaded_echo):
    init, echo, _ = loaded_echo
    # (prior test left echo unloaded — fixture is module-scoped)
    assert echo.is_loaded is False
    mem_unloaded = _mem()

    init.load("echo")
    assert init.tier("echo") is Tier.GPU
    assert echo.is_loaded is True
    vsa = echo._compiled_module._VSA  # noqa: SLF001
    assert vsa.device.type == "cuda"
    mem_reloaded = _mem()
    print(f"[gpu-tiers] unloaded={mem_unloaded}  reloaded={mem_reloaded} "
          f"(+{mem_reloaded - mem_unloaded} B back on GPU)")
    assert mem_reloaded > mem_unloaded, "reload allocated no GPU memory"

    out = _run_echo_once(init, echo, 0.75)
    assert out is not None, "reloaded echo produced no output"
    oc = out.detach().cpu().float()
    assert torch.allclose(oc, torch.full_like(oc, 0.75), atol=1e-3), (
        f"reloaded echo did not faithfully echo its input; "
        f"mean={oc.mean().item():.4f}"
    )

    # Idempotent.
    init.load("echo")
    assert init.tier("echo") is Tier.GPU


def test_shared_runtime_service_refuses_individual_unload():
    """Honest boundary: a shared-MultiProcessRuntime service shares
    one _VSA, so per-service eviction is a documented follow-on, not
    the MVP. unload() must refuse clearly, not silently mis-free."""
    from kernel import make_shared_sutra_services

    runtime, (svc,) = make_shared_sutra_services([
        {"name": "shared_echo", "source_path": ECHO_SU,
         "output_role": "R_o"},
    ], runtime_dim=16)
    init = Init(compute_pool=5)
    init.admit(
        Manifest(
            name="shared_echo", axon_width=AXON_WIDTH, compute_units=1,
            read_roles=frozenset({"R_i"}),
            write_roles=frozenset({"R_o"}),
            source="services/echo.su",
        ),
        svc,
    )
    assert svc.unloadable is False
    with pytest.raises(NotImplementedError, match="shared MultiProcessRuntime"):
        init.unload("shared_echo")
