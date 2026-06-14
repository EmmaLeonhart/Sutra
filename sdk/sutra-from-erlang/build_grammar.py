"""Build the Erlang tree-sitter grammar DLL this frontend loads.

No PyPI wheel exists for tree-sitter-erlang, so this script clones the grammar
(https) and compiles `parser.c` + `scanner.c` into `_grammar/erlang.dll` with
MSVC; `lower.py` loads that DLL via ctypes. Same pattern as
`sutra-from-clojure/build_grammar.py`. Emma authorized the Erlang frontend
2026-06-14 ("implement erlang right now"); the WhatsApp grammar is the
maintained reference source.

    py sdk/sutra-from-erlang/build_grammar.py

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
REPO_URL = "https://github.com/WhatsApp/tree-sitter-erlang"

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
        clone = os.path.join(td, "ts-erlang")
        subprocess.run(["git", "clone", "--depth", "1", REPO_URL, clone], check=True)
        src = os.path.join(clone, "src")
        dll = OUT_DIR / "erlang.dll"
        # Erlang's grammar ships an external scanner.c alongside parser.c — compile both.
        # Drive the build through a temp .bat: cmd.exe mangles `cmd /c "<quoted
        # path>" && ...` when the command starts with a quote (strips the outer
        # pair), breaking the spaced vcvars path. A batch file sidesteps that.
        bat = os.path.join(td, "build.bat")
        with open(bat, "w", encoding="ascii") as f:
            f.write("@echo off\n")
            f.write(f'call "{vcvars}" >nul\n')
            f.write(
                f'cl /nologo /LD /O2 /I "{src}" '
                f'"{src}\\parser.c" "{src}\\scanner.c" '
                f'/Fe:"{dll}" /link /EXPORT:tree_sitter_erlang\n'
            )
        subprocess.run(["cmd", "/c", bat], check=True, cwd=td)
        print(f"built {dll}")


if __name__ == "__main__":
    main()
