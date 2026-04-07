"""Standard RAG baseline — vector similarity retrieval only.

Retrieves top-k corpus sentences by cosine similarity and sends them
as context to the LLM. No entity bridging, no logic gating.
"""

from __future__ import annotations

from dataclasses import dataclass

import re

import numpy as np
import ollama

from prototype.pillar2_mapping import embed_texts, retrieve_by_similarity


def _strip_think(text: str) -> str:
    """Remove <think>...</think> blocks from deepseek-r1 output."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

LLM_MODEL = "deepseek-r1:8b"

ANSWER_PROMPT = """\
Answer the question using ONLY the provided context. If the context
does not contain enough information, say so.

Context:
{context}

Question: {query}

Answer:"""


@dataclass
class StandardRAGResult:
    retrieved_texts: list[str]
    retrieved_scores: list[float]
    answer: str
    context_sent: str


def run_standard_rag(
    query: str,
    corpus: list[str],
    top_k: int = 5,
    corpus_embeddings: np.ndarray | None = None,
) -> StandardRAGResult:
    """Run the standard RAG pipeline: embed → rank → top-k → LLM."""
    print("\n" + "=" * 60)
    print("STANDARD RAG (vector similarity only)")
    print("=" * 60)

    # Retrieve
    results, embeddings = retrieve_by_similarity(
        query, corpus, top_k=top_k, corpus_embeddings=corpus_embeddings
    )

    print(f"\n  Top-{top_k} by cosine similarity:")
    for r in results:
        print(f"    [{r.score:.3f}] {r.text[:80]}")

    # Build context
    context = "\n".join(f"- {r.text}" for r in results)

    # Generate answer
    prompt = ANSWER_PROMPT.format(context=context, query=query)
    print("\n  Generating answer...")

    try:
        response = ollama.chat(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.3, "num_predict": 1024},
        )
        answer = _strip_think(response["message"]["content"])
    except Exception as e:
        answer = f"[LLM error: {e}]"

    return StandardRAGResult(
        retrieved_texts=[r.text for r in results],
        retrieved_scores=[r.score for r in results],
        answer=answer,
        context_sent=context,
    )
