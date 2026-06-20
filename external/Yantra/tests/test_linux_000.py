"""Linux 0.00 on Yantra — the Connectome-Manager-native replica.

Linux 0.00 (Torvalds, 1991) is the smallest possible OS that
demonstrates kernel-mediated multitasking: two hardcoded tasks, A
writing 'A' forever and B writing 'B' forever, alternated by the
timer interrupt, output poked into VGA memory by a write_char
syscall. See planning/21-linux-0.00.md for the full faithful
mapping and the honest-scope limits (no bare-metal boot, no TSS —
those are a separate, gated bootloader-track item, by Yantra
architecture on purpose).

This test exercises the Yantra-native realization on the real v0.0
Connectome Manager with **real Sutra-compiled services**:

  - `task_a.su` / `task_b.su` emit the ASCII codepoints of 'A'/'B'
    (65 / 66) as substrate number-vectors via `real_number`
    (a substrate op — `_VSA.make_real`). NOT a faked A/B: the
    emitted vector genuinely carries chr(65)/chr(66) on the real
    axis. Decoded host-side via the `.real()` monitoring accessor
    (CLAUDE.md: accessors are monitoring-only and allowed).
  - `console.su` is the VGA-memory analogue (the fan-in receiver).
  - `Init.tick()` driving both tasks is the timer-IRQ analogue;
    the router carrying their output is the kernel mediation.
    Yantra's kernel does NOT context-switch (by design — see
    kernel/init.py); both tasks live in the connectome at once and
    their output interleaves under kernel mediation. That is the
    faithful translation of Linux 0.00's *purpose*, not its TSS.

Torch-gated like test_kernel_sutra.py so CI lanes without the
Sutra runtime stack still pass cleanly.
"""

from __future__ import annotations

import pathlib

import pytest

torch = pytest.importorskip("torch", reason="Sutra services need torch")

from kernel import Init, Manifest, make_shared_sutra_services
from kernel.router import Axon

KERNEL_DIR = pathlib.Path(__file__).resolve().parent.parent / "kernel"
SERVICES = KERNEL_DIR / "services"
AXON_WIDTH = 768  # nomic-embed-text default; matches the manifests

# 'A' == chr(65), 'B' == chr(66) — the literal Linux 0.00 output.
CODE_A = 65
CODE_B = 66
N_TICKS = 8


@pytest.fixture(scope="module")
def linux_000():
    """Three real shared-runtime Sutra services: task_a, task_b, console."""
    runtime, (a_svc, b_svc, con_svc) = make_shared_sutra_services([
        {"name": "task_a", "source_path": SERVICES / "task_a.su",
         "output_role": "R_console"},
        {"name": "task_b", "source_path": SERVICES / "task_b.su",
         "output_role": "R_console"},
        {"name": "console", "source_path": SERVICES / "console.su",
         "output_role": "R_console_done"},
    ], runtime_dim=16)
    init = Init(compute_pool=10)
    init.admit(
        Manifest(
            name="task_a", axon_width=AXON_WIDTH, compute_units=1,
            read_roles=frozenset({"R_tick"}),
            write_roles=frozenset({"R_console"}),
            source="services/task_a.su",
        ),
        a_svc,
    )
    init.admit(
        Manifest(
            name="task_b", axon_width=AXON_WIDTH, compute_units=1,
            read_roles=frozenset({"R_tick"}),
            write_roles=frozenset({"R_console"}),
            source="services/task_b.su",
        ),
        b_svc,
    )
    init.admit(
        Manifest(
            name="console", axon_width=AXON_WIDTH, compute_units=1,
            read_roles=frozenset({"R_console"}),
            write_roles=frozenset({"R_console_done"}),
            source="services/console.su",
        ),
        con_svc,
    )
    return init, runtime, a_svc, b_svc


