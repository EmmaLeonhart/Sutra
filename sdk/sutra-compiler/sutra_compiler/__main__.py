"""Command-line entry point for the Sutra compiler/validator.

Usage:

    python -m sutra_compiler FILE [FILE ...]
    python -m sutra_compiler --json FILE
    python -m sutra_compiler --summary DIR_OR_FILE [...]

The CLI lexes, parses, and validates each `.su` file and prints any
diagnostics in `file:line:col: level: message` form — the same shape
every major compiler and every editor knows how to parse.

Exit code is 0 if no errors were reported, 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List

from . import __version__
from . import ast_nodes as ast
from .codegen_base import CodegenNotSupported
from .codegen_pytorch import translate_module as translate_pytorch
from .diagnostics import Diagnostic, DiagnosticLevel
from .lexer import Lexer
from .parser import Parser
from .validator import validate_file, _Walker, _check_pipe_forward


def _iter_akasha_files(paths: List[str]) -> List[str]:
    """Expand a list of files/directories into a flat list of `.su`
    files. Non-existent paths are left to the caller to report."""
    out: List[str] = []
    for p in paths:
        if os.path.isdir(p):
            for root, _, files in os.walk(p):
                for f in sorted(files):
                    if f.endswith(".su"):
                        out.append(os.path.join(root, f))
        else:
            out.append(p)
    return out


def _diag_to_dict(d: Diagnostic) -> dict:
    return {
        "file": d.file,
        "line": d.span.start.line,
        "column": d.span.start.column,
        "end_line": d.span.end.line,
        "end_column": d.span.end.column,
        "level": d.level.value,
        "code": d.code,
        "message": d.message,
        "hint": d.hint,
    }


def _run_text(paths: List[str], *, summary: bool) -> int:
    files = _iter_akasha_files(paths)
    total_errors = 0
    total_warnings = 0
    per_file = []
    for f in files:
        if not os.path.exists(f):
            print(f"{f}: error: file not found", file=sys.stderr)
            total_errors += 1
            continue
        bag = validate_file(f)
        n_err = len(bag.errors)
        n_warn = len(bag.warnings)
        total_errors += n_err
        total_warnings += n_warn
        per_file.append((f, n_err, n_warn))
        if not summary:
            for d in bag:
                print(d.format())
    if summary:
        width = max((len(f) for f, _, _ in per_file), default=0)
        print(f"{'file'.ljust(width)}  errors  warnings")
        print("-" * (width + 20))
        for f, e, w in per_file:
            print(f"{f.ljust(width)}  {e:6d}  {w:8d}")
        print("-" * (width + 20))
        print(f"{'total'.ljust(width)}  {total_errors:6d}  {total_warnings:8d}")
    else:
        if total_errors == 0 and total_warnings == 0:
            print(f"ok: {len(files)} file(s) validated, 0 diagnostics")
        else:
            print(
                f"done: {len(files)} file(s) validated, "
                f"{total_errors} error(s), {total_warnings} warning(s)"
            )
    return 1 if total_errors else 0


def _run_json(paths: List[str]) -> int:
    files = _iter_akasha_files(paths)
    out = []
    total_errors = 0
    for f in files:
        entry = {"file": f, "diagnostics": []}
        if not os.path.exists(f):
            entry["diagnostics"].append(
                {
                    "file": f,
                    "line": 1,
                    "column": 1,
                    "end_line": 1,
                    "end_column": 1,
                    "level": "error",
                    "code": "SUT9999",
                    "message": "file not found",
                    "hint": None,
                }
            )
            total_errors += 1
            out.append(entry)
            continue
        bag = validate_file(f)
        for d in bag:
            entry["diagnostics"].append(_diag_to_dict(d))
        total_errors += len(bag.errors)
        out.append(entry)
    json.dump({"files": out, "version": __version__}, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 1 if total_errors else 0


def _run_consistency(paths: List[str]) -> int:
    """Cross-file class-name casing check.

    For each non-primitive type name that appears across the file set,
    report every distinct casing and the files it appears in. This
    flags drift like `animal` vs `Animal` across the repo.
    """
    files = _iter_akasha_files(paths)
    # name_lower -> { casing -> set of files }
    usages: dict = {}
    for f in files:
        if not os.path.exists(f):
            print(f"{f}: error: file not found", file=sys.stderr)
            continue
        with open(f, encoding="utf-8") as fp:
            src = fp.read()
        lexer = Lexer(src, file=f)
        tokens = lexer.tokenize()
        parser = Parser(tokens, file=f, diagnostics=lexer.diagnostics)
        module = parser.parse_module()
        walker = _Walker(lexer.diagnostics)
        # Walk just the declarations to collect type-name usages.
        for item in module.items:
            walker.visit(item)
        for name in walker._class_name_usages:
            entry = usages.setdefault(name.lower(), {})
            entry.setdefault(name, set()).add(f)

    drift_count = 0
    print("Cross-file class-name casing check")
    print("=" * 60)
    for lower_name, casings in sorted(usages.items()):
        if len(casings) < 2:
            continue
        drift_count += 1
        print(f"\n  DRIFT: {lower_name} appears in {len(casings)} casings")
        for casing in sorted(casings.keys()):
            file_list = sorted(casings[casing])
            print(f"    `{casing}`")
            for f in file_list:
                print(f"       {f}")
    if drift_count == 0:
        print("\n  no cross-file casing drift detected")
    else:
        print(f"\n{drift_count} class name(s) with casing drift across the file set")
    return 1 if drift_count else 0


def _read_atman_loop_T(source_path: str) -> int | None:
    """Walk up from the .su source file looking for an atman.toml that
    declares `[project.compile] loop_max_iterations = N`. Returns N if
    found, else None.
    """
    try:
        import tomllib  # py3.11+
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore
        except ImportError:
            return None
    cur = os.path.dirname(os.path.abspath(source_path))
    while True:
        candidate = os.path.join(cur, "atman.toml")
        if os.path.isfile(candidate):
            try:
                with open(candidate, "rb") as fp:
                    data = tomllib.load(fp)
            except Exception:
                return None
            v = (data.get("project", {})
                     .get("compile", {})
                     .get("loop_max_iterations"))
            if isinstance(v, int) and v > 0:
                return v
            return None
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent


def _read_atman_max_preeval_depth(source_path: str) -> int | None:
    """Walk up from the .su source for an atman.toml declaring
    `[project.compile] max_preeval_depth = N`. Returns N if found, else None.
    (Mirrors `_read_atman_loop_T`; the compile-time pre-evaluation depth cap for
    `--preeval` / Phase-5.5 tier 3.)"""
    try:
        import tomllib  # py3.11+
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore
        except ImportError:
            return None
    cur = os.path.dirname(os.path.abspath(source_path))
    while True:
        candidate = os.path.join(cur, "atman.toml")
        if os.path.isfile(candidate):
            try:
                with open(candidate, "rb") as fp:
                    data = tomllib.load(fp)
            except Exception:
                return None
            v = (data.get("project", {})
                     .get("compile", {})
                     .get("max_preeval_depth"))
            return v if isinstance(v, int) and v > 0 else None
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent


def _compile_to_python(path: str, *, runtime_dim: int,
                       runtime_seed: int,
                       loop_T: int | None = None,
                       preeval: bool = False,
                       max_preeval_depth: int | None = None) -> str | None:
    """Validate + parse + codegen one .su file. Returns generated Python
    source, or None on failure (diagnostics already printed).

    `loop_T` resolution: if the caller passes an explicit value, use it.
    Else, walk up from the source file looking for `atman.toml` with a
    `[project.compile] loop_max_iterations` field. Else default to 50.
    """
    if not os.path.exists(path):
        print(f"{path}: error: file not found", file=sys.stderr)
        return None
    bag = validate_file(path)
    if bag.errors:
        for d in bag:
            print(d.format(), file=sys.stderr)
        return None
    with open(path, encoding="utf-8") as fp:
        src = fp.read()
    lexer = Lexer(src, file=path)
    tokens = lexer.tokenize()
    parser = Parser(tokens, file=path, diagnostics=lexer.diagnostics)
    module = parser.parse_module()
    # Compile-time pre-evaluation of bounded pure recursion (Phase 5.5 tier 3): fold
    # constant-arg calls to bounded pure recursive functions into literals. Runs by
    # DEFAULT at a SHALLOW depth (Emma 2026-06-17: "default ... should not be zero but
    # around 2-3") — it only fires when the compiler can see a call is precalculable
    # (constant args), which is uncommon, so the default is cheap. `--preeval` raises
    # the cap to a deep value; `--max-preeval-depth N` sets it (0 disables).
    from .preeval import (preeval_bounded_recursion, DEFAULT_MAX_PREEVAL_DEPTH,
                          DEEP_MAX_PREEVAL_DEPTH)
    if max_preeval_depth is not None:
        depth = max_preeval_depth
    elif preeval:
        depth = DEEP_MAX_PREEVAL_DEPTH
    else:
        depth = _read_atman_max_preeval_depth(path) or DEFAULT_MAX_PREEVAL_DEPTH
    if depth > 0:
        preeval_bounded_recursion(module, max_depth=depth)
    # Tier 4 — native recursion via memoization (Phase 5.5): rewrite tabulable multiple-recursive
    # functions (the fib family) into a memoizing `while_loop` (recurrent neurons, native — Sutra
    # has no native runtime recursion otherwise). Conservative: only the exact tabulable shape is
    # transformed; everything else is untouched. Runs by default so recursion "just works" natively.
    from .tabulate import tabulate_module
    tabulate_module(module)
    if loop_T is None:
        loop_T = _read_atman_loop_T(path) or 50
    try:
        return translate_pytorch(
            module, runtime_dim=runtime_dim, runtime_seed=runtime_seed,
            loop_max_iterations=loop_T,
        )
    except CodegenNotSupported as exc:
        # The backend can't lower this construct (an unsupported builtin like
        # `snap`, an unsupported node, etc.). `exc` already formats as
        # `line:col: codegen: <message>`; prepend the file path so it reads
        # like every other Sutra diagnostic (`file:line:col: …`) instead of
        # surfacing to the user as an uncaught Python traceback. Single choke
        # point: --run / --emit / runtime-viz all route through here.
        print(f"{path}:{exc}", file=sys.stderr)
        return None


def _run_execute(path: str, *, runtime_dim: int, runtime_seed: int,
                 loop_T: int | None = None, preeval: bool = False,
                 max_preeval_depth: int | None = None) -> int:
    """Compile a .su file with the PyTorch codegen and exec the generated
    module. A `main()` function in the module, if present, is called and
    its return value is printed; otherwise the module's top-level prints
    carry the output. Requires `torch` to be importable at runtime."""
    import types
    py_src = _compile_to_python(
        path, runtime_dim=runtime_dim, runtime_seed=runtime_seed,
        loop_T=loop_T, preeval=preeval, max_preeval_depth=max_preeval_depth,
    )
    if py_src is None:
        return 1
    mod = types.ModuleType("_sutra_run")
    mod.__file__ = f"<generated from {path}>"
    try:
        exec(compile(py_src, mod.__file__, "exec"), mod.__dict__)
        if hasattr(mod, "main") and callable(mod.main):
            result = mod.main()
            if result is not None:
                print(_decode_terminal_result(mod, result))
        else:
            # The substrate program is the body of main(); a file without one
            # has nothing to run. Say so rather than exiting silently with no
            # output (a newcomer otherwise can't tell why nothing happened).
            print(f"{path}: no main() found — nothing to run", file=sys.stderr)
    except Exception as exc:
        # A runtime error in the generated module — e.g. a type mismatch the v0.1
        # validator can't catch yet — should read like a Sutra diagnostic, not an
        # uncaught Python traceback. KeyboardInterrupt / SystemExit are not caught
        # (they subclass BaseException, not Exception), so Ctrl-C still works.
        print(f"{path}: runtime error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


def _decode_terminal_result(mod, result):
    """Terminal/output boundary: decode a `main()` result to a host value for
    display. The language has no scalar-readout accessor (`real()` was removed —
    substrate purity); the host reading the FINAL result for display is the one
    external terminal boundary, the same as printing a returned value in any
    runtime.

    Both a String and a number-vector are 1-D tensors of length `_VSA.dim`; the
    AXIS_STRING_FLAG tells them apart. The string check MUST come first: a String
    stores its codepoints on synthetic axes and the real axis coincides with the
    first codepoint, so a String read as a number prints that char's codepoint
    (e.g. `return "hello world"` would print 104.0 = 'h'). A String decodes to its
    Python text via the sanctioned `string_to_python` terminal decode; a
    number-vector decodes to its real-axis value; anything else prints as-is."""
    try:
        import torch as _t
        vsa = getattr(mod, "_VSA", None)
        if (vsa is not None and isinstance(result, _t.Tensor)
                and result.ndim == 1 and result.shape[0] == vsa.dim):
            if vsa.is_string(result):
                return vsa.string_to_python(result)
            return float(result[vsa.semantic_dim + vsa.AXIS_REAL])
    except Exception:
        pass
    return result


def _run_viz(path: str, *, runtime_dim: int, runtime_seed: int,
             loop_T: int | None = None,
             output_html: str | None = None,
             preeval: bool = False,
             max_preeval_depth: int | None = None) -> int:
    """Compile, execute with tracing, and output a 3D visualization HTML.

    Strategy: inject a tracing shim into the generated Python source that
    wraps every _VSA method. This way tracing is active from the first
    embed() call during module-level init.
    """
    import types
    from .trace import SutraTracer

    py_src = _compile_to_python(
        path, runtime_dim=runtime_dim, runtime_seed=runtime_seed,
        loop_T=loop_T, preeval=preeval, max_preeval_depth=max_preeval_depth,
    )
    if py_src is None:
        return 1

    program_name = os.path.basename(path)
    tracer = SutraTracer(program_name)

    # Inject tracing shim: after the _VSA = _TorchVSA(...) line,
    # wrap every method with a tracing version.
    shim = '''
# ── Tracing shim (injected by --run-viz) ──
_orig_embed = _VSA.embed
_orig_bind = _VSA.bind
_orig_unbind = _VSA.unbind
_orig_bundle = _VSA.bundle

def _traced_embed(name):
    v = _orig_embed(name)
    _tracer.record_vector(name, v, "basis")
    return v

def _traced_bind(a, b):
    result = _orig_bind(a, b)
    _tracer.record_op("bind", [a, b], result)
    return result

def _traced_unbind(role, bound):
    result = _orig_unbind(role, bound)
    _tracer.record_op("unbind", [role, bound], result)
    return result

def _traced_bundle(*vectors):
    result = _orig_bundle(*vectors)
    _tracer.record_op("bundle", list(vectors), result)
    return result

_VSA.embed = _traced_embed
_VSA.bind = _traced_bind
_VSA.unbind = _traced_unbind
_VSA.bundle = _traced_bundle
# ── End tracing shim ──
'''
    # Find the _VSA = _TorchVSA(...) line and inject after it
    lines = py_src.split('\n')
    inject_idx = None
    for i, line in enumerate(lines):
        if line.strip().startswith('_VSA = _TorchVSA('):
            inject_idx = i + 1
            break

    if inject_idx is None:
        print("warning: could not find _VSA init line for tracing", file=sys.stderr)
        inject_idx = len(lines)

    lines.insert(inject_idx, shim)
    traced_src = '\n'.join(lines)

    # Execute with tracer in the namespace
    ns = {"_tracer": tracer}
    exec(compile(traced_src, f"<traced {path}>", "exec"), ns)

    # Run main if it exists
    if "main" in ns and callable(ns["main"]):
        result = ns["main"]()
        if result is not None:
            print(result)

    # Generate output HTML
    if output_html is None:
        output_html = os.path.splitext(path)[0] + "_viz.html"

    html = tracer.to_html()
    with open(output_html, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n3D visualization written to: {output_html}", file=sys.stderr)

    # Also write trace JSON for the VS Code extension
    trace_json = os.path.splitext(path)[0] + "_trace.json"
    with open(trace_json, "w", encoding="utf-8") as f:
        f.write(tracer.to_json())

    return 0


def _run_emit(path: str, *, runtime_dim: int, runtime_seed: int,
              loop_T: int | None = None, preeval: bool = False,
              max_preeval_depth: int | None = None) -> int:
    out = _compile_to_python(
        path, runtime_dim=runtime_dim, runtime_seed=runtime_seed,
        loop_T=loop_T, preeval=preeval, max_preeval_depth=max_preeval_depth,
    )
    if out is None:
        return 1
    sys.stdout.write(out)
    return 0


def _emit_thrml(path: str) -> int:
    """ADDITIVE experimental backend (approach G). Validate + parse the .su, then
    lower it to a thrml/JAX energy-based-sampling program via `codegen_thrml`.
    Entirely separate from the PyTorch path; on an unsupported construct it prints
    a clear `thrml-codegen:` diagnostic and exits 2 (no silent mislowering)."""
    if not os.path.exists(path):
        print(f"{path}: error: file not found", file=sys.stderr)
        return 1
    bag = validate_file(path)
    if bag.errors:
        for d in bag:
            print(d.format(), file=sys.stderr)
        return 1
    with open(path, encoding="utf-8") as fp:
        src = fp.read()
    lexer = Lexer(src, file=path)
    parser = Parser(lexer.tokenize(), file=path, diagnostics=lexer.diagnostics)
    module = parser.parse_module()
    from .codegen_thrml import translate_thrml, ThrmlCodegenNotSupported
    try:
        out = translate_thrml(module)
    except ThrmlCodegenNotSupported as exc:
        print(f"thrml-codegen: {exc}", file=sys.stderr)
        return 2
    sys.stdout.write(out)
    return 0


def main(argv: List[str] | None = None) -> int:
    # `sutrac repl` (or `--repl`) launches the interactive evaluator. Intercepted
    # before argparse because the validator requires a `paths` positional and the
    # REPL takes no file.
    _args = argv if argv is not None else sys.argv[1:]
    if _args and _args[0] in ("repl", "--repl"):
        from .repl import main_repl
        return main_repl()

    parser = argparse.ArgumentParser(
        prog="sutrac",
        description="Validate Sutra (.su) source files.",
    )
    parser.add_argument(
        "paths",
        nargs="+",
        help="Files or directories to validate. Directories are walked recursively.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable diagnostics as JSON. For editors and language servers.",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print a per-file summary table instead of individual diagnostics.",
    )
    parser.add_argument(
        "--consistency",
        action="store_true",
        help="Cross-file check: report class names that appear in multiple casings across the file set.",
    )
    parser.add_argument(
        "--emit",
        action="store_true",
        help=(
            "Compile the first input file to self-contained torch Python and "
            "print it to stdout. Picks CUDA at module init if available; "
            "falls back to CPU otherwise. This is the one main codegen target — "
            "PyTorch is the runtime and the tensor-op library Sutra compiles "
            "against."
        ),
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help=(
            "Compile and execute the first input file (PyTorch backend) in "
            "one step. Captures and prints whatever the generated module "
            "prints. Requires torch to be importable."
        ),
    )
    parser.add_argument(
        "--emit-thrml",
        action="store_true",
        help=(
            "ADDITIVE, EXPERIMENTAL alternative backend. Compile the first input "
            "file to a thrml/JAX energy-based-sampling program and print it to "
            "stdout. The default PyTorch path (--emit/--run) is untouched; this is "
            "the Extropic thermodynamic-sampling compile target (queue.md approach "
            "G). Requires jax + the thrml submodule. Lowering coverage is the "
            "validated subset only — see codegen_thrml.py."
        ),
    )
    parser.add_argument(
        "--run-viz",
        action="store_true",
        help=(
            "Compile and execute with tracing, then generate a standalone "
            "Three.js 3D visualization HTML alongside the program output."
        ),
    )
    parser.add_argument(
        "--review",
        action="store_true",
        help=(
            "Step-by-step review mode: show source, parsed AST, "
            "inlined AST, every simplification rewrite that fires "
            "(before/after), final simplified AST, and emitted Python. "
            "For debugging and teaching."
        ),
    )
    parser.add_argument(
        "--runtime-dim", type=int, default=50,
        help="Hypervector dimension for the emitted runtime (default 50).",
    )
    parser.add_argument(
        "--runtime-seed", type=int, default=42,
        help="Random seed for the emitted runtime (default 42).",
    )
    parser.add_argument(
        "--loop-T", type=int, default=None,
        help=(
            "Maximum compile-time loop unroll depth (T) for "
            "tail-recursive loop functions and the soft-halt RNN cell. "
            "If unset, the compiler reads the value from the nearest "
            "[project.compile] loop_max_iterations field in atman.toml, "
            "and falls back to 50 if no manifest declares it. The "
            "soft-halt cell freezes state once halt-cum saturates, so "
            "larger T costs only a longer emitted graph, not extra "
            "runtime work."
        ),
    )
    parser.add_argument(
        "--preeval", action="store_true",
        help=(
            "Raise the compile-time pre-evaluation cap to a DEEP value (folds deeper "
            "bounded pure recursion into literals). Pre-evaluation runs by default at a "
            "shallow depth (~3); this opts into deep folding. --max-preeval-depth overrides."
        ),
    )
    parser.add_argument(
        "--max-preeval-depth", type=int, default=None,
        help=(
            "Recursion-depth cap for compile-time pre-evaluation (Phase 5.5 tier 3). "
            "Default is a shallow ~3 (read from [project.compile] max_preeval_depth in "
            "atman.toml if set; --preeval bumps it deep). 0 disables pre-evaluation; "
            "larger values fold deeper recursion (kept within the host evaluator's stack)."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"sutrac {__version__}",
    )
    args = parser.parse_args(argv)
    if args.review:
        if len(args.paths) != 1:
            print(
                "--review takes exactly one .su source file",
                file=sys.stderr,
            )
            return 2
        from .review import review_file
        return review_file(args.paths[0])
    if args.emit_thrml:
        # Additive experimental backend — entirely separate from the PyTorch
        # path below, which is untouched (approach G, non-destructive).
        if len(args.paths) != 1:
            print("--emit-thrml takes exactly one .su source file", file=sys.stderr)
            return 2
        return _emit_thrml(args.paths[0])
    if args.emit or args.run or args.run_viz:
        if len(args.paths) != 1:
            print(
                "--emit/--run/--run-viz takes exactly one .su source file",
                file=sys.stderr,
            )
            return 2
        if args.run_viz:
            return _run_viz(
                args.paths[0],
                runtime_dim=args.runtime_dim,
                runtime_seed=args.runtime_seed,
                loop_T=args.loop_T,
                preeval=args.preeval,
                max_preeval_depth=args.max_preeval_depth,
            )
        if args.run:
            return _run_execute(
                args.paths[0],
                runtime_dim=args.runtime_dim,
                runtime_seed=args.runtime_seed,
                loop_T=args.loop_T,
                preeval=args.preeval,
                max_preeval_depth=args.max_preeval_depth,
            )
        return _run_emit(
            args.paths[0],
            runtime_dim=args.runtime_dim,
            runtime_seed=args.runtime_seed,
            loop_T=args.loop_T,
            preeval=args.preeval,
            max_preeval_depth=args.max_preeval_depth,
        )
    if args.json:
        return _run_json(args.paths)
    if args.consistency:
        return _run_consistency(args.paths)
    return _run_text(args.paths, summary=args.summary)


if __name__ == "__main__":
    sys.exit(main())
