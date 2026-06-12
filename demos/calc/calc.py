"""CLI calculator — type ``5 * 10 =`` and it prints ``50`` — with the
arithmetic running on the Sutra substrate. Migrated from Yantra into Sutra
as a KERNEL-FREE demo (Phase-3 migration, 2026-05-29).

In Yantra this admitted ``switch.su`` as a kernel SutraService and routed
operands/results over R_switch_in / R_switch_out axon channels with a
producer + sink + tick loop. Here it is re-architected to skip the kernel
entirely: ``switch.su`` is compiled with ``compile_su`` and its ``on_axon``
is called directly on a host-built axon (the same pattern as demos/echo,
demos/font, demos/gui). No ``Init``, ``Manifest``, ``SutraService``,
``PythonService``, or router.

What still runs on the substrate (unchanged):
  - **which operation** runs is decided in ``switch.su`` from the operator
    character's codepoint (``string_char_at`` + ``select`` made exact by
    softmax saturation) — no host ``OPS[op]`` dispatch, no ``CODE[op]`` map.
  - the **arithmetic** itself (``a + b`` etc.) in float64, exact integers
    to 2^53.
  - the user-facing **digit string** is decomposed on the substrate by
    ``digits.su`` (Fourier-series eigenrotation modulus + integer division).

The host does text I/O + a recursive-descent parser (precedence,
parentheses, unary minus), evaluating each binary op on the substrate in
turn, and verifies every substrate result against an exact-rational oracle
— refusing (never approximating) anything it can't confirm exactly (a
non-terminating quotient like ``10 / 3``, divide-by-zero, or a value past
the float64 exact range).

Requires Ollama with nomic-embed-text (switch.su embeds its axon keys
"a"/"b"/"op_char" via the frozen LLM; runtime_dim=8 is the audited floor —
no basis_vector calls, so the semantic block is unused but the keys still
embed). Run: py demos/calc/calc.py
"""
from __future__ import annotations

import operator
import os
import pathlib
import re
import sys
from fractions import Fraction

HERE = pathlib.Path(__file__).resolve().parent
_REPO_ROOT = HERE.parent.parent
_SUTRA_SDK = _REPO_ROOT / "sdk" / "sutra-compiler"
if str(_SUTRA_SDK) not in sys.path:
    sys.path.insert(0, str(_SUTRA_SDK))
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from _display import read_real  # noqa: E402  (display/output boundary helper)

# Width of every axon AND of every substrate vector (compile_su's runtime_dim).
# 8 per the Yantra audit: none of the .su files call basis_vector, so the
# semantic block is unused; measured exact at width 8 (2+3=5, 7*8=56,
# 100-50=50, 2*(3+4)=14, 15/3=5). The axon keys still embed via the LLM.
AXON_WIDTH = 8
LLM_MODEL = "nomic-embed-text"

_FOPS = {
    "+": operator.add, "-": operator.sub,
    "*": operator.mul, "/": operator.truediv,
}
# Expression tokens: integer literals, the four operators, parentheses.
_TOKEN = re.compile(r"\d+|[-+*/()]")


def _compile_su(su_name: str, runtime_dtype: str = "float64") -> dict:
    """Compile a .su file in this demo dir directly; return its module
    namespace (functions + _VSA). Kernel-free — the direct-substrate
    pattern font/gui/echo use."""
    from sutra_compiler import compile_su

    mod = compile_su(
        HERE / su_name, llm_model=LLM_MODEL, runtime_dim=AXON_WIDTH,
        runtime_dtype=runtime_dtype, verbose=False,
    )
    return mod.__dict__


def _fmt(x: Fraction) -> int | float:
    """An int when integral, else a float — for display/error messages."""
    return int(x) if x.denominator == 1 else float(x)


