"""Yantra CLI calculator — type ``5 * 10 =`` and it prints ``50``.

Not a GUI: a plain text-in / text-out calculator. It is the small,
definitive contrast with Meta's *Neural Computers* (NCCLIGen — a DiT
video model that *generates* terminal frames, and whose own paper
names symbolic stability as unsolved). Two things it demonstrates:

  1. **Text parsing** — a real expression parser, not frame generation.
  2. **Reliable math** — the arithmetic runs on the Sutra substrate
     through the kernel, exact by construction. Where a diffusion model
     would hallucinate a plausible-looking number, Yantra computes the
     true one.

Layering matches the architecture (planning/01): text I/O + parsing is
**host orchestration** (the CPU side's job); the arithmetic — including
*which* operation runs, and *which character* names it — happens on the
substrate. ``switch.su`` computes all four ops, reads the operator
codepoint with ``string_char_at`` from a single-character string in the
axon (``"+"``/``"-"``/``"*"``/``"/"``), and selects the requested one via
``select`` made exact by softmax saturation. The host no longer carries a
``CODE`` map or an ``OPS[op]`` dispatch — the operator's identification
from its character runs on the substrate too. Multi-term expressions with
precedence and parentheses are supported (``2 + 3 * 4 = 14``,
``(10 - 2) * 5 = 40``) — a recursive-descent parser on the host evaluates
each binary operation on the substrate in turn.

The substrate runs in float64 (Sutra v0.6.2 ``runtime_dtype``), so exact
integers hold to 2**53 (~9.007e15) — not float32's ~2**24; this is the
substrate computing in higher precision, no host carries.

Step c (Emma's product decision 2026-05-25 — DONE for the demo): the
user-facing result is now a digit STRING decomposed ON THE SUBSTRATE.
``result_string`` runs ``digits.su`` (the Fourier-series eigenrotation
modulus + integer division) to peel the 1000s / 100s / 10s / 1s, each digit
decoded from the substrate with ``real()`` — not a host ``Fraction``. The
REPL prints that string. 4-digit demo scope (0..9999); the internal
``evaluate`` still composes exact ``Fraction``s for multi-term precedence +
the monitoring oracle, and still refuses what it can't confirm exactly (a
non-terminating quotient like ``10 / 3``, divide-by-zero, or a value past
the float64 exact range 2**53) — never approximated. True arbitrary
precision (beyond 4 digits) is planning/22 Stage 3.
"""
from __future__ import annotations

import operator
import pathlib
import re
import sys
from fractions import Fraction

# Allow running standalone (`python apps/calc/calc.py`, `demo.py`): put
# the repo root on sys.path so `from kernel import ...` resolves even
# when this file is the script entry point (pytest already does this via
# pyproject's pythonpath; a bare `python` invocation does not).
_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from kernel import Init, Manifest, PythonService, SutraService  # noqa: E402
from kernel.router import Axon  # noqa: E402

APPS_CALC = pathlib.Path(__file__).resolve().parent
# Width of every axon AND of every substrate vector (compile_su's runtime_dim).
# Was 768 (the nomic-embed-text default); dropped to 8 on 2026-05-27 after
# audit (planning/27-substrate-honesty-audit-2026-05-27.md) found none of the
# four .su files in this app call basis_vector. The semantic block of the
# extended-state layout was therefore unused — every op carried 766 dead-weight
# tensor elements per call. Measured exact at width 8: 2+3=5, 7*8=56, 100-50=50,
# 2*(3+4)=14, 15/3=5; full test_calc.py suite (57 cases) green at width 8.
AXON_WIDTH = 8

# digits.su is compiled directly (its `digit(n, place)` is a pure substrate
# function call, not an axon service — the same direct-substrate pattern the GUI
# uses for frame.su / count.su). That needs the Sutra compiler on the path.
_SUTRA_SDK = _REPO_ROOT.parent.parent / "sdk" / "sutra-compiler"  # Yantra vendored in-tree under Sutra
if str(_SUTRA_SDK) not in sys.path:
    sys.path.insert(0, str(_SUTRA_SDK))


def _compile_su(su_path: pathlib.Path, runtime_dtype: str = "float64") -> dict:
    """Compile a .su file directly; return its module namespace (functions + _VSA).

    Thin wrapper over `sutra_compiler.compile_su` (Sutra >= v0.7.1) which
    caches the emitted Python on disk so repeat calls skip codegen entirely.
    Returns a dict view (source-compat with the prior `ns["fn"]` pattern).
    """
    from sutra_compiler import compile_su
    mod = compile_su(
        su_path, llm_model="nomic-embed-text", runtime_dim=AXON_WIDTH,
        runtime_dtype=runtime_dtype, verbose=False,
    )
    return mod.__dict__

