"""Yantra kernel — Connectome Manager (v0.0).

The kernel admits Sutra services as processes, gives each one a
fixed budget at admission time, and routes axons between them with
capability checks. **Sutra is doing the actual computation**: each
service is a `SutraService` whose `.su` source is compiled by the
Sutra v0.4.0 compiler and executed on real torch tensors carried
through the router as axon payloads. The Python here is the
**orchestration layer** — the CPU-side init/resource-manager and
the in-process axon router. It does not do the compute; it
schedules and connects the things that do.

The orchestration layer is in **Python** in this repo as a
near-term implementation. The eventual production form on the
CPU side is **Rust** (per `planning/01-architecture.md` §
"CPU side: small, Rust, orchestrator"); the Python implementation
here pins the API shape and gives the Rust port a target test
suite (currently 19 unit tests + 6 real-Sutra integration tests,
all passing).

See `planning/01-architecture.md` § "The kernel is a Connectome
Manager" for the architectural framing. See `kernel/README.md` for
what the v0.0 covers and what is honestly out of scope until
upstream Sutra-side work (per-process GPU memory arenas, evict-
to-RAM, GPU-tick-parallel scheduling) lands.

What is real here:

- Manifest format and parsing (`manifest.py`).
- Per-process admission control against a fixed pool budget,
  refusing new admissions cleanly when the pool is exhausted
  (`init.py`).
- An in-memory axon router with capability check on both write
  (sender must possess the role) and read (receiver must possess
  the role) (`router.py`).
- A service abstraction that does NOT yet require a `.su` file —
  Python-callable services and `.su`-compiled services are both
  supported; in v0.0 the included services are Python stubs
  (`services.py`) and one example `.su` file showing the shape
  the real ones will take (`services/echo.su`).

What is stubbed and known to be stubbed:

- "Fixed GPU memory arena" allocation is currently book-keeping
  only — the runtime tracks a budget pool but does not carve out
  actual device memory. This matches what a v0.0 can do without
  the multi-process runtime that lives in Sutra itself.
- Inter-process concurrency is thread-based, not GPU-tick-based.
  A real Yantra kernel runs all admitted processes simultaneously
  on the GPU at each tick; the v0.0 schedules service ticks
  sequentially on the CPU.
- Service failure isolation is not enforced. A misbehaving
  service can crash the runtime in v0.0; capability discipline
  is what's enforced, not memory isolation.

These stubs are documented at the call sites where they bite, so
that the v0.1 work knows what to harden.
"""

from kernel.manifest import Manifest, ManifestError, load_manifest
from kernel.router import (
    Axon,
    AxonRouter,
    CapabilityError,
    NotAdmittedError,
)
from kernel.init import (
    AdmissionError,
    Init,
    PoolExhaustedError,
    Tier,
)
from kernel.checkpoint import (
    CheckpointError,
    ColdProcess,
    parse_process,
    restore_kernel_state,
    serialise_kernel_state,
    serialise_process,
)
from kernel.serialise import (
    AxonSerialiseError,
    deserialise_axon,
    deserialise_axon_payload,
    serialise_axon,
    serialise_axon_payload,
)
from kernel.services import (
    PythonService,
    Service,
    SutraService,
    make_shared_sutra_services,
)

__all__ = [
    "AdmissionError",
    "Axon",
    "AxonRouter",
    "AxonSerialiseError",
    "CapabilityError",
    "CheckpointError",
    "ColdProcess",
    "Init",
    "Manifest",
    "ManifestError",
    "NotAdmittedError",
    "PoolExhaustedError",
    "PythonService",
    "Service",
    "SutraService",
    "Tier",
    "deserialise_axon",
    "deserialise_axon_payload",
    "load_manifest",
    "make_shared_sutra_services",
    "parse_process",
    "restore_kernel_state",
    "serialise_axon",
    "serialise_axon_payload",
    "serialise_kernel_state",
    "serialise_process",
]
