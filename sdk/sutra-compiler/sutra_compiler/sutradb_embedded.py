"""Embedded SutraDB wrapper — ctypes binding to sutra_ffi.dll.

Thin Python class around the SutraDB FFI: opens a `.sdb` file,
inserts labeled embeddings, and runs nearest-neighbor queries via
SPARQL+'s `VECTOR_SIMILAR` operator.

This module proves the embedding path works standalone. The Sutra
runtime does not yet route `argmax_cosine` through it; this file
gives codegen something to call once that wiring lands.

## Architecture

SutraDB is a Rust HNSW + RDF triplestore (`sutraDB/` in this repo).
Its C-ABI shared library (`sutra_ffi.dll` from `sutra-ffi` crate)
exposes opaque database handles + SPARQL execution. We `ctypes`-load
that library, open a database (in-memory `:memory:` or a `.sdb`
file), insert N-triples that bind labels to vector literals, and
query via SPARQL+ for nearest-neighbor lookup.

The "embedded" claim is real: no separate process, no HTTP, no
daemon. The compiled Sutra program loads the .dll at module init
and uses the database in-process.

## Vector encoding

SutraDB stores vectors as object literals typed `<http://sutra.dev/
f32vec>` with whitespace-separated floats:

    <urn:label:cat> <urn:embedding> "0.23 -0.11 0.87 ..."^^<http://sutra.dev/f32vec> .

The FFI's `sutra_db_open` rebuilds HNSW indexes from any vector
triples in the existing store; the FFI's `sutra_insert_ntriples`
adds new vectors and updates the index.

## Querying

SPARQL+ exposes `VECTOR_SIMILAR(?s :pred ?vec, threshold)`. Today's
nearest-neighbor query for our use case:

    SELECT ?s WHERE {
        ?s <urn:embedding> ?v .
        VECTOR_SIMILAR(?s <urn:embedding> "<query_vec>"^^<http://sutra.dev/f32vec>, 0.0)
    }
    ORDER BY DESC(VECTOR_SCORE(?s <urn:embedding> "<query_vec>"^^<http://sutra.dev/f32vec>))
    LIMIT 1

The threshold of 0.0 means "any cosine"; ORDER BY DESC + LIMIT 1
picks the closest. For k-NN, set LIMIT k.

## Known limitations

- SPARQL string concatenation per query is wasteful; for a hot
  argmax_cosine loop this needs cached PreparedQuery shape (not yet
  exposed by FFI).
- Vector literal encoding (whitespace-separated floats) round-trips
  through string formatting on every insert. For large codebooks at
  compile time this is fine; for runtime hot-path it isn't.
- The DLL load path assumes the build artifact is at
  `sutraDB/target/release/sutra_ffi.dll` relative to the repo root.
  Production deployment needs a packaging story (TODO).
"""
from __future__ import annotations

import ctypes
import os
from pathlib import Path
from typing import Optional, Sequence


# ────────────────────────────────────────────────────────────────────────
# DLL discovery
# ────────────────────────────────────────────────────────────────────────


def _default_dll_path() -> Path:
    """Locate sutra_ffi.dll relative to this file's repo root.

    Override via env var SUTRA_FFI_DLL.
    """
    env = os.environ.get("SUTRA_FFI_DLL")
    if env:
        return Path(env)
    # this file is at sdk/sutra-compiler/sutra_compiler/sutradb_embedded.py;
    # repo root is three parents up.
    repo_root = Path(__file__).resolve().parents[3]
    return repo_root / "sutraDB" / "target" / "release" / "sutra_ffi.dll"


# ────────────────────────────────────────────────────────────────────────
# ctypes signature setup
# ────────────────────────────────────────────────────────────────────────


def _bind_sutra_ffi(dll_path: Path) -> ctypes.CDLL:
    """Load the sutra_ffi DLL and bind argument/return types."""
    if not dll_path.exists():
        raise FileNotFoundError(
            f"sutra_ffi.dll not found at {dll_path}. Build with:\n"
            f"  cd {dll_path.parents[2]} && cargo build --release -p sutra-ffi\n"
            f"or set SUTRA_FFI_DLL to override the path."
        )
    lib = ctypes.CDLL(str(dll_path))

    # ── Lifecycle
    lib.sutra_db_open.argtypes = [ctypes.c_char_p]
    lib.sutra_db_open.restype = ctypes.c_void_p
    lib.sutra_db_close.argtypes = [ctypes.c_void_p]
    lib.sutra_db_close.restype = None

    # ── Errors
    lib.sutra_last_error.argtypes = []
    lib.sutra_last_error.restype = ctypes.c_char_p

    # ── Triples
    lib.sutra_insert_ntriples.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    lib.sutra_insert_ntriples.restype = ctypes.c_int64

    # ── Query
    lib.sutra_query.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    lib.sutra_query.restype = ctypes.c_void_p

    lib.sutra_result_column_count.argtypes = [ctypes.c_void_p]
    lib.sutra_result_column_count.restype = ctypes.c_uint32

    lib.sutra_result_row_count.argtypes = [ctypes.c_void_p]
    lib.sutra_result_row_count.restype = ctypes.c_uint64

    lib.sutra_result_value.argtypes = [
        ctypes.c_void_p, ctypes.c_uint64, ctypes.c_uint32,
    ]
    lib.sutra_result_value.restype = ctypes.c_void_p

    lib.sutra_result_free.argtypes = [ctypes.c_void_p]
    lib.sutra_result_free.restype = None

    lib.sutra_string_free.argtypes = [ctypes.c_void_p]
    lib.sutra_string_free.restype = None

    return lib


