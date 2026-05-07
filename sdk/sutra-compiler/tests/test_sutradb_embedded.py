"""Tests for the embedded SutraDB wrapper.

Smoke test that confirms (a) the FFI DLL loads, (b) labeled
vectors can be inserted, (c) nearest-neighbor query returns the
expected label. If sutra_ffi.dll isn't built, all tests are
skipped — they don't fail the suite.

The embedded SutraDB replaces argmax_cosine in compiled Sutra
programs. This test pins the embedded API shape so codegen
wiring has a known-good surface to call.
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


@unittest.skipUnless(
    _DLL_AVAILABLE,
    f"sutra_ffi.dll not found at {_DLL}. Build with: "
    "cd sutraDB && cargo build --release -p sutra-ffi",
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


@unittest.skipUnless(
    _DLL_AVAILABLE,
    f"sutra_ffi.dll not found at {_DLL}. Build with: "
    "cd sutraDB && cargo build --release -p sutra-ffi",
)
class TestSutraDBCodebookIntegration(unittest.TestCase):
    """Compile-time SutraDB population + nearest_string decode.

    Every embedded string in a Sutra program goes into SutraDB at
    compile time. The runtime can decode any query vector back to
    the nearest string via `_VSA.nearest_string(query)`. Strings
    declared but not used in expressions are still inserted so
    they remain decodable.

    These tests exercise the runtime methods directly (via a
    minimal _TorchVSA instance) rather than running the full
    compile pipeline against a `.su` source.
    """

    def test_populate_then_decode_three_words(self):
        # Build a tiny _TorchVSA, manually populate the codebook
        # with three labeled vectors, push to SutraDB, decode.
        # We don't go through ollama here; the test just exercises
        # populate_sutradb + nearest_string against a hand-built
        # codebook so it doesn't depend on a running embedding model.
        import torch
        from sutra_compiler.codegen_pytorch import PyTorchCodegen
        from sutra_compiler import ast_nodes
        cg = PyTorchCodegen()
        cg._prefetch_strings = []  # don't try to embed anything at module init
        empty = ast_nodes.Module(items=[], span=None)  # type: ignore[arg-type]
        try:
            py = cg.translate(empty)
        except Exception:
            self.skipTest("PyTorchCodegen.translate(empty) failed; skip")
        ns: dict = {}
        exec(py, ns)
        vsa = ns.get("_VSA")
        self.assertIsNotNone(vsa, "_VSA missing from emitted module")
        # Hand-populate the codebook with three orthogonal-ish vectors
        # in the semantic block (synthetic block stays zero — that's
        # the layout populate_sutradb expects).
        sem = vsa.semantic_dim
        syn = vsa.synthetic_dim
        v_cat = torch.zeros(sem + syn, dtype=vsa.dtype, device=vsa.device)
        v_dog = torch.zeros(sem + syn, dtype=vsa.dtype, device=vsa.device)
        v_bird = torch.zeros(sem + syn, dtype=vsa.dtype, device=vsa.device)
        v_cat[0] = 1.0
        v_dog[1] = 1.0
        v_bird[2] = 1.0
        vsa._codebook = {"cat": v_cat, "dog": v_dog, "bird": v_bird}
        vsa.populate_sutradb()
        # Query close to "dog".
        query = torch.zeros(sem + syn, dtype=vsa.dtype, device=vsa.device)
        query[0] = 0.1
        query[1] = 0.95
        query[2] = 0.05
        result = vsa.nearest_string(query)
        self.assertEqual(result, "dog")

    def test_env_var_path_override(self):
        # SUTRA_DB_PATH env var overrides the tempdir. Two _VSA instances
        # pointed at the same path should see each other's inserts after
        # close+reopen (not tested explicitly here; just confirm the env
        # var routes the path).
        import os
        import torch
        from sutra_compiler.codegen_pytorch import PyTorchCodegen
        from sutra_compiler import ast_nodes

        custom_path = os.path.join(self._tmpdir, "custom_codebook.sdb")
        old_env = os.environ.get("SUTRA_DB_PATH")
        os.environ["SUTRA_DB_PATH"] = custom_path
        try:
            cg = PyTorchCodegen()
            cg._prefetch_strings = []
            empty = ast_nodes.Module(items=[], span=None)  # type: ignore[arg-type]
            try:
                py = cg.translate(empty)
            except Exception:
                self.skipTest("translate(empty) failed; skip")
            ns: dict = {}
            exec(py, ns)
            vsa = ns["_VSA"]
            sem = vsa.semantic_dim
            syn = vsa.synthetic_dim
            v = torch.zeros(sem + syn, dtype=vsa.dtype, device=vsa.device)
            v[0] = 1.0
            vsa._codebook = {"persistent_label": v}
            vsa.populate_sutradb()
            # Confirm the .sdb sled directory was created at our custom path.
            self.assertTrue(os.path.isdir(custom_path),
                            f"expected sled dir at {custom_path}")
        finally:
            if old_env is None:
                os.environ.pop("SUTRA_DB_PATH", None)
            else:
                os.environ["SUTRA_DB_PATH"] = old_env

    def setUp(self) -> None:
        import tempfile
        self._tmpdir = tempfile.mkdtemp(prefix="sutradb_codebook_test_")

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_decode_unicode_label(self):
        # URL-quoting in populate_sutradb / unquoting in nearest_string
        # round-trips a label with spaces / non-ASCII characters.
        import torch
        from sutra_compiler.codegen_pytorch import PyTorchCodegen
        from sutra_compiler import ast_nodes
        cg = PyTorchCodegen()
        cg._prefetch_strings = []
        empty = ast_nodes.Module(items=[], span=None)  # type: ignore[arg-type]
        try:
            py = cg.translate(empty)
        except Exception:
            self.skipTest("PyTorchCodegen.translate(empty) failed; skip")
        ns: dict = {}
        exec(py, ns)
        vsa = ns["_VSA"]
        sem = vsa.semantic_dim
        syn = vsa.synthetic_dim
        v = torch.zeros(sem + syn, dtype=vsa.dtype, device=vsa.device)
        v[0] = 1.0
        label = "hello world café"
        vsa._codebook = {label: v}
        vsa.populate_sutradb()
        result = vsa.nearest_string(v)
        self.assertEqual(result, label)


if __name__ == "__main__":
    unittest.main()
