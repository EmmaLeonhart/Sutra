"""Terminal surface — a command reader over the migrated substrate
utilities. Migrated from Yantra into Sutra as a KERNEL-FREE demo (Phase-3
migration, 2026-05-29).

A terminal whose output is *computed on the substrate*, not generated:
where a diffusion terminal-frame model hallucinates plausible bytes that
drift, this prints the exact bytes the substrate produced — zero drift
however long the session runs.

In Yantra this admitted echo through the kernel (Init / SutraService /
admit_from_path / producer / sink / tick loop) and lazily imported the
kernel-routed calc. Here it simply COMPOSES the two already-migrated
kernel-free demos: `_cmd_echo` calls `demos/echo`'s `echo()` (which
compiles echo.su via compile_su and round-trips the string on the
substrate), and `_cmd_calc` uses `demos/calc`'s `Calculator` (switch.su
via compile_su, operator selected on the substrate). No kernel.

What runs where (unchanged from the design): the terminal itself —
reading a line, splitting the command name from its arguments, choosing
which utility to route to — is HOST orchestration ("deciding what is
connected to what"). The computation, and the output shown, is the
substrate's: echo decodes the substrate round-trip verbatim (never a host
re-echo); calc evaluates on switch.su and refuses anything inexact.

Requires Ollama with nomic-embed-text (echo + calc embed their axon keys
via the frozen LLM). Run: py demos/terminal/terminal.py
"""
from __future__ import annotations

import pathlib
import sys

_DEMOS = pathlib.Path(__file__).resolve().parent.parent
# Compose the two already-migrated kernel-free demos (sibling demo dirs).
for _sib in ("echo", "calc"):
    _p = str(_DEMOS / _sib)
    if _p not in sys.path:
        sys.path.insert(0, _p)

import echo_demo  # noqa: E402  (demos/echo/echo_demo.py — provides echo())


class CommandError(Exception):
    """A user-facing terminal error (unknown command, bad usage)."""


class Terminal:
    """A command reader over the migrated substrate utilities.

    Construct once, then call :meth:`run` per command line, or
    :meth:`run_script` for a whole interaction trace. Output is the
    substrate's, decoded verbatim. No kernel — composes demos/echo +
    demos/calc directly.
    """

    def __init__(self) -> None:
        # calc is lazy so an echo-only session doesn't pay calc's compile.
        self._calc = None
        self._commands = {
            "echo": self._cmd_echo,
            "calc": self._cmd_calc,
            "help": self._cmd_help,
        }

    # --- the command reader -------------------------------------------------

    def run(self, line: str) -> str:
        """Run one command line; return its output (the substrate's).

        Raises :class:`CommandError` for an unknown command or bad usage.
        """
        s = line.strip()
        if not s:
            return ""
        name, _, args = s.partition(" ")
        handler = self._commands.get(name)
        if handler is None:
            raise CommandError(f"yterm: command not found: {name}")
        return handler(args)

    def run_script(self, lines: list[str]) -> list[str]:
        """Run an interaction trace; return one output per line. Every
        output is exact, with zero drift as the trace grows."""
        return [self.run(line) for line in lines]

    # --- handlers -----------------------------------------------------------

    def _cmd_echo(self, args: str) -> str:
        """``echo <text>`` — carry text through echo.su and decode it. The
        returned value is the SUBSTRATE's decoded string (rotation
        bind/unbind round-trip), not a host re-echo of args."""
        return echo_demo.echo(args)

    def _cmd_calc(self, args: str) -> str:
        """``calc <expr>`` — evaluate expr on the calc substrate (switch.su;
        operator selected on the substrate). Exact or refused."""
        if not args.strip():
            raise CommandError("usage: calc <expression>  (e.g. calc 2 + 3 * 4 =)")
        if self._calc is None:
            from calc import Calculator  # demos/calc/calc.py
            self._calc = Calculator()
        try:
            return str(self._calc.evaluate(args))
        except (ValueError, RuntimeError) as exc:
            raise CommandError(f"calc: {exc}") from exc

    def _cmd_help(self, args: str) -> str:
        """``help`` — list the available commands."""
        names = ", ".join(sorted(self._commands))
        return f"yterm commands: {names}"


def main() -> None:  # pragma: no cover - interactive REPL
    term = Terminal()
    print(
        "Sutra terminal — output is computed on the substrate, exact every "
        "time.\nTry: `echo hello world`, `calc 2 + 3 * 4 =`, `help`  "
        "(Ctrl-D to quit)."
    )
    for line in sys.stdin:
        line = line.rstrip("\n")
        if not line.strip():
            continue
        try:
            out = term.run(line)
        except CommandError as exc:
            print(exc)
        else:
            print(out)


if __name__ == "__main__":  # pragma: no cover
    main()
