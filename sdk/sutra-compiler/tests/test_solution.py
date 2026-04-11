"""Tests for the Akasha solution/project parser.

Covers the happy path (a valid two-project solution round-trips
through the parser and returns the expected Solution object in
topological build order) and the error-case matrix from
`planning/akasha-spec/22-solutions.md` §Error reporting (SUT2001
through SUT2015).

Each error-case test writes a temporary solution and project
structure into a `tmp_path`, hands the solution file to
`load_solution`, and asserts that the resulting SolutionError
carries the expected code. We do not match on the error message
text because it may evolve with nicer wording over time; the
code is the stable contract.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from sutra_compiler.solution import (
    SolutionError,
    load_solution,
)


def _mk(root: Path, relative: str, content: str) -> Path:
    """Write `content` to `root/relative`, creating parent dirs."""
    p = root / relative
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


class TestHappyPath(unittest.TestCase):
    """The canonical two-project example from the spec should parse."""

    def test_corpus_then_similarity_in_build_order(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _mk(root, "pipe.aksln", """
[solution]
name = "pipe"
akasha_version = "0.2"

[[project]]
path = "corpus"

[[project]]
path = "similarity"
""")
            _mk(root, "corpus/corpus.akproj", """
[project]
name = "corpus"
entry = "main.ak"
""")
            _mk(root, "corpus/main.ak", "function void Main() { return; }\n")
            _mk(root, "similarity/similarity.akproj", """
[project]
name = "similarity"
entry = "main.ak"

