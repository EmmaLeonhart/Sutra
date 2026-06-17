"""End-to-end tests for the v0.0 kernel runtime.

Covers the architecture's load-bearing claims at the v0.0 scope:

  - Manifest parsing rejects bad input cleanly.
  - Init admits processes against a fixed pool budget; refuses
    admission when the pool is exhausted; releases budget on
    deregister.
  - Router enforces capability check on send (sender must hold the
    write role) and on receive (receiver must hold the read role).
  - Multi-process axon routing: echo + sink can be admitted, an axon
    sent into echo's inbox arrives at sink's inbox after one tick.
  - Black-hole sends (no receiver for a role) are dropped, not
    raised — startup-order tolerance.

These are the pure-Python router/kernel unit tests. The real
Sutra-compiled `.su` service path is NOT stubbed — it works via
`SutraService(source_path=…)` and is exercised separately in
`tests/test_kernel_sutra.py` (admits real echo/sink `.su`
services, routes axons end-to-end). Real per-process GPU arena
allocation is still bookkeeping-only (that part remains v0.1
work).
"""

from __future__ import annotations

import pathlib

import pytest

from kernel import (
    AdmissionError,
    AxonRouter,
    CapabilityError,
    Init,
    Manifest,
    ManifestError,
    NotAdmittedError,
    PoolExhaustedError,
    PythonService,
    load_manifest,
)
from kernel.router import Axon


def _echo_python(output_role: str = "R_output") -> PythonService:
    """Python stand-in for an echo service (real version uses SutraService)."""
    def on_axon(svc: PythonService, ax: Axon) -> None:
        svc.emit(output_role, ax.payload)
    return PythonService(on_axon=on_axon)


class _CountingSink(PythonService):
    """Python stand-in for a sink that counts axons and emits stats."""

    def __init__(self, *, stat_role: str = "R_stat", report_every: int = 1) -> None:
        self._stat_role = stat_role
        self._report_every = report_every
        self.count = 0
        self._since = 0

        def on_axon(svc: PythonService, ax: Axon) -> None:
            self.count += 1
            self._since += 1
            if self._since >= self._report_every:
                svc.emit(self._stat_role, {"count": self.count})
                self._since = 0

        super().__init__(on_axon=on_axon)


KERNEL_DIR = pathlib.Path(__file__).resolve().parent.parent / "kernel"
MANIFESTS = KERNEL_DIR / "manifests"


# ---- manifest parsing -------------------------------------------------


def _make_manifest(name: str = "p", **overrides) -> Manifest:
    fields = {
        "name": name,
        "axon_width": 768,
        "compute_units": 1,
        "read_roles": frozenset({"R_in"}),
        "write_roles": frozenset({"R_out"}),
        "source": "p.su",
        "axon_keys": frozenset(),
    }
    fields.update(overrides)
    return Manifest(**fields)


def test_load_echo_manifest_real_file() -> None:
    m = load_manifest(MANIFESTS / "echo.toml")
    assert m.name == "echo"
    assert m.axon_width == 768
    assert m.compute_units == 1
    assert m.read_roles == frozenset({"R_input"})
    assert m.write_roles == frozenset({"R_output"})
    assert m.source.endswith("echo.su")


def test_load_sink_manifest_real_file() -> None:
    m = load_manifest(MANIFESTS / "sink.toml")
    assert m.name == "sink"
    assert m.read_roles == frozenset({"R_output"})
    assert m.write_roles == frozenset({"R_stat"})


def test_load_manifest_missing_file(tmp_path: pathlib.Path) -> None:
    with pytest.raises(ManifestError, match="not found"):
        load_manifest(tmp_path / "does-not-exist.toml")


def test_load_manifest_missing_required_field(tmp_path: pathlib.Path) -> None:
    p = tmp_path / "bad.toml"
    p.write_text(
        'name = "x"\naxon_width = 1\ncompute_units = 1\n'
        'read_roles = []\n# missing: write_roles, source\n',
        encoding="utf-8",
    )
    with pytest.raises(ManifestError, match="missing required field"):
        load_manifest(p)


def test_load_manifest_bad_types(tmp_path: pathlib.Path) -> None:
    p = tmp_path / "bad.toml"
    p.write_text(
        'name = "x"\naxon_width = 0\ncompute_units = 1\n'
        'read_roles = []\nwrite_roles = []\nsource = "x.su"\n',
        encoding="utf-8",
    )
    with pytest.raises(ManifestError, match="axon_width must be a positive int"):
        load_manifest(p)


# ---- admission control -----------------------------------------------