def _run_ticks(init, runtime, a_svc, b_svc):
    """Drive N timer ticks; return (stream, first_a_val, first_b_val).

    Each tick: inject the trigger axon (timer-IRQ analogue) into
    task_a and task_b inboxes, run them (deterministic A-then-B
    order), then drain the console (read VGA memory) decoding each
    payload's real axis to a character.
    """
    vsa = runtime.vsa()
    stream: list[str] = []
    first_a_val: float | None = None
    first_b_val: float | None = None
    for _ in range(N_TICKS):
        # The timer interrupt: a tick stimulus into both tasks.
        # Direct inbox injection is the established kernel-test
        # pattern for external stimulus (see test_kernel_sutra.py).
        for name in ("task_a", "task_b"):
            init.router._inboxes[name].append(  # noqa: SLF001 — test
                Axon(role="R_tick",
                     payload=torch.zeros(vsa.dim),
                     from_proc=name)
            )
        a_svc.tick()  # on_axon → real_number(65) → emit R_console
        b_svc.tick()  # on_axon → real_number(66) → emit R_console
        while True:
            ax = init.router.receive("console")
            if ax is None:
                break
            val = float(vsa._re(ax.payload))  # monitoring accessor (0-d tensor -> float)
            if ax.from_proc == "task_a" and first_a_val is None:
                first_a_val = val
            if ax.from_proc == "task_b" and first_b_val is None:
                first_b_val = val
            stream.append(chr(int(round(val))))
    return "".join(stream), first_a_val, first_b_val


def test_linux_000_kernel_mediated_AB_stream(linux_000):
    """Both hardcoded tasks run every tick under kernel mediation,
    producing the interleaved A/B stream — Linux 0.00's behaviour."""
    init, runtime, a_svc, b_svc = linux_000
    stream, first_a, first_b = _run_ticks(init, runtime, a_svc, b_svc)

    print(
        f"\n[linux 0.00] stream={stream!r}  "
        f"measured real(task_a)={first_a}  real(task_b)={first_b}"
    )

    # Only the two characters appear — no garbage from the substrate.
    assert set(stream) == {"A", "B"}, f"unexpected chars in {stream!r}"
    # Neither task is starved: the kernel ran BOTH every tick.
    assert stream.count("A") == N_TICKS
    assert stream.count("B") == N_TICKS
    # Kernel-mediated interleaving: one A then one B per tick (the
    # router carried both; deterministic A-then-B emit order). This
    # is the faithful "AAAA…BBBB…" analogue at per-tick granularity.
    assert stream == "AB" * N_TICKS, (
        f"expected kernel-interleaved 'AB'*{N_TICKS}, got {stream!r}"
    )


def test_linux_000_emitted_values_are_literal_ascii(linux_000):
    """Measured-honestly: the emitted vectors decode to the EXACT
    ASCII codepoints of 'A' and 'B' — not a faked or approximate
    constant. real_number puts the value on the real axis exactly;
    the router round-trips it unchanged (no binding)."""
    init, runtime, a_svc, b_svc = linux_000
    _, first_a, first_b = _run_ticks(init, runtime, a_svc, b_svc)

    assert first_a is not None and first_b is not None
    # Report the measurement; the tolerance only guards float32
    # representation, it is not a weakened correctness bar — the
    # value is expected exact.
    assert abs(first_a - CODE_A) < 1e-5, (
        f"task_a real axis = {first_a}, expected {CODE_A} (chr={chr(CODE_A)!r})"
    )
    assert abs(first_b - CODE_B) < 1e-5, (
        f"task_b real axis = {first_b}, expected {CODE_B} (chr={chr(CODE_B)!r})"
    )
    assert chr(int(round(first_a))) == "A"
    assert chr(int(round(first_b))) == "B"


def test_linux_000_uses_real_router_capability_check(linux_000):
    """Sanity that this is the real Connectome Manager, not a stub:
    a task cannot write a role it does not hold."""
    from kernel.router import CapabilityError

    init, runtime, a_svc, b_svc = linux_000
    with pytest.raises(CapabilityError):
        a_svc.emit("R_console_done", torch.zeros(runtime.vsa().dim))
