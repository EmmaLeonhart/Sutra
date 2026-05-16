"""CI gate: the substrate-leak sweep must stay clean.

`experiments/substrate_leak_sweep.py` compiles every `.su` program
under the corpus + examples and greps the emitted Python for raw
operators (`**`, `//`, ` % `, bit-shifts, bitwise `& | ^`) on lines
outside the `_VSA` runtime class. `%` slipped through for 33 days
because no corpus program used it and nothing in CI looked; this
test makes the next binary-operator leak fail at PR time instead.

Loaded by file path because `experiments/` is not an importable
package. The sweep resolves repo paths relative to its own
`__file__`, so it is CWD-independent.
"""
from __future__ import annotations

import importlib.util
import os

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_SWEEP = os.path.normpath(
    os.path.join(_HERE, "..", "..", "..", "experiments",
                 "substrate_leak_sweep.py")
)


@pytest.mark.skipif(
    not os.path.exists(_SWEEP),
    reason="substrate_leak_sweep.py not present",
)
def test_no_substrate_leaks_in_corpus():
    spec = importlib.util.spec_from_file_location(
        "substrate_leak_sweep", _SWEEP
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    rc = mod.main()
    assert rc == 0, (
        "substrate_leak_sweep found raw-operator leaks in compiled "
        ".su programs (see stdout above). A new binary-operator "
        "substrate leak landed — fix it, do not relax this gate."
    )
