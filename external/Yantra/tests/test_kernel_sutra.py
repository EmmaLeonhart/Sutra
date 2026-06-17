"""End-to-end test: real Sutra-compiled .su services through the router.

This is the test that proves Sutra is actually doing the computation
— not a Python stub re-using the same data structures. Two .su files
in `kernel/services/` are compiled by the real Sutra v0.3.1 compiler
(via the submodule under `external/Sutra/sdk/sutra-compiler/`) and
their `on_axon(vector) -> vector` exports are wired to the kernel's
axon router. A real torch tensor is sent in; the router delivers it
through the chain; the receiver gets a real torch tensor back.

Skipped when torch is not installed, so CI lanes that don't carry
the full Sutra runtime stack still pass cleanly. Local dev with
torch installed (which Sutra requires anyway) gets the real test.
"""

from __future__ import annotations

import pathlib

import pytest

torch = pytest.importorskip("torch", reason="Sutra services need torch")

from kernel import Init, Manifest, PythonService, SutraService


KERNEL_DIR = pathlib.Path(__file__).resolve().parent.parent / "kernel"
SERVICES = KERNEL_DIR / "services"

# These tests compile real .su programs through the Sutra v0.3.1
# pipeline. First compile in a fresh interpreter downloads the
# embedding model (`nomic-embed-text` by default), which is slow
# (~tens of seconds to minutes on cold cache). All tests in this
# module share that cost via session-scoped fixtures.

AXON_WIDTH = 768  # matches nomic-embed-text default


@pytest.fixture(scope="module")
def echo_sink_init() -> Init:
    """Init with two real Sutra services (echo, sink) + a producer."""
    init = Init(compute_pool=10)

    echo = SutraService(
        source_path=SERVICES / "echo.su",
        output_role="R_output",
    )
    init.admit(
        Manifest(
            name="echo", axon_width=AXON_WIDTH, compute_units=1,
            read_roles=frozenset({"R_input"}),
            write_roles=frozenset({"R_output"}),
            source="services/echo.su",
        ),
        echo,
    )

    sink = SutraService(
        source_path=SERVICES / "sink.su",
        output_role="R_stat",
    )
    init.admit(
        Manifest(
            name="sink", axon_width=AXON_WIDTH, compute_units=1,
            read_roles=frozenset({"R_output"}),
            write_roles=frozenset({"R_stat"}),
            source="services/sink.su",
        ),
        sink,
    )

    producer = PythonService(lambda s, ax: None)
    init.admit(
        Manifest(
            name="producer", axon_width=AXON_WIDTH, compute_units=1,
            read_roles=frozenset(),
            write_roles=frozenset({"R_input"}),
            source="producer.py",
        ),
        producer,
    )
    return init


def _producer(init: Init) -> PythonService:
    """Look up the producer by name."""
    # The Init API exposes admitted names but not the bound services
    # directly; for the test we know the producer is a PythonService
    # we admitted by hand. Get it via the table.
    return init._table["producer"].service  # noqa: SLF001 — test


def test_real_sutra_services_compile_and_admit(echo_sink_init: Init) -> None:
    """Both Sutra services compiled cleanly and joined the connectome."""
    assert sorted(echo_sink_init.admitted()) == ["echo", "producer", "sink"]
    # Compute pool decremented by 3 * 1 = 3.
    assert echo_sink_init.compute_pool_free == 10 - 3


def test_real_sutra_round_trip_with_torch_tensor(echo_sink_init: Init) -> None:
    """A real torch tensor routes producer → echo (real Sutra) → sink (real Sutra)."""
    payload = torch.randn(AXON_WIDTH)
    expected_norm = payload.norm().item()

    producer = _producer(echo_sink_init)
    delivered = producer.emit("R_input", payload)
    assert delivered == 1, "producer's R_input should route to echo only"
    assert echo_sink_init.router.inbox_depth("echo") == 1
    assert echo_sink_init.router.inbox_depth("sink") == 0

    counts = echo_sink_init.tick()
    # Producer has nothing inbound; echo drains 1; sink drains the 1
    # that echo emitted.
    assert counts["producer"] == 0
    assert counts["echo"] == 1
    assert counts["sink"] == 1

    # Sink's R_stat emit goes to a black hole (no reader admitted)
    # — the dropped count goes up by exactly 1.
    assert echo_sink_init.router.dropped_count() == 1


