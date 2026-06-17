"""Runnable showcase for the Yantra CLI calculator.

``python apps/calc/demo.py`` runs a fixed session and prints a
transcript: expressions go in, EXACT answers come out — each computed
on the Sutra substrate through the kernel, not generated.

The contrast with Meta's *Neural Computers* (NCCLIGen, a DiT video
model that generates a plausible terminal *frame*, and whose own paper
lists symbolic stability as unsolved): every number here is computed,
so it is right every time, and it does not drift. Division works for
exact quotients; non-exact ones (and out-of-range products) are refused
rather than guessed — Yantra never prints a wrong answer.

This is the seed of the downloadable demo in
`planning/22-meta-demo-replication.md` Stage 4: a thing you can run.
"""
from __future__ import annotations

from calc import Calculator

# A fixed session. Every result is exact. The substrate runs in float64
# (Sutra v0.6.2), so exact integers hold to 2**53 (~9.007e15) — far past
# float32's ~2**24. `4729 * 8831` was refused under float32; here it is
# computed exactly, on the substrate, no host carries.
SESSION = [
    "5 * 10 =",
    "12 + 30 =",
    "100 - 7 =",
    "10 / 2 =",
    "2 + 3 * 4 =",
    "9 * 9 =",
    "123 + 877 =",
    "-4 * 6 =",
    "4096 * 4096 =",
    "4729 * 8831 =",
    "99999 * 99999 =",
]

# Things the calculator REFUSES rather than answer wrong — the
# "never a wrong answer" guarantee in action, now at the float64 ceiling.
REFUSED = [
    ("10 / 3", "not an exact quotient — refused rather than approximated"),
    ("99999999 * 99999999", "result past the float64-exact range (2**53), not representable"),
]


def run_demo(calc: Calculator | None = None) -> list[str]:
    """Run the fixed session; return transcript lines ``"<expr> <result>"``.

    The last line records that division is refused (no Sutra runtime
    divide op yet) — proof we never emit a guessed answer.
    """
    calc = calc or Calculator()
    lines: list[str] = []
    for expr in SESSION:
        lines.append(f"{expr} {calc.evaluate(expr)}")
    for expr, why in REFUSED:
        try:
            calc.evaluate(expr)
            lines.append(f"{expr} = <<unexpected: should be refused>>")
        except ValueError:
            lines.append(f"{expr} = (refused — {why}; never a wrong answer)")
    return lines


def main() -> None:  # pragma: no cover - interactive showcase
    print("Yantra calculator — exact math on the Sutra substrate.")
    print("(Meta's NCCLIGen would generate a plausible frame; Yantra computes.)\n")
    for line in run_demo():
        print("  " + line)


if __name__ == "__main__":  # pragma: no cover
    main()
