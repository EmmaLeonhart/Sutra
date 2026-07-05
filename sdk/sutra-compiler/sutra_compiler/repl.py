"""`sutrac repl` — an interactive Sutra evaluator.

A read-eval-print loop for exploring the embedding geometry. You type Sutra
expressions; the REPL compiles + runs them on the PyTorch substrate and shows
the result. Declarations (lines ending in `;` or `}`) accumulate as session
state so later expressions can use them.

Readout discipline (CLAUDE.md): Sutra has no value-readout accessor — `real()`
was removed for substrate purity. The REPL displays results only at the
**terminal boundary**, exactly as `sutrac --run` prints a returned value:

  - a number-vector shows its real-axis value (the one external terminal read);
  - any other vector decodes to the nearest known concept (cosine argmax over the
    program's string codebook — the same `argmax_cosine`-over-codebook the demos
    use), shown as `~ "concept" (cos 0.NN)`;
  - an already-decoded host value (string / int) prints as-is.

No `.real()` / `.item()` is used inside any Sutra operation; the decode happens
in this host process on the FINAL result, for display only.

Driveable non-interactively for tests: `run_repl(lines, out)` consumes an
iterable of input lines and writes transcript to `out`.
"""
from __future__ import annotations

import re
import sys
import types
from typing import Iterable, List, Optional, TextIO

from .diagnostics import DiagnosticLevel
from .lexer import Lexer
from .parser import Parser
from .codegen_pytorch import translate_module as _translate

_BANNER = (
    "Sutra REPL - type an expression to evaluate it; end a line with ';' or '}' "
    "to add a declaration.\n"
    "Commands: :help  :decls  :reset  :quit\n"
)
_HELP = (
    "Sutra REPL help\n"
    "  <expression>        evaluate and show the result\n"
    "                      (number -> real value; concept -> nearest known string)\n"
    "  <stmt>;             add a declaration/statement to the session (e.g. vector k = embed(\"king\");)\n"
    "  function ... { }    add a function to the session\n"
    "  :decls              print the accumulated session declarations\n"
    "  :reset              clear all session declarations\n"
    "  :help               this help\n"
    "  :quit  / :q         leave the REPL (Ctrl-D also works)\n"
)

_EVAL_FN = "__repl_eval__"


def _compile_and_exec(src: str, *, runtime_dim: int, runtime_seed: int):
    """Compile Sutra source string to a runnable module. Returns (module, None)
    on success or (None, error_messages) on a parse/codegen error."""
    lexer = Lexer(src, file="<repl>")
    tokens = lexer.tokenize()
    parser = Parser(tokens, file="<repl>", diagnostics=lexer.diagnostics)
    module_ast = parser.parse_module()
    if lexer.diagnostics.has_errors():
        return None, [d.format() for d in lexer.diagnostics
                      if d.level is DiagnosticLevel.ERROR]
    try:
        py_src = _translate(module_ast, runtime_dim=runtime_dim, runtime_seed=runtime_seed)
    except Exception as e:  # codegen rejection (e.g. unsupported construct)
        return None, [f"{type(e).__name__}: {e}"]
    mod = types.ModuleType("_sutra_repl")
    mod.__file__ = "<repl>"
    try:
        exec(compile(py_src, mod.__file__, "exec"), mod.__dict__)
    except Exception as e:
        return None, [f"runtime error: {type(e).__name__}: {e}"]
    return mod, None


def _decode_result(mod, result, *, concept_threshold: float = 0.5) -> str:
    """Decode a FINAL result for terminal display (no in-operation readout)."""
    # Already a host value (string / int / float) — print as-is.
    try:
        import torch as _t
    except Exception:
        return repr(result)
    vsa = getattr(mod, "_VSA", None)
    if isinstance(result, _t.Tensor) and result.numel() == 1:
        # A scalar substrate result (similarity / dot / norm reductions land
        # here as a 0-d tensor). Show the number at the sanctioned terminal
        # display boundary — NOT torch's raw `tensor(0.68, device='cuda:0')`
        # repr, which leaked CUDA/dtype internals a newcomer shouldn't see
        # (REPL first-run finding 2026-07-04).
        return f"= {float(result):g}"
    if not (vsa is not None and isinstance(result, _t.Tensor)
            and result.ndim == 1 and result.shape[0] == vsa.dim):
        return repr(result)

    # Nearest known concept: cosine argmax over the string codebook the program
    # built. This is the sanctioned argmax-over-codebook decode (demos do it in
    # Sutra source via argmax_cosine + a map<vector, string>).
    best_name: Optional[str] = None
    best_cos = -2.0
    codebook = getattr(vsa, "_codebook", {}) or {}
    rn = _t.linalg.norm(result)
    if rn > 0:
        for name, vec in codebook.items():
            vn = _t.linalg.norm(vec)
            if vn <= 0:
                continue
            cos = float(_t.dot(result, vec) / (rn * vn))
            if cos > best_cos:
                best_cos, best_name = cos, name

    if best_name is not None and best_cos >= concept_threshold:
        return f'~ "{best_name}"  (cos {best_cos:.2f})'

    # Otherwise treat it as a number-vector: show the real-axis value (the one
    # external terminal read, same boundary as `sutrac --run`).
    try:
        val = float(result[vsa.semantic_dim + vsa.AXIS_REAL])
    except Exception:
        return f"<vector, no close concept; best cos {best_cos:.2f}>"
    # Only mention a nearest concept if it's actually somewhat close — a cos~0
    # "nearest" is noise on a plain number result.
    extra = (f"; nearest \"{best_name}\" cos {best_cos:.2f}"
             if best_name is not None and best_cos >= 0.25 else "")
    return f"= {val:g}{extra}"


