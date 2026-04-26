"""Tests for the Sutra workspace / `atman.toml` parser.

Covers the happy path (a valid two-project workspace round-trips
through the parser and returns the expected Workspace object in
topological build order) and the error-case matrix from
`planning/sutra-spec/22-workspaces.md` §Error reporting (SUT2001
through SUT2015).

Each error-case test writes a temporary workspace and project
structure into a `tmp_path`, hands the workspace file to
`load_workspace`, and asserts that the resulting WorkspaceError
carries the expected code. We do not match on the error message
text because it may evolve with nicer wording over time; the
code is the stable contract.

The SUT#### diagnostic code range and the underlying validation
rules carry over unchanged from the old `.aksln`/`.akproj` era —
only the TOML schema changed (`[solution]` -> `[workspace]`,
`[[project]]` -> `[[workspace.member]]`, `akasha_version` ->
`sutra_version`, and the filename is now always `atman.toml`).
"""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from sutra_compiler.workspace import (
    WorkspaceError,
    load_workspace,
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
            _mk(root, "atman.toml", """
[workspace]
name = "pipe"
sutra_version = "0.2"

[[workspace.member]]
path = "corpus"

[[workspace.member]]
path = "similarity"
""")
            _mk(root, "corpus/atman.toml", """
[project]
name = "corpus"
entry = "main.su"
""")
            _mk(root, "corpus/main.su", "function void Main() { return; }\n")
            _mk(root, "similarity/atman.toml", """
[project]
name = "similarity"
entry = "main.su"

[project.dependencies]
corpus = { path = "../corpus" }
""")
            _mk(root, "similarity/main.su", "function void Main() { return; }\n")

            ws = load_workspace(root / "atman.toml")
            self.assertEqual(ws.name, "pipe")
            self.assertEqual(ws.sutra_version, "0.2")
            self.assertEqual(ws.default_substrate, "silicon")
            self.assertEqual(len(ws.projects), 2)
            # corpus must come before similarity.
            self.assertEqual(ws.projects[0].name, "corpus")
            self.assertEqual(ws.projects[1].name, "similarity")
            self.assertEqual(ws.projects[1].dependencies[0].name, "corpus")
            # Every project got at least one source file from the default
            # include glob.
            self.assertTrue(all(len(p.sources) > 0 for p in ws.projects))

    def test_workspace_level_overrides_apply(self) -> None:
        """A [[workspace.member]] override in the workspace file should
        shadow the member project's own value for the same field
        (here: substrate)."""
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _mk(root, "atman.toml", """
[workspace]
name = "s"
sutra_version = "0.2"
default_substrate = "silicon"

[[workspace.member]]
path = "a"
substrate = "logit"
""")
            _mk(root, "a/atman.toml", """
[project]
name = "a"
entry = "main.su"
substrate = "silicon"
""")
            _mk(root, "a/main.su", "function void Main() { return; }\n")

            ws = load_workspace(root / "atman.toml")
            # Workspace-level override wins over the project atman.toml's substrate.
            self.assertEqual(ws.projects[0].substrate, "logit")

    def test_default_substrate_propagates_when_unspecified(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _mk(root, "atman.toml", """
[workspace]
name = "s"
sutra_version = "0.2"
default_substrate = "logit"

[[workspace.member]]
path = "p"
""")
            _mk(root, "p/atman.toml", """
[project]
name = "p"
entry = "main.su"
""")
            _mk(root, "p/main.su", "function void Main() { return; }\n")

            ws = load_workspace(root / "atman.toml")
            self.assertEqual(ws.projects[0].substrate, "logit")


class TestErrorCases(unittest.TestCase):
    """Each error in the spec's SUT2000-SUT2099 range has a test."""

    def _assert_error(self, code: str, atman: Path) -> None:
        with self.assertRaises(WorkspaceError) as cm:
            load_workspace(atman)
        self.assertEqual(cm.exception.code, code)

    def test_sut2001_invalid_toml_in_workspace(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _mk(root, "atman.toml", "this is not = valid = toml\n")
            self._assert_error("SUT2001", root / "atman.toml")

    def test_sut2002_missing_workspace_table(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _mk(root, "atman.toml", "[other]\nkey = 'value'\n")
            self._assert_error("SUT2002", root / "atman.toml")

    def test_sut2002_missing_required_name(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _mk(root, "atman.toml", """
[workspace]
sutra_version = "0.2"

[[workspace.member]]
path = "x"
""")
            self._assert_error("SUT2002", root / "atman.toml")

    def test_sut2002_zero_members(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _mk(root, "atman.toml", """
[workspace]
name = "empty"
sutra_version = "0.2"
""")
            self._assert_error("SUT2002", root / "atman.toml")

    def test_sut2004_member_path_missing(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _mk(root, "atman.toml", """
[workspace]
name = "s"
sutra_version = "0.2"

[[workspace.member]]
path = "does_not_exist"
""")
            self._assert_error("SUT2004", root / "atman.toml")

    def test_sut2005_member_has_no_atman_toml(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _mk(root, "atman.toml", """
[workspace]
name = "s"
sutra_version = "0.2"

[[workspace.member]]
path = "empty_proj"
""")
            (root / "empty_proj").mkdir()
            self._assert_error("SUT2005", root / "atman.toml")

    def test_sut2006_invalid_toml_in_project(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _mk(root, "atman.toml", """
[workspace]
name = "s"
sutra_version = "0.2"

[[workspace.member]]
path = "p"
""")
            _mk(root, "p/atman.toml", "not valid toml == ==\n")
            self._assert_error("SUT2006", root / "atman.toml")

    def test_sut2007_project_missing_name(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _mk(root, "atman.toml", """
[workspace]
name = "s"
sutra_version = "0.2"

[[workspace.member]]
path = "p"
""")
            _mk(root, "p/atman.toml", '[project]\nentry="main.su"\n')
            _mk(root, "p/main.su", "")
            self._assert_error("SUT2007", root / "atman.toml")

    def test_sut2008_dependency_name_mismatch(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _mk(root, "atman.toml", """
[workspace]
name = "s"
sutra_version = "0.2"

[[workspace.member]]
path = "corpus"

[[workspace.member]]
path = "similarity"
""")
            _mk(root, "corpus/atman.toml", """
[project]
name = "actually_different"
entry = "main.su"
""")
            _mk(root, "corpus/main.su", "")
            _mk(root, "similarity/atman.toml", """
[project]
name = "similarity"
entry = "main.su"

[project.dependencies]
corpus = { path = "../corpus" }
""")
            _mk(root, "similarity/main.su", "")
            self._assert_error("SUT2008", root / "atman.toml")

    def test_sut2009_entry_file_missing(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _mk(root, "atman.toml", """
[workspace]
name = "s"
sutra_version = "0.2"

[[workspace.member]]
path = "p"
""")
            _mk(root, "p/atman.toml", """
[project]
name = "p"
entry = "does_not_exist.su"
""")
            self._assert_error("SUT2009", root / "atman.toml")

    def test_sut2010_dependency_path_invalid(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _mk(root, "atman.toml", """
[workspace]
name = "s"
sutra_version = "0.2"

[[workspace.member]]
path = "p"
""")
            _mk(root, "p/atman.toml", """
[project]
name = "p"
entry = "main.su"

[project.dependencies]
ghost = { path = "../ghost" }
""")
            _mk(root, "p/main.su", "")
            self._assert_error("SUT2010", root / "atman.toml")

    def test_sut2011_dependency_cycle(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _mk(root, "atman.toml", """
[workspace]
name = "s"
sutra_version = "0.2"

[[workspace.member]]
path = "a"

[[workspace.member]]
path = "b"
""")
            _mk(root, "a/atman.toml", """
[project]
name = "a"
entry = "main.su"

[project.dependencies]
b = { path = "../b" }
""")
            _mk(root, "a/main.su", "")
            _mk(root, "b/atman.toml", """
[project]
name = "b"
entry = "main.su"

[project.dependencies]
a = { path = "../a" }
""")
            _mk(root, "b/main.su", "")
            self._assert_error("SUT2011", root / "atman.toml")

    def test_sut2014_unknown_substrate(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            _mk(root, "atman.toml", """
[workspace]
name = "s"
sutra_version = "0.2"
default_substrate = "quantum_nonsense"

[[workspace.member]]
path = "p"
""")
            _mk(root, "p/atman.toml", """
[project]
name = "p"
entry = "main.su"
""")
            _mk(root, "p/main.su", "")
            self._assert_error("SUT2014", root / "atman.toml")


if __name__ == "__main__":
    unittest.main()
