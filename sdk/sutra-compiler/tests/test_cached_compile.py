"""Tests for ``sutra_compiler.compile_su`` (the disk-cached codegen helper).

The helper memoizes the output of ``codegen_pytorch.translate_module`` on
disk, keyed by SHA-256 of (.su content + codegen source + lowering
kwargs). On a cache hit it skips codegen entirely; on a cache miss it
runs codegen, atomic-writes the result, and returns the compiled module.

We exercise:

1. **Cache miss writes the file, cache hit skips codegen.** The proof:
   monkey-patch ``codegen_pytorch.translate_module`` to count calls.
   First compile_su() -> 1 call; second compile_su() with same args
   -> still 1 call; cache file exists between them.
2. **Editing the .su invalidates the cache.** Hash changes -> different
   filename -> miss -> codegen runs again.
3. **Changing kwargs invalidates the cache.** Same .su, different
   ``runtime_dtype`` -> different cache filename, miss, codegen runs.
4. **The returned module actually runs.** ``mod.<fn_name>(...)`` works
   and is independent across calls (fresh ``_VSA`` per call).
5. **Atomic write semantics.** Direct check: after compile_su(), only
   the named cache file exists in the cache dir; no leftover ``.tmp``.
"""
from __future__ import annotations

import pathlib
import tempfile
import textwrap
import unittest

def _rv(_vsa, _vec):
    # Host-side terminal-boundary read of a number-vector's real axis
    # (the `real()` runtime method was removed — no scalar accessor). This
    # is the sanctioned external verification read, done by direct indexing.
    return float(_vec[_vsa.semantic_dim + _vsa.AXIS_REAL])

# torch is required to exec the emitted Python (the _TorchVSA runtime).
# If torch isn't available the integration tests are skipped; the
# cache-key tests still run since they only touch translate_module.
try:
    import torch  # noqa: F401
    _HAS_TORCH = True
except ImportError:
    _HAS_TORCH = False


# A tiny .su that exercises real codegen but compiles quickly.
TINY_SU = textwrap.dedent("""\
    // Smallest .su that does meaningful codegen: one function, one op.
    function vector add_one(scalar x) {
        return make_real(x + 1.0);
    }
""")