def test_admit_decrements_pool() -> None:
    init = Init(compute_pool=5)
    assert init.compute_pool_free == 5

    init.admit(_make_manifest("a", compute_units=2), PythonService(lambda s, ax: None))
    assert init.compute_pool_free == 3
    assert init.admitted() == ["a"]

    init.admit(_make_manifest("b", compute_units=3), PythonService(lambda s, ax: None))
    assert init.compute_pool_free == 0
    assert init.admitted() == ["a", "b"]


def test_admit_refuses_when_pool_exhausted() -> None:
    init = Init(compute_pool=2)
    init.admit(_make_manifest("a", compute_units=2), PythonService(lambda s, ax: None))

    with pytest.raises(PoolExhaustedError, match="needs 1 compute_units"):
        init.admit(_make_manifest("b", compute_units=1), PythonService(lambda s, ax: None))

    # Failed admission must not have changed pool state.
    assert init.compute_pool_free == 0
    assert init.admitted() == ["a"]


def test_admit_refuses_duplicate_name() -> None:
    init = Init(compute_pool=10)
    init.admit(_make_manifest("a"), PythonService(lambda s, ax: None))
    with pytest.raises(AdmissionError, match="already admitted"):
        init.admit(_make_manifest("a"), PythonService(lambda s, ax: None))


def test_deregister_returns_budget() -> None:
    init = Init(compute_pool=5)
    init.admit(_make_manifest("a", compute_units=3), PythonService(lambda s, ax: None))
    assert init.compute_pool_free == 2

    init.deregister("a")
    assert init.compute_pool_free == 5
    assert init.admitted() == []


def test_deregister_unknown_raises() -> None:
    init = Init(compute_pool=5)
    with pytest.raises(AdmissionError, match="not admitted"):
        init.deregister("nope")


def test_init_rejects_zero_pool() -> None:
    with pytest.raises(ValueError, match="compute_pool must be positive"):
        Init(compute_pool=0)


# ---- router capability checks ----------------------------------------


def _admit(
    init: Init, *,
    name: str, reads: set[str], writes: set[str],
    svc: PythonService | None = None,
    axon_keys: set[str] | None = None,
) -> PythonService:
    s = svc or PythonService(lambda s, ax: None)
    init.admit(
        _make_manifest(
            name=name,
            read_roles=frozenset(reads),
            write_roles=frozenset(writes),
            axon_keys=frozenset(axon_keys or set()),
        ),
        s,
    )
    return s


def test_send_refused_when_sender_lacks_write_role() -> None:
    init = Init(compute_pool=5)
    sender = _admit(init, name="sender", reads=set(), writes={"R_a"})
    _admit(init, name="receiver", reads={"R_b"}, writes=set())

    with pytest.raises(CapabilityError, match="cannot write role 'R_b'"):
        sender.emit("R_b", "payload")


def test_send_to_unadmitted_role_is_black_hole() -> None:
    init = Init(compute_pool=5)
    sender = _admit(init, name="sender", reads=set(), writes={"R_x"})
    # No process has read_roles containing "R_x" — the send is dropped.
    delivered = sender.emit("R_x", "payload")
    assert delivered == 0
    assert init.router.dropped_count() == 1


def test_send_delivers_to_one_receiver() -> None:
    init = Init(compute_pool=5)
    sender = _admit(init, name="sender", reads=set(), writes={"R_x"})
    _admit(init, name="receiver", reads={"R_x"}, writes=set())

    delivered = sender.emit("R_x", "payload")
    assert delivered == 1
    assert init.router.inbox_depth("receiver") == 1


def test_send_fans_out_to_multiple_receivers() -> None:
    init = Init(compute_pool=5)
    sender = _admit(init, name="sender", reads=set(), writes={"R_x"})
    _admit(init, name="r1", reads={"R_x"}, writes=set())
    _admit(init, name="r2", reads={"R_x"}, writes=set())

    delivered = sender.emit("R_x", "payload")
    assert delivered == 2
    assert init.router.inbox_depth("r1") == 1
    assert init.router.inbox_depth("r2") == 1