def test_real_sutra_output_is_torch_tensor(echo_sink_init: Init) -> None:
    """The vector that lands in sink's inbox came back from real Sutra compute."""
    # We need to inspect what arrives at sink BEFORE sink's tick drains
    # it, so do this in two halves.
    payload = torch.ones(AXON_WIDTH) * 0.5
    producer = _producer(echo_sink_init)
    producer.emit("R_input", payload)

    # Tick echo manually so we can peek at sink's inbox before sink ticks.
    echo_svc = echo_sink_init._table["echo"].service  # noqa: SLF001
    echo_svc.tick()

    inbound_to_sink = echo_sink_init.router.receive("sink")
    assert inbound_to_sink is not None
    assert inbound_to_sink.from_proc == "echo"
    assert inbound_to_sink.role == "R_output"
    assert torch.is_tensor(inbound_to_sink.payload), (
        "sink received a real torch tensor; the .su compute path produced it"
    )
    assert inbound_to_sink.payload.shape == (AXON_WIDTH,)


def test_real_sutra_capability_check_still_fires(echo_sink_init: Init) -> None:
    """The router still refuses sends from Sutra services on roles they don't hold."""
    from kernel.router import CapabilityError
    echo_svc = echo_sink_init._table["echo"].service  # noqa: SLF001
    with pytest.raises(CapabilityError, match="cannot write role 'R_stat'"):
        echo_svc.emit("R_stat", torch.zeros(AXON_WIDTH))


def test_sutra_service_unbound_tick_raises() -> None:
    """A SutraService not yet admitted to an Init can't tick — clear error."""
    svc = SutraService(
        source_path=SERVICES / "echo.su",
        output_role="R_output",
    )
    with pytest.raises(RuntimeError, match="not bound"):
        svc.tick()


def test_sutra_service_missing_entry_point_raises(tmp_path: pathlib.Path) -> None:
    """A .su without the expected entry-point function fails at admit time."""
    bad = tmp_path / "no_entry.su"
    bad.write_text(
        "function string main() { return \"nope\"; }\n",
        encoding="utf-8",
    )

    init = Init(compute_pool=5)
    svc = SutraService(source_path=bad, output_role="R_x")
    with pytest.raises(AttributeError, match="no `on_axon` symbol"):
        init.admit(
            Manifest(
                name="bad", axon_width=AXON_WIDTH, compute_units=1,
                read_roles=frozenset({"R_in"}),
                write_roles=frozenset({"R_x"}),
                source=str(bad),
            ),
            svc,
        )


# ---- lazy axon evaluation: compiler-emitted constants drive routing -


def test_sutra_service_exposes_axon_keys_from_compiled_module(tmp_path: pathlib.Path) -> None:
    """The Sutra v0.3.3+ AXON_KEYS_BOUND/READ constants surface as service properties."""
    # A .su that both binds and reads — exercise both halves of the static analysis.
    src = tmp_path / "mixed.su"
    src.write_text(
        "function vector on_axon(vector input_axon) {\n"
        "    Axon a;\n"
        "    a.add(\"out_key\", input_axon);\n"
        "    return axon_item(a, \"out_key\");\n"
        "}\n",
        encoding="utf-8",
    )

    init = Init(compute_pool=5)
    svc = SutraService(source_path=src, output_role="R_out")
    init.admit(
        Manifest(
            name="mixed", axon_width=AXON_WIDTH, compute_units=1,
            read_roles=frozenset({"R_in"}),
            write_roles=frozenset({"R_out"}),
            source=str(src),
        ),
        svc,
    )
    assert svc.axon_keys_bound == frozenset({"out_key"})
    assert svc.axon_keys_read == frozenset({"out_key"})