_BARE_STRING_RE = re.compile(r'^(?:"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\')$')


def _bare_string_literal(expr: str) -> Optional[str]:
    """If `expr` is nothing but a single string literal, return its text; else
    None. The REPL wraps expressions as `function vector __eval__() { return
    <expr>; }`, and a raw string sent through that vector-typed path throws an
    internal `TypeError` (a Sutra string is a codepoint vector that needs a
    `string`-typed wrapper — see queue.md item 1). Until that fix lands, catch
    the bare-literal case up front and steer the newcomer to `embed(...)`."""
    s = expr.strip()
    m = _BARE_STRING_RE.match(s)
    return s if m else None


def _looks_like_declaration(line: str) -> bool:
    """A line that ends a statement (`;`) or a block (`}`) is session state;
    anything else is an expression to evaluate."""
    s = line.rstrip()
    return s.endswith(";") or s.endswith("}")


def _balanced(text: str) -> bool:
    """True if braces/parens/brackets are balanced — used to keep reading a
    multi-line declaration (e.g. a function spanning lines)."""
    depth = 0
    for ch in text:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
    return depth <= 0


def run_repl(
    lines: Iterable[str],
    out: TextIO,
    *,
    runtime_dim: int = 64,
    runtime_seed: int = 42,
    banner: bool = True,
) -> int:
    """Run the REPL over `lines`, writing transcript to `out`. Returns 0."""
    if banner:
        out.write(_BANNER)
        out.flush()
    decls: List[str] = []
    it = iter(lines)
    for raw in it:
        line = raw.rstrip("\n")
        stripped = line.strip()
        if not stripped:
            continue
        if stripped in (":quit", ":q", ":exit"):
            break
        if stripped == ":help":
            out.write(_HELP); out.flush(); continue
        if stripped == ":reset":
            decls.clear(); out.write("(session cleared)\n"); out.flush(); continue
        if stripped == ":decls":
            out.write("".join(d + "\n" for d in decls) or "(no declarations)\n")
            out.flush(); continue

        # Accumulate a multi-line declaration until braces balance.
        buf = line
        while _looks_like_declaration(buf) and not _balanced(buf):
            try:
                buf += "\n" + next(it).rstrip("\n")
            except StopIteration:
                break

        if _looks_like_declaration(buf):
            # Validate the declaration in the context of the session before
            # keeping it, so a bad line doesn't poison every later eval.
            trial = "\n".join(decls + [buf, f"function int {_EVAL_FN}_probe() {{ return 0; }}"])
            mod, errs = _compile_and_exec(trial, runtime_dim=runtime_dim, runtime_seed=runtime_seed)
            if errs:
                out.write("error: " + "; ".join(errs) + "\n")
            else:
                decls.append(buf)
                out.write("(added)\n")
            out.flush()
            continue

        # Bare string literal: the vector-typed eval wrapper can't evaluate it
        # yet (queue.md item 1). Steer to embed() instead of the raw TypeError.
        lit = _bare_string_literal(buf)
        if lit is not None:
            out.write(f"strings live on the substrate via embed(...). Try: embed({lit})\n")
            out.flush()
            continue

        # Expression: wrap, compile the whole session, run, decode.
        program = "\n".join(decls + [f"function vector {_EVAL_FN}() {{ return {buf}; }}"])
        mod, errs = _compile_and_exec(program, runtime_dim=runtime_dim, runtime_seed=runtime_seed)
        if errs:
            out.write("error: " + "; ".join(errs) + "\n"); out.flush(); continue
        fn = getattr(mod, _EVAL_FN, None)
        if fn is None or not callable(fn):
            out.write("error: could not evaluate expression\n"); out.flush(); continue
        try:
            result = fn()
        except Exception as e:
            out.write(f"runtime error: {type(e).__name__}: {e}\n"); out.flush(); continue
        out.write(_decode_result(mod, result) + "\n")
        out.flush()
    return 0


def main_repl(*, runtime_dim: int = 64, runtime_seed: int = 42) -> int:
    """Interactive entry point: drive run_repl from stdin with a prompt."""
    def _prompted_lines():
        while True:
            try:
                yield input("sutra> ")
            except EOFError:
                print()
                return
            except KeyboardInterrupt:
                print("\n(use :quit to exit)")
                continue
    return run_repl(_prompted_lines(), sys.stdout,
                    runtime_dim=runtime_dim, runtime_seed=runtime_seed)