class Calculator:
    """A CLI calculator whose arithmetic runs on the Sutra substrate.

    Construct once (compiles switch.su), then call :meth:`evaluate` per
    expression. No kernel: switch.su's ``on_axon`` is invoked directly.
    """

    DIGIT_MAX = 9999  # 4-digit substrate-digit demo scope (0..9999).

    def __init__(self) -> None:
        # Compile switch.su directly and keep its entry fn + runtime. No
        # Init / SutraService / Manifest / producer / sink / tick loop.
        ns = _compile_su("switch.su")
        self._switch_on_axon = ns["on_axon"]
        self._vsa = ns["_VSA"]
        # digits.su compiled lazily on the first result_string() call.
        self._digit = None
        self._digit_vsa = None

    def _ensure_digits(self) -> None:
        if self._digit is None:
            ns = _compile_su("digits.su")
            self._digit = ns["digit"]
            self._digit_vsa = ns["_VSA"]

    def result_string(self, value: int) -> str:
        """Return the result's decimal digits as a STRING, decomposed ON THE
        SUBSTRATE via digits.su. Non-negative integers 0..9999 (negatives get
        a leading '-'). Raises ValueError for a non-integer or out-of-range
        value — never a guessed string."""
        if not isinstance(value, int):
            raise ValueError(
                f"result {value!r} is not an integer; the substrate digit "
                "string is integer-only (step-c demo scope)"
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
            round(read_real(vsa, self._digit(float(n), float(place))))  # SUBSTRATE, display boundary
            for place in (1000.0, 100.0, 10.0, 1.0)
        ]
        s = "".join(str(d) for d in digs).lstrip("0") or "0"
        return ("-" if value < 0 else "") + s

    def evaluate(self, line: str) -> int | float:
        """Evaluate an arithmetic expression on the substrate. Supports
        + - * /, precedence, parentheses, unary minus, optional trailing '='.
        Each binary op is computed on switch.su and verified exact; refused
        (never approximated) on a parse error, /0, or any inexact result."""
        toks = self._tokenize(line)
        self._toks, self._pos = toks, 0
        value = self._parse_expr()
        if self._pos != len(toks):
            raise ValueError(f"unexpected token {toks[self._pos]!r} in {line!r}")
        return _fmt(value)

    @staticmethod
    def _tokenize(line: str) -> list[str]:
        s = line.strip()
        if s.endswith("="):
            s = s[:-1]
        toks = _TOKEN.findall(s)
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
        Anything not confirmed exact is refused rather than approximated."""
        if op == "/" and b == 0:
            raise ValueError("division by zero")
        result = self._binop_substrate(float(a), float(b), op)
        true = _FOPS[op](a, b)  # exact rational oracle (monitoring)
        if Fraction(result) != true:
            raise ValueError(
                f"{_fmt(a)} {op} {_fmt(b)} is not exactly representable on "
                f"the substrate (~ {result:g}); refusing rather than printing "
                f"an approximation"
            )
        return true

    def _binop_substrate(self, a: float, b: float, op: str) -> float:
        """Run one binary op on switch.su, with the OPERATOR SELECTED ON THE
        SUBSTRATE. Kernel-free: build the input axon, call on_axon directly,
        decode the real axis. (Was: producer.emit + init.tick + sink.)"""
        vsa = self._vsa
        axon = vsa.axon_add(vsa.zero_vector(), "a", a)
        axon = vsa.axon_add(axon, "b", b)
        axon = vsa.axon_add(axon, "op_char", vsa.make_string(op))
        out = self._switch_on_axon(axon)
        return read_real(vsa, out)  # decode real axis at the display boundary


def main() -> None:  # pragma: no cover - interactive REPL
    calc = Calculator()
    print("Sutra calculator — type an expression, e.g. `2 + 3 * 4 =`  (Ctrl-D to quit).")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            value = calc.evaluate(line)
            if isinstance(value, int) and abs(value) <= Calculator.DIGIT_MAX:
                print(calc.result_string(value))
            else:
                print(value)
        except (ValueError, RuntimeError) as exc:
            print(f"error: {exc}")


if __name__ == "__main__":  # pragma: no cover
    main()
