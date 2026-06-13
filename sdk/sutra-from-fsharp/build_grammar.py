"""Build the F# tree-sitter grammar DLL this frontend loads.

There is no PyPI wheel for tree-sitter-fsharp, and `pip install git+…` fails on
the repo's example submodules (SSH-only URLs) and would fail anyway (the repo
ships no Python binding). So this script does the minimal real thing — clone
the grammar (https, no submodules) and compile `parser.c` + `scanner.c` into
`_grammar/fsharp.dll` with MSVC — and `lower.py` loads that DLL via ctypes.
Emma authorized the ionide source 2026-06-12 (AskUserQuestion).

    py sdk/sutra-from-fsharp/build_grammar.py

Requires MSVC (Visual Studio Build Tools). The DLL is machine-local
(_grammar/ is gitignored); tests skip with a loud reason if it is missing.
"""
from __future__ import annotations

import glob
import os
import pathlib
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
OUT_DIR = HERE / "_grammar"
REPO_URL = "https://github.com/ionide/tree-sitter-fsharp"

_VCVARS_GLOBS = [
    r"C:\Program Files\Microsoft Visual Studio\2022\*\VC\Auxiliary\Build\vcvars64.bat",
    r"C:\Program Files (x86)\Microsoft Visual Studio\2019\*\VC\Auxiliary\Build\vcvars64.bat",
]


def _find_vcvars() -> str:
    for pattern in _VCVARS_GLOBS:
        hits = glob.glob(pattern)
        if hits:
            return hits[0]
    raise SystemExit("MSVC not found (no vcvars64.bat); install VS Build Tools.")


def main() -> None:
    vcvars = _find_vcvars()
    OUT_DIR.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        clone = os.path.join(td, "ts-fsharp")
        subprocess.run(["git", "clone", "--depth", "1", REPO_URL, clone], check=True)
        src = os.path.join(clone, "fsharp", "src")
        dll = OUT_DIR / "fsharp.dll"
        cmdline = (
            f'"{vcvars}" >nul && cl /nologo /LD /O2 /I "{src}" '
            f'"{src}\\parser.c" "{src}\\scanner.c" /Fe:"{dll}" '
            f"/link /EXPORT:tree_sitter_fsharp"
        )
        subprocess.run(["cmd", "/c", cmdline], check=True, cwd=td)
        print(f"built {dll}")


if __name__ == "__main__":
    main()