def test_fv_role_contract_read_isolation() -> None:
    """FV §3.1 contract obligation, RECEIVE half: a process is delivered ONLY
    axons on roles it declared in read_roles, even when other roles flow
    concurrently — no cross-role leakage.

    Complements the WRITE/capability half (test_send_refused_when_sender_
    lacks_write_role) and the no-reader case (test_send_to_unadmitted_role_
    is_black_hole). Together these mechanically discharge the role-level
    contract obligation the kernel enforces (cf.
    external/Sutra/planning/sutra-spec/formal-verification.md §3.1). The
    router enforces read-isolation structurally via its role->readers table;
    this confirms it with two concurrent roles and checks the payloads are
    role-correct, so a routing bug that crossed the streams would be caught.
    """
    init = Init(compute_pool=5)
    got_a: list[tuple[str, object]] = []
    got_b: list[tuple[str, object]] = []
    sender = _admit(init, name="sender", reads=set(), writes={"R_a", "R_b"})
    _admit(
        init, name="reader_a", reads={"R_a"}, writes=set(),
        svc=PythonService(lambda s, ax: got_a.append((ax.role, ax.payload))),
    )
    _admit(
        init, name="reader_b", reads={"R_b"}, writes=set(),
        svc=PythonService(lambda s, ax: got_b.append((ax.role, ax.payload))),
    )

    sender.emit("R_a", "payload_a")
    sender.emit("R_b", "payload_b")
    init.tick()

    # Each reader saw exactly its own role's axon — no cross-delivery.
    assert got_a == [("R_a", "payload_a")], f"reader_a cross-delivery: {got_a}"
    assert got_b == [("R_b", "payload_b")], f"reader_b cross-delivery: {got_b}"


def test_send_from_unadmitted_process_raises() -> None:
    router = AxonRouter()
    with pytest.raises(NotAdmittedError):
        router.send(Axon(role="R_x", payload=None, from_proc="ghost"))


def test_inbox_depth_unadmitted_raises() -> None:
    router = AxonRouter()
    with pytest.raises(NotAdmittedError):
        router.inbox_depth("ghost")


# ---- multi-process round trip ---------------------------------------


def test_echo_sink_round_trip_with_real_manifests() -> None:
    """Infrastructure round-trip: real manifests, two services, axons routed.

    Uses PythonService stand-ins so this test runs without the Sutra
    runtime cost. The same scenario with real Sutra-compiled services
    is in tests/test_kernel_sutra.py.
    """
    init = Init(compute_pool=4)
    echo = _echo_python(output_role="R_output")
    sink = _CountingSink(stat_role="R_stat", report_every=10_000)

    init.admit_from_path(MANIFESTS / "echo.toml", echo)
    init.admit_from_path(MANIFESTS / "sink.toml", sink)

    # Inject a producer-shaped process that can write R_input. We
    # do this through a third manifest constructed inline so the
    # test doesn't need a real producer.toml shipping.
    producer = PythonService(lambda s, ax: None)
    init.admit(
        _make_manifest(
            name="producer", compute_units=1,
            read_roles=frozenset(),
            write_roles=frozenset({"R_input"}),
        ),
        producer,
    )

    # Send three payloads in. Echo's inbox should fill; sink's
    # should be empty until echo ticks.
    for payload in ("alpha", "beta", "gamma"):
        producer.emit("R_input", payload)
    assert init.router.inbox_depth("echo") == 3
    assert init.router.inbox_depth("sink") == 0

    # One tick: echo drains its inbox, re-emits each on R_output;
    # the router delivers each to sink. Sink's tick then drains.
    counts = init.tick()
    assert counts == {"producer": 0, "echo": 3, "sink": 3}
    assert sink.count == 3
    assert init.router.inbox_depth("echo") == 0
    assert init.router.inbox_depth("sink") == 0


def test_sink_stat_emit_is_black_hole_no_logger() -> None:
    """Sink emits R_stat every report_every ticks; no logger ⇒ dropped."""
    init = Init(compute_pool=3)
    echo = _echo_python()
    sink = _CountingSink(stat_role="R_stat", report_every=2)
    init.admit_from_path(MANIFESTS / "echo.toml", echo)
    init.admit_from_path(MANIFESTS / "sink.toml", sink)
    producer = PythonService(lambda s, ax: None)
    init.admit(
        _make_manifest(
            name="producer", compute_units=1,
            read_roles=frozenset(),
            write_roles=frozenset({"R_input"}),
        ),
        producer,
    )

    for _ in range(4):
        producer.emit("R_input", "x")
    init.tick()  # echo drains 4 → emits 4 to sink → sink drains 4
    # Sink emits R_stat every 2 absorbs ⇒ 2 emissions to a non-existent
    # logger ⇒ dropped audit count goes up by 2.
    assert init.router.dropped_count() == 2
    assert sink.count == 4


# ---- lazy axon evaluation -------------------------------------------


