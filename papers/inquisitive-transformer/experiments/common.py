"""Shared utilities for experiment scripts."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import torch

from src.inquisitive_gpt2 import InquisitiveGPT2
from src.benchmark.evaluate import evaluate_model, save_results, save_summary_csv, EvalResult

# Default alpha sweep from the technical spec
ALPHA_SWEEP = [-1.0, -0.5, -0.25, 0.0, 0.25, 0.5, 1.0]
TEMPERATURE_SWEEP = [0.5, 1.0, 1.5]


def get_base_parser(description: str) -> argparse.ArgumentParser:
    """Create an argument parser with common experiment flags."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--model", default="gpt2", help="HuggingFace model name (default: gpt2)"
    )
    parser.add_argument(
        "--device", default=None, help="Device (default: auto-detect cuda/cpu)"
    )
    parser.add_argument(
        "--output-dir", default="results", help="Directory for output files"
    )
    parser.add_argument(
        "--alphas", nargs="+", type=float, default=ALPHA_SWEEP,
        help="Alpha values to sweep",
    )
    parser.add_argument(
        "--temperatures", nargs="+", type=float, default=TEMPERATURE_SWEEP,
        help="Temperature values for control sweep",
    )
    parser.add_argument(
        "--surprise-fn", default="causal_running_mean",
        help="Surprise function to use",
    )
    parser.add_argument(
        "--temperature-control", action="store_true",
        help="Also sweep temperature as a control comparison",
    )
    return parser


def load_model(args) -> InquisitiveGPT2:
    """Load the model from args."""
    print(f"Loading model: {args.model}")
    model = InquisitiveGPT2.from_pretrained(args.model, device=args.device)
    model.set_surprise_function(args.surprise_fn)
    print(f"Model loaded on {model.device}")
    return model


def run_alpha_sweep(
    model: InquisitiveGPT2,
    alphas: list[float],
    experiment_name: str,
    output_dir: str,
    configure_fn=None,
) -> list[EvalResult]:
    """Run the CVD benchmark across a sweep of alpha values.

    Args:
        model: The loaded InquisitiveGPT2 model.
        alphas: Alpha values to test.
        experiment_name: Name for output files.
        output_dir: Directory for results.
        configure_fn: Optional callable(model, alpha) to set up alpha
            in an experiment-specific way. If None, uses model.set_alpha(alpha).

    Returns:
        List of EvalResult, one per alpha value.
    """
    results = []
    output_path = Path(output_dir)

    for alpha in alphas:
        if configure_fn:
            configure_fn(model, alpha)
        else:
            model.set_alpha(alpha)

        print(f"\n{'='*60}")
        print(f"[{experiment_name}] alpha={alpha:.2f}")
        print(f"  Layer alphas: {model.get_alphas()}")

        start = time.time()
        result = evaluate_model(
            model.model, model.tokenizer, device=model.device, alpha=alpha,
        )
        elapsed = time.time() - start

        print(f"  Accuracy: {result.accuracy:.2%} ({result.num_items} items, {elapsed:.1f}s)")
        for cat, acc in result.accuracy_by_category.items():
            print(f"    {cat}: {acc:.2%}")

        results.append(result)

    # Save results
    save_results(results, output_path / f"{experiment_name}_full.json")
    save_summary_csv(results, output_path / f"{experiment_name}_summary.csv")
    print(f"\nResults saved to {output_path / experiment_name}_*.{{json,csv}}")

    return results


def run_temperature_control(
    model: InquisitiveGPT2,
    temperatures: list[float],
    experiment_name: str,
    output_dir: str,
) -> list[EvalResult]:
    """Run CVD benchmark across temperatures (with alpha=0) as a control."""
    results = []
    output_path = Path(output_dir)
    model.set_alpha(0.0)

    for temp in temperatures:
        print(f"\n{'='*60}")
        print(f"[{experiment_name}-temp-control] temperature={temp:.2f}, alpha=0.0")

        result = evaluate_model(
            model.model, model.tokenizer, device=model.device,
            alpha=0.0, temperature=temp,
        )

        print(f"  Accuracy: {result.accuracy:.2%} ({result.num_items} items)")
        results.append(result)

    save_summary_csv(results, output_path / f"{experiment_name}_temp_control.csv")
    return results
