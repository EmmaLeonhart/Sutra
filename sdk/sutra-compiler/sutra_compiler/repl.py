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

import sys
import types
from typing import Iterable, List, Optional, TextIO

from . import ast_nodes as ast
from .diagnostics import DiagnosticLevel
from .lexer import Lexer
from .parser import Parser
from .symbol_table import build_symbol_table, infer_type
from .codegen_pytorch import translate_module as _translate

# Inferred expression types the REPL will use to type the __eval__ wrapper. `string`
# is the one that MUST override the default `vector` wrapper — a Sutra string is a
# codepoint vector, and the vector-typed path does vector math on it and throws
# (the bare-string REPL crash). Other types keep the default vector wrapper, which
# already displays numbers/concepts correctly; they are added here only as they are
# verified to round-trip through the wrapper + `_decode_result`.
_EVAL_WRAP_TYPES = {"string"}

_BANNER = (
    "Sutra REPL - type an expression to evaluate it; end a line with ';' or '}' "
    "to add a declaration.\n"
    "Commands: :help  :ops  :decls  :reset  :quit\n"
)
_HELP = (
    "Sutra REPL help\n"
    "  <expression>        evaluate and show the result\n"
    "                      (number -> real value; concept -> nearest known string)\n"
    "  <stmt>;             add a declaration/statement to the session (e.g. vector k = embed(\"king\");)\n"
    "  function ... { }    add a function to the session\n"
    "  :ops                list the callable operations (builtins, stdlib, special forms)\n"
    "  :decls              print the accumulated session declarations\n"
    "  :reset              clear all session declarations\n"
    "  :help               this help\n"
    "  :quit  / :q         leave the REPL (Ctrl-D also works)\n"
)


def _ops_listing() -> str:
    """The `:ops` discovery surface: every operation callable from REPL
    source, grouped. Built from the live dispatch tables (BUILTINS + the
    stdlib intrinsic registry) so it cannot drift from what actually
    resolves — a hand-written list here would rot."""
    from .codegen_base import BUILTINS
    try:
        from .stdlib_loader import stdlib_class_intrinsic_methods
        stdlib = stdlib_class_intrinsic_methods()
    except Exception:
        stdlib = {}

    def _columns(names, indent="    ", width=76):
        lines, cur = [], indent
        for n in names:
            if len(cur) + len(n) + 2 > width and cur.strip():
                lines.append(cur.rstrip())
                cur = indent
            cur += n + "  "
        if cur.strip():
            lines.append(cur.rstrip())
        return "\n".join(lines)

    parts = ["Operations callable from Sutra source in this REPL\n"]
    parts.append("  builtins:\n" + _columns(sorted(BUILTINS.keys())) + "\n")
    for cls in sorted(stdlib):
        methods = sorted(stdlib[cls])
        if not methods:
            continue
        parts.append(f"  {cls} (call bare or as {cls}.<name>):\n"
                     + _columns(methods) + "\n")
    parts.append(
        "  special forms:\n"
        "    embed(\"...\")   defuzzy(v)   unsafeCast<T>(v)   unsafeOverride(v)\n"
        "    (Type) expr casts   $\"text {interpolant}\" interpolation\n"
    )
    parts.append(
        "  full reference: https://sutra.topazcomputing.com/capabilities/\n")
    return "".join(parts)

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


def _decode_string(vsa, result) -> Optional[str]:
    """If `result` is a Sutra String vector, reconstruct its text; else None.

    Reads the codepoints stored on the string's synthetic axes back into a Python
    `str` using the runtime's own String accessors (`is_string` / `string_length` /
    `string_char_at`). This is a RAW codepoint read at the terminal DISPLAY
    boundary — the sanctioned terminal I/O point, not a mid-computation readout —
    and is distinct from the codebook-nearest decode used for embedding vectors: a
    `make_string("hello")` value carries "hello" literally on its axes, it is not a
    concept in the codebook."""
    try:
        if not (hasattr(vsa, "is_string") and bool(vsa.is_string(result))):
            return None
        n = int(vsa.string_length(result))
        return "".join(
            chr(int(round(float(vsa.string_char_at(result, i))))) for i in range(n)
        )
    except Exception:
        return None


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

    # A Sutra String decodes to its literal text (raw codepoint read at the
    # display boundary), NOT to a nearest codebook concept.
    text = _decode_string(vsa, result)
    if text is not None:
        return f'"{text}"'

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


def _infer_eval_type(decls: List[str], expr: str) -> Optional[str]:
    """Infer the Sutra type of a REPL expression in the session context, so the
    `__eval__` wrapper can be typed correctly (a string expression needs a
    string-typed wrapper, not the default `vector`). Returns None when the type
    can't be determined — the caller then keeps the `vector` wrapper. Purely a
    parse+inference pass; it neither compiles nor runs anything."""
    try:
        lx = Lexer("\n".join(decls), file="<repl>")
        m = Parser(lx.tokenize(), file="<repl>", diagnostics=lx.diagnostics).parse_module()
        symbols = build_symbol_table(m)
        # Top-level session vars (e.g. `vector a = embed("cat");`) give an
        # identifier its type when the expression references them.
        env = {}
        for item in m.items:
            if isinstance(item, ast.VarDecl):
                t = (getattr(getattr(item, "type_ref", None), "name", None)
                     or getattr(getattr(item, "var_type", None), "name", None))
                if t:
                    env[item.name] = t
        elx = Lexer(f"function vector __repl_probe__() {{ return {expr}; }}", file="<repl>")
        em = Parser(elx.tokenize(), file="<repl>",
                    diagnostics=elx.diagnostics).parse_module()
        if elx.diagnostics.has_errors():
            return None
        ret = next((s for s in em.items[0].body.statements
                    if type(s).__name__ == "ReturnStmt"), None)
        if ret is None:
            return None
        return infer_type(ret.value, symbols, env)
    except Exception:
        return None


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
        if stripped == ":ops":
            out.write(_ops_listing()); out.flush(); continue
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

        # Expression: infer its type so the wrapper is typed correctly (a string
        # expression needs a `string` wrapper — the default `vector` one does
        # vector math on the codepoint array and throws). Falls back to `vector`
        # when the type is unknown or not in the verified wrap set.
        inferred = _infer_eval_type(decls, buf)
        eval_type = inferred if inferred in _EVAL_WRAP_TYPES else "vector"
        program = "\n".join(decls + [f"function {eval_type} {_EVAL_FN}() {{ return {buf}; }}"])
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