def test_lazy_skip_when_keys_dont_intersect() -> None:
    """Receiver declaring axon_keys it doesn't share with the axon is skipped."""
    init = Init(compute_pool=5)
    sender = _admit(init, name="s", reads=set(), writes={"R_x"})
    # Receiver wants {"animal_2", "color_1"} but the axon will only
    # carry {"user_1"} — no intersection ⇒ skip.
    _admit(
        init, name="r", reads={"R_x"}, writes=set(),
        axon_keys={"animal_2", "color_1"},
    )

    delivered = sender.emit("R_x", "payload", keys={"user_1"})
    assert delivered == 0, "axon's keys don't intersect r's axon_keys; skip"
    assert init.router.lazy_skipped_count() == 1
    assert init.router.inbox_depth("r") == 0
    # Black-hole NOT triggered — there is a wired receiver, we just
    # chose not to deliver to them.
    assert init.router.dropped_count() == 0


def test_lazy_delivers_when_keys_intersect() -> None:
    """Receiver gets the axon when key intersection is non-empty."""
    init = Init(compute_pool=5)
    sender = _admit(init, name="s", reads=set(), writes={"R_x"})
    _admit(
        init, name="r", reads={"R_x"}, writes=set(),
        axon_keys={"animal_2", "color_1"},
    )

    # Axon carries one of the two keys r asked for.
    delivered = sender.emit("R_x", "payload", keys={"animal_2", "user_1"})
    assert delivered == 1
    assert init.router.lazy_skipped_count() == 0
    assert init.router.inbox_depth("r") == 1


def test_lazy_eager_fallback_when_receiver_unkeyed() -> None:
    """Receiver with no axon_keys gets every axon — original behaviour."""
    init = Init(compute_pool=5)
    sender = _admit(init, name="s", reads=set(), writes={"R_x"})
    # No axon_keys declared = eager fallback.
    _admit(init, name="r", reads={"R_x"}, writes=set(), axon_keys=set())

    delivered = sender.emit("R_x", "payload", keys={"some_key"})
    assert delivered == 1, "unkeyed receivers get every axon (eager fallback)"
    assert init.router.lazy_skipped_count() == 0


def test_lazy_eager_fallback_when_axon_unkeyed() -> None:
    """Axon with no declared keys gets delivered to every receiver."""
    init = Init(compute_pool=5)
    sender = _admit(init, name="s", reads=set(), writes={"R_x"})
    _admit(
        init, name="r", reads={"R_x"}, writes=set(),
        axon_keys={"strict_key"},
    )

    # Sender doesn't declare keys ⇒ router can't make a lazy decision
    # ⇒ falls back to eager. Useful for v0.0 stub producers and
    # debugger-emitted axons that don't go through static wiring.
    delivered = sender.emit("R_x", "payload")
    assert delivered == 1
    assert init.router.lazy_skipped_count() == 0


def test_lazy_partial_fanout_one_skips_one_delivers() -> None:
    """Two receivers on same role; only the keyed-matching one gets it."""
    init = Init(compute_pool=5)
    sender = _admit(init, name="s", reads=set(), writes={"R_x"})
    _admit(
        init, name="r_match", reads={"R_x"}, writes=set(),
        axon_keys={"animal_2"},
    )
    _admit(
        init, name="r_skip", reads={"R_x"}, writes=set(),
        axon_keys={"unrelated_key"},
    )

    delivered = sender.emit("R_x", "payload", keys={"animal_2"})
    assert delivered == 1
    assert init.router.inbox_depth("r_match") == 1
    assert init.router.inbox_depth("r_skip") == 0
    assert init.router.lazy_skipped_count() == 1


def test_lazy_capability_check_still_fires_first() -> None:
    """A sender without write capability fails even if keys would intersect."""
    init = Init(compute_pool=5)
    sender = _admit(init, name="s", reads=set(), writes={"R_only"})
    _admit(
        init, name="r", reads={"R_x"}, writes=set(),
        axon_keys={"k"},
    )

    with pytest.raises(CapabilityError, match="cannot write role 'R_x'"):
        sender.emit("R_x", "payload", keys={"k"})


def test_lazy_keys_optional_in_manifest_toml(tmp_path: pathlib.Path) -> None:
    """Manifest TOML without axon_keys parses cleanly (defaults to empty)."""
    p = tmp_path / "p.toml"
    p.write_text(
        'name = "p"\n'
        'axon_width = 768\n'
        'compute_units = 1\n'
        'read_roles = ["R_in"]\n'
        'write_roles = ["R_out"]\n'
        'source = "p.su"\n',
        encoding="utf-8",
    )
    m = load_manifest(p)
    assert m.axon_keys == frozenset()


