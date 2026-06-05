#!/usr/bin/env python3
"""CI entry point for the Percepta transformer-vm replication.

Runs the authors' reproduction recipe (`uv run wasm-run`) against the
`replication_target/transformer-vm` submodule, parses the per-program results
from the C++ inference engine, and writes `results/metrics.json`.

The headline claim being checked: a transformer whose weights are computed
analytically (not trained) reproduces the reference WASM execution traces
token-for-token (every program reports PASS), at tens of thousands of tokens/sec.

Usage:
    python scripts/run.py                 # run all manifest programs
    python scripts/run.py --skip-slow     # drop sudoku (the ~1M-token program)

Exit code is non-zero if any program FAILs or the engine could not be built.
This script assumes the toolchain is already present (uv, clang+wasm32, g++);
see scripts/wsl_setup.sh / the CI workflow for provisioning.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
VM = REPO / "replication_target" / "transformer-vm"
RESULTS = REPO / "results"

# e.g. "collatz: PASS  44589 tok, 9009 ops in 2.03s (22002 tok/s)"
LINE_RE = re.compile(
    r"^(?P<name>\w+):\s+(?P<status>PASS|FAIL)\s+"
    r"(?P<tokens>\d+) tok,\s+(?P<ops>\d+) ops in\s+(?P<secs>[\d.]+)s\s+"
    r"\((?P<tok_s>\d+) tok/s\)"
)
SLOW_PROGRAMS = {"sudoku"}


def run_recipe(skip_slow: bool) -> tuple[str, int]:
    """Run `uv run wasm-run` in the submodule, return (combined_output, returncode)."""
    if not VM.exists():
        sys.exit(f"submodule missing: {VM} (run `git submodule update --init`)")
    cmd = ["uv", "run", "wasm-run"]
    env = dict(os.environ)
    env["PATH"] = f"{Path.home()/'.local'/'bin'}{os.pathsep}{env.get('PATH','')}"
    proc = subprocess.run(
        cmd, cwd=VM, env=env, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    return proc.stdout, proc.returncode


def parse(output: str) -> list[dict]:
    programs = []
    for line in output.splitlines():
        m = LINE_RE.match(line.strip())
        if not m:
            continue
        programs.append({
            "program": m["name"],
            "status": m["status"],
            "tokens": int(m["tokens"]),
            "ops": int(m["ops"]),
            "seconds": float(m["secs"]),
            "tokens_per_second": int(m["tok_s"]),
        })
    return programs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-slow", action="store_true",
                    help="drop the ~1M-token sudoku program (for fast CI)")
    args = ap.parse_args()

    output, rc = run_recipe(args.skip_slow)
    programs = parse(output)
    if args.skip_slow:
        programs = [p for p in programs if p["program"] not in SLOW_PROGRAMS]

    passed = [p for p in programs if p["status"] == "PASS"]
    failed = [p for p in programs if p["status"] != "PASS"]
    tputs = [p["tokens_per_second"] for p in programs if p["tokens_per_second"]]

    metrics = {
        "target": "Percepta/transformer-vm",
        "submodule_commit": _submodule_sha(),
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "recipe": "uv run wasm-run",
        "n_programs": len(programs),
        "n_pass": len(passed),
        "n_fail": len(failed),
        "all_pass": len(programs) > 0 and not failed,
        "throughput_tok_s": {
            "min": min(tputs) if tputs else None,
            "max": max(tputs) if tputs else None,
            "mean": round(sum(tputs) / len(tputs)) if tputs else None,
        },
        "programs": programs,
        "engine_returncode": rc,
    }

    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "metrics.json").write_text(json.dumps(metrics, indent=2))
    print(json.dumps(metrics, indent=2))

    if not metrics["all_pass"]:
        print(f"\nFAIL: {len(failed)} program(s) did not pass", file=sys.stderr)
        return 1
    print(f"\nOK: {len(passed)}/{len(programs)} programs PASS")
    return 0


def _submodule_sha() -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=VM, text=True,
            capture_output=True, check=True,
        ).stdout.strip()
    except Exception:
        return None


if __name__ == "__main__":
    raise SystemExit(main())
