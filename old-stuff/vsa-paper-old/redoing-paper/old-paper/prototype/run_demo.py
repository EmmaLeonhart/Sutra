"""Entry point: run both pipelines and print side-by-side comparison.

Usage:
    python prototype/run_demo.py                          # original demo
    python prototype/run_demo.py --benchmark              # full 7-scenario suite
    python prototype/run_demo.py --benchmark --save-json results.json
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time

# Ensure project root is on sys.path so `python prototype/run_demo.py` works
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Windows Unicode fix
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from prototype.knowledge_base import (
    CORPUS,
    EXPECTED_ANSWER_KEYWORDS,
    GROUND_TRUTH_CHAIN,
    QUERY,
    ground_truth_coverage,
)
from prototype.neurosymbolic_rag import run_neurosymbolic_rag
from prototype.standard_rag import run_standard_rag


def _strip_think_tags(text: str) -> str:
    """Remove <think>...</think> blocks from deepseek-r1 output."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def _keyword_hit(answer: str, keywords: list[str]) -> bool:
    """Check if the answer contains any expected keyword."""
    lower = answer.lower()
    return any(kw.lower() in lower for kw in keywords)


def main():
    parser = argparse.ArgumentParser(
        description="Neurosymbolic GraphRAG demo and benchmark"
    )
    parser.add_argument(
        "--benchmark", action="store_true",
        help="Run the full multi-scenario benchmark suite"
    )
    parser.add_argument(
        "--save-json", type=str, default=None,
        help="Save benchmark results to a JSON file (requires --benchmark)"
    )
    parser.add_argument(
        "--scenario", type=str, default=None,
        help="Run a single benchmark scenario by ID (requires --benchmark)"
    )
    args = parser.parse_args()

    if args.benchmark:
        from prototype.benchmark import run_benchmark
        from prototype.scenarios import get_scenario
        scenarios = [get_scenario(args.scenario)] if args.scenario else None
        run_benchmark(scenarios=scenarios, save_json=args.save_json)
        return

    print("=" * 70)
    print("  NEUROSYMBOLIC GraphRAG vs STANDARD RAG — Demo Comparison")
    print("=" * 70)
    print(f"\nQuery: {QUERY}")
    print(f"Corpus: {len(CORPUS)} sentences "
          f"({len(GROUND_TRUTH_CHAIN)} ground-truth, "
          f"{len(CORPUS) - len(GROUND_TRUTH_CHAIN)} distractors)")
    print(f"Expected answer keywords: {EXPECTED_ANSWER_KEYWORDS}")

    # ── Run Standard RAG ──────────────────────────────────────────────────
    t0 = time.time()
    std_result = run_standard_rag(QUERY, CORPUS, top_k=5)
    std_time = time.time() - t0

    # ── Run Neurosymbolic RAG ─────────────────────────────────────────────
    t0 = time.time()
    ns_result = run_neurosymbolic_rag(QUERY, CORPUS)
    ns_time = time.time() - t0

    # ── Comparison ────────────────────────────────────────────────────────
    std_coverage = ground_truth_coverage(std_result.retrieved_texts)
    ns_coverage = ground_truth_coverage(ns_result.pruned_sources)

    std_answer_clean = _strip_think_tags(std_result.answer)
    ns_answer_clean = _strip_think_tags(ns_result.answer)

    std_correct = _keyword_hit(std_answer_clean, EXPECTED_ANSWER_KEYWORDS)
    ns_correct = _keyword_hit(ns_answer_clean, EXPECTED_ANSWER_KEYWORDS)

    print("\n" + "=" * 70)
    print("  RESULTS COMPARISON")
    print("=" * 70)

    print("\n--- Standard RAG ---")
    print(f"  Retrieved {len(std_result.retrieved_texts)} sentences")
    print(f"  Ground truth coverage: {std_coverage:.0%} "
          f"({int(std_coverage * len(GROUND_TRUTH_CHAIN))}/{len(GROUND_TRUTH_CHAIN)})")
    print(f"  Answer contains expected keywords: {std_correct}")
    print(f"  Time: {std_time:.1f}s")
    print(f"  Answer: {std_answer_clean[:200]}")

    print("\n--- Neurosymbolic RAG ---")
    print(f"  Propositions extracted: {len(ns_result.propositions)}")
    print(f"  VKG size: {ns_result.vkg.nx_graph.number_of_nodes()} nodes, "
          f"{ns_result.vkg.nx_graph.number_of_edges()} edges")
    print(f"  Reasoning chains found: {len(ns_result.chains)}")
    print(f"  Pruned sources: {len(ns_result.pruned_sources)}")
    print(f"  Ground truth coverage: {ns_coverage:.0%} "
          f"({int(ns_coverage * len(GROUND_TRUTH_CHAIN))}/{len(GROUND_TRUTH_CHAIN)})")
    print(f"  Answer contains expected keywords: {ns_correct}")
    print(f"  Time: {ns_time:.1f}s")
    print(f"  Answer: {ns_answer_clean[:200]}")

    print("\n--- Ground Truth ---")
    for i, gt in enumerate(GROUND_TRUTH_CHAIN):
        in_std = gt in std_result.retrieved_texts
        in_ns = gt in ns_result.pruned_sources
        std_mark = "[x]" if in_std else "[ ]"
        ns_mark = "[x]" if in_ns else "[ ]"
        print(f"  {i + 1}. Std {std_mark}  NS {ns_mark}  {gt[:70]}")

    print("\n" + "=" * 70)
    print(f"  Standard RAG coverage: {std_coverage:.0%}  |  "
          f"Neurosymbolic RAG coverage: {ns_coverage:.0%}")
    if ns_coverage > std_coverage:
        print("  >> Neurosymbolic RAG retrieved more of the reasoning chain!")
    print("=" * 70)


if __name__ == "__main__":
    main()