def test_sutra_service_auto_populates_manifest_axon_keys(tmp_path: pathlib.Path) -> None:
    """When manifest doesn't declare axon_keys, SutraService fills it from the .su."""
    consumer = tmp_path / "consumer.su"
    consumer.write_text(
        "function vector on_axon(vector input_axon) {\n"
        "    return axon_item(input_axon, \"animal_2\");\n"
        "}\n",
        encoding="utf-8",
    )

    init = Init(compute_pool=5)
    svc = SutraService(source_path=consumer, output_role="R_out")
    init.admit(
        Manifest(
            name="consumer", axon_width=AXON_WIDTH, compute_units=1,
            read_roles=frozenset({"R_in"}),
            write_roles=frozenset({"R_out"}),
            source=str(consumer),
            # axon_keys NOT declared — service should auto-populate.
        ),
        svc,
    )
    # The router's view of the receiver's axon_keys should now reflect
    # what the .su source statically reads.
    receiver_manifest = init._table["consumer"].manifest  # noqa: SLF001
    assert receiver_manifest.axon_keys == frozenset({"animal_2"})


def test_sutra_service_respects_explicit_manifest_axon_keys(tmp_path: pathlib.Path) -> None:
    """If the manifest DID declare axon_keys, don't overwrite — explicit wins."""
    src = tmp_path / "consumer.su"
    src.write_text(
        "function vector on_axon(vector input_axon) {\n"
        "    return axon_item(input_axon, \"static_key\");\n"
        "}\n",
        encoding="utf-8",
    )
    init = Init(compute_pool=5)
    svc = SutraService(source_path=src, output_role="R_out")
    init.admit(
        Manifest(
            name="explicit", axon_width=AXON_WIDTH, compute_units=1,
            read_roles=frozenset({"R_in"}),
            write_roles=frozenset({"R_out"}),
            source=str(src),
            axon_keys=frozenset({"override_key"}),  # explicit wins
        ),
        svc,
    )
    receiver_manifest = init._table["explicit"].manifest  # noqa: SLF001
    assert receiver_manifest.axon_keys == frozenset({"override_key"})


def test_sutra_service_emit_tags_axon_with_bound_keys(tmp_path: pathlib.Path) -> None:
    """SutraService.tick() forwards AXON_KEYS_BOUND to router.send()'s keys field.

    With Sutra v0.3.4's device-coherence fix in axon_add/bind, the
    .su body can now construct a real Axon from a CPU input tensor
    without crashing. That's the natural shape of a producer
    service: take an input, bind some keys onto it, emit. This
    test exercises that natural shape end-to-end.
    """
    producer = tmp_path / "producer.su"
    producer.write_text(
        "function vector on_axon(vector input_axon) {\n"
        "    Axon a;\n"
        "    a.add(\"key_one\", input_axon);\n"
        "    a.add(\"key_two\", input_axon);\n"
        "    return a;\n"
        "}\n",
        encoding="utf-8",
    )
    init = Init(compute_pool=5)
    prod_svc = SutraService(source_path=producer, output_role="R_out")
    init.admit(
        Manifest(
            name="prod", axon_width=AXON_WIDTH, compute_units=1,
            read_roles=frozenset({"R_in"}),
            write_roles=frozenset({"R_out"}),
            source=str(producer),
        ),
        prod_svc,
    )
    # Sanity: static analysis picked up both bind keys.
    assert prod_svc.axon_keys_bound == frozenset({"key_one", "key_two"})

    # Receiver that wants only "key_one" — producer's emission should
    # still arrive (intersection non-empty), and its keys field
    # should reflect what the producer's source statically binds.
    receiver_consumer = tmp_path / "rcv.su"
    receiver_consumer.write_text(
        "function vector on_axon(vector input_axon) {\n"
        "    return input_axon;\n"
        "}\n",
        encoding="utf-8",
    )
    receiver = SutraService(source_path=receiver_consumer, output_role="R_done")
    init.admit(
        Manifest(
            name="recv", axon_width=AXON_WIDTH, compute_units=1,
            read_roles=frozenset({"R_out"}),
            write_roles=frozenset({"R_done"}),
            source=str(receiver_consumer),
            axon_keys=frozenset({"key_one"}),
        ),
        receiver,
    )

    # Inject an axon on the producer's R_in. CPU tensor — Sutra
    # v0.3.4's device-coherence fix in axon_add/bind handles the
    # CPU→runtime-device coercion now, so we don't need to
    # pre-pin the device on the test side.
    vsa_dim = prod_svc._compiled_module._VSA.dim  # noqa: SLF001
    init.router._inboxes["prod"].append(  # noqa: SLF001 — test
        Axon(
            role="R_in",
            payload=torch.zeros(vsa_dim),  # CPU — Sutra coerces
            from_proc="prod",
        ),
    )
    prod_svc.tick()  # runs on_axon (real Axon construction!) → emits
    inbox = init.router.receive("recv")
    assert inbox is not None
    # With Sutra v0.3.5 + the kernel router's per-receiver
    # projection wired up, the receiver gets the SLIMMED axon —
    # only the intersection of the producer's bound keys
    # ({key_one, key_two}) and the receiver's interest set
    # ({key_one}). The delivered axon's keys field reflects the
    # intersection.
    assert inbox.keys == frozenset({"key_one"})
    # No lazy-skip (intersection is non-empty), but the projection
    # path DID fire because the receiver wanted a strict subset.
    assert init.router.lazy_skipped_count() == 0
    assert init.router.lazy_projected_count() == 1


