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
from .codegen_flybrain import CodegenNotSupported
from .codegen_flybrain import translate_module as translate_flybrain
from .codegen_numpy import translate_module as translate_numpy
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


def _compile_to_python(path: str, backend: str, *, runtime_dim: int,
                       runtime_seed: int, runtime_n_kc: int) -> str | None:
    """Validate + parse + codegen one .su file. Returns generated Python
    source, or None on failure (diagnostics already printed)."""
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
    try:
        if backend == "numpy":
            return translate_numpy(
                module, runtime_dim=runtime_dim, runtime_seed=runtime_seed,
            )
        return translate_flybrain(
            module, runtime_dim=runtime_dim, runtime_seed=runtime_seed,
            runtime_n_kc=runtime_n_kc,
        )
    except CodegenNotSupported as exc:
        print(f"{path}:{exc}", file=sys.stderr)
        return None


def _run_execute(path: str, *, runtime_dim: int, runtime_seed: int) -> int:
    """Compile a .su file with the numpy backend and exec the generated
    module. A `main()` function in the module, if present, is called and
    its return value is printed; otherwise the module's top-level prints
    carry the output."""
    import types
    py_src = _compile_to_python(
        path, "numpy", runtime_dim=runtime_dim, runtime_seed=runtime_seed,
        runtime_n_kc=0,
    )
    if py_src is None:
        return 1
    mod = types.ModuleType("_sutra_run")
    mod.__file__ = f"<generated from {path}>"
    exec(compile(py_src, mod.__file__, "exec"), mod.__dict__)
    if hasattr(mod, "main") and callable(mod.main):
        result = mod.main()
        if result is not None:
            print(result)
    return 0


def _run_viz(path: str, *, runtime_dim: int, runtime_seed: int,
             output_html: str | None = None) -> int:
    """Compile, execute with tracing, and output a 3D visualization HTML.

    Strategy: inject a tracing shim into the generated Python source that
    wraps every _NumpyVSA method. This way tracing is active from the
    first embed() call during module-level init.
    """
    import types
    from .trace import SutraTracer

    py_src = _compile_to_python(
        path, "numpy", runtime_dim=runtime_dim, runtime_seed=runtime_seed,
        runtime_n_kc=0,
    )
    if py_src is None:
        return 1

    program_name = os.path.basename(path)
    tracer = SutraTracer(program_name)

    # Inject tracing shim: after the _VSA = _NumpyVSA(...) line,
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
    # Find the _VSA = _NumpyVSA(...) line and inject after it
    lines = py_src.split('\n')
    inject_idx = None
    for i, line in enumerate(lines):
        if line.strip().startswith('_VSA = _NumpyVSA('):
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


def _run_emit(path: str, backend: str, *, runtime_dim: int, runtime_seed: int,
              runtime_n_kc: int) -> int:
    out = _compile_to_python(
        path, backend, runtime_dim=runtime_dim, runtime_seed=runtime_seed,
        runtime_n_kc=runtime_n_kc,
    )
    if out is None:
        return 1
    sys.stdout.write(out)
    return 0


def main(argv: List[str] | None = None) -> int:
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
        "--emit-flybrain",
        action="store_true",
        help=(
            "Compile the first input file to Python targeting the FlyBrainVSA "
            "runtime and print it to stdout. Fly-brain-only work — the demo "
            "path is --emit-numpy."
        ),
    )
    parser.add_argument(
        "--emit-numpy",
        action="store_true",
        help=(
            "Compile the first input file to self-contained numpy Python and "
            "print it to stdout. This is the demo-path backend: no fly-brain "
            "imports, no spiking simulator, ops run as plain matrix operations."
        ),
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help=(
            "Compile and execute the first input file (numpy backend) in one "
            "step. Captures and prints whatever the generated module prints."
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
        "--runtime-dim", type=int, default=50,
        help="Hypervector dimension for the emitted FlyBrainVSA runtime (default 50).",
    )
    parser.add_argument(
        "--runtime-seed", type=int, default=42,
        help="Random seed for the emitted FlyBrainVSA runtime (default 42).",
    )
    parser.add_argument(
        "--runtime-n-kc", type=int, default=2000,
        help="Number of Kenyon cells in the emitted mushroom body (default 2000).",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"sutrac {__version__}",
    )
    args = parser.parse_args(argv)
    if args.emit_flybrain or args.emit_numpy or args.run or args.run_viz:
        if len(args.paths) != 1:
            print(
                "--emit-*/--run/--run-viz takes exactly one .su source file",
                file=sys.stderr,
            )
            return 2
        backend = "flybrain" if args.emit_flybrain else "numpy"
        if args.run_viz:
            return _run_viz(
                args.paths[0],
                runtime_dim=args.runtime_dim,
                runtime_seed=args.runtime_seed,
            )
        if args.run:
            return _run_execute(
                args.paths[0],
                runtime_dim=args.runtime_dim,
                runtime_seed=args.runtime_seed,
            )
        return _run_emit(
            args.paths[0], backend,
            runtime_dim=args.runtime_dim,
            runtime_seed=args.runtime_seed,
            runtime_n_kc=args.runtime_n_kc,
        )
    if args.json:
        return _run_json(args.paths)
    if args.consistency:
        return _run_consistency(args.paths)
    return _run_text(args.paths, summary=args.summary)


if __name__ == "__main__":
    sys.exit(main())
