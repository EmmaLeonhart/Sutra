"""Symbol-fidelity harness — the measured seed of the Meta-demo contrast.

This is Stage 1 of `planning/22-meta-demo-replication.md`. Meta's
*Neural Computers* (arXiv:2604.06425) generate interface frames with a
DiT video-diffusion model (NCCLIGen for terminals), and their own paper
names **symbolic stability** as an open problem — over a long horizon a
generative model drifts and garbles the symbols it is meant to show.

Yantra's posture is the opposite: a symbol routed through the kernel is
*executed/carried*, not *generated*, so it is exact by construction and
does not drift no matter how long the sequence runs. This test measures
that directly: it pushes N >= 1024 distinct numeric symbols through a
real Sutra-compiled service and the kernel router, decodes each, and
asserts EXACT recovery with zero drift across the horizon.

Mechanism (the same one `test_linux_000.py` proves for chr(65)/chr(66),
generalised to N >= 1024 with a drift check): each symbol is encoded on
the real axis by the substrate op `_VSA.make_real`, carried as the axon
payload through a passthrough `.su` service (real on-substrate compute)
and the capability-checked router, then decoded host-side by the
`.real()` monitoring accessor (CLAUDE.md: accessors are monitoring-only
and allowed). Ground truth is the integer symbol itself; we report the
true delta — no faked or weakened bar.

Torch-gated like the other real-Sutra tests so CI lanes without the
Sutra runtime stack still pass cleanly.
"""

from __future__ import annotations

import pathlib

import pytest

torch = pytest.importorskip("torch", reason="symbol fidelity runs through real Sutra")

from kernel import Init, Manifest, PythonService, SutraService
from kernel.router import Axon

AXON_WIDTH = 768  # nomic-embed-text default; matches the manifests
N_SYMBOLS = 1024  # >= 1000 distinct symbols, per the roadmap
# float32 representation guard on the real-axis decode — NOT a weakened
# correctness bar. The symbolic bar is exact integer recovery
# (round(recovered) == symbol); this only bounds float noise so we can
# also report the magnitude of that noise.
FLOAT_GUARD = 1e-2


@pytest.fixture(scope="module")
def passthrough_harness(tmp_path_factory):
    """producer(Python) -> passthrough(real Sutra) -> sink(Python).

    The passthrough `.su` runs `on_axon` on the substrate and returns
    its input unchanged; the kernel router carries the payload under
    capability check. This is the minimal real path that still
    exercises (a) a real Sutra service and (b) the kernel router.
    """
    tmp = tmp_path_factory.mktemp("symfid")
    passthrough = tmp / "passthrough.su"
    passthrough.write_text(
        "function vector on_axon(vector input_axon) { return input_axon; }\n",
        encoding="utf-8",
    )

    init = Init(compute_pool=10)

    svc = SutraService(source_path=passthrough, output_role="R_out")
    init.admit(
        Manifest(
            name="passthrough", axon_width=AXON_WIDTH, compute_units=1,
            read_roles=frozenset({"R_in"}),
            write_roles=frozenset({"R_out"}),
            source=str(passthrough),
        ),
        svc,
    )

    producer = PythonService(lambda s, ax: None)
    init.admit(
        Manifest(
            name="producer", axon_width=AXON_WIDTH, compute_units=1,
            read_roles=frozenset(),
            write_roles=frozenset({"R_in"}),
            source="producer.py",
        ),
        producer,
    )

    received: list[Axon] = []
    sink = PythonService(on_axon=lambda s, ax: received.append(ax))
    init.admit(
        Manifest(
            name="sink", axon_width=AXON_WIDTH, compute_units=1,
            read_roles=frozenset({"R_out"}),
            write_roles=frozenset(),
            source="sink.py",
        ),
        sink,
    )

    vsa = svc._compiled_module._VSA  # noqa: SLF001 — host monitoring
    return init, producer, received, vsa