# Need Axon at module scope for the previous test.
from kernel.router import Axon  # noqa: E402


@pytest.mark.xfail(
    strict=True,
    reason=(
        "axon_project(bundle,[k]) = bind(k, unbind(k, bundle)); for "
        "orthogonal rotation binding on semantic-block (embedding) "
        "fillers Q_k·Q_kᵀ=I, so the 'projected' payload reconstructs "
        "the FULL bundle — every key still decodes. Measured "
        "2026-05-15: kept 'animal'→dog +0.5999 vs projected-OUT "
        "'color'→red +0.5726 (~equal). Per-receiver projection thus "
        "gives NEITHER bandwidth reduction NOR capability isolation "
        "for embedding fillers (a receiver asking for only 'animal' "
        "still recovers 'color'/'user' — bears on paper §3.3.1). "
        "Real slimming needs producer-side pruning (skip axon_add for "
        "unwanted keys, axons.md §lazy-materialization), NOT post-hoc "
        "axon_project on a finished bundle. Sutra-side design "
        "decision; precise blocker in queue.md + "
        "planning/20-lazy-axon-evaluation.md § Status. strict=True so "
        "this flips loud the moment the projection is actually fixed."
    ),
)
def test_projected_payload_still_decodes_semantically(tmp_path: pathlib.Path) -> None:
    """End-to-end SEMANTIC proof of per-receiver projection.

    The existing emit-tags test proves the plumbing (real
    `_VSA.axon_project` fires, `keys` field == intersection,
    `lazy_projected_count` increments). It does NOT prove the
    projected payload is still semantically correct — it bundles a
    zeros filler and never decodes. That is exactly the bug class
    that bit multi_program_axon (the `keys` field looked right
    while the recovered content was noise — fixed 2026-05-15 in
    Sutra `eb0ce93e`).

    This test closes that gap: a producer bundles THREE keys with
    DISTINCT embedded fillers; a receiver declares interest in ONE;
    after the router projects via the real `_VSA.axon_project`, the
    receiver must (c) still recover its requested key with high
    cosine to the true filler, and (d) NOT recover a projected-out
    key. No tuning — the bars encode the semantic requirement; if
    they fail it is a real defect to report, not a number to fudge.
    """
    producer = tmp_path / "producer.su"
    producer.write_text(
        "// Builds a 3-key axon with distinct embedded fillers, like\n"
        "// examples/multi_program_axon/producer.su but as a service.\n"
        "vector v_dog   = basis_vector(\"dog\");\n"
        "vector v_red   = basis_vector(\"red\");\n"
        "vector v_alice = basis_vector(\"alice\");\n"
        "\n"
        "function vector on_axon(vector input_axon) {\n"
        "    Axon a;\n"
        "    a.add(\"animal\", v_dog);\n"
        "    a.add(\"color\",  v_red);\n"
        "    a.add(\"user\",   v_alice);\n"
        "    return a;\n"
        "}\n",
        encoding="utf-8",
    )
    init = Init(compute_pool=5)
    prod_svc = SutraService(source_path=producer, output_role="R_out")
    init.admit(
        Manifest(
            name="prod", axon_width=AXON_WIDTH, compute_units=1,
            read_roles=frozenset({"R_in"}),
            write_roles=frozenset({"R_out"}),
            source=str(producer),
        ),
        prod_svc,
    )
    assert prod_svc.axon_keys_bound == frozenset({"animal", "color", "user"})

    consumer = tmp_path / "rcv.su"
    consumer.write_text(
        "function vector on_axon(vector input_axon) { return input_axon; }\n",
        encoding="utf-8",
    )
    receiver = SutraService(source_path=consumer, output_role="R_done")
    init.admit(
        Manifest(
            name="recv", axon_width=AXON_WIDTH, compute_units=1,
            read_roles=frozenset({"R_out"}),
            write_roles=frozenset({"R_done"}),
            source=str(consumer),
            axon_keys=frozenset({"animal"}),  # STRICT subset of 3
        ),
        receiver,
    )

    vsa = prod_svc._compiled_module._VSA  # noqa: SLF001 — host monitoring
    init.router._inboxes["prod"].append(  # noqa: SLF001 — test injection
        Axon(role="R_in", payload=torch.zeros(vsa.dim), from_proc="prod")
    )
    prod_svc.tick()  # on_axon builds the real 3-key axon → router projects

    inbox = init.router.receive("recv")
    assert inbox is not None
    # Plumbing (same as the sibling test): real projector fired, the
    # delivered keys field is the intersection.
    assert init.router.lazy_projected_count() == 1
    assert init.router.lazy_skipped_count() == 0
    assert inbox.keys == frozenset({"animal"})

    # SEMANTIC: decode the PROJECTED payload (host-side monitoring,
    # allowed per CLAUDE.md). The requested key must still recover
    # its filler; a projected-out key must not.
    def _cos(a, b) -> float:
        a = a.flatten().float()
        b = b.flatten().float()
        return float(
            torch.dot(a, b)
            / (torch.linalg.norm(a) * torch.linalg.norm(b) + 1e-9)
        )

    rec_animal = vsa.axon_item(inbox.payload, "animal")
    rec_color = vsa.axon_item(inbox.payload, "color")  # projected OUT
    cos_animal = _cos(rec_animal, vsa.embed("dog"))
    cos_color = _cos(rec_color, vsa.embed("red"))
    print(
        f"\n[projection semantics] cos(kept 'animal'→dog)={cos_animal:+.4f}  "
        f"cos(dropped 'color'→red)={cos_color:+.4f}"
    )

    # (c) requested key still decodes from the slimmed payload. A
    # single-key projected axon decodes at least as strongly as the
    # 5-key multi_program_axon case (+0.40); 0.30 is a conservative
    # floor, not a tuned target.
    assert cos_animal > 0.30, (
        f"projected payload lost the requested key: "
        f"cos(decode('animal'), embed('dog'))={cos_animal:+.4f}"
    )
    # (d) a projected-OUT key does not meaningfully decode, and
    # decodes strictly worse than the kept key.
    assert cos_color < 0.15, (
        f"projected-out key still decodes — projection didn't drop it: "
        f"cos(decode('color'), embed('red'))={cos_color:+.4f}"
    )
    assert cos_animal > cos_color + 0.20, (
        f"insufficient separation: kept={cos_animal:+.4f} "
        f"dropped={cos_color:+.4f}"
    )


