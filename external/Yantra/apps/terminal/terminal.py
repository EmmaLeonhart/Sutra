"""Yantra terminal surface — a command reader over kernel-admitted utilities.

This is **Stage 2** of the headline demo (``planning/22-meta-demo-
replication.md``): a terminal whose output is *computed*, not *generated*.
Where Meta's NCCLIGen (a DiT video model) *hallucinates* plausible
terminal frames that drift symbol-by-symbol, this terminal admits a real
utility through the kernel and prints **the exact bytes the substrate
produced** — exact by construction, zero drift however long the session
runs. Same surface as theirs, opposite engineering, and we win precisely
on the axis their own paper lists as unsolved (symbolic stability).

What runs where (the architecture, planning/01):

  - **The terminal itself is host orchestration.** Reading a line,
    splitting a command name from its arguments, and deciding which
    admitted utility to route to is the **Connectome Manager's job** —
    "deciding what is connected to what" — which is explicitly the
    CPU-side orchestrator's work, not substrate computation. (Contrast
    the calculator: *which arithmetic operation* runs is data-driven
    computation on operands, so it happens ON the substrate via
    ``switch.su``. *Which program a typed command names* is admission /
    routing — host-side by design. The two dispatches look similar but
    sit on opposite sides of the host/substrate line.)

  - **The computation runs on the substrate, and the output shown is the
    substrate's.** ``echo`` carries the typed text through a compiled
    ``echo.su`` on real tensors and we decode the result verbatim
    (``axon_item`` / ``string_to_python``) — never a host re-echo of the
    input. ``calc`` evaluates on ``switch.su`` through the kernel.

Substrate-purity note (don't overclaim): this terminal does **not** close
the calculator's known step-c gap (``planning/23``) — ``calc`` still
returns a host ``Fraction`` behind a host-oracle refuse-gate. The terminal
composes calc as-is; it neither adds nor removes that gap.

The Python here is the host stand-in for the eventual command reader (a
Rust-orchestrator unit, or the browser/GUI terminal of build-sequence
milestone 3). It is dev tooling, not the boot path.
"""
from __future__ import annotations

import pathlib
import sys

# Standalone-run convenience: put the repo root on sys.path so
# `from kernel import ...` and `from apps.calc...` resolve when this file
# is the script entry point (pytest gets this via pyproject's pythonpath).
_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from kernel import Init, Manifest, PythonService, SutraService  # noqa: E402
from kernel.router import Axon  # noqa: E402

APPS = _REPO_ROOT / "apps"
APPS_ECHO = APPS / "echo"
AXON_WIDTH = 768


class CommandError(Exception):
    """A user-facing terminal error (unknown command, bad usage)."""


class Terminal:
    """A command reader over utilities admitted through the kernel.

    Construct once (admits ``echo`` into a kernel and builds the calc
    service), then call :meth:`run` per command line, or :meth:`run_script`
    for a whole interaction trace. Output is the substrate's, decoded
    verbatim.
    """

    def __init__(self) -> None:
        self.init = Init(compute_pool=32)

        # --- echo: admitted through the kernel, runs on the substrate ---
        self._echo = SutraService(
            source_path=APPS_ECHO / "echo.su",
            output_role="R_stdout",
        )
        self.init.admit_from_path(APPS_ECHO / "echo.toml", self._echo)

        # Host producer (writes R_stdin) and sink (reads R_stdout) — the
        # orchestrator's I/O endpoints, capability-checked like any process.
        self._producer = PythonService(lambda s, ax: None)
        self.init.admit(
            Manifest(
                name="stdin_producer", axon_width=AXON_WIDTH, compute_units=1,
                read_roles=frozenset(), write_roles=frozenset({"R_stdin"}),
                source="stdin_producer.py", axon_keys=frozenset(),
            ),
            self._producer,
        )
        self._received: list[Axon] = []
        sink = PythonService(on_axon=lambda s, ax: self._received.append(ax))
        self.init.admit(
            Manifest(
                name="stdout_sink", axon_width=AXON_WIDTH, compute_units=1,
                read_roles=frozenset({"R_stdout"}), write_roles=frozenset(),
                source="stdout_sink.py", axon_keys=frozenset({"stdout_text"}),
            ),
            sink,
        )

        # --- calc: composed as-is (its own kernel + documented step-c gap) ---
        # Lazy so a session that only runs `echo` doesn't pay calc's compile.
        self._calc = None

        # Command name -> handler. A plain dict dispatch (Rust-portable);
        # adding a utility is a one-line registration. NOT a substrate
        # decision — see the module docstring.
        self._commands = {
            "echo": self._cmd_echo,
            "calc": self._cmd_calc,
            "help": self._cmd_help,
        }

    # --- the command reader -------------------------------------------------

    def run(self, line: str) -> str:
        """Run one command line; return its output (the substrate's).

        Raises :class:`CommandError` for an unknown command or bad usage —
        the caller (the REPL) prints it like a shell error.
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
        """Run an interaction trace; return one output per line.

        This is the measurable form for the headline demo: a scripted
        sequence of N commands where *every* output is exact and there is
        **zero drift** as N grows (planning/22 § "Making it measurable").
        """
        return [self.run(line) for line in lines]

    # --- handlers -----------------------------------------------------------

    def _cmd_echo(self, args: str) -> str:
        """``echo <text>`` — carry ``text`` through echo.su and decode it.

        The string round-trips on the substrate (rotation-bind into the
        axon, kernel route under capability check, ``echo.su`` re-binds it,
        we unbind + decode). The returned value is the SUBSTRATE's decoded
        string, not a host re-echo of ``args``.
        """
        vsa = self._echo._compiled_module._VSA  # noqa: SLF001 — host monitoring
        self._received.clear()
        inp = vsa.axon_add(vsa.zero_vector(), "stdin_text", vsa.make_string(args))
        self._producer.emit("R_stdin", inp, keys=frozenset({"stdin_text"}))
        self.init.tick()  # fire echo (drains R_stdin)
        self.init.tick()  # fire the sink (drains R_stdout)
        if len(self._received) != 1:
            raise RuntimeError(
                f"echo delivered {len(self._received)} axons (expected 1)"
            )
        out_val = vsa.axon_item(self._received[0].payload, "stdout_text")
        return vsa.string_to_python(out_val)

    def _cmd_calc(self, args: str) -> str:
        """``calc <expr>`` — evaluate ``expr`` on the calc substrate.

        Delegates to ``apps/calc`` (arithmetic on ``switch.su`` through the
        kernel; operator SELECTED on the substrate). The result is exact or
        refused. See the module docstring re: the calc's step-c purity gap —
        this terminal composes calc as-is.
        """
        if not args.strip():
            raise CommandError("usage: calc <expression>  (e.g. calc 2 + 3 * 4 =)")
        if self._calc is None:
            from apps.calc.calc import Calculator
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
        "Yantra terminal — output is computed on the substrate, exact every "
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
