"""Runnable showcase for the Yantra terminal surface.

``python apps/terminal/demo.py`` runs a fixed interaction trace and
prints the transcript: commands go in, EXACT output comes out — each
line *computed* on the Sutra substrate through the kernel, not generated.

The contrast with Meta's *Neural Computers* (NCCLIGen, a DiT video model
that *generates* plausible terminal frames, and whose own paper lists
symbolic stability as unsolved): every symbol here is computed, so it is
right every time and does not drift, however long the trace runs. Same
terminal surface, opposite engineering — and the wedge goes in exactly
where their paper concedes weakness.

The seed of the downloadable demo in planning/22 Stage 4: a thing you
can run and watch stay exact.
"""
from __future__ import annotations

from terminal import Terminal

# A fixed interaction trace. echo carries text bit-exact through echo.su;
# calc computes arithmetic on switch.su (operator selected on the
# substrate, float64 so exact integers reach 2**53). Every output below
# is the substrate's, exact by construction.
SESSION = [
    "echo booting yantra terminal",
    "calc 2 + 3 * 4 =",
    "echo symbols are computed, not generated",
    "calc (10 - 2) * 5 =",
    "calc 4729 * 8831 =",          # exact in float64 (refused under float32)
    "echo 1234567890",
    "help",
    "echo no drift, however long the session",
]


def run_demo(term: Terminal | None = None) -> list[str]:
    """Run the fixed trace; return transcript lines ``"<command> -> <output>"``."""
    term = term or Terminal()
    return [f"{line}  ->  {term.run(line)}" for line in SESSION]


def main() -> None:  # pragma: no cover - interactive showcase
    print("Yantra terminal — output computed on the Sutra substrate, exact.")
    print("(Meta's NCCLIGen would generate a plausible frame; Yantra runs it.)\n")
    for line in run_demo():
        print("  " + line)


if __name__ == "__main__":  # pragma: no cover
    main()
