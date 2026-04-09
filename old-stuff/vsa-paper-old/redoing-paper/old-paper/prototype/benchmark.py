"""Benchmark runner — evaluates Neurosymbolic vs Standard RAG across scenarios.

Runs each scenario through both pipelines and produces rich console output
plus optional JSON export.

Usage:
    python prototype/benchmark.py                        # full 7-scenario suite
    python prototype/benchmark.py --scenario everest_boiling  # single scenario
    python prototype/benchmark.py --save-json results.json    # export results
    python prototype/benchmark.py --quiet                     # summary only
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, field

# Ensure project root is on sys.path
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Windows Unicode fix
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from prototype.neurosymbolic_rag import run_neurosymbolic_rag
from prototype.scenarios import SCENARIOS, Scenario, get_scenario
from prototype.standard_rag import run_standard_rag


def _strip_think(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def _keyword_hit(answer: str, keywords: list[str]) -> bool:
    lower = answer.lower()
    return any(kw.lower() in lower for kw in keywords)


# ── Result dataclasses ────────────────────────────────────────────────────────

@dataclass
class ScenarioResult:
    scenario_id: str
    scenario_name: str
    chain_length: int
    failure_mode: str
    # Standard RAG
    std_coverage: float
    std_coverage_hits: int
    std_keyword_hit: bool
    std_time: float
    std_retrieved_count: int
    # Neurosymbolic RAG
    ns_coverage: float
    ns_coverage_hits: int
    ns_keyword_hit: bool
    ns_time: float
    ns_propositions: int
    ns_chains: int
    ns_pruned_count: int
    # Derived
    coverage_delta: float = 0.0
    winner: str = ""

    def __post_init__(self):
        self.coverage_delta = self.ns_coverage - self.std_coverage
        if self.ns_coverage > self.std_coverage:
            self.winner = "NS"
        elif self.std_coverage > self.ns_coverage:
            self.winner = "Std"
        else:
            self.winner = "Tie"


@dataclass
class BenchmarkSummary:
    results: list[ScenarioResult] = field(default_factory=list)
    total_time: float = 0.0

    @property
    def mean_std_coverage(self) -> float:
        if not self.results:
            return 0.0
        return sum(r.std_coverage for r in self.results) / len(self.results)

    @property
    def mean_ns_coverage(self) -> float:
        if not self.results:
            return 0.0
        return sum(r.ns_coverage for r in self.results) / len(self.results)

    @property
    def mean_coverage_delta(self) -> float:
        return self.mean_ns_coverage - self.mean_std_coverage

    @property
    def ns_coverage_wins(self) -> int:
        return sum(1 for r in self.results if r.winner == "NS")

    @property
    def ns_keyword_wins(self) -> int:
        return sum(1 for r in self.results
                   if r.ns_keyword_hit and not r.std_keyword_hit)

    @property
    def total_std_time(self) -> float:
        return sum(r.std_time for r in self.results)

    @property
    def total_ns_time(self) -> float:
        return sum(r.ns_time for r in self.results)

    def to_dict(self) -> dict:
        return {
            "scenarios": [asdict(r) for r in self.results],
            "aggregate": {
                "num_scenarios": len(self.results),
                "mean_std_coverage": round(self.mean_std_coverage, 4),
                "mean_ns_coverage": round(self.mean_ns_coverage, 4),
                "mean_coverage_delta": round(self.mean_coverage_delta, 4),
                "ns_coverage_wins": self.ns_coverage_wins,
                "ns_keyword_wins": self.ns_keyword_wins,
                "total_std_time_s": round(self.total_std_time, 1),
                "total_ns_time_s": round(self.total_ns_time, 1),
                "total_time_s": round(self.total_time, 1),
            },
        }


# ── Core benchmark logic ─────────────────────────────────────────────────────

def _run_scenario(scenario: Scenario, verbose: bool = True) -> ScenarioResult:
    """Run both pipelines on a single scenario and return metrics."""

    # ── Standard RAG ──
    t0 = time.time()
    std_result = run_standard_rag(scenario.query, scenario.corpus, top_k=5)
    std_time = time.time() - t0

    # ── Neurosymbolic RAG ──
    t0 = time.time()
    ns_result = run_neurosymbolic_rag(scenario.query, scenario.corpus)
    ns_time = time.time() - t0

    # ── Metrics ──
    std_coverage = scenario.ground_truth_coverage(std_result.retrieved_texts)
    ns_coverage = scenario.ground_truth_coverage(ns_result.pruned_sources)

    std_answer = _strip_think(std_result.answer)
    ns_answer = _strip_think(ns_result.answer)

    return ScenarioResult(
        scenario_id=scenario.id,
        scenario_name=scenario.name,
        chain_length=scenario.chain_length,
        failure_mode=scenario.failure_mode,
        std_coverage=std_coverage,
        std_coverage_hits=int(std_coverage * scenario.chain_length),
        std_keyword_hit=_keyword_hit(std_answer, scenario.expected_answer_keywords),
        std_time=std_time,
        std_retrieved_count=len(std_result.retrieved_texts),
        ns_coverage=ns_coverage,
        ns_coverage_hits=int(ns_coverage * scenario.chain_length),
        ns_keyword_hit=_keyword_hit(ns_answer, scenario.expected_answer_keywords),
        ns_time=ns_time,
        ns_propositions=len(ns_result.propositions),
        ns_chains=len(ns_result.chains),
        ns_pruned_count=len(ns_result.pruned_sources),
    )


def run_benchmark(
    scenarios: list[Scenario] | None = None,
    save_json: str | None = None,
    verbose: bool = True,
) -> BenchmarkSummary:
    """Run the full benchmark suite and print results."""
    if scenarios is None:
        scenarios = SCENARIOS

    n = len(scenarios)
    summary = BenchmarkSummary()

    print("=" * 70)
    print(f"  BENCHMARK: Neurosymbolic GraphRAG vs Standard RAG ({n} scenarios)")
    print("=" * 70)

    t_total = time.time()

    for i, scenario in enumerate(scenarios, 1):
        # ── Per-scenario header ──
        print(f"\n{'━' * 3} SCENARIO {i}/{n}: {scenario.name} {'━' * 3}")
        print(f"  Query: \"{scenario.query}\"")
        print(f"  Chain: {scenario.chain_length} hops | "
              f"Failure mode: {scenario.failure_mode}")
        print(f"  Corpus: {len(scenario.corpus)} sentences "
              f"({scenario.chain_length} ground-truth, "
              f"{len(scenario.corpus) - scenario.chain_length} distractors)")

        result = _run_scenario(scenario, verbose=verbose)
        summary.results.append(result)

        # ── Per-scenario results ──
        print(f"\n  Standard RAG:   Coverage {result.std_coverage:.0%} "
              f"({result.std_coverage_hits}/{result.chain_length})  "
              f"Keywords: {'YES' if result.std_keyword_hit else 'NO'}   "
              f"Time: {result.std_time:.1f}s")
        print(f"  Neurosymbolic:  Coverage {result.ns_coverage:.0%} "
              f"({result.ns_coverage_hits}/{result.chain_length})  "
              f"Keywords: {'YES' if result.ns_keyword_hit else 'NO'}   "
              f"Time: {result.ns_time:.1f}s")

        delta = result.coverage_delta
        if delta > 0:
            print(f"  >> NEUROSYMBOLIC WINS (+{delta:.0%} coverage)")
        elif delta < 0:
            print(f"  >> STANDARD RAG WINS ({delta:+.0%} coverage)")
        else:
            print(f"  >> TIE (both {result.std_coverage:.0%})")

    summary.total_time = time.time() - t_total

    # ── Summary table ──
    _print_summary_table(summary)

    # ── Aggregate stats ──
    _print_aggregate_stats(summary)

    # ── JSON export ──
    if save_json:
        with open(save_json, "w", encoding="utf-8") as f:
            json.dump(summary.to_dict(), f, indent=2)
        print(f"\nResults saved to: {save_json}")

    return summary


def _print_summary_table(summary: BenchmarkSummary) -> None:
    """Print the comparative results table."""
    print(f"\n{'=' * 70}")
    print("  SUMMARY TABLE")
    print("=" * 70)

    header = (f"  {'Scenario':<30s} | {'Std':>5s} | {'NS':>5s} | "
              f"{'Delta':>6s} | {'Winner':>6s}")
    print(header)
    print(f"  {'-' * 30}-+-{'-' * 5}-+-{'-' * 5}-+-{'-' * 6}-+-{'-' * 6}")

    for r in summary.results:
        print(f"  {r.scenario_name:<30s} | {r.std_coverage:>4.0%} | "
              f"{r.ns_coverage:>4.0%} | {r.coverage_delta:>+5.0%} | "
              f"{r.winner:>6s}")


def _print_aggregate_stats(summary: BenchmarkSummary) -> None:
    """Print aggregate benchmark statistics."""
    n = len(summary.results)
    print(f"\n{'=' * 70}")
    print("  AGGREGATE STATISTICS")
    print("=" * 70)

    print(f"  Mean Coverage:  Std {summary.mean_std_coverage:.0%}  |  "
          f"NS {summary.mean_ns_coverage:.0%}  |  "
          f"Delta {summary.mean_coverage_delta:+.0%}")

    ns_cov_wins = summary.ns_coverage_wins
    ns_kw_wins = summary.ns_keyword_wins
    print(f"  NS Wins: {ns_cov_wins}/{n} (coverage)  |  "
          f"{ns_kw_wins}/{n} (keywords)")

    std_t = summary.total_std_time
    ns_t = summary.total_ns_time
    overhead = ns_t / std_t if std_t > 0 else float("inf")
    print(f"  Time: Std {std_t:.0f}s  |  NS {ns_t:.0f}s  |  "
          f"Overhead {overhead:.1f}x")
    print(f"  Total wall time: {summary.total_time:.0f}s")
    print("=" * 70)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Benchmark Neurosymbolic GraphRAG vs Standard RAG"
    )
    parser.add_argument(
        "--scenario", type=str, default=None,
        help="Run a single scenario by ID (e.g. 'drug_interaction')"
    )
    parser.add_argument(
        "--save-json", type=str, default=None,
        help="Save results to a JSON file"
    )
    parser.add_argument(
        "--quiet", action="store_true",
        help="Suppress per-sentence pipeline output (show only results)"
    )
    args = parser.parse_args()

    if args.scenario:
        scenarios = [get_scenario(args.scenario)]
    else:
        scenarios = None  # all

    run_benchmark(
        scenarios=scenarios,
        save_json=args.save_json,
        verbose=not args.quiet,
    )


if __name__ == "__main__":
    main()