# ---- Sutra v0.4.0 shared MultiProcessRuntime --------------------


def test_make_shared_sutra_services_share_one_vsa(tmp_path: pathlib.Path) -> None:
    """Two services constructed via the factory share one _VSA instance."""
    from kernel import make_shared_sutra_services

    src_a = tmp_path / "a.su"
    src_a.write_text(
        "function vector on_axon(vector input_axon) { return input_axon; }\n",
        encoding="utf-8",
    )
    src_b = tmp_path / "b.su"
    src_b.write_text(
        "function vector on_axon(vector input_axon) { return input_axon; }\n",
        encoding="utf-8",
    )

    runtime, services = make_shared_sutra_services([
        {"name": "a", "source_path": src_a, "output_role": "R_a"},
        {"name": "b", "source_path": src_b, "output_role": "R_b"},
    ], runtime_dim=16)

    init = Init(compute_pool=10)
    init.admit(
        Manifest(
            name="a", axon_width=AXON_WIDTH, compute_units=1,
            read_roles=frozenset({"R_in_a"}),
            write_roles=frozenset({"R_a"}),
            source=str(src_a),
        ),
        services[0],
    )
    init.admit(
        Manifest(
            name="b", axon_width=AXON_WIDTH, compute_units=1,
            read_roles=frozenset({"R_in_b"}),
            write_roles=frozenset({"R_b"}),
            source=str(src_b),
        ),
        services[1],
    )
    # Both services' compiled-module _VSA references point at the
    # same Python object — the runtime's shared _VSA.
    vsa_a = services[0]._compiled_module._VSA  # noqa: SLF001
    vsa_b = services[1]._compiled_module._VSA  # noqa: SLF001
    assert vsa_a is vsa_b
    assert vsa_a is runtime.vsa()