class TestCompileSuCacheBehavior(unittest.TestCase):
    """Cache miss runs codegen; cache hit skips it."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.src_path = pathlib.Path(self.tmp.name) / "tiny.su"
        self.src_path.write_text(TINY_SU, encoding="utf-8")

    @unittest.skipUnless(_HAS_TORCH, "compile_su exec needs torch")
    def test_second_call_hits_cache_skipping_codegen(self):
        """Two compiles of the same .su run translate_module exactly once."""
        from sutra_compiler import compile_su
        from sutra_compiler import codegen_pytorch

        calls = []
        original = codegen_pytorch.translate_module

        def counting(*args, **kwargs):
            calls.append(1)
            return original(*args, **kwargs)

        codegen_pytorch.translate_module = counting
        try:
            mod1 = compile_su(
                self.src_path, llm_model="nomic-embed-text", runtime_dim=768,
                verbose=False,
            )
            self.assertEqual(len(calls), 1,
                             "first compile_su should call translate_module")
            mod2 = compile_su(
                self.src_path, llm_model="nomic-embed-text", runtime_dim=768,
                verbose=False,
            )
            self.assertEqual(len(calls), 1,
                             "second compile_su should hit the disk cache, "
                             "NOT call translate_module again")
            # Cache file actually landed and is the only one of its kind.
            caches = list(pathlib.Path(self.tmp.name).glob(".tiny.compiled-*.py"))
            self.assertEqual(len(caches), 1,
                             f"expected 1 cache file, found {caches}")
            # Both modules are usable and independent.
            self.assertIsNot(mod1, mod2)
        finally:
            codegen_pytorch.translate_module = original

    @unittest.skipUnless(_HAS_TORCH, "compile_su exec needs torch")
    def test_editing_su_invalidates_cache(self):
        """Changing .su content -> different hash -> codegen runs again."""
        from sutra_compiler import compile_su
        from sutra_compiler import codegen_pytorch

        calls = []
        original = codegen_pytorch.translate_module

        def counting(*args, **kwargs):
            calls.append(1)
            return original(*args, **kwargs)

        codegen_pytorch.translate_module = counting
        try:
            compile_su(self.src_path, llm_model="nomic-embed-text",
                       runtime_dim=768, verbose=False)
            self.assertEqual(len(calls), 1)

            # Edit the .su: add a second function. New hash, new cache file,
            # new codegen call.
            self.src_path.write_text(
                TINY_SU + "function vector add_two(scalar x) "
                          "{ return make_real(x + 2.0); }\n",
                encoding="utf-8",
            )
            compile_su(self.src_path, llm_model="nomic-embed-text",
                       runtime_dim=768, verbose=False)
            self.assertEqual(len(calls), 2,
                             "editing the .su should force a fresh codegen")
            caches = list(pathlib.Path(self.tmp.name).glob(".tiny.compiled-*.py"))
            self.assertEqual(len(caches), 2,
                             f"two distinct .su contents -> two cache files, "
                             f"got {caches}")
        finally:
            codegen_pytorch.translate_module = original

    @unittest.skipUnless(_HAS_TORCH, "compile_su exec needs torch")
    def test_changing_kwargs_invalidates_cache(self):
        """Same .su, different runtime_dtype -> different cache file."""
        from sutra_compiler import compile_su
        from sutra_compiler import codegen_pytorch

        calls = []
        original = codegen_pytorch.translate_module

        def counting(*args, **kwargs):
            calls.append(1)
            return original(*args, **kwargs)

        codegen_pytorch.translate_module = counting
        try:
            compile_su(self.src_path, llm_model="nomic-embed-text",
                       runtime_dim=768, runtime_dtype="float32", verbose=False)
            self.assertEqual(len(calls), 1)
            compile_su(self.src_path, llm_model="nomic-embed-text",
                       runtime_dim=768, runtime_dtype="float64", verbose=False)
            self.assertEqual(len(calls), 2,
                             "different runtime_dtype -> different hash -> "
                             "codegen should run again")
            caches = list(pathlib.Path(self.tmp.name).glob(".tiny.compiled-*.py"))
            self.assertEqual(len(caches), 2,
                             f"two dtypes -> two cache files, got {caches}")
        finally:
            codegen_pytorch.translate_module = original

    @unittest.skipUnless(_HAS_TORCH, "compile_su exec needs torch")
    def test_returned_module_actually_runs(self):
        """End-to-end: the compiled module's function runs on the substrate."""
        from sutra_compiler import compile_su
        mod = compile_su(
            self.src_path, llm_model="nomic-embed-text", runtime_dim=768,
            verbose=False,
        )
        # add_one(3) -> 4, via make_real -> real-axis vector
        vsa = mod._VSA
        out = mod.add_one(3.0)
        decoded = float(_rv(vsa, out))
        self.assertAlmostEqual(decoded, 4.0, places=6,
                               msg=f"add_one(3) decoded as {decoded}, expected ~4.0")

    @unittest.skipUnless(_HAS_TORCH, "compile_su exec needs torch")
    def test_no_leftover_tmp_files(self):
        """After a successful compile, no .tmp files survive in cache_dir."""
        from sutra_compiler import compile_su
        compile_su(self.src_path, llm_model="nomic-embed-text",
                   runtime_dim=768, verbose=False)
        tmp_files = list(pathlib.Path(self.tmp.name).glob("*.tmp"))
        self.assertEqual(tmp_files, [],
                         f"leftover tmp files after compile: {tmp_files}")


class TestCompileSuParseErrorPath(unittest.TestCase):
    """Parse failures surface as RuntimeError, not as a broken cache."""

    def test_parse_error_does_not_write_cache(self):
        from sutra_compiler import compile_su
        with tempfile.TemporaryDirectory() as tmp:
            src = pathlib.Path(tmp) / "bad.su"
            src.write_text("function vector { return make_real(1.0); }\n",
                           encoding="utf-8")  # missing function name
            with self.assertRaises(RuntimeError):
                compile_su(src, llm_model="nomic-embed-text",
                           runtime_dim=768, verbose=False)
            caches = list(pathlib.Path(tmp).glob(".bad.compiled-*.py"))
            self.assertEqual(caches, [],
                             "parse error should NOT have written a cache file")


class TestCompileSuMissingFile(unittest.TestCase):
    def test_missing_file_raises_filenotfound(self):
        from sutra_compiler import compile_su
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                compile_su(pathlib.Path(tmp) / "nope.su",
                           llm_model="nomic-embed-text", runtime_dim=768,
                           verbose=False)


if __name__ == "__main__":
    unittest.main()
