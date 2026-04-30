"""Tests for the embedded SutraDB wrapper.

Smoke test that confirms (a) the FFI DLL loads, (b) we can insert
labeled vectors, (c) nearest-neighbor query returns the expected
label. If sutra_ffi.dll isn't built, all tests are skipped — they
don't fail the suite.

Per Emma 2026-04-30 (queue item 2): SutraDB embedded in compiled
Sutra programs replaces argmax_cosine. This test pins the
embedded API so codegen wiring (separate task) has a known-good
shape to call.
"""
from __future__ import annotations

import os
import tempfile
import unittest

import pytest

from sutra_compiler.sutradb_embedded import (
    SutraDBEmbedded,
    _default_dll_path,
)


_DLL = _default_dll_path()
_DLL_AVAILABLE = _DLL.exists()


@pytest.mark.skipif(
    not _DLL_AVAILABLE,
    reason=(
        f"sutra_ffi.dll not found at {_DLL}. Build with: "
        "cd sutraDB && cargo build --release -p sutra-ffi"
    ),
)
class TestSutraDBEmbedded(unittest.TestCase):
    """Round-trip insert + nearest-neighbor over the FFI.

    SutraDB's sled-backed store needs a real filesystem path, so each
    test uses a fresh temp dir. (':memory:' is not supported by sled.)
    """

    def setUp(self) -> None:
        self._tmpdir = tempfile.mkdtemp(prefix="sutradb_test_")

    def tearDown(self) -> None:
        # sled keeps the dir around; ignore cleanup errors.
        import shutil
        try:
            shutil.rmtree(self._tmpdir, ignore_errors=True)
        except OSError:
            pass

    def _new_db(self) -> SutraDBEmbedded:
        path = os.path.join(self._tmpdir, "test.sdb")
        return SutraDBEmbedded(path)

    def test_open_db(self):
        with self._new_db() as db:
            self.assertIsNotNone(db._db)

    def test_insert_one_and_retrieve(self):
        with self._new_db() as db:
            db.add("cat", [1.0, 0.0, 0.0])
            labels = db.nearest([1.0, 0.0, 0.0], k=1)
            self.assertEqual(labels, ["cat"])

    def test_three_labels_nearest_neighbor(self):
        # Three orthogonal vectors; query close to one. Expect that one.
        with self._new_db() as db:
            db.add("cat", [1.0, 0.0, 0.0])
            db.add("dog", [0.0, 1.0, 0.0])
            db.add("bird", [0.0, 0.0, 1.0])
            # Query closest to "dog".
            labels = db.nearest([0.1, 0.95, 0.05], k=1)
            self.assertEqual(labels, ["dog"])

    def test_top_k(self):
        with self._new_db() as db:
            db.add("a", [1.0, 0.0])
            db.add("b", [0.95, 0.05])
            db.add("c", [-1.0, 0.0])
            labels = db.nearest([1.0, 0.0], k=2)
            # Top-2 should both be near (1, 0); "c" is the antipode.
            self.assertEqual(set(labels), {"a", "b"})


if __name__ == "__main__":
    unittest.main()
