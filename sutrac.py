"""Wrapper that runs the Sutra compiler CLI from the repo root.

The compiler package lives at `sdk/sutra-compiler/sutra_compiler/`
and is not pip-installed, so `python -m sutra_compiler ...` from the
repo root fails with "No module named sutra_compiler". This wrapper
inserts the sdk path into sys.path and delegates to the CLI's main().

Usage (from the repo root):

    python sutrac.py --review examples/analogy.su
    python sutrac.py --emit examples/hello_world.su
    python sutrac.py --run examples/hello_world.su
    python sutrac.py examples/            # validate everything

Long-term follow-up: add a `pyproject.toml` under `sdk/sutra-compiler/`
so `pip install -e sdk/sutra-compiler` registers `sutra_compiler` on
the Python path system-wide and `python -m sutra_compiler` works from
any cwd without this shim.
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SDK_PATH = os.path.join(HERE, "sdk", "sutra-compiler")
if SDK_PATH not in sys.path:
    sys.path.insert(0, SDK_PATH)

from sutra_compiler.__main__ import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