# ────────────────────────────────────────────────────────────────────────
# High-level wrapper
# ────────────────────────────────────────────────────────────────────────


VECTOR_PRED = "<urn:sutra:embedding>"
F32VEC_TYPE = "<http://sutra.dev/f32vec>"


class SutraDBEmbedded:
    """In-process SutraDB for vector lookup.

    Usage:
        db = SutraDBEmbedded(":memory:")
        db.add("cat", [0.23, -0.11, 0.87, ...])
        db.add("dog", [0.31, -0.05, 0.42, ...])
        label = db.nearest([0.25, -0.10, 0.85, ...])  # -> "cat"
        db.close()

    Reads from an existing `.sdb` file rebuild the HNSW index on open
    so subsequent queries are fast.
    """

    def __init__(
        self,
        path: str = ":memory:",
        dll_path: Optional[Path] = None,
    ) -> None:
        self._lib = _bind_sutra_ffi(dll_path or _default_dll_path())
        self._path = path
        c_path = path.encode("utf-8")
        self._db = self._lib.sutra_db_open(c_path)
        if not self._db:
            err = self._last_error()
            raise RuntimeError(f"sutra_db_open failed: {err}")
        self._closed = False

    def _last_error(self) -> str:
        ptr = self._lib.sutra_last_error()
        if not ptr:
            return "(no error message)"
        return ctypes.c_char_p(ptr).value.decode("utf-8", errors="replace")

    def add(self, label: str, vec: Sequence[float]) -> None:
        """Insert one (label, vector) pair as a triple.

        Each label gets a unique IRI `<urn:sutra:label:LABEL>` (must be
        URL-safe — the wrapper does not validate). The vector is stored
        as the object of a triple with predicate `<urn:sutra:embedding>`,
        typed `<http://sutra.dev/f32vec>`.

        As of FFI build 2026-04-30 (queue item 2 piece 6),
        `sutra_insert_ntriples` auto-declares vector predicates and
        adds the vector to the HNSW index inline — no close+reopen
        needed. The FFI rebuild on open still works; this just removes
        the slow path for fresh inserts.
        """
        if self._closed:
            raise RuntimeError("SutraDBEmbedded already closed")
        # Encode the vector literal: whitespace-separated floats.
        vec_lit = " ".join(f"{float(x):.8g}" for x in vec)
        # N-triple: <subj> <pred> "<vec>"^^<f32vec> .
        triple = (
            f"<urn:sutra:label:{label}> {VECTOR_PRED} "
            f'"{vec_lit}"^^{F32VEC_TYPE} .\n'
        )
        n = self._lib.sutra_insert_ntriples(self._db, triple.encode("utf-8"))
        if n < 0:
            err = self._last_error()
            raise RuntimeError(f"sutra_insert_ntriples failed: {err}")

    def nearest(self, query: Sequence[float], k: int = 1) -> list[str]:
        """Return the `k` nearest labels to `query` by cosine similarity.

        Result is ordered most-similar first.
        """
        if self._closed:
            raise RuntimeError("SutraDBEmbedded already closed")
        vec_lit = " ".join(f"{float(x):.8g}" for x in query)
        sparql = (
            f"SELECT ?s WHERE {{ "
            f"?s {VECTOR_PRED} ?v . "
            f'VECTOR_SIMILAR(?s {VECTOR_PRED} "{vec_lit}"^^{F32VEC_TYPE}, 0.0) '
            f"}} "
            f'ORDER BY DESC(VECTOR_SCORE(?s {VECTOR_PRED} "{vec_lit}"^^{F32VEC_TYPE})) '
            f"LIMIT {int(k)}"
        )
        result = self._lib.sutra_query(self._db, sparql.encode("utf-8"))
        if not result:
            err = self._last_error()
            raise RuntimeError(f"sutra_query failed: {err}")
        try:
            n_rows = self._lib.sutra_result_row_count(result)
            labels: list[str] = []
            for i in range(n_rows):
                val_ptr = self._lib.sutra_result_value(result, i, 0)
                if not val_ptr:
                    continue
                raw = ctypes.c_char_p(val_ptr).value
                s = raw.decode("utf-8", errors="replace") if raw else ""
                # Strip the IRI wrapping back to bare label. SutraDB
                # returns IRIs without angle brackets in result rows.
                prefix_naked = "urn:sutra:label:"
                prefix_bracketed = "<urn:sutra:label:"
                if s.startswith(prefix_bracketed) and s.endswith(">"):
                    s = s[len(prefix_bracketed):-1]
                elif s.startswith(prefix_naked):
                    s = s[len(prefix_naked):]
                labels.append(s)
                self._lib.sutra_string_free(val_ptr)
            return labels
        finally:
            self._lib.sutra_result_free(result)

    def close(self) -> None:
        if self._closed:
            return
        self._lib.sutra_db_close(self._db)
        self._closed = True
        self._db = None  # type: ignore[assignment]

    def __enter__(self) -> "SutraDBEmbedded":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass
