"""Q# — the most FP-native quantum language — via the `qsharp` Python package (Q3).

Q# leans into functional idioms: strong typing, immutability of quantum state
mid-circuit, operations as first-class. It runs here on the built-in sparse
simulator with no quantum hardware. Measured 2026-06-18: Bell + 3-qubit GHZ both
give the correct entangled distribution.

Install: python -m pip install qsharp   (Azure QDK; dotnet 9 present on this box).
NOTE: the `qsharp` pip package now warns it is superseded by `qdk` — `import qsharp`
still works; migrate to `qdk` if this breaks. Silq (the other FP-native quantum
language Emma mentioned) is NOT pip-installable — it ships as a standalone compiler
binary / VS Code extension (D-language toolchain), so it was not exercised here.

Run: python experiments/quantum/qsharp_fp_native.py
"""
from __future__ import annotations

from collections import Counter

import qsharp

qsharp.eval("""
operation Bell() : (Result, Result) {
    use (q0, q1) = (Qubit(), Qubit());
    H(q0);                        // superposition
    CNOT(q0, q1);                 // entangle
    let result = (M(q0), M(q1));  // measure — the irreversible side effect
    ResetAll([q0, q1]);
    return result;
}

operation GHZ() : Result[] {
    use qs = Qubit[3];
    H(qs[0]);
    CNOT(qs[0], qs[1]);
    CNOT(qs[1], qs[2]);           // |000> + |111>
    let result = MeasureEachZ(qs);
    ResetAll(qs);
    return result;
}
""")


def main():
    bell = Counter(str(s) for s in qsharp.run("Bell()", shots=2000))
    print("Q# Bell counts:", dict(bell))
    ghz = Counter(str(s) for s in qsharp.run("GHZ()", shots=2000))
    print("Q# GHZ counts:", dict(ghz))


if __name__ == "__main__":
    main()