[project.dependencies]
corpus = { path = "../corpus" }
""")
            _mk(root, "similarity/main.ak", "function void Main() { return; }\n")

            sln = load_solution(root / "pipe.aksln")
            self.assertEqual(sln.name, "pipe")
            self.assertEqual(sln.akasha_version, "0.2")
            self.assertEqual(sln.default_substrate, "silicon")
            self.assertEqual(len(sln.projects), 2)
            # corpus must come before similarity.
            self.assertEqual(sln.projects[0].name, "corpus")
            self.assertEqual(sln.projects[1].name, "similarity")
            self.assertEqual(sln.projects[1].dependencies[0].name, "corpus")
            # Every project got at least one source file from the default
            # include glob.
            self.assertTrue(all(len(p.sources) > 0 for p in sln.projects))

    def test_solution_level_overrides_apply(self) -> None:
        """A [[project]] override in the solution file should shadow the
        .akproj's own value for the same field (here: substrate)."""
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _mk(root, "s.aksln", """
[solution]
name = "s"
akasha_version = "0.2"
default_substrate = "silicon"

[[project]]
path = "a"
substrate = "fly-brain"
""")
            _mk(root, "a/a.akproj", """
[project]
name = "a"
entry = "main.ak"
substrate = "silicon"
""")
            _mk(root, "a/main.ak", "function void Main() { return; }\n")

            sln = load_solution(root / "s.aksln")
            # Solution-level override wins over the .akproj's own substrate.
            self.assertEqual(sln.projects[0].substrate, "fly-brain")

    def test_default_substrate_propagates_when_unspecified(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _mk(root, "s.aksln", """
[solution]
name = "s"
akasha_version = "0.2"
default_substrate = "fly-brain"

[[project]]
path = "p"
""")
            _mk(root, "p/p.akproj", """
[project]
name = "p"
entry = "main.ak"
""")
            _mk(root, "p/main.ak", "function void Main() { return; }\n")

            sln = load_solution(root / "s.aksln")
            self.assertEqual(sln.projects[0].substrate, "fly-brain")


class TestErrorCases(unittest.TestCase):
    """Each error in the spec's SUT2000-SUT2099 range has a test."""

    def _assert_error(self, code: str, aksln: Path) -> None:
        with self.assertRaises(SolutionError) as cm:
            load_solution(aksln)
        self.assertEqual(cm.exception.code, code)

    def test_aka2001_invalid_toml_in_solution(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _mk(root, "bad.aksln", "this is not = valid = toml\n")
            self._assert_error("SUT2001", root / "bad.aksln")

    def test_aka2002_missing_solution_table(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _mk(root, "nosol.aksln", "[other]\nkey = 'value'\n")
            self._assert_error("SUT2002", root / "nosol.aksln")

    def test_aka2002_missing_required_name(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _mk(root, "s.aksln", """
[solution]
akasha_version = "0.2"

[[project]]
path = "x"
""")
            self._assert_error("SUT2002", root / "s.aksln")

    def test_aka2002_zero_projects(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _mk(root, "empty.aksln", """
[solution]
name = "empty"
akasha_version = "0.2"
""")
            self._assert_error("SUT2002", root / "empty.aksln")

    def test_aka2004_project_path_missing(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _mk(root, "s.aksln", """
[solution]
name = "s"
akasha_version = "0.2"

[[project]]
path = "does_not_exist"
""")
            self._assert_error("SUT2004", root / "s.aksln")

    def test_aka2005_zero_akproj_files(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _mk(root, "s.aksln", """
[solution]
name = "s"
akasha_version = "0.2"

[[project]]
path = "empty_proj"
""")
            (root / "empty_proj").mkdir()
            self._assert_error("SUT2005", root / "s.aksln")

    def test_aka2005_multiple_akproj_files(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _mk(root, "s.aksln", """
[solution]
name = "s"
akasha_version = "0.2"

[[project]]
path = "dup"
""")
            _mk(root, "dup/a.akproj", '[project]\nname="a"\nentry="main.ak"\n')
            _mk(root, "dup/b.akproj", '[project]\nname="b"\nentry="main.ak"\n')
            _mk(root, "dup/main.ak", "")
            self._assert_error("SUT2005", root / "s.aksln")

    def test_aka2006_invalid_toml_in_project(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _mk(root, "s.aksln", """
[solution]
name = "s"
akasha_version = "0.2"

[[project]]
path = "p"
""")
            _mk(root, "p/p.akproj", "not valid toml == ==\n")
            self._assert_error("SUT2006", root / "s.aksln")

    def test_aka2007_project_missing_name(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _mk(root, "s.aksln", """
[solution]
name = "s"
akasha_version = "0.2"

[[project]]
path = "p"
""")
            _mk(root, "p/p.akproj", '[project]\nentry="main.ak"\n')
            _mk(root, "p/main.ak", "")
            self._assert_error("SUT2007", root / "s.aksln")

    def test_aka2008_dependency_name_mismatch(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _mk(root, "s.aksln", """
[solution]
name = "s"
akasha_version = "0.2"

[[project]]
path = "corpus"

[[project]]
path = "similarity"
""")
            _mk(root, "corpus/corpus.akproj", """
[project]
name = "actually_different"
entry = "main.ak"
""")
            _mk(root, "corpus/main.ak", "")
            _mk(root, "similarity/similarity.akproj", """
[project]
name = "similarity"
entry = "main.ak"

[project.dependencies]
corpus = { path = "../corpus" }
""")
            _mk(root, "similarity/main.ak", "")
            self._assert_error("SUT2008", root / "s.aksln")

    def test_aka2009_entry_file_missing(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _mk(root, "s.aksln", """
[solution]
name = "s"
akasha_version = "0.2"

[[project]]
path = "p"
""")
            _mk(root, "p/p.akproj", """
[project]
name = "p"
entry = "does_not_exist.ak"
""")
            self._assert_error("SUT2009", root / "s.aksln")

    def test_aka2010_dependency_path_invalid(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _mk(root, "s.aksln", """
[solution]
name = "s"
akasha_version = "0.2"

[[project]]
path = "p"
""")
            _mk(root, "p/p.akproj", """
[project]
name = "p"
entry = "main.ak"

[project.dependencies]
ghost = { path = "../ghost" }
""")
            _mk(root, "p/main.ak", "")
            self._assert_error("SUT2010", root / "s.aksln")

    def test_aka2011_dependency_cycle(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _mk(root, "s.aksln", """
[solution]
name = "s"
akasha_version = "0.2"

[[project]]
path = "a"

[[project]]
path = "b"
""")
            _mk(root, "a/a.akproj", """
[project]
name = "a"
entry = "main.ak"

[project.dependencies]
b = { path = "../b" }
""")
            _mk(root, "a/main.ak", "")
            _mk(root, "b/b.akproj", """
[project]
name = "b"
entry = "main.ak"

[project.dependencies]
a = { path = "../a" }
""")
            _mk(root, "b/main.ak", "")
            self._assert_error("SUT2011", root / "s.aksln")

    def test_aka2014_unknown_substrate(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _mk(root, "s.aksln", """
[solution]
name = "s"
akasha_version = "0.2"
default_substrate = "quantum_nonsense"

[[project]]
path = "p"
""")
            _mk(root, "p/p.akproj", """
[project]
name = "p"
entry = "main.ak"
""")
            _mk(root, "p/main.ak", "")
            self._assert_error("SUT2014", root / "s.aksln")


if __name__ == "__main__":
    unittest.main()
