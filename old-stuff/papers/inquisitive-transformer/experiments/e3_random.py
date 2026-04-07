"""Experiment 3: Random alpha per layer.

Question: Is structure necessary, or just diversity?

Each layer gets a random alpha drawn from [-alpha_scale, +alpha_scale].
If the split experiment (E2) outperforms this, then structured assignment
matters. If this performs similarly, mere diversity is enough.
"""

import random

from experiments.common import get_base_parser, load_model, run_alpha_sweep, run_temperature_control


def make_configure_random(seed: int):
    """Create a configure function with a fixed random seed for reproducibility."""

    def configure_random(model, alpha):
        """Assign random alpha in [-|alpha|, +|alpha|] to each layer."""
        rng = random.Random(seed)
        n_layers = len(model.model.transformer.h)
        scale = abs(alpha)

        for i in range(n_layers):
            layer_alpha = rng.uniform(-scale, scale)
            model.set_alpha(layer_alpha, layers=[i])

    return configure_random


def main():
    parser = get_base_parser("E3: Random alpha per layer")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument(
        "--num-trials", type=int, default=3,
        help="Number of random trials to average over",
    )
    args = parser.parse_args()

    model = load_model(args)

    print("\n" + "=" * 60)
    print("EXPERIMENT 3: Random Alpha")
    print(f"Random alpha per layer, {args.num_trials} trial(s)")
    print("=" * 60)

    all_trial_results = []
    for trial in range(args.num_trials):
        seed = args.seed + trial
        print(f"\n--- Trial {trial + 1}/{args.num_trials} (seed={seed}) ---")

        results = run_alpha_sweep(
            model, args.alphas, f"e3_random_trial{trial}",
            args.output_dir, configure_fn=make_configure_random(seed),
        )
        all_trial_results.append(results)

    # Print averaged summary
    print("\n" + "=" * 60)
    print("E3 SUMMARY (averaged across trials)")
    print("-" * 40)
    for alpha_idx, alpha in enumerate(args.alphas):
        accs = [trial[alpha_idx].accuracy for trial in all_trial_results]
        mean_acc = sum(accs) / len(accs)
        print(f"  alpha_scale={abs(alpha):.2f}  mean_accuracy={mean_acc:.2%}")


if __name__ == "__main__":
    main()
