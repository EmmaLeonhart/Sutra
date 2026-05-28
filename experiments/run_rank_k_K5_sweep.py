"""Python wrapper for the K=5 rank-k sweep — k in {1, 2, 4}, n=3, 20 epochs.

Avoids the shell `;`-chain wrapper that the prior background launch
(`bodzn9d6y`, 2026-05-28) exited at 127 with no salvageable runlog. A
single Python invocation runs all three k values sequentially; each
k's stdout+stderr go to a dated runlog under experiments/runlogs/;
the wrapper continues past a per-k failure rather than stopping the
sweep.

Usage:
    python experiments/run_rank_k_K5_sweep.py

Output (UTC date YYYY-MM-DD):
    experiments/runlogs/YYYY-MM-DD-rank-k-K5-k1-n3.txt
    experiments/runlogs/YYYY-MM-DD-rank-k-K5-k2-n3.txt
    experiments/runlogs/YYYY-MM-DD-rank-k-K5-k4-n3.txt
    experiments/runlogs/YYYY-MM-DD-rank-k-K5-summary.txt
"""
from __future__ import annotations

import datetime
import os
import subprocess
import sys
import time


REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RUNLOGS = os.path.join(REPO, "experiments", "runlogs")
K_VALUES = [1, 2, 4]
SEEDS = "0,1,2"
EPOCHS = 20


def main() -> int:
    os.makedirs(RUNLOGS, exist_ok=True)
    date_utc = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d")
    summary_path = os.path.join(RUNLOGS, f"{date_utc}-rank-k-K5-summary.txt")

    summary_lines: list[str] = []
    summary_lines.append(f"K=5 rank-k sweep launched at {datetime.datetime.now(datetime.UTC).isoformat()} UTC")
    summary_lines.append(f"K=5, k in {K_VALUES}, seeds={SEEDS}, epochs={EPOCHS}")
    summary_lines.append("")

    overall_t0 = time.time()
    for k in K_VALUES:
        runlog = os.path.join(RUNLOGS, f"{date_utc}-rank-k-K5-k{k}-n3.txt")
        cmd = [
            sys.executable,
            os.path.join(REPO, "experiments", "rank_k_is_x.py"),
            "--K", "5",
            "--k", str(k),
            "--seeds", SEEDS,
            "--epochs", str(EPOCHS),
        ]
        t0 = time.time()
        line = f"[k={k}] launching: {' '.join(cmd)}  -> {runlog}"
        print(line, flush=True)
        summary_lines.append(line)

        with open(runlog, "w", encoding="utf-8") as f:
            result = subprocess.run(
                cmd,
                stdout=f,
                stderr=subprocess.STDOUT,
                cwd=REPO,
            )
        wall = time.time() - t0
        line = f"[k={k}] exit={result.returncode}  wall={wall:.1f}s  log={runlog}"
        print(line, flush=True)
        summary_lines.append(line)

        if result.returncode != 0:
            summary_lines.append(f"  ⚠️  k={k} failed; continuing to next k")
        # Append the runlog's last 30 lines into the summary for quick inspection.
        try:
            with open(runlog, "r", encoding="utf-8", errors="replace") as f:
                tail = f.readlines()[-30:]
            summary_lines.append("  --- last 30 lines of runlog ---")
            summary_lines.extend("  " + ln.rstrip() for ln in tail)
            summary_lines.append("  --- end runlog tail ---")
            summary_lines.append("")
        except OSError as e:
            summary_lines.append(f"  could not read runlog tail: {e}")

    summary_lines.append("")
    summary_lines.append(f"total wall: {time.time() - overall_t0:.1f}s")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("\n".join(summary_lines) + "\n")
    print(f"summary -> {summary_path}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
