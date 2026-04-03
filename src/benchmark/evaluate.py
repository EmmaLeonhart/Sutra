"""Evaluation harness for the CVD benchmark.

Scores a model on CVD items by comparing the log-probability of each
multiple-choice answer given the passage + question as context. The model
"picks" whichever choice has the highest log-prob continuation.

This is a zero-shot, generation-free evaluation: no sampling needed,
just forward passes to compute token likelihoods.
"""

from __future__ import annotations

import json
import csv
from dataclasses import dataclass, field, asdict
from pathlib import Path

import torch
from transformers import GPT2Tokenizer

from .cvd_dataset import get_dataset, get_dataset_by_category, CATEGORIES


@dataclass
class ItemResult:
    """Result for a single CVD item."""
    category: str
    question: str
    correct_idx: int
    predicted_idx: int
    is_correct: bool
    choice_logprobs: list[float]
    violation_hint: str


@dataclass
class EvalResult:
    """Aggregated evaluation results."""
    alpha: float
    temperature: float
    accuracy: float
    accuracy_by_category: dict[str, float]
    num_items: int
    item_results: list[ItemResult] = field(default_factory=list)


def score_choice(model, tokenizer, context: str, choice: str, device: str) -> float:
    """Compute mean log-probability of `choice` tokens given `context`.

    Args:
        model: A GPT2LMHeadModel (or InquisitiveGPT2-wrapped model).
        tokenizer: The tokenizer.
        context: The passage + question prefix.
        choice: A candidate answer string.
        device: torch device string.

    Returns:
        Mean log-probability of the choice tokens.
    """
    # Encode context and choice separately to know the boundary
    context_ids = tokenizer.encode(context, add_special_tokens=False)
    choice_ids = tokenizer.encode(" " + choice, add_special_tokens=False)

    input_ids = torch.tensor([context_ids + choice_ids], device=device)

    with torch.no_grad():
        outputs = model(input_ids)
        logits = outputs.logits  # [1, seq_len, vocab_size]

    # Log-softmax over vocabulary
    log_probs = torch.log_softmax(logits, dim=-1)

    # Score only the choice tokens (starting after context)
    choice_start = len(context_ids)
    choice_log_prob = 0.0
    for i, token_id in enumerate(choice_ids):
        # Probability of token at position (choice_start + i) given prefix
        choice_log_prob += log_probs[0, choice_start + i - 1, token_id].item()

    # Mean log-prob per token (normalize for choice length)
    return choice_log_prob / max(len(choice_ids), 1)


def evaluate_model(
    model,
    tokenizer,
    device: str = "cpu",
    alpha: float = 0.0,
    temperature: float = 1.0,
    categories: list[str] | None = None,
) -> EvalResult:
    """Run the CVD benchmark on a model.

    Args:
        model: A GPT2LMHeadModel with InquisitiveAttention layers.
        tokenizer: The GPT-2 tokenizer.
        device: torch device.
        alpha: The alpha value being tested (for record-keeping).
        temperature: Temperature value (for record-keeping; doesn't affect
            log-prob scoring directly).
        categories: If specified, only evaluate these categories.

    Returns:
        EvalResult with accuracy and per-item details.
    """
    dataset = get_dataset()
    if categories:
        dataset = [item for item in dataset if item["category"] in categories]

    item_results = []

    for item in dataset:
        context = f"{item['passage']}\n\nQuestion: {item['question']}\nAnswer:"

        choice_logprobs = []
        for choice in item["choices"]:
            lp = score_choice(model, tokenizer, context, choice, device)
            choice_logprobs.append(lp)

        predicted_idx = max(range(len(choice_logprobs)), key=lambda i: choice_logprobs[i])
        is_correct = predicted_idx == item["correct"]

        item_results.append(ItemResult(
            category=item["category"],
            question=item["question"],
            correct_idx=item["correct"],
            predicted_idx=predicted_idx,
            is_correct=is_correct,
            choice_logprobs=choice_logprobs,
            violation_hint=item["violation_hint"],
        ))

    # Aggregate
    accuracy = sum(r.is_correct for r in item_results) / max(len(item_results), 1)

    accuracy_by_cat = {}
    for cat in CATEGORIES:
        cat_results = [r for r in item_results if r.category == cat]
        if cat_results:
            accuracy_by_cat[cat] = sum(r.is_correct for r in cat_results) / len(cat_results)

    return EvalResult(
        alpha=alpha,
        temperature=temperature,
        accuracy=accuracy,
        accuracy_by_category=accuracy_by_cat,
        num_items=len(item_results),
        item_results=item_results,
    )


def save_results(results: list[EvalResult], output_path: str | Path) -> None:
    """Save a list of EvalResults to a JSON file."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    data = []
    for r in results:
        d = asdict(r)
        # item_results can be large; keep them but they're serializable
        data.append(d)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def save_summary_csv(results: list[EvalResult], output_path: str | Path) -> None:
    """Save a summary CSV with one row per (alpha, temperature) configuration."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        header = ["alpha", "temperature", "accuracy", "num_items"] + [
            f"accuracy_{cat}" for cat in CATEGORIES
        ]
        writer.writerow(header)

        for r in results:
            row = [r.alpha, r.temperature, f"{r.accuracy:.4f}", r.num_items]
            for cat in CATEGORIES:
                row.append(f"{r.accuracy_by_category.get(cat, 0.0):.4f}")
            writer.writerow(row)
