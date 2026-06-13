"""Build the Clojure tree-sitter grammar DLL this frontend loads.

No PyPI wheel exists for tree-sitter-clojure, so this script clones the
grammar (https) and compiles `parser.c` into `_grammar/clojure.dll` with MSVC;
`lower.py` loads that DLL via ctypes. Emma authorized the sogaiu source
2026-06-12 (AskUserQuestion).

    py sdk/sutra-from-clojure/build_grammar.py

Requires MSVC (Visual Studio Build Tools). The DLL is machine-local
(_grammar/ is gitignored); tests skip with a loud reason if it is missing.
"""
from __future__ import annotations

import glob
import os
import pathlib
import subprocess
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
OUT_DIR = HERE / "_grammar"
REPO_URL = "https://github.com/sogaiu/tree-sitter-clojure"

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
        clone = os.path.join(td, "ts-clojure")
        subprocess.run(["git", "clone", "--depth", "1", REPO_URL, clone], check=True)
        src = os.path.join(clone, "src")
        dll = OUT_DIR / "clojure.dll"
        cmdline = (
            f'"{vcvars}" >nul && cl /nologo /LD /O2 /I "{src}" '
            f'"{src}\\parser.c" /Fe:"{dll}" /link /EXPORT:tree_sitter_clojure'
        )
        subprocess.run(["cmd", "/c", cmdline], check=True, cwd=td)
        print(f"built {dll}")


if __name__ == "__main__":
    main()