# The operator is fed to switch.su as a 1-char STRING (make_string(op)); switch
# reads its codepoint on the substrate and selects the operation there. No host
# operator->code map: the operator->operation mapping is a substrate decision.
# Host oracle for the exactness gate (monitoring only): exact rational
# arithmetic used to verify each substrate op's result.
_FOPS = {
    "+": operator.add, "-": operator.sub,
    "*": operator.mul, "/": operator.truediv,
}
# Expression tokens: integer literals, the four operators, parentheses.
_TOKEN = re.compile(r"\d+|[-+*/()]")


def _fmt(x: Fraction) -> int | float:
    """An int when integral, else a float — for display/error messages."""
    return int(x) if x.denominator == 1 else float(x)


class Calculator:
    """A CLI calculator whose arithmetic runs on the Sutra substrate.

    Construct once (compiles the three op services), then call
    :meth:`evaluate` per expression.
    """

    def __init__(self) -> None:
        self.init = Init(compute_pool=32)
        # ONE service computes every operation and selects the requested
        # one on the substrate (switch.su's select+saturation one-hot,
        # scored against the operator codepoint). No host `OPS[op]`
        # choosing which .su to run; no host `CODE[op]` numeric op-code.
        self._service = SutraService(
            source_path=APPS_CALC / "switch.su",
            output_role="R_switch_out",
            # float64 substrate: exact integers to 2^53 (~9.007e15), not
            # float32's ~2^24. No host carries — the substrate computes in
            # higher precision (needs Sutra >= v0.6.2). Past 2^53 the gate
            # still refuses, so "never a wrong answer" holds.
            runtime_dtype="float64",
        )
        self.init.admit(
            Manifest(
                name="switch", axon_width=AXON_WIDTH, compute_units=1,
                read_roles=frozenset({"R_switch_in"}),
                write_roles=frozenset({"R_switch_out"}),
                source="switch.su",
            ),
            self._service,
        )

        # Host producer (injects the input axon) and sink (reads the
        # result). The math — including which operation runs — happens
        # inside switch.su; these are just the orchestrator's I/O endpoints.
        self._producer = PythonService(lambda s, ax: None)
        self.init.admit(
            Manifest(
                name="calc_in", axon_width=AXON_WIDTH, compute_units=1,
                read_roles=frozenset(), write_roles=frozenset({"R_switch_in"}),
                source="calc_in.py",
            ),
            self._producer,
        )
        self._received: list[Axon] = []
        sink = PythonService(on_axon=lambda s, ax: self._received.append(ax))
        self.init.admit(
            Manifest(
                name="calc_out", axon_width=AXON_WIDTH, compute_units=1,
                read_roles=frozenset({"R_switch_out"}), write_roles=frozenset(),
                source="calc_out.py",
            ),
            sink,
        )

        # digits.su is compiled lazily on the first result_string() call, so the
        # arithmetic-only path (the 57 evaluate() tests) doesn't pay for it.
        self._digit = None
        self._digit_vsa = None

    # 4-digit demo scope (Emma 2026-05-25): the substrate digit decomposition
    # covers integers 0..9999 (negatives get a leading '-').
    DIGIT_MAX = 9999

    def _ensure_digits(self) -> None:
        if self._digit is None:
            ns = _compile_su(APPS_CALC / "digits.su")
            self._digit = ns["digit"]
            self._digit_vsa = ns["_VSA"]

    def result_string(self, value: int) -> str:
        """Return the result's decimal digits as a STRING, decomposed ON THE
        SUBSTRATE — Emma's product decision for step c.

        Rather than return a host ``Fraction``, decompose the integer result
        into its 1000s / 100s / 10s / 1s digits via ``digits.su`` (the
        Fourier-series eigenrotation modulus + integer division) and join them.
        Each digit is decoded from the substrate with ``real()``; the host only
        assembles the string. The arithmetic upstream is kernel-routed; this is
        the final substrate display step.

        Non-negative integers 0..9999 (negatives get a leading ``-``). Raises
        ``ValueError`` for a non-integer or out-of-range value — never a guessed
        string.
        """
        if not isinstance(value, int):
            raise ValueError(
                f"result {value!r} is not an integer; the substrate digit string "
                "is integer-only (step-c demo scope)"
            )
        if abs(value) > self.DIGIT_MAX:
            raise ValueError(
                f"result {value} is outside the 4-digit substrate-digit demo "
                f"range (|x| <= {self.DIGIT_MAX})"
            )
        self._ensure_digits()
        vsa = self._digit_vsa
        n = abs(value)
        digs = [
            round(float(vsa.real(self._digit(float(n), float(place)))))  # SUBSTRATE
            for place in (1000.0, 100.0, 10.0, 1.0)
        ]
        s = "".join(str(d) for d in digs).lstrip("0") or "0"
        return ("-" if value < 0 else "") + s

    def evaluate(self, line: str) -> int | float:
        """Evaluate an arithmetic expression on the substrate.

        Supports multi-term expressions with ``+ - * /``, precedence, and
        parentheses (``2 + 3 * 4`` → ``14``), unary minus, and an optional
        trailing ``=``. Each binary operation is computed on a real Sutra
        service through the kernel and verified exact; the returned value
        is an ``int`` (or a ``float`` for an exact fraction like
        ``7 / 2``). Raises ``ValueError`` on a parse error, division by
        zero, or any result the substrate cannot compute exactly (refused,
        never approximated).
        """
        toks = self._tokenize(line)
        self._toks, self._pos = toks, 0
        value = self._parse_expr()
        if self._pos != len(toks):
            raise ValueError(
                f"unexpected token {toks[self._pos]!r} in {line!r}"
            )
        return _fmt(value)

    @staticmethod
    def _tokenize(line: str) -> list[str]:
        s = line.strip()
        if s.endswith("="):
            s = s[:-1]
        toks = _TOKEN.findall(s)
        # Reject stray characters: the tokens must account for everything
        # but whitespace.
        if "".join(toks) != re.sub(r"\s+", "", s):
            raise ValueError(f"cannot parse expression: {line!r}")
        if not toks:
            raise ValueError(f"empty expression: {line!r}")
        return toks

    # --- recursive-descent parser; each binary op runs on the substrate ---

    def _peek(self) -> str | None:
        return self._toks[self._pos] if self._pos < len(self._toks) else None

    def _parse_expr(self) -> Fraction:  # term (('+' | '-') term)*
        value = self._parse_term()
        while self._peek() in ("+", "-"):
            op = self._toks[self._pos]
            self._pos += 1
            value = self._binop(value, op, self._parse_term())
        return value

    def _parse_term(self) -> Fraction:  # factor (('*' | '/') factor)*
        value = self._parse_factor()
        while self._peek() in ("*", "/"):
            op = self._toks[self._pos]
            self._pos += 1
            value = self._binop(value, op, self._parse_factor())
        return value

    def _parse_factor(self) -> Fraction:  # NUMBER | '(' expr ')' | ('-'|'+') factor
        t = self._peek()
        if t is None:
            raise ValueError("unexpected end of expression")
        if t == "-":
            self._pos += 1
            return -self._parse_factor()
        if t == "+":
            self._pos += 1
            return self._parse_factor()
        if t == "(":
            self._pos += 1
            value = self._parse_expr()
            if self._peek() != ")":
                raise ValueError("missing closing parenthesis")
            self._pos += 1
            return value
        if t.isdigit():
            self._pos += 1
            return Fraction(int(t))
        raise ValueError(f"unexpected token {t!r}")

    def _binop(self, a: Fraction, op: str, b: Fraction) -> Fraction:
        """Compute ``a op b`` on the substrate; verify exact; return exact.

        The substrate computes the value; an exact-rational host oracle
        (monitoring) verifies it. Anything not confirmed exact is refused
        rather than approximated.
        """
        if op == "/" and b == 0:
            raise ValueError("division by zero")
        result = self._binop_substrate(float(a), float(b), op)
        true = _FOPS[op](a, b)  # exact rational
        if Fraction(result) != true:
            raise ValueError(
                f"{_fmt(a)} {op} {_fmt(b)} is not exactly representable on "
                f"the substrate (~ {result:g}); refusing rather than printing "
                f"an approximation (arbitrary precision: planning/22 Stage 3)"
            )
        return true

    def _binop_substrate(self, a: float, b: float, op: str) -> float:
        """Run one binary op on the substrate, with the OPERATOR SELECTED
        ON THE SUBSTRATE.

        The host injects operands ``a``/``b`` and an operator *code* (not
        a choice of service); ``switch.su`` computes all four operations
        and returns the one the operator code selects via exact Lagrange
        one-hot masks. There is no host ``OPS[op]`` dispatch — which
        operation runs is decided on the substrate.
        """
        vsa = self._service._compiled_module._VSA  # noqa: SLF001
        axon = vsa.axon_add(vsa.zero_vector(), "a", a)
        axon = vsa.axon_add(axon, "b", b)
        axon = vsa.axon_add(axon, "op_char", vsa.make_string(op))
        self._received.clear()
        self._producer.emit("R_switch_in", axon)
        self.init.tick()  # fire the switch service
        self.init.tick()  # fire the sink
        if len(self._received) != 1:
            raise RuntimeError(
                f"calculator delivered {len(self._received)} results (expected 1)"
            )
        return float(vsa.real(self._received[0].payload))  # decode real axis


def main() -> None:  # pragma: no cover - interactive REPL
    import sys

    calc = Calculator()
    print("Yantra calculator — type an expression, e.g. `2 + 3 * 4 =`  (Ctrl-D to quit).")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            value = calc.evaluate(line)
            # Integer results in the 4-digit demo range print as the digit
            # STRING decomposed on the substrate (Emma's step c); other results
            # print as the numeric value.
            if isinstance(value, int) and abs(value) <= Calculator.DIGIT_MAX:
                print(calc.result_string(value))
            else:
                print(value)
        except (ValueError, RuntimeError) as exc:
            print(f"error: {exc}")


if __name__ == "__main__":  # pragma: no cover
    main()