def test_lazy_keys_in_manifest_toml(tmp_path: pathlib.Path) -> None:
    """When axon_keys IS in the manifest TOML, it parses to a frozenset."""
    p = tmp_path / "p.toml"
    p.write_text(
        'name = "p"\n'
        'axon_width = 768\n'
        'compute_units = 1\n'
        'read_roles = ["R_in"]\n'
        'write_roles = ["R_out"]\n'
        'source = "p.su"\n'
        'axon_keys = ["animal_2", "color_1", "user_1"]\n',
        encoding="utf-8",
    )
    m = load_manifest(p)
    assert m.axon_keys == frozenset({"animal_2", "color_1", "user_1"})


def test_lazy_bad_manifest_axon_keys_raises(tmp_path: pathlib.Path) -> None:
    """axon_keys that isn't a list of strings is a clear error."""
    p = tmp_path / "p.toml"
    p.write_text(
        'name = "p"\n'
        'axon_width = 768\n'
        'compute_units = 1\n'
        'read_roles = ["R_in"]\n'
        'write_roles = ["R_out"]\n'
        'source = "p.su"\n'
        'axon_keys = "not-a-list"\n',
        encoding="utf-8",
    )
    with pytest.raises(ManifestError, match="axon_keys must be a list of strings"):
        load_manifest(p)


# ---- per-receiver projection ----------------------------------------


def test_projector_slims_payload_when_intersection_is_strict_subset() -> None:
    """When sender has projector + receiver wants subset, router projects."""
    # Stand-in projector returns a tagged tuple so we can verify what
    # arguments it received without needing real Sutra.
    init = Init(compute_pool=5)
    sender = _admit(init, name="s", reads=set(), writes={"R_x"})
    _admit(
        init, name="r", reads={"R_x"}, writes=set(),
        axon_keys={"k1"},  # wants only k1
    )

    captured: list[tuple] = []
    def projector(payload, requested_keys):
        captured.append((payload, requested_keys))
        return f"PROJECTED:{sorted(requested_keys)}"

    init.router.register_projector("s", projector)
    delivered = sender.emit("R_x", "FULL_PAYLOAD", keys={"k1", "k2", "k3"})
    assert delivered == 1
    # Projector got called with the full payload + the intersection.
    assert captured == [("FULL_PAYLOAD", frozenset({"k1"}))]
    # And the router's projection counter ticked.
    assert init.router.lazy_projected_count() == 1
    # The receiver's inbox holds the projected payload, not the original.
    inbox = init.router.receive("r")
    assert inbox is not None
    assert inbox.payload == "PROJECTED:['k1']"
    assert inbox.keys == frozenset({"k1"})


def test_projector_skipped_when_receiver_wants_all_keys() -> None:
    """When intersection == full keys, no projection — pass through."""
    init = Init(compute_pool=5)
    sender = _admit(init, name="s", reads=set(), writes={"R_x"})
    _admit(
        init, name="r", reads={"R_x"}, writes=set(),
        axon_keys={"k1", "k2"},  # wants both
    )

    def projector(payload, requested_keys):
        raise AssertionError("projector should not be called when receiver wants everything")

    init.router.register_projector("s", projector)
    sender.emit("R_x", "FULL", keys={"k1", "k2"})
    assert init.router.lazy_projected_count() == 0
    inbox = init.router.receive("r")
    assert inbox.payload == "FULL"  # untouched


def test_no_projector_falls_back_to_full_delivery() -> None:
    """Senders without a registered projector get pass-through behaviour."""
    init = Init(compute_pool=5)
    sender = _admit(init, name="s", reads=set(), writes={"R_x"})
    _admit(
        init, name="r", reads={"R_x"}, writes=set(),
        axon_keys={"k1"},  # wants subset
    )
    # NO register_projector call.
    sender.emit("R_x", "FULL", keys={"k1", "k2", "k3"})
    inbox = init.router.receive("r")
    assert inbox.payload == "FULL"  # full delivered, no projection
    assert inbox.keys == frozenset({"k1", "k2", "k3"})  # original keys
    assert init.router.lazy_projected_count() == 0


def test_register_projector_for_unadmitted_raises() -> None:
    init = Init(compute_pool=5)
    with pytest.raises(NotAdmittedError):
        init.router.register_projector("ghost", lambda p, k: p)


def test_deregister_drops_projector() -> None:
    """When a sender deregisters, its projector goes too."""
    init = Init(compute_pool=5)
    _admit(init, name="s", reads=set(), writes={"R_x"})
    init.router.register_projector("s", lambda p, k: "X")
    init.deregister("s")
    # Internal projectors dict should have dropped the entry.
    assert "s" not in init.router._projectors  # noqa: SLF001 — test