def test_shared_runtime_axon_passing_through_router(tmp_path: pathlib.Path) -> None:
    """Two shared-runtime services exchange axons through the kernel router."""
    from kernel import make_shared_sutra_services

    producer_src = tmp_path / "p.su"
    producer_src.write_text(
        "function vector on_axon(vector input_axon) {\n"
        "    Axon a;\n"
        "    a.add(\"shared\", input_axon);\n"
        "    return a;\n"
        "}\n",
        encoding="utf-8",
    )
    consumer_src = tmp_path / "c.su"
    consumer_src.write_text(
        "function vector on_axon(vector input_axon) {\n"
        "    return axon_item(input_axon, \"shared\");\n"
        "}\n",
        encoding="utf-8",
    )

    runtime, (prod, cons) = make_shared_sutra_services([
        {"name": "prod", "source_path": producer_src, "output_role": "R_out"},
        {"name": "cons", "source_path": consumer_src, "output_role": "R_done"},
    ], runtime_dim=16)

    init = Init(compute_pool=10)
    init.admit(
        Manifest(
            name="prod", axon_width=AXON_WIDTH, compute_units=1,
            read_roles=frozenset({"R_in"}),
            write_roles=frozenset({"R_out"}),
            source=str(producer_src),
        ),
        prod,
    )
    init.admit(
        Manifest(
            name="cons", axon_width=AXON_WIDTH, compute_units=1,
            read_roles=frozenset({"R_out"}),
            write_roles=frozenset({"R_done"}),
            source=str(consumer_src),
        ),
        cons,
    )
    # Static analysis surfaced through the shared runtime.
    assert prod.axon_keys_bound == frozenset({"shared"})
    assert cons.axon_keys_read == frozenset({"shared"})

    # Inject + tick. CPU input — Sutra v0.3.4 device coercion handles it.
    vsa_dim = runtime.vsa().dim
    init.router._inboxes["prod"].append(  # noqa: SLF001
        Axon(role="R_in", payload=torch.zeros(vsa_dim), from_proc="prod"),
    )
    counts = init.tick()
    assert counts["prod"] == 1
    assert counts["cons"] == 1  # received from prod's emit, processed


def test_sutraservice_runtime_requires_program_name() -> None:
    """SutraService(runtime=...) without runtime_program_name is a clear error."""
    with pytest.raises(ValueError, match="runtime_program_name"):
        SutraService(
            source_path="dummy.su",
            output_role="R_x",
            runtime=object(),  # any non-None value triggers the check
        )


def test_sutraservice_runtime_with_unknown_program_raises(tmp_path: pathlib.Path) -> None:
    """SutraService(runtime=..., runtime_program_name=NAME) where NAME isn't in the runtime."""
    from kernel import make_shared_sutra_services

    src = tmp_path / "x.su"
    src.write_text(
        "function vector on_axon(vector input_axon) { return input_axon; }\n",
        encoding="utf-8",
    )
    runtime, _ = make_shared_sutra_services([
        {"name": "real", "source_path": src, "output_role": "R_real"},
    ], runtime_dim=16)
    # Wire a SutraService claiming to be admitted under a name the
    # runtime doesn't know — bind() should raise.
    bad = SutraService(
        source_path=src, output_role="R_x",
        runtime=runtime, runtime_program_name="ghost",
    )
    init = Init(compute_pool=5)
    with pytest.raises(KeyError, match="not admitted to the runtime"):
        init.admit(
            Manifest(
                name="bad", axon_width=AXON_WIDTH, compute_units=1,
                read_roles=frozenset(),
                write_roles=frozenset({"R_x"}),
                source=str(src),
            ),
            bad,
        )