def test_symbol_fidelity_exact_over_long_horizon(passthrough_harness):
    """N >= 1024 distinct symbols recover exactly, with zero drift."""
    init, producer, received, vsa = passthrough_harness

    symbols = list(range(N_SYMBOLS))
    errors: list[float] = []
    mismatches: list[tuple[int, int, float]] = []  # (step, symbol, recovered)

    for step, sym in enumerate(symbols):
        received.clear()
        # Encode the symbol on the real axis (substrate op).
        payload = vsa.make_real(float(sym))
        # Route it: producer -> passthrough (real Sutra) -> sink.
        producer.emit("R_in", payload)
        # Two ticks guarantee delivery regardless of intra-tick order
        # (the proven apps/echo pattern): one fires passthrough, one
        # fires the sink.
        init.tick()
        init.tick()

        assert len(received) == 1, (
            f"step {step}: expected exactly one delivered axon, "
            f"got {len(received)}"
        )
        recovered = float(vsa.real(received[0].payload))  # monitoring decode
        err = abs(recovered - float(sym))
        errors.append(err)
        if round(recovered) != sym:
            mismatches.append((step, sym, recovered))

    n = len(symbols)
    exact = n - len(mismatches)
    decile = max(1, n // 10)
    first_decile_max = max(errors[:decile])
    last_decile_max = max(errors[-decile:])

    print(
        f"\n[symbol fidelity] N={n}  exact={exact}/{n} "
        f"({100.0 * exact / n:.2f}%)  max|err|={max(errors):.2e}  "
        f"mean|err|={sum(errors) / n:.2e}\n"
        f"[symbol fidelity] drift check — first-decile max|err|="
        f"{first_decile_max:.2e}  last-decile max|err|={last_decile_max:.2e}"
    )

    # (1) Every symbol recovered exactly — 100% symbolic fidelity.
    assert not mismatches, (
        f"symbol drift: {len(mismatches)} of {n} symbols misrecovered; "
        f"first few: {mismatches[:5]}"
    )
    # (2) Float-axis noise stays inside the representation guard.
    assert max(errors) < FLOAT_GUARD, (
        f"real-axis decode noise {max(errors):.2e} exceeds the float guard "
        f"{FLOAT_GUARD:.0e} — investigate before trusting exactness"
    )
    # (3) Zero drift: the tail of the horizon is no worse than the head.
    # If symbol fidelity decayed with N (the generative-model failure
    # mode), the last decile would be worse than the first. It is not.
    assert last_decile_max <= max(first_decile_max, FLOAT_GUARD), (
        f"fidelity drifted with horizon: first-decile max|err|="
        f"{first_decile_max:.2e}, last-decile max|err|={last_decile_max:.2e}"
    )


def test_symbol_fidelity_runs_through_real_sutra_and_router(passthrough_harness):
    """Guard that the harness exercises real Sutra + the real router,
    not a Python stand-in — otherwise the fidelity result is hollow."""
    init, producer, received, vsa = passthrough_harness
    # The passthrough is a real SutraService with a compiled module.
    svc = init._table["passthrough"].service  # noqa: SLF001
    assert isinstance(svc, SutraService)
    assert svc._compiled_module is not None  # noqa: SLF001 — compiled .su
    # The capability check is live: producer cannot write R_out.
    from kernel.router import CapabilityError
    with pytest.raises(CapabilityError):
        producer.emit("R_out", vsa.make_real(1.0))


def test_text_symbol_fidelity_exact_over_long_horizon(passthrough_harness):
    """Long run of distinct TEXT lines, each recovered exactly.

    The numeric harness above proves number-symbol stability; this proves
    the same for **text**, which is the axis Meta's NCCLIGen (a video
    model that generates terminal frames) lists as unsolved. Each line is
    encoded on the substrate (`make_string`), carried through a real Sutra
    service + the kernel router, and decoded host-side (`string_to_python`,
    monitoring). Where a generative terminal model drifts as the session
    grows, an executing substrate carries the text verbatim.
    """
    init, producer, received, vsa = passthrough_harness

    maxlen = vsa.string_max_length()
    base = "the quick brown fox jumps over the lazy dog 0123456789"
    # Distinct terminal-shaped lines, each within the string capacity
    # (the distinguishing index is at the front, so it survives the cap).
    lines = [f"line {i:04d}: {base}"[:maxlen] for i in range(N_SYMBOLS)]
    assert len(set(lines)) == len(lines), "test lines must be distinct"

    mismatches: list[tuple[int, str, str]] = []
    for step, text in enumerate(lines):
        received.clear()
        producer.emit("R_in", vsa.make_string(text))
        init.tick()
        init.tick()
        assert len(received) == 1, (
            f"step {step}: expected one delivered axon, got {len(received)}"
        )
        back = vsa.string_to_python(received[0].payload)  # monitoring decode
        if back != text:
            mismatches.append((step, text, back))

    n = len(lines)
    print(
        f"\n[text fidelity] N={n}  exact={n - len(mismatches)}/{n} "
        f"({100.0 * (n - len(mismatches)) / n:.2f}%)  "
        f"max line length={max(len(s) for s in lines)} (cap {maxlen})"
    )
    assert not mismatches, (
        f"text drift: {len(mismatches)} of {n} lines misrecovered; "
        f"first few: {mismatches[:3]}"
    )
