"""Neurosymbolic RAG — full pipeline orchestrating all 3 pillars.

Pillar 1: Extract propositions from corpus
Pillar 2: Build VKG via entity bridging
Pillar 3: Discover reasoning chains, prune, format context
Then: Send grounded context to LLM for answer generation
"""

from __future__ import annotations

from dataclasses import dataclass, field

import re

import ollama

from prototype.pillar1_extraction import Proposition, extract_all


def _strip_think(text: str) -> str:
    """Remove <think>...</think> blocks from deepseek-r1 output."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
from prototype.pillar2_mapping import VKG, build_vkg
from prototype.pillar3_logic import (
    ReasoningChain,
    detect_contradictions,
    find_reasoning_chains,
    format_grounded_context,
    prune_irrelevant,
)

LLM_MODEL = "deepseek-r1:8b"

ANSWER_PROMPT = """\
You are a precise reasoning assistant. Answer the question using the
structured reasoning chain and facts provided below. Follow the logical
steps to derive your answer.

{grounded_context}

Question: {query}

Provide a clear, concise answer that follows the reasoning chain above.
Answer:"""


@dataclass
class NeurosymbolicRAGResult:
    propositions: list[Proposition]
    vkg: VKG
    chains: list[ReasoningChain]
    contradictions: list[str]
    pruned_sources: list[str]
    grounded_context: str
    answer: str


def run_neurosymbolic_rag(
    query: str,
    corpus: list[str],
    top_k_seed: int = 4,
    bridge_threshold_ratio: float = 0.6,
) -> NeurosymbolicRAGResult:
    """Run the full neurosymbolic RAG pipeline."""
    print("\n" + "=" * 60)
    print("NEUROSYMBOLIC RAG (VKG + logic-gated retrieval)")
    print("=" * 60)

    # ── Pillar 1: Extract propositions ────────────────────────────────────
    print("\n--- Pillar 1: Propositional Extraction ---")
    propositions = extract_all(corpus)
    print(f"\n  Total propositions extracted: {len(propositions)}")

    # ── Pillar 2: Build VKG ───────────────────────────────────────────────
    print("\n--- Pillar 2: VKG Construction ---")
    vkg = build_vkg(
        query=query,
        propositions=propositions,
        corpus=corpus,
        top_k_seed=top_k_seed,
        bridge_threshold_ratio=bridge_threshold_ratio,
    )
    print(f"  Graph nodes: {vkg.nx_graph.number_of_nodes()}")
    print(f"  Graph edges: {vkg.nx_graph.number_of_edges()}")

    # ── Pillar 3: Logic engine ────────────────────────────────────────────
    print("\n--- Pillar 3: Logic Engine ---")
    chains = find_reasoning_chains(vkg)
    contradictions = detect_contradictions(vkg)
    pruned = prune_irrelevant(vkg, chains)

    print(f"  Reasoning chains found: {len(chains)}")
    if chains:
        print(f"  Best chain ({len(chains[0].steps)} steps):")
        for i, step in enumerate(chains[0].steps, 1):
            print(f"    {i}. {step[:80]}")

    if contradictions:
        print(f"  Contradictions detected: {len(contradictions)}")

    print(f"  Pruned context: {len(pruned)} relevant source texts")

    # ── Format and generate answer ────────────────────────────────────────
    grounded_context = format_grounded_context(chains, pruned)
    prompt = ANSWER_PROMPT.format(
        grounded_context=grounded_context, query=query
    )

    print("\n  Generating answer with grounded context...")
    try:
        response = ollama.chat(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.3, "num_predict": 1024},
        )
        answer = _strip_think(response["message"]["content"])
    except Exception as e:
        answer = f"[LLM error: {e}]"

    return NeurosymbolicRAGResult(
        propositions=propositions,
        vkg=vkg,
        chains=chains,
        contradictions=contradictions,
        pruned_sources=pruned,
        grounded_context=grounded_context,
        answer=answer,
    )
