"""Tests for the stdlib loader — step 1 of the function-expansion
pipeline.

The loader walks `sutra_compiler/stdlib/*.su` and returns a symbol
table of FunctionDecl nodes. These tests assert:

  - Every expected implemented-in-Sutra function is present.
  - No duplicates across files.
  - Signatures match what the stdlib .su files declare.
  - Parse diagnostics on stdlib files are fatal (compiler-bug
    category — a broken stdlib is never a user error).

When the inliner (step 2) lands, its tests build on this table.
"""
from __future__ import annotations

import os
import tempfile
import unittest

from sutra_compiler import ast_nodes as ast
from sutra_compiler.stdlib_loader import (
    STDLIB_DIR,
    StdlibLoadError,
    load_stdlib,
    stdlib_function_names,
)


# The set of function names the stdlib currently implements in pure
# Sutra. The blocked-on-intrinsics entries (eq, gt, make_real,
# complex_mul, bind, bundle, ...) live as commented pseudo-Sutra and
# are deliberately NOT in this set — they don't appear as
# FunctionDecl nodes until their intrinsics land.
EXPECTED_IMPLEMENTED: frozenset[str] = frozenset({
    "defuzzy",
    "logical_not",
    "logical_and",
    "logical_or",
    "neq",
    "lt",
    "ge",
    "le",
    "hashmap_new",
    "hashmap_set",
    "hashmap_get",
})


class TestStdlibLoad(unittest.TestCase):
    """Exercises the real stdlib directory shipped with the compiler."""

    def test_load_returns_all_implemented_functions(self):
        table = load_stdlib()
        missing = EXPECTED_IMPLEMENTED - set(table.keys())
        self.assertFalse(
            missing,
            f"stdlib loader missed expected functions: {sorted(missing)}",
        )

    def test_loaded_entries_are_function_decls(self):
        table = load_stdlib()
        for name, decl in table.items():
            self.assertIsInstance(
                decl, ast.FunctionDecl,
                f"stdlib entry {name!r} is not a FunctionDecl",
            )
            # Bare-name keys must match decl.name. Namespaced keys
            # (`Math.log`) are also registered — their suffix after the
            # `.` must match decl.name.
            if "." in name:
                _, suffix = name.split(".", 1)
                self.assertEqual(
                    decl.name, suffix,
                    f"namespaced key {name!r} suffix vs decl.name {decl.name!r}",
                )
            else:
                self.assertEqual(
                    decl.name, name,
                    f"name mismatch: key {name!r} vs decl.name {decl.name!r}",
                )

    def test_signatures_match_expected(self):
        """Spot-check signatures for the entries we care most about.
        If the stdlib evolves, update the expected shapes here."""
        table = load_stdlib()

        # defuzzy(fuzzy v) -> fuzzy
        defuzzy = table["defuzzy"]
        self.assertEqual(defuzzy.return_type.name, "fuzzy")
        self.assertEqual(len(defuzzy.params), 1)
        self.assertEqual(defuzzy.params[0].type_ref.name, "fuzzy")

        # logical_and(fuzzy a, fuzzy b) -> fuzzy
        land = table["logical_and"]
        self.assertEqual(land.return_type.name, "fuzzy")
        self.assertEqual(len(land.params), 2)
        self.assertEqual(land.params[0].type_ref.name, "fuzzy")
        self.assertEqual(land.params[1].type_ref.name, "fuzzy")

        # neq(vector a, vector b) -> fuzzy  (lives in similarity.su)
        neq = table["neq"]
        self.assertEqual(neq.return_type.name, "fuzzy")
        self.assertEqual(neq.params[0].type_ref.name, "vector")
        self.assertEqual(neq.params[1].type_ref.name, "vector")

    def test_intrinsics_are_in_table_but_not_inlineable(self):
        """Intrinsic declarations (`intrinsic function ...;`) DO appear
        in the stdlib table — they're FunctionDecl nodes with empty
        bodies and is_intrinsic=True. The inliner skips them (no body
        to substitute); the codegen routes Call(intrinsic, ...) to
        `_VSA.<name>(...)` so the runtime implements them."""
        table = load_stdlib()
        for name in ("eq", "gt", "make_real", "make_complex",
                     "make_char", "complex_mul", "embed",
                     "zero_vector", "similarity", "make_truth"):
            self.assertIn(name, table)
            self.assertTrue(
                table[name].is_intrinsic,
                f"{name!r} should be marked is_intrinsic=True",
            )
            self.assertEqual(
                table[name].body.statements, [],
                f"{name!r} body should be an empty Block",
            )

    def test_still_unlisted_stubs(self):
        """Functions that remain commented-out pseudo-Sutra (bind,
        unbind, bundle, snap, conj, ...) are still not in the table —
        they lack either a body or an intrinsic declaration."""
        table = load_stdlib()
        for name in ("bind", "unbind", "bundle", "snap", "conj",
                     "permute", "make_random_rotation"):
            self.assertNotIn(
                name, table,
                f"{name!r} is still a commented stub, not yet declared",
            )

    def test_function_names_sorted_and_deduplicated(self):
        names = stdlib_function_names()
        self.assertEqual(names, sorted(names), "names should be sorted")
        self.assertEqual(len(names), len(set(names)), "no dupes")


class TestStdlibLoaderErrors(unittest.TestCase):
    """The loader treats stdlib diagnostics as fatal compiler bugs."""

    def test_duplicate_function_across_files_raises(self):
        # Build a synthetic stdlib where two files declare `dup_fn`.
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "a.su"), "w") as f:
                f.write("function fuzzy dup_fn(fuzzy v) { return v; }\n")
            with open(os.path.join(tmp, "b.su"), "w") as f:
                f.write("function fuzzy dup_fn(fuzzy v) { return v; }\n")
            with self.assertRaises(StdlibLoadError) as ctx:
                load_stdlib(tmp)
            self.assertIn("duplicate stdlib function 'dup_fn'", str(ctx.exception))

    def test_parse_error_in_stdlib_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "broken.su"), "w") as f:
                # Unterminated function — parser will flag.
                f.write("function fuzzy oops(fuzzy v) {\n")
            with self.assertRaises(StdlibLoadError):
                load_stdlib(tmp)

    def test_non_su_files_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            # README.md and the like should be skipped silently.
            with open(os.path.join(tmp, "README.md"), "w") as f:
                f.write("# not Sutra\n")
            with open(os.path.join(tmp, "legit.su"), "w") as f:
                f.write("function fuzzy id(fuzzy v) { return v; }\n")
            table = load_stdlib(tmp)
            self.assertEqual(sorted(table.keys()), ["id"])


if __name__ == "__main__":
    unittest.main()
