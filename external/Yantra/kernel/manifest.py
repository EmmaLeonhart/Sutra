"""Per-process manifest format for the Yantra kernel.

A manifest declares everything `init` needs to admit a process:

  - `name`            — unique process name (also the routing identity)
  - `axon_width`      — fixed-width vector size, in dim count
  - `compute_units`   — abstract compute budget against the pool
  - `read_roles`      — role names the process can read (capability)
  - `write_roles`     — role names the process can write (capability)
  - `source`          — relative path to the .su (or .py stub) source

The format is TOML to match Sutra's `atman.toml` convention. Per
`planning/17-memory-model.md`, a future `scratchpad_units` field is
expected; for v0.0 the only allocation is `compute_units` against the
admission pool.
"""

from __future__ import annotations

import dataclasses
import pathlib
import sys

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover — current target is 3.13
    import tomli as tomllib  # type: ignore[no-redef]


class ManifestError(ValueError):
    """A manifest is missing required fields or has invalid values."""


@dataclasses.dataclass(frozen=True)
class Manifest:
    """Parsed, validated process manifest.

    Frozen so the resource manager can hash + cache it without worry.
    """

    name: str
    axon_width: int
    compute_units: int
    read_roles: frozenset[str]
    write_roles: frozenset[str]
    source: str  # relative to the manifest file's directory
    # Lazy axon evaluation (per planning/20-lazy-axon-evaluation.md):
    # which axon-internal keys this process actually reads. The router
    # uses this to skip delivery of axons whose keys don't intersect.
    # Empty (default) means "no key declarations" — eager fallback,
    # the receiver gets every axon on its read_roles regardless of
    # what's bound inside. For a real connectome this should be
    # populated; for v0.0 smoke tests the empty fallback is fine.
    axon_keys: frozenset[str] = dataclasses.field(default_factory=frozenset)

    def resolved_source(self, manifest_path: pathlib.Path) -> pathlib.Path:
        """Return the absolute source path implied by this manifest.

        `source` in the manifest is relative to the manifest file's
        directory, so that manifest files stay portable.
        """
        return (manifest_path.parent / self.source).resolve()


_REQUIRED_FIELDS = {
    "name", "axon_width", "compute_units", "read_roles", "write_roles", "source",
}


def load_manifest(path: str | pathlib.Path) -> Manifest:
    """Read + validate a manifest TOML file.

    Raises `ManifestError` with a single clear message on any
    validation failure — admission control needs structured failures,
    not a stack trace inside `init`.
    """
    p = pathlib.Path(path)
    if not p.is_file():
        raise ManifestError(f"manifest not found: {p}")

    with p.open("rb") as f:
        try:
            doc = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            raise ManifestError(f"manifest {p} is not valid TOML: {e}") from e

    missing = _REQUIRED_FIELDS - set(doc)
    if missing:
        raise ManifestError(
            f"manifest {p} missing required field(s): {sorted(missing)}"
        )

    if not isinstance(doc["name"], str) or not doc["name"]:
        raise ManifestError(f"manifest {p}: name must be a non-empty string")
    if not isinstance(doc["axon_width"], int) or doc["axon_width"] <= 0:
        raise ManifestError(f"manifest {p}: axon_width must be a positive int")
    if not isinstance(doc["compute_units"], int) or doc["compute_units"] <= 0:
        raise ManifestError(f"manifest {p}: compute_units must be a positive int")
    for field in ("read_roles", "write_roles"):
        val = doc[field]
        if not isinstance(val, list) or not all(isinstance(r, str) for r in val):
            raise ManifestError(
                f"manifest {p}: {field} must be a list of strings"
            )
    if not isinstance(doc["source"], str) or not doc["source"]:
        raise ManifestError(f"manifest {p}: source must be a non-empty string")

    # axon_keys is optional (default to empty frozenset = eager
    # fallback). When present, must be a list of strings.
    axon_keys_raw = doc.get("axon_keys", [])
    if not isinstance(axon_keys_raw, list) or not all(
        isinstance(k, str) for k in axon_keys_raw
    ):
        raise ManifestError(
            f"manifest {p}: axon_keys must be a list of strings (omit or [] for "
            f"eager-fallback delivery)"
        )

    return Manifest(
        name=doc["name"],
        axon_width=doc["axon_width"],
        compute_units=doc["compute_units"],
        read_roles=frozenset(doc["read_roles"]),
        write_roles=frozenset(doc["write_roles"]),
        source=doc["source"],
        axon_keys=frozenset(axon_keys_raw),
    )
